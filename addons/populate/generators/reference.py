from __future__ import annotations

from typing import TYPE_CHECKING, cast

from .generator import ComodelGenerator

if TYPE_CHECKING:
    from odoo.fields import Many2oneReference, Reference


class ReferenceOne(ComodelGenerator):
    """Pick a random record ID for a Many2oneReference field."""
    name = 'reference.one'
    allowed_fields_type = ['many2one_reference']

    def __init__(self, field: Many2oneReference, **kwargs):
        # Validate field's type before reading `model_field`
        self._validate_field_type(field)
        super().__init__(field=field, depends=[field.model_field], **kwargs)
        self.field = cast('Many2oneReference', self.field)

    def _next(self, known_vals):
        comodel_name = known_vals[self.field.model_field]
        comodel_ids = self._get_comodel_ids(comodel_name, domain=[])

        if not comodel_ids:
            return False

        return self.distribution.choice(comodel_ids)


class ReferenceRaw(ComodelGenerator):
    """Generate ``'model_name,id'`` strings for Reference fields."""
    name = 'reference.raw'
    allowed_fields_type = ['reference']

    def __init__(
        self,
        res_model: str | None = None,
        res_id: str | None = None,
        **kwargs,
    ):
        depends = []
        if res_model:
            depends.append(res_model)
            if res_id:
                depends.append(res_id)

        super().__init__(depends=depends, **kwargs)
        self.field = cast('Reference', self.field)

        self.res_model = res_model
        self.res_id = res_id
        self.model_names = self.field.get_values(self.env)

    def _next(self, known_vals):
        if len(self.depends) == 2:
            model_name = known_vals[self.depends[0]]
            record_id = known_vals[self.depends[1]]

            if model_name not in self.model_names:
                raise ValueError(self.env._(
                    "Model '%(model_name)s' is not in the allowed models "
                    "for reference field '%(field_name)s': %(model_names)s.",
                    model_name=model_name,
                    field_name=self.field.name,
                    model_names=self.model_names,
                ))

            if isinstance(record_id, str):
                record_id = int(record_id)

            return f"{model_name},{record_id}"

        if len(self.depends) == 1:
            # Infer it's the `model_name`
            model_name = known_vals[self.depends[0]]

            if model_name not in self.model_names:
                raise ValueError(self.env._(
                    "Model '%(model_name)s' is not in the allowed models "
                    "for reference field '%(field_name)s': %(model_names)s.",
                    model_name=model_name,
                    field_name=self.field.name,
                    model_names=self.model_names,
                ))

        else:
            # distribution is applied on the ids, not the models
            model_name = self.rng.choice(self.model_names)

        assert model_name

        comodel_ids = self._get_comodel_ids(model_name, domain=[])

        if not comodel_ids:
            return False

        record_id = self.distribution.choice(comodel_ids)

        return f"{model_name},{record_id}"

    @classmethod
    def get_kwargs(cls, attrs):
        kwargs = super().get_kwargs(attrs)
        kwargs.update(**{k: v for k, v in attrs.items() if k in ('res_model', 'res_id')})
        return kwargs
