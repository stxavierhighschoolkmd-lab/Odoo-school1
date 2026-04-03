# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class TestRateLimitLog(models.TransientModel):
    _name = 'test.rate.limit.log'
    _inherit = ['rate.limit.log']
    _description = 'Test Rate Limit Log'

    scope = fields.Char(readonly=True)
    key = fields.Char(readonly=True)

    def _get_rate_limit_rules(self):
        return [
            {'fields': ['scope'], 'limit': 3, 'interval': 3600},
            {'fields': ['scope', 'key'], 'limit': 2, 'interval': 3600},
        ]
