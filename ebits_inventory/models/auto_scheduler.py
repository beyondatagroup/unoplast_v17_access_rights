# -*- coding: utf-8 -*-
# Part of EBITS TechCon

from collections import defaultdict
from datetime import datetime
import time
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_round
from odoo.exceptions import UserError
from odoo import api, fields, models, registry, _
import odoo.addons.decimal_precision as dp
import pytz
from psycopg2 import OperationalError
import logging

_logger = logging.getLogger(__name__)

class AutoInterTransferRequest(models.Model):
    _name = 'auto.intertransfer.request'
    _description = 'Auto Inter Transfer Request Generation'

    date = fields.Date(string='Date', default=fields.Date.context_today, copy=False)
    
    # @api.model
    # def _procurement_from_orderpoint_get_grouping_key(self, orderpoint_ids):
    #     orderpoints = self.env['stock.branch.orderpoint'].browse(orderpoint_ids)
    #     return orderpoints.location_id.id
        
    @api.model
    def _procurement_from_orderpoint_get_groups(self, orderpoint_ids):
        """ Make groups for a given orderpoint; by default schedule all operations in one without date """
        return [{'to_date': False, 'procurement_values': dict()}]
        
        
    # #@api.multi
    def _prepare_itr_values(self, warehouse_id=False):
        master_obj = self.env['internal.stock.transfer.master']
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        warehouse_master_id = False
        if warehouse_id:
            warehouse_master_bro = master_obj.search([('requesting_warehouse_id', '=', warehouse_id),('allow_auto_request', '=', True)], limit=1)
            warehouse_master_id = warehouse_master_bro and warehouse_master_bro or False
        
        return {
            'date_requested': fields.Date.context_today(self),
            'date_required': fields.Date.context_today(self),
            'user_id': self.env.user.id,
            'requesting_warehouse_id': warehouse_id,
            'warehouse_master_id': warehouse_master_bro and warehouse_master_bro.id or False,
            'requester': self.env.user.name,
            'required_location_id': warehouse_master_bro and (warehouse_master_bro.requesting_warehouse_id.int_type_id.default_location_src_id and warehouse_master_bro.requesting_warehouse_id.int_type_id.default_location_src_id.id or False) or False,
            'state': 'draft',
            'history': "This automatic request(based on stock rules) has been created on " + str(date) + " by " + str(self.env.user.name) ,
        }
        
    #@api.multi
    def _prepare_itr_line_values(self, request_form_id=False, product_id=False, qty_uom_dict={}):
        uom_id = False
        qty = 0.00
        if 'uom_id' in qty_uom_dict:
            uom_id = qty_uom_dict['uom_id']
        if 'qty' in qty_uom_dict:
            qty = qty_uom_dict['qty']
        return {
            'request_id': request_form_id.id,
            'product_id': product_id,
            'uom_id': uom_id,
            'required_qty': qty,
            'qty': qty,
            'date_required': fields.Date.context_today(self),
            'state': 'draft',
            }
    
    #
    # Scheduler
    #
    # @api.model
    # def run_itr_material_request_scheduler(self, use_new_cursor=False, company_id=False):
    #     # pass
    #     if use_new_cursor:
    #         cr = registry(self._cr.dbname).cursor()
    #         self = self.with_env(self.env(cr=cr))

    #     orderpoint_obj = self.env['stock.branch.orderpoint']

    #     request_obj = self.env['internal.stock.transfer.request']
        
    #     request_line_obj = self.env['internal.stock.transfer.request.lines']
    #     master_obj = self.env['internal.stock.transfer.master']
    #     product_obj = self.env['product.product']
    #     warehouse_id = []
    #     warehouse_dict = {}
    #     request_list = []
    #     master_bro = master_obj.search([('allow_auto_request', '=', True)])
    #     for each_master in master_bro:
    #         warehouse_id.append(each_master.requesting_warehouse_id.id)

    #     warehouse_id = list(set(warehouse_id))
    #     for each in warehouse_id:
    #         warehouse_dict[each] = {}
    #     print("\n\n..........warehouse_id.........", warehouse_id)
    #     orderpoints_noprefetch = orderpoint_obj.search([('warehouse_id', 'in', warehouse_id)], order='location_id')
    #     print("\n..........orderpoints_noprefetch........",orderpoints_noprefetch)
    #     while orderpoints_noprefetch:
    #         orderpoints = orderpoint_obj.browse(orderpoints_noprefetch[:1000].ids)
    #         orderpoints_noprefetch = orderpoints_noprefetch[1000:]

    #         # Calculate groups that can be executed together
    #         location_data = defaultdict(lambda: dict(products=self.env['product.product'], orderpoints=self.env['stock.branch.orderpoint'], groups=list()))
    #         for orderpoint in orderpoints:
    #             key = self._procurement_from_orderpoint_get_grouping_key([orderpoint.id])
    #             location_data[key]['products'] += orderpoint.product_id
    #             location_data[key]['orderpoints'] += orderpoint
    #             location_data[key]['groups'] = self._procurement_from_orderpoint_get_groups([orderpoint.id])
    #         print("\n\n..........run_itr_material_request_scheduler.........",self)
    #         for location_id, location_data in location_data.iteritems():
    #             location_orderpoints = location_data['orderpoints']
    #             product_context = dict(self._context, location=location_orderpoints[0].location_id.id)
    #             add_request_quantity = location_orderpoints.add_request_from_orderpoints()
    #             add_issue_quantity = location_orderpoints.add_issue_from_orderpoints()
    #             add_receive_quantity = location_orderpoints.add_receive_from_orderpoints()
    #             subtract_request_quantity = location_orderpoints.subtract_request_from_orderpoints()
    #             subtract_issue_quantity = location_orderpoints.subtract_issue_from_orderpoints()
    #             for group in location_data['groups']:
    #                 if group['to_date']:
    #                     product_context['to_date'] = group['to_date'].strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    #                 product_quantity = location_data['products'].with_context(product_context)._product_available()
    #                 for orderpoint in location_orderpoints:
    #                     try:
    #                         op_product_virtual = product_quantity[orderpoint.product_id.id]['virtual_available']
    #                         if op_product_virtual is None:
    #                             op_product_virtual = 0.00
    #                         op_product_virtual += add_request_quantity[orderpoint.id]
    #                         op_product_virtual += add_issue_quantity[orderpoint.id]
    #                         op_product_virtual += add_receive_quantity[orderpoint.id]
    #                         op_product_virtual -= subtract_request_quantity[orderpoint.id]
    #                         op_product_virtual -= subtract_issue_quantity[orderpoint.id]
    #                         if op_product_virtual is None:
    #                             continue
    #     #                     if float_compare(op_product_virtual, orderpoint.product_min_qty, precision_rounding=orderpoint.product_uom.rounding) <= 0:
    #                             qty = max(orderpoint.product_min_qty, orderpoint.product_max_qty) - op_product_virtual
    #                             remainder = orderpoint.qty_multiple > 0 and qty % orderpoint.qty_multiple or 0.0

    #                             if float_compare(remainder, 0.0, precision_rounding=orderpoint.product_uom.rounding) > 0:
    #                                 qty += orderpoint.qty_multiple - remainder

    #                             if float_compare(qty, 0.0, precision_rounding=orderpoint.product_uom.rounding) < 0:
    #                                 continue

    #                             qty_rounded = float_round(qty, precision_rounding=orderpoint.product_uom.rounding)
    #                             if qty_rounded > 0:
    #                                 if orderpoint.warehouse_id.id in warehouse_dict:
    #                                     if orderpoint.product_id.id in warehouse_dict[orderpoint.warehouse_id.id]:
    #                                         warehouse_dict[orderpoint.warehouse_id.id][orderpoint.product_id.id]['qty'] += qty_rounded
    #                                     else:
    #                                         warehouse_dict[orderpoint.warehouse_id.id][orderpoint.product_id.id] = {'qty': 0.00, 'uom_id': orderpoint.product_uom.id}
    #                                         warehouse_dict[orderpoint.warehouse_id.id][orderpoint.product_id.id]['qty'] += qty_rounded
    #                             if use_new_cursor:
    #                                 cr.commit()

    #                     except OperationalError:
    #                         if use_new_cursor:
    #                             orderpoints_noprefetch += orderpoint.id
    #                             cr.rollback()
    #                             continue
    #                         else:
    #                             raise
    #         try:
    #             for each_warehouse_id in warehouse_dict:
    #                 request_form_id = False
    #                 for each_product_id in warehouse_dict[each_warehouse_id]:
    #                     if warehouse_dict[each_warehouse_id][each_product_id]:
    #                         if not request_form_id:
    #                             request_form_id = request_obj.create(self._prepare_itr_values(each_warehouse_id))
    #                             request_list.append(request_form_id)
    #                         request_line_obj.create(self._prepare_itr_line_values(request_form_id, each_product_id, warehouse_dict[each_warehouse_id][each_product_id]))
    #     # print("\n\n...........each_warehouse_id........",warehouse_dict)
    #             # TDE CLEANME: use record set ?
    #             #request_list.reverse()
    #             requests = request_obj
    #             for r in request_list:
    #                 requests += r
    #             requests.action_send_approval()
    #             requests.action_approve()
    #             if use_new_cursor:
    #                 cr.commit()
    #         except OperationalError:
    #             if use_new_cursor:
    #                 cr.rollback()
    #                 continue
    #             else:
    #                 raise

    #         if use_new_cursor:
    #             cr.commit()

    #     if use_new_cursor:
    #         cr.commit()
    #         cr.close()
    #     return {}
