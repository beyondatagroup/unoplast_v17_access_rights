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

class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    product_mtrs = fields.Float(string='Equivalent Length (mtrs)', digits=('Product Unit of Measure'), copy=False)

class RawMaterialIssue(models.Model):
    _name = 'raw.material.issue'
    _description = 'Raw Material Issue'
    _order = 'id desc'
    
    # @api.multi
    @api.depends('return_lines', 'returned_mtrs', 'qty_price_unit', 'qty_price_value')
    def _get_total_mtrs(self):
        expected_mtrs_total = 0.00
        balance_mtrs_total = 0.00
        for each in self:
            expected_mtrs_total = 0.00
            balance_mtrs_total = 0.00
            for eachline in each.return_lines:
                expected_mtrs_total += eachline.expected_mtrs
            balance_mtrs_total += each.issued_mtrs - each.returned_mtrs
            each.expected_mtrs_total = expected_mtrs_total
            each.balance_mtrs_total = balance_mtrs_total
            each.balance_mtrs_total_value = (balance_mtrs_total * each.qty_price_unit)
        
    # @api.one
    # @api.depends('return_lines.uom_id', 'return_lines.total_returned_qty', 'return_lines.total_returned_mtrs')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string, mtrs_string = "", ""
        for line in self.return_lines:
            if line.uom_id.id in qty_dict:
                qty_dict[line.uom_id.id]['total_returned_qty'] += line.total_returned_qty and line.total_returned_qty or 0.00
                qty_dict[line.uom_id.id]['total_returned_mtrs'] += line.total_returned_mtrs and line.total_returned_mtrs or 0.00
            else:
                qty_dict[line.uom_id.id] = {
                    'total_returned_qty': line.total_returned_qty and line.total_returned_qty or 0.00,
                    'total_returned_mtrs': line.total_returned_mtrs and line.total_returned_mtrs or 0.00,
                    'product_uom': line.uom_id and line.uom_id.name or '' 
                    }
        for each in qty_dict:
            if qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['total_returned_qty']) + " " + (qty_dict[each]['product_uom'])
                if mtrs_string:
                    mtrs_string += " , "
                mtrs_string += "{0:.3f}".format(qty_dict[each]['total_returned_mtrs']) + " Mtrs"
        self.total_quantity_based_uom = qty_string
        self.total_mtrs_based_uom = mtrs_string
                
    name = fields.Char(string='Issue No', required=True, readonly=True, default=lambda self: _('Issue #'), copy=False)
    date_issue = fields.Date(string='Issue Date', required=True, default=fields.Date.context_today, copy=False,readonly=True, )
    user_id = fields.Many2one('res.users', string='Created By', readonly=True, required=True, default=lambda self: self.env.user, copy=False)
    issued_to = fields.Char(string='Material Issued To', required=True, copy=False,  size=20)
    department_id = fields.Many2one('hr.department', string='Issued To Department', copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', required=True, copy=False,)
    product_id = fields.Many2one('product.product', string='Product', required=True, copy=False, )
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True, copy=False, readonly=True, )
    current_stock = fields.Float(string='Current Stock', readonly=True, copy=False, digits=('Product Unit of Measure'))
    qty_price_unit = fields.Float(string='Price Unit(in Mtrs)', readonly=True, copy=False)
    qty_price_value = fields.Float(string='Total Value(in Qty)', readonly=True, copy=False)
    issued_qty = fields.Float(string='Issued Quantity', required=True, copy=False, digits=('Product Unit of Measure'),  )
    issued_mtrs = fields.Float(string='Equivalent Mtrs', required=True, copy=False, digits=('Product Unit of Measure'), )
    returned_mtrs = fields.Float(string='Returned Mtrs', copy=False, digits=('Product Unit of Measure'), readonly=True)
    expected_mtrs_total = fields.Float(string='Expected Return Mtrs', copy=False, digits=('Product Unit of Measure'), readonly=True, compute='_get_total_mtrs', store=True)
    balance_mtrs_total = fields.Float(string='Balance Return Mtrs', copy=False, digits=('Product Unit of Measure'), readonly=True, compute='_get_total_mtrs', store=True)
    balance_mtrs_total_value = fields.Float(string='Value of Balance Return', copy=False, digits=('Product Unit of Measure'), readonly=True, compute='_get_total_mtrs', store=True)
    location_id = fields.Many2one('stock.location', string='Source Location', required=True, copy=False,  )
    location_dest_id = fields.Many2one('stock.location', string='Destination Location', required=True, copy=False,  )
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('raw.material.issue'), copy=False)
    closed = fields.Boolean(string='Force Closed', copy=False, default=False, readonly=True)
    reason = fields.Text(string='Reason', readonly=True, copy=False, default=' ')
    return_lines = fields.One2many('raw.material.return.line', 'issue_id', string='Issue', required=True, copy=False, )
    move_lines = fields.One2many('stock.move', 'issue_id', string='Stock Move', copy=False)
    remarks = fields.Text(string='Remarks', copy=False, readonly=True)
    picking_type_id = fields.Many2one('stock.picking.type', 'Picking Type', required=True, 
        help="This will determine picking type of incoming shipment", readonly=True)
    state = fields.Selection([
        ('draft','Draft'),
        ('issued','Issued'),
        ('inprogress','Return in Progress'),
        ('done','Done')
        ], string='Status', readonly=True, copy=False, default='draft')
    issue_type = fields.Selection([('normal', 'Normal'), ('reverse', 'Unbuild')], string='Issue Type', readonly=True, default='normal')
    reverse_issue = fields.Boolean('Unbuild Cloth Issue', default=False, readonly=True, copy=False)
    reverse_issue_id = fields.Many2one('raw.material.issue', 'Unbuild Cloth Issue No', readonly=True, copy=False)  
    source_doc = fields.Char('Source Document', readonly=True, copy=False)
    hide_done = fields.Boolean('Hide', default=False)
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Returned Quantity')
    total_mtrs_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Returned Mtrs')

    def print_raw_material_issue(self):
        return self.env.ref('ebits_inventory.action_raw_material_issue_report').report_action(self)
    @api.onchange('product_id')
    def _onchange_product_id(self):
        warning = {}
        if self.product_id:
            if not self.product_id.product_mtrs:
                warning = {
                    'title': _('Warning'),
                    'message': _('Equivalent mtrs is not defined in the product master!. \nKindly contact your administrator!!!.')}
                self.product_id = False
                self.issued_qty = 0.00
                self.issued_mtrs = 0.00
            else:
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                self.issued_qty = 0.00
                self.issued_mtrs = 0.00
        else:
            self.uom_id = False
            self.issued_qty = 0.00
            self.issued_mtrs = 0.00
        return {'warning': warning}

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        warning = {}
        if self.warehouse_id:
            if self.warehouse_id.cloth_order_picking_type_id:
                self.picking_type_id = self.warehouse_id.cloth_order_picking_type_id and self.warehouse_id.cloth_order_picking_type_id.id or False
            else:
                self.picking_type_id = False
                self.location_id = False
                self.location_dest_id = False
                warning = {
                    'title': _('Warning'),
                    'message': _('The picking type of cloth orders is not configured in  warehouse')} 
        else:
            self.picking_type_id = False
        return {'warning': warning}
        
    @api.onchange('picking_type_id')
    def _onchange_picking_type_id(self):
        warning = {}
        if self.picking_type_id and self.warehouse_id:
            if self.picking_type_id.id != self.warehouse_id.cloth_order_picking_type_id.id:
                self.picking_type_id = self.warehouse_id.cloth_order_picking_type_id and self.warehouse_id.cloth_order_picking_type_id.id or False
                warning = {
                            'title': _('Warning'),
                            'message': _('picking type cannot be changed.This picking type is the default warehouse of the picking type that you have selected')}
        return {'warning': warning}
            
            
    @api.onchange('product_id', 'issued_qty')
    def _onchange_issued_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            if not self.product_id.product_mtrs:
                warning = {
                    'title': _('Warning'),
                    'message': _('Equivalent mtrs is not defined in the product master!. \nKindly contact your administrator!!!.')
                    }
                self.issued_qty = 0.00
                self.product_id = False
                self.issued_mtrs = 0.00
                return {'warning': warning}
            if self.issued_qty:
                if not self.uom_id.allow_decimal_digits:
                    integer, decimal = divmod(self.issued_qty, 1)
                    if decimal:
                        self.issued_qty = 0.00
                        self.issued_mtrs = 0.00
                        warning = {
                            'title': _('Warning'),
                            'message': _('You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the issued quantity should not contains decimal value') % (self.uom_id.name)
                            }
                        return {'warning': warning}
                self.issued_mtrs = self.product_id.product_mtrs and (self.product_id.product_mtrs * self.issued_qty) or 0.00
        else:
            self.issued_qty = 0.00
            self.issued_mtrs = 0.00
        return {'warning': warning}
        
    @api.onchange('product_id', 'issued_mtrs')
    def _onchange_issued_mtrs(self):
        warning = {}
        if self.issued_mtrs:
            if (not self.product_id) or (not self.issued_qty):
                self.issued_mtrs = 0.00
                warning = {
                    'title': _('Warning'),
                    'message': _('Please enter product or issued quantity first')
                }
            elif self.product_id.product_mtrs and ((self.issued_qty * self.product_id.product_mtrs) != self.issued_mtrs):
                self.issued_mtrs = self.issued_qty * self.product_id.product_mtrs
                warning = {
                    'title': _('Warning'),
                    'message': (_('Issued mtrs cannot be changed.This is the default equivalent length of  %s %s of %s ')%(self.issued_qty, self.product_id.uom_id.name, self.product_id.name_get()[0][1]))
                }
        else:
            if self.product_id and self.issued_qty:
                self.issued_mtrs = self.issued_qty * self.product_id.product_mtrs
        return {'warning': warning}
        
    @api.onchange('location_id')
    def onchange_location_id(self):
        warning = {}
        if self.location_id:
            if not self.picking_type_id:
                self.location_id = False
                warning = {
                        'title': _('Warning'),
                        'message': _('Please select warehouse and picking type first.')}
            if self.picking_type_id:
                if self.location_id.id != self.picking_type_id.default_location_src_id.id:
                    warning = {
                        'title': _('Warning'),
                        'message': _('Cannot be changed.This is the default source location of the picking type you have mentioned.')}
                    self.location_id = self.picking_type_id.default_location_src_id and self.picking_type_id.default_location_src_id.id or False
        return {'warning': warning}
    
    @api.onchange('location_dest_id')
    def onchange_location_dest_id(self):
        warning = {}
        if self.location_dest_id:
            if not self.picking_type_id:
                self.location_dest_id = False
                warning = {
                        'title': _('Warning'),
                        'message': _('Please select warehouse and picking type first.')}
            if self.picking_type_id:
                if self.location_dest_id.id != self.picking_type_id.default_location_dest_id.id:
                    warning = {
                        'title': _('Warning'),
                        'message': _('Location cannot be changed.This is the default destination location of the picking type you have selected.')}
                    self.location_dest_id = self.picking_type_id.default_location_dest_id and self.picking_type_id.default_location_dest_id.id or False
        return {'warning': warning}
    
    @api.onchange('picking_type_id')
    def onchange_picking_type_id(self):
        warning = {}
        if self.picking_type_id:
            if not self.warehouse_id:
                self.picking_type_id = False
                warning = {
                        'title': _('Warning'),
                        'message': _('Please select warehouse first.')}
            elif self.warehouse_id.id != self.picking_type_id.warehouse_id.id:
                self.picking_type_id = False
                if self.location_id:
                    self.location_id = False
                warning = {
                        'title': _('Warning'),
                        'message': _('Picking type did not match.Please select a picking type with respect to the warehouse mentioned.')}
            else:
                self.location_id = self.picking_type_id.default_location_src_id and self.picking_type_id.default_location_src_id.id or False
                self.location_dest_id = self.picking_type_id.default_location_dest_id and self.picking_type_id.default_location_dest_id.id or False
        return {'warning': warning}
        
    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        warning = {}
        if self.product_id and self.uom_id:
            if self.uom_id.id != self.product_id.uom_id.id:
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                        'title': _('Warning'),
                        'message': _('Unit of measure cannot be changed.')}
        else:
            self.uom_id = False
        return {'warning': warning}
    
    # @api.multi
    def action_check_stock(self):
        stock_quant_obj = self.env['stock.quant']
        qty_available = 0.00
        for each in self:
            qty_available = 0.00
            quant_search = stock_quant_obj.search_read([('location_id', '=', each.location_id.id), ('product_id', '=' ,each.product_id.id)],['inventory_quantity_auto_apply'])
            for each_quant in quant_search:
                qty_available += each_quant['inventory_quantity_auto_apply']
            each.write({'current_stock' : qty_available})
        return True
    
    # @api.multi
    def action_issued(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        issue = False
        picking_id = False
        qty_price_value = 0.00
        for each in self:
            if each.issue_type == 'normal':
                each.action_check_stock()
                if each.name == 'Issue #': 
                    if each.warehouse_id.raw_material_issue_sequence_id:
                        name = each.warehouse_id.raw_material_issue_sequence_id.next_by_id()
                        each.name = name
                    else:
                        raise UserError(_('Raw material sequence is not defined in warehouse (%s).Please contact your administrator') % (each.warehouse_id.name))
                if not each.return_lines:
                    raise UserError(_('No return products mentioned! \nPlease enter the return products to proceed further'))
                if each.issued_qty > each.current_stock:
                    raise UserError(_('Stock unavailable! \nCannot issue more than the current stock.'))
                if each.issued_qty <= 0.00:
                    raise UserError(_('Zero quantity.\nIssue is not accepted due to zero issue quantity'))
                if each.issued_mtrs <= 0.00:
                    raise UserError(_('Issue is not accepted due to zero equivalent metres'))
            else:
                if each.name == 'Unbuild #': 
                    each.name = self.env['ir.sequence'].next_by_code('raw.material.issue.code') or 'Unbuild #'
            if each.issued_qty:
                each.state = 'issued'
                picking_obj = self.env['stock.picking']
                move_obj = self.env['stock.move']
                if not issue:
                    picking_id = picking_obj.create({
                        'location_dest_id':  each.location_dest_id and each.location_dest_id.id or False,
                        'location_id': each.location_id and each.location_id.id or False,
                        'origin': each.name and each.name or '',
                        'picking_type_id': each.picking_type_id and each.picking_type_id.id or False
                    })
                    issue = True
                move_id = move_obj.create({
                    'name': each.product_id and (each.product_id.display_name) + ' / ' +
                                                (each.name and each.name or '') +  
                                                (each.issue_type == 'reverse' and  ' (' + each.source_doc + ')' or '') or "",
                    'company_id': each.company_id and each.company_id.id or False,
                    'product_id': each.product_id and each.product_id.id or False,
                    'product_uom': each.uom_id and each.uom_id.id or False,
                    'product_uom_qty': each.issued_qty and each.issued_qty or 0.00,
                    'location_id': each.location_id and each.location_id.id or False,
                    'location_dest_id': each.location_dest_id and each.location_dest_id.id or False,
                    'origin': each.name,
                    'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                    'issue_id': each.id,
                    'picking_id': picking_id.id,
                })
            for line in each.return_lines:
                line.state = 'waiting'
            if picking_id:
                picking_id.action_confirm()
                picking_id.action_assign()
                # picking_id.force_assign()
                for pack_line in picking_id.move_ids_without_package:
                    pack_line.write({'product_packaging_quantity': pack_line.product_qty})
                # picking_id.do_transfer()
                each.action_check_stock()
                picking_id.button_validate()

                if each.issue_type == 'normal':
                    each.reason += '\nIssue has been done by ' + str(self.env.user.name) + ' on ' + str(date)
                else:
                    each.reason += '\nReturn has been done by ' + str(self.env.user.name) + ' on ' + str(date)
                for move_line in each.move_lines:
                    if move_line.product_id.id == each.product_id.id:
                        qty_price_value += (move_line.price_unit * move_line.product_uom_qty)
                each.qty_price_value = qty_price_value
                each.qty_price_unit = (qty_price_value / each.issued_mtrs)
        return True

    # @api.multi
    def action_closed(self):
        for each in self:
            each.state = 'done'
            for eachline in each.return_lines:
                eachline.state = 'done'
        return True

    # @api.multi
    def action_done_issue(self):
        for each in self:
            if each.balance_mtrs_total:
                raise UserError(_('You cannot complete the form since issued and return qty is not equal! \nPlease force close the form'))
            each.state = 'done'
        return True
        
    # @api.multi
    def action_state_update(self):
        flag = True
        state = []
        for each in self:
            for eachline in each.return_lines:
                state.append(eachline.state)
            if 'draft' in state:
                each.state = 'Draft'
            elif 'waiting' in state:
                each.state = 'inprogress'
            elif 'partial' in state:
                each.state = 'inprogress'
            elif 'done' in state:
                each.state = 'inprogress'
                each.hide_done = True
#            else:
#                each.state = 'done'
        return True
    
        
    def _prepare_account_move_line(self, cost, credit_account_id, debit_account_id):
        """
        Generate the account.move.line values to post to track the stock valuation difference due to the
        processing of the given quant.
        """
        self.ensure_one()
        name = ""
        if self.source_doc:
            name = self.name + "( " + self.source_doc + ")"
        else:
            name = self.name
        debit_line_vals = {
            'name': self.product_id.name_get()[0][1] + " / " + name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_id.uom_id.id,
            'ref': self.name,
            'debit': cost,
            'credit': 0,
            'account_id': debit_account_id,
        }
        credit_line_vals = {
            'name': self.product_id.name_get()[0][1] + " / " + name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_id.uom_id.id,
            'ref': self.name,
            'credit': cost,
            'debit': 0,
            'account_id': credit_account_id,
        }
        res = [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]
        return res
        
    # @api.multi
    def action_create_account_entry(self):
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']
        journal_id = False
        for each in self:
            if each.balance_mtrs_total_value < 0.00:
                #RM category stock valuation account
                credit_account_id = each.product_id.categ_id and (each.product_id.categ_id.property_stock_account_output_categ_id and each.product_id.categ_id.property_stock_account_output_categ_id.id or False) or False
                #WIP location account
                debit_account_id = each.location_dest_id and (each.location_dest_id.valuation_in_account_id and each.location_dest_id.valuation_in_account_id.id or False) or False
                cost = abs(each.balance_mtrs_total_value)
                if not credit_account_id:
                    raise UserError(_("Configuration error. Please configure the stock valuation account in product category '%s'.") % (each.product_id.categ_id.name))
                if not debit_account_id:
                    raise UserError(_("Configuration error. Please configure the account in location master '%s'.") % (each.location_dest_id.name_get()[0][1]))
                move_lines = each._prepare_account_move_line(cost, credit_account_id, debit_account_id)
            elif each.balance_mtrs_total_value > 0.00:
                #WIP location account
                credit_account_id = each.location_dest_id and (each.location_dest_id.valuation_in_account_id and each.location_dest_id.valuation_in_account_id.id or False) or False
                #Cogs category stock output account
                debit_account_id = each.product_id.categ_id and (each.product_id.categ_id.property_stock_account_output_categ_id and each.product_id.categ_id.property_stock_account_output_categ_id.id or False) or False
                cost = abs(each.balance_mtrs_total_value)
                if not credit_account_id:
                    raise UserError(_("Configuration error. Please configure the account in location master '%s'.") % (each.location_dest_id.name_get()[0][1]))
                if not debit_account_id:
                    raise UserError(_("Configuration error. Please configure the stock output account in product category '%s'.") % (each.product_id.categ_id.name))
                move_lines = each._prepare_account_move_line(cost, credit_account_id, debit_account_id)
            if move_lines:
                date = self._context.get('force_period_date', fields.Date.context_today(self))
                accounts_data = self.product_id.product_tmpl_id.get_product_accounts()
                journal_id = accounts_data['stock_journal'].id
                move_vals = {
                    'journal_id': journal_id,
                    'line_ids': move_lines,
                    'date': date,
                    'ref': self.source_doc and (self.name + "( " + self.source_doc + " )") or self.name,
                    'user_id': self.env.user.id,
                    }
                new_account_move = move_obj.sudo().create(move_vals)
                new_account_move.sudo().post()
        return True
        
    # @api.multi
    def action_create_account_entry_reverse(self):
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']
        journal_id = False
        for each in self:
            if each.balance_mtrs_total_value > 0.00:
                #RM category stock valuation account
                credit_account_id = each.product_id.categ_id and (each.product_id.categ_id.property_stock_account_output_categ_id and each.product_id.categ_id.property_stock_account_output_categ_id.id or False) or False
                #WIP location account
                debit_account_id = each.location_id and (each.location_id.valuation_in_account_id and each.location_id.valuation_in_account_id.id or False) or False
                cost = abs(each.balance_mtrs_total_value)
                if not credit_account_id:
                    raise UserError(_("Configuration error. Please configure the stock valuation account in product category '%s'.") % (each.product_id.categ_id.name))
                if not debit_account_id:
                    raise UserError(_("Configuration error. Please configure the account in location master '%s'.") % (each.location_id.name_get()[0][1]))
                move_lines = each._prepare_account_move_line(cost, credit_account_id, debit_account_id)
            elif each.balance_mtrs_total_value < 0.00:
                #WIP location account
                credit_account_id = each.location_id and (each.location_id.valuation_in_account_id and each.location_id.valuation_in_account_id.id or False) or False
                #Cogs category stock output account
                debit_account_id = each.product_id.categ_id and (each.product_id.categ_id.property_stock_account_output_categ_id and each.product_id.categ_id.property_stock_account_output_categ_id.id or False) or False
                cost = abs(each.balance_mtrs_total_value)
                if not credit_account_id:
                    raise UserError(_("Configuration error. Please configure the account in location master '%s'.") % (each.location_id.name_get()[0][1]))
                if not debit_account_id:
                    raise UserError(_("Configuration error. Please configure the stock output account in product category '%s'.") % (each.product_id.categ_id.name))
                move_lines = each._prepare_account_move_line(cost, credit_account_id, debit_account_id)
            if move_lines:
                date = self._context.get('force_period_date', fields.Date.context_today(self))
                accounts_data = self.product_id.product_tmpl_id.get_product_accounts()
                journal_id = accounts_data['stock_journal'].id
                move_vals = {
                    'journal_id': journal_id,
                    'line_ids': move_lines,
                    'date': date,
                    'ref': self.name,
                    'user_id': self.env.user.id}
                new_account_move = move_obj.sudo().create(move_vals)
                new_account_move.sudo().post()
        return True
        
    # @api.multi
    def action_receive(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        picking_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        picking = False
        picking_id = False
        error = []
        state = []
        for each in self:
            for each_line in each.return_lines:
                if each_line.returned_qty:
                    error.append('yes')
            if 'yes' not in error:
                raise UserError(_('Kindly enter the return/receive qty to receive product(s)'))
            for line in each.return_lines:
                if line.returned_qty:
                    line.total_returned_qty += line.returned_qty
                    line.total_returned_mtrs += (line.expected_qty and (line.returned_qty * (line.expected_mtrs / line.expected_qty)) or 0.00)
                    each.returned_mtrs += (line.expected_qty and (line.returned_qty * (line.expected_mtrs / line.expected_qty)) or 0.00)
                    if line.balance_qty:
                        line.state = 'partial'
                    else:
                        line.state = 'done'
                    if not picking:
                        picking_id = picking_obj.create({
                            'location_dest_id':  line.location_dest_id and line.location_dest_id.id or False,
                            'location_id': line.location_id and line.location_id.id or False,
                            'origin': each.name and each.name or '',
                            'picking_type_id': each.picking_type_id and each.picking_type_id.id or False
                        })
                        picking = True
                    move_id = move_obj.create({
                        'name': line.product_id and (line.product_id.name_get()[0][1]) + ' / ' + 
                                                    (each.name and each.name or '') +  
                                                    (each.issue_type == 'reverse' and  ' (' + each.source_doc + ')'  or '') or "",
                        'company_id': line.company_id and line.company_id.id or False,
                        'product_id': line.product_id and line.product_id.id or False,
                        'product_uom': line.uom_id and line.uom_id.id or False,
                        'product_uom_qty': line.returned_qty and line.returned_qty or 0.00,
                        'location_id': line.location_id and line.location_id.id or False,
                        'location_dest_id': line.location_dest_id and line.location_dest_id.id or False,
                        'origin': each.name,
                        'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                        'issue_id': each.id,
                        'picking_id': picking_id.id,
                        'picking_type_id': each.picking_type_id and each.picking_type_id.id or False,
                        'price_unit': line.product_id.product_mtrs and ((line.product_id.product_mtrs) * each.qty_price_unit) or 0.00
                    })
                    line.returned_qty = 0.00
            if picking_id:
                picking_id.action_confirm()
                picking_id.action_assign()
                # picking_id.force_assign()
                for pack_line in picking_id.move_ids_without_package:
                    pack_line.write({'product_packaging_quantity': pack_line.product_qty})
                # picking_id.do_transfer()
            each.action_check_stock()
            each.action_state_update()
            if each.state == 'done':
                if each.returned_mtrs and each.balance_mtrs_total_value != 0.00:
                    each.action_create_account_entry()
                each.reason += '\nFinal receipt has been received by ' + str(self.env.user.name) + ' on ' + str(date)
            else:
                each.reason += '\nPartial receipt has been received by ' + str(self.env.user.name) + ' on ' + str(date)
#                if each.issue_type == 'reverse':
#                    each.action_closed()
        return True
        
    # @api.multi
    def action_reverse_order(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        material_return_line_obj = self.env['raw.material.return.line']
        picking_obj = self.env['stock.picking']
        for each in self:
            mat_issue_id = self.create({
                'product_id': each.product_id and each.product_id.id or False,
                'uom_id': each.uom_id and each.uom_id.id or False,
                'issued_to': each.issued_to and each.issued_to or '',
                'issued_qty': each.issued_qty and each.issued_qty or 0.00,
                'issued_mtrs': each.issued_mtrs and each.issued_mtrs or 0.00,
                'returned_mtrs': each.returned_mtrs and each.returned_mtrs or 0.00,
                'qty_price_value': each.qty_price_value and each.qty_price_value or 0.00,
                'qty_price_unit': each.qty_price_unit and each.qty_price_unit or 0.00,
                'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                'picking_type_id': each.picking_type_id and each.picking_type_id.id or False,
                'location_id': each.location_dest_id and each.location_dest_id.id or False,
                'location_dest_id': each.location_id and each.location_id.id or False,
                'source_doc': each.name and each.name or '',
                'company_id': each.company_id and each.company_id.id or False,
                'issue_type': 'reverse',
                'state': 'done', 
                'name': self.env['ir.sequence'].next_by_code('raw.material.issue.code') or 'Unbuild #',
                'reason': 'Unbuild entry has been created and posted by ' + str(self.env.user.name) + ' on ' + str(date)
            })
            for line in each.return_lines:
                material_return_line_obj.create({
                    'product_id': line.product_id and line.product_id.id or False,
                    'uom_id': line.uom_id and line.uom_id.id or  False,
                    'expected_qty': line.total_returned_qty and line.total_returned_qty or 0.00,
                    'expected_mtrs': line.total_returned_mtrs and line.total_returned_mtrs or 0.00,
                    'returned_qty': line.total_returned_qty and line.total_returned_qty or 0.00,
                    'total_returned_qty': line.total_returned_qty and line.total_returned_qty or 0.00,
                    'total_returned_mtrs': line.total_returned_mtrs and line.total_returned_mtrs or 0.00,
                    'location_id': line.location_dest_id and line.location_dest_id.id or False,
                    'location_dest_id': line.location_id and line.location_id.id or False,
                    'warehouse_id': line.warehouse_id and line.warehouse_id.id or False,
                    'issue_id': mat_issue_id.id,
                    'state': 'done'})
            each.reverse_issue = True
            each.reverse_issue_id = mat_issue_id.id
            
            return_picking = []
            for return_move in each.move_lines:
                if return_move.picking_id:
                    return_picking.append(return_move.picking_id.id)
            return_picking = list(set(return_picking))
            for each_picking_return in picking_obj.browse(return_picking):
                picking_type_id = each_picking_return.picking_type_id.return_picking_type_id.id or each_picking_return.picking_type_id.id
                new_picking = each_picking_return.copy({
                    'move_lines': [],
                    'picking_type_id': picking_type_id,
                    'state': 'draft',
                    'origin': 'Return of ' + each_picking_return.name,
                    'location_id': each_picking_return.location_dest_id.id,
                    'location_dest_id': each_picking_return.location_id.id,})
                    
                for return_move in each_picking_return.move_lines:
                    move_dest_id = False
                    return_move.origin =  mat_issue_id.name and mat_issue_id.name or ''
                    if return_move.product_uom_qty:
                        if return_move.origin_returned_move_id.move_dest_id.id and return_move.origin_returned_move_id.move_dest_id.state != 'cancel':
                            move_dest_id = return_move.origin_returned_move_id.move_dest_id.id
                        else:
                            move_dest_id = False

                        return_move.copy({
                            'name': return_move.product_id and (return_move.product_id.name_get()[0][1]) + ' / ' + 
                                                (mat_issue_id.name and mat_issue_id.name or '') +  
                                                " (" + mat_issue_id.source_doc + ")",
                            'company_id': mat_issue_id.company_id and mat_issue_id.company_id.id or False,
                            'product_id': return_move.product_id.id,
                            'product_uom_qty': return_move.product_uom_qty,
                            'picking_id': new_picking.id,
                            'state': 'draft',
                            'location_id': return_move.location_dest_id.id,
                            'location_dest_id': return_move.location_id.id or each.location_id.id,
                            'picking_type_id': picking_type_id,
                            'warehouse_id': return_move.warehouse_id.id,
                            'origin_returned_move_id': return_move.id,
                            'procure_method': 'make_to_stock',
                            'move_dest_id': move_dest_id,
                            'issue_id': mat_issue_id.id,
                            })
                new_picking.action_confirm()
                new_picking.action_assign()
                
                if new_picking:
                    new_picking.action_confirm()
                    new_picking.action_assign()
                    # new_picking.force_assign()
                    for pack_line in new_picking.move_ids_without_package:
                        pack_line.write({'product_packaging_quantity': pack_line.product_qty})
                    # new_picking.do_transfer()
                    new_picking.button_validate()
            if mat_issue_id.returned_mtrs and mat_issue_id.balance_mtrs_total_value != 0.00:
                mat_issue_id.action_create_account_entry_reverse()
        return True
                        
    # @api.multi
    def action_open_reverse_issue_link(self):
        view = self.env.ref('ebits_inventory.raw_material_issue_reverse_form_view')
        wiz = self.env['raw.material.issue'].browse(self.reverse_issue_id.id)
        return {
            'name': _('Unbuild Issue'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'res_model': 'raw.material.issue',
            'res_id': wiz.id,
        }
    
    # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete a form which is only in draft state'))
        return super(RawMaterialIssue, self).unlink()

class RawMaterialReturnline(models.Model):
    _name = 'raw.material.return.line'
    _description = 'Raw Material Issue Return Lines'
    _order  = 'id desc'
    _rec_name = 'product_id'
    
    @api.depends('returned_qty', 'expected_qty', 'total_returned_qty')
    def get_balance_qty(self):
        for line in self:
            line.balance_qty = line.expected_qty - line.total_returned_qty
            line.balance_mtrs = line.expected_mtrs - line.total_returned_mtrs

    issue_id = fields.Many2one('raw.material.issue', string='Issue No', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True, )
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure',readonly=True, )
    expected_qty = fields.Float(string='Expected Return Quantity', required=True, digits=('Product Unit of Measure'), readonly=True, )
    expected_mtrs = fields.Float(string='Expected Return Mtrs', required=True, digits=('Product Unit of Measure'), readonly=True, )
    returned_qty = fields.Float(string='Return Quantity', readonly=True, digits=('Product Unit of Measure'), )
    total_returned_qty = fields.Float(string='Total Returned Quantity', readonly=True, digits=('Product Unit of Measure'))
    total_returned_mtrs = fields.Float(string='Total Returned Mtrs', readonly=True, digits=('Product Unit of Measure'))
    balance_qty = fields.Float(compute='get_balance_qty', string='Balance To be Received', digits=('Product Unit of Measure'), store=True)
    balance_mtrs = fields.Float(compute='get_balance_qty', string='Balance Mtrs To be Received', digits=('Product Unit of Measure'), store=True)
    location_id = fields.Many2one('stock.location', string='Source Location',readonly=True, )
    location_dest_id = fields.Many2one('stock.location', string='Destination Location', readonly=True,)
    closed = fields.Boolean(string='Force Closed', copy=False, default=False, readonly=True)
    remarks = fields.Char(string='Remarks', readonly=True, )
    state = fields.Selection([
        ('draft','Draft'),
        ('waiting','Waiting'),
        ('partial','Partially Returned'),
        ('done','Done')
        ], string='Status', readonly=True, copy=False, default='draft')
    company_id = fields.Many2one('res.company', string='Company', related='issue_id.company_id', store=True, readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse / Branch', related='issue_id.warehouse_id', store=True, readonly=True)
    issued_to = fields.Char(string='Material Issued To', related='issue_id.issued_to', store=True, readonly=True)
    issue_type = fields.Selection(string='Issue Type', related='issue_id.issue_type', store=True, readonly=True)
        
    # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can delete an item which is only in draft state'))
        return super(RawMaterialReturnline, self).unlink()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        warning = {}
        if self.env.context.get('create_additional'):
            if self.product_id:
                if not self.env.context.get('location_id'):
                    warning = {
                            'title': _('Warning'),
                            'message': _('Kindly enter source location in the form.')}
                    self.product_id = False
                    self.expected_qty = 0.00
                    self.expected_mtrs = 0.00
                    return {'warning': warning}
                if not self.env.context.get('location_dest_id'):
                    warning = {
                            'title': _('Warning'),
                            'message': _('Kindly enter destination location in the form.')}
                    self.product_id = False
                    self.expected_qty = 0.00
                    self.expected_mtrs = 0.00
                    return {'warning': warning}
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id  or False
            else:
                self.uom_id = False
                self.expected_qty = 0.00
                self.expected_mtrs = 0.00
        else:
            if self.product_id:
                if self.issue_id.state != 'draft':
                    warning = {
                            'title': _('Warning'),
                            'message': _('You can change or select the product only in draft state.')}
                    self.product_id = False
                    self.expected_qty = 0.00
                    self.expected_mtrs = 0.00
                    return {'warning': warning}
                if not self.issue_id.location_id:
                    warning = {
                            'title': _('Warning'),
                            'message': _('Kindly enter source location in the form.')}
                    self.product_id = False
                    self.expected_qty = 0.00
                    self.expected_mtrs = 0.00
                    return {'warning': warning}
                if not self.issue_id.location_dest_id:
                    warning = {
                            'title': _('Warning'),
                            'message': _('Kindly enter destination location in the form.')}
                    self.product_id = False
                    self.expected_qty = 0.00
                    self.expected_mtrs = 0.00
                    return {'warning': warning}
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id  or False
            else:
                self.uom_id = False
                self.expected_qty = 0.00
                self.expected_mtrs = 0.00
        return {}
    #
    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        warning = {}
        if self.product_id and self.uom_id:
            if self.uom_id.id != self.product_id.uom_id.id:
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed.')}
        else:
            self.uom_id = False
        return {'warning': warning}


    @api.onchange('product_id', 'expected_mtrs')
    def _onchange_expected_mtrs(self):
        warning = {}
        if self.expected_mtrs:
            if (not self.product_id) or (not self.expected_qty):
                self.expected_mtrs = 0.00
                warning = {
                    'title': _('Warning'),
                    'message': _('Please enter product or return quantity first')
                }
            elif self.product_id.product_mtrs and self.expected_mtrs != (self.product_id.product_mtrs * self.expected_qty):
                self.expected_mtrs = self.product_id.product_mtrs * self.expected_qty
                warning = {
                    'title': _('Warning'),
                    'message': _('expected return mtrs cannot be changed. This is the default equivalent length of  %s %s of %s ') % (self.expected_qty, self.product_id.uom_id.name, self.product_id.name_get()[0][1])}
        else:
            if self.product_id and self.expected_qty:
                self.expected_mtrs = self.expected_qty * self.product_id.product_mtrs
        return {'warning': warning}

    @api.onchange('product_id', 'expected_qty')
    def _onchange_expected_qty(self):
        warning = {}
        if self.product_id:
            if not self.product_id.product_mtrs:
                warning = {
                    'title': _('Warning'),
                    'message': _('Equivalent mtrs is not defined in the product master!. \nKindly contact your administrator!!!.')
                    }
                self.expected_qty = 0.00
                self.product_id = False
                self.expected_mtrs = 0.00
                return {'warning': warning}
            integer, decimal = 0.00, 0.00
            if self.expected_qty:
                if not self.uom_id.allow_decimal_digits:
                    integer, decimal = divmod(self.expected_qty, 1)
                    if decimal:
                        self.expected_qty = 0.00
                        self.expected_mtrs = 0.00
                        warning = {
                            'title': _('Warning'),
                            'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the expected return quantity should not contains decimal value') % (self.uom_id.name)}
                        return {'warning': warning}
                self.expected_mtrs = self.product_id.product_mtrs * self.expected_qty
        else:
            self.expected_qty = 0.00
            self.expected_mtrs = 0.00
        return {'warning': warning}

    @api.onchange('returned_qty', 'balance_qty')
    def _onchange_returned_qty(self):
        warning = {}
        if self.product_id:
            integer, decimal = 0.00, 0.00
            if self.returned_qty:
                if self.returned_qty > self.balance_qty:
                    warning = {
                        'title': _('Warning'),
                        'message': _('Return qty must be lesser than the balance qty !. \nKindly contact your administrator!!!.')
                        }
                    self.returned_qty = 0.00
                    return {'warning': warning}
	            # if not self.uom_id.allow_decimal_digits:
			    #     integer, decimal = divmod(self.returned_qty, 1)
			    #     if decimal:
				#         self.returned_qty = 0.00
				#         warning = {
				# 	        'title': _('Warning'),
				# 	        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the return quantity should not contains decimal value') % (self.uom_id.name)}
        return {'warning': warning}

    # @api.onchange('location_id')
    # def _onchange_location_id(self):
    #     warning = {}
    #     if self.location_id:
    #         if self.issue_id.location_dest_id.id != self.location_id.id:
    #             self.location_id = self.issue_id.location_dest_id and self.issue_id.location_dest_id.id or False
    #             warning = {
    #                 'title': _('Warning'),
    #                 'message': _('Cannot be changed.This location should be same as that of the destination location in the form')}
    #     return {'warning': warning}

    # @api.onchange('location_dest_id')
    # def _onchange_location_dest_id(self):
    #     warning = {}
    #     if self.location_dest_id:
    #         if self.issue_id.location_id.id != self.location_dest_id.id:
    #             self.location_dest_id = self.issue_id.location_id and self.issue_id.location_id.id or False
    #             warning = {
    #                 'title': _('Warning'),
    #                 'message': _('Cannot be changed.This location should be same as that of the source location in the form')}
    #     return {'warning': warning}
    #
    # @api.multi
    def action_update_return_line(self):
        for each in self:
            if self.env.context.get('default_issue_id'):
                if not each.expected_qty:
                    raise UserError(_('Kindly enter the expected qty to return/scrap.'))
                each.write({'issue_id': self.env.context.get('issue_id'), 'state': 'waiting'})
        return True
    
class StockMove(models.Model):
    _inherit = 'stock.move'
    
    issue_id = fields.Many2one('raw.material.issue', string='Raw Material Issue', readonly=True, copy=False)
