import ast

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    estimated_cost = fields.Monetary(compute='_compute_estimated_cost', export_string_translation=False)
    estimated_cost_ratio = fields.Float(compute='_compute_estimated_cost', export_string_translation=False)

    def _get_sol_cost_data_per_project(self, order_lines):
        query = """
            SELECT
                SUM (purchase_price * product_uom_qty) AS cost,
                SUM (price_subtotal) AS sold
            FROM sale_order_line
            WHERE id IN %s
        """
        self.env.cr.execute(query, (tuple(order_lines.ids),))
        return self.env.cr.fetchone()

    def _compute_estimated_cost(self):
        all_sale_orders_lines = self._fetch_sale_order_items({'project.task': [('is_closed', '=', False)]})
        costs_per_project = self._get_sol_cost_data_per_project(all_sale_orders_lines) if all_sale_orders_lines else (0, 0)
        for project in self:
            cost, sold = costs_per_project
            project.estimated_cost = cost
            project.estimated_cost_ratio = 100 * (project.estimated_cost / sold) if sold else 0.0

    def action_projected_margin(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('sale_margin.action_order_report_projected_margins')
        all_sale_orders_lines = self._fetch_sale_order_items({'project.task': [('is_closed', '=', False)]})
        action["domain"] = [("id", "in", all_sale_orders_lines.ids)]
        context = ast.literal_eval(action.get('context', '{}'))
        context.update({'search_default_customer': 0})
        action['context'] = context
        return action
