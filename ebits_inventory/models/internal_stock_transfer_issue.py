# -*- coding: utf-8 -*-
# Part of EBITS TechCon

from datetime import datetime
import time
from odoo.exceptions import UserError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
import pytz
from odoo.tools.float_utils import float_compare, float_is_zero, float_round


class InternalStockTransferIssue(models.Model):
    _name = 'internal.stock.transfer.issue'
    _inherit = ['mail.thread']
    _description = 'Internal Stock Transfer Issue'
    _order = 'id desc'
    
    # @api.one
    # @api.depends('issue_lines.uom_id', 'issue_lines.issued_qty')
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
    
    name = fields.Char(string='Issue No', copy=False, required=True, readonly=True, default=lambda self: _('STI #'))
    date_required = fields.Date(string='Required Date', copy=False, required=True, readonly=True)
    date_last_issue = fields.Date(string='Last Issued Date', copy=False, readonly=True)
    date_requested = fields.Date(string='Requested Date', copy=False, readonly=True, required=True)
    date_approved = fields.Date(string='Approved Date', copy=False, readonly=True)
    issuer_user_id = fields.Many2one('res.users', string='Last Issue by', copy=False, readonly=True)
    approver_user_id = fields.Many2one('res.users', string='Approved By', copy=False, readonly=True, required=True)
    issuing_warehouse_id = fields.Many2one('stock.warehouse', string='Issuing Warehouse', readonly=True, copy=False, required=True)
    warehouse_master_id = fields.Many2one('internal.stock.transfer.master', string='Issuing From', copy=False)
    request_warehouse = fields.Char(string='Requesting Warehouse', copy=False, readonly=True)
    requesting_location_id = fields.Many2one('stock.location', string='Requesting Location', readonly=True, copy=False, required=True)
    issuing_location_id = fields.Many2one('stock.location', string='Issuing Location', readonly=True, copy=False, required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('internal.stock.transfer.issue'), copy=False)
    date_probable = fields.Date(string='Probable Date of Delivery', copy=False, )
    requester = fields.Char(string='Requester', readonly=True, copy=False)
    request_id = fields.Many2one('internal.stock.transfer.request', string='Request ID', readonly=True, copy=False)
    request_no = fields.Char(string='Request No', readonly=True, copy=False)
    issue_lines = fields.One2many('internal.stock.transfer.issue.line', 'issue_id', string='Issue')
    history = fields.Text(string='History', readonly=True, default=' ')
    picking_id = fields.Many2one('stock.picking', string='Reference', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('partial', 'Partially Issued'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], string='Status', readonly=True, copy=False, default='draft', index=True, tracking=True)
    closed = fields.Boolean(string='Force Closed')
    driver_id = fields.Many2one('truck.driver.employee', string="Driver", copy=False)
    vehicle_no = fields.Char(string="Vehicle No", size=64, copy=False)
    vehicle_owner = fields.Char(string="Vehicle Owner", size=64, copy=False)
    vehicle_owner_address = fields.Char(string="Vehicle Owner Address", size=128, copy=False)
    driver_licence = fields.Char(string="Driver Licence No", size=64, copy=False)
    driver_name = fields.Char(string="Driver Name", size=64, copy=False, )
    driver_licence_type = fields.Char(string="Driver Licence Type", size=64, copy=False, )
    driver_licence_place = fields.Char(string="Issued Licence Place", size=64, copy=False, )
    driver_phone = fields.Char(string="Driver Contact No", size=64, copy=False, )
    agent_name = fields.Char(string="Agent Name", size=64, copy=False, )
    move_lines = fields.One2many('stock.move', 'internal_stock_transfer_issue_id', string='Stock Move', tracking=True)
    req_remarks = fields.Text(string='Requested Remarks', readonly=True)
    issue_remarks = fields.Text(string='Issue Remarks', readonly=False, )
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Issued Quantity')
    
    ## @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You cannot delete a form which is not in draft state'))
        return super(InternalStockTransferIssue, self).unlink()
        
    ## @api.multi
    # def action_check_stock(self):
    #     print("\n\n...action_check_stock..........")
    #     stock_quant_obj = self.env['stock.quant']
    #     qty_available = on_hand_qty = 0.00
    #     for each in self:
    #         for line in each.issue_lines:
    #             qty_available = on_hand_qty = 0.00
    #             on_hand_qty = line.product_id.qty_available
    #             quant_search = stock_quant_obj.search_read([('location_id', '=', line.location_id.id), ('product_id', '=' ,line.product_id.id)],['inventory_quantity_auto_apply'])
    #             for each_quant in quant_search:
    #                 qty_available += each_quant['inventory_quantity_auto_apply']
    #             line.write({'stock_available': on_hand_qty, 'current_loc_stock': qty_available})
    #     return True

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

    
    @api.onchange('driver_id')
    def _onchange_driver_id(self):
        if self.driver_id:
            self.driver_name = self.driver_id.name or ""
            self.driver_licence = self.driver_id.driver_licence or ""
            self.driver_licence_type = self.driver_id.driver_licence_type or ""
            self.driver_licence_place = self.driver_id.driver_licence_place or ""
            self.driver_phone = self.driver_id.driver_phone or ""
        else:
            self.driver_name = ""
            self.driver_licence = ""
            self.driver_licence_type = ""
            self.driver_licence_place = ""
            self.driver_phone = ""
        
    ## @api.multi
    def action_issue_state_update(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        flag = []
        for each in self:
            for issue_line in each.issue_lines:
                if issue_line.state != 'done':
                    flag.append('no')
            if 'no' in flag:
                each.write({'state': 'partial'})
                each.history += '\nPartially issued by ' + str(self.env.user.name) + ' on ' + str(date)
            else:
                each.write({'state': 'done'})
                each.history += '\nThe final issue has been done by ' + str(self.env.user.name) + ' on ' + str(date)
        return True
    

    def action_issue(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        receipt_obj = self.env['internal.stock.transfer.receipt']
        receipt_line_obj = self.env['internal.stock.transfer.receipt.line']
        picking_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        issue = False
        picking_id = False
        for each in self:
            if not (each.vehicle_no) or not (each.vehicle_owner) or not (each.vehicle_owner_address) or not(each.driver_licence) or  not (each.driver_name) or not (each.driver_licence_type) or not (each.driver_licence_place) or not (each.driver_phone) or not (each.agent_name) or not (each.date_probable):
                raise UserError(_('Issue not complete.Please fill the transportation details completely and try again'))
            for line in each.issue_lines:
                if line.issue_qty > 0.00 and line.state != 'done':
                    if line.issue_qty <= line.pending_issue_qty and line.issue_qty <= line.current_loc_stock:
                        line.issued_qty += line.issue_qty
                        if each.name == 'STI #':
                            each.name =  self.env['ir.sequence'].next_by_code('internal.stock.transfer.issue') or 'STI #'
                        each.state = 'partial'
                        line.state  = 'partial' if line.pending_issue_qty != 0.00 else 'done'
                        if not issue:
                            picking_id = picking_obj.sudo().create({
                                'location_dest_id': each.issuing_warehouse_id.transit_location_id and each.issuing_warehouse_id.transit_location_id.id or False,
                                'scheduled_date': each.date_probable and each.date_probable or False,
                                'location_id': each.issuing_location_id and each.issuing_location_id.id or False,
                                'origin': each.name or '',
                                'picking_type_id': each.sudo().issuing_warehouse_id.int_type_id and each.sudo().issuing_warehouse_id.int_type_id.id or False,
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
                                'internal_stock_transfer_issue_id': each.id,
                                'internal_stock_transfer_request_id': each.sudo().request_id and each.sudo().request_id.id or False,
                                'note': each.issue_remarks and each.issue_remarks or '',
                            })
                            receipt_id = receipt_obj.sudo().create({
                                'receiving_warehouse_id': each.sudo().warehouse_master_id.requesting_warehouse_id and each.sudo().warehouse_master_id.requesting_warehouse_id.id or False,
                                'receiving_location_id': each.sudo().requesting_location_id and each.sudo().requesting_location_id.id or False,
                                'request_id': each.sudo().request_id and each.sudo().request_id.id or False,
                                'request_no': each.request_no and each.request_no or "",
                                'issue_id': each.id,
                                'date_requested': each.date_requested and each.date_requested or False,
                                'date_required': each.date_required and each.date_required or False,
                                'approver_user_id': each.approver_user_id and each.approver_user_id.id or False,
                                'date_approved': each.date_approved and each.date_approved or False,
                                'date_probable': each.date_probable and each.date_probable or False,
                                'date_last_issue': fields.Date.context_today(self),
                                'requester': each.requester and each.requester or "",
                                'warehouse_master_id': each.sudo().warehouse_master_id and each.sudo().warehouse_master_id.id or False,
                                'issue_warehouse': each.issuing_warehouse_id and each.issuing_warehouse_id.name or "",
                                'issuing_location_id': each.issuing_location_id and each.issuing_location_id.id or False,
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
                                'issue_ref': picking_id.name and picking_id.name or '',
                                'remarks': each.issue_remarks and each.issue_remarks or '',
                            })
                            issue = True
                        receipt_line_obj.sudo().create({
                            'receipt_id': receipt_id.id,
                            'product_id': line.product_id and line.product_id.id or False,
                            'uom_id': line.uom_id and line.uom_id.id or False,
                            'issued_qty': line.issue_qty and line.issue_qty or False,
                            'date_required': line.date_required and line.date_required or False
                        })
                        move_obj.sudo().create({
                            'product_id': line.product_id and line.product_id.id or False,
                            'product_uom': line.uom_id and line.uom_id.id or False,
                            'product_uom_qty': line.issue_qty and line.issue_qty or False,
                            'name': (line.product_id.display_name + ' / ' + each.name or ''),
                            'origin': each.name or '',
                            'location_id': each.issuing_location_id and each.issuing_location_id.id or False,
                            'location_dest_id': each.issuing_warehouse_id.transit_location_id and each.issuing_warehouse_id.transit_location_id.id or False,
                            'picking_id': picking_id.id,
                            'internal_stock_transfer_issue_id': each.id,
                            #'internal_stock_transfer_issue_line_id': line.id,
                            'internal_stock_transfer_request_id': line.issue_id.sudo().request_id and line.issue_id.sudo().request_id.id or False,
                            'picking_type_id': each.sudo().issuing_warehouse_id.int_type_id and each.sudo().issuing_warehouse_id.int_type_id.id or False
                        })
                    elif line.issue_qty > line.current_loc_stock:
                        raise UserError(_('Issue not complete.The issue qty for the product %s is greater than issuing location stock.Please click the check stock button and try  issuing again') % (line.product_id.name_get()[0][1]))
                    else:
                        raise UserError(_('Issue not complete.The issue qty for the product %s is greater than the pending quantity.Please change the issue quantity and try again') % (line.product_id.name_get()[0][1]))
                line.issue_qty = 0.00
            if picking_id:
                picking_id.action_confirm()
                picking_id.action_assign()
                # picking_id.force_assign()
                for pack_line in picking_id.move_ids_without_package:
                    pack_line.write({'product_packaging_quantity': pack_line.product_qty})
                # picking_id.do_transfer()
                each.action_issue_state_update()
                each.action_check_stock()
                picking_id.button_validate()


                each.date_last_issue = fields.Date.context_today(self)
                each.issuer_user_id = self.env.user.id
                each.picking_id = picking_id.id
                each.driver_id = False
                each.vehicle_no = ''
                each.vehicle_owner = ''
                each.vehicle_owner_address = ''
                each.driver_licence = ''
                each.driver_name = ''
                each.driver_licence_type = ''
                each.driver_licence_place = ''
                each.driver_phone = ''
                each.agent_name = ''
                each.date_probable = False
        return True

class InternalStockTransferIssueline(models.Model):
    _name = 'internal.stock.transfer.issue.line'
    _inherit = ['mail.thread']
    _description = 'Internal Stock Transfer Issue Line'

    @api.depends('approved_qty', 'issued_qty')
    def get_pending_qty(self):
        for line in self:
            line.pending_issue_qty = line.approved_qty - line.issued_qty
          
    @api.depends('issue_id.move_lines', 'issue_id.move_lines.internal_stock_transfer_receipt_id')
    def get_received_qty(self):
        stock_move_obj = self.env['stock.move']
        closed_receipt = []
        state_receipt = []
        for line in self:
            closed_receipt = []
            receipt_qty = 0.00
            for each_move in line.issue_id.move_lines:
                if each_move.sudo().internal_stock_transfer_receipt_id and each_move.product_id == line.product_id:
                    receipt_qty += each_move.product_uom_qty
                    if each_move.sudo().internal_stock_transfer_receipt_line_id.closed:
                        closed_receipt.append('True')
                    if each_move.sudo().internal_stock_transfer_receipt_line_id.state == 'draft':
                        state_receipt.append('draft')
                    elif each_move.sudo().internal_stock_transfer_receipt_line_id.state == 'partial':
                        state_receipt.append('partial')
                    elif each_move.sudo().internal_stock_transfer_receipt_line_id.state == 'done':
                        state_receipt.append('done')
            line.sudo().received_qty = receipt_qty
            line.sudo().pending_receipt_qty = line.sudo().issued_qty - line.sudo().received_qty
            if 'True' in closed_receipt:
                line.sudo().closed_receipt = True
            else:
                line.sudo().closed_receipt = False
            if 'done' in state_receipt:
                line.sudo().state_receipt = 'Received'
            if 'partial' in state_receipt:
                line.sudo().state_receipt = 'Partially Received'
            else:
                line.sudo().state_receipt = 'Draft'
            
    
    issue_id = fields.Many2one('internal.stock.transfer.issue', string='Issue No', ondelete='cascade')
    request_ref = fields.Char(string="Request Ref", size=64, copy=False, readonly=True)
    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True, readonly=True)
    approved_qty = fields.Float(string='Approved Quantity', digits=('Product Unit of Measure'), readonly=True)
    date_required = fields.Date(string='Required Date', required=True, readonly=True)
    stock_available = fields.Float(string='Current Stock', digits=('Product Unit of Measure'), readonly=True)
    current_loc_stock = fields.Float(string='Issuing Location Stock', digits=('Product Unit of Measure'), readonly=True)
    issue_qty = fields.Float(string='Issue Quantity', digits=('Product Unit of Measure'))
    issued_qty = fields.Float(string='Issued Quantity', digits=('Product Unit of Measure'), readonly=True)
    pending_issue_qty = fields.Float(compute='get_pending_qty', string='Pending Issue Quantity', digits=('Product Unit of Measure'), readonly=True, store=True)
    received_qty = fields.Float(compute=get_received_qty, string='Received Quantity', digits=('Product Unit of Measure'), readonly=True, store=True, compute_sudo=True)
    pending_receipt_qty = fields.Float(compute=get_received_qty, string='Pending to Receive Quantity', digits=('Product Unit of Measure'), readonly=True, store=True, compute_sudo=True)
    location_id = fields.Many2one('stock.location', string='Issuing Location', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('partial', 'Partially Issued'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], string='Status', readonly=True, copy=False, default='draft', index=True, tracking=True)
    state_receipt = fields.Char(compute=get_received_qty, string='Received Status', readonly=True, store=True, compute_sudo=True)
    remarks = fields.Text(string='Remarks', readonly=True)
    closed = fields.Boolean(string='Force Closed in Issue', default=False)
    closed_receipt = fields.Boolean(compute=get_received_qty, string='Force Closed in Receipt', readonly=True, store=True, compute_sudo=True, default=False)
    issuing_warehouse_id = fields.Many2one('stock.warehouse', string='Issuing Warehouse', related='issue_id.issuing_warehouse_id', readonly=True, copy=False, store=True)
    warehouse_master_id = fields.Many2one('internal.stock.transfer.master', string='Issuing From', related='issue_id.warehouse_master_id', readonly=True, store=True, copy=False)
    request_warehouse = fields.Char(string='Requesting Warehouse', related='issue_id.request_warehouse', readonly=True, store=True, copy=False)
    
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

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    internal_stock_transfer_issue_id = fields.Many2one('internal.stock.transfer.issue', string='Internal Stock Transfer Issue')
    
class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    internal_stock_transfer_issue_id = fields.Many2one('internal.stock.transfer.issue', string='Internal Stock Transfer Issue')
    
