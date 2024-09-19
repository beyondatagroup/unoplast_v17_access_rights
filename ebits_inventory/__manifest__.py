# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': "Customized Inventory Module",
    'version': '1.0',
    'category': 'Inventory',
    'sequence': 100,
    'summary': 'Customized Inventory Module',
    'description': """Customized Inventory Module
        *Raw Material Issue
        *Material Request Non Returnable
        *Material Request Returnable
        *Material Issue Non Returnable
        *Material Issue Returnable
        *Material Return
        *Stock Transfer
        *Related Reports""",
    'author': 'EBITS TechCon',
    'website': 'http://www.ebitstechcon.com',
    # 'depends': ['base', 'product', 'sale_stock', 'stock', 'hr', 'mrp', 'ebits_custom_base', 'ebits_custom_stock', 'warehouse_stock_restrictions'],
    'depends': ['base', 'product', 'sale_stock', 'stock', 'hr', 'mrp','ebits_custom_base' ,'warehouse_stock_restrictions'],
    "license": "LGPL-3",
    'data': [
        "security/inventory_security.xml",
        "security/ir.model.access.csv",
        "views/inventory_menu.xml",
        "wizard/force_close_raw_issue_view.xml",
        "wizard/raw_material_report_view.xml",
        "wizard/material_issue_report_view.xml",
# #        "wizard/material_return_report_view.xml",
        "wizard/stock_transfer_report_view.xml",
#         "wizard/transit_loss_report_view.xml",
         "wizard/product_movement_report_view.xml",
# #        "wizard/material_issue_detailed_report_view.xml",
#         #"wizard/intertransfer_request_merge_view.xml",
#         "wizard/intertransfer_issue_merge_view.xml",
        # "wizard/auto_scheduler_request_wizard.xml",
        "wizard/material_issue_register_report_view.xml",
        "wizard/material_return_register_report_view.xml",
        "wizard/internal_stock_transfer_register_report_view.xml",
        "wizard/internal_stock_transfer_receipt_report_view.xml",
        "wizard/internal_stock_transfer_req_summary_report_view.xml",
        "views/raw_material_issue_view.xml",
        "views/raw_material_return_line_view.xml",
        "views/material_request_view.xml",
        "views/material_request_lines_view.xml",
        "views/material_issue_view.xml",
        "views/material_issue_lines_view.xml",
        "views/material_return_view.xml",
        "views/internal_stock_transfer_request_view.xml",
        "views/internal_stock_transfer_issue_view.xml",
        "views/internal_stock_transfer_receipt_view.xml",
        "views/stock_warehouse_view.xml",
        "views/ir_sequence_data.xml",
        "data/sequence_view.xml",
        "data/auto_scheduler_data.xml",
        "report/internal_stock_transfer_report.xml",
        "report/raw_material_issue_report.xml",
        "report/material_issue_report.xml",
        "report/material_return_report.xml",
        "report/internal_stock_transfer_issue.xml",
        "report/internal_stock_transfer_receipt.xml",
        "report/material_request_report.xml",
        # "report/material_moves_report_view.xml",
        # "report/report_inventory_adjustments.xml",
         ],
    'auto_install': False,
    'installable': True,
    'application': True,
}
