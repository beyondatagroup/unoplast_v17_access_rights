# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

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

class PoProductLocationQuantityWizard(models.TransientModel):
    _name = "po.product.location.quantity.wizard"
    _description = "Purchase Order Product Location Quantity Wizard"
    
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    location_line = fields.One2many('po.location.quantity.line', 'location_qty_id', string="PO Location Quantity")
    
    @api.model
    def default_get(self, fields):
        res = super(PoProductLocationQuantityWizard, self).default_get(fields)
        po_line_id = self.env['purchase.order.line'].browse(self.env.context.get('active_id')) 
        res['product_id'] = po_line_id.product_id and po_line_id.product_id.id or False
        stock_quant_search = self.env['stock.quant'].search([('product_id', '=', po_line_id.product_id.id)])
        value = []
        loc_qty = {}
        warehouse_search = False
        for each in stock_quant_search:
            if each.location_id.usage in ('internal', 'transit'):
                loc_search = self.env['stock.location'].search([('id', 'parent_of', each.location_id.id)])
                for each_loc_search in loc_search:
                    warehouse_search = self.env['stock.warehouse'].search([('view_location_id', '=', each_loc_search.id)])
                    if warehouse_search:
                        break
                if each.location_id.id in loc_qty:
                    loc_qty[each.location_id.id]['qty'] += each.qty and each.qty or 0.00  
                else:
                    loc_qty[each.location_id.id] = {}
                    loc_qty[each.location_id.id] = {
                        'warehouse_id': warehouse_search and warehouse_search.id or False, 
                        'location_id': each.location_id and each.location_id.id or False,
                        'qty': each.qty and each.qty or 0.00 
                    }
        for line in loc_qty: 
            value.append((0, 0, loc_qty[line]))
            res.update({
                'location_line': value 
            })
        return res
    
    # @api.multi
    def action_done(self):
        return True
        
class PoLocationQuantityLine(models.TransientModel):
    _name = "po.location.quantity.line"
    _description = "Purchase Order Location Quantity Line"
    
    location_qty_id = fields.Many2one('po.product.location.quantity.wizard', string='PO Product Quantity', ondelete='cascade')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    location_id = fields.Many2one('stock.location', string='Location')
    qty = fields.Float(string="Quantity", digits='Product Unit of Measure')
    
