# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


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
        self._compute_visitor_statistics(
            rel_field='product_ids',
            track_field='product_id',
            count_field='visitor_product_count',
            unique_count_field='product_count',
            extra_domain=[
                ('product_id', 'any', self.env['product.product']._check_company_domain(self.env.companies))
            ],
        )

    def _add_viewed_product(self, product_id):
        """Add a website_track with a page marked as viewed."""
        self.ensure_one()
        if product_id and self.env["product.product"].browse(product_id)._is_variant_possible():
            domain = [("product_id", "=", product_id)]
            website_track_values = {"product_id": product_id}
            self._add_tracking(domain, website_track_values)
