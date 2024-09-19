# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class PosSaleRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(PosSaleRmlReport,self).set_context(objects, data, ids, report_type)
        #self.setCompany(objects[0])
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })

    # @api.multi
    def _get_product_qty(self, pos_id):
        qty_dict = {}
        qty_string = ''
        for line in pos_id.lines:
            if line.qty:
                if line.product_id.uom_id.id in qty_dict:
                    qty_dict[line.product_id.uom_id.id]['product_uom_qty'] += line.qty
                else:
                    qty_dict[line.product_id.uom_id.id] = {
                        'product_uom_qty': line.qty,
                        'product_uom': line.product_id.uom_id and line.product_id.uom_id.name or '' 
                        }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        return qty_string

report_sxw.report_sxw('report.pos.sale.rml.report', 'pos.order',
      'addons_ebits/ebits_custom_pos/report/pos_sale_rml_report.rml', parser=PosSaleRmlReport, header=False)
