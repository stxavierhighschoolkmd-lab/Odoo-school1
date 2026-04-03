# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrAttendanceOvertimeLine(models.Model):
    _name = 'hr.attendance.overtime.line'
    _description = "Attendance Overtime Line"
    _order = 'date'

    attendance_id = fields.Many2one('hr.attendance', string="Attendance", ondelete='cascade', index=True, required=True)

    date = fields.Date(string='Day', index=True, required=True, default=lambda self: self.attendance_id.date)
    status = fields.Selection([
            ('to_approve', "To Approve"),
            ('approved', "Approved"),
            ('refused', "Refused")
        ],
        compute='_compute_status',
        required=True, store=True, readonly=False, precompute=True,
    )
    duration = fields.Float(string='Extra Hours', default=0.0, required=True)
    manual_duration = fields.Float(
        string='Extra Hours (encoded)',
        compute='_compute_manual_duration',
        store=True, readonly=False,
    )

    amount_rate = fields.Float("Overtime pay rate", required=True, default=1.0)

    is_manager = fields.Boolean(compute="_compute_is_manager")

    rule_ids = fields.Many2many("hr.attendance.overtime.rule", string="Applied Rules")

    @api.depends('attendance_id.employee_id')
    def _compute_status(self):
        for overtime in self:
            if not overtime.status:
                overtime.status = 'to_approve' if overtime.attendance_id.employee_id.company_id.attendance_overtime_validation == 'by_manager' else 'approved'

    @api.depends('duration')
    def _compute_manual_duration(self):
        for overtime in self:
            overtime.manual_duration = overtime.duration

    @api.depends('attendance_id.employee_id')
    def _compute_is_manager(self):
        has_manager_right = self.env.user.has_group('hr_attendance.group_hr_attendance_manager')
        has_officer_right = self.env.user.has_group('hr_attendance.group_hr_attendance_officer')
        for overtime in self:
            overtime.is_manager = (
                has_manager_right or
                (
                    has_officer_right
                    and overtime.attendance_id.employee_id.attendance_manager_id == self.env.user
                )
            )

    def action_approve(self):
        self.write({'status': 'approved'})

    def action_refuse(self):
        self.write({'status': 'refused'})
