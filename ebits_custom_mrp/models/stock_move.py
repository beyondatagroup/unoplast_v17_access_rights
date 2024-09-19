# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import json
import time
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare
from odoo.tools.misc import formatLang

from odoo.exceptions import UserError, RedirectWarning, ValidationError

import odoo.addons.decimal_precision as dp
import logging

class StockMove(models.Model):
    _inherit = "stock.move"
    
    shift_type = fields.Selection([('shift_1', 'Shift 1'), ('shift_2', 'Shift 2'), ('shift_3', 'Shift 3')], string="Shift", readonly=True, copy=False)
    sf_raw_material_id = fields.Many2one('raw.materials.line', string='Raw Materials Line', readonly=True, copy=False)
    move_product_id = fields.Many2one('mrp.production', string="Move Product")
    quant_ids = fields.Many2many('stock.quant', 'stock_quant_move_rel', 'move_id', 'quant_id', 'Moved Quants', copy=False)

    

