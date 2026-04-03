# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route

from odoo.addons.website_sale.controllers.cart import Cart as WebsiteSaleCart


class Cart(WebsiteSaleCart):
    @route()
    def cart(self, **post):
        if order_sudo := request.cart:
            order_sudo._update_programs_and_rewards()
            order_sudo._auto_apply_rewards()
        return super().cart(**post)

    def _cart_values(self, **post):
        values = super()._cart_values(**post)
        if order_sudo := request.cart:
            values["promotion_progress_bars"] = order_sudo._get_promotion_progress_bars(
                include_applied=True
            )
        return values

    @route("/wallet/top_up", type="http", auth="user", website=True, sitemap=False)
    def wallet_top_up(self, **kwargs):
        product = self.env["product.product"].browse(int(kwargs["trigger_product_id"]))
        self.add_to_cart(product.product_tmpl_id.id, product.id, 1)
        return request.redirect("/shop/cart")

    @route()
    def add_to_cart(self, *args, **kwargs):
        order_before = request.cart
        applied_before = set()
        if order_before:
            applied_before = {p.id for p in order_before._get_applied_programs()}

        result = super().add_to_cart(*args, **kwargs)

        order_after = request.cart
        if order_after:
            bars = [
                bar
                for bar in order_after._get_promotion_progress_bars(include_applied=True)
                if not bar["just_matched"] or bar["program_id"] not in applied_before
            ]
            if bars:
                for notif in result.get("notifications", []):
                    if notif["type"] == "item_added":
                        notif["data"]["promotion_progress_bars"] = bars
                        break
        return result

    @route()
    def update_cart(self, *args, **kwargs):
        result = super().update_cart(*args, **kwargs)
        order_sudo = request.cart
        if order_sudo:
            result["website_sale.total"] = request.env["ir.ui.view"]._render_template(
                "website_sale.total",
                {
                    "website_sale_order": order_sudo,
                    "promotion_progress_bars": order_sudo._get_promotion_progress_bars(
                        include_applied=True
                    ),
                },
            )
        return result
