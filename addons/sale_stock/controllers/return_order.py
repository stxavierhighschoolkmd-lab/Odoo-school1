# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from collections import defaultdict

from odoo.exceptions import AccessError, MissingError
from odoo.http import request, route

from odoo.addons.sale.controllers import portal as sale_portal


class CustomerPortal(sale_portal.CustomerPortal):

    @route(
        '/return/order/content',
        type='jsonrpc', auth='user', website=True, readonly=True
    )
    def return_order_content(self, order_id, access_token):
        """Prepare return details of order depending on deliveries.

        :param int order_id: The order for which we are preparing return content.
        :param str access_token: The access token used to authenticate the request.
        :rtype: dict.
        :return: A dict containing a list of returnable lines vals depending on deliveries.
        """
        try:
            sale_order = self._document_check_access(
                'sale.order', order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        return_data = {
            'company_name': sale_order.company_id.name,
            'warehouse_address': sale_order.warehouse_id.partner_id.address,
            'returnable_lines': [],
            'return_reasons': [{
                'id': reason.id,
                'name': reason.name,
            } for reason in request.env['return.reason'].search([])],
        }
        for line in sale_order.order_line:
            if not line._is_returnable():
                continue

            common_line_vals = {
                'name': line.product_id.with_context(display_default_code=False).display_name,
                'currency': line.currency_id.id,
                'description_sale': line.name,
                'price': line.price_unit,
                'product_id': line.product_id.id,
            }

            for move in line.move_ids:
                picking = move.picking_id
                if picking.picking_type_code != 'outgoing' or picking.state != 'done':
                    continue

                returned_qty = sum(
                    rm.quantity for rm in move.returned_move_ids if rm.state == 'done'
                )
                remaining_delivered_qty = move.quantity - returned_qty
                if remaining_delivered_qty:
                    return_data['returnable_lines'].append({
                        **common_line_vals,
                        **picking._get_return_details(),
                        'delivered_qty': remaining_delivered_qty,
                        'lot_name': move.lot_ids and ', '.join(move.lot_ids.mapped('name')) or '',
                    })

        return return_data

    @route('/my/orders/return_order/download_label', type='http', auth="user")
    def return_order_dowload_label(
        self, order_id, access_token=False, selected_lines='', return_reason=''
    ):
        """Download return report of picking for selected products."""
        try:
            sale_order = self._document_check_access(
                'sale.order', int(order_id), access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        selected_lines_list = json.loads(selected_lines)
        return_product_qty_by_delivery = defaultdict(dict)
        for line in selected_lines_list:
            delivery_id = line['delivery_id']
            product_id = line['product_id']
            return_product_qty_by_delivery[delivery_id][product_id] = line['quantity']

        return_data = {
            'wh_address_id': sale_order.warehouse_id.partner_id,
            'return_product_qty_by_delivery': return_product_qty_by_delivery,
            'return_reason': self.env['return.reason'].browse(int(return_reason)),
        }

        pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'sale_stock.action_report_return_label',
            list(return_product_qty_by_delivery.keys()), data=return_data,
        )[0]
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
        ]
        return request.make_response(pdf, headers=pdfhttpheaders)
