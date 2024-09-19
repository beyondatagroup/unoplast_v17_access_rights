# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class HrLoanRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(HrLoanRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.hr.loan.rml.report', 'hr.loan',
      'addons_ebits/ebits_custom_hr/report/hr_loan_report_rml.rml', parser=HrLoanRmlReport, header=False)
