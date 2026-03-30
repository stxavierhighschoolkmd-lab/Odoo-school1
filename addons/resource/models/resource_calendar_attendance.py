# Part of Odoo. See LICENSE file for full copyright and licensing details.
import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_time
from odoo.tools.date_utils import float_to_time, parse_iso_date
from odoo.tools.intervals import Intervals


def extended_gcd(a, b):
    if a == 0: return b, 0, 1
    gcd, x1, y1 = extended_gcd(b % a, a)
    x = y1 - (b // a) * x1
    y = x1
    return gcd, x, y


def check_conflict(interval1, offset, interval2):
    gcd, x0, _ = extended_gcd(interval1, interval2)

    # 1. Check if the sequences ever align
    if offset % gcd != 0:
        return None

    # 2. Find the first mathematical collision (k1)
    # We solve: interval1 * k1 ≡ offset (mod interval2)
    mod_val = interval2 // gcd
    k1 = (x0 * (offset // gcd)) % mod_val

    first_collision = k1 * interval1

    # 3. Ensure the collision is not before the second offset starts
    if first_collision < offset:
        lcm = abs(interval1 * interval2) // gcd
        diff = offset - first_collision
        steps = math.ceil(diff / lcm)
        first_collision += steps * lcm

    return first_collision

class ResourceCalendarAttendance(models.Model):
    _name = 'resource.calendar.attendance'
    _description = "Work Detail"
    _order = 'sequence, date, dayofweek, hour_from'

    hour_from = fields.Float(string='Work from', default=0, required=True, index=True,
        help="Start and End time of working.\n"
             "A specific value of 24:00 is interpreted as 23:59:59.999999.")
    hour_to = fields.Float(string='Work to', default=0, required=True)
    # For the hour duration, the compute function is used to compute the value
    # unambiguously, while the duration in days is computed for the default
    # value but can be manually overridden.
    duration_hours = fields.Float(compute='_compute_duration_hours', string='Hours', store=True, readonly=False)
    calendar_id = fields.Many2one("resource.calendar", string="Resource's Calendar", required=True, index=True, ondelete='cascade')
    schedule_type = fields.Selection(related='calendar_id.schedule_type', readonly=True)
    duration_based = fields.Boolean(compute='_compute_duration_based', store=True)
    day_period = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('full_day', 'Full Day')], store=True, compute='_compute_day_period')
    sequence = fields.Integer(default=10,
        help="Gives the sequence of this line when displaying the resource calendar.")

    # Fixed
    dayofweek = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday')
        ], 'Day of Week', required=True, index=True, precompute=True,
        compute="_compute_dayofweek", store=True, readonly=False)

    # Variable
    date = fields.Date()
    recurrency = fields.Boolean()
    recurrency_excluded_occurences = fields.Json(default={'dates': []}, required=True)
    recurrency_type = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
    ], default='weeks')
    recurrency_interval = fields.Integer(string="Interval", default=1, help="Number of days or weeks between each occurrence.")
    recurrency_end_type = fields.Selection([
        ('forever', 'Forever'),
        ('times', 'Number of Occurrences'),
        ('date', 'Until'),
    ], default='forever', string="Recurrence End Condition")
    recurrency_count = fields.Integer(string="Number of Repetitions", default=1)
    recurrency_until = fields.Date(string="Recurrence End Date", compute="_compute_recurrency_until", store=True, readonly=False)

    _check_interval = models.Constraint(
        "CHECK(recurrency IS NOT TRUE OR recurrency_interval >= 1)",
        "The recurrency interval should be greater than 0",
    )

    _check_recurrency_until = models.Constraint(
        "CHECK(recurrency_until IS NULL OR recurrency_until >= date)",
        "A recurrency should finish after the first occurence",
    )

    @api.constrains('calendar_id', 'date', 'duration_hours', 'dayofweek')
    def _check_attendance(self):
        # Check for each day of week that there are no superimposed attendances.
        target_calendars = self.mapped("calendar_id")
        target_dates = list(set(self.mapped("date")))
        target_dayofweeks = list(set(self.mapped("dayofweek")))

        domain = [
            ('calendar_id', 'in', target_calendars.ids),
            '|',
                ('date', 'in', target_dates),
                '&',
                    ('date', '=', False),
                    ('dayofweek', 'in', target_dayofweeks)
        ]

        attendances_overlappable = self.search(domain)

        att_by_date_overlappable = defaultdict(list)
        att_by_weekday_overlappable = defaultdict(list)

        for attendance in attendances_overlappable:
            if attendance.date:
                att_by_date_overlappable[attendance.calendar_id, attendance.date].append(attendance)
            else:
                att_by_weekday_overlappable[attendance.calendar_id, attendance.dayofweek].append(attendance)

        for (att_calendar, att_date, att_dayofweek), attendances in self.grouped(lambda a: (a.calendar_id, a.date, a.dayofweek)).items():
            intervals_attendances = []
            duration_per_date = defaultdict(float)
            for attendance in att_by_date_overlappable[att_calendar, att_date] or att_by_weekday_overlappable[att_calendar, att_dayofweek]:
                if attendance.duration_hours <= 0 or attendance.duration_hours > 24:
                    raise ValidationError(self.env._("Attendance duration must be between 0 and 24 hours"))
                if attendance.date:
                    date_to_combine = attendance.date
                else:
                    date_to_combine = date.min + timedelta(days=int(attendance.dayofweek))
                if not attendance.duration_based:
                    intervals_attendances.append((
                        datetime.combine(date_to_combine, float_to_time(attendance.hour_from)) + timedelta(
                            microseconds=1),
                        datetime.combine(date_to_combine, float_to_time(attendance.hour_to)),
                        attendance
                    ))
                duration_per_date[date_to_combine] += attendance.duration_hours
                if duration_per_date[date_to_combine] > 24:
                    raise ValidationError(self.env._("Attendance durations can't exceed 24 hours in the day."))
            if len(Intervals(intervals_attendances)) != len(intervals_attendances):
                raise ValidationError(self.env._("Attendances can't overlap."))

    @api.onchange('hour_from')
    def _onchange_hour_from(self):
        # avoid negative or after midnight
        self.hour_from = min(self.hour_from, 23.99)
        self.hour_from = max(self.hour_from, 0.0)

    @api.onchange('hour_to')
    def _onchange_hour_to(self):
        # avoid negative or after midnight
        self.hour_to = min(self.hour_to, 24)
        self.hour_to = max(self.hour_to, 0.0)

        if self.hour_from and not self.hour_to:
            self.hour_from = 0.0

        # avoid wrong order
        self.hour_to = max(self.hour_to, self.hour_from)

    @api.onchange('duration_hours')
    def _onchange_duration_hours(self):
        self.duration_hours = min(self.duration_hours, 24)
        if self.hour_from or self.hour_to:
            if self.hour_from + self.duration_hours > 24:
                self.hour_from = 24 - self.duration_hours
                self.hour_to = 24
            else:
                self.hour_to = self.hour_from + self.duration_hours

    @api.depends('hour_from', 'hour_to')
    def _compute_duration_based(self):
        for attendance in self:
            attendance.duration_based = not attendance.hour_from and not attendance.hour_to

    @api.depends('duration_hours', 'hour_from', 'hour_to')
    def _compute_day_period(self):
        for attendance in self:
            if attendance.duration_hours > (0.75 * attendance.calendar_id.hours_per_day) or (not attendance.hour_from and not attendance.hour_to):
                attendance.day_period = 'full_day'
            elif attendance.hour_from and attendance.hour_to:
                if attendance.hour_from > 12 or (12 - attendance.hour_from <= attendance.hour_to - 12):
                    attendance.day_period = 'afternoon'
                else:
                    attendance.day_period = 'morning'
            else:
                attendance.day_period = 'morning'

    @api.depends('date')
    def _compute_dayofweek(self):
        for attendance in self:
            if attendance.date:
                attendance.dayofweek = str(attendance.date.weekday())
            elif not attendance.dayofweek:  # default value
                attendance.dayofweek = '0'

    @api.depends('hour_from', 'hour_to')
    def _compute_duration_hours(self):
        for attendance in self.filtered(lambda att: att.hour_from or att.hour_to):
            attendance.duration_hours = max(0, attendance.hour_to - attendance.hour_from)

    @api.depends('recurrency', 'recurrency_end_type', 'recurrency_type', 'recurrency_interval', 'recurrency_count', 'date')
    def _compute_recurrency_until(self):
        for attendance in self.filtered(lambda a: a.date):
            if not attendance.recurrency:
                attendance.recurrency_until = attendance.date
                continue
            match attendance.recurrency_end_type:
                case 'date':
                    break  # It should already be set by the user
                case 'times' if attendance.recurrency_type and attendance.recurrency_interval and attendance.recurrency_count:
                    attendance.recurrency_until = attendance.date + timedelta(**{attendance.recurrency_type: attendance.recurrency_interval * attendance.recurrency_count})
                case _:  # 'forever' or missing parameters
                    attendance.recurrency_until = date.max

    def _compute_display_name(self):
        for attendance in self:
            if attendance.duration_based:
                attendance.display_name = self.env._("%(duration)s hours Attendance", duration=format_time(self.env, float_to_time(attendance.duration_hours), time_format="HH:mm"))
            else:
                attendance.display_name = self.env._("%(hour_from)s - %(hour_to)s Attendance",
                                                     hour_from=format_time(self.env, float_to_time(attendance.hour_from), time_format="short"),
                                                     hour_to=format_time(self.env, float_to_time(attendance.hour_to), time_format="short"))

    def _to_dict(self):
        self.ensure_one()
        return {
            'date': self.date,
            'dayofweek': self.dayofweek,
            'day_period': self.day_period,
            'duration_hours': self.duration_hours,
            'hour_from': self.hour_from,
            'hour_to': self.hour_to,
            'sequence': self.sequence,
        }

    def _is_work_period(self):
        self.ensure_one()
        return True

    def _filter_by_date(self, date_obj: date):
        """
        Get the attendances for a specific date. For variable schedule, it will return the attendances with the same date or with a recurrency rule matching the date. For fixed schedule, it will return the attendances with the same day of week as the date.

        :param date_obj: the date to get the attendances for (date object)
        """
        def is_recurrent_attendance_today(a):
            if not a.recurrency_interval:
                return False
            return (a.recurrency and fields.Date.to_string(date_obj) not in a.recurrency_excluded_occurences['dates'] and a.date <= date_obj <= a.recurrency_until and (
                        (a.recurrency_type == 'days' and not (date_obj - a.date).days % a.recurrency_interval) or
                        (a.recurrency_type == 'weeks' and not (date_obj - a.date).days % 7 and not ((date_obj - a.date).days // 7) % a.recurrency_interval)
                    )
                )
        return self.filtered(lambda a: (a.date == date_obj or is_recurrent_attendance_today(a)) if a.calendar_id.schedule_type == 'variable' else (a.dayofweek == str(date_obj.weekday())))

    def _filter_between_dates(self, date_from, date_to):
        def _is_between_dates(att):
            att.ensure_one()
            if att.date:
                if att.recurrency:
                    return att.date <= date_to and att.recurrency_until >= date_from
                return date_from <= att.date <= date_to
            return att.calendar_id.schedule_type != 'variable'

        return self.filtered(_is_between_dates)

    def exclude_occurence(self, date):
        self.ensure_one()
        excluded_ocurrences = self.recurrency_excluded_occurences['dates']
        if date not in excluded_ocurrences:
            excluded_ocurrences.append(date)
            self.recurrency_excluded_occurences = {'dates': excluded_ocurrences}

    def stop_recurrency(self, date):
        self.ensure_one()
        self.update({
            'recurrency_until': parse_iso_date(date) - relativedelta(days=1),
            'recurrency_end_type': 'date',
        })

    def create_ad_hoc(self, date, changes):
        self.ensure_one()
        self.exclude_occurence(date)
        changes_without_recurrency = {f: v for f, v in changes.items() if "recurrency" not in f}
        return self.copy({
            **changes_without_recurrency,
            'date': parse_iso_date(date),
            'recurrency': False,
        })

    def create_new_recurrency(self, date, changes):
        self.ensure_one()
        new_recurrency = self.copy({
            **changes,
            'date': parse_iso_date(date),
        })
        self.stop_recurrency(date)
        return new_recurrency

    def _check_day_overlap(self):
        if not self:
            return False
        assert len(set(att.calendar_id for att in self)) == 1
        assert self.calendar_id.schedule_type == 'variable'
        assert all(self.mapped('recurrency'))
        # M: This function is the same as _check_overlap_time_based but it half handles the duration_based.
        # M: A duration_based cannot overlap in the same day with a non-duration based attendance (time based)

        date_intervals = [(attendance.date, attendance.recurrency_until, attendance) for attendance in self]
        date_overlaps = Intervals(date_intervals, keep_distinct=True)
        date_overlaps_to_check = [attendances for _, _, attendances in date_overlaps._items if len(attendances) > 1]
        for attendances in date_overlaps_to_check:
            if len(set(attendances.mapped('duration_based'))) == 1:
                continue
            for one in attendances:
                for other in (attendances - one):
                    if one.date > other.recurrency_until or other.date > one.recurrency_until:
                        continue
                    if one.duration_based == other.duration_based:
                        # M: If they have a different type of base, meaning one is time based and the other is duration based.
                        # M: We treat it like a time overlap and we check that they never meet in any day.
                        if (one.duration_based == False and (one.hour_from >= other.hour_to or one.hour_to <= other.hour_from)):
                            # If they are based differently or they overlap in hours, then they shouldn't collide.
                            continue
                    interval1 = one.recurrency_interval * (7 if one.recurrency_type == 'weeks' else 1)
                    interval2 = other.recurrency_interval * (7 if other.recurrency_type == 'weeks' else 1)
                    offset = abs((one.date - other.date).days)
                    first_collision = check_conflict(interval1, offset, interval2)
                    if first_collision is not None:
                        collision_date = min(one.date, other.date) + timedelta(days=first_collision)
                        if collision_date < min(one.recurrency_until, other.recurrency_until):
                            return True
        return False

    def _check_overlap_time_based(self):
        """Check overlap on recurrent time-based attendances."""

        # Should work perfectly.
        if not self:
            return False
        assert len(set(att.calendar_id for att in self)) == 1
        assert self.calendar_id.schedule_type == 'variable'
        assert all(att.recurrency and not att.duration_based for att in self)

        date_intervals = [(attendance.date, attendance.recurrency_until, attendance) for attendance in self]
        date_overlaps = Intervals(date_intervals, keep_distinct=True)
        # M: We make an interval with all dates to see if they overlap. keep_distinct is important so that att 1-4 and 4-6 dont get overlapped.
        date_overlaps_to_check = [attendances for _, _, attendances in date_overlaps._items if len(attendances) > 1]
        # M: Now we take all the overlap groups:
        for attendances in date_overlaps_to_check:
            for one in attendances:
                for other in (attendances - one):
                    # M: We have to re-check because if we have 3 attendances: A 1-10, B 8-12, C 11-15. A and C dont overlap, but the intervals function will fuse A-B-C together as B overlaps with both.
                    # M: In the end this is useful so we dont check attendance D 20-30 with ABC.
                    if one.date > other.recurrency_until or other.date > one.recurrency_until:
                        continue
                    # M: If they overlap by dates, we check if they overlap by hours.
                    if one.hour_from >= other.hour_to or one.hour_to <= other.hour_from:
                        continue
                    # M: If they overlap by hours then we find the first day collision.
                    interval1 = one.recurrency_interval * (7 if one.recurrency_type == 'weeks' else 1)
                    interval2 = other.recurrency_interval * (7 if other.recurrency_type == 'weeks' else 1)
                    offset = abs((one.date - other.date).days)
                    first_collision = check_conflict(interval1, offset, interval2) # blackbox.
                    if first_collision is not None:
                        collision_date = min(one.date, other.date) + timedelta(days=first_collision)
                        if collision_date < min(one.recurrency_until, other.recurrency_until):
                            # M: We still need to check that the first collision date is before the end of the recurrency, as they will never collide.
                            return True
        return False

    def _check_overlap_duration_based(self):
        """Check overlap on recurrent duration-based attendances."""
        if not self:
            return False
        assert len(set(att.calendar_id for att in self)) == 1
        assert self.calendar_id.schedule_type == 'variable'
        assert all(att.recurrency and att.duration_based for att in self)

        date_intervals = [(attendance.date, attendance.recurrency_until, attendance) for attendance in self]
        date_overlaps = Intervals(date_intervals, keep_distinct=True)
        date_overlaps_to_check = [attendances for _, _, attendances in date_overlaps._items if len(attendances) > 1]
        for attendances in date_overlaps_to_check:
            # M: I still dont know how to handle this. Jugj suggestion is to calculate the hyper period, but is it really feasable?
            # The problem is that we need to check if there is ever a day where the total duration is more than 24h.
            # With the dates overlap strategy we can filter down the things to check.
            # We could have a greedy stategy where we assume you are overlapping always with attendances of a different interval as yours.
            # something like how check_conflict detects if they are parallel
            raise NotImplementedError("Checking overlap between duration based attendances with recurrency is not implemented yet.")
        return False
