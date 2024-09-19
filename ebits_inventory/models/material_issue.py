# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil import relativedelta
import time

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMA 
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
import pytz

class MaterialIssue(models.Model):
    _name = 'material.issue'
    _inherit = ['mail.thread']
    _description = 'Material Issue'
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
    @api.depends('issue_lines.uom_id', 'issue_lines.issued_qty')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.issue_lines:
            if line.uom_id.id in qty_dict:
                qty_dict[line.uom_id.id]['product_uom_qty'] += line.issued_qty
            else:
                qty_dict[line.uom_id.id] = {
                    'product_uom_qty': line.issued_qty,
                    'product_uom': line.uom_id and line.uom_id.name or '' 
                    }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        self.total_quantity_based_uom = qty_string
    
    name = fields.Char(string='Issue No', required=True, readonly=True, default=lambda self: _('Issue #'), copy=False)
    date_required = fields.Date(string='Required Date', required=True, copy=False, readonly=True)
    date_last_issue = fields.Date(string='Last Issued Date', readonly=True, copy=False)
    date = fields.Date(string='Requested Date', readonly=True, required=True, default=fields.Date.context_today, copy=False)
    date_approved = fields.Datetime(string='Approved Date', readonly=True, copy=False)
    user_id = fields.Many2one('res.users', string='Creator', readonly=True, required=True, default=lambda self: self.env.user, copy=False)
    issuer_user_id = fields.Many2one('res.users', string='Issuer', readonly=True, copy=False)
    approver_user_id = fields.Many2one('res.users', string='Approved by', readonly=True, required=True, default=_get_manager_id, copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True, copy=False, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('material.issue'), copy=False)
    material_requester = fields.Char(string='Material Requester', copy=False, readonly=True)
    department_id = fields.Many2one('hr.department', string='Required To Department', readonly=True, copy=False)
    request_id = fields.Many2one('material.request', string='Request No', readonly=True, copy=False)
    returnable = fields.Selection([('yes','Yes'),('no','No')], string='Returnable', readonly=True, copy=False, default="yes")
    issue_lines = fields.One2many('material.issue.line', 'issue_id', string='Issue', readonly=True, required=True, copy=False)
    move_lines = fields.One2many('stock.move', 'material_issue_id', string='Stock Move', tracking=True, copy=False)
    remarks = fields.Text(string='Remarks', copy=False)
    closed = fields.Boolean(string='Force Closed', copy=False, default=False, readonly=True)
    history = fields.Text(string='History', copy=False, default=' ')
    picking_type_id = fields.Many2one('stock.picking.type', 'Picking Type', required=True, help="This will determine picking type of incoming shipment", readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('inprogress', 'Issue in Progress'),
        ('done', 'Done'),
        ], string='Status', readonly=True, copy=False, default='draft', index=True, tracking=True)
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Issued Quantity')
        
   # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete a form which is only in draft state'))
        return super(MaterialIssue, self).unlink()
    def print_material_issue(self):
        return self.env.ref('ebits_inventory.action_material_issue_report').report_action(self)
        
   # @api.multi
    def action_check_stock(self):
        stock_quant_obj = self.env['stock.quant']
        qty_available = on_hand_qty = 0.00
        for each in self:
            for line in each.issue_lines:
                qty_available = on_hand_qty = 0.00
                on_hand_qty = line.product_id.qty_available
                quant_search = stock_quant_obj.search_read([('location_id', '=', line.location_id.id), ('product_id', '=' ,line.product_id.id)],['inventory_quantity_auto_apply'])
                for each_quant in quant_search:
                    qty_available += each_quant['inventory_quantity_auto_apply']
                line.write({'stock_available': on_hand_qty, 'current_loc_stock': qty_available})
        return True
    
   # @api.multi
    def action_material_issue_state_update(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        flag = []
        for each in self:
            for issue_line in each.issue_lines:
                if issue_line.state != 'done':
                    flag.append('no')
            if 'no' in flag:
                each.state =  'inprogress'
                each.history += '\nPartial issue has been done by ' + str(self.env.user.name) + ' on ' + str(date)
            else:
                each.state = 'done'
                each.history += '\nFinal issue has been done by ' + str(self.env.user.name) + ' on ' + str(date)
        return True
    
   # @api.multi
    def action_issue(self):
        return_obj = self.env['material.return']
        return_line_obj = self.env['material.return.line']
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        picking_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        picking_id = False
        return_id = False
        for each in self:
            for line in each.issue_lines:
                if line.issue_qty > line.pending_qty:
                    raise UserError(_('Issue incomplete.The issue quantity for the product %s is greater than the pending issue quantity to be received.Please enter a value which is not greater than the pending issue quantity')%(line.product_id.name_get()[0][1]))
                if line.issue_qty > line.current_loc_stock and line.product_id.type == 'product':
                    raise UserError(_('Issue incomplete.The issue quantity for the product %s is greater than the source location stock.Please click the check stock button and try issuing again')%(line.product_id.name_get()[0][1]))
                if line.issue_qty > 0.00:
                    if each.name == 'Issue #':
                        if each.warehouse_id.material_issue_sequence_id:
                            each.name = each.warehouse_id.material_issue_sequence_id.next_by_id()
                        else:
                            raise UserError(_('Material Issue sequence is not defined in warehouse (%s).Please contact your administrator') % (each.warehouse_id.name))
                    line.issued_qty += line.issue_qty
                    line.state = 'done' if line.pending_qty == 0.00 else 'partial'
                    each.issuer_user_id = self.env.user.id
                    each.date_last_issue = fields.Date.context_today(self)
                
                    if not picking_id:
                        picking_id = picking_obj.create({
                            'location_dest_id':  line.location_dest_id and line.location_dest_id.id or False,
                            'location_id': line.location_id and line.location_id.id or False,
                            'origin': each.name and each.name or '',
                            'picking_type_id': each.picking_type_id and each.picking_type_id.id or False
                        })
                        if each.returnable == 'yes':
                            return_id = return_obj.create({
                                'issue_id': each.id,
                                'date_accepted': fields.Date.context_today(self),
                                'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                                'picking_type_id': each.picking_type_id and each.picking_type_id.id or False,
                                'return_material': True
                            })
                    move_id = move_obj.create({
                        'name': line.product_id and line.product_id.display_name + ' / ' + each.name or "",
                        'company_id': line.company_id and line.company_id.id or False,
                        'product_id': line.product_id and line.product_id.id or False,
                        'product_uom': line.uom_id and line.uom_id.id or False,
                        'product_uom_qty': line.issue_qty and line.issue_qty or 0.00,
                        'location_id': line.location_id and line.location_id.id or False,
                        'location_dest_id': line.location_dest_id and line.location_dest_id.id or False,
                        'origin': each.name,
                        'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                        'picking_id': picking_id.id,
                        'material_issue_id': each.id,
                        'picking_type_id': each.picking_type_id and each.picking_type_id.id or False
                    })
                    if return_id:
                        return_line_obj.create({
                            'return_id': return_id.id,
                            'product_id': line.product_id.id,
                            'machine_product_id': line.machine_product_id.id or False,
                            'uom_id': line.uom_id.id,
                            'qty': line.issue_qty,
                            'location_id': line.location_dest_id and line.location_dest_id.id or False,
                            'location_dest_id': line.location_id and line.location_id.id or False,
                            'state': 'draft',
                            'return_material': True
                        })
                    line.issue_qty = 0.00
            if picking_id:
                picking_id.action_confirm()
                picking_id.action_assign()
                # picking_id.force_assign()
                for pack_line in picking_id.move_ids_without_package:
                    pack_line.write({'product_packaging_quantity': pack_line.product_qty})
                # picking_id.do_transfer()
                each.action_check_stock()
                each.action_material_issue_state_update()
                picking_id.button_validate()
        return True
        
class MaterialIssueline(models.Model):
    _name = 'material.issue.line'
    _inherit = ['mail.thread']
    _description = 'Material Issue Line'
    _rec_name = "product_id"

    @api.depends('qty', 'issued_qty')
    def get_pending_qty(self):
        for line in self:
            line.pending_qty = line.qty - line.issued_qty
    
    issue_id = fields.Many2one('material.issue', string='Issue', copy=False, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True, copy=False, readonly=True)
    machine_product_id = fields.Many2one('mrp.workcenter', string='Machine', copy=False, readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True, copy=False, readonly=True)
    qty = fields.Float(string='Approved Quantity', digits=('Product Unit of Measure'), required=True, copy=False, readonly=True)
    date_expected = fields.Date(string='Required Date', required=True, copy=False, readonly=True)
    stock_available = fields.Float(string='Total Stock Available', digits=('Product Unit of Measure'), readonly=True, copy=False)
    current_loc_stock = fields.Float(string='Source Location Stock', digits=('Product Unit of Measure'), readonly=True, copy=False)
    receiver_name = fields.Char(string='Receiver Name', copy=False)
    pending_qty = fields.Float(compute='get_pending_qty', digits=('Product Unit of Measure'), string='Pending Issue Quantity', readonly=True, store=True)
    issue_qty = fields.Float(string='Issue Quantity', digits=('Product Unit of Measure'),  copy=False, )
    issued_qty = fields.Float(string='Issued Quantity', digits=('Product Unit of Measure'), readonly=True, copy=False)
    location_id = fields.Many2one('stock.location', string='Source Location', copy=False, readonly=True)
    closed = fields.Boolean(string='Force Closed', copy=False, default=False, readonly=True)
    location_dest_id = fields.Many2one('stock.location', string='Destination Location', required=True, copy=False, readonly=True)
    returnable = fields.Selection([('yes','Yes'),('no','No')], string='Returnable', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('partial', 'Partially Issued'),
        ('done', 'Done'),
        ], string='Status', readonly=True, copy=False, default='draft', index=True, tracking=True)
    remarks = fields.Text(string='Remarks', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', 'Company', related="issue_id.company_id", store=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', related="issue_id.warehouse_id", store=True, copy=False)
    
   # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete an item which is only in draft state'))
        return super(MaterialIssueline, self).unlink()
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.issue_id.state != 'draft':
            raise UserError(_('You can change or select the product only in draft state.'))
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
        
    @api.onchange('issue_qty')
    def _onchange_issue_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            if self.issue_qty and (not self.uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.issue_qty, 1)
                if decimal:
                    self.issue_qty = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the issue quantity should not contains decimal value') % (self.uom_id.name)}
                    return {'warning': warning}
    
   # @api.multi
    def action_call_material_issue_line_wizard(self):
        for issue_line in self:
            view = self.env.ref('ebits_inventory.material_issue_line_wizard_form')
            wiz = self.env['material.issue.line.wizard'].create({
                'issue_line_id': issue_line.id, 
                'product_id': issue_line.product_id.id,
                'pending_qty': issue_line.pending_qty,
                'uom_id': issue_line.uom_id.id})
            return {
                'name': _('Enter Issue Qty'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'material.issue.line.wizard',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                #'context': self.env.context,
            }

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    material_issue_id = fields.Many2one('material.issue', string='Material Issue', readonly=True, copy=False)
