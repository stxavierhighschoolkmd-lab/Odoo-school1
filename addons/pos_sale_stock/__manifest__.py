# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'POS - Sales Stock',
    'version': '1.1',
    'category': 'Sales/Point of Sale',
    'summary': 'Link module between Pos Stock and Sales',
    'description': """

This module adds a custom Sales Team for the Point of Sale. This enables you to view and manage your point of sale sales with more ease.
""",
    'depends': ['pos_stock', 'pos_sale'],
    'data': [
        'views/stock_template.xml',
    ],
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_sale_stock/static/src/**/*',
        ],
        'web.assets_tests': [
            'pos_sale_stock/static/tests/tours/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
