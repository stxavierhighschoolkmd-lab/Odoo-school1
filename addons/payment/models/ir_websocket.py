from odoo import models

from odoo.addons.payment import utils as payment_utils


class IrWebsocket(models.AbstractModel):
    _inherit = "ir.websocket"

    def _build_bus_channel_list(self, channels):
        new_channels = []
        for channel in channels:
            if "payment_transaction_channel" in channel:
                data = channel.split(":")[1]
                tx_id, access_token = data.split(",")
                if tx := self.env["payment.transaction"].browse(int(tx_id)).exists():
                    if payment_utils.generate_access_token(tx.id, env=self.env) == access_token:
                        new_channels.append(tx)
        channels += new_channels
        return channels
