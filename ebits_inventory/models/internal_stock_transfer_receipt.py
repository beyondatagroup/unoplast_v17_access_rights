# -*- coding: utf-8 -*-
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

class InternalStockTransferReceipt(models.Model):
    _name = 'internal.stock.transfer.receipt'
    _inherit = ['mail.thread']
    _description = 'Internal Stock Transfer Receipt'
    _order = 'id desc'
    
    # @api.one
    # @api.depends('receipt_lines.uom_id', 'receipt_lines.received_qty')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.receipt_lines:
            if line.uom_id.id in qty_dict:
                qty_dict[line.uom_id.id]['product_uom_qty'] += line.received_qty
            else:
                qty_dict[line.uom_id.id] = {
                    'product_uom_qty': line.received_qty,
                    'product_uom': line.uom_id and line.uom_id.name or '' 
                    }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        self.total_quantity_based_uom = qty_string
    
    name = fields.Char(string='Receipt No', copy=False, required=True, readonly=True, default=lambda self: _('STRPT #'))
    issue_id = fields.Many2one('internal.stock.transfer.issue', string='Issue No', readonly=True, copy=False, required=True)
    date_required = fields.Date(string='Required Date', copy=False, required=True, readonly=True)
    date_last_received = fields.Date(string='Last Received Date', copy=False, readonly=True)
    date_last_issue = fields.Date(string='Last Issued Date', copy=False, readonly=True)
    date_requested = fields.Date(string='Requested Date', copy=False, readonly=True, required=True)
    date_probable = fields.Date(string='Probable Date of Delivery', copy=False, readonly=True)
    date_approved = fields.Datetime(string='Approved Date', copy=False, readonly=True)
    issuer_user_id = fields.Many2one('res.users', string='Issuer', copy=False, readonly=True)
    receiver_user_id = fields.Many2one('res.users', string='Last Received by', copy=False, readonly=True)
    approver_user_id = fields.Many2one('res.users', string='Approved By', copy=False, readonly=True, required=True)
    warehouse_master_id = fields.Many2one('internal.stock.transfer.master', string='Issuing From', copy=False)
    issue_warehouse = fields.Char(string='Issuing Warehouse', readonly=True, copy=False)
    receiving_warehouse_id = fields.Many2one('stock.warehouse', string='Receiving Warehouse', readonly=True, copy=False, required=True)
    issuing_location_id = fields.Many2one('stock.location', string='Issuing Location', readonly=True, copy=False, required=True)
    receiving_location_id = fields.Many2one('stock.location', string='Receiving Location', readonly=True, copy=False, required=True)
    issue_ref = fields.Char(string="Issue Ref", size=64, copy=False, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('internal.stock.transfer.receipt'), copy=False)
    requester = fields.Char(string='Requester', readonly=True, copy=False)
    request_id = fields.Many2one('internal.stock.transfer.request', string='Request ID', readonly=True, copy=False)
    request_no = fields.Char(string='Request No', readonly=True, copy=False)
    receipt_lines = fields.One2many('internal.stock.transfer.receipt.line', 'receipt_id', string='Receipt', required=True)
    history = fields.Text(string='History', readonly=True, default=' ')
    closed = fields.Boolean(string='Force Closed')
    driver_id = fields.Many2one('truck.driver.employee', string="Driver", readonly=True)
    vehicle_no = fields.Char(string="Vehicle No", size=64, copy=False, readonly=True)
    vehicle_owner = fields.Char(string="Vehicle Owner", size=64, copy=False, readonly=True)
    vehicle_owner_address = fields.Char(string="Vehicle Owner Address", size=128, copy=False, readonly=True)
    driver_licence = fields.Char(string="Driver Licence No", size=64, copy=False, readonly=True)
    driver_name = fields.Char(string="Driver Name", size=64, copy=False, readonly=True)
    driver_licence_type = fields.Char(string="Driver Licence Type", size=64, copy=False, readonly=True)
    driver_licence_place = fields.Char(string="Issued Licence Place", size=64, copy=False, readonly=True)
    driver_phone = fields.Char(string="Driver Contact No", size=64, copy=False, readonly=True)
    agent_name = fields.Char(string="Agent Name", size=64, copy=False, readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Reference', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('partial', 'Partially Received'),
        ('done', 'Done'),
        ], string='Status', readonly=True, copy=False, default='draft', index=True, tracking=True)
    move_lines = fields.One2many('stock.move', 'internal_stock_transfer_receipt_id', string='Stock Move', tracking=True)
    remarks = fields.Text(string='Issued Remarks', readonly=True)
    force_closed_reason = fields.Text(string='Force Closed Reason', readonly=True)
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Received Quantity')
    
   # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You cannot delete a form which is only  in draft state'))
        return super(InternalStockTransferReceipt, self).unlink()
        
   # @api.multi
    def action_receive(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        picking_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        picking = False
        picking_id = False
        for each in self:
            for line in each.receipt_lines:
                if line.receipt_qty > 0.00:
                    if line.receipt_qty <= line.pending_receipt_qty:
                        line.received_qty += line.receipt_qty
                        if each.name == 'STRPT #':
                            each.name =  self.env['ir.sequence'].next_by_code('internal.stock.transfer.receipt') or 'STRPT #'
                        each.state = 'partial'
                        line.state  = 'partial' if line.pending_receipt_qty != 0.00 else 'done' 
                        if not picking:
                            picking_id = picking_obj.create({
                                'location_id': each.sudo().warehouse_master_id.issuing_warehouse_id.transit_location_id and each.sudo().warehouse_master_id.issuing_warehouse_id.transit_location_id.id or False,
                                'location_dest_id': each.receiving_location_id and each.receiving_location_id.id or False,
                                'origin': each.name or '',
                                'picking_type_id': each.receiving_warehouse_id.sudo().int_type_id and each.receiving_warehouse_id.sudo().int_type_id.id or False,
                                'driver_id': each.driver_id and each.driver_id.id or False,
                                'vehicle_no': each.vehicle_no and each.vehicle_no or '',
                                'vehicle_owner': each.vehicle_owner and each.vehicle_owner or '',
                                'vehicle_owner_address': each.vehicle_owner_address and each.vehicle_owner_address or '',
                                'driver_licence': each.driver_licence and each.driver_licence or '',
                                'driver_name': each.driver_name and each.driver_name or '',
                                'driver_licence_type': each.driver_licence_type and each.driver_licence_type or '',
                                'driver_licence_place': each.driver_licence_place and each.driver_licence_place or '',
                                'driver_phone': each.driver_phone and each.driver_phone or '',
                                'agent_name': each.agent_name and each.agent_name or '',
                                'internal_stock_transfer_receipt_id': each.id,
                                'internal_stock_transfer_issue_id': each.sudo().issue_id and each.sudo().issue_id.id or False,
                            })
                            picking = True
                        move_obj.create({
                            'product_id': line.product_id and line.product_id.id or False,
                            'product_uom': line.uom_id and line.uom_id.id or False,
                            'product_uom_qty': line.receipt_qty and line.receipt_qty or False,
                            'name': (line.product_id.name_get()[0][1] + ' / ' + each.name or ''),
                            'origin': each.name or '',
                            'location_dest_id': each.receiving_location_id and each.receiving_location_id.id or False,
                            'location_id': each.sudo().warehouse_master_id.issuing_warehouse_id.transit_location_id and each.sudo().warehouse_master_id.issuing_warehouse_id.transit_location_id.id or False,
                            'picking_id': picking_id.id,
                            'internal_stock_transfer_receipt_id': each.id,
                            'internal_stock_transfer_receipt_line_id': line.id,
                            'internal_stock_transfer_request_id': line.receipt_id.request_id and line.receipt_id.request_id.id or False,
                            'internal_stock_transfer_issue_id': line.receipt_id.sudo().issue_id and line.receipt_id.sudo().issue_id.id or False,
                            'picking_type_id': each.receiving_warehouse_id.sudo().int_type_id and each.receiving_warehouse_id.sudo().int_type_id.id or False
                        })
                        line.receipt_qty = 0.00
                    else:
                        raise UserError(_('Receipt not completed.The receipt qty for the product %s is greater than the pending receipt quantity.Please change the receipt quantity and try again') % (line.product_id.name_get()[0][1]))
                line.receipt_qty = 0.00
            if picking_id:
                picking_id.action_confirm()
                picking_id.action_assign()
                picking_id.force_assign()
                for pack_line in picking_id.move_ids_without_package:
                    pack_line.write({'product_packaging_quantity': pack_line.product_qty})
                # picking_id.do_transfer()
                each.action_receipt_state_update()
                picking_id.button_validate()
                each.date_last_received = fields.Date.context_today(self)
                each.receiver_user_id = self.env.user.id
                each.picking_id = picking_id.id
                if each.state != 'done':
                    each.history += '\nPartially received by ' + str(self.env.user.name) + ' on ' + str(date)
                else:
                    each.history += '\nThe final receipt has been received by ' + str(self.env.user.name) + ' on ' + str(date)
        return True         
              
   # @api.multi
    def action_receipt_state_update(self):
        flag = []
        for each in self:
            for line in each.receipt_lines:
                if line.state != 'done':
                    flag.append('no')
            if 'no' in flag:
                each.write({'state': 'partial'})
            else:
                each.write({'state': 'done'})
        return True


class InternalStockTransferReceiptline(models.Model):
    _name = 'internal.stock.transfer.receipt.line'
    _inherit = ['mail.thread']
    _description = 'Internal Stock Transfer Receipt Line'

    @api.depends('received_qty', 'issued_qty')
    def get_pending_qty(self):
        for line in self:
            line.pending_receipt_qty = line.issued_qty - line.received_qty
    
    receipt_id = fields.Many2one('internal.stock.transfer.receipt', string='Receipt No', ondelete='cascade', required=True)
    request_no = fields.Char(string='Request No', related='receipt_id.request_no', readonly=True, copy=False, store=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True, required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True, required=True)
    issued_qty = fields.Float(string='Issued Quantity', digits=('Product Unit of Measure'), readonly=True)
    date_required = fields.Date(string='Required Date', readonly=True, required=True)
    receipt_qty = fields.Float(string='Receipt Quantity', digits=('Product Unit of Measure'))
    received_qty = fields.Float(string='Received Quantity', digits=('Product Unit of Measure'), readonly=True)
    pending_receipt_qty = fields.Float(compute='get_pending_qty', string='Pending Receipt Quantity', digits=('Product Unit of Measure'), readonly=True, store=True)
    closed = fields.Boolean(string='Force Closed')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('partial', 'Partially Received'),
        ('done', 'Done'),
        ], string='Receipt Status', readonly=True, copy=False, default='draft', index=True, tracking=True)
    remarks = fields.Text(string='Remarks', readonly=True)
    warehouse_master_id = fields.Many2one('internal.stock.transfer.master', string='Issuing From', related='receipt_id.warehouse_master_id', readonly=True, store=True, copy=False)
    issue_warehouse = fields.Char(string='Issuing Warehouse', related='receipt_id.issue_warehouse', readonly=True, store=True, copy=False)
    receiving_warehouse_id = fields.Many2one('stock.warehouse', string='Receiving Warehouse', related='receipt_id.receiving_warehouse_id', readonly=True, copy=False, store=True)
    issuing_location_id = fields.Many2one('stock.location', string='Issuing Location', related='receipt_id.issuing_location_id', readonly=True, copy=False, store=True)
    receiving_location_id = fields.Many2one('stock.location', string='Receiving Location', related='receipt_id.receiving_location_id', readonly=True, copy=False, store=True)
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
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
        
    @api.onchange('receipt_qty')
    def _onchange_receipt_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            if self.receipt_qty and (not self.uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.receipt_qty, 1)
                if decimal:
                    self.receipt_qty = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the receipt quantity should not contains decimal value') % (self.uom_id.name)}
                    return {'warning': warning}

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    internal_stock_transfer_receipt_id = fields.Many2one('internal.stock.transfer.receipt', string='IST Receipt')
    internal_stock_transfer_receipt_line_id = fields.Many2one('internal.stock.transfer.receipt.line', string='IST Receipt Line')
    
class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    internal_stock_transfer_receipt_id = fields.Many2one('internal.stock.transfer.receipt', string='Internal Stock Transfer Receipt')
    
