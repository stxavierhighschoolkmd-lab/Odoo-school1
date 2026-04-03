# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Domain
from odoo.http import request

from odoo.addons.website_sale.controllers import main


class WebsiteSale(main.WebsiteSale):
    def _prepare_product_values(self, product, category, **kwargs):
        values = super()._prepare_product_values(product, category, **kwargs)
        # We need the user mail to prefill the back of stock notification, so we put it in the value
        # that will be sent
        values["user_email"] = request.env.user.email or request.session.get(
            "stock_notification_email", ""
        )
        return values

    def _get_out_of_stock_ribbon_ids(self, auto_assign_ribbons):
        return set(auto_assign_ribbons.filtered(lambda r: r.assign == "out_of_stock").ids)

    def _has_out_of_stock_products(self, products):
        return any(p._is_sold_out() for p in products)

    def _get_ribbon_filter_domain(self, ribbon):
        if ribbon == "in_stock":
            out_of_stock_ribbon_ids = set(
                request.env["product.ribbon"].sudo().search([("assign", "=", "out_of_stock")]).ids
            )
            products = (
                request.env["product.template"].sudo().search(request.website.sale_product_domain())
            )
            sold_out_ids = products.filtered(
                lambda p: p._is_sold_out() or p.website_ribbon_id.id in out_of_stock_ribbon_ids
            ).ids
            return Domain("id", "not in", sold_out_ids)
        return super()._get_ribbon_filter_domain(ribbon)
