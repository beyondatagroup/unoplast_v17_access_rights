# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

{
    'name': 'Customized Basic Module',
    'version': '1.0',
    'category': 'All Modules Dependency',
    'sequence': 100,
    'summary': 'This Module is the Basic Module(Customized one) for all the installed module',
    'description': """ """,
    'license': 'LGPL-3',
    'website': 'http://www.ebitstechcon.com',
    'author': 'EBITS TechCon',
    'depends': ['base', 'stock', 'product', 'sale', 'account', 'purchase', 'sales_team', 
        'sale_stock', 'mail', 'point_of_sale', 'hr', 'contacts', 'warehouse_stock_restrictions'
        ],

    #'warehouse_stock_restrictions'

    'data': [
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizard/credit_limit_update.xml",
        "wizard/partner_pricelist_update.xml",
        "wizard/ir_sequence_wizard_view.xml",
        "wizard/customer_data_update_wizard_view.xml",
        "views/res_partner_registration.xml",
        "views/ir_sequence_view.xml",
        "views/product_view.xml",
        "views/res_production_unit_view.xml",
        "views/res_partner_view.xml",
        "views/sale_view.xml",
        "views/res_currency_view.xml",
        "views/master_view.xml",
        "data/sequence_view.xml",
        ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
