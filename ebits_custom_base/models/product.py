# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import itertools
import psycopg2

from itertools import groupby
from datetime import datetime, timedelta

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang
import odoo.addons.decimal_precision as dp
#custom
#from odoo.exceptions import ValidationError, except_orm
from odoo.exceptions import ValidationError


class ProductUoM(models.Model):
    _inherit = 'uom.uom'
    
    allow_decimal_digits = fields.Boolean(string='Allow Decimal Value', default=True, help="This is used in the sale, purchase, stock move, invoice, inventory, quality, production form", copy=False)

class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    stock_warehouse_ids = fields.Many2many('stock.warehouse', 'product_product_stock_warehouse_rela', 'product_id', 'warehouse_id', string='Warehouse/Branch')
    purchase_req_required = fields.Boolean(string="Purchase Requisition Required")


class ProductProduct(models.Model):
    _inherit = "product.product"

    package_product_lines = fields.One2many('product.package.product', 'product_id', 'Product(s) Pack', copy=False)
    package_available = fields.Boolean(string='Pack Available')
    
class ProductCategory(models.Model):
    _inherit = "product.category"
    
    discount_lines = fields.One2many('qty.category.discount', 'category_id', 'Discount Lines', copy=False)
    
class Pricelist(models.Model):
    _inherit = "product.pricelist"

    # commented as already in v17
    #@api.multi
    # def _compute_price_rule(self, products_qty_partner, date=False, uom_id=False):
    #     """ Low-level method - Mono pricelist, multi products
    #     Returns: dict{product_id: (price, suitable_rule) for the given pricelist}
    #
    #     If date in context: Date of the pricelist (%Y-%m-%d)
    #
    #         :param products_qty_partner: list of typles products, quantity, partner
    #         :param datetime date: validity date
    #         :param ID uom_id: intermediate unit of measure
    #     """
    #     self.ensure_one()
    #     if not date:
    #         date = self._context.get('date', fields.Date.today())
    #     if not uom_id and self._context.get('uom'):
    #         uom_id = self._context['uom']
    #     if uom_id:
    #         # rebrowse with uom if given
    #         product_ids = [item[0].id for item in products_qty_partner]
    #         products = self.env['product.product'].with_context(uom=uom_id).browse(product_ids)
    #
    #         print("Length of products_qty_partner:", len(products_qty_partner))
    #         print("Length of products:", len(products))
    #
    #         products_qty_partner = [(products[index], data_struct[1], data_struct[2])
    #                                 for index, data_struct in enumerate(products_qty_partner)]
    #
    #         print("Length of products_qty_partner2222:", len(products_qty_partner))
    #     else:
    #         products = [item[0] for item in products_qty_partner]
    #
    #     if not products:
    #         return {}
    #
    #     categ_ids = {}
    #     for p in products:
    #         categ = p.categ_id
    #         while categ:
    #             categ_ids[categ.id] = True
    #             categ = categ.parent_id
    #     categ_ids = categ_ids.keys()
    #
    #     is_product_template = products[0]._name == "product.template"
    #     if is_product_template:
    #         prod_tmpl_ids = [tmpl.id for tmpl in products]
    #         # all variants of all products
    #         prod_ids = [p.id for p in
    #                     list(itertools.chain.from_iterable([t.product_variant_ids for t in products]))]
    #     else:
    #         prod_ids = [product.id for product in products]
    #         prod_tmpl_ids = [product.product_tmpl_id.id for product in products]
    #
    #     # Load all rules
    #     self._cr.execute(
    #         'SELECT item.id '
    #         'FROM product_pricelist_item AS item '
    #         'LEFT JOIN product_category AS categ '
    #         'ON item.categ_id = categ.id '
    #         'WHERE (item.product_tmpl_id IS NULL OR item.product_tmpl_id = any(%s))'
    #         'AND (item.product_id IS NULL OR item.product_id = any(%s))'
    #         'AND (item.categ_id IS NULL OR item.categ_id = any(%s)) '
    #         'AND (item.pricelist_id = %s) '
    #         'AND (item.date_start IS NULL OR item.date_start<=%s) '
    #         'AND (item.date_end IS NULL OR item.date_end>=%s)'
    #         'ORDER BY item.applied_on, item.min_quantity desc, categ.parent_left desc',
    #         (prod_tmpl_ids, prod_ids, categ_ids, self.id, date, date))
    #
    #     item_ids = [x[0] for x in self._cr.fetchall()]
    #
    #     items = self.env['product.pricelist.item'].browse(item_ids)
    #     results = {}
    #     for product, qty, partner in products_qty_partner:
    #         results[product.id] = 0.0
    #         suitable_rule = False
    #
    #         # Final unit price is computed according to `qty` in the `qty_uom_id` UoM.
    #         # An intermediary unit price may be computed according to a different UoM, in
    #         # which case the price_uom_id contains that UoM.
    #         # The final price will be converted to match `qty_uom_id`.
    #         qty_uom_id = self._context.get('uom') or product.uom_id.id
    #         price_uom_id = product.uom_id.id
    #         qty_in_product_uom = qty
    #         if qty_uom_id != product.uom_id.id:
    #             try:
    #                 qty_in_product_uom = self.env['uom.uom'].browse([self._context['uom']])._compute_quantity(qty, product.uom_id)
    #             except UserError:
    #                 # Ignored - incompatible UoM in context, use default product UoM
    #                 pass
    #
    #         # if Public user try to access standard price from website sale, need to call price_compute.
    #         # TDE SURPRISE: product can actually be a template
    #         #price = product.price_compute('list_price')[product.id]
    #         price = False
    #         price_uom = self.env['uom.uom'].browse([qty_uom_id])
    #         for rule in items:
    #             if rule.min_quantity and qty_in_product_uom < rule.min_quantity:
    #                 continue
    #             if is_product_template:
    #                 if rule.product_tmpl_id and product.id != rule.product_tmpl_id.id:
    #                     continue
    #                 if rule.product_id and not (product.product_variant_count == 1 and product.product_variant_id.id == rule.product_id.id):
    #                     # product rule acceptable on template if has only one variant
    #                     continue
    #             else:
    #                 if rule.product_tmpl_id and product.product_tmpl_id.id != rule.product_tmpl_id.id:
    #                     continue
    #                 if rule.product_id and product.id != rule.product_id.id:
    #                     continue
    #
    #             if rule.categ_id:
    #                 cat = product.categ_id
    #                 while cat:
    #                     if cat.id == rule.categ_id.id:
    #                         break
    #                     cat = cat.parent_id
    #                 if not cat:
    #                     continue
    #
    #             if rule.base == 'pricelist' and rule.base_pricelist_id:
    #                 price_tmp = rule.base_pricelist_id._compute_price_rule([(product, qty, partner)])[product.id][0]  # TDE: 0 = price, 1 = rule
    #                 price = rule.base_pricelist_id.currency_id.compute(price_tmp, self.currency_id, round=False)
    #             else:
    #                 # if base option is public price take sale price else cost price of product
    #                 # price_compute returns the price in the context UoM, i.e. qty_uom_id
    #                 price = product.price_compute(rule.base)[product.id]
    #
    #             convert_to_price_uom = (lambda price: product.uom_id._compute_price(price, price_uom))
    #             if price is not False:
    #                 if rule.compute_price == 'fixed':
    #                     price = convert_to_price_uom(rule.fixed_price)
    #                 elif rule.compute_price == 'percentage':
    #                     if rule.pricelist_id.discount_policy == 'with_discount':
    #                         price = price
    #                     else:
    #                         price = (price - (price * (rule.percent_price / 100))) or 0.0
    #                 else:
    #                     # complete formula
    #                     price_limit = price
    #                     if rule.pricelist_id.discount_policy == 'with_discount':
    #                         price = price
    #                     else:
    #                         price = (price - (price * (rule.price_discount / 100))) or 0.0
    #                     if rule.price_round:
    #                         price = tools.float_round(price, precision_rounding=rule.price_round)
    #
    #                     if rule.price_surcharge:
    #                         price_surcharge = convert_to_price_uom(rule.price_surcharge)
    #                         price += price_surcharge
    #
    #                     if rule.price_min_margin:
    #                         price_min_margin = convert_to_price_uom(rule.price_min_margin)
    #                         price = max(price, price_limit + price_min_margin)
    #
    #                     if rule.price_max_margin:
    #                         price_max_margin = convert_to_price_uom(rule.price_max_margin)
    #                         price = min(price, price_limit + price_max_margin)
    #                 suitable_rule = rule
    #             break
    #         # Final price conversion into pricelist currency
    #         if suitable_rule and suitable_rule.compute_price != 'fixed' and suitable_rule.base != 'pricelist':
    #             price = product.currency_id.compute(price, self.currency_id, round=False)
    #
    #         results[product.id] = (price, suitable_rule and suitable_rule.id or False)
    #     return results

    
class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"
    
    price_discount = fields.Float('Price Discount', default=0, digits=(16, 2))
    percent_price = fields.Float('Percentage Price')
    discount_policy = fields.Selection(related='pricelist_id.discount_policy', store=True, copy=False)
    
    # discount_policy = fields.Selection([
    #     ('with_discount', 'Discount included in the price'),
    #     ('without_discount', 'Show public price & discount to the customer')], related='pricelist_id.discount_policy', default='with_discount', store=True, copy=False)
    
    #@api.multi
    @api.constrains('product_id', 'applied_on', 'product_tmpl_id', 'categ_id')
    def _check_constraint(self):
        for item in self:
            
            print("\n item --- ", item)

            if item.applied_on == '0_product_variant':
                domain = [
                    ('product_id', '=', item.product_id.id),
                    ('applied_on', '=', item.applied_on),
                    ('id', '!=', item.id),
                    ('product_id', '!=', False),
                    ('pricelist_id', '=', item.pricelist_id.id),
                    ]
                
                print("\n domain --- ", domain)
                
                all_item = self.search_count(domain)

                print("\n all item --- ", all_item)

                if not self.env.registry.in_test_mode():
                    if all_item:
                        raise ValidationError(_("PriceList product variant duplication error!.\nKindly remove the duplicated record of '%s'") % (item.product_id.display_name))
                #     # raise ValidationError(_("PriceList product variant duplication error!.\nKindly remove the duplicated record of '%s'") % (item.product_id.name_get()[0][1]))
            
            elif item.applied_on == '1_product':
                domain = [
                    ('product_tmpl_id', '=', item.product_tmpl_id.id),
                    ('applied_on', '=', item.applied_on),
                    ('id', '!=', item.id),
                    ('product_tmpl_id', '!=', False),
                    ('pricelist_id', '=', item.pricelist_id.id),
                    ]
                all_item = self.search_count(domain)
                
                if not self.env.registry.in_test_mode():
                    if all_item:
                        raise ValidationError(_("PriceList product duplication error!.\nKindly remove the duplicated record of '%s'") % (item.product_tmpl_id.display_name))
                        # raise ValidationError(_("PriceList product duplication error!.\nKindly remove the duplicated record of '%s'") % (item.product_tmpl_id.name_get()[0][1]))
            elif item.applied_on == '2_product_category':
                domain = [
                    ('categ_id', '=', item.categ_id.id),
                    ('applied_on', '=', item.applied_on),
                    ('id', '!=', item.id),
                    ('categ_id', '!=', False),
                    ('pricelist_id', '=', item.pricelist_id.id),
                    ]
                all_item = self.search_count(domain)
                
                if not self.env.registry.in_test_mode():
                    if all_item:
                        # raise ValidationError(_("PriceList category duplication error!.\nKindly remove the duplicated record of category '%s'")% (item.categ_id.name_get()[0][1]))
                        raise ValidationError(_("PriceList category duplication error!.\nKindly remove the duplicated record of category '%s'")% (item.categ_id.display_name))
            
            elif item.applied_on == '3_global':
                domain = [
                    ('applied_on', '=', item.applied_on),
                    ('id', '!=', item.id),
                    ('pricelist_id', '=', item.pricelist_id.id),
                    ]
                all_item = self.search_count(domain)
                
                if not self.env.registry.in_test_mode():
                    if all_item:
                        raise ValidationError(_("PriceList global category duplication error!.\nKindly remove the duplicated record of global category"))
            else:
                continue

class ProductPackageProduct(models.Model):
    _name = "product.package.product"
    _description = "Sub Packaging Products"
    _rec_name = "product_id"
    
    product_id = fields.Many2one('product.product', string='Parent Product', required=True, ondelete='cascade')
    product_pack_id = fields.Many2one('product.product', string='Product', copy=False, required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', copy=False, required=True)
    # product_qty = fields.Float(string='Qty Consumable (For 1 Base Unit)', default=1.00, copy=False, required=True, digits=dp.get_precision('Product Unit of Measure'))
    product_qty = fields.Float(string='Qty Consumable (For 1 Base Unit)', default=1.00, copy=False, required=True, digits='Product Unit of Measure')
    
    @api.onchange('product_pack_id')
    def onchange_product_pack_id(self):
        if self.product_pack_id:
            self.uom_id = self.product_pack_id.uom_id and self.product_pack_id.uom_id.id or False
            
class QtyProductDiscount(models.Model):
    _name = "qty.category.discount"
    _description = "Quantity and Product Category Wise Discount"
    _rec_name = "category_id"
    
    #warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', copy=False, required=True)
    category_id = fields.Many2one('product.category', string='Product Category', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env['res.company']._company_default_get('qty.category.discount'))
    # min_qty = fields.Float(string='Minimum Qty', default=1.00, copy=False, required=True, digits=dp.get_precision('Product Unit of Measure'))
    min_qty = fields.Float(string='Minimum Qty', default=1.00, copy=False, required=True, digits='Product Unit of Measure')
    max_qty = fields.Float(string='Maximum Qty', default=1.00, copy=False, required=True, digits='Product Unit of Measure')
    # max_qty = fields.Float(string='Maximum Qty', default=1.00, copy=False, required=True, digits=dp.get_precision('Product Unit of Measure'))
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    discount = fields.Float(string='Discount (%)', required=True)
    description = fields.Text(string='Description')
    
