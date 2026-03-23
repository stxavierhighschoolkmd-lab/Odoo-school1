# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _apply_inventory(self, date=None):
        """Override to trigger auto-publish check after manual inventory adjustments."""
        # Capture template IDs before super() clears inventory_quantity on the quants.
        template_ids = self.product_id.product_tmpl_id.ids
        res = super()._apply_inventory(date=date)
        if template_ids:
            try:
                # Flush pending writes and drop the full ORM cache so that free_qty
                # is recomputed from the quant quantities just committed by _apply_inventory.
                self.env.flush_all()
                self.env.invalidate_all()
                # Re-browse in a clean environment so there is no stale cached data.
                templates = self.env["product.template"].sudo().browse(template_ids)
                templates._check_auto_publish_state()
            except Exception:
                _logger.exception("Error during auto-publish check after inventory adjustment")
        return res
