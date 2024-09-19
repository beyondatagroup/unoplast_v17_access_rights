# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class InterProcessProductionRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(InterProcessProductionRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.inter.process.production.rml.report', 'inter.process.production',
      'addons_ebits/ebits_custom_mrp/report/inter_process_production_report_rml.rml', parser=InterProcessProductionRmlReport, header=False)
