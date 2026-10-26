{
    'name': 'Technical Test - Odoo 17 Solution',
    'version': '17.0.1.0.0',
    'category': 'Operations',
    'summary': 'ROP Management, Inventory Validations, POS Enhancements, Ecommerce ROP Views, and REST APIs',
    'description': """
        Technical Test Module for Odoo 17:
        - Inventory: Outgoing picking validation, ROP fields (has_rop, rop_count) on product.template, smart buttons, ROP menus.
        - POS: Stock ROP validation (< 5 units) with notification, Payment screen customer validation (+2 phone), "Cash now" quick-checkout with invoice printing.
        - Ecommerce: ROP low-stock view (/shop/rop), on-hand stock update wizard/popup with warehouse notifications, Real-time ROP view (/shop/realtime-rop), /rop-product endpoint.
        - APIs: Authenticated Odoo endpoints for Orders by date range, Products with ROP count, Add/Update ROP count, and POS session orders.
    """,
    'author': 'Abdallah Moustafa Hafez',
    'depends': ['base', 'product', 'stock', 'point_of_sale', 'website', 'website_sale', 'sale', 'mail', 'bus'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/inventory_menus.xml',
        'views/website_rop_templates.xml',
        'wizard/update_product_qty_wizard_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'technical_test/static/src/app/**/*',
        ],
        'web.assets_frontend': [
            'technical_test/static/src/js/website_rop.js',
            'technical_test/static/src/css/website_rop.css',
        ],
        'point_of_sale.assets_qunit_tests': [
            'web/static/src/legacy/js/public/public_widget.js',
            'technical_test/static/src/js/website_rop.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install' : False,
    'license': 'LGPL-3',
}
