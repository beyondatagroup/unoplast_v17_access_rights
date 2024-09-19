
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    def force_assign(self):
        """ Changes state of picking to available if moves are confirmed or waiting.
        @return: True
        """
        self.mapped('move_ids').filtered(lambda move: move.state in ['confirmed', 'waiting'])
        # self.mapped('move_ids').filtered(lambda move: move.state in ['confirmed', 'waiting'])._prepare_move_line_vals()
        return True