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
import pytz

class MaterialRequest(models.Model):
    _name = 'material.request'
    _description = 'Material Request'
    _order = 'id desc'
    
    @api.model
    def _get_manager_id(self):
        if self.env.user.employee_ids:
            if self.env.user.employee_ids[0].parent_id:
                return self.env.user.employee_ids[0].parent_id.user_id and self.env.user.employee_ids[0].parent_id.user_id.id or False
            else:
                return False
        else:
            return False
            
    # @api.one
    # @api.depends('request_lines.uom_id', 'request_lines.required_qty')
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
    
    name = fields.Char(string='Request No', required=True, readonly=True, default=lambda self: _('Request #'), copy=False)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('material.request'), copy=False)
    date_requested = fields.Date(string='Requested Date', required=True, readonly=True, default=fields.Date.context_today, copy=False)
    date_required = fields.Date(string='Required Date', required=True, copy=False)
    date_approved = fields.Datetime(string='Approved Date', readonly=True, copy=False)
    user_id = fields.Many2one('res.users', string='Creator', readonly=True, required=True, default=lambda self: self.env.user, copy=False)
    department_id = fields.Many2one('hr.department', string='Required To Department', copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', required=True, copy=False)
    material_requester = fields.Char(string='Material Requester', copy=False)
    request_lines = fields.One2many('material.request.lines', 'request_id', string='Material Request Line', copy=False)
    returnable = fields.Selection([('yes','Yes'),('no','No')], string='Returnable', copy=False)
    approver_user_id = fields.Many2one('res.users', string='Approved by', readonly=True, default=_get_manager_id, copy=False)
    issue_id = fields.Many2one('material.issue', string='Issue No', copy=False, readonly=True)
    history = fields.Text(string='History', copy=False, default=' ')
    remarks = fields.Text(string='Remarks', copy=False)
    picking_type_id = fields.Many2one('stock.picking.type', 'Picking Type',
        help="This will determine picking type of incoming shipment")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting For Approval'),
        ('done', 'Done'),
        ('cancelled', 'Rejected'),
        ], string='Status', readonly=True, copy=False, default='draft')
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Required Qty')
        
    @api.onchange('picking_type_id')
    def onchange_picking_type_id(self):
        warning = {}
        if self.picking_type_id:
            if self.request_lines:
                for eachline in self.request_lines:
                    eachline.location_dest_id = self.picking_type_id.default_location_dest_id and self.picking_type_id.default_location_dest_id.id or False
                    eachline.location_id = self.picking_type_id.default_location_src_id and self.picking_type_id.default_location_src_id.id or False 
                warning = {
                    'title': _('Warning'),
                    'message': _('Since you have changed the warehouse and picking type, the destination and the source location in the line has been changed in accordance. Kindly verify')} 
        
        return {'warning': warning}

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        warning = {}
        if self.warehouse_id:
            if self.warehouse_id.cloth_order_picking_type_id:
                self.picking_type_id = self.warehouse_id.material_request_picking_type_id and self.warehouse_id.material_request_picking_type_id.id or False

            else:
                self.picking_type_id = False
                warning = {
                    'title': _('Warning'),
                    'message': _('The picking type of material request is not configured in  warehouse')} 
        else:
            self.picking_type_id = False
        return {'warning': warning}
        
   # @api.multi
    def action_send_approval(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        product = {}
        for each in self:
            if not each.request_lines:
                raise UserError(_('Material request lines should not be empty!.\nKindly select product and proceed forward'))
            for req_line in each.request_lines:
                if req_line.product_id in product:
                    product[req_line.product_id] += 1
                else:
                    product[req_line.product_id] = 1
            for each_p in product:
                if product[each_p] > 1:
                    raise UserError(_('Duplication of product %s will not allow you to proceed forward!!!') % (each_p.name_get()[0][1]))
            each.action_check_stock()
            for line in each.request_lines:
                if (line.required_qty > line.source_loc_stock) and line.product_id.type == 'product':
                    raise UserError(_('Required quantity (%s) for the product (%s) is lesser than source location stock (%s).\nKindly check stock or reduce the required qty') % (line.required_qty, line.product_id.name_get()[0][1], line.source_loc_stock))
                if line.required_qty > 0.00:
                    line.state = 'waiting'
                    line.qty = line.required_qty
                    if each.name == 'Request #':
                        if each.warehouse_id.material_request_sequence_id:
                            name = each.warehouse_id.material_request_sequence_id.next_by_id()
                            each.name = name
                        else:
                            raise UserError(_('Material Request sequence is not defined in warehouse (%s).Please contact your administrator') % (each.warehouse_id.name))
                else:
                    raise UserError(_('Zero quantity.\nRequest not sent due to zero quantity entered in required qty'))
            each.state = 'waiting'
            each.history += '\nRequest has been sent for approval by ' + str(self.env.user.name) + ' on ' + str(date)
        return True

   # @api.multi
    def action_approve(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        issue_obj = self.env['material.issue']
        issue_line_obj = self.env['material.issue.line']
        for each in self:
            if not each.request_lines:
                raise UserError(_('No products selected.\nSystem will not proceed forward for nill products'))
            for line in each.request_lines:
                if line.qty <= 0.00:
                    raise UserError(_('Zero quantity.\nNot approved due to zero quantity defined in approved qty'))
            issue_id = issue_obj.create({
                'user_id': each.user_id and each.user_id.id or False,
                'material_requester': each.material_requester and each.material_requester or '',
                'department_id': each.department_id and each.department_id.id or False,
                'request_id': each.id,
                'date': each.date_requested and each.date_requested or False,
                'date_required': each.date_required and each.date_required or False,
                'date_approved': fields.Datetime.now(),
                'approver_user_id':self.env.user.id,
                'returnable': each.returnable and each.returnable or '',
                'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                'picking_type_id': each.picking_type_id and each.picking_type_id.id or False,
                'remarks': each.remarks and each.remarks or "",
                'department_id': each.department_id and each.department_id.id or False
            })
            for line in each.request_lines:
                issue_line_obj.create({
                    'issue_id': issue_id.id,
                    'product_id': line.product_id and line.product_id.id or False,
                    'machine_product_id': line.machine_product_id and line.machine_product_id.id or False,
                    'uom_id': line.uom_id and line.uom_id.id or False,
                    'qty': line.qty and line.qty or 0.00,
                    'date_expected': line.date_expected and line.date_expected or False,
                    'location_id': each.picking_type_id.default_location_src_id and each.picking_type_id.default_location_src_id.id or False,
                    'location_dest_id': line.location_dest_id and line.location_dest_id.id or False,
                    'remarks': line.remarks and line.remarks or ""
                })
                line.state = 'done'
            each.state = 'done'
            each.date_approved = fields.Datetime.now()
            each.approver_user_id = self.env.user.id
            each.issue_id = issue_id.id
            each.history += '\nRequest has been approved by ' + str(self.env.user.name) + ' on ' + str(date)
            each.action_check_stock()
        return True
        
   # @api.multi
    def action_reedit(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            for line in each.request_lines:
                line.state = 'draft'
            each.state = 'draft'
            each.history += '\nRequest has been send back to re-edit by ' + str(self.env.user.name) + ' on ' + str(date)
        return True

   # @api.multi
    def action_check_stock(self):
        stock_quant_obj = self.env['stock.quant']
        qty_available = on_hand_qty = source_loc_stock = 0.00
        for each in self:
            for line in each.request_lines:
                qty_available = on_hand_qty = source_loc_stock = 0.00
                on_hand_qty = line.product_id.qty_available
                quant_search = stock_quant_obj.search_read([('location_id', '=', line.location_dest_id.id), ('product_id', '=' ,line.product_id.id)],['inventory_quantity_auto_apply'])
                source_quant_search = stock_quant_obj.search_read([('location_id', '=', line.location_id.id), ('product_id', '=' ,line.product_id.id)],['inventory_quantity_auto_apply'])

                for source_quant in source_quant_search:
                    source_loc_stock += source_quant['inventory_quantity_auto_apply']

                for each_quant in quant_search:
                    qty_available += each_quant['inventory_quantity_auto_apply']
                line.write({'stock_available': on_hand_qty, 'source_loc_stock': source_loc_stock, 'dest_loc_stock': qty_available})
        return True
        
   # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete a form which is only in draft state'))
        return super(MaterialRequest, self).unlink()

class MaterialRequestLines(models.Model):
    _name = 'material.request.lines'
    _description = 'Material Request Lines'
    _rec_name = 'product_id'
    
    request_id = fields.Many2one('material.request', string='Material Request', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True, copy=False)
    machine_product_id = fields.Many2one('mrp.workcenter', string='Machine', copy=False)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True, copy=False)
    required_qty = fields.Float(string='Required Quantity', digits=('Product Unit of Measure'), required=True, copy=False)
    stock_available = fields.Float(string='Total Stock Available', digits=('Product Unit of Measure'), readonly=True, copy=False)
    source_loc_stock = fields.Float(string='Source Location Stock', digits=('Product Unit of Measure'), readonly=True, copy=False)
    dest_loc_stock = fields.Float(string='Destination Location Stock', digits=('Product Unit of Measure'), readonly=True, copy=False)
    qty = fields.Float(string='Approved Quantity', digits=('Product Unit of Measure'), readonly=True, copy=False)
    date_expected = fields.Date(string='Required Date', required=True, copy=False)
    returnable = fields.Selection([('yes','Yes'),('no','No')], string='Returnable', copy=False, default='yes')
    location_id = fields.Many2one('stock.location', string='Source Location', required=True, copy=False)
    location_dest_id = fields.Many2one('stock.location', string='Destination Location', required=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting For Approval'),
        ('done', 'Done'),
        ('cancelled', 'Rejected'),
        ], string='Status', readonly=True, copy=False, default='draft')
    remarks = fields.Text(string='Approver Remarks', copy=False)
    company_id = fields.Many2one('res.company', string='Company', related='request_id.company_id', store=True, readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/ Branch', related='request_id.warehouse_id', store=True, readonly=True)
    
   # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete an item which is only in draft state'))
        return super(MaterialRequestLines, self).unlink()
        
    @api.onchange('location_dest_id')
    def _onchange_location_dest_id(self):
        warning = {}
        if self.location_dest_id:
            if self.location_dest_id.id != self.request_id.picking_type_id.default_location_dest_id.id:
                self.location_dest_id = self.request_id.picking_type_id.default_location_dest_id and self.request_id.picking_type_id.default_location_dest_id.id or False
                warning = {
                        'title': _('Warning'),
                        'message': _('Location cannot be changed.This location is the default destination location of the picking type that you have selected')}
        return {'warning': warning}
    
    @api.onchange('location_id')
    def _onchange_location_id(self):
        warning = {}
        if self.location_id:
            if self.location_id.id != self.request_id.picking_type_id.default_location_src_id.id:
                self.location_id = self.request_id.picking_type_id.default_location_src_id and self.request_id.picking_type_id.default_location_src_id.id or False
                warning = {
                        'title': _('Warning'),
                        'message': _('Location cannot be changed.This location is the default source location of the picking type that you have selected')}
        return {'warning': warning}
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.request_id.state != 'draft':
            raise UserError(_('You can change or select the product only in draft state.'))
        if not self.request_id.date_required:
            raise UserError(_('Kindly enter the required date.'))
        if not self.request_id.picking_type_id:
            raise UserError(_('Kindly enter picking type.'))
        if self.product_id:
            self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id  or False
            self.location_dest_id = self.request_id.picking_type_id.default_location_dest_id and self.request_id.picking_type_id.default_location_dest_id.id or False
            self.location_id = self.request_id.picking_type_id.default_location_src_id and self.request_id.picking_type_id.default_location_src_id.id or False
        else:
            self.uom_id = False
            self.location_dest_id = False
            self.location_id = False
            
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
                
