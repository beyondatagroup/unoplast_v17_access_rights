# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil import relativedelta
import time

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
import pytz

class InternalStockTransferMaster(models.Model):
    _name = 'internal.stock.transfer.master'
    _description = 'Internal Stock Transfer Master'
    
    name = fields.Char(string='Name', copy=False,required=True)
#    production_unit_id = fields.Many2one('res.production.unit', 'Unit', copy=False)
    issuing_warehouse_id = fields.Many2one('stock.warehouse', string='Issuing Warehouse', required=True, copy=False)
    requesting_warehouse_id = fields.Many2one('stock.warehouse', string='Requesting Warehouse', required=True, copy=False)
    allow_auto_request = fields.Boolean('Allow Auto Request Generation', default=False)
    active = fields.Boolean('Active', default=True)

   # @api.multi
    @api.constrains('allow_auto_request', 'requesting_warehouse_id')
    def _check_customer_receipt(self):
        for each in self:
            domain = [
                ('allow_auto_request', '=', True),
                ('requesting_warehouse_id', '=', each.requesting_warehouse_id.id),
                ]
            all_master = self.search_count(domain)
            if all_master > 1:
                raise ValidationError(_('Allow auto request for same requesting warehouse must be configured only once not multiple times! \n'))
            else:
                continue

# InternalStockTransferMaster()
class InternalStockTransferRequest(models.Model):
    _name = 'internal.stock.transfer.request'
    _inherit = ['mail.thread']
    _description = 'Internal Stock Transfer Request'
    _order = 'date_requested desc, id desc'
    
    # @api.one
    @api.depends('request_lines.uom_id', 'request_lines.required_qty')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.request_lines:
            if line.uom_id.id in qty_dict:
                qty_dict[line.uom_id.id]['product_uom_qty'] += line.required_qty
            else:
                qty_dict[line.uom_id.id] = {
                    'product_uom_qty': line.required_qty,
                    'product_uom': line.uom_id and line.uom_id.name or '' 
                    }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        self.total_quantity_based_uom = qty_string
    
    name = fields.Char(string='Request No', copy=False, required=True, readonly=True, default=lambda self: _('STR #'))
    date_requested = fields.Date(string='Requested Date', readonly=True, required=True, default=fields.Date.context_today, copy=False)
    date_required = fields.Date(string='Required Date', required=True, copy=False)
    date_approved = fields.Date(string='Approved Date', readonly=True, copy=False)
    user_id = fields.Many2one('res.users', string='Creator', readonly=True, required=True, default=lambda self: self.env.user, copy=False)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('internal.stock.transfer.request.request'), copy=False)
    warehouse_master_id = fields.Many2one('internal.stock.transfer.master', string='Issuing Warehouse', copy=False)
    requesting_warehouse_id = fields.Many2one('stock.warehouse', string='Requesting Warehouse', required=True, copy=False)
    requester = fields.Char(string='Requester', copy=False)
    request_lines = fields.One2many('internal.stock.transfer.request.lines', 'request_id', string='Stock Transfer Request Line', copy=False)
    approver_user_id = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False)
    required_location_id = fields.Many2one('stock.location', string='Required Location', required=True)
    remarks = fields.Text(string='Remarks', copy=False)
    history = fields.Text(string='History', copy=False)
    issue_id = fields.Many2one('internal.stock.transfer.issue', string='Issue No', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting For Approval'),
        ('done', 'Approved'),
        ('cancelled', 'Rejected'),
        ], string='Status', readonly=True, copy=False, default='draft')
    move_lines = fields.One2many('stock.move', 'internal_stock_transfer_request_id', string='Stock Move', tracking=True)
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Required Quantity')

   # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You cannot delete a form which is not in draft state'))
        return super(InternalStockTransferRequest, self).unlink()

    @api.onchange('requesting_warehouse_id')
    def _onchange_requesting_warehouse_id(self):
        if self.requesting_warehouse_id:
            self.required_location_id = self.requesting_warehouse_id.int_type_id.default_location_src_id and self.requesting_warehouse_id.int_type_id.default_location_src_id.id or False
            self.warehouse_master_id = False
        else:
            self.required_location_id = False
            self.warehouse_master_id = False
    
    @api.onchange('required_location_id')
    def _onchange_required_location_id(self):
        warning = {}
        if self.required_location_id:
            if not self.requesting_warehouse_id:
                self.required_location_id = False
                warning = {
                        'title': _('Warning'),
                        'message': _('Please mention requesting warehouse first')}
                return {'warning': warning}
            if self.required_location_id.id != self.requesting_warehouse_id.int_type_id.default_location_src_id.id:
                self.required_location_id = self.requesting_warehouse_id.int_type_id.default_location_src_id and self.requesting_warehouse_id.int_type_id.default_location_src_id.id or False
                warning = {
                        'title': _('Warning'),
                        'message': _('Cannot be changed.This location is the default source location of the requesting warehouse that you have mentioned')}
                return {'warning': warning}
        return {}
    
   # @api.multi
    def action_send_approval(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        product = {}
        for each in self:
            product = {}
            if not each.request_lines:
                raise UserError(_('No products mentioned!! \nPlease specify the product details'))
            for req_line in each.request_lines:
                if req_line.product_id in product:
                    product[req_line.product_id] += 1
                else:
                    product[req_line.product_id] = 1
            for each_p in product:
                
                if product[each_p] > 1:
                    raise UserError(_('Duplication of product %s will not allow you to send for approval') % (each_p.name_get()[0][1]))
            for line in each.request_lines:
                if line.required_qty <= 0.00:
                    raise UserError(_('Please specify a valid required quantity for the product %s') % (line.product_id.name_get()[0][1]))
                line.state = 'waiting'
                line.qty = line.required_qty
            each.state = 'waiting'
            each.date_requested = fields.Date.today()
            if each.name == "STR #":
                each.name =  self.env['ir.sequence'].next_by_code('internal.stock.transfer.request') or 'STR #'
            if not each.history:
                each.history = "This request has been sent for approval on " + str(date) + " by " + str(self.env.user.name) 
            else:
                each.history += "\nThis request has been sent for approval on " + str(date) + " by " + str(self.env.user.name)
        return True

   # @api.multi
    def action_approve(self):
        issue_obj = self.env['internal.stock.transfer.issue']
        issue_line_obj = self.env['internal.stock.transfer.issue.line']
        date_approved = fields.Date.context_today(self)
        issue = False
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        issuing_location_id = False
        for each in self:
            issuing_location_id = False
            issue = False
            fmt = "%d-%m-%Y %H:%M:%S"
            date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
            for req_line in each.request_lines:
                if req_line.qty <= 0.00:
                    raise UserError(_('Approved quantity cannot be zero or less'))
                if req_line.qty > req_line.required_qty:
                    raise UserError(_('You cannot approve more than the required quantity. The approved quantity for %s is greater than the required quantity') % (req_line.product_id.name_get()[0][1]))
                    
            issuing_location_id = each.sudo().warehouse_master_id.issuing_warehouse_id.int_type_id.default_location_dest_id and each.sudo().warehouse_master_id.issuing_warehouse_id.sudo().int_type_id.default_location_dest_id.id or False
            
            for line in each.request_lines:
                if not issue:
                    issue_id = issue_obj.sudo().create({
                        'requester': each.requester and each.requester or '',
                        'request_id': each.id,
                        'request_no': each.name,
                        'date_requested': each.date_requested and each.date_requested or False,
                        'date_required': each.date_required and each.date_required or False,
                        'date_approved': fields.Date.context_today(self),
                        'approver_user_id': self.env.user.id,
                        'warehouse_master_id': each.sudo().warehouse_master_id and each.sudo().warehouse_master_id.id or False,
                        'request_warehouse': each.requesting_warehouse_id and each.requesting_warehouse_id.name or '',
                        'requesting_location_id': each.required_location_id and each.required_location_id.id or False,
                        'issuing_warehouse_id': each.sudo().warehouse_master_id.issuing_warehouse_id and each.sudo().warehouse_master_id.issuing_warehouse_id.id or False,
                        'issuing_location_id': issuing_location_id,
                        'req_remarks': each.remarks and each.remarks or '',
                        })
                    issue = True
                issue_line_obj.sudo().create({
                    'issue_id': issue_id.id,
                    'product_id': line.product_id and line.product_id.id or False,
                    'uom_id': line.uom_id and line.uom_id.id or False,
                    'approved_qty': line.qty and line.qty or 0.00,
                    'date_required': line.date_required and line.date_required or False,
                    'location_id': issuing_location_id,
                    'request_ref': each.name,
                    })
                line.state = 'done'
            each.write({'state':'done',
                'approver_user_id': self.env.user.id,
                'date_approved': date_approved,
                'issue_id': issue_id.id,
                })
            if issue:
                each.history += "\nThis request has been approved by " + str(self.env.user.name) + " on " + str(date) 
        return True
        
   # @api.multi
    def action_reedit(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.state = 'draft'
            each.history += "\nThis request has been return back to re-edit" + " on " + str(date) + " by " + str(self.env.user.name)  
            for line in each.request_lines:
                line.state = 'draft'
        return True

   # @api.multi
    def action_cancel(self):
        for each in self:
            each.state = 'cancelled'
            for line in each.request_lines:
                line.state = 'cancelled'
        return True

   # @api.multi
    def action_check_stock(self):
        stock_quant_obj = self.env['stock.quant']
        qty_available = 0.00
        stock_available = 0.00
        issuing_location_id = False
        for each in self:
            issuing_location_id = each.sudo().warehouse_master_id.issuing_warehouse_id.int_type_id.default_location_dest_id and each.sudo().warehouse_master_id.issuing_warehouse_id.int_type_id.default_location_dest_id.id or False
            for line in each.request_lines:
                qty_available = 0.00
                stock_available = 0.00
                quant_search = stock_quant_obj.search_read([('location_id', '=', issuing_location_id), ('product_id', '=' ,line.product_id.id)],['inventory_quantity_auto_apply'])
                req_quant_search = stock_quant_obj.search_read([('location_id', '=', each.required_location_id.id), ('product_id', '=' ,line.product_id.id)],['inventory_quantity_auto_apply'])
                for each_quant in quant_search:
                    qty_available += each_quant['inventory_quantity_auto_apply']
                for req_quant in req_quant_search:
                    stock_available += req_quant['inventory_quantity_auto_apply']
                line.write({
                    'dest_loc_stock': qty_available,
                    'req_loc_stock': stock_available
                })
        return True

    def print_internal_stock_transfer_request(self):
        return self.env.ref('ebits_inventory.action_interanl_stock_tran_request').report_action(self)


class InternalStockTransferRequestLines(models.Model):
    _name = 'internal.stock.transfer.request.lines'
    _description = 'Internal Stock Transfer Request Lines'
    
    @api.depends('request_id.move_lines', 'request_id.move_lines.internal_stock_transfer_request_id', 'request_id.move_lines.internal_stock_transfer_issue_id','request_id.move_lines.internal_stock_transfer_receipt_id')
    def get_pending_qty(self):
        for line in self:
            issued_qty, receipt_qty, pending_issue_qty, pending_receipt_qty = 0.00, 0.00, 0.00, 0.00
            for each_move in line.sudo().request_id.move_lines:
                if line.sudo().product_id.id == each_move.sudo().product_id.id:
                    if each_move.sudo().internal_stock_transfer_issue_id:
                        issued_qty += each_move.sudo().product_uom_qty
                    if each_move.sudo().internal_stock_transfer_receipt_id:
                        receipt_qty += each_move.sudo().product_uom_qty
            line.sudo().issued_qty = issued_qty
            line.sudo().received_qty = receipt_qty
            line.sudo().pending_issue_qty = line.sudo().qty - line.sudo().issued_qty
            line.sudo().pending_receipt_qty = line.sudo().issued_qty - line.sudo().received_qty
        
    request_id = fields.Many2one('internal.stock.transfer.request', string='Request No')
    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    required_qty = fields.Float(string='Required Quantity', digits=('Product Unit of Measure'))
    dest_loc_stock = fields.Float(string='Issuing Location Stock', digits=('Product Unit of Measure'), )
    req_loc_stock = fields.Float(string='Requesting Location Stock', digits=('Product Unit of Measure'),)
    qty = fields.Float(string='Approved Quantity', digits=('Product Unit of Measure'))
    issued_qty = fields.Float(compute=get_pending_qty, string='Issued Quantity', digits=('Product Unit of Measure'), store=True, compute_sudo=True)
    pending_issue_qty = fields.Float(compute=get_pending_qty, string='Pending Issue Quantity', digits=('Product Unit of Measure'), store=True, compute_sudo=True)
    received_qty = fields.Float(compute=get_pending_qty, string='Received Quantity', digits=('Product Unit of Measure'), readonly=True, store=True, compute_sudo=True)
    pending_receipt_qty = fields.Float(compute=get_pending_qty, string='Pending to Receive Quantity', digits=('Product Unit of Measure'), store=True, compute_sudo=True)
    date_required = fields.Date(string='Required Date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting For Approval'),
        ('done', 'Done'),
        ('cancelled', 'Rejected'),
        ], string='Request Status', copy=False, default='draft')
    remarks = fields.Text(string='Approver Remarks')
    warehouse_master_id = fields.Many2one('internal.stock.transfer.master', string='Issuing Warehouse', related='request_id.warehouse_master_id',store=True, copy=False)
    requesting_warehouse_id = fields.Many2one('stock.warehouse', string='Requesting Warehouse', related='request_id.requesting_warehouse_id',  store=True, copy=False)
    
   # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You cannot delete an item which is not in draft state'))
        return super(InternalStockTransferRequestLines, self).unlink()
        
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.request_id.state != 'draft':
            raise UserError(_("You can add an item only when the request is in draft state. Click 'Re-Edit' to move to draft state"))
        if self.product_id:
            self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id  or False
        else:
            self.uom_id = False
    
    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        warning = {}
        if self.product_id and self.uom_id:
            if self.uom_id.id != self.product_id.uom_id.id:
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed.')}
        return {'warning': warning}
        
    @api.onchange('required_qty', 'qty')
    def _onchange_required_qty(self):
        warning = {}
        if self.product_id:
            integer, decimal = 0.00, 0.00
            if self.required_qty and (not self.uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.required_qty, 1)
                if decimal:
                    self.required_qty = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the required quantity should not contains decimal value') % (self.uom_id.name)}
                    return {'warning': warning}
            integer, decimal = 0.00, 0.00
            if self.qty and (not self.uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.qty, 1)
                if decimal:
                    self.qty = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the approved quantity should not contains decimal value') % (self.uom_id.name)}
                    return {'warning': warning}




class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    internal_stock_transfer_request_id = fields.Many2one('internal.stock.transfer.request', string='Internal Stock Transfer Request')              

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    internal_stock_transfer_request_id = fields.Many2one('internal.stock.transfer.request', string='Internal Stock Transfer Request')
        
