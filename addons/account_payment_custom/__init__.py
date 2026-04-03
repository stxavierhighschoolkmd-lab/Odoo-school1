# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models


def post_init_hook(env):
    env["payment.provider"]._setup_payment_method("wire_transfer")
    env.ref("account_payment_custom.cron_auto_confirm_paid_wire_transfer_txs").active = True
