# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

BILLABLE_TYPES = [
    ('01_revenues_fixed', 'Revenues (Fixed Price)'),
    ('05_revenues_milestones', 'Revenues (Milestones)'),
    ('07_revenues_manual', 'Revenues (Manual)'),
    ('10_service_revenues', 'Service Revenues'),
    ('11_expense', 'Expense'),
    ('12_manufacturing_order', 'Manufacturing Order'),
    ('13_picking_entry', 'Inventory Transfer'),
    ('14_other_costs', 'Other Costs'),
    ('15_other_revenues', 'Other Revenues'),
]


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    billable_type = fields.Selection(BILLABLE_TYPES, string="Billable Type",
        compute='_compute_project_billable_type', compute_sudo=True, store=True, readonly=True)

    category_report = fields.Selection(
        [('invoice', 'Customer Invoice'), ('vendor_bill', 'Vendor Bill'), ('other', 'Other')],
        compute='_compute_project_category_report', compute_sudo=True, store=True, readonly=True)

    @api.depends('so_line.product_id', 'amount')
    def _compute_project_billable_type(self):
        for line in self:
            if line.amount >= 0 and line.unit_amount >= 0:
                if line.so_line and line.so_line.product_id.type == 'service':
                    line.billable_type = '10_service_revenues'
                else:
                    if line.product_id.invoice_policy == 'delivery':
                        service_type = line.product_id.service_type
                        if service_type == 'milestones':
                            invoice_type = '05_revenues_milestones'
                        elif service_type == 'manual':
                            invoice_type = '07_revenues_manual'
                        else:
                            invoice_type = '01_revenues_fixed'
                    elif line.product_id.invoice_policy == 'order':
                        invoice_type = '01_revenues_fixed'
                    else:
                        invoice_type = '15_other_revenues'
                    line.billable_type = invoice_type
            else:
                if line.category == 'picking_entry':
                    line.billable_type = '13_picking_entry'
                elif line.category == 'manufacturing_order':
                    line.billable_type = '12_manufacturing_order'
                elif line.category == 'expense':
                    line.billable_type = '11_expense'
                else:
                    line.billable_type = '15_other_costs'

    @api.depends('category')
    def _compute_project_category_report(self):
        for line in self:
            if line.category == 'invoice':
                line.category_report = 'invoice'
            elif line.category == 'vendor_bill':
                line.category_report = 'vendor_bill'
            else:
                line.category_report = 'other'

    def action_open_account_analytic_line_origine(self):
        self.ensure_one()
        if (self.so_line):
            return {
                'res_model': self.so_line._name,
                'type': 'ir.actions.act_window',
                'views': [[False, "form"]],
                'res_id': self.so_line.id,
            }
        return {
            'res_model': self._name,
            'type': 'ir.actions.act_window',
            'views': [[False, "form"]],
            'res_id': self.id,
        }
