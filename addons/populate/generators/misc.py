from itertools import count, cycle

from odoo import Command
from odoo.tools.safe_eval import safe_eval
from odoo.tools.view_validation import get_expression_field_names

from .generator import Generator


class Counter(Generator):
    """
    Generate values from an arithmetic sequence, similar to Python's ``range()``.

    Produces values starting at ``start``, incrementing by ``step`` each time.
    If ``end`` is provided, the sequence wraps around (like ``misc.cycle``) once
    the boundary is reached. Without ``end``, the counter runs indefinitely.
    """
    name = 'misc.counter'
    allowed_fields_type = ['integer', 'float', 'virtual']

    def __init__(self, start: float = 0, step: float = 1, end: float | None = None, **kwargs):
        super().__init__(**kwargs)

        if step == 0:
            raise ValueError(self.env._(
                "Step cannot be zero for the counter generator. Use `eval` with a static value instead.",
            ))

        if start.is_integer():
            start = int(start)

        if step.is_integer():
            step = int(step)

        if end is not None:
            if step > 0 and end <= start:
                raise ValueError(self.env._(
                    "When step is positive, end (%(end)s) must be greater than start (%(start)s).",
                    end=end, start=start,
                ))
            if step < 0 and end >= start:
                raise ValueError(self.env._(
                    "When step is negative, end (%(end)s) must be less than start (%(start)s).",
                    end=end, start=start,
                ))
            if end.is_integer():
                end = int(end)

        self.null_frac = 0

        self.counter = (
            cycle(range(start, end, step))
            if end is not None
            else count(start, step)
        )

    def _next(self, known_vals):
        return next(self.counter)

    @classmethod
    def get_kwargs(cls, attrs):
        kwargs = super().get_kwargs(attrs)
        kwargs.update(**{k: float(v) for k, v in attrs.items() if k in ('start', 'step', 'end')})
        return kwargs


class Cycle(Generator):
    """Deterministically cycle through a list of values in order."""
    name = 'misc.cycle'
    allowed_fields_type = ['integer', 'float', 'char', 'text', 'html', 'date', 'datetime', 'virtual']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not self.values:
            raise ValueError(self.env._("Values cannot be empty for the cycle generator."))

        if self.has_weights:
            raise ValueError(self.env._("Weights cannot be provided for the cycle generator."))

        # The cycle generator cycles through values deterministically in order.
        # To prevent unintended False/None values, null_frac is set to 0.
        # If False/None values are needed, they should be explicitly included in the values list.
        self.null_frac = 0
        self.cycle = cycle(self.values)

    def _next(self, known_vals):
        return next(self.cycle)


class Eval(Generator):
    """Evaluate a Python expression, optionally depending on other fields."""
    name = 'misc.eval'

    def __init__(self, expr: str, **kwargs):
        env = kwargs['env']

        if expr.strip().startswith('lambda'):
            raise ValueError(env._(
                "The eval generator takes an expression directly instead of a lambda. "
                "Use 'x + y' instead of 'lambda x, y: x + y'.",
            ))

        required_names = get_expression_field_names(expr)
        eval_ctx = self._get_eval_context(**kwargs)
        depends = list(required_names - set(eval_ctx.keys())) if required_names else None

        super().__init__(depends=depends, **kwargs)

        # Store the original expression for clear error reporting
        self.expr = expr

        # Only the result of the evaluation should be a possible output value.
        self.null_frac = 0

        if self.depends:
            # it's a raw expression that has dependencies,
            # wrap it into a lambda that takes the depends as args.
            args = ', '.join(self.depends)
            expr = f'lambda {args}: {expr}'
        elif self.unique:
            raise ValueError(self.env._("This Eval returns the same value, so it cannot be unique."))

        self.evaluation = safe_eval(expr, context=eval_ctx)

    def _next(self, known_vals):
        if not callable(self.evaluation):
            return self.evaluation

        kwargs = {dep: known_vals[dep] for dep in self.depends}
        try:
            return self.evaluation(**kwargs)
        except Exception as e:  # noqa: BLE001
            e.add_note(f"Expression: '{self.expr}'")
            raise

    @classmethod
    def get_kwargs(cls, attrs):
        kwargs = super().get_kwargs(attrs)

        if 'eval' in attrs:
            kwargs['expr'] = attrs['eval']

        return kwargs

    def _get_eval_context(self, **kwargs):
        env = getattr(self, 'env', False) or kwargs['env']
        field = getattr(self, 'field', False) or kwargs['field']
        return {
            'env': env,
            'model': env[field.model_name],
            'Command': Command,
        }
