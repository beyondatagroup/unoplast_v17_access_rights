# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class InventoryAdjustmentsRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(InventoryAdjustmentsRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })

    @api.multi 
    def _get_product_qty(self, inventory_id):
        qty_dict = {}
        qty_string = ''
        for line in inventory_id.move_ids:
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
        
report_sxw.report_sxw('report.inventory.adjustments.rml.report', 'stock.inventory',
      'addons/ebits_inventory/report/inventory_adjustments_report_rml.rml', parser=InventoryAdjustmentsRmlReport, header=False)
      

class PhysicalStockRecordRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(PhysicalStockRecordRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })
        
    @api.multi 
    def _get_product_qty(self, inventory_id):
        qty_dict = {}
        qty_string = ''
        for line in inventory_id.line_ids:
            if line.theoretical_qty:
                if line.product_uom_id.id in qty_dict:
                    qty_dict[line.product_uom_id.id]['theoretical_qty'] += line.theoretical_qty
                else:
                    qty_dict[line.product_uom_id.id] = {
                        'theoretical_qty': line.theoretical_qty,
                        'product_uom': line.product_uom_id and line.product_uom_id.name or '' 
                        }
        for each in qty_dict:
            if qty_dict[each]['theoretical_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['theoretical_qty']) + " " + (qty_dict[each]['product_uom'])
        return qty_string

report_sxw.report_sxw('report.physical.stock.record.report', 'stock.inventory',
      'addons/ebits_inventory/report/physical_stock_record_rml.rml', parser=PhysicalStockRecordRmlReport, header=False)
