# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Egypt - Withholding Tax',
    'icon': '/account/static/description/l10n.png',
    'author': 'Odoo S.A.',
    'category': 'Accounting/Localizations/Account Charts',
    'website': 'https://www.odoo.com/documentation/latest/applications/finance/fiscal_localizations/egypt.html',
    'description': """
Egypt Withholding Tax Module

Force the installation of the Withholding Tax on Payment module
""",
    'depends': ['l10n_account_withholding_tax', 'l10n_eg'],
    'auto_install': ['l10n_eg'],
    'license': 'LGPL-3',
}
