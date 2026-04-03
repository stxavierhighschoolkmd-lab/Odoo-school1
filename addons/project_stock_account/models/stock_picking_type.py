# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    analytic_costs = fields.Boolean(
        compute="_compute_analytic_costs",
        store=True,
        readonly=False,
        precompute=True,
        help="Validating stock pickings will generate analytic entries for the selected project. Products set for re-invoicing will also be billed to the customer."
        )

    def _compute_analytic_costs(self):
        for picking_type in self:
            picking_type.analytic_costs = picking_type.code == 'mrp_operation'
