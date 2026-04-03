from __future__ import annotations

import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..utils import xml

DEFINITION_PREFETCH_GROUP = 'Definitions'


class Blueprint(models.Model):
    """
    Declarative definition of what synthetic data to create.

    A blueprint holds an XML or JSON definition describing which models to
    populate, how many records to create, and which generators to use for
    each field.  It supports simple inheritance via ``inherit_id``
    (XPath specs applied to the parent's XML).

    Blueprints are instantiated into ``populate.job`` records
    within a ``populate.session`` at execution time.
    """
    _name = 'populate.blueprint'
    _description = 'Data Population Blueprint'
    _parent_name = 'inherit_id'

    name = fields.Char("Blueprint Name", required=True)
    inherit_id = fields.Many2one(
        comodel_name='populate.blueprint',
        string='Inherited Blueprint',
        ondelete='set null',
        index=True,
        help="Blueprint to inherit from. Use XPath expressions in definition_xml to modify the parent.",
    )
    definition_xml = fields.Char("Raw XML Definition", prefetch=DEFINITION_PREFETCH_GROUP)
    definition_json = fields.Json("Raw JSON Definition", prefetch=DEFINITION_PREFETCH_GROUP)
    definition = fields.Json(
        string="JSON Definition",
        compute='_compute_definition',
        prefetch=DEFINITION_PREFETCH_GROUP,
        readonly=True,
    )

    _has_definition = models.Constraint(
        'CHECK(definition_xml IS NOT NULL OR definition_json IS NOT NULL)',
        "Either XML or JSON definition must be provided",
    )

    @api.constrains('definition_xml', 'definition_json', 'inherit_id')
    def _check_definition(self):
        self._check_inheritance_recursion()
        self._check_models_exist_in_definition()
        self._check_fields_exist_in_definition()

    def _check_inheritance_recursion(self):
        for blueprint in self.filtered('inherit_id'):
            if blueprint._has_cycle():
                raise ValidationError(self.env._("You cannot create recursive inherited blueprints."))

    def _check_models_exist_in_definition(self):
        exceptions = []
        for blueprint in self:
            for model in blueprint.definition:
                model_name = model['name']
                if model_name not in self.env:
                    pretty_definition = json.dumps(model, indent=2)
                    exceptions.append(
                        ValidationError(self.env._(
                            "Blueprint '%(blueprint)s': Model '%(model)s' doesn't exist.\n"
                            "Definition that failed:\n%(definition)s",
                            blueprint=blueprint.name,
                            model=model_name,
                            definition=pretty_definition,
                        )),
                    )
        if exceptions:
            raise ExceptionGroup(self.env._("Some blueprint's definition(s) have inexistent models used."), exceptions)

    def _check_fields_exist_in_definition(self):
        exceptions = []
        for blueprint in self:
            for model in blueprint.definition:
                model_name = model['name']
                if inexistent_fields := [
                    field_name
                    for field_name, attrs in model['fields'].items()
                    if field_name not in self.env[model_name]._fields
                       and not attrs.get('virtual', False)
                ]:
                    pretty_definition = json.dumps(model, indent=2)
                    exceptions.append(
                        ValidationError(self.env._(
                            "Blueprint '%(blueprint)s': Model '%(model)s' "
                            "doesn't have field(s): %(fields)s.\n"
                            "Definition that failed:\n%(definition)s",
                            blueprint=blueprint.name,
                            model=model_name,
                            fields=', '.join(repr(f) for f in inexistent_fields),
                            definition=pretty_definition,
                        )),
                    )
        if exceptions:
            raise ExceptionGroup(self.env._("Some blueprint's definition(s) have inexistent fields used."), exceptions)

    @api.depends('definition_xml', 'definition_json')
    def _compute_definition(self):
        """
        Compute the blueprint's definition in JSON.
        If both raw definitions are specified, the XML one takes precedence.
        If inherit_id is set, apply inheritance specs first.
        """
        for blueprint in self:
            resolved_definition = blueprint.get_resolved_definition()
            if resolved_definition:
                blueprint.definition = xml.parse(resolved_definition)
            else:
                blueprint.definition = blueprint.definition_json

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if definition_xml := vals.get('definition_xml'):
                vals['definition_xml'] = xml.ensure_root(definition_xml)
        return super().create(vals_list)

    def write(self, vals):
        if definition_xml := vals.get('definition_xml'):
            vals['definition_xml'] = xml.ensure_root(definition_xml)
        return super().write(vals)

    @api.private
    def get_resolved_definition(self):
        """Get the resolved XML definition of the blueprint, applying inheritance if needed."""
        self.ensure_one()

        if not self.definition_xml:
            return None

        if not self.inherit_id:
            return self.definition_xml

        parent_definition_xml = self.inherit_id.get_resolved_definition()
        if not parent_definition_xml:
            raise ValueError(self.env._(
                "The blueprint '%(parent)s' does not have an XML definition, but '%(child)s' inherit from it.",
                parent=self.inherit_id.name,
                child=self.name,
            ))

        try:
            return xml.apply_inheritance(parent_definition_xml, self.definition_xml)
        except ValueError as e:
            raise ValueError(self.env._(
                "Error applying blueprint inheritance from %(parent)s' to %(child)s: %(error)s",
                parent=self.inherit_id.name,
                child=self.name,
                error=e,
            ))

    def _register_hook(self):
        """Load populate data if the `populate` module was installed or upgraded."""
        super()._register_hook()
        # Local import to avoid import failure due to partially initialized module
        from .. import load_populate  # noqa: PLC0415

        if 'populate' in self.env.registry.updated_modules:
            load_populate(self.env)
