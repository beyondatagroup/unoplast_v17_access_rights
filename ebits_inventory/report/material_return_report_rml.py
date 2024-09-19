# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class MaterialReturnRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(MaterialReturnRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })
        
    @api.multi 
    def _get_product_qty(self, return_id):
        qty_dict = {}
        qty_string = ''
        for line in return_id.return_lines:
            if line.returned_qty:
                if line.uom_id.id in qty_dict:
                    qty_dict[line.uom_id.id]['returned_qty'] += line.returned_qty
                else:
                    qty_dict[line.uom_id.id] = {
                        'returned_qty': line.returned_qty,
                        'product_uom': line.uom_id and line.uom_id.name or '' 
                        }
        for each in qty_dict:
            if qty_dict[each]['returned_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['returned_qty']) + " " + (qty_dict[each]['product_uom'])
        return qty_string
        
report_sxw.report_sxw('report.material.return.rml.report', 'material.return',
      'addons/ebits_inventory/report/material_return_report_rml.rml', parser=MaterialReturnRmlReport, header=False)
