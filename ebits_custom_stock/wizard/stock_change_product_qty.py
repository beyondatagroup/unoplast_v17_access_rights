# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, tools, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError


class ProductChangeQuantity(models.TransientModel):
    _inherit = "stock.change.product.qty"

    # TDE FIXME: strange dfeault method, was present before migration ? to check
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse/Branch')
    location_id = fields.Many2one('stock.location', 'Location', required=True)
    view_location_id = fields.Many2one('stock.location', 'View Location')

    @api.model
    def default_get(self, fields):
        res = super(ProductChangeQuantity, self).default_get(fields)
        res['location_id'] = False
        return res
        
    @api.onchange('location_id', 'product_id')
    def onchange_location_id(self):
        # TDE FIXME: should'nt we use context / location ?
        if self.location_id and self.product_id:
            availability = self.product_id.with_context(location=self.location_id.id)._product_available()
            self.new_quantity = availability[self.product_id.id]['qty_available']

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        domain = {}
        if self.warehouse_id:
            self.view_location_id = self.warehouse_id.view_location_id.id
            self.location_id = self.warehouse_id.lot_stock_id.id
            domain = {
                'location_id': ['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')],
                }
        else:
            self.view_location_id = False
            self.location_id = False
        return {'domain': domain}
