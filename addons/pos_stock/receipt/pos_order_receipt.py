from odoo import models
from odoo.tools.misc import format_date


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def _order_receipt_generate_line_data(self):
        line_data = super()._order_receipt_generate_line_data()

        for idx, line in enumerate(self.lines):
            data = line_data[idx]
            data['lot_names'] = line.pack_lot_ids.mapped('lot_name') if line.pack_lot_ids else False

        return line_data

    def order_receipt_generate_data(self, basic_receipt=False):
        receipt_data = super().order_receipt_generate_data(basic_receipt)
        receipt_data['extra_data']['formated_shipping_date'] = format_date(self.env, self.shipping_date) if self.shipping_date else False
        return receipt_data
