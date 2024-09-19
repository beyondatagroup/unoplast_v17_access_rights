# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class JournalEntriesRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(JournalEntriesRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.journal.entries.rml.report', 'account.move',
      'addons_ebits/ebits_custom_account/report/journal_entries_report_rml.rml', parser=JournalEntriesRmlReport, header=False)
