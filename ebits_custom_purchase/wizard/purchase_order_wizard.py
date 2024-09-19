# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
import math
import pytz
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp

class PurchaseOrderCancelWizard(models.TransientModel):
    _name = "purchase.order.cancel.wizard"
    _description = "Purchase Order Cancel Reason"
    
    name = fields.Text(string='Cancel Reason', required=True)
    purchase_id = fields.Many2one('purchase.order', string="Purchase Order", required=True)
    
    # @api.multi
    def action_cancel(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            purchase_id = each.purchase_id
            if purchase_id.history:
                history = purchase_id.history + "\n"  
            purchase_id.history = history + 'This document is cancelled by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name
            purchase_id.button_cancel()
        return True
            
class PurchaseOrderApprovewWizard(models.TransientModel):
    _name = "purchase.order.approve.wizard"
    _description = "Purchase Order Approve Reason"
    
    name = fields.Text(string='Approval Reason', required=True)
    purchase_id = fields.Many2one('purchase.order', string="Purchase Order", required=True)
    
    # @api.multi
    def action_approve(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            purchase_id = each.purchase_id
            if purchase_id.history:
                history = purchase_id.history + "\n"
            if purchase_id.two_approver_ids:
                purchase_id.history = history + 'This document is approved and sent for 2nd Level Approval by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name
            else: 
                purchase_id.history = history + 'This document is approved by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name
            purchase_id.action_one_approve() 
            
class PurchaseOrderTwoApprovewWizard(models.TransientModel):
    _name = "purchase.order.two.approve.wizard"
    _description = "Purchase Order 2nd Approve Reason"
    
    name = fields.Text(string='Approval Reason', required=True)
    purchase_id = fields.Many2one('purchase.order', string="Purchase Order", required=True)
    
    # @api.multi
    def action_approve(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            purchase_id = each.purchase_id
            if purchase_id.history:
                history = purchase_id.history + "\n"  
            purchase_id.history = history + 'This document is approved by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name
            purchase_id.action_two_approve()
            
class PurchaseOrderAmendmentWizard(models.TransientModel):
    _name = "purchase.order.amendment.wizard"
    _description = "Purchase Order Amendment Reason"
    
    name = fields.Text(string='Amendment Reason', required=True)
    purchase_id = fields.Many2one('purchase.order', string="Purchase Order", required=True)
    
    # @api.multi
    def action_amend(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        amendment_no = 0
        for each in self:
            purchase_id = each.purchase_id
            if purchase_id.history:
                history = purchase_id.history + "\n"  
            purchase_id.history = history + 'This document is amended by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name
            purchase_id.button_cancel()
            purchase_id.button_draft()
            if purchase_id.amendment_no:
                amendment_no = purchase_id.amendment_no
            purchase_id.write({'one_approved_id': False, 
                'one_approved_date': False, 
                'two_approved_id': False,
                'two_approved_date': False,
                'one_approver_ids': [],
                'two_approver_ids': [],
                'amendment_no': amendment_no + 1})
            
class PurchaseOrderHistoryWizard(models.TransientModel):
    _name = "purchase.order.history.wizard"
    _description = "Purchase Order History Wizard"
    
    po_line_id = fields.Many2one('purchase.order.line', string='Purchase Line')
    pending_requisition_ids = fields.One2many('pending.requisition.line.wizard', 'history_id', "Pending Requisition Lines")
    pending_picking_ids = fields.One2many('pending.picking.line.wizard', 'history_id', "Pending GRN Lines")
    last_invoice_ids = fields.One2many('last.invoice.line.wizard', 'history_id', "Last 10 Purchase(s) Lines")
    po_location_stock_ids = fields.One2many('po.location.stock.wizard', 'history_id', "Location Wise Stock")

    @api.model
    def default_get(self, fields):
        res = super(PurchaseOrderHistoryWizard, self).default_get(fields)
        purchase_line_id = self.env['purchase.order.line'].sudo().browse(self.env.context.get('active_id')) 
        res['po_line_id'] = purchase_line_id and purchase_line_id.id or False 
        pr_line_search = self.env['po.requisition.item.lines'].sudo().search([('state', '=', 'approved'), ('requisition_id.category_id', '=', purchase_line_id.order_id.category_id.id),('product_id', '=', purchase_line_id.product_id.id)])
        requisition_line = []
        for line in pr_line_search:
            temp_line = {}
            if line.to_ordered_qty:
                temp_line['requisition_id'] = line.requisition_id and line.requisition_id.id or False
                temp_line['product_id'] = line.product_id and line.product_id.id or False
                temp_line['uom_id'] = line.uom_id and line.uom_id.id or False
                temp_line['required_date'] = line.date_required and line.date_required or False
                temp_line['approved_qty'] = line.to_ordered_qty and line.to_ordered_qty or 0.00
                requisition_line.append((0, 0, temp_line)) 
        res.update({"pending_requisition_ids": requisition_line})
        
        # Update to use stock.move.line instead of stock.pack.operation
        pack_search = self.env['stock.move.line'].sudo().search([
            ('state', 'not in', ('done', 'cancel')),
            ('picking_id.picking_type_id.warehouse_id', '=', purchase_line_id.order_id.warehouse_id.id),
            ('product_id', '=', purchase_line_id.product_id.id)
        ])        
        
        # pack_search = self.env['stock.pack.operation'].sudo().search([('state', 'not in', ('done', 'cancel')), ('picking_id.picking_type_id.warehouse_id', '=', purchase_line_id.order_id.warehouse_id.id),('product_id', '=', purchase_line_id.product_id.id)])
        
        pending_picking_ids = []
        for line in pack_search:
            picking_line = {}
            picking_line['picking_id'] = line.picking_id and line.picking_id.id or False
            picking_line['product_id'] = line.product_id and line.product_id.id or False
            picking_line['uom_id'] = line.product_uom_id and line.product_uom_id.id or False
            picking_line['qty'] = line.quantity and line.quantity or 0.00
            picking_line['schedule_date'] = line.picking_id.scheduled_date and line.picking_id.scheduled_date or False
            picking_line['partner_id'] = line.picking_id.partner_id and line.picking_id.partner_id.id or False
            picking_line['origin'] = line.picking_id.origin and line.picking_id.origin or ""
            pending_picking_ids.append((0, 0, picking_line)) 
        res.update({"pending_picking_ids": pending_picking_ids}) 
        
        # inv_search = self.env['account.invoice.line'].sudo().search([('invoice_id.state', 'not in', ('draft', 'cancel')), ('invoice_id.type', '=', 'in_invoice'),('product_id', '=', purchase_line_id.product_id.id)], limit=10)
        
        inv_search = self.env['account.move.line'].sudo().search([
            
            ('move_id.state', 'not in', ('draft', 'cancel')),
            ('move_id.move_type', '=', 'in_invoice'),
            ('product_id', '=', purchase_line_id.product_id.id)

        ], limit=10)
        
        last_invoice_ids = []
        for line in inv_search:
            inv_line = {}
            inv_line['move_id'] = line.move_id and line.move_id.id or False
            # inv_line['invoice_id'] = line.invoice_id and line.invoice_id.id or False
            inv_line['product_id'] = line.product_id and line.product_id.id or False
            
            inv_line['uom_id'] = line.product_id.uom_id and line.product_id.uom_id.id or False

            # inv_line['uom_id'] = line.uom_id and line.uom_id.id or False
            inv_line['qty'] = line.quantity and line.quantity or 0.00
            inv_line['price_unit'] = line.price_unit and line.price_unit or 0.00
            inv_line['price_total'] = line.price_subtotal and line.price_subtotal or 0.00
            inv_line['date_invoice'] = line.move_id.invoice_date and line.move_id.invoice_date or False
            # inv_line['date_invoice'] = line.invoice_id.date_invoice and line.invoice_id.date_invoice or False
            
            inv_line['partner_id'] = line.move_id.partner_id and line.move_id.partner_id.id or False
            
            inv_line['origin'] = line.move_id.invoice_origin and line.move_id.invoice_origin or ""
            
            last_invoice_ids.append((0, 0, inv_line)) 
        
        res.update({"last_invoice_ids": last_invoice_ids}) 
        
        location_ids = self.env['stock.location'].search([('usage','in', ['transit', 'internal'])])
        location_lines = []
        stock_quant_obj = self.env['stock.quant']
        
        for each_location_id in location_ids:
            temp_location_lines = {}
            qty_available_uom = {}
            
            quant_search = stock_quant_obj.sudo().search_read([('location_id', '=', each_location_id.id), ('product_id', '=' , purchase_line_id.product_id.id)],['quantity', 'product_uom_id'])
            
            # quant_search = stock_quant_obj.sudo().search_read([('location_id', '=', each_location_id.id), ('product_id', '=' , purchase_line_id.product_id.id)],['qty', 'product_uom_id'])
            
            for each_quant in quant_search:
                if each_quant['product_uom_id'] in qty_available_uom:
                    qty_available_uom[each_quant['product_uom_id']] += each_quant['quantity']
                else:
                    qty_available_uom[each_quant['product_uom_id']] = 0.000
                    qty_available_uom[each_quant['product_uom_id']] += each_quant['quantity']
            for each_uom in qty_available_uom:
                if qty_available_uom[each_uom]:
                    temp_location_lines = {}
                    temp_location_lines = {
                        'location_id': each_location_id.id,
                        'qty_available': qty_available_uom[each_uom],
                        'product_uom': each_uom,
                        }
                    location_lines.append((0, 0, temp_location_lines))
        res.update({"po_location_stock_ids": location_lines})
        print("\n\n\n\n\n\n=====location_lines=======",location_lines)
        return res
    
class PendingRequisitionLineWizard(models.TransientModel):
    _name = "pending.requisition.line.wizard"
    _description = "Pending Requisition Line Wizard" 
    
    history_id = fields.Many2one('purchase.order.history.wizard', string="Purchase History Wizard", ondelete="cascade")
    requisition_id = fields.Many2one('purchase.requisition.extend', string='PR Reference', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='UOM', readonly=True)
    required_date = fields.Date(string='Required Date', readonly=True)
    approved_qty = fields.Float(string='To Be Ordered Qty', readonly=True, digits='Product Unit of Measure')
    
class PendingPickingLineWizard(models.TransientModel):
    _name = "pending.picking.line.wizard"
    _description = "Pending Picking Line Wizard" 
    
    history_id = fields.Many2one('purchase.order.history.wizard', string="Purchase History Wizard", ondelete="cascade")
    picking_id = fields.Many2one('stock.picking', string='GRN No', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='UOM', readonly=True)
    qty = fields.Float(string='Pending Qty', readonly=True, digits='Product Unit of Measure')
    schedule_date = fields.Date(string='Expected Delivery Date', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    origin = fields.Char(string='Source Document', readonly=True)
    
class LastInvoiceLineWizard(models.TransientModel):
    _name = "last.invoice.line.wizard"
    _description = "Last 10 Invoice Line Wizard" 
    
    history_id = fields.Many2one('purchase.order.history.wizard', string="Purchase History Wizard", ondelete="cascade")
    invoice_id = fields.Many2one('account.move', string='Invoice No', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='UOM', readonly=True)
    qty = fields.Float(string='Qty', readonly=True, digits='Product Unit of Measure')
    price_unit = fields.Float(string='Unit Price', readonly=True, digits='Purchase Product Price')
    price_total = fields.Float(string='Subtotal', readonly=True, digits='Product Price')
    date_invoice = fields.Date(string='Invoice Date', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    origin = fields.Char(string='Source Document', readonly=True)

class PoLocationStockWizard(models.TransientModel):
    _name = 'po.location.stock.wizard'
    _description = "PO Location Stock Wizard"

    history_id = fields.Many2one('purchase.order.history.wizard', string="Purchase History Wizard", ondelete="cascade")
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)
    qty_available = fields.Float(string='Qty', readonly=True, digits='Product Unit of Measure')
    product_uom = fields.Many2one('uom.uom', string='UOM', readonly=True)
    
