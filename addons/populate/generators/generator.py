from __future__ import annotations

import inspect
from abc import abstractmethod
from collections.abc import Generator as GeneratorABC
from collections.abc import Sequence
from functools import partial
from random import Random
from typing import TYPE_CHECKING, ClassVar, final

from odoo.fields import Domain
from odoo.tools import find_circular_dependency, str2bool, topological_sort
from odoo.tools.lru import LRU
from odoo.tools.safe_eval import const_eval

from ..utils.distributions import Distribution, UniformDistribution
from ..utils.orm import get_ref_domain
from odoo.addons.populate.utils.distributions import WeightedDistribution

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Mapping
    from typing import Any

    from odoo.api import DomainType, Environment, ValuesType
    from odoo.fields import Field

    from ..models.job import Job
    from ..models.session import Session
    from ..utils.orm import VirtualField

GENERATORS_REGISTRY = {}
MAX_RETRY = 10
NO_VALUE = object()
NO_UNIQ_VALUE = object()
DEFAULT_WEIGHT = 1


class Generator(GeneratorABC):
    """
    Defines the base class `Generator` used to manage and generate values based on field
    attributes specified in a populate job.

    Concrete subclasses are registered in a global registry for retrieval.

    They must define a `name` class attribute and are responsible for implementing
    the `_next` method for value generation. `__init__` can be overridden to specify custom
    initialization parameters. If attributes from the field definition need to be converted into
    `__init__` arguments, override the `get_kwargs` class method to handle the conversion.

    :ivar name: The unique name for the generator, used as its identifier in the registry
     and how it's referenced in blueprints.
    :ivar allowed_fields_type: A list of allowed field types for this generator,
     or `None` for no restriction.
    """
    name: ClassVar[str]
    allowed_fields_type: ClassVar[list[str] | None] = None

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        if not inspect.isabstract(cls):
            if cls.name is None:
                raise TypeError(
                    f"Concrete Generator subclass '{cls.__qualname__}' "
                    f"must define a 'name' class attribute.",
                )

            GENERATORS_REGISTRY[cls.name] = cls

    def _validate_field_type(self, field: Field | VirtualField):
        if self.allowed_fields_type is not None and field.type not in self.allowed_fields_type:
            raise TypeError(
                f"Incompatible field type '{field.type}'. "
                f"Expected field type(s): {self.allowed_fields_type}.",
            )

    def __init__(
        self,
        field: Field | VirtualField,
        env: Environment,
        rng: Random | None = None,
        job: Job | None = None,
        session: Session | None = None,
        valid_fields: Collection[str] | None = None,
        # Passed attributes
        values: Sequence[Any] | Mapping[Any, float] | None = None,
        depends: list[str] | None = None,
        null_frac: float = 0.3,
        distribution: Distribution | Callable[[Random], Distribution] | None = None,
        unique: bool = False,
        **kwargs,
    ):
        self._validate_field_type(field)

        self.field = field
        self.env = job.env if job else env

        if rng is None:
            rng = Random()

        self.rng = rng
        self.session = job.session_id if job else session
        self.job = job

        if valid_fields is None:
            if self.field.type == 'virtual':
                raise ValueError(self.env._(
                    "Cannot infer valid fields for a virtual field. "
                    "The 'valid_fields' parameter must be explicitly provided.",
                ))

            valid_fields = self.env[self.field.model_name]._fields.keys()

        if values is not None:
            if isinstance(values, Sequence):
                # A sequence is provided, then they have equal weights
                values = dict(zip(values, [DEFAULT_WEIGHT] * len(values)))

            if len(values.keys()) != len(set(values.keys())):
                # Having multiple instances of the same value will bias sampling
                raise ValueError(self.env._("Cannot have repeated entries in `values`."))

            self.weighted_values = values
        else:
            self.weighted_values = {}

        if depends is None:
            depends = []

        if not all(dep in valid_fields for dep in depends):
            invalid_fields = [dep for dep in depends if dep not in valid_fields]
            raise ValueError(self.env._(
                "Invalid field dependencies: %(invalid_fields)s. "
                "These fields do not exist in the model's blueprint.",
                invalid_fields=invalid_fields,
            ))

        self.depends = depends

        if not (0 <= null_frac <= 1):
            raise ValueError(self.env._(
                "Null fraction must be strictly between 0 and 1, got %(null_frac)s instead.",
                null_frac=null_frac,
            ))

        if self.field.required:
            null_frac = 0

        if self.has_weights:
            # Don't generate False entries if the user provided weights.
            # It will throw off the requested bias.
            null_frac = 0

        self.null_frac = null_frac

        if distribution and self.has_weights:
            raise ValueError(self.env._(
                "Cannot have both a distribution and weighted values. "
                "Please provide either 'distribution' or 'values' with weights, but not both.",
            ))

        if self.has_weights:
            self.distribution = WeightedDistribution(
                weighted_values=self.weighted_values,
                rng=self.rng,
            )
        elif isinstance(distribution, Distribution):
            self.distribution = distribution
        elif callable(distribution):
            self.distribution = distribution(self.rng)
        else:
            self.distribution = UniformDistribution(rng=self.rng)

        self.unique = unique
        self._init_seen()

    def _init_seen(self):
        if self.unique:
            if self.field.type == 'virtual':
                # Virtual fields are computed and not stored in the database.
                # Since we can't query existing values from the database,
                # we can only guarantee uniqueness within the current job run.
                # Therefore, values may be duplicated across different jobs and/or populate sessions.
                self._seen = set()
            else:
                model_name = self.field.model_name
                field_name = self.field.name
                present_values = (
                    self.env[model_name]
                    .search_fetch([], [field_name])
                    .mapped(field_name)
                )
                self._seen = {
                    seen_entry(value)
                    for value in present_values
                }
        else:
            self._seen = None

    def _reset_seen(self):
        self._seen = None
        self._init_seen()

    def reset(self):
        self._reset_seen()

    @property
    def values(self) -> list[Any]:
        return list(self.weighted_values.keys())

    @values.setter
    def values(self, new_values: Iterable):
        self.weighted_values = dict(zip(new_values, [DEFAULT_WEIGHT] * len(new_values)))

    @property
    def weights(self) -> list[float]:
        return list(self.weighted_values.values())

    @property
    def has_weights(self) -> bool:
        return not all(weight == DEFAULT_WEIGHT for weight in self.weighted_values.values())

    @final
    def send(self, known_vals: ValuesType | None = None) -> Any:
        if known_vals is None:
            known_vals = {}

        if not all(dep in known_vals for dep in self.depends):
            return NO_VALUE

        if self.null_frac and self.rng.random() < self.null_frac:
            return False

        if self.unique:
            for _ in range(MAX_RETRY):
                value = self._next(known_vals)
                entry = seen_entry(value)

                if entry in self._seen:
                    continue

                self._seen.add(entry)
                return value

            return NO_UNIQ_VALUE

        return self._next(known_vals)

    @final
    def throw(self, typ, val=None, tb=None):
        return super().throw(typ, val, tb)

    @abstractmethod
    def _next(self, known_vals: ValuesType) -> Any:
        """Generate the next value for this field based on known dependent field values."""
        ...

    @classmethod
    def get_kwargs(cls, attrs: dict[str, str]) -> dict[str, Any]:
        """Convert the fields' attributes of job instructions into kwargs consumable by generators."""
        kwargs = {}

        if 'values' in attrs:
            kwargs['values'] = const_eval(attrs['values'])

        if 'null_frac' in attrs:
            kwargs['null_frac'] = float(attrs['null_frac'])

        if 'distribution' in attrs:
            distribution_def = attrs['distribution']
            distribution = Distribution.from_definition(distribution_def, partial=True)
            kwargs['distribution'] = distribution

        if 'unique' in attrs:
            value = attrs['unique']
            kwargs['unique'] = str2bool(value)

        if 'virtual' in attrs:
            # The field is of the type 'virtual', there is no need for an arg.
            attrs.pop('virtual')

        return kwargs

    @staticmethod
    def get(name: str) -> type[Generator]:
        return GENERATORS_REGISTRY[name]


class ComodelGenerator(Generator):
    """
    Intermediate base for generators that resolve records from a comodel.

    Centralizes ref-scoping, caching, and partitioning of comodel IDs.
    """

    def __init__(self, ref: str | None = None, partition: bool = False, **kwargs):
        super().__init__(**kwargs)

        self.ref = ref

        assert not (partition and not self.job)

        if partition and self.job.parent_id:
            siblings_ids = self.job.parent_id.child_ids.ids
            self.partition = partial(
                partition_values,
                count=len(siblings_ids),
                index=siblings_ids.index(self.job.id),
            )
        else:
            self.partition = None

        self._comodel_ids_cache = LRU(32)

    def _get_comodel_ids(self, comodel_name: str, domain: DomainType) -> list[int]:
        cache_key = (comodel_name, repr(domain))
        if cache_key in self._comodel_ids_cache:
            return self._comodel_ids_cache[cache_key]

        domain = Domain(domain)

        if self.ref:
            domain &= get_ref_domain(self.env, comodel_name, self.ref, self.session)

        ids = self.env[comodel_name].with_context(active_test=False).search(domain).ids

        if self.partition:
            ids = self.partition(ids)

        self._comodel_ids_cache[cache_key] = ids
        return ids

    @abstractmethod
    def _next(self, known_vals):
        ...

    @classmethod
    def get_kwargs(cls, attrs):
        kwargs = super().get_kwargs(attrs)

        if 'ref' in attrs:
            kwargs['ref'] = attrs['ref']

        if 'partition' in attrs:
            value = attrs['partition']
            kwargs['partition'] = str2bool(value)

        return kwargs


def get_fields_vals(generators: Mapping[str, Generator]) -> ValuesType:
    """Get the vals for a specific record that needs to be created/written."""
    vals = {}

    fields_depends = {
        field_name: generator.depends
        for field_name, generator in generators.items()
    }
    if cycle := find_circular_dependency(fields_depends):
        chain = ' -> '.join(str(n) for n in cycle)
        raise RuntimeError(
            f"Circular dependency detected in fields' generator dependencies: {chain}.",
        )

    for field_name in topological_sort(fields_depends):
        generator = generators[field_name]
        try:
            value = generator.send(vals)

            if value is NO_VALUE:
                missing_deps = [dep for dep in generator.depends if dep not in vals]
                raise RuntimeError(generator.env._(  # noqa: TRY301
                    "Could not generate a value because "
                    "required dependencies are missing: %(missing_deps)s. "
                    "Expected dependencies: %(expected_deps)s.",
                    missing_deps=missing_deps,
                    expected_deps=generator.depends,
                ))

            if value is NO_UNIQ_VALUE:
                # A unique field couldn't find a novel value with the current
                # upstream values -> Re-roll the immediate dependencies if any.
                for _ in range(MAX_RETRY if generator.depends else 0):
                    for dep in generator.depends:
                        generators[dep].reset()
                        vals[dep] = generators[dep].send(vals)

                    value = generator.send(vals)

                    if value is not NO_UNIQ_VALUE:
                        break
                else:
                    raise RuntimeError(generator.env._(  # noqa: TRY301
                        "Couldn't find a unique value for field %(field)s.",
                        field=generator.field,
                    ))

        except Exception as exc:
            exc.add_note(f"Generator: '{generator.name}'")
            exc.add_note(f"Field: '{generator.field}'")
            raise

        vals[field_name] = value

    # Remove values from virtual fields.
    # Virtual fields may have the same name as real fields,
    # but we should not commit their values to the database.
    for field_name, generator in generators.items():
        if generator.field.type == 'virtual':
            vals.pop(field_name)

    return vals


def partition_values[T](values: Sequence[T], count: int, index: int) -> list[T]:
    """Partition a sequence of values into subsets by distributing them round-robin style.

    :param values: Sequence of values to partition.
    :param count: Total number of partitions to divide values into.
    :param index: Index of the partition to return (0-based).
    :return: List containing values assigned to the specified partition index.
    """
    return [v for i, v in enumerate(values) if i % count == index]


def seen_entry(value):
    """Ensures that ``value`` is hashable for set insertion"""
    if isinstance(value, list):
        return tuple(seen_entry(v) for v in value)
    if isinstance(value, set):
        return frozenset(seen_entry(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, seen_entry(v)) for k, v in value.items()))
    if isinstance(value, tuple):
        return tuple(seen_entry(v) for v in value)

    return value
