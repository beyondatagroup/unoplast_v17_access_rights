# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import warnings

class ResUsers(models.Model):
    _inherit = 'res.users'

    restrict_locations = fields.Boolean('Restrict Location')

    stock_location_ids = fields.Many2many(
        'stock.location',
        'location_security_stock_location_users',
        'user_id',
        'location_id',
        'Stock Locations')
        
    default_warehouse_ids = fields.Many2many(
        'stock.warehouse', 'stock_warehouse_users_rel',
        'user_id', 'warehouse_id', string='Default Warehouses')

    default_picking_type_ids = fields.Many2many(
        'stock.picking.type', 'stock_picking_type_users_rel',
        'user_id', 'picking_type_id', string='Default Warehouse Operations')


class stock_move(models.Model):
    _inherit = 'stock.move'

    @api.constrains('state', 'location_id', 'location_dest_id')
    def check_user_location_rights(self):
        for state in self:
            if state.state == 'draft':
                return True
            user_locations = self.env.user.stock_location_ids
            if self.env.user.restrict_locations:
                message = _(
                    'Invalid Location. You cannot process this move since you do '
                    'not control the location "%s". '
                    'Please contact your Adminstrator.')
                if self.location_id not in user_locations:
                    raise warnings.warn(message % self.location_id.name)
                elif self.location_dest_id not in user_locations:
                    raise warnings.warn(message % self.location_dest_id.name)


