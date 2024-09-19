# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round
from datetime import datetime
import operator as py_operator

OPERATORS = {
    '<': py_operator.lt,
    '>': py_operator.gt,
    '<=': py_operator.le,
    '>=': py_operator.ge,
    '==': py_operator.eq,
    '!=': py_operator.ne
}

class ProductCategory(models.Model):
    _inherit = "product.category"
    
    type = fields.Selection([
        ('view', 'View'),
        ('normal', 'Normal')], 'Category Type', default='normal',
        help="A category of the view type is a virtual category that can be used as the parent of another category to create a hierarchical structure.")
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_product_categ_warehouse', 'category_id', 'warehouse_id', string='Warehouse')

class Product(models.Model):
    _inherit = "product.product"
    
    
    nbr_reordering_rules = fields.Integer('ROL Warehouse', compute='_compute_nbr_reordering_rules')
    reordering_min_qty = fields.Float('Warehouse ROL Min Qty', compute='_compute_nbr_reordering_rules', digits=('Product Unit of Measure'))
    reordering_max_qty = fields.Float('Warehouse ROL Min Qty', compute='_compute_nbr_reordering_rules', digits=('Product Unit of Measure'))
    orderpoint_ids = fields.One2many('stock.warehouse.orderpoint', 'product_id', string='Warehouse Minimum Stock Rules')
    branch_orderpoint_ids = fields.One2many('stock.branch.orderpoint', 'product_id', string='Branch Minimum Stock Rules')
    branch_nbr_reordering_rules = fields.Integer('ROL Branch', compute='_compute_branch_nbr_reordering_rules')
    branch_reordering_min_qty = fields.Float('Branch ROL Min Qty', compute='_compute_branch_nbr_reordering_rules', digits=('Product Unit of Measure'))
    branch_reordering_max_qty = fields.Float('Branch ROL Max Qty', compute='_compute_branch_nbr_reordering_rules', digits=('Product Unit of Measure'))
    
    def _compute_nbr_reordering_rules(self): 
        read_group_res = self.env['stock.warehouse.orderpoint'].read_group(
            [('product_id', 'in', self.ids)],
            ['product_id', 'product_min_qty', 'product_max_qty'],
            ['product_id'])
        res = {i: {} for i in self.ids}
        for data in read_group_res:
            res[data['product_id'][0]]['nbr_reordering_rules'] = int(data['product_id_count'])
            res[data['product_id'][0]]['reordering_min_qty'] = data['product_min_qty']
            res[data['product_id'][0]]['reordering_max_qty'] = data['product_max_qty']
        for product in self:
            product.nbr_reordering_rules = res[product.id].get('nbr_reordering_rules', 0)
            product.reordering_min_qty = res[product.id].get('reordering_min_qty', 0)
            product.reordering_max_qty = res[product.id].get('reordering_max_qty', 0)
    
    def _compute_branch_nbr_reordering_rules(self):
        read_group_res = self.env['stock.branch.orderpoint'].read_group(
            [('product_id', 'in', self.ids)],
            ['product_id', 'product_min_qty', 'product_max_qty'],
            ['product_id'])
        res = {i: {} for i in self.ids}
        for data in read_group_res:
            res[data['product_id'][0]]['branch_nbr_reordering_rules'] = int(data['product_id_count'])
            res[data['product_id'][0]]['branch_reordering_min_qty'] = data['product_min_qty']
            res[data['product_id'][0]]['branch_reordering_max_qty'] = data['product_max_qty']
        for product in self:
            product.branch_nbr_reordering_rules = res[product.id].get('branch_nbr_reordering_rules', 0)
            product.branch_reordering_min_qty = res[product.id].get('branch_reordering_min_qty', 0)
            product.branch_reordering_max_qty = res[product.id].get('branch_reordering_max_qty', 0)
            
    
    def toggle_active(self):
        res = super(Product, self).toggle_active()
        if self.qty_available != 0.00:
            raise UserError(_('Product can be made inactive only when quantity on hand is zero'))
        return res

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    def _get_default_category_id(self):
#        if self._context.get('categ_id') or self._context.get('default_categ_id'):
#            return self._context.get('categ_id') or self._context.get('default_categ_id')
#        category = self.env.ref('product.product_category_all', raise_if_not_found=False)
#        return category and category.id or False
        return False
    # remove from categ_id==> domain="[('type','=','normal')]"
    categ_id = fields.Many2one('product.category', 'Internal Category',
                               change_default=True, default=_get_default_category_id,
                               required=True, help="Select category for the current product")
    nbr_reordering_rules = fields.Integer('Warehouse ROL', compute='_compute_nbr_reordering_rules')
    reordering_min_qty = fields.Float('Warehouse ROL Min Qty', compute='_compute_nbr_reordering_rules', digits=('Product Unit of Measure'))
    reordering_max_qty = fields.Float('Warehouse ROL Min Qty', compute='_compute_nbr_reordering_rules', digits=('Product Unit of Measure'))
    branch_nbr_reordering_rules = fields.Integer('ROL Branch', compute='_compute_branch_nbr_reordering_rules')
    branch_reordering_min_qty = fields.Float('Branch ROL Min Qty', compute='_compute_branch_nbr_reordering_rules', digits=('Product Unit of Measure'))
    branch_reordering_max_qty = fields.Float('Branch ROL Max Qty', compute='_compute_branch_nbr_reordering_rules', digits=('Product Unit of Measure'))
    
    def _compute_nbr_reordering_rules(self):
        res = {k: {'nbr_reordering_rules': 0, 'reordering_min_qty': 0, 'reordering_max_qty': 0} for k in self.ids}
        product_data = self.env['stock.warehouse.orderpoint'].read_group([('product_id.product_tmpl_id', 'in', self.ids)], ['product_id', 'product_min_qty', 'product_max_qty'], ['product_id'])
        for data in product_data:
            product = self.env['product.product'].browse([data['product_id'][0]])
            product_tmpl_id = product.product_tmpl_id.id
            res[product_tmpl_id]['nbr_reordering_rules'] += int(data['product_id_count'])
            res[product_tmpl_id]['reordering_min_qty'] = data['product_min_qty']
            res[product_tmpl_id]['reordering_max_qty'] = data['product_max_qty']
        for template in self:
            template.nbr_reordering_rules = res[template.id]['nbr_reordering_rules']
            template.reordering_min_qty = res[template.id]['reordering_min_qty']
            template.reordering_max_qty = res[template.id]['reordering_max_qty']
    
    def _compute_branch_nbr_reordering_rules(self):
        res = {k: {'branch_nbr_reordering_rules': 0, 'branch_reordering_min_qty': 0, 'branch_reordering_max_qty': 0} for k in self.ids}
        product_data = self.env['stock.branch.orderpoint'].read_group([('product_id.product_tmpl_id', 'in', self.ids)], ['product_id', 'product_min_qty', 'product_max_qty'], ['product_id'])
        for data in product_data:
            product = self.env['product.product'].browse([data['product_id'][0]])
            product_tmpl_id = product.product_tmpl_id.id
            res[product_tmpl_id]['branch_nbr_reordering_rules'] += int(data['product_id_count'])
            res[product_tmpl_id]['branch_reordering_min_qty'] = data['product_min_qty']
            res[product_tmpl_id]['branch_reordering_max_qty'] = data['product_max_qty']
        for template in self:
            template.branch_nbr_reordering_rules = res[template.id]['branch_nbr_reordering_rules']
            template.branch_reordering_min_qty = res[template.id]['branch_reordering_min_qty']
            template.branch_reordering_max_qty = res[template.id]['branch_reordering_max_qty']
            
            
    
    def action_view_branch_orderpoints(self):
        products = self.mapped('product_variant_ids')
        action = self.env.ref('ebits_custom_stock.product_open_branch_orderpoint').read()[0]
        if products and len(products) == 1:
            action['context'] = {'default_product_id': products.ids[0], 'search_default_product_id': products.ids[0]}
        else:
            action['domain'] = [('product_id', 'in', products.ids)]
            action['context'] = {}
        return action
        
    
    def toggle_active(self):
        if self.qty_available != 0.00:
            raise UserError(_('Product can be made inactive only when quantity on hand is zero'))
        res = super(ProductTemplate, self).toggle_active()
        return res
        
