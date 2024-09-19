# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

{
    'name': 'Customized Manufacturing Module',
    'version': '17.0',
    'category': 'MRP',
    'sequence': 100,
    'summary': 'Customized Manufacturing Module',
    'description': """Customized Manufacturing Module""",
    'author': 'EBITS TechCon',
    'website': 'http://www.ebitstechcon.com',
    'depends': ['base', 'sale', 'product', 'stock', 'mrp','ebits_custom_base', 'ebits_inventory','mrp_account'],
    'data': [
        "security/ir.model.access.csv",
        "security/security.xml",
        "report/manufacturing_order.xml",
        "report/sf_manufacturing_order.xml",
        # "wizard/mrp_product_produce_wizard_view.xml",
        "wizard/sf_manufacturing_order_report_wizard_view.xml",
        "wizard/manufacturing_order_report_wizard_view.xml",
#        "wizard/ip_production_report_wizard_view.xml", ============ aleredy commneted
#         "wizard/ip_process_report_view.xml",
        "wizard/manufacturing_order_list_report_wizard_view.xml",
        "wizard/raw_material_requirement_report_wizard_view.xml",
        "wizard/record_production_wizard_view.xml",
        "views/manufacturing_order_view.xml",
        "views/mrp_production_view.xml",
        # "views/inter_process_production_view.xml",
        "views/stock_move_view.xml",
        "data/sequence_view.xml",
        # "report/production_report_rml_view.xml"
        ],
    'auto_install': False,
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

