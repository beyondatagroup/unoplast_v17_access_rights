# -*- encoding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2004-2014 OpenERP S.A. (<http://odoo.com>).
#
##############################################################################
import time

from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError
from datetime import datetime
import pytz

class InterTransferRequestMerge(models.TransientModel):
    _name = 'inter.transfer.request.merge'
    _description = 'Inter transfer Request Merge Wizard'
    
    date_requested = fields.Date(string='Requested Date', required=True, default=fields.Date.context_today, copy=False)
    date_required = fields.Date(string='Required Date', required=True, copy=False)
    requester = fields.Char(string='Requester', required=True, copy=False)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        warehouse_master_id = []
        requesting_warehouse_id = []
        required_location_id = []
        res = super(InterTransferRequestMerge, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.env.context.get('active_model','') == 'internal.stock.transfer.request' and len(self.env.context['active_ids']) < 2:
            raise UserError(_('Please select multiple request to merge in the list view.'))
        for each in self.env['internal.stock.transfer.request'].browse(self.env.context['active_ids']):
            if each.state != 'draft':
                raise UserError(_('You can merge only draft requests.\nKindly uncheck the other status request'))
            warehouse_master_id.append(each.warehouse_master_id.id)
            requesting_warehouse_id.append(each.requesting_warehouse_id.id)
            required_location_id.append(each.required_location_id.id)
        if list(set(warehouse_master_id)) != warehouse_master_id:
            raise UserError(_('You can merge only same issuing warehouse request.\nKindly uncheck the other issuing warehouse request'))
        if list(set(requesting_warehouse_id)) != requesting_warehouse_id:
            raise UserError(_('You can merge only same requesting warehouse request.\nKindly uncheck the other requesting warehouse request'))
        if list(set(required_location_id)) != required_location_id:
            raise UserError(_('You can merge only same required location request.\nKindly uncheck the other required location request'))
        return res
    
    @api.multi
    def action_merge(self):
        request_obj = self.env['internal.stock.transfer.request']
        request_line_obj = self.env['internal.stock.transfer.request.line']
        new_orders = {}

        order_lines_to_move = {}
        for porder in [order for order in request_obj.browse(self.env.context['active_ids']) if order.state == 'draft']:
            order_key = make_key(porder, ('warehouse_master_id', 'requesting_warehouse_id', 'required_location_id'))
            new_order = new_orders.setdefault(order_key, ({}, []))
            new_order[1].append(porder.id)
            order_infos = new_order[0]
            order_lines_to_move.setdefault(order_key, [])

            if not order_infos:
                order_infos.update({
                    'warehouse_master_id': porder.warehouse_master_id.id,
                    'requesting_warehouse_id': porder.requesting_warehouse_id.id,
                    'required_location_id': porder.required_location_id.id,
                    'name': 'STR #',
                    'date_requested': self.date_requested,
                    'date_required': self.date_required,
                    'user_id': self.env.user.id,
                    'requester': self.requester,
                    'state': 'draft',
                    'request_lines': {},
                })

            order_lines_to_move[order_key] += [request_lines.id for request_lines in porder.request_lines
                                               if request_lines.state != 'cancel']
        
        allorders = []
        orders_info = {}
        for order_key, (order_data, old_ids) in new_orders.iteritems():
            # skip merges with only one order
            if len(old_ids) < 2:
                allorders += (old_ids or [])
                continue

            # cleanup order line data
            for key, value in order_data['request_lines'].iteritems():
                del value['uom_factor']
                value.update(dict(key))
            order_data['request_lines'] = [(6, 0, order_lines_to_move[order_key])]

            # create the new order
            neworder_id = request_obj.create(order_data)
            orders_info.update({neworder_id: old_ids})
            allorders.append(neworder_id)

            # make triggers pointing to the old orders point to the new order
            for old_id in old_ids:
                request_obj.browse(old_id).write({'state': 'state'})
        return True
        
InterTransferRequestMerge()
        
