# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class AccountMoveForexRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(AccountMoveForexRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.account.move.forex.rml.report', 'account.move.forex',
      'addons_ebits/ebits_custom_account/report/account_move_forex_report_rml.rml', parser=AccountMoveForexRmlReport, header=False)
