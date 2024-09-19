# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import json
from lxml import etree
from datetime import timedelta
import time
import pytz
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import odoo.addons.decimal_precision as dp
import logging

_logger = logging.getLogger(__name__)

class PosMakePayment(models.TransientModel):
    _inherit = 'pos.make.payment'
    
    def _default_amount_to_be_paid(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            order = self.env['pos.order'].browse(active_id)
            return (order.amount_total - order.amount_paid)
        return False

    amount_tendered = fields.Float(digits=(16, 2), string="Amount Received", copy=False)
    amount_balance = fields.Float(digits=(16, 2), string="Balance To Be Given", copy=False)
    amount_to_be_paid = fields.Float(digits=(16, 2), required=True, default=_default_amount_to_be_paid, string="Amount To be Paid")

    # @api.multi
    def check(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            order = self.env['pos.order'].browse(active_id)
            order.date_order = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            if order.name == '/':
                if order.pos_refund:
                    if not order.session_id.config_id.refund_sequence_id:
                        raise UserError("To return product(s), you need to set a refund sequence in pos configuration.")
                    order.name = order.session_id.config_id.refund_sequence_id._next()
                else:
                    if not order.session_id.config_id.sequence_id:
                        raise UserError("To register payment, you need to set a sequence in pos configuration.")
                    order.name = order.session_id.config_id.sequence_id._next()
        res = super(PosMakePayment, self).check()
        return res
    
    # @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PosMakePayment, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        context = self._context
        if context.get('active_model') == 'pos.order' and context.get('active_ids'):
            pos = self.env['pos.order'].browse(context['active_ids'])[0]
            journal_ids = pos.session_id.config_id.journal_ids
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='journal_id']"):
                journal_id = []
                for each in journal_ids:
                    journal_id.append(each.id)
                node.set('domain', "[('id', 'in', " + str(journal_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res
        
    # @api.multi
    def action_check_stock_qty(self):
        quant_obj = self.env['stock.quant']
        qty_available, move_qty_available = 0.00, 0.00
        for each in self:
            for each_line in each.pack_operation_product_ids:
                qty_available = 0.00
                quant_search = quant_obj.search_read([('location_id','=', each_line.location_id.id),('product_id','=', each_line.product_id.id)],['qty'])
                for each_quant_qty in quant_search:
                    qty_available += each_quant_qty['qty']
                each_line.write({'qty_onhand': qty_available})    
            for each_move in each.move_lines:
                move_qty_available = 0.00
                quant_search = quant_obj.search_read([('location_id','=', each_move.location_id.id),('product_id','=', each_move.product_id.id)],['qty'])
                for each_quant_qty in quant_search:
                    move_qty_available += each_quant_qty['qty']
                each_move.write({'qty_onhand': move_qty_available})
        return True
        
    # @api.model
    def default_get(self, fields):
        quant_obj = self.env['stock.quant']
        pos_obj = self.env['pos.order']
        qty_available = 0.00
        if len(self.env.context.get('active_ids', list())) > 1:
            raise UserError("You may pay only one order at a time!")
        res = super(PosMakePayment, self).default_get(fields)
        pos_order = pos_obj.browse(self.env.context.get('active_id'))
        if pos_order:
            for line in pos_order.lines:
                if line.product_id.type != 'service':
                    qty_available = 0.00
                    quant_search = quant_obj.search_read([('location_id','=', pos_order.location_id.id),('product_id','=', line.product_id.id)],['qty'])
                    for each_quant_qty in quant_search:
                        qty_available += each_quant_qty['qty']
                    if qty_available < line.qty:
                        raise UserError(_("You cannot do the payment until the product %s stock is available!. \n Availabile stock is %s") % (line.product_id.name, qty_available))
        return res
        
    @api.onchange('amount', 'amount_to_be_paid')
    def _onchange_amount_to_be_paid(self):
        warning = {}
        if self.amount and self.amount_to_be_paid:
            if self.amount_to_be_paid < self.amount:
                warning = {
                    'title': _('Warning!'),
                    'message': (_('Entered amount (%s) is greater than the actual amount to be paid (%s)!') % (self.amount, self.amount_to_be_paid)),
                }
                self.amount = self.amount_to_be_paid
        return {'warning': warning}    

    @api.onchange('amount', 'amount_tendered', 'amount_balance')
    def _onchange_amount_tendered(self):
        if self.amount or self.amount_tendered:
            if self.amount_tendered > self.amount:
                self.amount_balance = self.amount_tendered - self.amount
            else:
                self.amount_balance = 0.00
        return {}
