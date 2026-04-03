from abc import ABC, abstractmethod

from odoo.tools import date_utils

from .generator import Generator


class Temporal(Generator, ABC):
    """
    Base class for date/datetime generators over a ``[start, end]`` range.

    Subclasses define the time unit, format, and default range bounds.
    """
    time_unit: str
    format: str
    default_start: str
    default_end: str

    def __init__(self, start: str | None = None, end: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.start = date_utils.parse_date(start or self.default_start, self.env)
        self.end = date_utils.parse_date(end or self.default_end, self.env)

        # Allows more flexibility on the "direction" of the range.
        if self.start > self.end:
            self.start, self.end = self.end, self.start

    def _next(self, known_vals):
        offset = self.distribution.sample_discrete(0, self.delta)
        return date_utils.add(self.start, **{self.time_unit: offset}).strftime(self.format)

    @property
    @abstractmethod
    def delta(self):
        ...

    @classmethod
    def get_kwargs(cls, attrs):
        kwargs = super().get_kwargs(attrs)
        kwargs.update(**{k: v for k, v in attrs.items() if k in ('start', 'end')})
        return kwargs


class Date(Temporal):
    """Generate random dates between ``start`` and ``end``."""
    name = 'temporal.date'
    allowed_fields_type = ['date', 'datetime', 'virtual']
    time_unit = 'days'
    format = '%Y-%m-%d'
    default_start = 'today'
    default_end = 'today -5y'

    @property
    def delta(self):
        return (self.end - self.start).days


class Datetime(Temporal):
    """Generate random datetimes between ``start`` and ``end``."""
    name = 'temporal.datetime'
    allowed_fields_type = ['datetime', 'virtual']
    time_unit = 'seconds'
    format = '%Y-%m-%d %H:%M:%S'
    default_start = 'now'
    default_end = 'now -5y'

    @property
    def delta(self):
        return int((self.end - self.start).total_seconds())
