# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class L10n_LatamDocumentType(models.Model):
    _inherit = 'l10n_latam.document.type'

    internal_type = fields.Selection(
        selection_add=[
            ('invoice_in', 'Purchase Invoices'),
            ('payment', 'Payments'),
        ],
    )
