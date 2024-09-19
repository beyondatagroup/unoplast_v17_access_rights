# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import time
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare, float_round
from odoo.tools.misc import formatLang
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import odoo.addons.decimal_precision as dp
import logging

# class MrpProductProduce(models.TransientModel):
#     _inherit = "mrp.product.produce"
#
#     shift_type = fields.Selection([('shift_1', 'Shift 1'), ('shift_2', 'Shift 2'), ('shift_3', 'Shift 3')], string="Shift", required=True)
#     quantity_check = fields.Float('Quantity Check', digits=dp.get_precision('Product Unit of Measure'))
#
#     @api.model
#     def default_get(self, fields):
#         res = super(MrpProductProduce, self).default_get(fields)
#         if self._context and self._context.get('active_id'):
#             production = self.env['mrp.production'].browse(self._context['active_id'])
#             #serial_raw = production.move_raw_ids.filtered(lambda x: x.product_id.tracking == 'serial')
#             main_product_moves = production.move_finished_ids.filtered(lambda x: x.product_id.id == production.product_id.id)
#             serial_finished = (production.product_id.tracking == 'serial')
#             serial = bool(serial_finished)
#             if serial_finished:
#                 quantity = 1.0
#             else:
#                 quantity = production.product_qty - sum(main_product_moves.mapped('quantity_done'))
#                 quantity = quantity if (quantity > 0) else 0
#             res['quantity_check'] = quantity
#         return res
#
#     @api.onchange('product_qty')
#     def onchange_product_qty(self):
#         warning = {}
#         integer, decimal = 0.00, 0.00
#         if not self.production_id:
#             self.product_qty = 0.00
#             warning = {
#                 'title': _('Warning'),
#                 'message': _('MO not available.')}
#             return {'warning': warning}
#         if self.product_qty and (not self.production_id.product_uom_id.allow_decimal_digits):
#             integer, decimal = divmod(self.product_qty, 1)
#             if decimal:
#                 self.product_qty = self.quantity_check
#                 warning = {
#                     'title': _('Warning'),
#                     'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.production_id.product_uom_id.name)}
#                 return {'warning': warning}
#         if self.product_qty > self.quantity_check:
#             self.product_qty = self.quantity_check
#             warning = {
#                 'title': _('Warning'),
#                 'message': _('You cannot enter the quantity greater than to be produced quantity')}
#             return {'warning': warning}
#
#
#     # @api.multi
#     def do_produce(self):
#         integer, decimal = 0.00, 0.00
#         quantity = 0.00
#         if self.product_qty:
#             self.production_id.action_assign()
#             if (not self.production_id.product_uom_id.allow_decimal_digits):
#                 integer, decimal = divmod(self.product_qty, 1)
#                 if decimal:
#                     raise UserError(_("You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value") % (self.production_id.product_uom_id.name))
#             if self.product_qty > self.quantity_check:
#                 raise UserError(_("You cannot enter the quantity greater than to be produced quantity"))
#             for move in self.production_id.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel')):
#                 #qty = self.product_qty / move.bom_line_id.bom_id.product_qty * move.bom_line_id.product_qty
#
#                 if (move.quantity_available - move.quantity_done) < (move.product_uom_qty - move.quantity_done):
#                     raise UserError(_(""" Raw material - "%s" is not available to produce the "%s" """) % (move.product_id.name_get()[0][1], self.production_id.product_id.name_get()[0][1]))
#         moves = self.production_id.move_finished_ids.filtered(lambda x: x.product_id.tracking == 'none' and x.state not in ('done', 'cancel'))
#         for move in moves:
#             if move.product_id.id == self.production_id.product_id.id:
#                 move.shift_type = self.shift_type
#             elif move.unit_factor:
#                 move.shift_type = self.shift_type
#         res = super(MrpProductProduce, self).do_produce()
#         return res
        
        
class ChangeProductionQty(models.TransientModel):
    _inherit = 'change.production.qty'
    
    # @api.multi
    def change_prod_qty(self):
        integer, decimal = 0.00, 0.00
        for wizard in self:
            production = wizard.mo_id
            if wizard.product_qty and (not production.product_uom_id.allow_decimal_digits):
                integer, decimal = divmod(wizard.product_qty, 1)
                if decimal:
                    raise UserError(_("You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the quantity should not contains decimal value") % (production.product_uom_id.name))
        result = super(ChangeProductionQty, self).change_prod_qty()
        return result
        
