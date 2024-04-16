from __future__ import annotations

import csv
import functools
import io
import logging
import re
import typing
from ast import literal_eval
from collections import defaultdict
from dataclasses import dataclass, replace

from lxml import etree

from odoo.tools import SetDefinitions

if typing.TYPE_CHECKING:
    from collections.abc import Iterator


_logger = logging.getLogger(__name__)
_silent = logging.getLogger('silent')
_silent.setLevel(logging.CRITICAL)

REF_RE = re.compile(r"""ref\((?P<quote>["'])(?P<ref>[\w\.]+)(?P=quote)\)""")
TRUE_DOMAIN_RE = re.compile(r"""\[\]|\[\(1,\s*(?P<quote>["'])=(?P=quote),\s*1\)\]""")
FALSE_DOMAIN_RE = re.compile(r"""\[\(0,\s*(?P<quote>["'])=(?P=quote),\s*1\)\]""")
EXCLUSIVE_GROUPS = {'base.group_user', 'base.group_portal', 'base.group_public'}

XML_TAGS = ('delete', 'function', 'menuitem', 'record', 'template')

MODES = {
    'r': 'perm_read',
    'w': 'perm_write',
    'c': 'perm_create',
    'd': 'perm_unlink',
}


@dataclass
class Access:
    """ A common data structure to represent ir.model.access, ir.rule and ir.access records. """
    id: str
    name: str
    model: str
    group: str | None
    operations: set[str]
    domain: str = ""

    @property
    def module(self):
        return self.id.split('.', 1)[0]

    @property
    def suffix(self):
        return self.id.split('.', 1)[1]

    def subsumes(self, other: Access):
        """ Return whether ``self`` is more general than ``other``. """
        return (
            self.model == other.model
            and self.operations >= other.operations
            and (not self.domain or self.domain == other.domain)
        )


WELCOME_MESSAGE = """
This script is generating ir.access.csv files from existing data files.

The logging messages should be interpreted as:
 - INFO: normal operation
 - WARNING: partially handled case, should be checked and potentially fixed up
 - ERROR: not handled case, requires manual fixup

This script converts ir.rule records to corresponding ir.access records,
limiting the operations to the ones allowed by ir.model.access records from
the module and its dependencies.
"""


#
# upgrade(file_manager) creates an object that performs the upgrade at creation
#
class upgrade:
    def __init__(self, file_manager):
        self.file_manager = file_manager

        _logger.info(WELCOME_MESSAGE)

        modules = self.file_manager.get_modules()

        # determine which modules have a security directory before removing files
        has_security = {
            module
            for module in modules
            if any(fname.startswith('security/') for fname in self.get_manifest(module)['data'])
        }

        group_defs = self.get_group_definitions()

        # extract ir.model.access (ir_perms) and ir.rule (ir_rules)
        ir_perms = defaultdict(list)
        ir_rules = defaultdict(list)
        for module in modules:
            for perm in self.extract_perms(module):
                if perm.group and perm.operations:
                    ir_perms[perm.model].append(perm)
            for rule in self.extract_rules(module):
                if rule.operations:
                    ir_rules[rule.model].append(rule)

        # detect misconfigurations
        for model, perms in sorted(ir_perms.items()):
            perms = [perm for perm in perms if perm.group is not None]
            rules = [rule for rule in ir_rules[model] if rule.group is not None]
            if not (perms and rules):
                continue
            for operation in MODES:
                # determines acls that do not imply having rules, and non-trivial rules
                for perm in perms:
                    if operation not in perm.operations or any(
                        operation in rule.operations
                        and rule.group in group_defs.implied(perm.group)
                        and rule.module in self.get_installed_modules(perm.module)
                        for rule in rules
                    ):
                        continue
                    disjoint_groups = set(group_defs.disjoint(perm.group))
                    rules_with_domain = [
                        rule
                        for rule in rules
                        if operation in rule.operations and rule.domain
                        and rule.group not in disjoint_groups
                    ]
                    if not rules_with_domain:
                        continue
                    # This perm give some permission to all records in the model,
                    # but when combined with another group with rules, those
                    # permissions are granted to less records.
                    groups_with_perm = {
                        perm.group for perm in perms if operation in perm.operations
                    }
                    lines = [f"WARNING with {model=}, {operation=}"]
                    lines.append("    acl group without rules, giving access to ALL records:")
                    lines.append(f"     - {perm.group}: acl {perm.id}")
                    lines.append("    may interact with rules in groups, giving access to LESS records:")
                    for rule in sorted(rules_with_domain, key=lambda rule: rule.group):
                        if rule.group in disjoint_groups:
                            continue
                        has_perm = any(group in groups_with_perm for group in group_defs.implied(rule.group))
                        extra = " (with acl)" if has_perm else ""
                        lines.append(f"     - {rule.group}: rule {rule.id}{extra}")
                    lines.append("")
                    _logger.warning("\n".join(lines))

        #
        # Let's infer ir.access records from ir.model.access and ir.rule. The
        # result should reproduce as closely as possible the effects of the
        # existing mechanism based on access and rules. The basic principle
        # is: if group A implies group B, every access in group B is valid in
        # group A.
        #
        # Consider groups A, B, C such that A implies B, which itself implies C.
        # In terms of set of users, this means A ≤ B ≤ C. All the inference
        # cases can be rewritten as the following example, where we consider
        # access and rules for a given model, and there is no ir.rule for
        # operation "r".
        #
        #       group A           ≤     group B           ≤     group C
        #
        #   ir.rule("wc", DomA)     ir.model.access("rw")   ir.rule("wc", DomC)
        #
        #   ir.access("w", DomA)    ir.access("r", [])
        #                           ir.access("w", DomC)
        #

        # generate ir.access (grouped by module, model and group)
        ir_accesses = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        def add_access(access):
            accesses = ir_accesses[access.module][access.model][access.group]
            if any(acc.subsumes(access) for acc in accesses):
                return
            accesses[:] = (acc for acc in accesses if not access.subsumes(acc))
            accesses.append(access)

        # determine the operations permitted with no corresponding ir.rule; for
        # those operations, add an ir.access without domain
        for perm in (x for xs in ir_perms.values() for x in xs):
            # prepare entries in the same order as permissions
            ir_accesses[perm.module][perm.model][perm.group]
            perm_groups = set(group_defs.implied(perm.group))
            perm_modules = self.get_installed_modules(perm.module)
            if unrestricted_operations := {
                op for op in perm.operations if not any(
                    op in rule.operations and rule.group in perm_groups and rule.module in perm_modules
                    for rule in ir_rules[perm.model]
                )
            }:
                add_access(replace(perm, operations=unrestricted_operations))

        # now map ir.rules to corresponding ir.access for the permitted operations
        for rule in (x for xs in ir_rules.values() for x in xs):
            if rule.group is None:
                ir_accesses[rule.module][rule.model][rule.group].append(rule)
                continue

            # add rule in all subgroups that have a corresponding ir.model.access
            added = False

            for subgroup in group_defs.implying(rule.group):
                groups = set(group_defs.implied(rule.group)) if subgroup == rule.group else {subgroup}

                # separate permissions that are present when rule.module is
                # installed from the ones that are in other modules; the first
                # set generates some access in rule.module, while the other
                # ones generates some access in their respective module
                rule_modules = self.get_installed_modules(rule.module)
                bymodule = defaultdict(list)
                for perm in ir_perms[rule.model]:
                    if perm.group in groups:
                        if perm.module in rule_modules:
                            bymodule[rule.module].append(perm)
                        elif rule.module in self.get_installed_modules(perm.module):
                            bymodule[perm.module].append(perm)

                for module, perms in bymodule.items():
                    # determine effective operations for subgroup
                    if operations := {
                        op
                        for op in rule.operations
                        if any(op in perm.operations for perm in perms)
                    }:
                        added = True
                        newid = f"{module}.{rule.suffix}"
                        add_access(replace(rule, id=newid, group=subgroup, operations=operations))

            if not added and not FALSE_DOMAIN_RE.match(rule.domain):
                # ir.rules with a non-falsy domain that never apply look like a
                # configuration bug; mention alternative groups that provide
                # access and could be implied
                groups_with_permission = {
                    perm.group
                    for perm in ir_perms[rule.model]
                    if perm.group is not None and not rule.operations.isdisjoint(perm.operations)
                } - {
                    *group_defs.disjoint(rule.group),
                }
                _logger.warning(
                    "WARNING ir.rule %s without effective operations for group %s\n"
                    "    compatible ir.model.access found in groups: %s",
                    rule.id, rule.group, ", ".join(sorted(groups_with_permission) or ["none!"]),
                )

        # create ir.access.csv files
        xids = set()

        def uniquify(xid):
            if xid not in xids:
                return xids.add(xid) or xid
            for index in range(1, 100):
                xid2 = f"{xid}_{index}"
                if xid2 not in xids:
                    return xids.add(xid2) or xid2
            raise ValueError(f"Too many occurrences of {xid}")

        for module, bymodule in ir_accesses.items():
            with io.StringIO(newline='') as output:
                writer = csv.writer(output, lineterminator='\n')
                writer.writerow(["id", "name", "model_id", "group_id/id", "operation", "domain"])
                for access in (y for xs in bymodule.values() for ys in xs.values() for y in ys):
                    writer.writerow([
                        uniquify(access.id).removeprefix(f"{module}."),
                        access.name,
                        access.model,
                        access.group,
                        "".join(op for op in MODES if op in access.operations),
                        access.domain,
                    ])
                content = output.getvalue()

            file_name = 'security/ir.access.csv' if module in has_security else 'ir.access.csv'
            self.file_manager.get_file(module, file_name).content = content
            self.add_to_manifest(module, file_name)

    @functools.cache
    def get_manifest(self, module: str) -> dict:
        """ Return the manifest dict of the given module. """
        file = self.file_manager.get_file(module, "__manifest__.py")
        manifest = literal_eval(file.content)
        manifest.setdefault('depends', [])
        manifest.setdefault('data', [])
        return manifest

    def add_to_manifest(self, module: str, file_name: str):
        """ Add the given 'data' file to its module's manifest. """

        # add it to the manifest's dict
        manifest = self.get_manifest(module)
        assert file_name not in manifest['data'], f"ERROR {module}: file {file_name!r} found in manifest['data']"
        manifest['data'].append(file_name)

        # add it to the manifest's file
        file = self.file_manager.get_file(module, "__manifest__.py")
        content = file.content

        pattern = r"""
            ^ (?P<indent>\s*) (?P<quote>['"]) data (?P=quote) \s* : \s*
            \[ (?P<items>[^\]]*[^\]\s,])? (?P<comma>,?) (?P<newline>\n?) (?P<spaces>\s*) \]
        """
        match = re.search(pattern, content, re.MULTILINE | re.VERBOSE)
        if not match:
            _logger.error("ERROR %s: Cannot add %s to manifest, please add manually", module, file_name)
            return

        if match['newline']:  # list on several lines, add a line
            pos = match.start('newline')
            comma = "," if match['items'] and not match['comma'] else ""
            indent = match['indent']
            content = f"{content[:pos]}{comma}\n{indent}    {file_name!r},{content[pos:]}"
        elif match['items']:  # non-empty list, add an item
            pos = match.start('spaces')
            comma = "," if not match['comma'] else ""
            content = f"{content[:pos]}{comma} {file_name!r}{content[pos:]}"
        else:  # empty list
            pos = match.start('spaces')
            content = f"{content[:pos]}{file_name!r}{content[pos:]}"

        file.content = content

    def remove_from_manifest(self, module: str, file_name: str):
        """ Remove the given file from its module's manifest. """

        # remove it from the manifest's dict
        manifest = self.get_manifest(module)
        assert file_name in manifest['data'], f"File {file_name!r} not found in manifest['data']"
        manifest['data'].remove(file_name)

        # remove it from the manifest's file
        file_pattern = re.escape(str(file_name))
        pattern = rf"""\s*(?P<quote>['"]){file_pattern}(?P=quote),?"""

        file = self.file_manager.get_file(module, "__manifest__.py")
        file.content = re.sub(pattern, "", file.content, flags=re.MULTILINE)

    @functools.cache
    def get_installed_modules(self, module: str) -> set[str]:
        """ Return ``module`` with all its dependencies. """
        todo = [module]
        result = {'base'}
        for mod in todo:
            if mod not in result:
                result.add(mod)
                todo.extend(self.get_manifest(mod)['depends'])
        return result

    def extract_perms(self, module: str) -> Iterator[Access]:
        """ Extract ir.model.access or ir.access records from the given module. """
        manifest = self.get_manifest(module)
        # beware: manifest['data'] may be modified in-place
        for file_name in list(manifest['data']):
            if 'security' in file_name or 'access' in file_name:
                if file_name.endswith('ir.model.access.csv'):
                    yield from self.extract_perms_from_csv(module, file_name)
                elif file_name.endswith('.xml'):
                    yield from self.extract_perms_from_xml(module, file_name)

    def extract_perms_from_csv(self, module: str, file_name: str) -> Iterator[Access]:
        assert file_name.endswith('ir.model.access.csv'), f"Unexpected CSV file {file_name}"

        file = self.file_manager.get_file(module, file_name)
        reader = csv.reader(io.StringIO(file.content, newline=''), lineterminator='\n')

        fields = next(reader)
        model_field = next(field for field in fields if field.startswith('model_id'))
        group_field = next(field for field in fields if field.startswith('group_id'))

        lines_to_keep = []

        for line in reader:
            if not line:
                continue
            line_data = dict(zip(fields, line, strict=True))

            name = line_data['name']
            xid = with_prefix(module, line_data['id'])
            if not xid.startswith(f"{module}."):
                _logger.error("ERROR %s: modified ir.model.access, skipping %s in %s", module, xid, file_name)
                lines_to_keep.append(line)
                continue
            model = self.get_model_name(module, line_data[model_field])
            if not model:
                _logger.error("ERROR %s: ir.model.access without model, skipping %s in %s", module, xid, file_name)
                lines_to_keep.append(line)
                continue
            operations = {op for op, fname in MODES.items() if int(line_data[fname] or "0")}
            domain = make_domain(line_data.get('domain'))
            group = line_data[group_field]
            if not group:
                _logger.info("INFO %s: ir.model.access without group, base.group_everyone instead: %s in %s", module, xid, file_name)
                group = 'base.group_everyone'

            yield Access(xid, name, model, with_prefix(module, group), operations, domain)

        if lines_to_keep:
            with io.StringIO(newline='') as output:
                writer = csv.writer(output, lineterminator='\n')
                writer.writerow(fields)
                for line in lines_to_keep:
                    writer.writerow(line)
                content = output.getvalue()
            file.content = content
        else:
            file.content = None
            self.remove_from_manifest(module, file_name)

    def extract_perms_from_xml(self, module: str, file_name: str) -> Iterator[Access]:
        file = self.file_manager.get_file(module, file_name)
        tree = etree.fromstring(file.content.encode())
        nodes = []

        for node in tree.xpath("//record[@model='ir.model.access']"):
            xid = with_prefix(module, node.get('id'))
            if not xid.startswith(f"{module}."):
                _logger.error("ERROR %s: modified ir.model.access, skipping %s in %s", module, xid, file_name)
                continue
            if (
                (field := node.find("./field[@name='active']")) is not None
                and (field.text in ("0", "false", "off") or field.get('eval') in ("0", "False"))
            ):
                _logger.error("ERROR %s: ir.model.access with field 'active', skipping %s in %s", module, xid, file_name)
                continue
            name = name_node.text if (name_node := node.find("./field[@name='name']")) is not None else None
            model = self.get_model_name(module, get_xml_model_xid(node))
            if not model:
                _logger.error("ERROR %s: ir.model.access without model, skipping %s in %s", module, xid, file_name)
                continue
            operations = {
                op
                for op, fname in MODES.items()
                if (opnode := node.find(f"./field[@name='{fname}']")) is not None
                and literal_eval(opnode.get('eval') or opnode.text)
            }
            domain = make_domain()
            group = get_xml_group_xid(node)
            if not group:
                _logger.info("INFO %s: ir.model.access without group, base.group_everyone instead: %s in %s", module, xid, file_name)
                group = 'base.group_everyone'

            yield Access(xid, name, model, with_prefix(module, group), operations, domain)
            nodes.append(node)

        if nodes:
            self.remove_from_etree(tree, nodes)
            if any(tree.find(f".//{tag}") is not None for tag in XML_TAGS):
                file.content = etree.tostring(tree).decode() + "\n"
            else:
                file.content = None
                self.remove_from_manifest(module, file_name)

    def extract_rules(self, module: str) -> Iterator[Access]:
        """ Extract ir.rule records from the given module. """
        manifest = self.get_manifest(module)
        # beware: manifest['data'] may be modified in-place
        for file_name in list(manifest['data']):
            if 'security' in file_name and file_name.endswith('.xml'):
                yield from self.extract_rules_from_xml(module, file_name)

    def extract_rules_from_xml(self, module: str, file_name: str) -> Iterator[Access]:
        file = self.file_manager.get_file(module, file_name)
        tree = etree.fromstring(file.content.encode())
        nodes = []

        for node in tree.xpath("//record[@model='ir.rule']"):
            xid = with_prefix(module, node.get('id'))
            if not xid.startswith(f"{module}."):
                _logger.error("ERROR %s: modified ir.rule, skipping %s in %s", module, xid, file_name)
                continue
            if (
                (field := node.find("./field[@name='active']")) is not None
                and (field.text in ("0", "false", "off") or field.get('eval') in ("0", "False"))
            ):
                _logger.error("ERROR %s: ir.rule with field 'active', skipping %s in %s", module, xid, file_name)
                continue
            name = node.findtext("./field[@name='name']")
            model = self.get_model_name(module, get_xml_model_xid(node))
            if not model:
                _logger.error("ERROR %s: ir.rule without model, skipping %s in %s", module, xid, file_name)
                continue
            groups = [
                with_prefix(module, match['ref'])
                for group_node in node.findall("./field[@name='groups']")
                for match in REF_RE.finditer(group_node.get('eval'))
            ]
            operations = {
                op
                for op, fname in MODES.items()
                if (opnode := node.find(f"./field[@name='{fname}']")) is None
                or literal_eval(opnode.get('eval'))
            }
            domain = make_domain(node.findtext("./field[@name='domain_force']"))
            if groups:
                for group in groups:
                    yield Access(xid, name, model, group, operations, domain)
            else:
                yield Access(xid, name, model, None, operations, domain)

            nodes.append(node)

        if nodes:
            self.remove_from_etree(tree, nodes)
            if any(tree.find(f".//{tag}") is not None for tag in XML_TAGS):
                file.content = etree.tostring(tree).decode() + "\n"
            else:
                file.content = None
                self.remove_from_manifest(module, file_name)

    def remove_from_etree(self, tree: etree.Element, nodes: list):
        """ Remove the given nodes from the XML tree, and return it serialized. """
        for node in nodes:
            while (parent := node.getparent()) is not None:
                parent.remove(node)
                node = parent
                if len(node):
                    break

    def get_model_name(self, module: str, xid: str | None) -> str | None:
        """ Retrieve the model name from a model's external id or model name. """
        if not xid:
            return None
        model_xid = with_prefix(module, xid)
        return self.get_model_xids().get(model_xid, xid)

    @functools.cache
    def get_model_xids(self) -> dict[str, str]:
        """ Return a mapping from model external ids to model names. """
        result = {}
        for file in self.file_manager:
            if file.path.suffix == '.py':
                module = file.addon.name
                for model_name in extract_model_names(file):
                    result[model_xmlid(module, model_name)] = model_name
        return result

    @functools.cache
    def get_group_definitions(self) -> GroupDefinitions:
        definitions: dict[str, dict] = {}

        for module in self.file_manager.get_modules():
            for file_name in self.get_manifest(module)['data']:
                if not file_name.endswith('.xml'):
                    continue
                for info in self._get_group_from_xml(module, file_name):
                    xid = info['ref']
                    group = definitions.get(xid)
                    if group is None:
                        definitions[xid] = group = {'ref': xid, 'supersets': [], 'disjoints': []}
                    group['supersets'].extend(info.get('supersets', ()))
                    group['disjoints'].extend(info.get('disjoints', ()))

        # those ones may be missing from data files
        definitions['base.group_user']['disjoints'].extend(['base.group_portal'])
        definitions['base.group_portal']['disjoints'].extend(['base.group_public'])
        definitions['base.group_public']['disjoints'].extend(['base.group_user'])

        return GroupDefinitions(definitions)  # type: ignore[arg-type]

    def _get_group_from_xml(self, module: str, file_name: str) -> Iterator[dict]:
        """ Retrieve the group definitions from a given XML file. """
        try:
            file = self.file_manager.get_file(module, file_name)
            tree = etree.fromstring(file.content.encode())
        except UnicodeDecodeError:
            _logger.info("Unexpected encoding, skip %s/%s", module, file_name)
            return

        for node in tree.xpath("//record[@model='res.groups']"):
            xid = with_prefix(module, node.get('id'))
            yield {
                'ref': xid,
                'supersets': [
                    with_prefix(module, match['ref'])
                    for field_node in node.findall("./field[@name='implied_ids']")
                    for match in REF_RE.finditer(field_node.get('eval'))
                ],
                'disjoints': [
                    with_prefix(module, match['ref'])
                    for field_node in node.findall("./field[@name='disjoint_ids']")
                    for match in REF_RE.finditer(field_node.get('eval'))
                ],
            }
            for field_node in node.findall("./field[@name='implied_by_ids']"):
                for match in REF_RE.finditer(field_node.get('eval')):
                    yield {
                        'ref': with_prefix(module, match['ref']),
                        'supersets': [xid],
                    }


class GroupDefinitions(SetDefinitions):
    """ Simple extension for methods ``implied`` and ``implying``. """

    def implied(self, group):
        """ Return all groups implied by the given ``group``, including ``group``. """
        yield group
        yield from self.get_superset_ids([group])

    def implying(self, group):
        """ Return all groups implying the given ``group``, including ``group``. """
        yield group
        yield from self.get_subset_ids([group])

    def disjoint(self, group):
        """ Return all groups disjoint from the given ``group``. """
        return self.get_disjoint_ids([group])


def with_prefix(module: str, xid: str) -> str:
    """ Return a fully qualified external id. """
    return xid and (xid if '.' in xid else f"{module}.{xid}")


def get_xml_model_xid(node) -> str | None:
    """ Retrieve the value of field 'model_id' from the given XML record. """
    model_node = node.find("./field[@name='model_id']")
    if model_node is None:
        return None
    if (model := model_node.get('ref')):
        return model
    domain = model_node.get('search')
    for item in literal_eval(domain):
        if item[0] == 'model' and item[1] == '=':
            return f"model_{item[2].replace('.', '_')}"
    return None


def get_xml_group_xid(node) -> str | None:
    """ Retrieve the value of field 'group_id' from the given XML record. """
    group_node = node.find("./field[@name='group_id']")
    if group_node is None:
        return None
    return group_node.get('ref')


def make_domain(domain: str | None = None) -> str:
    """ Normalize the given domain. """
    return "" if domain is None or TRUE_DOMAIN_RE.match(domain) else domain


# matches all the lines like one of those:
#   class <identifier> (... Model ...
#       _name = <str>
#       _inherit = <str>
RE_MODEL_DEF = re.compile(
    r"""
        (
            ^class \s+ (?P<class>\w+) \s* \( [^)]* \b \w*Model \b
        )|(
            ^\s{4,8} (?P<attr>_name|_inherit) \s* = \s*
            (?P<attrs> (\w+ \s* = \s*)*)
            (?P<quote>['"]) (?P<model>[\w.]+) (?P=quote)
        )
    """,
    re.VERBOSE)

# matches the places where to insert a '.' in class_name_to_model_name()
RE_DOT_PLACE = re.compile(r"(?<=[^_])([A-Z])")


def extract_model_names(file) -> list[str]:
    """ Return a list of model names defined in the given file. """
    result: list[str] = []
    class_name = None
    name = None
    inherit = None

    def flush():
        if class_name:
            result.append(name or inherit or RE_DOT_PLACE.sub(r'.\1', class_name).lower())

    for line in file.content.splitlines():
        match = RE_MODEL_DEF.match(line)
        if not match:
            continue

        if match['class']:
            # we found a new class definition
            flush()
            class_name, name, inherit = match['class'], None, None

        elif class_name and match['model']:
            # we found a model name (_name)
            if match['attr'] == '_name':
                name = match['model']
            else:
                inherit = match['model']

    flush()
    return result


def model_xmlid(module, model_name):
    """ Return the XML id of the given model. """
    return '%s.model_%s' % (module, model_name.replace('.', '_'))
