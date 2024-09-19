# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import time
from odoo import api, fields, models, _

class ProductCategory(models.Model):
    _inherit = "product.category"
    
#    x_density = fields.Float('Density (Kg/m3)', help="The Density in kg/m3.")
    x_density = fields.Float(compute='_compute_current_density', string='Current Density (Kg/m3)')
    density_ids = fields.One2many('product.category.density', 'category_id', string='Density')
    x_density_date = fields.Date(compute='_compute_date', string='Date')
    
    # @api.multi
    def _compute_current_density(self):
        date = self._context.get('x_density_date') or fields.Datetime.now()
        company_id = self._context.get('company_id') or self.env.user.company_id.id
        query = """SELECT c.id, (SELECT r.density FROM product_category_density r
                                  WHERE r.category_id = c.id AND r.name <= %s
                                    AND (r.company_id IS NULL OR r.company_id = %s)
                               ORDER BY r.company_id, r.name DESC
                                  LIMIT 1) AS density
                   FROM product_category c
                   WHERE c.id IN %s"""
        self._cr.execute(query, (date, company_id, tuple(self.ids)))
        category_density = dict(self._cr.fetchall())
        for category in self:
            category.x_density = category_density.get(category.id) or 0.0
   
    # @api.multi
    @api.depends('density_ids.name')
    def _compute_date(self):
        for category in self:
            category.x_density_date = category.density_ids[:1].name
            
class CategoryDensity(models.Model):
    _name = "product.category.density"
    _description = "Category Density"
    _order = "name desc"

    name = fields.Datetime(string='Date', required=True, index=True, default=lambda self: str(fields.Date.today()) + ' 00:00:00')
    density = fields.Float('Density (Kg/m3)', help="The Density in kg/m3.")
    category_id = fields.Many2one('product.category', string='Category', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=80):
        if operator in ['=', '!=']:
            try:
                date_format = '%Y-%m-%d'
                if self._context.get('lang'):
                    langs = self.env['res.lang'].search([('code', '=', self._context['lang'])])
                    if langs:
                        date_format = langs.date_format
                name = time.strftime('%Y-%m-%d', time.strptime(name, date_format))
            except ValueError:
                try:
                    args.append(('density', operator, float(name)))
                except ValueError:
                    return []
                name = ''
                operator = 'ilike'
        return super(CategoryDensity, self).name_search(name, args=args, operator=operator, limit=limit)
    
class ProductTemplate(models.Model):
    _inherit = "product.template"

    # landed_cost_ok = fields.Boolean('Landed Costs')

    @api.depends('product_variant_ids', 'product_variant_ids.x_length')
    def _compute_x_length(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_length = template.product_variant_ids.x_length
        for template in (self - unique_variants):
            template.x_length = 0.0
            

    # @api.one
    def _set_x_length(self):
        for each in self:
            if len(each.product_variant_ids) == 1:
                each.product_variant_ids.x_length = each.x_length
            
    @api.depends('product_variant_ids', 'product_variant_ids.x_width')
    def _compute_x_width(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_width = template.product_variant_ids.x_width
        for template in (self - unique_variants):
            template.x_width = 0.0

    # @api.one
    def _set_x_width(self):
        for each in self:
            if len(each.product_variant_ids) == 1:
                each.product_variant_ids.x_width = each.x_width
            
    @api.depends('product_variant_ids', 'product_variant_ids.x_thickness')
    def _compute_x_thickness(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_thickness = template.product_variant_ids.x_thickness
        for template in (self - unique_variants):
            template.x_thickness = 0.0
            
    # @api.one
    def _set_x_thickness(self):
        for each in self:
            if len(each.product_variant_ids) == 1:
                each.product_variant_ids.x_thickness = each.x_thickness
            
            
    @api.depends('x_length', 'x_width', 'x_thickness', 'categ_id.density_ids', 'categ_id.x_density', 'product_variant_ids', 'product_variant_ids.volume')
    def _compute_volume(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.volume = template.product_variant_ids.volume
        for template in (self - unique_variants):
            template.volume = 0.0

    # @api.one
    def _set_volume(self):
        for each in self:
            if len(each.product_variant_ids) == 1:
                each.product_variant_ids.volume = each.volume

    @api.depends('x_length', 'x_width', 'x_thickness', 'volume', 'categ_id.density_ids', 'categ_id.x_density', 'product_variant_ids', 'product_variant_ids.weight')
    def _compute_weight(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.weight = template.product_variant_ids.weight
        for template in (self - unique_variants):
            template.weight = 0.0

    # @api.one
    def _set_weight(self):
        for each in self:
            if len(each.product_variant_ids) == 1:
                each.product_variant_ids.weight = each.weight
            
    quality_check_required = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Quality Check Required')
    x_length = fields.Float('Length (inch)', compute='_compute_x_length', inverse='_set_x_length', store=True, digits='Product Unit of Measure')
    x_width = fields.Float('Width (inch)', compute='_compute_x_width', inverse='_set_x_width', store=True, digits='Product Unit of Measure')
    x_thickness = fields.Float('Thickness (inch)', compute='_compute_x_thickness', inverse='_set_x_thickness', store=True, digits='Product Unit of Measure')
    volume = fields.Float(
        'Volume (m3)', compute='_compute_volume', inverse='_set_volume',
        help="The volume in m3.", store=True, digits='Product Unit of Measure')
    weight = fields.Float(
        'Weight (Kg)', compute='_compute_weight', digits='Product Unit of Measure',
        inverse='_set_weight', store=True,
        help="The weight of the contents in Kg, not including any packaging, etc.")

class ProductProduct(models.Model):
    _inherit = "product.product"
    
    @api.depends('x_length', 'x_width', 'x_thickness')
    def _compute_product_variant_volume(self):
        for each in self:
            each.volume = (((each.x_length * 25.4) * (each.x_width * 25.4) * (each.x_thickness * 25.4)) / 1000000000)
        
    @api.depends('x_length', 'x_width', 'x_thickness', 'volume', 'categ_id.density_ids', 'categ_id.x_density')
    def _compute_product_variant_weight(self):
        for each in self:
            print("\n\n.........each.weight........",each.weight)
            print(".........each.volume.......",each.volume)
            print(".......each.categ_id.x_density.......",each.categ_id.x_density)
            each.weight = each.volume * each.categ_id.x_density
        
            
    incoming_quality_line = fields.One2many('incoming.quality.parameter', 'product_id', string='Incoming Quality Parameter')
    x_length = fields.Float('Length (inch)', digits='Product Unit of Measure')
    x_width = fields.Float('Width (inch)', digits='Product Unit of Measure')
    x_thickness = fields.Float('Thickness (inch)', digits='Product Unit of Measure')
    volume = fields.Float('Volume (m3)', help="The volume in m3.", compute="_compute_product_variant_volume", digits='Product Unit of Measure')
    weight = fields.Float(
        'Weight (Kg)', digits='Product Unit of Measure',
        help="The weight of the contents in Kg, not including any packaging, etc.", compute="_compute_product_variant_weight")
    
class IncomingQualityParameter(models.Model):
    _name = "incoming.quality.parameter"
    _description = "Incoming Quality Parameter"
    
    product_id = fields.Many2one('product.product', string='Product', required=True)
    # parameter_id = fields.Many2one('quality.parameter', string='Parameter', required=True)
    measure = fields.Char(string='Measure', size=20, required=True)
    # parameter_type_id = fields.Many2one('parameter.type', string='Type of Parameter', required=True)
    std_min_value = fields.Float(string='Standard Min Value', digits='Product Unit of Measure')
    std_max_value = fields.Float(string='Standard Max Value', digits='Product Unit of Measure')
    
    # @api.onchange('parameter_id')
    # def onchange_parameter_id(self):
    #     self.measure = self.parameter_id.measure and self.parameter_id.measure or ''
    #     self.parameter_type_id = self.parameter_id.parameter_id and self.parameter_id.parameter_id.id or False
        
