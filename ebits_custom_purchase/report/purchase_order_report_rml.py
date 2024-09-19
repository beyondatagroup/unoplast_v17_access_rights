# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class PurchaseOrderRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(PurchaseOrderRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })
        
    @api.multi
    def _get_product_qty(self, order_id):
        qty_dict = {}
        qty_string = ''
        for line in order_id.order_line:
            if line.product_qty:
                if line.product_uom.id in qty_dict:
                    qty_dict[line.product_uom.id]['product_qty'] += line.product_qty
                else:
                    qty_dict[line.product_uom.id] = {
                        'product_qty': line.product_qty,
                        'product_uom': line.product_uom and line.product_uom.name or '' 
                        }
        for each in qty_dict:
            if qty_dict[each]['product_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_qty']) + " " + (qty_dict[each]['product_uom'])
        return qty_string
        
report_sxw.report_sxw('report.purchase.order.rml.report', 'purchase.order',
      'addons_ebits/ebits_custom_purchase/report/purchase_order_report_rml.rml', parser=PurchaseOrderRmlReport, header=False)
      
        
report_sxw.report_sxw('report.purchase.order.service.rml.report', 'purchase.order',
      'addons_ebits/ebits_custom_purchase/report/purchase_order_service_report_rml.rml', parser=PurchaseOrderRmlReport, header=False)
