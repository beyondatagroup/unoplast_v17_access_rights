# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class CreditNoteRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(CreditNoteRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })
        
    @api.multi
    def _get_product_qty(self, invoice_id):
        qty_dict = {}
        qty_string = ''
        for line in invoice_id.invoice_line_ids:
            if line.product_id.type != 'service' and line.quantity:
                    if line.uom_id.id in qty_dict:
                        qty_dict[line.uom_id.id]['product_uom_qty'] += line.quantity
                    else:
                        qty_dict[line.uom_id.id] = {
                            'product_uom_qty': line.quantity,
                            'product_uom': line.uom_id and line.uom_id.name or '' 
                            }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        return qty_string
        
report_sxw.report_sxw('report.credit.note.rml.report', 'account.invoice',
      'addons_ebits/ebits_custom_account/report/credit_note_report_rml.rml', parser=CreditNoteRmlReport, header=False)
      
report_sxw.report_sxw('report.credit.note.cash.rml.report', 'account.invoice',
      'addons_ebits/ebits_custom_account/report/credit_note_cash_report_rml.rml', parser=CreditNoteRmlReport, header=False)
      
      
class DebitNoteRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(DebitNoteRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_product_qty': self._get_product_qty,
        })
        
    @api.multi
    def _get_product_qty(self, invoice_id):
        qty_dict = {}
        qty_string = ''
        for line in invoice_id.invoice_line_ids:
            if line.product_id.type != 'service' and line.quantity:
                    if line.uom_id.id in qty_dict:
                        qty_dict[line.uom_id.id]['product_uom_qty'] += line.quantity
                    else:
                        qty_dict[line.uom_id.id] = {
                            'product_uom_qty': line.quantity,
                            'product_uom': line.uom_id and line.uom_id.name or '' 
                            }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        return qty_string
        
report_sxw.report_sxw('report.debit.note.rml.report', 'account.invoice',
      'addons_ebits/ebits_custom_account/report/debit_note_report_rml.rml', parser=DebitNoteRmlReport, header=False)
