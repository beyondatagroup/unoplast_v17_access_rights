# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import groupby
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang
import odoo.addons.decimal_precision as dp

class Warehouse(models.Model):
    _inherit = "stock.warehouse"
    
    #@api.multi
    def _compute_sale_count(self):
        domains = {
            'count_sale_draft': [('state', 'in', ('draft', 'sent'))],
            'count_sale_waiting_approval': [('state', '=', 'waiting')],
            'count_sale_to_invoice': [('state', 'in', ('sale', 'done')),('invoice_status', '!=', 'invoiced')],
            'count_sale_waiting_h_approval': [('state', '=', 'waiting_higher')],
        }
        for field in domains:
            data = self.env['sale.order'].read_group(domains[field] +
                [('warehouse_id', 'in', self.ids)],
                ['warehouse_id'], ['warehouse_id'])
            count = dict(map(lambda x: (x['warehouse_id'] and x['warehouse_id'][0], x['warehouse_id_count']), data))
            for record in self:
                record[field] = count.get(record.id, 0)
                
    #@api.multi
    def _compute_purchase_count(self):
        domains = {
            'count_purchase_draft': [('state', 'in', ('draft', 'sent'))],
            'count_purchase_to_approve': [('state', '=', 'to approve')],
            'count_purchase_to_2nd_approve': [('state', '=', 'to_2nd_approve')],
            }
        for field in domains:
            data = self.env['purchase.order'].read_group(domains[field] +
                [('warehouse_id', 'in', self.ids)],
                ['warehouse_id'], ['warehouse_id'])
            count = dict(map(lambda x: (x['warehouse_id'] and x['warehouse_id'][0], x['warehouse_id_count']), data))
            for record in self:
                record[field] = count.get(record.id, 0)
    
    count_sale_draft = fields.Integer(compute='_compute_sale_count')
    count_sale_waiting_approval = fields.Integer(compute='_compute_sale_count')
    count_sale_to_invoice = fields.Integer(compute='_compute_sale_count')
    count_sale_waiting_h_approval = fields.Integer(compute='_compute_sale_count')
    color = fields.Integer(string='Color Index', help="The color of the team")
    count_purchase_draft = fields.Integer(compute='_compute_purchase_count')
    count_purchase_to_approve = fields.Integer(compute='_compute_purchase_count')
    count_purchase_to_2nd_approve = fields.Integer(compute='_compute_purchase_count')
