import pytz
from datetime import datetime

from odoo import fields, models


class POSOrder(models.Model):
    _inherit = 'pos.order'

    def _prepare_invoice_vals(self):
        """
        Override to ensure invoice_date complies with ZATCA requirements for SA companies.
        The generic implementation derives invoice_date from the user's local timezone, which
        can produce a future date when the user is in a timezone ahead of Riyadh (e.g. Dubai).
        """
        self.ensure_one()
        vals = super()._prepare_invoice_vals()

        if self.company_id.country_id.code == 'SA':
            sa_tz = pytz.timezone('Asia/Riyadh')
            now_sa = datetime.now(sa_tz).date()
            invoice_dt = (
                fields.Datetime.now()
                if self.session_id.state == 'closed'
                else self.date_order
            )
            invoice_date_sa = invoice_dt.astimezone(sa_tz).date()
            invoice_date = min(invoice_date_sa, now_sa)
            vals['invoice_date'] = invoice_date
            vals['l10n_sa_confirmation_datetime'] = self.env[
                'account.move'
            ]._get_normalized_l10n_sa_confirmation_datetime(invoice_date)

        return vals
