# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import SQL


class WebsiteVisitor(models.Model):
    _inherit = "website.visitor"

    visitor_product_count = fields.Integer(
        string="Product Views",
        help="Total number of views on products",
        compute="_compute_product_statistics",
    )
    product_ids = fields.Many2many(
        string="Visited Products",
        comodel_name="product.product",
        compute="_compute_product_statistics",
    )
    product_count = fields.Integer(
        string="Products Views",
        help="Total number of product viewed",
        compute="_compute_product_statistics",
    )

    @api.depends("website_track_ids")
    def _compute_product_statistics(self):
        results = self.env["website.track"]._read_group(
            [
                ("visitor_id", "in", self.ids),
                ("product_id", "!=", False),
                (
                    "product_id",
                    "any",
                    self.env["product.product"]._check_company_domain(self.env.companies),
                ),
            ],
            ["visitor_id"],
            ["product_id:array_agg", "__count"],
        )
        mapped_data = {
            visitor.id: {"product_count": count, "product_ids": product_ids}
            for visitor, product_ids, count in results
        }

        for visitor in self:
            visitor_info = mapped_data.get(visitor.id, {"product_ids": [], "product_count": 0})

            visitor.product_ids = [(6, 0, visitor_info["product_ids"])]
            visitor.visitor_product_count = visitor_info["product_count"]
            visitor.product_count = len(visitor_info["product_ids"])

    def _get_additional_track_query_parts(self, **kwargs):
        select_extra, cols_extra, vals_extra = super()._get_additional_track_query_parts(**kwargs)
        if product_id := kwargs.get('product_id'):
            return (
                SQL(
                    "%(og_select)s, %(product_id)s AS product_id",
                    og_select=select_extra,
                    product_id=product_id,
                ),
                SQL(
                    "%(og_cols)s, product_id",
                    og_cols=cols_extra,
                ),
                SQL(
                    "%(og_vals)s, product_id::integer",
                    og_vals=vals_extra,
                ),
            )
        return select_extra, cols_extra, vals_extra

    def _add_viewed_product(self, product_id):
        # Remove this?
        """Add a website_track with a page marked as viewed."""
        self.ensure_one()
        if product_id and self.env["product.product"].browse(product_id)._is_variant_possible():
            domain = [("product_id", "=", product_id)]
            website_track_values = {"product_id": product_id}
            self._add_tracking(domain, website_track_values)
