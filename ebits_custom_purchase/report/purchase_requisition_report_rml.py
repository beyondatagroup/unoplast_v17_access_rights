# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class PurchaseRequisitionRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(PurchaseRequisitionRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })
        
    @api.multi
    def _get_product_qty(self, requisition_id):
        qty_dict = {}
        qty_string = ''
        for line in requisition_id.purchase_line:
            if line.approved_qty:
                if line.uom_id.id in qty_dict:
                    qty_dict[line.uom_id.id]['approved_qty'] += line.approved_qty
                else:
                    qty_dict[line.uom_id.id] = {
                        'approved_qty': line.approved_qty,
                        'uom_id': line.uom_id and line.uom_id.name or '' 
                        }
        for each in qty_dict:
            if qty_dict[each]['approved_qty'] and qty_dict[each]['uom_id']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['approved_qty']) + " " + (qty_dict[each]['uom_id'])
        return qty_string
        
report_sxw.report_sxw('report.purchase.requisition.rml.report', 'purchase.requisition.extend',
      'addons_ebits/ebits_custom_purchase/report/purchase_requisition_report_rml.rml', parser=PurchaseRequisitionRmlReport, header=False)
