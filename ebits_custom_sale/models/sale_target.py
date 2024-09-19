# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import groupby
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang

import odoo.addons.decimal_precision as dp

class SalesTarget(models.Model):
    _name = "sales.target"
    _description = "Sales Target"
    _order = "id desc"

    name = fields.Char(string='Target Name', required=True)
    date_start = fields.Date('Start Date', required=True)
    date_end = fields.Date('End Date', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True)
    based_product = fields.Selection([('product', 'Product'), ('product_category', 'Product Category'), ('parent_category', 'Parent Category')], string='Based on', required=True)
    based_team = fields.Selection([('sales_team', 'Sales Team'), ('sales_person', 'Sales Person')], string='Based on')
    target_line = fields.One2many('sales.target.line', 'target_id', string='Target Line')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], string='State', readonly=True, default='draft')
    active = fields.Boolean('Active', default=True)
    
    #@api.multi
    def move_to_done(self):
        for each in self:
            if not each.target_line:
                raise UserError(_('Target Line has to be entered'))
            each.state = 'done'
        return True
            
    #@api.multi
    def move_to_reedit(self):
        for each in self:
            each.state = 'draft'
        return True
        
    #@api.multi
    def unlink(self):
        for order in self:
            raise UserError(_('You can not delete sales target form.'))
        return super(SalesTarget, self).unlink()
    
class SalesTargetLine(models.Model):
    _name = "sales.target.line"
    _description = "Sales Target Line"
    
    target_id = fields.Many2one('sales.target', string='Sales Target') 
    team_id = fields.Many2one('crm.team', string='Sales Team')
    user_id = fields.Many2one('res.users', string='Sales Person')
    product_ids = fields.Many2many('product.product', 'sales_target_product_relation', 'target_line_id', 'product_id', string='Product')
    product_category_ids = fields.Many2many('product.category', 'sales_target_category_relation', 'target_line_id', 'category_id', string='Product Category')
    parent_category_ids = fields.Many2many('product.category', 'sales_target_parent_category_relation', 'target_line_id', 'parent_categ_id', string='Parent Category')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    target_qty = fields.Float('Target Qty', digits='Product Unit of Measure')
    target_value = fields.Float('Target Value', digits='Product Price')
    based_product = fields.Selection([('product', 'Product'), ('product_category', 'Product Category'), ('parent_category', 'Parent Category')], string='Based on', readonly=True)
    based_team = fields.Selection([('sales_team', 'Sales Team'), ('sales_person', 'Sales Person')], string='Based on', readonly=True)
    
