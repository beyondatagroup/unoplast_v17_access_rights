from odoo import api, fields, models, _
from datetime import datetime
import time


class ProductCategory(models.Model):
    _inherit = "product.category"
    
#    x_density = fields.Float('Density (Kg/m3)', help="The Density in kg/m3.")
    # x_density = fields.Float(compute='_compute_current_density', string='Current Density (Kg/m3)')
    x_density = fields.Float( string='Current Density (Kg/m3)')
    density_ids = fields.One2many('product.category.density', 'category_id', string='Density')
    x_density_date = fields.Date(compute='_compute_date', string='Date')
    
    # def _compute_current_density(self):
    #     date = self._context.get('x_density_date') or fields.Datetime.now()
    #     company_id = self._context.get('company_id') or self.env['res.users']._get_company().id
    #     # the subquery selects the last density before 'date' for the given category
    #     query = """SELECT c.id, (SELECT r.density FROM product_category_density r
    #                               WHERE r.category_id = c.id AND r.name <= %s
    #                                 AND (r.company_id IS NULL OR r.company_id = %s)
    #                            ORDER BY r.company_id, r.name DESC
    #                               LIMIT 1) AS density
    #                FROM product_category c
    #                WHERE c.id IN %s"""
    #     self._cr.execute(query, (date, company_id, tuple(self.ids)))
    #     category_density = dict(self._cr.fetchall())
    #     for category in self:
    #         category.x_density = category_density.get(category.id) or 0.0
   
    @api.depends('density_ids.name')
    def _compute_date(self):
        for category in self:
            category.x_density_date = category.density_ids[:1].name

class CategoryDensity(models.Model):
    _name = "product.category.density"
    _description = "Category Density"
    _order = "name desc"

    name = fields.Datetime(
        string='Date', 
        required=True, 
        index=True, 
        
    )
    density = fields.Float('Density (Kg/m3)', help="The Density in kg/m3.")
    category_id = fields.Many2one('product.category', string='Category', readonly=True)
    company_id = fields.Many2one('res.company', string='Company')

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
  
  