# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

{
    'name': 'Customized POS Module',
    'version': '1.0',
    'category': 'POS',
    'sequence': 100,
    'summary': 'Customized POS Module',
    'description': """ """,
    'author': 'EBITS TechCon',
    'website': 'http://www.ebitstechcon.com',
    'depends': ['base', 'sale', 'account', 'stock', 'product', 'sale_stock', 'sale_mrp', 'sales_team',
                'point_of_sale', 'ebits_custom_base', 'warehouse_stock_restrictions'],
    'data': [
        "security/ir.model.access.csv",
        "security/pos_security.xml",
        # "wizard/pos_payment.xml",
        "wizard/pos_sale_register_report_view.xml",
        # "wizard/pos_sale_register_detailed_report_view.xml",
        "wizard/pos_invoice_sale_register_report_view.xml",
        # "wizard/pos_invoice_detailed_report_wizard_view.xml",
        "views/point_of_sale_dashboard.xml",
        # "views/pos_order_org_view.xml",
        "views/pos_order_view.xml",
        # "report/pos_sale_report.xml",
        #        "report/pos_sale_report_templates.xml",
    ],
    'license': 'LGPL-3',

    "assets": {
        "point_of_sale._assets_pos": [
            "ebits_custom_pos/static/xml/pos_contact_page.xml",
        ]
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
