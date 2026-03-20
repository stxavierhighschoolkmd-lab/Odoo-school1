from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _grouping_function(self, line):
        res = super()._grouping_function(line)  # Warning return an immutable tuple
        if self.company_id.account_fiscal_country_id.code == 'IN':
            res += (line.l10n_in_hsn_code,)
        return res
