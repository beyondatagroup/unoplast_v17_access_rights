# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class RawMaterialIssueRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(RawMaterialIssueRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })
        
        
    @api.multi 
    def _get_product_qty(self, issue_id):
        qty_dict = {}
        qty_string, mtrs_string = "", ""
        for line in issue_id.return_lines:
            if line.total_returned_qty or total_returned_mtrs:
                if line.uom_id.id in qty_dict:
                    qty_dict[line.uom_id.id]['total_returned_qty'] += line.total_returned_qty and line.total_returned_qty or 0.00
                    qty_dict[line.uom_id.id]['total_returned_mtrs'] += line.total_returned_mtrs and line.total_returned_mtrs or 0.00
                else:
                    qty_dict[line.uom_id.id] = {
                        'total_returned_qty': line.total_returned_qty and line.total_returned_qty or 0.00,
                        'total_returned_mtrs': line.total_returned_mtrs and line.total_returned_mtrs or 0.00,
                        'product_uom': line.uom_id and line.uom_id.name or '' 
                        }
        for each in qty_dict:
            if qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['total_returned_qty']) + " " + (qty_dict[each]['product_uom'])
                if mtrs_string:
                    mtrs_string += " , "
                mtrs_string += "{0:.3f}".format(qty_dict[each]['total_returned_mtrs']) + " Mtrs"
        return {'qty_string': qty_string, 'mtrs_string': mtrs_string}
        
report_sxw.report_sxw('report.raw.material.issue.rml.report', 'raw.material.issue',
      'addons/ebits_inventory/report/raw_material_issue_report_rml.rml', parser=RawMaterialIssueRmlReport, header=False)
