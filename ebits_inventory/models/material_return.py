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

class MaterialReturn(models.Model):
    _name = 'material.return'
    _inherit = ['mail.thread']
    _description = 'Material Return'
    _order = 'id desc'


    @api.model
    def _get_department_id(self):
        if self.env.user.employee_ids:
            return self.env.user.employee_ids[0].department_id and self.env.user.employee_ids[0].department_id.id or False
        else:
            return False
            
    # @api.one
    # @api.depends('return_lines.uom_id', 'return_lines.returned_qty')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.return_lines:
            if line.uom_id.id in qty_dict:
                qty_dict[line.uom_id.id]['product_uom_qty'] += line.returned_qty
            else:
                qty_dict[line.uom_id.id] = {
                    'product_uom_qty': line.returned_qty,
                    'product_uom': line.uom_id and line.uom_id.name or '' 
                    }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        self.total_quantity_based_uom = qty_string
    
    name = fields.Char(string='Return No', required=True , readonly=True, default=lambda self: _('Return #'), copy=False)
    date_return = fields.Date(string='Last Returned Date', readonly=True, copy=False)
    date_accepted = fields.Date(string='Date', readonly=True, default=fields.Date.context_today, copy=False)
    user_id = fields.Many2one('res.users', string='Return User', required=True, default=lambda self: self.env.user, copy=False, readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True, copy=False, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('material.return'), copy=False)
    accepted_by = fields.Many2one('res.users', string='Accepted By', copy=False)
    department_id = fields.Many2one('hr.department', string='Department', default=_get_department_id, copy=False)
    issue_id = fields.Many2one('material.issue', string='Origin', readonly=True, copy=False)
    closed = fields.Boolean(string='Force Closed', copy=False, default=False, readonly=True)
    history = fields.Text(string='History', readonly=True, copy=False, default=' ')
    return_lines = fields.One2many('material.return.line', 'return_id', string='Return' , copy=False)
    move_lines = fields.One2many('stock.move', 'material_return_id', string='Stock Move', tracking=True, copy=False)
    picking_type_id = fields.Many2one('stock.picking.type', 'Picking Type', required=True, readonly=True)
    remarks = fields.Text(string='Remarks', copy=False)
    return_material = fields.Boolean(string="Is returned Material?", default=False, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('inprogress', 'Return in Progress'),
        ('done', 'Done'),
        ], string='Status', readonly=True, copy=False, default='draft', index=True, tracking=True)
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Returned Qty')

    def print_material_return(self):
        return self.env.ref('ebits_inventory.action_material_return_report').report_action(self)

   # @api.multi
    def action_material_return_state_update(self):
        flag = []
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            for return_line in each.return_lines:
                if return_line.state != 'done':
                    flag.append('no')
            if 'no' in flag:
                each.write({'state': 'inprogress'})
                each.history += '\nPartial return has been done by ' + str(self.env.user.name) + ' on ' + str(date)
            else:
                each.write({'state': 'done'})
                each.history += '\nFinal return has been done by ' + str(self.env.user.name) + ' on ' + str(date)
        return True
        
   # @api.multi
    def action_confirm(self):
        product = {}
        for each in self:
            if not each.return_lines:
                raise UserError(_('Product lines should not be empty!.\nKindly select product and proceed forward!!!'))
            for ret_line in each.return_lines:
                if ret_line.qty > ret_line.current_loc_stock:
                    raise UserError(_('Quantity of the product %s is greater than the source location stock.\nPlease click the check stock button and try again') % (ret_line.product_id.name_get()[0][1]))
                if ret_line.product_id in product:
                    product[ret_line.product_id] += 1
                else:
                    product[ret_line.product_id] = 1
            for each_p in product:
                if product[each_p] > 1:
                    raise UserError(_('Duplication of product %s will not allow you to proceed forward') % (each_p.name_get()[0][1]))
            for line in each.return_lines:
                if not line.qty > 0.00:
                    raise UserError(_('Zero quantity.\ncan not confirm due to zero quantity entered in %s Product qty') %(line.product_id.name))
                line.state = 'inprogress'
            each.state = 'inprogress'
        return True
        
    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        warning = {}
        if self.warehouse_id:
            if self.warehouse_id.material_return_picking_type_id:
                self.picking_type_id = self.warehouse_id.material_return_picking_type_id and self.warehouse_id.material_return_picking_type_id.id or False
            else:
                self.picking_type_id = False
                warning = {
                    'title': _('Warning'),
                    'message': _('The picking type of material return is not configured in  warehouse')} 
        else:
            self.picking_type_id = False
        return {'warning': warning}
        
   # @api.multi
    def action_check_stock(self):
        stock_quant_obj = self.env['stock.quant']
        qty_available = 0.00
        for each in self:
            for line in each.return_lines:
                qty_available = 0.00
                quant_search = stock_quant_obj.search_read([('location_id', '=', line.location_id.id), ('product_id', '=' ,line.product_id.id)],['inventory_quantity_auto_apply'])
                for each_quant in quant_search:
                    qty_available += each_quant['inventory_quantity_auto_apply']
                line.current_loc_stock = qty_available
        return True
        
   # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete a form which is only in draft state'))
        return super(MaterialReturn, self).unlink()

   # @api.multi
    def action_return(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        picking_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        picking_id = False
        for each in self:
            for line in each.return_lines:
                if line.return_qty > line.pending_qty:
                    raise UserError(_('Return incomplete.The return quantity for the product %s is greater than the pending return quantity.Please enter a value which is not greater than the pending return quantity')%(line.product_id.name_get()[0][1]))
                if line.return_qty > 0.00:
                    if each.name == 'Return #':
                        if each.warehouse_id.material_return_sequence_id:
                            each.name = each.warehouse_id.material_return_sequence_id.next_by_id()
                        else:
                            raise UserError(_('Material Return sequence is not defined in warehouse (%s).Please contact your administrator') % (each.warehouse_id.name))
                    line.returned_qty += line.return_qty
                    each.date_return = fields.Date.context_today(self)
                    line.state = 'done' if line.pending_qty == 0.00 else 'inprogress'
                    each.accepted_by = self.env.user.id
                    if not picking_id:
                        picking_id = picking_obj.create({
                            'location_dest_id':  line.location_dest_id and line.location_dest_id.id or False,
                            'location_id': line.location_id and line.location_id.id or False,
                            'origin': each.name and each.name or '',
                            'picking_type_id': each.return_material and each.issue_id.picking_type_id.id or each.picking_type_id.id
                        })
                    move_id = move_obj.create({
                        'name': line.product_id and line.product_id.name_get()[0][1] + ' / ' + each.name or "",
                        'company_id': line.company_id and line.company_id.id or False,
                        'product_id': line.product_id and line.product_id.id or False,
                        'product_uom': line.uom_id and line.uom_id.id or False,
                        'product_uom_qty': line.return_qty and line.return_qty or 0.00,
                        'location_id': line.location_id and line.location_id.id or False,
                        'location_dest_id': line.location_dest_id and line.location_dest_id.id or False,
                        'origin': each.name,
                        'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                        'picking_id': picking_id.id,
                        'material_return_id': each.id,
                    })
                    line.return_qty = 0.00
            if picking_id:
                picking_id.action_confirm()
                picking_id.action_assign()
                # picking_id.force_assign()
                for pack_line in picking_id.move_ids_without_package:
                    pack_line.write({'product_packaging_quantity': pack_line.product_qty})
                # picking_id.do_transfer()
                each.action_material_return_state_update()
                picking_id.button_validate()
        return True

class MaterialReturnline(models.Model):
    _name = 'material.return.line'
    _inherit = ['mail.thread']
    _description = 'Material Return Line'
    _rec_name = "product_id"

    @api.depends('qty', 'returned_qty')
    def get_pending_qty(self):
        for line in self:
            line.pending_qty = line.qty - line.returned_qty
    
    return_id = fields.Many2one('material.return', string='Return No', copy=False, ondelete='cascade')
    product_id = fields.Many2one('product.product' , string='Product', required=True, copy=False)
    machine_product_id = fields.Many2one('mrp.workcenter' , string='Machine', copy=False, readonly=True)
    uom_id = fields.Many2one('uom.uom' , string='Unit of Measure', required=True, copy=False)
    qty = fields.Float(string='Quantity', digits=('Product Unit of Measure'), required=True, copy=False)
    pending_qty = fields.Float(compute='get_pending_qty', digits=('Product Unit of Measure'), readonly=True, string='Pending Return Quantity', store=True)
    return_qty = fields.Float(string='Return Quantity', digits=('Product Unit of Measure'),  copy=False)
    returned_qty = fields.Float(string='Returned Quantity', digits=('Product Unit of Measure'), readonly=True, copy=False)
    location_id = fields.Many2one('stock.location', string='Source Location', copy=False, required=True)
    location_dest_id = fields.Many2one('stock.location', string='Destination Location', required=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('inprogress', 'Return in Progress'),
        ('done', 'Done'),
        ], string='Status', readonly=True, copy=False, default='draft', index=True, tracking=True)
    remarks = fields.Text(string='Remarks', copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', store=True, related='return_id.warehouse_id', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', store=True, related='return_id.company_id', readonly=True)
    return_material = fields.Boolean(string="Is returned Material?", default=False, readonly=True)
    current_loc_stock = fields.Float(string='Source Location Stock', digits=('Product Unit of Measure'), readonly=True, copy=False)
    closed = fields.Boolean(string='Force Closed', copy=False, default=False, readonly=True)
    
   # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete an item which is only in draft state'))
        return super(MaterialReturnline, self).unlink()
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.return_id.state != 'draft':
            raise UserError(_('You can change or select the product only in draft state.'))
        if self.product_id:
            self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id  or False
            self.location_dest_id = self.return_id.picking_type_id.default_location_dest_id and self.return_id.picking_type_id.default_location_dest_id.id or False
            self.location_id = self.return_id.picking_type_id.default_location_src_id and self.return_id.picking_type_id.default_location_src_id.id or False
        else:
            self.uom_id = False
            self.location_id = False
            self.location_dest_id = False
            
    @api.onchange('location_id')
    def onchange_location_id(self):
        warning = {}
        if self.location_id and self.product_id:
            if self.location_id.id != self.return_id.picking_type_id.default_location_src_id.id:
                self.location_id = self.return_id.picking_type_id.default_location_src_id and self.return_id.picking_type_id.default_location_src_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Source location cannot be changed.')}
        return {'warning': warning}
        
    @api.onchange('location_dest_id')
    def onchange_location_dest_id(self):
        warning = {}
        if self.location_dest_id and self.product_id:
            if self.location_dest_id.id != self.return_id.picking_type_id.default_location_dest_id.id:
                self.location_dest_id = self.return_id.picking_type_id.default_location_dest_id and self.return_id.picking_type_id.default_location_dest_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Destination location cannot be changed.')}
        return {'warning': warning}
            
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
        
    @api.onchange('return_qty')
    def _onchange_return_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            if self.return_qty and (not self.uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.return_qty, 1)
                if decimal:
                    self.return_qty = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the return quantity should not contains decimal value') % (self.uom_id.name)}
                    return {'warning': warning}
        
   # @api.multi
    def action_call_material_return_line_wizard(self):
        for return_line in self:
            view = self.env.ref('ebits_inventory.material_return_line_wizard_form')
            wiz = self.env['material.return.line.wizard'].create({
                'return_line_id': return_line.id, 
                'product_id': return_line.product_id.id,
                'pending_qty': return_line.pending_qty,
                'uom_id': return_line.uom_id.id})
            return {
                'name': _('Enter Return Qty'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'material.return.line.wizard',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                #'context': self.env.context,
            }

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    material_return_id = fields.Many2one('material.return', string='Material Return', readonly=True, copy=False)
