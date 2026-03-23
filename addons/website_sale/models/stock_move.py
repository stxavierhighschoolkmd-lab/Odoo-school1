# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        """Override to trigger auto-publish check after stock moves are confirmed.

        Skipped when called from _apply_inventory (which sets ignore_dest_packages=True),
        because StockQuant._apply_inventory handles that path after all quants are committed.
        """
        res = super()._action_done(cancel_backorder=cancel_backorder)
        if res and not self.env.context.get("ignore_dest_packages"):
            try:
                res.product_id.product_tmpl_id.sudo()._check_auto_publish_state()
            except Exception:
                _logger.exception("Error during auto-publish check after stock move confirmation")
        return res
