# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, api, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    branch_code = fields.Char("Branch Code", default='000', compute='_compute_branch_code', store=True)
    l10n_ph_entity_type = fields.Selection([
            ('individual', 'Individual'),
            ('corporation', 'Corporation'),
        ],
        string='Type of Entity',
        help='Philippines: Defines the type of entity.'
    )
    first_name = fields.Char("First Name")
    middle_name = fields.Char("Middle Name")
    last_name = fields.Char("Last Name")
    l10n_ph_rdo = fields.Char("RDO", help="Revenue District Office")

    @api.model
    def _commercial_fields(self):
        return super()._commercial_fields() + ['branch_code']

    @api.depends('vat', 'country_id')
    def _compute_branch_code(self):
        for partner in self:
            branch_code = '000'
            if partner.country_id.code == 'PH' and partner.vat:
                match = partner._check_vat_ph_re.match(partner.vat)
                branch_code = match and match.group(1) and match.group(1)[1:] or branch_code
            partner.branch_code = branch_code

    @api.constrains('l10n_ph_entity_type', 'first_name', 'middle_name', 'last_name')
    def _check_entity_fields(self):
        for partner in self:
            if partner.l10n_ph_entity_type == 'corporation' and (partner.first_name or partner.middle_name or partner.last_name):
                raise ValidationError(self.env._("First name, middle name, and last name should not be filled for corporation entities."))
