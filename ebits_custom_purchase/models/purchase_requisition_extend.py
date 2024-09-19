# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

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

class PurchaseCategory(models.Model):
    _name = "purchase.category"
    _description = "Purchase Category"
    
    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Sequence Code',size=5, required=True, help="This is used for purchase requisition and order sequence generation")
    type = fields.Selection([('normal', 'Normal'), 
        ('service', 'Service')], string='Type', required=True, default='normal')

class PurchaseRequisitionApprovalHierarchy(models.Model):
    _name = "purchase.requisition.approval.hierarchy"
    _description = "Purchase Requisition Approval Hierarchy"
    
    name = fields.Char(string="Name",size=64, required=True)
    date = fields.Datetime(string="Created Date", default=fields.Datetime.now, readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Production Unit / Division / Branch', required=True)
    category_ids = fields.Many2many('purchase.category', 'hierarchy_pr_category_rel', 'hierarchy_id', 'category_id', string='Category Type', required=True)
    hierarchy_type = fields.Selection([('one','One Level Approval'), ('two', 'Two Level Approval')], string="Hierarchy Type", required=True)
    one_level_user_ids = fields.Many2many('res.users', 'hierarchy_pr_one_res_users_rel', 'hierarchy_id', 'category_id' , string="1st Approver")
    two_level_user_ids = fields.Many2many('res.users', 'hierarchy_pr_two_res_users_rel', 'hierarchy_id', 'category_id' , string="2nd Approver")

class PurchaseRequisitionExtend(models.Model):
    _name = "purchase.requisition.extend"
    _description = "Purchase Requisition Extend"
    _order = "id desc"
    
    # @api.one
    @api.depends('purchase_line.uom_id', 'purchase_line.required_qty')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.purchase_line:
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
    
    name = fields.Char(string='Requisition No', readonly=True, copy=False, default=lambda self: _('New #'))
    category_id = fields.Many2one('purchase.category', string='Category Type', required=True,  copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True,  )
    date_requisition = fields.Date(string='Requisition Date', readonly=True, default=fields.Datetime.now)
    user_id = fields.Many2one('res.users',string='Requestor', default=lambda self: self.env.user, readonly=True)
    date_required = fields.Date(string='Required Date', required=True)
    history = fields.Text(string='History', readonly=True)
    remarks = fields.Text(string='Remarks', readonly=True)
    purchase_line = fields.One2many('po.requisition.item.lines', 'requisition_id', string='Purchase Item')
    state = fields.Selection([('draft', 'Draft'), 
        ('waiting', 'Waiting For Approval'), 
        ('waiting_2nd', 'Waiting For 2nd Approval'),
        ('approved', 'Approved'), 
        ('cancel', 'Cancel')], string='Status', readonly=True, default='draft')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,  default=lambda self: self.env.user.company_id.id)
    product_id = fields.Many2one('product.product', related='purchase_line.product_id', string='Product')
    one_approver_ids = fields.Many2many('res.users', 'pr_one_level_approver_rel', 'requisition_id', 'user_id', string='1st Approver', readonly=True, copy=False)
    two_approver_ids = fields.Many2many('res.users', 'pr_two_level_approver_rel', 'requisition_id', 'user_id', string='2nd Approver', readonly=True, copy=False)
    one_approved_id = fields.Many2one('res.users', string='1st Approved User', readonly=True, copy=False)
    two_approved_id = fields.Many2one('res.users', string='2nd Approved User', readonly=True, copy=False)
    one_approved_date = fields.Datetime(string='1st Approved Date', readonly=True, copy=False)
    two_approved_date = fields.Datetime(string='2nd Approved Date', readonly=True, copy=False)
    force_closed_reason = fields.Text('Force Close Reason', readonly=True)
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Required Qty')
    
    # @api.multi
    def action_send_for_approval(self):
        # employee_obj = self.env['hr.employee']
        hierarchy_obj = self.env['purchase.requisition.approval.hierarchy']
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        name = code = history = ""
        for each in self:
            if not each.purchase_line:
                raise UserError(_('You must entered a product line item to proceed forward'))
            for line in each.purchase_line:
                if line.required_qty <= 0.00:
                    raise UserError(_('The (%s) product - required quantity cannot be zero or less than zero') %(line.product_id.name_get()[0][1]))
                line.approved_qty = line.required_qty
            hierarchy_search = hierarchy_obj.search([('warehouse_id', '=', each.warehouse_id.id),('category_ids', '=', each.category_id.id)])
            if not hierarchy_search:
                raise UserError(_("Approval hierarchy not defined for selected warehouse [%s] and category [%s].") % (each.warehouse_id.name, each.category_id.name,))
            for hierarchy in hierarchy_search:
                each.write({'one_approver_ids': [(6, 0, hierarchy.one_level_user_ids.ids)]})
                if hierarchy.hierarchy_type == 'two':
                    each.write({'two_approver_ids': [(6, 0, hierarchy.two_level_user_ids.ids)]})
            if each.name == 'New #':
                if each.warehouse_id.po_requisition_sequence_id:
                    name = each.warehouse_id.po_requisition_sequence_id.next_by_id()
                    code = each.category_id.code
                    each.write({'name': code + "/" + name})
                    print("\n\\n\n...........each..........",each.name)
                else:
                    raise UserError(_('Purchase Requisition Sequence not defined in warehouse (%s)') % (each.warehouse_id.name))
            if each.history:
                history = each.history + "\n"
            each.write({
                'state': 'waiting',
                'history': history + 'This document is sent to approval by '+ self.env.user.name + ' on this date '+ date
                    })
        return True
        
    # @api.multi
    def action_approve(self):
        strf_date = time.strftime('%Y-%m-%d %H:%M:%S')
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        product_line = []
        approve_check = False
        for each in self:
            for line in each.purchase_line:
                if line.approved_qty:
                    product_line.append('True')
                else:
                    product_line.append('False')
                if line.required_qty < line.approved_qty:
                    raise UserError(_('The (%s) product - approved quantity is greater than the required quantity') % (line.product_id.name_get()[0][1]))
            if not 'True' in product_line:
                raise UserError(_('You have to fill approve qty for atleast one product line to proceed forward'))
            if each.history:
                history = each.history + "\n"
            for one in each.one_approver_ids:
                if one.id == self.env.user.id:
                    approve_check = True
                    each.write({'one_approved_id': self.env.user.id, 'one_approved_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                    if each.two_approver_ids:
                        each.write({'state': 'waiting_2nd', 'history': history + 'This document is approved and sent for 2nd Level Approval by '+ self.env.user.name + ' on this date '+ date})
                    else:
                        each.write({'state': 'approved','history': history + 'This document is approved by '+ self.env.user.name + ' on this date '+ date})
            if not approve_check:
                raise UserError(_("You cannot approve this requisition."))
        return True
    
    # @api.multi
    def action_two_approve(self):
        approve_check = False
        history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            if each.history:
                history = each.history + "\n"
            for two in each.two_approver_ids:
                if two.id == self.env.user.id:
                    approve_check = True
                    each.write({'state': 'approved', 'two_approved_id': self.env.user.id, 'two_approved_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT), 'history': history + 'This document is approved by '+ self.env.user.name + ' on this date '+ date})
            if not approve_check:
                raise UserError(_("You cannot approve this requisition."))
        return True
                
                
    # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete an item which is only in the draft state.'))
        return super(PurchaseRequisitionExtend, self).unlink()


    # @api.multi
    def action_check_quant(self):
        quant_obj = self.env['stock.quant'] 
        picking_obj = self.env['stock.picking']
        purchase_obj = self.env['purchase.order']
        stock_transfer_receipt_obj = self.env['internal.stock.transfer.receipt.line']
        quantity = qty_stock_categ =  0.00
        for each in self:
            if not each.warehouse_id.quality_location_id:
                raise UserError(_('Quality location not mapped in the warehouse (%s) !. Kindly contact manager or administrator!!') % (each.warehouse_id.name))
            for line in each.purchase_line:
                quantity, transit_loc_qty, qty_stock_categ, picking_qty, purchase_qty, quality_qty = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
                quant_search = quant_obj.search_read([('product_id', '=', line.product_id.id), ('location_id', '=', line.location_id.id)],['inventory_quantity_auto_apply'])
                quant_search_in_categ = quant_obj.search_read([('product_id.categ_id', '=', line.product_id.categ_id.id), ('location_id', '=', line.location_id.id)],['inventory_quantity_auto_apply'])
                quality_quant_search = quant_obj.search_read([('product_id', '=', line.product_id.id), ('location_id', '=', each.warehouse_id.quality_location_id.id)],['inventory_quantity_auto_apply'])
                picking_search = picking_obj.search([('picking_type_id', '=', each.sudo().warehouse_id.in_type_id.id), ('state', 'not in', ['approved','cancel'])])
                purchase_search = purchase_obj.search([('warehouse_id', '=', each.warehouse_id.id), ('state', 'not in', ['purchase', 'done', 'cancel'])])
                stock_transfer_receipt_search = stock_transfer_receipt_obj.sudo().search_read([('product_id', '=', line.product_id.id), ('state', 'in', ['draft', 'partial'])], ['pending_receipt_qty'])

                for each_quant in quant_search:
                    quantity += each_quant['inventory_quantity_auto_apply']
                for each_quant in quant_search_in_categ:
                    qty_stock_categ += each_quant['inventory_quantity_auto_apply']
                for transit in stock_transfer_receipt_search:
                    transit_loc_qty += transit['pending_receipt_qty']  
                for quality_quant in quality_quant_search:
                    quality_qty += quality_quant['inventory_quantity_auto_apply']
                for each_picking in picking_search:
                    for line_picking in each_picking.move_lines:
                        if line_picking.product_id == line.product_id:
                            picking_qty += line_picking.product_uom_qty
                for each_purchase in purchase_search:
                    for line_purchase in each_purchase.order_line:
                        if line_purchase.product_id == line.product_id:
                            purchase_qty += line_purchase.product_qty
                print("\n\n//////////////////-------",quantity)
                print("\n\n//////////////////-------",qty_stock_categ)
                print("\n\n//////////////////-------",quality_qty)
                print("\n\n//////////////////------picking_qty-",picking_qty)
                line.write({
                    'transit_location_qty': transit_loc_qty, 
                    'avail_stock_in_categ': qty_stock_categ, 
                    'available_stock': quantity,
                    'grn_qty': picking_qty,
                    'po_qty': purchase_qty,
                    'quality_stock': quality_qty
                    })
        return True
            
    # @api.multi
    def print_purchase_requisition(self):
        return self.env['report'].get_action(self, 'purchase.requisition.rml.report')
    
class PoRequisitionItemLines(models.Model):
    _name = "po.requisition.item.lines"
    _description = "Purchase Requisition Item"
    _rec_name = "product_id"
    
    @api.depends('po_lines', 'approved_qty', 'required_qty', 'state', 'po_lines.order_line_id', 'po_lines.order_line_id.state')
    def _po_line_compute(self):
        pr_qty = 0.00
        pr_qty
        po_obj = self.env['purchase.order']
        for line in self:
            pr_qty = 0.00
            for po_line in line.po_lines:
                if po_line.order_line_id.order_id:
                    if po_line.order_line_id.order_id.state != 'cancel':
                        #if po_line.order_line_id.order_id.state in ['purchase', 'done']:
                        po_obj |= po_line.order_line_id.order_id
                        pr_qty += po_line.pr_qty
            line.ordered_qty = pr_qty
            line.purchase_ids = po_obj
            line.to_ordered_qty = line.approved_qty - line.ordered_qty
    
    po_lines = fields.One2many('po.pr.link.line', 'pr_line_id', string="Purchase PR Lines")
    purchase_ids = fields.Many2many('purchase.order', 'pr_po_link_rel', 'pr_id', 'po_id', string="Purchase Order", readonly=True, compute="_po_line_compute", store=True)
    requisition_id = fields.Many2one('purchase.requisition.extend', string='Purchase Requisition')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    uom_id = fields.Many2one('uom.uom', string='UOM')
    required_qty = fields.Float(string='Required Qty', digits='Product Unit of Measure',  required=True,)
    location_id = fields.Many2one('stock.location', string='Required Location')
    available_stock = fields.Float(string='Stock Avail-Req Location', digits='Product Unit of Measure', readonly=True)
    avail_stock_in_categ = fields.Float(string='Stock Avail-Related Category', digits='Product Unit of Measure', readonly=True)
    transit_location_qty = fields.Float(string='In-Transit Qty', digits='Product Unit of Measure', readonly=True)
    quality_stock = fields.Float(string='Stock Avail-Quality Location', digits='Product Unit of Measure', readonly=True)
    grn_qty = fields.Float(string='Pending GRN Qty', digits='Product Unit of Measure', readonly=True)
    po_qty = fields.Float(string='PO Qty Pending for Approval', digits='Product Unit of Measure', readonly=True)
    approved_qty = fields.Float(string='PR Approved Quantity ** (A) **', digits='Product Unit of Measure', readonly=True, )
    ordered_qty = fields.Float(string='PR Qty in PO(Draft/Pending Approval/Approved) ** (B) **', digits='Product Unit of Measure', readonly=True, compute="_po_line_compute", store=True)
    to_ordered_qty = fields.Float(string='Pending Qty to be Ordered  (A-B) ', digits='Product Unit of Measure', readonly=True, compute="_po_line_compute", store=True)
    remarks = fields.Char(string='Remarks',readonly=True, )
    state = fields.Selection(related='requisition_id.state', string='PR Status', readonly=True, store=True)
    company_id = fields.Many2one('res.company', related='requisition_id.company_id', string='Company', store=True, readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', related='requisition_id.warehouse_id', string='Warehouse/Branch', readonly=True, store=True, copy=False)
    
    category_id = fields.Many2one('purchase.category', related='requisition_id.category_id', string='Category Type', readonly=True, store=True, copy=False)
    date_requisition = fields.Date(string='Requisition Date', related='requisition_id.date_requisition', readonly=True, store=True, copy=False)
    user_id = fields.Many2one('res.users', related='requisition_id.user_id', string='Requestor', readonly=True, store=True, copy=False)
    date_required = fields.Date(string='Required Date', copy=False,store=True)
    force_close = fields.Boolean('Force Closed', readonly=True, default=False, copy=False)
        
            
    @api.onchange('product_id')
    def onchange_product_id(self):
        if not self.requisition_id.date_required:
            raise UserError(_('You must select the required date in the form.'))
        if self.requisition_id.state != 'draft':
            raise UserError(_('You can add an item only in draft state.'))
        if self.product_id:
            self.uom_id = self.product_id.uom_po_id or self.product_id.uom_id
            self.location_id = self.requisition_id.warehouse_id.lot_stock_id
        else:
            pass
            # self.uom_id = False
            # self.location_id = False

    @api.onchange('location_id')
    def onchange_location_id(self):
        warning = {}
        if self.location_id:
            if self.location_id != self.requisition_id.warehouse_id.lot_stock_id:
                print("\n......location_id...iffffff....")
                self.location_id = self.requisition_id.warehouse_id.lot_stock_id
                warning = {
                    'title': _('Warning'),
                    'message': _('You cannot change the location.')}
        return {'warning': warning}


    @api.onchange('uom_id', 'required_qty', 'approved_qty')
    def _onchange_uom_id(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id and self.uom_id:
            product_uom = self.product_id.uom_po_id or self.product_id.uom_id
            if self.uom_id.id != product_uom.id:
                self.uom_id = product_uom.id
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed.')}
                return {'warning': warning}
        # if self.required_qty and (not self.uom_id.allow_decimal_digits):
        #     integer, decimal = divmod(self.required_qty, 1)
        #     if decimal:
        #         self.required_qty = 0.00
        #         warning = {
        #             'title': _('Warning'),
        #             'message': _('You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the required qty should not contains decimal value') % (self.uom_id.name)}
        #         return {'warning': warning}
        # if self.approved_qty and (not self.uom_id.allow_decimal_digits):
        #     integer, decimal = divmod(self.approved_qty, 1)
        #     if decimal:
        #         self.approved_qty = 0.00
        #         warning = {
        #             'title': _('Warning'),
        #             'message': _('You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the approve qty should not contains decimal value') % (self.uom_id.name)}
        #         return {'warning': warning}
        return {'warning': warning}

    # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete an item which is only in the draft state.'))
        return super(PoRequisitionItemLines, self).unlink()
    
