# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError

class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"
    
    @api.model
    def default_get(self, fields):
        if len(self.env.context.get('active_ids', list())) > 1:
            raise UserError("You may only return one picking at a time!")
        res = super(StockReturnPicking, self).default_get(fields)

        Quant = self.env['stock.quant']
        move_dest_exists = False
        product_return_moves = []
        picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
        # print('>>>>>>>>>>>>>>>>picking>>>>>>>>>>>>>>>>.',picking)
        if picking:

            res.update({'product_return_moves': []})
            if picking.state != 'done':
                raise UserError(_("You may only return Done pickings"))
            for move in picking.move_ids_without_package:
                # print('>>>>>>>>>move>>>>>>>>>>>',move)
                if move.scrapped:
                    continue
                if move.move_dest_ids:
                    move_dest_exists = True
                # Sum the quants in that location that can be returned (they should have been moved by the moves that were included in the returned picking)
                quantity = sum(quant.qty for quant in Quant.search([
                    ('history_ids', 'in', move.id),
                    ('qty', '>', 0.0), ('location_id', 'child_of', move.location_dest_id.id)
                ]).filtered(
                    lambda quant: not quant.reservation_id or quant.reservation_id.origin_returned_move_id != move)
                )
#                 print('>>>>>quantity>>>>>>>>>>',quantity)
                quantity = move.product_id.uom_id._compute_quantity(quantity, move.product_uom)
#                 print('-----quantity--------',quantity)
#                 print('-----product_id--------',move.product_id.id)
                #if quantity:
                product_return_moves.append((0, 0, {'product_id': move.product_id.id, 'quantity': quantity, 'move_id': move.id, 'to_refund_so': True}))
            print("\n........product_return_moves...",product_return_moves)
            if not product_return_moves:
                # print('>>>>>>product_return_moves>>>>>>>>>>>')
                raise UserError(_("No products to return (only lines in Done state and not fully returned yet can be returned)!"))
            if 'product_return_moves' in fields:
                res.update({'product_return_moves': product_return_moves})
                
        try:
            for line in res["product_return_moves"]:
                assert line[0] == 0
                move = self.env["stock.move"].browse(line[2]["move_id"])
                line[2]["purchase_line_id"] = (move.purchase_line_id.id)
        except KeyError:
            pass
        return res
    

    
    def _create_returns(self):
        picking = self.env['stock.picking'].browse(self.env.context['active_id'])
        for return_line in self.product_return_moves:
            if not return_line.move_id:
                raise UserError(_("You have manually created product lines, please delete them to proceed"))
            if return_line.quantity > return_line.move_id.product_uom_qty:
                raise UserError(_(" Product %s return qty (%s) must be lesser or equal to the already transfered qty (%s). ") % (return_line.product_id.name_get()[0][1], return_line.quantity, return_line.move_id.product_uom_qty))
        
        new_picking_id, pick_type_id = super(StockReturnPicking, self)._create_returns()
        new_picking = self.env['stock.picking'].browse([new_picking_id])
        refund = False
        for move in new_picking.move_ids_without_package:
            return_picking_line = self.product_return_moves.filtered(lambda r: r.move_id == move.origin_returned_move_id)
            if return_picking_line and return_picking_line.to_refund_so:
                refund = True
            if return_picking_line:
                if return_picking_line.purchase_line_id:
                    move.purchase_line_id = return_picking_line.purchase_line_id

        if refund:
            if picking.picking_type_code == 'outgoing':
                new_picking.write({'to_refund': True})
            elif picking.picking_type_code == 'incoming':
                new_picking.write({'to_refund_po': True})
        return new_picking_id, pick_type_id
        

class StockReturnPickingLine(models.TransientModel):
    _inherit = "stock.return.picking.line"
    
    to_refund_so = fields.Boolean(string="To Refund", help='Trigger a decrease of the delivered quantity in the associated Sale Order', default=True)
    purchase_line_id = fields.Many2one(comodel_name='purchase.order.line', string="Purchase order line", readonly=True)
