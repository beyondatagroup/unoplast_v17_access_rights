# -*- coding: utf-8 -*-
# Part of EBITS TechCon

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

class PoShippingMode(models.Model):
    _name = "po.shipping.mode"
    _description = "PO Shipping Mode"
    
    name = fields.Char(string="Name", size=64, required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env['res.company']._company_default_get('po.shipping.mode'))
    
    @api.constrains('name')
    def _check_name(self):
        for shipping in self:
            domain = [
                ('name', '=', shipping.name),
                ('id', '!=', shipping.id)
                ]
            all_shipping = self.search_count(domain)
            
            if not self.env.registry.in_test_mode():
                if all_shipping:
                    raise ValidationError(_('Shipping Mode duplication error!.\n Already shipping mode created with same name'))
        
#PoShippingMode()

class PurchaseOrderLcMaster(models.Model):
    _name = "purchase.order.lc.master"
    _description = "Purchase Order LC Master"
    _order = "id desc"
    
    name = fields.Char(string="Name",size=64, required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env['res.company']._company_default_get('purchase.order.lc.master'))
    
    @api.constrains('name')
    def _check_name(self):
        for lc in self:
            domain = [
                ('name', '=', lc.name),
                ('id', '!=', lc.id)
                ]
            all_lc = self.search_count(domain)
            if not self.env.registry.in_test_mode():
                if all_lc:
                    raise ValidationError(_('LC no duplication error!.\nThers is a purchase order already mapped with same LC no!'))
    
#PurchaseOrderLcMaster()

class StockReportMaster(models.Model):
    _name = "stock.report.master"
    _description = "Stock Report Configuration Master"
    
    name = fields.Char(string='Name', required=True)
    categ_ids = fields.Many2many('product.category', string='Product Categories', required=True)
    
    @api.constrains('name')
    def _check_name(self):
        for master in self:
            domain = [
                ('name', '=', master.name),
                ('id', '!=', master.id)
                ]
            all_master = self.search_count(domain)
            
            if not self.env.registry.in_test_mode():
                if all_master:
                    raise ValidationError(_('Report Configuration Master duplication error!.\nThers is a same name  already mapped with same master!'))
