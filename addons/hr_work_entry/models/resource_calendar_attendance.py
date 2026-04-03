# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    work_entry_type_id = fields.Many2one('hr.work.entry.type', 'Work Entry Type', groups="hr.group_hr_user")

    def _copy_attendance_vals(self):
        res = super()._copy_attendance_vals()
        res['work_entry_type_id'] = self.work_entry_type_id.id
        return res

    def _is_work_period(self):
        return self.work_entry_type_id.count_as == 'working_time' and super()._is_work_period()
