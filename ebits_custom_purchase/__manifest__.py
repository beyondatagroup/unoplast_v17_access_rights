# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.
{
    'name': 'Customized Purchase Module',
    'version': '1.0',
    'category': 'Purchase',
    'sequence': 150,
    'summary': 'Customized Purchase Module',
    'description': """ """,
    'author': 'EBITS TechCon',
    'maintainer': 'EBITS TechCon',
    'website': 'http://www.ebitstechcon.com',
    # 'depends': ['base', 'purchase', 'account', 'stock', 'product', 'stock_landed_costs', 'ebits_custom_base'],
    'depends': ['base','portal', 'purchase', 'account', 'stock', 'product','ebits_custom_base','account_external_tax','stock_landed_costs','account_check_printing'],
    'data': [
        "security/purchase_security.xml",
        "security/ir.model.access.csv",
        "wizard/purchase_requisition_extend_wizard_view.xml",
        "wizard/purchase_order_wizard.xml",
        "wizard/purchase_order_report_wizard_view.xml",
        "wizard/purchase_register_report_wizard_view.xml",
        # "wizard/purchase_req_report_view.xml",
        "wizard/po_billing_detail_report_view.xml",
        "wizard/po_register_billing_detail_report_view.xml",
        "wizard/product_qty_wizard_view.xml",
        "wizard/po_product_loc_qty_wizard_view.xml",
        "wizard/purchase_invoice_register_report_wizard_view.xml",
        "wizard/purchase_invoice_detailed_report_wizard_view.xml",
        "wizard/purchase_invoice_register_summary_report_view.xml",
        # "wizard/incoming_products_report_view.xml",
        "views/purchase_requisition_extend_view.xml",
        "views/purchase_order.xml",
        "views/purchase_dashboard_view.xml",
        "views/product_template.xml",
        "views/res_partner.xml",
        "views/purchase_menu.xml",
        "views/account_move_line.xml",
        "report/purchase_orders_report.xml",
        "report/header_footer_purchase_report.xml",
        # "report/purchase_order_report_view.xml",
        # 'data/mail_template_data.xml',
         ],
    'auto_install': False,
    'installable': True,
    'application': True,
    'license': 'LGPL-3',

'assets': {

    'web.assets_frontend':[
            'ebits_custom_purchase/static/css/tree_css.css',]
}
}

