# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import api, fields, models


class DeliveryTracker(models.AbstractModel):
    _name = "delivery.tracker"
    _description = "Delivery Tracker"

    allowed_carrier_ids = fields.Many2many(
        comodel_name="delivery.carrier", compute="_compute_allowed_carrier_ids"
    )
    carrier_id = fields.Many2one(
        string="Carrier",
        comodel_name="delivery.carrier",
        domain="[('id', 'in', allowed_carrier_ids)]",
    )
    carrier_tracking_ref = fields.Char(string="Tracking Reference", copy=False)
    carrier_tracking_url = fields.Char(
        string="Tracking URL", compute="_compute_carrier_tracking_url"
    )

    def _compute_allowed_carrier_ids(self):
        for tracker in self:
            carriers = self.env["delivery.carrier"].search([])
            tracker.allowed_carrier_ids = carriers

    @api.depends("carrier_id", "carrier_tracking_ref")
    def _compute_carrier_tracking_url(self):
        for tracker in self:
            tracker.carrier_tracking_url = (
                tracker.carrier_id.get_tracking_link(tracker)
                if tracker.carrier_id and tracker.carrier_tracking_ref
                else False
            )

    def get_multiple_carrier_tracking(self):
        self.ensure_one()
        try:
            return json.loads(self.carrier_tracking_url)
        except (ValueError, TypeError):
            return False
