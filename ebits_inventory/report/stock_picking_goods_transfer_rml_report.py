# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class StockPickingGoodsTransferRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(StockPickingGoodsTransferRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })
        
    @api.multi
    def _get_product_qty(self, picking_id):
        qty_dict = {}
        qty_string = ''
        for line in picking_id.pack_operation_ids:
            if line.qty_done:
                if line.product_uom_id.id in qty_dict:
                    qty_dict[line.product_uom_id.id]['qty_done'] += line.qty_done
                else:
                    qty_dict[line.product_uom_id.id] = {
                        'qty_done': line.qty_done,
                        'product_uom_id': line.product_uom_id and line.product_uom_id.name or '' 
                        }
        for each in qty_dict:
            if qty_dict[each]['qty_done'] and qty_dict[each]['product_uom_id']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['qty_done']) + " " + (qty_dict[each]['product_uom_id'])
        return qty_string

report_sxw.report_sxw('report.stock.picking.goods.transfer.rml.report', 'stock.picking',
      'addons/ebits_inventory/report/stock_picking_goods_transfer_report.rml', parser=StockPickingGoodsTransferRmlReport, header=False)
