# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Warehouse Restrictions",
    'version': '1.0',
    'category': 'Warehouse',
    'summary': """
         Warehouse and Stock Location Restriction on Users.""",
    'description': """
        This Module Restricts the User from Accessing Warehouse and Process Stock Moves other than allowed to Warehouses and Stock Locations.""",
    'author': "EBITS TechCon",
    "license": "LGPL-3",
    'website': 'http://www.ebitstechcon.com',
    
    # 'depends': ['base', 'product', 'stock', 'sale', 'purchase', 'mrp', 'account', 'point_of_sale', 'hr'],
    
    'depends': ['base', 'stock'],

    'data': [
        'users_view.xml',
        'security/security.xml', 
        ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
