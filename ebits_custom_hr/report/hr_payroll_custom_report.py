# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class HrPayrollRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(HrPayrollRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.hr.payroll.custom.rml', 'hr.payroll.custom',
      'addons_ebits/ebits_custom_hr/report/hr_payroll_custom_report.rml', parser=HrPayrollRmlReport, header=False)
      
class HrPayrollLineRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(HrPayrollLineRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.hr.payroll.line.custom.rml', 'hr.payroll.custom.line',
      'addons_ebits/ebits_custom_hr/report/hr_payroll_line_custom_report.rml', parser=HrPayrollLineRmlReport, header=False)
