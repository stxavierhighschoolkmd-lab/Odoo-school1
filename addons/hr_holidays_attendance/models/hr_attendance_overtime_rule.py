
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class HrAttendanceOvertimeRule(models.Model):
    _name = 'hr.attendance.overtime.rule'
    _inherit = 'hr.attendance.overtime.rule'

    compensable_as_leave = fields.Boolean("Give back as time off", default=False)

    def _extra_overtime_vals(self):
        return {
            **super()._extra_overtime_vals(),
            'compensable_as_leave': any(self.mapped('compensable_as_leave')),
        }
