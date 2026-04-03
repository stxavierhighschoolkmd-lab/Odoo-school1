from odoo import fields, models


class WebsiteFormSendCopyRateLimitLog(models.TransientModel):
    _name = 'website.form.send.copy.rate.limit.log'
    _inherit = ['rate.limit.log']
    _description = 'Website Form Send Copy Rate Limit Log'

    _ip_create_date_idx = models.Index("(ip, create_date)")
    _email_create_date_idx = models.Index("(email, create_date)")

    ip = fields.Char(readonly=True)
    email = fields.Char(readonly=True)

    def _get_rate_limit_rules(self):
        return [
            {'fields': ['ip'], 'limit': 5, 'interval': 3600},
            {'fields': ['email'], 'limit': 3, 'interval': 3600},
        ]
