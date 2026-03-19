import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _replace_tag(line, old_tag, new_tag):
    new_tags = (line.tax_tag_ids - old_tag) | new_tag
    line.tax_tag_ids = [(6, 0, new_tags.ids)]
    return True


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    tax_7 = env['account.tax'].search([('type_tax_use', '=', 'sale'), ('amount', '=', 7.0)])
    tax_5 = env['account.tax'].search([('type_tax_use', '=', 'sale'), ('amount', '=', 5.0)])

    tag_iii_1_base = env['account.account.tag'].search([('name', '=', 'III.1_base')], limit=1)
    tag_iii_1_tax = env['account.account.tag'].search([('name', '=', 'III.1_tax')], limit=1)
    tag_iii_2_base = env['account.account.tag'].search([('name', '=', 'III.2_base')], limit=1)
    tag_iii_2_tax = env['account.account.tag'].search([('name', '=', 'III.2_tax')], limit=1)
    tag_iii_3_base = env['account.account.tag'].search([('name', '=', 'III.3_base')], limit=1)
    tag_iii_3_tax = env['account.account.tag'].search([('name', '=', 'III.3_tax')], limit=1)

    updated_7_base = 0
    updated_7_tax = 0
    updated_5_base = 0
    updated_5_tax = 0

    lines_7 = env['account.move.line'].search(['|', ('tax_line_id', 'in', tax_7.ids), ('tax_ids', 'in', tax_7.ids)])
    lines_5 = env['account.move.line'].search(['|', ('tax_line_id', 'in', tax_5.ids), ('tax_ids', 'in', tax_5.ids)])

    for line in lines_7.with_context(check_move_validity=False):
        if line.tax_line_id in tax_7:
            if _replace_tag(line, tag_iii_1_tax, tag_iii_2_tax):
                updated_7_tax += 1
        elif tax_7 & line.tax_ids:
            if _replace_tag(line, tag_iii_1_base, tag_iii_2_base):
                updated_7_base += 1

    for line in lines_5.with_context(check_move_validity=False):
        if line.tax_line_id in tax_5:
            if _replace_tag(line, tag_iii_1_tax, tag_iii_3_tax):
                updated_5_tax += 1
        elif tax_5 & line.tax_ids:
            if _replace_tag(line, tag_iii_1_base, tag_iii_3_base):
                updated_5_base += 1

    _logger.info('Updated Malta tax grids: 7%% base=%s, 7%% tax=%s, 5%% base=%s, 5%% tax=%s', updated_7_base, updated_7_tax, updated_5_base, updated_5_tax)
