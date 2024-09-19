# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import time
from collections import namedtuple
from datetime import datetime
from dateutil import relativedelta

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import float_utils
import logging

_logger = logging.getLogger(__name__)

class Warehouse(models.Model):
    _inherit = "stock.warehouse"
    
    count_irequest_draft = fields.Integer(compute='_compute_irequest_count')
    count_irequest_waiting = fields.Integer(compute='_compute_irequest_count')
    count_irequest_done = fields.Integer(compute='_compute_irequest_count')
    count_irequest_cancel = fields.Integer(compute='_compute_irequest_count')
    count_iissue_draft = fields.Integer(compute='_compute_iissue_count')
    count_iissue_partial = fields.Integer(compute='_compute_iissue_count')
    count_iissue_done = fields.Integer(compute='_compute_iissue_count')
    count_ireceipt_draft = fields.Integer(compute='_compute_ireceipt_count')
    count_ireceipt_partial = fields.Integer(compute='_compute_ireceipt_count')
    count_ireceipt_done = fields.Integer(compute='_compute_ireceipt_count')
    
    # @api.multi
    def _compute_irequest_count(self):
        domains = {
            'count_irequest_draft': [('state', '=', 'draft')],
            'count_irequest_waiting': [('state', '=', 'waiting')],
            'count_irequest_done': [('state', '=', 'done')],
            'count_irequest_cancel': [('state', '=', 'cancelled')],
        }
        for field in domains:
            data = self.env['internal.stock.transfer.request'].read_group(domains[field] +
                [('requesting_warehouse_id', 'in', self.ids)],
                ['requesting_warehouse_id'], ['requesting_warehouse_id'])
            count = dict(map(lambda x: (x['requesting_warehouse_id'] and x['requesting_warehouse_id'][0], x['requesting_warehouse_id_count']), data))
            for record in self:
                record[field] = count.get(record.id, 0)
                
    # @api.multi
    def _compute_iissue_count(self):
        domains = {
            'count_iissue_draft': [('state', '=', 'draft')],
            'count_iissue_partial': [('state', '=', 'partial')],
            'count_iissue_done': [('state', '=', 'done')],
        }
        for field in domains:
            data = self.env['internal.stock.transfer.issue'].read_group(domains[field] +
                [('issuing_warehouse_id', 'in', self.ids)],
                ['issuing_warehouse_id'], ['issuing_warehouse_id'])
            count = dict(map(lambda x: (x['issuing_warehouse_id'] and x['issuing_warehouse_id'][0], x['issuing_warehouse_id_count']), data))
            for record in self:
                record[field] = count.get(record.id, 0)
                
    # @api.multi
    def _compute_ireceipt_count(self):
        domains = {
            'count_ireceipt_draft': [('state', '=', 'draft')],
            'count_ireceipt_partial': [('state', '=', 'partial')],
            'count_ireceipt_done': [('state', '=', 'done')],
        }
        for field in domains:
            data = self.env['internal.stock.transfer.receipt'].read_group(domains[field] +
                [('receiving_warehouse_id', 'in', self.ids)],
                ['receiving_warehouse_id'], ['receiving_warehouse_id'])
            count = dict(map(lambda x: (x['receiving_warehouse_id'] and x['receiving_warehouse_id'][0], x['receiving_warehouse_id_count']), data))
            for record in self:
                record[field] = count.get(record.id, 0)
            
