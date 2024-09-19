# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class InventoryValuationRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(InventoryValuationRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.lc.rml.report', 'lc.report.wizard',
      'addons_ebits/ebits_custom_account/report/lc_report_rml.rml', parser=InventoryValuationRmlReport, header=False)
