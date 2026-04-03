from odoo import models, fields


class Printer(models.Model):
    _inherit = 'printer.printer'

    type = fields.Selection(selection_add=[('epos', 'ePOS')], ondelete={"epos": "set default"})
