# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class ManufacturingOrderRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(ManufacturingOrderRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.manufacturing.order.rml.report', 'mrp.production',
      'addons_ebits/ebits_custom_mrp/report/manufacturing_order_report_rml.rml', parser=ManufacturingOrderRmlReport, header=False)
