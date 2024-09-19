# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

from datetime import datetime
import time
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
import pytz

class InternalLocationTransfer(models.Model):
    _name = 'internal.location.transfer'
    _description = 'Internal Location Transfer'
    _order = 'id desc'
    
    
    @api.depends('transfer_lines.uom_id', 'transfer_lines.quantity')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.transfer_lines:
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
        self.total_quantity_based_uom = qty_string
    
    name = fields.Char(string='Transfer No', required=True, readonly=True, default=lambda self: _('Transfer #'), copy=False)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('internal.location.transfer'), copy=False)
    date_transfer = fields.Date(string='Transfer Date', required=True, readonly=True, default=fields.Date.context_today, copy=False)
    date_approved = fields.Date(string='Approved Date', readonly=True, copy=False)
    user_id = fields.Many2one('res.users', string='Creator', readonly=True, required=True, default=lambda self: self.env.user, copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', required=True, copy=False)
    location_id = fields.Many2one('stock.location', string='Source Location', required=True, copy=False,  )
    location_dest_id = fields.Many2one('stock.location', string='Destination Location', required=True, copy=False,  )
    transfer_lines = fields.One2many('internal.transfer.lines', 'transfer_id', string='Internal Transfer Line', copy=False)
    approver_user_id = fields.Many2one('res.users', string='Approved by', readonly=True, copy=False)
    history = fields.Text(string='History', copy=False, default=' ', readonly=True)
    view_location_id = fields.Many2one('stock.location', string='View Location', copy=False)
    remarks = fields.Text(string='Remarks', copy=False, )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting For Approval'),
        ('done', 'Transfered'),
        ('cancel', 'Cancel'),
        ], string='Status', readonly=True, copy=False, default='draft')
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Quantity')
        
    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        warning = {}
        if self.warehouse_id:
            self.view_location_id = self.warehouse_id.view_location_id and self.warehouse_id.view_location_id.id or False
            self.location_id = False
            self.location_dest_id = False
        else:
            self.view_location_id = False
    
    
    def action_send_approval(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        product = {}
        for each in self:
            if not each.transfer_lines:
                raise UserError(_("Internal transfer line item should not be empty!.\nKindly select product and proceed forward"))
            for req_line in each.transfer_lines:
                if req_line.product_id in product:
                    product[req_line.product_id] += 1
                else:
                    product[req_line.product_id] = 1
            for each_p in product:
                if product[each_p] > 1:
                    raise UserError(_("Duplication of product %s will not allow you to proceed forward!") % (each_p.name_get()[0][1]))
            each.action_check_stock()
            for line in each.transfer_lines:
                if line.quantity <= 0.00:
                    raise UserError(_("Zero quantity.\nTransfer not sent due to zero quantity entered"))
                if (line.quantity > line.source_loc_stock):
                    raise UserError(_("Transfer quantity (%s) for the product (%s) is lesser than source location stock (%s).\nKindly check stock or reduce the quantity") % (line.quantity, line.product_id.name_get()[0][1], line.source_loc_stock))
            if each.name == 'Transfer #':
                each.name = self.env['ir.sequence'].next_by_code('internal.location.transfer.code') or 'Transfer #'
            each.write({
                'name': each.name,
                'state': 'waiting',
                'history': each.history + "\nThis Transfer has been sent for approval by " + str(self.env.user.name) + " on " + str(date) 
                    })
        return True

    
    def action_approve(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        picking_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        picking_id = False
        for each in self:
            each.action_check_stock()
            for each_line in each.transfer_lines:
                if each_line.quantity <= 0.00:
                    raise UserError(_("Zero quantity.\nTransfer not sent due to zero quantity entered"))
                if (each_line.quantity > each_line.source_loc_stock):
                    raise UserError(_("Transfer quantity (%s) for the product (%s) is lesser than source location stock (%s).\nKindly check stock or reduce the quantity") % (each_line.quantity, each_line.product_id.name_get()[0][1], each_line.source_loc_stock))
            for line in each.transfer_lines:
                if not picking_id:
                    picking_id = picking_obj.create({
                        'location_dest_id':  each.location_dest_id and each.location_dest_id.id or False,
                        'location_id': each.location_id and each.location_id.id or False,
                        'origin': each.name and each.name or '',
                        'picking_type_id': each.warehouse_id.int_type_id and each.warehouse_id.int_type_id.id or False
                    }) 
                move_id = move_obj.create({
                    'name': line.product_id and line.product_id.name_get()[0][1] + " / " + each.name or "",
                    'company_id': line.company_id and line.company_id.id or False,
                    'product_id': line.product_id and line.product_id.id or False,
                    'product_uom': line.uom_id and line.uom_id.id or False,
                    'product_uom_qty': line.quantity and line.quantity or 0.00,
                    'location_id': each.location_id and each.location_id.id or False,
                    'location_dest_id': each.location_dest_id and each.location_dest_id.id or False,
                    'origin': each.name,
                    'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                    'picking_id': picking_id.id,
                    'picking_type_id': each.warehouse_id.int_type_id and each.warehouse_id.int_type_id.id or False
                })
            each.write({
                'state': 'done',
                'date_approved': fields.Datetime.now(),
                'approver_user_id': self.env.user.id,
                'history': each.history + "\nThis Transfer has been approved by " + str(self.env.user.name) + " on " +str(date) 
                    })
            if picking_id:
                picking_id.action_confirm()
                picking_id.action_assign()
                # picking_id.force_assign()
                # for pack_line in picking_id.pack_operation_product_ids:
                #     pack_line.write({'qty_done': pack_line.product_qty})
                # picking_id.do_transfer()
        return True
        
    
    def action_cancel(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.write({
                'state': 'cancel',
                'history': each.history + "\nThis Transfer has been cancelled by " + str(self.env.user.name) + " on " + str(date)
                })
        return True

    
    def action_check_stock(self):
        stock_quant_obj = self.env['stock.quant']
        print("\n\n\n\nstock_quant_obj",stock_quant_obj)
        source_loc_stock = 0.00
        for each in self:
            for line in each.transfer_lines:
                source_loc_stock = 0.00
                print("\n\n\n line.location_id",line.location_id.name)
                source_quant_search = stock_quant_obj.search_read([('location_id', '=', line.location_id.id), ('product_id', '=' , line.product_id.id)],['inventory_quantity_auto_apply'])
                print("\n\n\n\nsource_quant_search",source_quant_search)
                for source_quant in source_quant_search:
                    source_loc_stock += source_quant['inventory_quantity_auto_apply']
                line.source_loc_stock = source_loc_stock
                print("\n\n\n\n line.source_loc_stock",line.source_loc_stock)
        return True
        
    
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_("You can delete a form which is only in draft state"))
        return super(InternalLocationTransfer, self).unlink()

class InternalTransferLines(models.Model):
    _name = 'internal.transfer.lines'
    _description = 'Internal Transfer Lines'
    
    transfer_id = fields.Many2one('internal.location.transfer', string='Internal Location Transfer', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True, copy=False)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True, copy=False)
    quantity = fields.Float(string='Quantity', digits=('Product Unit of Measure'), required=True, copy=False)
    source_loc_stock = fields.Float(string='Source Location Stock', digits=('Product Unit of Measure'), readonly=True, copy=False)
    location_id = fields.Many2one('stock.location', string='Source Location', related='transfer_id.location_id', copy=False)
    location_dest_id = fields.Many2one('stock.location', string='Destination Location', related='transfer_id.location_dest_id', copy=False)
    company_id = fields.Many2one('res.company', string='Company', related='transfer_id.company_id', store=True, readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', related='transfer_id.warehouse_id', store=True, readonly=True)
    
    state = fields.Selection(string='Status', readonly=True, store=True, related='transfer_id.state')
    
    # state = fields.Selection([
    #     ('draft', 'Draft'),
    #     ('waiting', 'Waiting For Approval'),
    #     ('done', 'Transfered'),
    #     ('cancel', 'Cancel'),
    #     ], string='Status', readonly=True, store=True, related='transfer_id.state')
    
    
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_("You can delete an item which is only in draft state"))
        return super(InternalTransferLines, self).unlink()
        
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
                    'title': _("Warning"),
                    'message': _("Unit of Measure cannot be changed.")}
        return {'warning': warning}
        
    @api.onchange('quantity')
    def _onchange_quantity(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            if self.quantity and (not self.uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.quantity, 1)
                if decimal:
                    self.quantity = 0.00
                    warning = {
                        'title': _("Warning"),
                        'message': _("You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value") % (self.uom_id.name)}
                    return {'warning': warning}
        
