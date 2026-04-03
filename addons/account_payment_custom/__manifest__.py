# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Payment Custom / Account Payment",
    "category": "Accounting/Payment Custom",
    "sequence": 350,
    "summary": "Bridge between payment_custom and account_payment.",
    "description": " ",  # Non-empty string to avoid loading the README file.
    "depends": ["account_payment", "payment_custom"],
    "data": ["data/ir_cron.xml"],
    "auto_install": True,
    "post_init_hook": "post_init_hook",
    "author": "Odoo S.A.",
    "license": "LGPL-3",
}
