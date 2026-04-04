from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_uz_vat_registry = fields.Char(string="VAT Registry (VAT ID)")

    @api.constrains('country_id', 'l10n_uz_vat_registry')
    def _check_l10n_uz_vat_registry(self):
        for partner in self:
            if vat_registry_len := partner.l10n_uz_vat_registry and len(partner.l10n_uz_vat_registry):
                if partner.country_id.code == 'UZ' and (vat_registry_len != 12 or not partner.l10n_uz_vat_registry.isdigit()):
                    raise ValidationError(self.env._("VAT Registry does not seem to be valid. It must be of 12 digits for residents."))
                elif partner.country_id.code != 'UZ' and (vat_registry_len != 9 or not partner.l10n_uz_vat_registry.isdigit()):
                    raise ValidationError(self.env._("VAT Registry does not seem to be valid. It must be of 9 digits for non-residents."))
