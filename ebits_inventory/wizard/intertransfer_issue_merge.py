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
from openerp.osv.orm import browse_record, browse_null
from odoo.exceptions import UserError
from datetime import datetime
import pytz


class InterTransferIssueMerge(models.TransientModel):
    _name = 'inter.transfer.issue.merge'
    _description = 'Inter Transfer Issue Merge Wizard'
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        warehouse_master_id = []
        issuing_warehouse_id = []
        issuing_location_id = []
        requesting_location_id = []
        res = super(InterTransferIssueMerge, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.env.context.get('active_model','') == 'internal.stock.transfer.issue' and len(self.env.context['active_ids']) < 2:
            raise UserError(_('Please select multiple issues to merge in the list view.'))
        for each in self.env['internal.stock.transfer.issue'].browse(self.env.context['active_ids']):
            if each.state != 'draft':
                raise UserError(_('You can merge only draft issue.\nKindly uncheck the other status of issues'))
            warehouse_master_id.append(each.warehouse_master_id.id)
            issuing_warehouse_id.append(each.issuing_warehouse_id.id)
            issuing_location_id.append(each.issuing_location_id.id)
            requesting_location_id.append(each.requesting_location_id.id)
        warehouse_master_id = list(set(warehouse_master_id))
        issuing_warehouse_id = list(set(issuing_warehouse_id)) 
        issuing_location_id = list(set(issuing_location_id)) 
        requesting_location_id = list(set(requesting_location_id)) 
        
        if len(warehouse_master_id) > 1:
            raise UserError(_('You can merge only same requesting warehouse issue.\nKindly uncheck the other requesting warehouse issue'))
        if len(issuing_warehouse_id) > 1:
            raise UserError(_('You can merge only same issuing warehouse issue.\nKindly uncheck the other issuing warehouse issue'))
        if len(issuing_location_id) > 1:
            raise UserError(_('You can merge only same issuing location issue.\nKindly uncheck the other issuing location issue'))
        if len(requesting_location_id) > 1:
            raise UserError(_('You can merge only same requesting location issue.\nKindly uncheck the other requesting location issue'))
        return res
    
    @api.multi
    def action_merge(self):
        issue_obj = self.env['internal.stock.transfer.issue']
        issue_line_obj = self.env['internal.stock.transfer.issue.line']
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        ctx = dict(self.env.context or {})
        def make_key(br, fields):
            list_key = []
            for field in fields:
                field_val = getattr(br, field)
                if field in ('product_id', 'location_id', 'warehouse_master_id', 'issuing_warehouse_id', 'requesting_location_id', 'issuing_location_id'):
                    if not field_val:
                        field_val = False
                if isinstance(field_val, browse_record):
                    field_val = field_val.id
                elif isinstance(field_val, browse_null):
                    field_val = False
                elif isinstance(field_val, list):
                    field_val = ((6, 0, tuple([v.id for v in field_val])),)
                list_key.append((field, field_val))
            list_key.sort()
            return tuple(list_key)
        
        new_orders = {}
        order_lines_to_move = {}
        for porder in [order for order in issue_obj.browse(self.env.context['active_ids']) if order.state == 'draft']:
            order_key = make_key(porder, ('warehouse_master_id', 'issuing_warehouse_id', 'requesting_location_id', 'issuing_location_id'))
            new_order = new_orders.setdefault(order_key, ({}, []))
            new_order[1].append(porder.id)
            order_infos = new_order[0]
            order_lines_to_move.setdefault(order_key, [])
            requester = []
            if not order_infos:
                order_infos.update({
                    'warehouse_master_id': porder.warehouse_master_id and porder.warehouse_master_id.id or False,
                    'request_warehouse': porder.request_warehouse or "",
                    'issuing_warehouse_id': porder.issuing_warehouse_id and porder.issuing_warehouse_id.id or False,
                    'issuing_location_id': porder.issuing_location_id and porder.issuing_location_id.id or False,
                    'requesting_location_id': porder.requesting_location_id and porder.requesting_location_id.id or False,
                    'name': 'STI #',
                    'date_requested': porder.date_requested or False,
                    'date_required': porder.date_required or False,
                    'date_approved': fields.Date.context_today(self),
                    'approver_user_id': self.env.user.id,
                    'requester': "",
                    'history': "Issues are merged by " + str(self.env.user.name) + " on " + str(date),
                    'state': 'draft',
                    'issue_lines': {},
                    'request_no': porder.sudo().request_id and porder.sudo().request_id.name or porder.request_no,
                    'req_remarks': porder.req_remarks and porder.req_remarks or '',
                    })
            else:
                order_infos['request_no'] += (order_infos['request_no'] and ", " or "")  + (porder.sudo().request_id and porder.sudo().request_id.name or porder.request_no)
                order_infos['req_remarks'] += (order_infos['req_remarks'] and "\n " or "") + porder.req_remarks and porder.req_remarks or ""
                if order_infos['date_requested'] > porder.date_requested:
                        order_infos['date_requested'] = porder.date_requested or False
                if order_infos['date_required'] > porder.date_required:
                        order_infos['date_required'] = porder.date_required or False
                
            if porder.requester:
                requester.append(porder.requester)
                
            for order_line in porder.issue_lines:
                line_key = make_key(order_line, ('product_id', 'location_id'))
                o_line = order_infos['issue_lines'].setdefault(line_key, {})
                if o_line:
                    # merge the line with an existing line
                    o_line['approved_qty'] += order_line.approved_qty * order_line.uom_id.factor / o_line['uom_factor']
                    o_line['request_ref'] += (o_line['request_ref'] and ", ") + order_line.request_ref
                    if o_line['date_required'] > order_line.date_required:
                        o_line['date_required'] = order_line.date_required or False
                else:
                    # append a new "standalone" line
                    for field in ('approved_qty', 'uom_id'):
                        field_val = getattr(order_line, field)
                        if isinstance(field_val, browse_record):
                            field_val = field_val.id
                        o_line[field] = field_val
                    o_line['uom_factor'] = order_line.uom_id and order_line.uom_id.factor or 1.0
                    o_line['date_required'] = order_line.date_required or False
                    o_line['request_ref'] = order_line.request_ref
                order_line.state = 'cancel'
                
        requester = list(set(requester))
        for each_requester in requester:
            order_infos['requester'] += (order_infos['requester'] and ", " or "")  + each_requester
            
        allorders = []
        orders_info = {}
        for order_key, (order_data, old_ids) in new_orders.iteritems():
            # skip merges with only one order
            if len(old_ids) < 2:
                allorders += (old_ids or [])
                continue
                
            # cleanup order line data
            for key, value in order_data['issue_lines'].iteritems():
                del value['uom_factor']
                value.update(dict(key))
            order_data['issue_lines'] = [(0, 0, value) for value in order_data['issue_lines'].itervalues()]

            # create the new order
            neworder_id = issue_obj.create(order_data)
            orders_info.update({neworder_id: old_ids})
            allorders.append(neworder_id)

            # make triggers pointing to the old orders point to the new order
            for old_id in old_ids:
                issue_obj.browse(old_id).write({'state': 'cancel'})
        issue_ids = []    
        for new_order in allorders:
            issue_ids.append(new_order.id)
        result = {}
        action = self.env.ref('ebits_inventory.action_internal_stock_transfer_issue')
        result = action.read()[0]
        result['context'] = ctx
        if len(issue_ids) > 1:
            result['domain'] = "[('id','in',[" + ','.join(map(str, issue_ids)) + "])]"
        else:
            res = self.env.ref('ebits_inventory.internal_stock_transfer_issue_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = issue_ids and issue_ids[0] or False
        return result
        
InterTransferIssueMerge()
        
