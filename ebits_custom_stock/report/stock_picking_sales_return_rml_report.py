# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class StockPickingSalesReportRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(StockPickingSalesReportRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })
        
    
    def _get_product_qty(self, picking_id):
        qty_dict = {}
        qty_string = ''
        for line in picking_id.move_lines:
            if line.product_uom_qty:
                if line.product_uom.id in qty_dict:
                    qty_dict[line.product_uom.id]['product_uom_qty'] += line.product_uom_qty
                else:
                    qty_dict[line.product_uom.id] = {
                        'product_uom_qty': line.product_uom_qty,
                        'product_uom': line.product_uom and line.product_uom.name or '' 
                        }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        return qty_string

report_sxw.report_sxw('report.stock.picking.sales.return.rml.report', 'stock.picking',
      'addons_ebits/ebits_custom_stock/report/stock_picking_sales_return_rml_report.rml', parser=StockPickingSalesReportRmlReport, header=False)
