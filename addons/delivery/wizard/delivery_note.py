# Part of Odoo. See LICENSE file for full copyright and licensing details.
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.fields import Command


class DeliveryNote(models.TransientModel):
    _name = "delivery.note"
    _inherit = "delivery.tracker"
    _description = "Delivery Note"

    backorder_id = fields.Many2one(
        string="Back Order of",
        help="If this shipment was split, links to the original shipment.",
        comodel_name="delivery.note",
    )
    backorder_ids = fields.One2many(
        string="Back Orders", comodel_name="delivery.note", inverse_name="backorder_id"
    )
    note_line_ids = fields.One2many(
        string="Operations", comodel_name="delivery.note.line", inverse_name="note_id"
    )
    name = fields.Char(string="Reference", default="/")
    origin = fields.Char(string="Source Document", related="sale_id.name")
    partner_id = fields.Many2one(
        string="Contact", comodel_name="res.partner", related="sale_id.partner_id"
    )
    sale_id = fields.Many2one(string="Sales Order", comodel_name="sale.order")
    shipping_date = fields.Datetime(
        string="Shipping Date",
        help="Date at which the delivery has been processed.",
        default=fields.Datetime.now,
    )

    # === COMPUTE METHODS ===#

    @api.depends(
        "partner_id",
        "carrier_id.max_weight",
        "carrier_id.max_volume",
        "carrier_id.must_have_tag_ids",
        "carrier_id.excluded_tag_ids",
    )
    def _compute_allowed_carrier_ids(self):
        for note in self:
            carriers = self.env["delivery.carrier"].search(
                self.env["delivery.carrier"]._check_company_domain(note.sale_id.company_id)
            )
            note.allowed_carrier_ids = (
                carriers.available_carriers(note.partner_id, note) if note.partner_id else carriers
            )

    # === BUSINESS METHODS ===#

    def action_confirm(self):
        for note in self:
            # Generate the message to be posted on the sale_order
            msg = _("A shipment has been confirmed with %s including:", note.carrier_id.name)
            product_lines = Markup("<br>").join([
                "- %d %s" % (line.product_uom_qty, line.product_id.display_name)
                for line in note.note_line_ids
                if line.product_uom_qty > 0
            ])

            tracking_url = note.carrier_tracking_url
            tracking_url_line = (
                Markup('<br><br><a href="%s">%s</a>') % (tracking_url, _("Track Shipping"))
                if tracking_url
                else ""
            )

            message_post = Markup("%s<br><br>%s%s") % (msg, product_lines, tracking_url_line)

            # If nothing delivered, do nothing
            if not product_lines:
                continue

            # Generate the name
            seq_date = (
                fields.Datetime.context_timestamp(self, note.shipping_date)
                if note.shipping_date
                else None
            )
            note.name = (
                self
                .env["ir.sequence"]
                .with_company(note.sale_id.company_id)
                .next_by_code("delivery.note", sequence_date=seq_date)
                or "/"
            )

            # Create the backorder and set the delivered quantities on the sale order
            note._update_qty_delivered_and_create_backorder()

            # Set the delivery line as delivered
            for line in note.sale_id.order_line:
                if line.is_delivery:
                    line.qty_delivered = line.product_uom_qty

            # Post the message on the sale order and send the confirmation email
            note.sale_id.message_post(body=message_post)
            note._send_confirmation_email()

    def action_cancel(self):
        self.unlink()

    def _find_mail_template(self):
        return self.env.ref(
            "delivery.mail_template_data_delivery_confirmation", raise_if_not_found=False
        )

    def _send_confirmation_email(self):
        delivery_template = self._find_mail_template()
        for note in self:
            delivery_template.send_mail(
                note.id, email_values={"model": "sale.order", "res_id": note.sale_id.id}
            )

    def _update_qty_delivered_and_create_backorder(self):
        """For each line, set the delivered quantity on the sale order. If the delivered quantity
        is less than the ordered quantity, create a backorder with the remaining quantity."""
        self.ensure_one()
        for line in self.note_line_ids:
            # Set the delivered quantity on the sale order
            line.sale_order_line_id.qty_delivered += line.product_uom_qty

        self._create_from_sale_order(self.sale_id, backorder=self)

    def _create_from_sale_order(self, sale_order, backorder=False):
        """Create a delivery note from a sale order."""
        if not sale_order.show_deliver_button:
            return None

        return self.env["delivery.note"].create({
            "backorder_id": backorder.id if backorder else False,
            "carrier_id": sale_order.carrier_id.id,
            "sale_id": sale_order.id,
            "note_line_ids": [
                Command.create({
                    "product_uom_qty": line.product_uom_qty - line.qty_delivered,
                    "quantity_ordered": line.product_uom_qty - line.qty_delivered,
                    "sale_order_line_id": line.id,
                })
                for line in sale_order.order_line.filtered(
                    lambda line: line.product_id.type == "consu"
                )
            ],
        })

    def _get_report_lang(self):
        """Determine language to use for translated description."""
        return self.partner_id.lang or self.env.lang
