# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class PosSession(models.Model):
    _inherit = 'pos.session'
    
    @api.model
    def _load_pos_data_models(self, config_id):
        data = super()._load_pos_data_models(config_id)
        data += ['mail.template']
        return data

    @api.model
    def _load_pos_self_data_domain(self, data, config):
        return [('config_id', '=', config.id), ('state', '=', 'opened')]

    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if not read_records:
            return read_records

        record = read_records[0]
        record['_self_ordering'] = (
            self.env["pos.config"]
            .sudo()
            .search_count(
                [
                    *self.env["pos.config"]._check_company_domain(self.env.company),
                    '|', ("self_ordering_mode", "=", "kiosk"),
                    ("self_ordering_mode", "=", "mobile"),
                ],
                limit=1,
            )
            > 0
        )
        return read_records

    def update_closing_control_state_session(self, notes):
        super().update_closing_control_state_session(notes)
        self.config_id._notify("SESSION_STATE_CHANGED", {})

    def _set_opening_control_data(self, cashbox_value: int, notes: str):
        super()._set_opening_control_data(cashbox_value, notes)
        self.config_id._notify("SESSION_STATE_CHANGED", {})
