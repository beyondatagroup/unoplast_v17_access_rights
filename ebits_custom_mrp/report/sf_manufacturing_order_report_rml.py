# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class SfManufacturingOrderRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(SfManufacturingOrderRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.sf.manufacturing.order.rml.report', 'sf.manufacturing.order',
      'addons_ebits/ebits_custom_mrp/report/sf_manufacturing_order_report_rml.rml', parser=SfManufacturingOrderRmlReport, header=False)
