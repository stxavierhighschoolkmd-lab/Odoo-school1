from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_uz_vat_registry = fields.Char(related='partner_id.l10n_uz_vat_registry', readonly=False)
