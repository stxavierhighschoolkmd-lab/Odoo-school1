# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # TODO: in master make l10n_hu_eu_vat stored and remove l10n_hu_eu_vat_stored
    l10n_hu_eu_vat_stored = fields.Char(compute='_compute_l10n_hu_eu_vat_stored', store=True)

    @api.depends('vat')
    def _compute_l10n_hu_eu_vat_stored(self):
        for partner in self:
            partner.l10n_hu_eu_vat_stored = partner.l10n_hu_eu_vat
