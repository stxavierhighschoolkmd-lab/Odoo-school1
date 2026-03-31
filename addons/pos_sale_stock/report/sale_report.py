from odoo import models


class SaleReport(models.Model):
    _inherit = "sale.report"

    def _select_pos(self):
        select_ = super()._select_pos()
        select_ = select_.replace("NULL AS qty_delivered", "SUM(l.qty_delivered) AS qty_delivered")
        select_ = select_.replace("NULL AS qty_to_deliver", "SUM(l.qty - l.qty_delivered) AS qty_to_deliver")
        untaxed_delivered_amount = f"(CASE WHEN pos.account_move IS NOT NULL THEN SUM(l.price_unit * l.qty_delivered) ELSE 0 END) / MIN({self._case_value_or_one('pos.currency_rate')}) * {self._case_value_or_one('account_currency_table.rate')}"
        select_ = select_.replace("NULL AS untaxed_delivered_amount", f"{untaxed_delivered_amount} AS untaxed_delivered_amount")
        return select_

    def _from_pos(self):
        return super()._from_pos() + "LEFT JOIN stock_picking_type picking ON picking.id=config.picking_type_id"

    def _group_by_pos(self):
        return super()._group_by_pos() + ", picking.warehouse_id"

    def _available_additional_pos_fields(self):
        additional_pos_fields = super()._available_additional_pos_fields()
        additional_pos_fields['warehouse_id'] = 'picking.warehouse_id'
        return additional_pos_fields
