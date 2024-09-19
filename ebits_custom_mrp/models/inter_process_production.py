# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import time
import math
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp

class LabourGroup(models.Model):
    _name = "labour.group"
    _description = "Labour Group"
    
    name = fields.Char(string='Name', size=64, required=True, copy=False)
    code = fields.Char(string='Code', size=32, required=True, copy=False)
    rate_lines = fields.One2many('labour.rate.line', 'group_id', string='Labour Rate')
    
class LabourRateLine(models.Model):
    _name = 'labour.rate.line'
    _description = 'Labour Rate Line'
    
    group_id = fields.Many2one('labour.group', string='Labour Group')
    date = fields.Date(string='Date', required=True)
    nssf = fields.Float(string='NSSF (%)', copy=False, digits='Product Price')
    rate = fields.Float(string='Rate', required=True, digits='Product Price')

class LabourLabour(models.Model):
    _name = "labour.labour"
    _description = "Labour"
    
    name = fields.Char(string='Name', size=64, required=True)
    code = fields.Char(string='Code', size=32, required=True)
    group_id = fields.Many2one('labour.group', string='Labour Group')
    
class InterProcessProduction(models.Model):
    _name = "inter.process.production"
    _description = "Inter Process Production"
    _rec_name = "user_id"
    _order = "id desc"
    
    date = fields.Date(string='Date', default=fields.Date.context_today, readonly=True, copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', required=True, string='Warehouse/Branch', copy=False)
    user_id = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user, readonly=True, copy=False)
    shift_type = fields.Selection([('shift_1', 'Shift 1'), ('shift_2', 'Shift 2'), ('shift_3', 'Shift 3')], string="Shift", readonly=True, copy=False, required=True)
    mrp_production_id = fields.Many2one('mrp.production', string='Manufacturing order', ondelete='cascade')
    production_line = fields.One2many('production.line.detail', 'production_id', string='Production', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'), 
        ('done', 'Done')], string='State', readonly=True, default='draft', copy=False)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('inter.process.production'), copy=False)
    
    # @api.multi
    def move_to_done(self):
        for each in self:
            if not each.production_line:
                raise UserError(_('Production Line has to be entered'))
            for line  in each.production_line:
                if line.product_qty <= 0.00:
                    raise UserError(_('Quantity must greater than zero'))
                line.state = 'done'
            each.state = 'done'
        return True
            
    # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can remove a form which is only in the draft state.'))    
        return super(InterProcessProduction, self).unlink()
    
class ProductionLineDetail(models.Model):
    _name = "production.line.detail"
    _description = "Production Line"
    
    production_id = fields.Many2one('inter.process.production', string='Inter Process Production')
    date = fields.Date(string='Date', copy=False, related='production_id.date' )
    product_id = fields.Many2one('product.product', string='Product', copy=False)
    uom_id = fields.Many2one('uom.uom', string='UOM', copy=False)
    process_id = fields.Many2one('mrp.workcenter', string='Process', copy=False)
    product_qty = fields.Float(string='Product Quantity', required=True, copy=False, digits='Product Unit of Measure')
    labour_id = fields.Many2one('labour.labour', string='Labour', copy=False)
    mrp_production_id = fields.Many2one('mrp.production', string="Manufacturing Order", copy=False, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', related="production_id.company_id", store=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse/Branch', related="production_id.warehouse_id", store=True)
    state = fields.Selection([
        ('draft', 'Draft'), 
        ('done', 'Done')], string='State', default='draft', store=True, readonly=True, copy=False)
        
    # @api.multi
    def action_done(self):
        self.state = 'done'
    
    @api.onchange('product_id')
    def onchange_product_id(self):
        warning = {}
        if self.product_id:
            self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
            if self.mrp_production_id:
                if self.product_id.id != self.mrp_production_id.product_id.id:
                    self.product_id = self.mrp_production_id.product_id and self.mrp_production_id.product_id.id or False
                    warning = {
                            'title': _('Warning'),
                            'message': _('Product cannot be changed.')}
                    return {'warning': warning} 
        else:
            self.uom_id = False
        
    @api.onchange('uom_id')
    def onchange_uom_id(self):
        warning = {}
        if self.product_id and self.uom_id:
            if self.uom_id.id != self.product_id.uom_id.id:
                self.uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed.')}
        return {'warning': warning}
        
    @api.onchange('product_qty')
    def _onchange_product_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id:
            if self.product_qty and (not self.uom_id.allow_decimal_digits):
                integer, decimal = divmod(self.product_qty, 1)
                if decimal:
                    self.product_qty = 0.00
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.uom_id.name)}
                    return {'warning': warning}
        
    # @api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_('You can remove an item which is only in the draft state.'))    
        return super(ProductionLineDetail,self).unlink() 
    
