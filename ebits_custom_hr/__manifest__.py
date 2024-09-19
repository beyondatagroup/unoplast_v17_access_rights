# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

{
    'name': 'Customized HR Module',
    'version': '1.0',
    'category': 'Account',
    'sequence': 100,
    'summary': """
        * Customized HR Module
        * HR Loan Management""",
    'description': """
        * Customized HR Module
        * HR Loan Management""",
    'license': "LGPL-3",    
    'author': 'EBITS TechCon',
    'website': 'http://www.ebitstechcon.com',
    'depends': ['base', 'hr', 'ebits_custom_base', 'warehouse_stock_restrictions'],
    'data': [

        "security/security.xml",
        "security/ir.model.access.csv",
        # "wizard/hr_loan_wizard_view.xml",
        # "wizard/hr_loan_emi_pay_wizard_view.xml",
        # "wizard/hr_payroll_custom_wizard_view.xml",
        # "wizard/hr_payroll_custom_upload_template_view.xml",
        # "wizard/hr_loan_report_wizard_view.xml",
        # "wizard/hr_payroll_custom_report_view.xml",
        "views/hr_employee_view.xml",
        # "views/hr_loan_view.xml",
        # "views/hr_payroll_custom_view.xml",
        # "views/hr_report.xml",
        # "data/sequence_view.xml", 
        # "report/hr_loan_report_rml_view.xml",
        
        ],
        
    'installable': True,
    'auto_install': False,
    'application': True,
}
