# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class BankAccountReconciliationRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(BankAccountReconciliationRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.bank.account.reconciliation.rml.report', 'bank.account.rec.statement',
      'addons_ebits/ebits_custom_account/report/bank_account_reconciliation_rml.rml', parser=BankAccountReconciliationRmlReport, header=False)
      
report_sxw.report_sxw('report.reconciled.entry.rml.report', 'bank.account.rec.statement',
      'addons_ebits/ebits_custom_account/report/reconciled_report_rml.rml', parser=BankAccountReconciliationRmlReport, header=False)
      
report_sxw.report_sxw('report.unreconciled.entry.rml.report', 'bank.account.rec.statement',
      'addons_ebits/ebits_custom_account/report/unreconciled_report_rml.rml', parser=BankAccountReconciliationRmlReport, header=False)
