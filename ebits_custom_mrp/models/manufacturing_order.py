# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import time
import math
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp

class SfManufaturingOrder(models.Model):
    _name = "sf.manufacturing.order"
    _description = "SF Manufacturing Orders"
    _order = "id desc"
    
    name = fields.Char('Sequence', size=20, readonly=True, copy=False, default=lambda self: _('New #'))
    date = fields.Date(string='Date', default=fields.Datetime.now, readonly=True, copy=False)
    date_done = fields.Date(string='Completed Date', readonly=True, copy=False)
    user_id = fields.Many2one('res.users', string='Creator', readonly=True, copy=False, default=lambda self: self.env.user)
    completed_user_id = fields.Many2one('res.users', string='Creator', readonly=True, copy=False)
    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True, copy=False)
    uom_id = fields.Many2one('uom.uom', string='UOM', required=True, readonly=True, copy=False)
    product_qty = fields.Float(string='Quantity', required=True, readonly=True, copy=False, digits='Product Unit of Measure')
    remarks = fields.Text(string='Remarks', readonly=True, copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', required=True, readonly=True)
    batch_number = fields.Char(string='Reference', readonly=True, size=64, copy=False)
    available_stock = fields.Float(string='Available Stock', readonly=True, copy=False, digits='Product Unit of Measure')
    source_location_id = fields.Many2one('stock.location', string='Source Location', readonly=True, copy=False)
    dest_location_id = fields.Many2one('stock.location', string='Destination Location', readonly=True, copy=False)
    shift_type = fields.Selection([('shift_1', 'Shift 1'), ('shift_2', 'Shift 2'), ('shift_3', 'Shift 3')], string="Shift", readonly=True, copy=False, required=True)
    materials_line = fields.One2many('raw.materials.line', 'order_id', string='Raw Materials', readonly=True)
    picking_type_id = fields.Many2one('stock.picking.type', string='Picking Type', readonly=True)
    scrap_line = fields.One2many('materials.scrap.line', 'order_id', string='Scrap')
    state = fields.Selection([('draft', 'Draft'), ('inprogress', 'Inprogress'), ('completed', 'Completed')], string='State', readonly=True, default='draft')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sf.manufacturing.order'), copy=False)
    material_issue_ids = fields.Many2many('material.issue', 'sf_mo_material_issue', 'order_id', 'issue_id', string='Material Issue', readonly=True)
    order_type = fields.Selection([('normal', 'Normal'), ('unbuild_order', 'Unbuild Order')], string='Order Type', readonly=True, default='normal')
    unbuild_order = fields.Boolean('SF Unbuild Order', default=False, readonly=True, copy=False)
    move_lines = fields.One2many('stock.move', 'sf_manuf_id', string='Stock Move', readonly=True)
    unbuild_order_id = fields.Many2one('sf.manufacturing.order', 'SF Unbuild Order', readonly=True, copy=False)  
    source_doc = fields.Char('Source Document', readonly=True, copy=False)
    type = fields.Char('Type', readonly=True, copy=False, default='Regular')
    product_category = fields.Char('Product Category', related="product_id.categ_id.name",readonly=True, copy=False)

    

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
            self.source_location_id = self.product_id.property_stock_production and self.product_id.property_stock_production.id or False
            #self.source_location_id = self.picking_type_id.default_location_dest_id and self.picking_type_id.default_location_dest_id.id or False
        else:
            self.uom_id = False
            self.source_location_id = False
        
    @api.onchange('uom_id')
    def onchange_uom_id(self):
        warning = {}
        if self.product_id and self.uom_id:
            if self.uom_id.id != self.product_id.uom_id.id:
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed.')}
        return {'warning': warning}
        
    @api.onchange('product_qty')
    def _onchange_product_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            if self.product_qty and (not self.uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.product_qty, 1)
                if decimal:
                    self.product_qty = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.uom_id.name)}
                    return {'warning': warning}
################################### COMMENTED FOR NOW########################################


    @api.onchange('picking_type_id')
    def onchange_picking_type_id(self):
        if self.picking_type_id:
            self.dest_location_id = self.picking_type_id.default_location_dest_id and self.picking_type_id.default_location_dest_id.id or False
            #self.source_location_id = self.picking_type_id.default_location_dest_id and self.picking_type_id.default_location_dest_id.id or False
        else:
            #self.source_location_id = False
            self.dest_location_id = False

    @api.onchange('dest_location_id')
    def onchange_dest_location_id(self):
        warning = {}
        if self.dest_location_id:
            if not self.picking_type_id:
                warning = {
                    'title': _('Warning'),
                    'message': _('Kindly select the picking type before selecting location.')}
                return {'warning': warning}
            if self.dest_location_id.id != self.picking_type_id.default_location_dest_id.id:
                self.dest_location_id = self.picking_type_id.default_location_dest_id and self.picking_type_id.default_location_dest_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Destination location cannot be changed.')}
        return {'warning': warning}


#########################################################################################

    # @api.multi
#     def move_to_start(self):
#         for each in self:
# #            for each_line in each.scrap_line:
# #                if each.uom_id != each_line.uom_id:
# #                    raise UserError(_('Warning! \nSF product uom and scrap product uom mismatch.\nKindly give the same uom for both SF product and scrap product'))
#             if each.order_type == 'normal':
#                 if each.product_qty <= 0.00:
#                     raise UserError(_('%s quantity must be greater than zero') % (each.product_id.name_get()[0][1]))
#                 if not each.materials_line:
#                     raise UserError(_('You must define raw materials to proceed further'))
#                 ####################COMMENTED FOR NOW###################
#
#                 if each.name == 'New #':
#                     if each.warehouse_id.sf_mo_sequence_id:
#                         each.name = each.warehouse_id.sf_mo_sequence_id.next_by_id()
#                     else:
#                         raise UserError(_('Semi finished MO sequence is not defined in warehouse (%s).Please contact your administrator') % (each.warehouse_id.name))
#
#
#
#                 ##########################################################
#                     #each.name = self.env['ir.sequence'].next_by_code('sf.manufacturing.order.code') or '#'
#                 each.action_check_stock()
#                 for line in each.materials_line:
#                     if line.quantity <= 0.00:
#                          raise UserError(_('%s quantity must be greater than zero') % (line.product_id.display_name))
#                     # if line.quantity > line.available_stock:
#                     #     raise UserError(_('%s entered quantity is greater than the available stock') % (line.product_id.display_name))
#                     line.state = 'inprogress'
#                 for each_line in each.scrap_line:
#                     if each_line.quantity <= 0.00:
#                          raise UserError(_('%s quantity must be greater than zero') % (each_line.product_id.display_name))
#                     each_line.state = 'inprogress'
#             else:
#                 if each.name == 'New #':
#                    each.name = self.env['ir.sequence'].next_by_code('sf.manufacturing.order.unbuild.code') or 'New #'
#                 for line in each.materials_line:
#                     line.state = 'inprogress'
#                 for each_line in each.scrap_line:
#                     each_line.state = 'inprogress'
#             each.state = 'inprogress'
#         return True



    def move_to_start(self):
        for each in self:
            #            for each_line in each.scrap_line:
            #                if each.uom_id != each_line.uom_id:
            #                    raise UserError(_('Warning! \nSF product uom and scrap product uom mismatch.\nKindly give the same uom for both SF product and scrap product'))
            if each.order_type == 'normal':
                if each.product_qty <= 0.00:
                    raise UserError(_('%s quantity must be greater than zero') % (each.product_id.name_get()[0][1]))
                if not each.materials_line:
                    raise UserError(_('You must define raw materials to proceed further'))
                if each.name == 'New #':
                    if each.warehouse_id.sf_mo_sequence_id:
                        each.name = each.warehouse_id.sf_mo_sequence_id.next_by_id()
                    else:
                        raise UserError(
                            _('Semi finished MO sequence is not defined in warehouse (%s).Please contact your administrator') % (
                                each.warehouse_id.name))
                    # each.name = self.env['ir.sequence'].next_by_code('sf.manufacturing.order.code') or '#'
                each.action_check_stock()
                for line in each.materials_line:
                    if line.quantity <= 0.00:
                        raise UserError(
                            _('%s quantity must be greater than zero') % (line.product_id.name_get()[0][1]))
                    if line.quantity > line.available_stock:
                        raise UserError(_('%s entered quantity is greater than the available stock') % (
                        line.product_id.name_get()[0][1]))
                    line.state = 'inprogress'
                for each_line in each.scrap_line:
                    if each_line.quantity <= 0.00:
                        raise UserError(
                            _('%s quantity must be greater than zero') % (each_line.product_id.name_get()[0][1]))
                    each_line.state = 'inprogress'
            else:
                if each.name == 'New #':
                    each.name = self.env['ir.sequence'].next_by_code(
                        'sf.manufacturing.order.unbuild.code') or 'New #'
                for line in each.materials_line:
                    line.state = 'inprogress'
                for each_line in each.scrap_line:
                    each_line.state = 'inprogress'
            each.state = 'inprogress'
        return True




#    @api.multi
#    def action_update_cost_price(self):
#        quant_obj = self.env['stock.quant']
#        for each in self:
#            price_unit, scrap_qty, total_qty = 0.00, 0.00, 0.00
##            for scrap_line in each.scrap_line:
##                scrap_qty += scrap_line.quantity and scrap_line.quantity or 0.00
#            total_qty = scrap_qty + each.product_qty
#            for move_line in each.materials_line:
#                if move_line.move_id.state == 'done':
#                    price_unit += (move_line.move_id.price_unit * move_line.move_id.product_uom_qty)
#            price_unit = (price_unit / total_qty)
#            for each_move in each.move_lines:
#                if each.product_id == each_move.product_id:
#                    each_move.price_unit = price_unit
#                    self._cr.execute("""SELECT quant_id FROM stock_quant_move_rel WHERE move_id = %s""", (each_move.id,))
#                    quant_ids = self._cr.fetchall()
#                    for quant_id in quant_ids:
#                        quant_bro = quant_obj.browse(quant_id[0])
#                        quant_bro.cost = price_unit
##            for move_line in each.scrap_line:
##                for each_scrap_move in each.move_lines:
##                    if move_line.product_id == each_scrap_move.product_id:
##                        each_scrap_move.price_unit = price_unit
##                        self._cr.execute("""SELECT quant_id FROM stock_quant_move_rel WHERE move_id = %s""", (each_scrap_move.id,))
##                        quant_ids = self._cr.fetchall()
##                        for quant_id in quant_ids:
##                            quant_bro = quant_obj.browse(quant_id[0])
##                            quant_bro.cost = price_unit
#        return True
        
        
        
    # @api.multi
    def move_to_complete(self):
        picking_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        picking = scrap_picking = False
        picking_id = scrap_picking_id = False
        for each in self:
            picking = scrap_picking = False
            picking_id = scrap_picking_id = False
#            for each_line in each.scrap_line:
#                if each.uom_id != each_line.uom_id:
#                    raise UserError(_('Warning! \nSF product uom and scrap product uom mismatch.\nKindly give the same uom for both SF product and scrap product'))
            for line in each.materials_line:
                if not picking:
                    picking_id = picking_obj.create({
                        'location_dest_id': line.dest_location_id and line.dest_location_id.id or False,
                        'location_id': line.source_location_id and line.source_location_id.id or False,
                        'origin': each.name and each.name or '',
                        'picking_type_id': each.picking_type_id and each.picking_type_id.id or False,
                        })
                    picking = True
                move_id = move_obj.create({
                    'company_id': each.company_id and each.company_id.id or False,
                    'product_id': line.product_id and line.product_id.id or False,
                    'product_uom': line.uom_id and line.uom_id.id or False,
                    'product_uom_qty': line.quantity and line.quantity or False,
                    'name': (line.product_id.display_name) + ' / ' +
                            (each.name and each.name or '') +
                            (each.order_type == 'unbuild_order' and  ' (' + each.source_doc + ') '  or '') or "",
                    'origin': each.name and each.name or '',
                    'location_id': line.source_location_id and line.source_location_id.id or False,
                    'location_dest_id': line.dest_location_id and line.dest_location_id.id or False,
                    'picking_id': picking_id.id,
                    'warehouse_id': each.warehouse_id and each.warehouse_id.id or False, 
                    'sf_raw_material_id': line.id,
                    'sf_manuf_id': each.id
                    })
                print('\n move id', move_id)
                line.state = 'completed'

                print('\n lineee-----', line.state)
                line.move_id = move_id
                print('\n lineee-----', line.move_id)
            if picking_id:
                print('\n picking id', picking_id)
                picking_id.action_confirm()
                picking_id.action_assign()
                # picking_id.force_assign()
                for picking_pack_line in picking_id.move_ids_without_package:
                    picking_pack_line.write({'product_packaging_quantity': picking_pack_line.product_qty})
                picking_id.button_validate()
                
            price_unit, scrap_qty, total_qty = 0.00, 0.00, 0.00
#            for scrap_line in each.scrap_line:
#                scrap_qty += scrap_line.quantity and scrap_line.quantity or 0.00
            total_qty = scrap_qty + each.product_qty
            for move_line in each.materials_line:
                if move_line.move_id.state == 'done':
                    price_unit += (move_line.move_id.price_unit * move_line.move_id.product_uom_qty)
            price_unit = (price_unit / total_qty)
                
            each_picking_id = picking_obj.create({
                'location_dest_id': each.dest_location_id and each.dest_location_id.id or False,
                'location_id': each.source_location_id and each.source_location_id.id or False,
                'origin': each.name and each.name or '',
                'picking_type_id': each.picking_type_id and each.picking_type_id.id or False,
                })
            move_obj.create({
                'company_id': each.company_id and each.company_id.id or False,
                'product_id': each.product_id and each.product_id.id or False,
                'product_uom': each.uom_id and each.uom_id.id or False,
                'product_uom_qty': each.product_qty and each.product_qty or False,
                'name': (each.product_id.display_name) + ' / ' +
                        (each.name and each.name or '') +  
                        (each.order_type == 'unbuild_order' and  ' (' + each.source_doc + ') '  or '') or "",
                'origin': each.name and each.name or '',
                'location_id': each.source_location_id and each.source_location_id.id or False,
                'location_dest_id': each.dest_location_id and each.dest_location_id.id or False,
                'picking_id': each_picking_id.id ,
                'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                'price_unit': price_unit,
                'sf_manuf_id': each.id
                })
            print('>>>>>>>>>>>>>>>>>>move obj>>>>>>>>>222222>>>>>', move_obj)
            each_picking_id.action_confirm()
            each_picking_id.action_assign()
            # each_picking_id.force_assign()
            for each_pack_line in each_picking_id.move_ids_without_package:
                each_pack_line.write({'product_packaging_quantity': each_pack_line.product_qty})
            each_picking_id.button_validate()
            
            for scrap_line in each.scrap_line:
                if not scrap_picking:
                    scrap_picking_id = picking_obj.create({
                        'location_dest_id': scrap_line.dest_location_id and scrap_line.dest_location_id.id or False,
                        'location_id': scrap_line.source_location_id and scrap_line.source_location_id.id or False,
                        'origin': each.name and each.name or '',
                        'picking_type_id': each.picking_type_id and each.picking_type_id.id or False,
                        })
                    scrap_picking = True
                scrap_move_id = move_obj.create({
                    'company_id': each.company_id and each.company_id.id or False,
                    'product_id': scrap_line.product_id and scrap_line.product_id.id or False,
                    'product_uom': scrap_line.uom_id and scrap_line.uom_id.id or False,
                    'product_uom_qty': scrap_line.quantity and scrap_line.quantity or 0.00,
                    'name': (scrap_line.product_id.name_get()[0][1]) + ' / ' + 
                            (each.name and each.name or '') +  
                            (each.order_type == 'unbuild_order' and  ' (' + each.source_doc + ') '  or '') or "",
                    'origin': each.name and each.name or '',
                    'location_id': scrap_line.source_location_id and scrap_line.source_location_id.id or False,
                    'location_dest_id': scrap_line.dest_location_id and scrap_line.dest_location_id.id or False,
                    'picking_id': scrap_picking_id.id ,
                    'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                    #'price_unit': price_unit,
                    'sf_manuf_id': each.id
                    })
                scrap_line.state = 'completed'
                scrap_line.move_id = scrap_move_id
            if scrap_picking_id:
                scrap_picking_id.action_confirm()
                scrap_picking_id.action_assign()
                # scrap_picking_id.force_assign()
                for pack_line in scrap_picking_id.move_ids_without_package:
                    pack_line.write({'product_packaging_quantity': pack_line.product_qty})
                scrap_picking_id.button_validate()
            
            each.update({
                'state': 'completed',
                'date_done': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'completed_user_id': self.env.user.id,
                })
        return True

    # @api.multi
    def action_check_stock(self):
        print('\n in action check stock')
        quant_obj = self.env['stock.quant']
        line_quantity = quantity = 0.00
        for each in self:
            line_quantity = quantity = 0.00
            quant_search = quant_obj.search_read([('product_id', '=', each.product_id.id),('location_id', '=', each.dest_location_id.id)],['inventory_quantity_auto_apply'])
            print('\n quant search', quant_search)
            print('\n quant search -----------', each.dest_location_id.id)
            for each_quant in quant_search:
                quantity += each_quant['inventory_quantity_auto_apply']
                print('\n quantity', quantity)
            each.available_stock = quantity
            for line in each.materials_line:
                line_quantity = 0.00
                line_quant_search = quant_obj.search_read([('product_id', '=', line.product_id.id), ('location_id', '=', line.source_location_id.id)],['inventory_quantity_auto_apply'])
                for line_quant in line_quant_search:
                    line_quantity += line_quant['inventory_quantity_auto_apply']
                line.available_stock = line_quantity  
        return True
################################################COMMENTED FOR NOW##################################################
    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        warning = {}
        if self.warehouse_id:
            if self.warehouse_id.sf_mo_picking_type_id:
                self.picking_type_id = self.warehouse_id.sf_mo_picking_type_id and self.warehouse_id.sf_mo_picking_type_id.id or False
            else:
                self.picking_type_id = False
                warning = {
                    'title': _('Warning'),
                    'message': _('The picking type of semi finished orders is not configured in  warehouse')}
        else:
            self.picking_type_id = False
        return {'warning': warning}

    @api.onchange('picking_type_id')
    def _onchange_picking_type_id(self):
        warning = {}
        if self.picking_type_id and self.warehouse_id:
            if self.picking_type_id.id != self.warehouse_id.sf_mo_picking_type_id.id:
                self.picking_type_id = self.warehouse_id.sf_mo_picking_type_id and self.warehouse_id.sf_mo_picking_type_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Picking type cannot be changed.This picking type is the default warehouse of the picking type that you have selected')}
        return {'warning': warning}

#############################################################################################
        
    # @api.multi
    def action_add_product(self):
        material_issue_obj = self.env['raw.materials.line']
        dict_issue = {}
        for each in self:
            if each.material_issue_ids:
                if each.materials_line:
                    for mat_issue_line in each.material_issue_ids:  
                        for issue_line in mat_issue_line.issue_lines:
                            if issue_line.product_id.id in dict_issue:
                                dict_issue[issue_line.product_id.id]['quantity'] += issue_line.issued_qty and issue_line.issued_qty or 0.00
                            else:
                                dict_issue[issue_line.product_id.id] = {}
                                dict_issue[issue_line.product_id.id] = {
                                    'product_id': issue_line.product_id and issue_line.product_id.id or False,
                                    'uom_id': issue_line.uom_id and issue_line.uom_id.id or False,
                                    'quantity': issue_line.issued_qty and issue_line.issued_qty or 0.00,
                                    'order_id': each.id,
                                    'source_location_id': each.picking_type_id.default_location_src_id and each.picking_type_id.default_location_src_id.id or False,
                                    'dest_location_id': issue_line.product_id.property_stock_production and issue_line.product_id.property_stock_production.id or False,
                                    'update_issue': True
                                } 
                    for line in each.materials_line:
                        if not line.update_issue: 
                            if line.product_id.id in dict_issue:
                                dict_issue[line.product_id.id]['quantity'] += line.quantity and line.quantity or 0.00 
                            else:
                                dict_issue[line.product_id.id] = {
                                    'product_id': line.product_id and line.product_id.id or False,
                                    'uom_id': line.uom_id and line.uom_id.id or False,
                                    'quantity': line.quantity and line.quantity or 0.00,
                                    'order_id': each.id,
                                    'source_location_id': each.picking_type_id.default_location_src_id and each.picking_type_id.default_location_src_id.id or False,
                                    'dest_location_id': line.product_id.property_stock_production and line.product_id.property_stock_production.id or False,
                                } 
                    models.Model.unlink(each.materials_line)
                    for dict_line in dict_issue:
                        material_issue_obj.create(dict_issue[dict_line])   
                else:
                    for mat_issue_line in each.material_issue_ids:
                        for issue_line in mat_issue_line.issue_lines:
                            if issue_line.product_id.id in dict_issue:
                                dict_issue[issue_line.product_id.id]['quantity'] += issue_line.issued_qty and issue_line.issued_qty or 0.00 
                            else:
                                dict_issue[issue_line.product_id.id] = {}
                                dict_issue[issue_line.product_id.id] = {
                                    'product_id': issue_line.product_id and issue_line.product_id.id or False,
                                    'uom_id': issue_line.uom_id and issue_line.uom_id.id or False,
                                    'quantity': issue_line.issued_qty and issue_line.issued_qty or 0.00,
                                    'order_id': each.id,
                                    'source_location_id': each.picking_type_id.default_location_src_id and each.picking_type_id.default_location_src_id.id or False,
                                    'dest_location_id': issue_line.product_id.property_stock_production and issue_line.product_id.property_stock_production.id or False,
                                    'update_issue': True
                                } 
                    for dict_line in dict_issue:
                        material_issue_obj.create(dict_issue[dict_line])  
        return True   
        
    # @api.multi
    def action_remove_line(self):
        for each in self:
            models.Model.unlink(each.materials_line)
        return True
           
    # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can remove a form which is only in the draft state.'))    
        return super(SfManufaturingOrder,self).unlink() 
        
    # @api.multi
    def action_move_to_unbuild_order(self):
        sf_manuf_obj = self.env['sf.manufacturing.order']
        sf_manuf_line_obj = self.env['raw.materials.line']
        sf_manu_scrap_obj = self.env['materials.scrap.line']
        for each in self:
            sf_manuf_id = sf_manuf_obj.create({
                'product_id': each.product_id and each.product_id.id or False,
                'uom_id': each.uom_id and each.uom_id.id or False,
                'product_qty': each.product_qty and each.product_qty or 0.00,
                'batch_number': each.batch_number and each.batch_number or '',
                'shift_type': each.shift_type and each.shift_type or '',
                'warehouse_id': each.warehouse_id and each.warehouse_id.id or False,
                'picking_type_id': each.picking_type_id and each.picking_type_id.id or False,
                'source_location_id': each.dest_location_id and each.dest_location_id.id or False,
                'dest_location_id': each.source_location_id and each.source_location_id.id or False,
                'remarks': each.remarks and each.remarks or '',
                'source_doc': each.name and each.name or '',
                'order_type': 'unbuild_order',
                'state': 'draft'
            })
            for mat_line in each.materials_line:
                 sf_manuf_line_obj.create({
                    'product_id': mat_line.product_id and mat_line.product_id.id or False,
                    'uom_id': mat_line.uom_id and mat_line.uom_id.id or False,
                    'quantity': mat_line.quantity and mat_line.quantity or 0.00,
                    'source_location_id': mat_line.dest_location_id and mat_line.dest_location_id.id or False,
                    'dest_location_id': mat_line.source_location_id and mat_line.source_location_id.id or False,
                    'warehouse_id': mat_line.warehouse_id and mat_line.warehouse_id.id or False,
                    'order_id': sf_manuf_id.id 
                 })
            for line in each.scrap_line:
                sf_manu_scrap_obj.create({
                    'product_id': line.product_id and line.product_id.id or False,
                    'uom_id': line.uom_id and line.uom_id.id or False,
                    'quantity': line.quantity and line.quantity or 0.00,
                    'source_location_id': line.dest_location_id and line.dest_location_id.id or False,
                    'dest_location_id': line.source_location_id and line.source_location_id.id or False,
                    'warehouse_id': line.warehouse_id and line.warehouse_id.id or False,
                    'order_id': sf_manuf_id.id 
                })
            each.unbuild_order = True
            each.unbuild_order_id = sf_manuf_id.id
        return True
        
    # @api.multi
    def action_open_unbuid_order_link(self):
        view = self.env.ref('ebits_custom_mrp.sf_manufacturing_order_unbuild_form')
        wiz = self.env['sf.manufacturing.order'].browse(self.unbuild_order_id.id)
        return {
            'name': _('Unbuild Orders'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'res_model': 'sf.manufacturing.order',
            'res_id': wiz.id,
        }
                
        
class RawMaterialsLine(models.Model):
    _name = "raw.materials.line"
    _description = "Raw materials"
    
    order_id = fields.Many2one('sf.manufacturing.order', string='SF Manufacturing order', ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True, domain=[('purchase_ok', '=', 'True')])
    quantity = fields.Float(string='Quantity', required=True, digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string='UOM', required=True)
    source_location_id = fields.Many2one('stock.location', string='Source Location')
    dest_location_id = fields.Many2one('stock.location', string='Destination Location')
    available_stock = fields.Float(string='Available Stock', digits='Product Unit of Measure')
    state = fields.Selection([('draft', 'Draft'), ('inprogress', 'Inprogress'), ('completed', 'Completed')], string='State', readonly=True, default='draft')
    company_id = fields.Many2one('res.company', 'string=Company', related="order_id.company_id", store=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', related="order_id.warehouse_id", store=True)
    move_id = fields.Many2one('stock.move', string='Move', readonly=True, copy=False)
    update_issue = fields.Boolean("Update", default=False)
    order_type = fields.Selection(related="order_id.order_type", string='Order Type', readonly=True)
    
    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
            self.dest_location_id = self.product_id.property_stock_production and self.product_id.property_stock_production.id or False
            self.source_location_id = self.order_id.picking_type_id.default_location_src_id and self.order_id.picking_type_id.default_location_src_id.id or False
        else:
            self.uom_id = False
            self.dest_location_id = False 
        
    @api.onchange('uom_id')
    def onchange_uom_id(self):
        warning = {}
        if self.product_id and self.uom_id:
            if self.uom_id.id != self.product_id.uom_id.id:
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed.')}
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
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.uom_id.name)}
                    return {'warning': warning}
        
    @api.onchange('source_location_id')
    def onchange_source_location_id(self):
        warning = {}
        if self.source_location_id and self.product_id:
            if self.source_location_id.id != self.order_id.picking_type_id.default_location_src_id.id:
                self.source_location_id = self.order_id.picking_type_id.default_location_src_id and self.order_id.picking_type_id.default_location_src_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Source location cannot be changed.')}
        return {'warning': warning}
        
    # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can remove an item which is only in the draft state.'))    
        return super(RawMaterialsLine,self).unlink() 

class MaterialsScrapLine(models.Model):
    _name = "materials.scrap.line"
    _description = "Production Scrap" 
    
    order_id = fields.Many2one('sf.manufacturing.order', string='SF Manufacturing order', ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', required=True, digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string='UOM', required=True)
    source_location_id = fields.Many2one('stock.location', string='Source Location', readonly=True)
    dest_location_id = fields.Many2one('stock.location', string='Destination Location')
    state = fields.Selection([('draft', 'Draft'), ('inprogress', 'Inprogress'), ('completed', 'Completed')], string='State', readonly=True, default='draft')
    company_id = fields.Many2one('res.company', 'Company', related="order_id.company_id", store=True)
    move_id = fields.Many2one('stock.move', string='Move', readonly=True, copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse/Branch', related="order_id.warehouse_id", store=True)
    
    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
            self.source_location_id = self.product_id.property_stock_production and self.product_id.property_stock_production.id or False
            self.dest_location_id = self.order_id.picking_type_id.default_location_dest_id and self.order_id.picking_type_id.default_location_dest_id.id or False
        else:
            self.uom_id = False
            self.dest_location_id = False
            self.source_location_id = False
        
    @api.onchange('uom_id')
    def onchange_uom_id(self):
        warning = {}
        if self.product_id and self.uom_id:
            if self.uom_id.id != self.product_id.uom_id.id:
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed.')}
        return {'warning': warning}
        
    # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can remove an item which is only in the draft state.'))    
        return super(MaterialsScrapLine,self).unlink() 
        
class StockMove(models.Model):
    _inherit = 'stock.move'
    
    sf_manuf_id = fields.Many2one('sf.manufacturing.order', string='SF Manufacturing Order')
    date_expected = fields.Datetime(
        'Expected Date', default=fields.Datetime.now, index=True, required=True,
        help="Scheduled date for the processing of this move")
