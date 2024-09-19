# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import json
import time
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _,Command
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import odoo.addons.decimal_precision as dp
from odoo.tools import float_compare
import logging

class MrpBom(models.Model):
    _inherit = 'mrp.bom'
    
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', copy=False)
    addl_warehouse_ids = fields.Many2many('stock.warehouse', string='Addl Warehouse/Branch', copy=False)
    is_by_product = fields.Boolean('By Product Available for this BOM ?', default=False, copy=False)
    equalent_weight = fields.Float('Total Equalent Weight of Quantity(in Kg)', copy=False, default=0.00, digits=(16, 4))
    
    @api.onchange('product_uom_id')
    def onchange_uom_id(self):
        warning = {}
        if self.product_uom_id and self.product_id:
            if self.product_uom_id.id != self.product_id.uom_id.id:
                self.product_uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed')}
        return {'warning': warning}
    
    @api.onchange('product_qty')
    def onchange_product_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            self.equalent_weight = self.product_qty
            if self.product_qty and (not self.product_uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.product_qty, 1)
                if decimal:
                    self.product_qty = 0.00
                    self.equalent_weight = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.product_uom_id.name)}
            return {'warning': warning}
                
class MrpBom(models.Model):
    _inherit = 'mrp.bom.line'
    
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', related='bom_id.warehouse_id', readonly=True, store=True, copy=False)
    product_qty = fields.Float('Product Quantity', default=1.0, digits=dp.get_precision('BOM Product Unit of Measure'), required=True)
    
    @api.onchange('product_uom_id')
    def onchange_uom_id(self):
        warning = {}
        if self.product_uom_id and self.product_id:
            if self.product_uom_id.id != self.product_id.uom_id.id:
                self.product_uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed')}
        return {'warning': warning}
    
    @api.onchange('product_qty')
    def onchange_product_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            if self.product_qty and (not self.product_uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.product_qty, 1)
                if decimal:
                    self.product_qty = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.product_uom_id.name)}
                    return {'warning': warning}
                    
class MrpSubProduct(models.Model):
    _inherit = 'mrp.bom.byproduct'

    product_qty = fields.Float(
        'Product Qty',
        default=1.0, digits=dp.get_precision('Product Unit of Measure'), required=True)
    product_uom_id = fields.Many2one('uom.uom', 'Unit of Measure', required=True)
    equalent_weight = fields.Float('Total Equalent Weight(in Kg) if product uom is Kg, enter the same qty', copy=False, default=0.00, required=True, digits=dp.get_precision('Product Unit of Measure'))

#    @api.onchange('product_uom_id')
#    def onchange_uom_id(self):
#        warning = {}
#        if self.product_uom_id and self.product_id:
#            if self.product_uom_id.id != self.product_id.uom_id.id:
#                self.product_uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
#                warning = {
#                    'title': _('Warning'),
#                    'message': _('Unit of Measure cannot be changed')}
#        return {'warning': warning}

    @api.onchange('product_qty')
    def onchange_product_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            self.equalent_weight = self.product_qty
            if self.product_qty and (not self.product_uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.product_qty, 1)
                if decimal:
                    self.product_qty = 0.00
                    self.equalent_weight = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.product_uom_id.name)}
                    return {'warning': warning}

class MrpProduction(models.Model):
    _inherit = "mrp.production"
    
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', related='picking_type_id.warehouse_id', readonly=True, store=True)
    force_closed = fields.Boolean(string='Force Close', readonly=True)
    # date_planned_start = fields.Datetime('Planned Start Date', copy=False, default=fields.Datetime.now, index=True, required=True,
    #     states={'confirmed': [('readonly', False)]}, oldname='date_planned')
    finished_product_ids = fields.One2many(
        'stock.move', 'move_product_id', 'Finished Products', readonly=False,
         store=True,
        domain=[('scrapped', '=', False)])
    shift_type = fields.Selection([('shift_1', 'Shift 1'), ('shift_2', 'Shift 2'), ('shift_3', 'Shift 3')],
                                  string="Shift", required=True,copy=False)

    product_cat_name = fields.Char(string="Product Category", related='product_id.categ_id.name', store=True)

    availability = fields.Selection([
        ('assigned', 'Available'),
        ('partially_available', 'Partially Available'),
        ('waiting', 'Waiting'),
        ('none', 'None')], string='Raw Material Availability',
        compute='_compute_availability', store=True)



    def write(self, vals):
        if 'move_byproduct_ids' in vals and 'move_finished_ids' not in vals:
            vals['move_finished_ids'] = vals.get('move_finished_ids', []) + vals['move_byproduct_ids']
            del vals['move_byproduct_ids']
        if 'bom_id' in vals and 'move_byproduct_ids' in vals and 'move_finished_ids' in vals:
            # If byproducts are given, they take precedence over move_finished for byproduts definition
            bom = self.env['mrp.bom'].browse(vals.get('bom_id'))
            bom_product = bom.product_id or bom.product_tmpl_id.product_variant_id
            joined_move_ids = vals.get('move_byproduct_ids', [])
            for move_finished in vals.get('move_finished_ids', []):
                # Remove CREATE lines from finished_ids as they do not reflect the form current state (nor the byproduct vals)
                if move_finished[0] == Command.CREATE and move_finished[2].get('product_id') != bom_product.id:
                    continue
                joined_move_ids.append(move_finished)
            vals['move_finished_ids'] = joined_move_ids
            del vals['move_byproduct_ids']
        if 'workorder_ids' in self:
            production_to_replan = self.filtered(lambda p: p.is_planned)
        for move_str in ('move_raw_ids', 'move_finished_ids'):
            if move_str not in vals or self.state in ['draft', 'cancel', 'done']:
                continue
            # When adding a move raw/finished, it should have the source location's `warehouse_id`.
            # Before, it was handle by an onchange, now it's forced if not already in vals.
            warehouse_id = self.location_src_id.warehouse_id.id
            if vals.get('location_src_id'):
                location_source = self.env['stock.location'].browse(vals.get('location_src_id'))
                warehouse_id = location_source.warehouse_id.id
            for move_vals in vals[move_str]:
                command, _id, field_values = move_vals
                if command == Command.CREATE and not field_values.get('warehouse_id', False):
                    field_values['warehouse_id'] = warehouse_id

        if vals.get('picking_type_id'):
            picking_type = self.env['stock.picking.type'].browse(vals.get('picking_type_id'))
            for production in self:
                if production.state == 'draft' and picking_type != production.picking_type_id:
                    production.name = picking_type.sequence_id.next_by_id()

        res = super(MrpProduction, self).write(vals)
        for rec in self:
            if rec.product_id == rec.move_finished_ids.product_id:
                rec.move_finished_ids.price_unit = rec.product_id.standard_price

            for line in rec.move_raw_ids:
                for m_line in rec.all_move_raw_ids:
                    if line.product_id == m_line.product_id:
                        m_line.price_unit = line.product_id.standard_price

        for production in self:
            if 'date_start' in vals and not self.env.context.get('force_date', False):
                if production.state in ['done', 'cancel']:
                    raise UserError(_('You cannot move a manufacturing order once it is cancelled or done.'))
                if production.is_planned:
                    production.button_unplan()
            if vals.get('date_start'):
                production.move_raw_ids.write({'date': production.date_start, 'date_deadline': production.date_start})
            if vals.get('date_finished'):
                production.move_finished_ids.write({'date': production.date_finished})
            if any(field in ['move_raw_ids', 'move_finished_ids', 'workorder_ids'] for field in vals) and production.state != 'draft':
                production.with_context(no_procurement=True)._autoconfirm_production()
                if production in production_to_replan:
                    production._plan_workorders()
            if production.state == 'done' and ('lot_producing_id' in vals or 'qty_producing' in vals):
                finished_move = production.move_finished_ids.filtered(
                    lambda move: move.product_id == production.product_id and move.state == 'done')
                finished_move_lines = finished_move.move_line_ids
                if 'lot_producing_id' in vals:
                    finished_move_lines.write({'lot_id': vals.get('lot_producing_id')})
                if 'qty_producing' in vals:
                    finished_move.quantity = vals.get('qty_producing')
                    if production.product_tracking == 'lot':
                        finished_move.move_line_ids.lot_id = production.lot_producing_id
            if self._has_workorders() and not production.workorder_ids.operation_id and vals.get('date_start') and not vals.get('date_finished'):
                new_date_start = fields.Datetime.to_datetime(vals.get('date_start'))
                if not production.date_finished or new_date_start >= production.date_finished:
                    production.date_finished = new_date_start + datetime.timedelta(hours=1)
        return res



    @api.model
    def create(self, values):
        print('>>>>>>>>>>>>>>>>>>>>create>>>>>>>>>>>>>>>>>>>>>>>')
        if not values.get('name', False) or values['name'] == _('New'):
            if values['picking_type_id']:
                picking = self.env['stock.picking.type'].sudo().browse(values['picking_type_id'])
                if picking.sudo().warehouse_id.mo_sequence_id:
                    values['name'] = picking.sudo().warehouse_id.mo_sequence_id.next_by_id() or _('New')
                else:
                    raise UserError(_('MO sequence is not defined in warehouse (%s).Please contact your administrator') % (picking.warehouse_id.name))

        production = super(MrpProduction, self).create(values)
        if production.product_id == production.move_finished_ids.product_id:
            production.move_finished_ids.price_unit = production.product_id.standard_price

        for line in production.move_raw_ids:
            for m_line in production.all_move_raw_ids:
                if line.product_id == m_line.product_id:
                    m_line.price_unit = line.product_id.standard_price


        return production

    @api.depends('move_raw_ids.state', 'workorder_ids.move_raw_ids',
                 'bom_id.ready_to_produce')
    def _compute_availability(self):
        for order in self:
            if not order.move_raw_ids:
                order.availability = 'none'
                continue
            if order.bom_id.ready_to_produce == 'all_available':
                order.availability = any(move.state not in ('assigned', 'done', 'cancel') for move in
                                         order.move_raw_ids) and 'waiting' or 'assigned'
            else:
                partial_list = [x.partially_available and x.state in ('waiting', 'confirmed', 'assigned') for x in
                                order.move_raw_ids]
                assigned_list = [x.state in ('assigned', 'done', 'cancel') for x in order.move_raw_ids]
                order.availability = (all(assigned_list) and 'assigned') or (
                            any(partial_list) and 'partially_available') or 'waiting'

    # def _create_update_move_finished(self):
    #     print('>>>>>>>>>>>>>>>_create_update_move_finished>>>>')
    #
    #
    #     """ This is a helper function to support complexity of onchange logic for MOs.
    #     It is important that the special *2Many commands used here remain as long as function
    #     is used within onchanges.
    #     """
    #     list_move_finished = []
    #     moves_finished_values = self._get_moves_finished_values()
    #     moves_byproduct_dict = {move.byproduct_id.id: move for move in self.move_finished_ids.filtered(lambda m: m.byproduct_id)}
    #     move_finished = self.move_finished_ids.filtered(lambda m: m.product_id == self.product_id)
    #     for move_finished_values in moves_finished_values:
    #         if move_finished_values.get('byproduct_id') in moves_byproduct_dict:
    #             # update existing entries
    #             list_move_finished += [Command.update(moves_byproduct_dict[move_finished_values['byproduct_id']].id, move_finished_values)]
    #         elif move_finished_values.get('product_id') == self.product_id.id and move_finished:
    #             list_move_finished += [Command.update(move_finished.id, move_finished_values)]
    #         else:
    #             # add new entries
    #             list_move_finished += [Command.create(move_finished_values)]
    #     print('>>>>>>>>>>list_move_finished>>>>>>>>',list_move_finished)
    #     # self.move_finished_ids = list_move_finished
    #     self.finished_product_ids = list_move_finished

    def button_mark_done(self):
        res = self.pre_button_mark_done()
        if not self.shift_type:
            raise UserError(_('Shift is not defined for the production.'))

        if res is not True:
            return res

        if self.env.context.get('mo_ids_to_backorder'):
            productions_to_backorder = self.browse(self.env.context['mo_ids_to_backorder'])
            productions_not_to_backorder = self - productions_to_backorder
        else:
            productions_not_to_backorder = self
            productions_to_backorder = self.env['mrp.production']

        self.workorder_ids.button_finish()
        if self.show_produce_all:
            produce_all_data = self.move_finished_ids
            produce_all_data_dict = {
                'product_id': (produce_all_data.product_id.id),
                'product_uom_qty': produce_all_data.product_uom_qty,
                'data': produce_all_data.product_uom_qty,
                'quantity': produce_all_data.quantity,
                'product_uom': produce_all_data.product_uom.id,
                'location_id': produce_all_data.location_id.id,
                'location_dest_id': produce_all_data.location_dest_id.id,
                'name': produce_all_data.name,
                'shift_type': self.shift_type,
                'date_finished': self.date_finished
            }
            self.finished_product_ids.sudo().create({
                'product_id': produce_all_data_dict['product_id'],
                'product_uom_qty': produce_all_data_dict['product_uom_qty'],
                'quantity': produce_all_data_dict['quantity'],
                'product_uom': produce_all_data_dict['product_uom'],
                'move_product_id': self.id,
                'location_id': produce_all_data_dict['location_id'],
                'location_dest_id': produce_all_data_dict['location_dest_id'],
                'name': produce_all_data_dict['name'],
                'shift_type': produce_all_data_dict['shift_type'],
                'state': 'done',
                'date_deadline': produce_all_data_dict['date_finished']
            })
            delete_record = self.finished_product_ids.sudo().search([('move_product_id','=',self.id),('state','=','confirmed')])
            print("\n...........delete_record......",delete_record)
            delete_record.unlink()


        backorders = productions_to_backorder and productions_to_backorder._split_productions()
        backorders = backorders - productions_to_backorder

        productions_not_to_backorder._post_inventory(cancel_backorder=True)
        productions_to_backorder._post_inventory(cancel_backorder=True)

        # if completed products make other confirmed/partially_available moves available, assign them
        done_move_finished_ids = (
                    productions_to_backorder.move_finished_ids | productions_not_to_backorder.move_finished_ids).filtered(
            lambda m: m.state == 'done')
        done_move_finished_ids._trigger_assign()

        # Moves without quantity done are not posted => set them as done instead of canceling. In
        # case the user edits the MO later on and sets some consumed quantity on those, we do not
        # want the move lines to be canceled.
        (productions_not_to_backorder.move_raw_ids | productions_not_to_backorder.move_finished_ids).filtered(
            lambda x: x.state not in ('done', 'cancel')).write({
            'state': 'done',
            'product_uom_qty': 0.0,
        })
        for production in self:
            production.write({
                'date_finished': fields.Datetime.now(),
                'priority': '0',
                'is_locked': True,
                'state': 'done',
            })

        report_actions = self._get_autoprint_done_report_actions()
        if self.env.context.get('skip_redirection'):
            if report_actions:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'do_multi_print',
                    'context': {},
                    'params': {
                        'reports': report_actions,
                    }
                }
            return True
        another_action = False
        if not backorders:
            if self.env.context.get('from_workorder'):
                another_action = {
                    'type': 'ir.actions.act_window',
                    'res_model': 'mrp.production',
                    'views': [[self.env.ref('mrp.mrp_production_form_view').id, 'form']],
                    'res_id': self.id,
                    'target': 'main',
                }
            elif self.user_has_groups('mrp.group_mrp_reception_report'):
                mos_to_show = self.filtered(lambda mo: mo.picking_type_id.auto_show_reception_report)
                lines = mos_to_show.move_finished_ids.filtered(lambda
                                                                   m: m.product_id.type == 'product' and m.state != 'cancel' and m.picked and not m.move_dest_ids)
                if lines:
                    if any(mo.show_allocation for mo in mos_to_show):
                        another_action = mos_to_show.action_view_reception_report()
            if report_actions:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'do_multi_print',
                    'params': {
                        'reports': report_actions,
                        'anotherAction': another_action,
                    }
                }
            if another_action:
                return another_action
            return True
        context = self.env.context.copy()
        context = {k: v for k, v in context.items() if not k.startswith('default_')}
        for k, v in context.items():
            if k.startswith('skip_'):
                context[k] = False
        another_action = {
            'res_model': 'mrp.production',
            'type': 'ir.actions.act_window',
            'context': dict(context, mo_ids_to_backorder=None)
        }
        if len(backorders) == 1:
            another_action.update({
                'views': [[False, 'form']],
                'view_mode': 'form',
                'res_id': backorders[0].id,
            })
        else:
            another_action.update({
                'name': _("Backorder MO"),
                'domain': [('id', 'in', backorders.ids)],
                'views': [[False, 'list'], [False, 'form']],
                'view_mode': 'tree,form',
            })
        if report_actions:
            return {
                'type': 'ir.actions.client',
                'tag': 'do_multi_print',
                'params': {
                    'reports': report_actions,
                    'anotherAction': another_action,
                }
            }
        return another_action

    def button_unbuild(self):
        self.ensure_one()
        return {
            'name': _('Unbuild: %s', self.product_id.display_name),
            'view_mode': 'form',
            'res_model': 'mrp.unbuild',
            'view_id': self.env.ref('mrp.mrp_unbuild_form_view_simplified').id,
            'type': 'ir.actions.act_window',
            'context': {'default_product_id': self.product_id.id,
                        'default_lot_id': self.lot_producing_id.id,
                        'default_mo_id': self.id,
                        'default_company_id': self.company_id.id,
                        'default_location_id': self.location_dest_id.id,
                        'default_location_dest_id': self.location_src_id.id,
                        'default_warehouse_id': self.warehouse_id.id,
                        'create': False, 'edit': False},
            'target': 'new',
        }


    @api.onchange('product_uom_id')
    def onchange_uom_id(self):
        warning = {}
        if self.product_id and self.product_uom_id:
            if self.product_uom_id.id != self.product_id.uom_id.id:
                self.product_uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed')}
        return {'warning': warning}


        
    @api.onchange('product_qty')
    def onchange_product_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            if self.product_qty and (not self.product_uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.product_qty, 1)
                if decimal:
                    self.product_qty = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.product_uom_id.name)}
                    return {'warning': warning}
        
    @api.onchange('picking_type_id')
    def onchange_picking_type_id(self):
        if self.picking_type_id:
            self.warehouse_id = self.picking_type_id.warehouse_id and self.picking_type_id.warehouse_id.id or False
            
    def _generate_raw_move(self, bom_line, line_data):
        print('>>>>>>>>>>>>>>>>>>>>_generate_raw_move>>>>>>>>>>>>>>>>>>>>>>>')
        quantity = line_data['qty']
        # alt_op needed for the case when you explode phantom bom and all the lines will be consumed in the operation given by the parent bom line
        alt_op = line_data['parent_line'] and line_data['parent_line'].operation_id.id or False
        if bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom':
            return self.env['stock.move']
        if bom_line.product_id.type not in ['product', 'consu']:
            return self.env['stock.move']
        if self.bom_id.routing_id and self.bom_id.routing_id.location_id:
            source_location = self.bom_id.routing_id.location_id
        else:
            source_location = self.location_src_id
        original_quantity = self.product_qty - self.qty_produced
        data = {
            'name': bom_line.product_id.name_get()[0][1] + ' / ' + self.name,
            'date': self.date_planned_start,
            'bom_line_id': bom_line.id,
            'product_id': bom_line.product_id.id,
            'product_uom_qty': quantity,
            'product_uom': bom_line.product_uom_id.id,
            'location_id': source_location.id,
            'location_dest_id': self.product_id.property_stock_production.id,
            'raw_material_production_id': self.id,
            'company_id': self.company_id.id,
            'operation_id': bom_line.operation_id.id or alt_op,
            #'price_unit': bom_line.product_id.standard_price,
            'procure_method': 'make_to_stock',
            'origin': self.name,
            'warehouse_id': source_location.get_warehouse().id,
            'group_id': self.procurement_group_id.id,
            'propagate': self.propagate,
            'unit_factor': quantity / original_quantity,
            'warehouse_id': self.warehouse_id.id,
        }
        return self.env['stock.move'].create(data)
        
    def _generate_finished_moves(self):
        print('\n ================================in generate finished moves===========================')
        move = self.env['stock.move'].create({
            'name': self.product_id.name_get()[0][1] + ' / ' + self.name,
            'date': self.date_planned_start,
            'date_expected': self.date_planned_start,
            'product_id': self.product_id.id,
            'product_uom': self.product_uom_id.id,
            'product_uom_qty': self.product_qty,
            'location_id': self.product_id.property_stock_production.id,
            'location_dest_id': self.location_dest_id.id,
            'move_dest_id': self.procurement_ids and self.procurement_ids[0].move_dest_id.id or False,
            'procurement_id': self.procurement_ids and self.procurement_ids[0].id or False,
            'company_id': self.company_id.id,
            'production_id': self.id,
            'origin': self.name,
            'group_id': self.procurement_group_id.id,
            'warehouse_id': self.warehouse_id.id,
            #'price_unit': price_unit,
        })
        move.action_confirm()
        return move
        
    def _create_byproduct_move(self, sub_product):
        print('=========>>>>>>>>>>>>>>>_create_byproduct_move>>>>>>>>>>>>>>>>>>>>====================')
        Move = self.env['stock.move']
        for production in self:
            source = production.product_id.property_stock_production.id
            product_uom_factor = production.product_uom_id._compute_quantity(production.product_qty - production.qty_produced, production.bom_id.product_uom_id)
            qty1 = sub_product.product_qty
            qty1 *= product_uom_factor / production.bom_id.product_qty
            data = {
                'name': sub_product.product_id.name_get()[0][1] + ' / ' + production.name,
                'date': production.date_planned_start,
                'product_id': sub_product.product_id.id,
                'product_uom_qty': qty1,
                'product_uom': sub_product.product_uom_id.id,
                'location_id': source,
                'location_dest_id': production.location_dest_id.id,
                'operation_id': sub_product.operation_id.id,
                'production_id': production.id,
                'origin': production.name,
                'unit_factor': qty1 / (production.product_qty - production.qty_produced),
                'subproduct_id': sub_product.id
            }
            move = Move.create(data)
            move.action_confirm()
        
    # @api.multi
    def action_force_closed(self):
        if any(workorder.state == 'progress' for workorder in self.mapped('workorder_ids')):
            raise UserError(_('You can not cancel production order, a work order is still in progress.'))
        # ProcurementOrder = self.env['procurement.order']
        for production in self:
            post_visible = any(production.move_raw_ids.filtered(lambda x: (x.quantity) > 0 and (x.state not in ['done', 'cancel'])))

            # if post_visible:
            #     raise UserError(_('Cannot force close when post inventory is not completed'))
        
            production.workorder_ids.filtered(lambda x: x.state != 'cancel').action_cancel()

            finish_moves = production.move_finished_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            production.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel'))._action_cancel()
            finish_moves._action_cancel()
            for rec in production.finished_product_ids:
                if rec.state == 'confirmed':
                    rec.state = 'cancel'
                if rec.state == 'assigned':
                    rec.state = 'cancel'


            # procurements = ProcurementOrder.search([('move_dest_id', 'in', finish_moves.ids)])
            # if procurements:
            #     procurements.cancel()

        # Put relatfinish_to_canceled procurements in exception -> I agree
        # ProcurementOrder.search([('production_id', 'in', self.ids)]).write({'state': 'exception'})
        self.write({'state': 'done', 'force_closed': True})
        return True

    def action_confirm(self):
        res = super(MrpProduction,self).action_confirm()
        finished_moves_to_confirm = set()
        for production in self:
            finished_moves_to_confirm.update((production.move_raw_ids | production.finished_product_ids).ids)

        f_moves_to_confirm = self.env['stock.move'].browse(sorted(finished_moves_to_confirm))
        f_moves_to_confirm._action_confirm(merge=False)

        return res


        
    # @api.multi
    def _generate_moves(self):
        print('\n ================================in generate moves===========================')
        for production in self:
            factor = production.product_uom_id._compute_quantity(production.product_qty, production.bom_id.product_uom_id) / production.bom_id.product_qty
            boms, lines = production.bom_id.explode(production.product_id, factor, picking_type=production.bom_id.picking_type_id)
            production._generate_raw_moves(lines)
            production._generate_finished_moves()
            # Check for all draft moves whether they are mto or not
            production._adjust_procure_method()
            production.move_raw_ids.action_confirm()
        for sub_production in self.filtered(lambda sub_production: sub_production.bom_id):
            for sub_product in sub_production.bom_id.byproduct_ids:
                sub_production._create_byproduct_move(sub_product)
        return True
        
    def _cal_price(self, consumed_moves):
        product_equalent_dict = {}
        bom_obj = self.env['mrp.bom']
        self.ensure_one()
        price_value, price_unit, product_qty = 0.000000, 0.000000, 0.000000
        bom_bro = bom_obj.search([('product_id', '=', self.product_id.id)])
        for each_consumed in consumed_moves:
            price_value += (each_consumed.price_unit * each_consumed.product_uom_qty)
        moves_to_finish = self.move_finished_ids.filtered(lambda x: x.state not in ('done','cancel'))
        if bom_bro.is_by_product:
            product_equalent_dict[bom_bro.product_id.id] = bom_bro.equalent_weight / bom_bro.product_qty
            for sub_products in bom_bro.byproduct_ids:
                product_equalent_dict[sub_products.product_id.id] = sub_products.equalent_weight / sub_products.product_qty
            for each_finish in moves_to_finish:
                if each_finish.product_id.id in product_equalent_dict:
                    product_qty += each_finish.quantity * (product_equalent_dict[each_finish.product_id.id] and product_equalent_dict[each_finish.product_id.id] or 1)
                else:
                    product_qty += each_finish.quantity
            if product_qty:
                price_unit = price_value / product_qty
            if price_unit:
                for each_move_finish in moves_to_finish:
                    if each_move_finish.product_id.id in product_equalent_dict:
                        each_move_finish.price_unit = (price_unit * (each_move_finish.quantity * (product_equalent_dict[each_move_finish.product_id.id] and product_equalent_dict[each_move_finish.product_id.id] or 1)) )/ (each_move_finish.quantity)
                    else:
                        each_move_finish.price_unit = price_unit
        else:
            for each_finish in moves_to_finish:
                product_qty += each_finish.quantity
            if product_qty:
                price_unit = price_value / product_qty
            if price_unit:
                for each_move_finish in moves_to_finish:
                    each_move_finish.price_unit = price_unit
        return True
        
    # # @api.multi
    # def button_scrap(self):
    #     self.ensure_one()
    #     return {
    #         'name': _('Scrap'),
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_model': 'stock.scrap',
    #         'view_id': self.env.ref('stock.stock_scrap_form_view2').id,
    #         'type': 'ir.actions.act_window',
    #         'context': {'default_production_id': self.id,
    #                     'product_ids': (self.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel')) | self.move_finished_ids.filtered(lambda x: x.state == 'done')).mapped('product_id').ids,
    #                     'default_warehouse_id': self.warehouse_id.id,
    #                     },
    #         'target': 'new',
    #     }
        
class MrpUnbuild(models.Model):
    _inherit = "mrp.unbuild"
    
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', copy=False, )
    location_id = fields.Many2one(
        'stock.location', 'Location',
        required=True,)
    location_dest_id = fields.Many2one(
        'stock.location', 'Destination Location',
        required=True, )
        
    # @api.multi
    def unlink(self):
        for unbuild in self:
            if unbuild.state != 'draft':
                raise UserError(_('Cannot delete a form not in draft state'))
        return super(MrpUnbuild, self).unlink()

    def action_validate(self):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        available_qty = self.env['stock.quant']._get_available_quantity(self.product_id, self.location_id, self.lot_id, strict=True)
        unbuild_qty = self.product_uom_id._compute_quantity(self.product_qty, self.product_id.uom_id)
        if float_compare(available_qty, unbuild_qty, precision_digits=precision) >= 0:
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>unbuild_qty',unbuild_qty)
            return self.action_unbuild()

        else:
            print('>>>>>>>>>>>elseeeeee>>>>>>>>>>>>>>>>>unbuild_qty',unbuild_qty)
            return {
                'name': self.product_id.display_name + _(': Insufficient Quantity To Unbuild'),
                'view_mode': 'form',
                'res_model': 'stock.warn.insufficient.qty.unbuild',
                'view_id': self.env.ref('mrp.stock_warn_insufficient_qty_unbuild_form_view').id,
                'type': 'ir.actions.act_window',
                'context': {
                    'default_product_id': self.product_id.id,
                    'default_location_id': self.location_id.id,
                    'default_unbuild_id': self.id,
                    'default_quantity': unbuild_qty,
                    'default_product_uom_name': self.product_id.uom_name,
                },
                'target': 'new',
            }

    # def _generate_consume_moves(self):
    #     move = super(MrpUnbuild, self)._generate_consume_moves()
    #     for each in move:
    #         each.name = each.consume_unbuild_id.product_id.name_get()[0][1] + " / " + each.consume_unbuild_id.name + " ( " + each.consume_unbuild_id.mo_id.name + " )"
    #     return move
    #
    # def _generate_move_from_bom_line(self, bom_line, quantity):
    #     move = super(MrpUnbuild, self)._generate_move_from_bom_line(bom_line, quantity)
    #     for each in move:
    #         each.name = bom_line.product_id.name_get()[0][1] + " / " + each.unbuild_id.name + " ( " + each.unbuild_id.mo_id.name + " )"
    #     return move
    #
    # @api.onchange('mo_id')
    # def onchange_mo_id(self):
    #     unbuild_qty = 0.00
    #     warning = {}
    #     if self.mo_id:
    #         self.product_id = self.mo_id.product_id.id
    #         unbuild_order = self.search([('mo_id', '=', self.mo_id.id),('id', '!=', self._origin.id)])
    #         if unbuild_order:
    #             for each in unbuild_order:
    #                 unbuild_qty += each.product_qty
    #         if self.mo_id.force_closed:
    #             main_product_moves = self.mo_id.move_finished_ids.filtered(lambda x: x.product_id.id == self.mo_id.product_id.id and x.state == 'done')
    #             if not (sum(main_product_moves.mapped('quantity_done')) - unbuild_qty):
    #                 warning = {
    #                     'title': _('Warning'),
    #                     'message': _("There is no qty left to do unbuild order against this MO '%s'") % (self.mo_id.name),
    #                     }
    #                 self.product_qty = 0.00
    #             else:
    #                 self.product_qty = (sum(main_product_moves.mapped('quantity_done')) - unbuild_qty)
    #         else:
    #             if not (self.mo_id.product_qty - unbuild_qty):
    #                 warning = {
    #                     'title': _('Warning'),
    #                     'message': _("There is no qty left to do unbuild order against this MO '%s'") % (self.mo_id.name),
    #                     }
    #                 self.product_qty = 0.00
    #             else:
    #                 self.product_qty = (self.mo_id.product_qty - unbuild_qty)
    #     return {'warning': warning}
    #
    # @api.onchange('warehouse_id')
    # def onchange_warehouse_id(self):
    #     warning = {}
    #     if self.warehouse_id:
    #         self.location_id = self.warehouse_id.lot_stock_id
    #         self.location_dest_id = self.warehouse_id.lot_stock_id
    #     else:
    #         self.location_id = False
    #         self.location_dest_id = False
    #
    # @api.onchange('location_id')
    # def onchange_location_id(self):
    #     warning = {}
    #     if self.location_id:
    #         if self.warehouse_id.lot_stock_id != self.location_id:
    #             self.location_id = False
    #             warning = {
    #                 'title': _('Warning'),
    #                 'message': _('Location cannot be changed')}
    #     return {'warning': warning}
    #
    # @api.onchange('location_dest_id')
    # def onchange_location_dest_id(self):
    #     warning = {}
    #     if self.location_dest_id:
    #         if self.warehouse_id.lot_stock_id != self.location_dest_id:
    #             self.location_dest_id = False
    #             warning = {
    #                 'title': _('Warning'),
    #                 'message': _('Location cannot be changed')}
    #     return {'warning': warning}
    #
    # @api.onchange('product_qty', 'mo_id')
    # def onchange_product_qty(self):
    #     warning = {}
    #     integer, decimal = 0.00, 0.00
    #     product_qty, unbuild_qty = 0.00, 0.00
    #     if self.product_qty:
    #         if self.mo_id:
    #             main_product_moves = self.mo_id.move_finished_ids.filtered(lambda x: x.product_id.id == self.mo_id.product_id.id and x.state == 'done')
    #             print('\n main product moves', main_product_moves)
    #             product_qty = sum(main_product_moves.mapped('quantity'))
    #             unbuild_order = self.search([('mo_id', '=', self.mo_id.id),('id', '!=', self._origin.id)])
    #             if unbuild_order:
    #                 for each in unbuild_order:
    #                     unbuild_qty += each.product_qty
    #             if self.product_qty > (product_qty - unbuild_qty):
    #                 self.product_qty = 0.00
    #                 warning = {
    #                     'title': _('Warning'),
    #                     'message': _("Unbuild qty must be lesser/equal to total generated MO qty.\n Selected MO's qty is '%s' and total unbuilt qty is '%s'") % ((product_qty, unbuild_qty))
    #                     }
    #         else:
    #             if not self.product_uom_id.allow_decimal_digits:
    #                 integer, decimal = divmod(self.product_qty, 1)
    #                 if decimal:
    #                     self.product_qty = 0.00
    #                     warning = {
    #                         'title': _('Warning'),
    #                         'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.product_uom_id.name)}
    #     return {'warning': warning}
    #
    # @api.onchange('product_uom_id')
    # def onchange_product_uom_id(self):
    #     warning = {}
    #     if self.product_id and self.product_uom_id:
    #         if self.product_uom_id.id != self.product_id.uom_id.id:
    #             self.product_uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
    #             warning = {
    #                 'title': _('Warning'),
    #                 'message': _('Unit of Measure cannot be changed')}
    #     return {'warning': warning}
        
        
class StockScrap(models.Model):
    _inherit = 'stock.scrap'
            
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', copy=False)
    location_id = fields.Many2one(
        'stock.location', 'Location', domain="[('usage', '=', 'internal')]",
        required=True,)
        
    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        warning = {}
        if self.warehouse_id:
            self.location_id = self.warehouse_id.lot_stock_id
        else:
            self.location_id = False
            
    @api.onchange('location_id')
    def onchange_location_id(self):
        warning = {}
        if self.location_id:
            if self.warehouse_id.lot_stock_id != self.location_id:
                self.location_id = False
                warning = {
                    'title': _('Warning'),
                    'message': _('Location cannot be changed')}
        return {'warning': warning}
