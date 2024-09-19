# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import time
import math
import pytz
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

class CustomerUpdateWizard(models.TransientModel):
    _name = "customer.data.update.wizard"
    _description = "Update Salesperson and Sales Manager Wizard"
    
    type = fields.Selection([('manager', 'Sales Manager'), ('user', 'Salesperson')], string="Update Type")
    existing_manager_id = fields.Many2one('res.users', string='Existing Sales Manager')
    new_manager_id = fields.Many2one('res.users', string='New Sales Manager')
    existing_sales_person_id = fields.Many2one('res.users', string='Existing Salesperson')
    new_sales_person_id = fields.Many2one('res.users', string='New Salesperson')
    
    #@api.multi
    def action_update_sales_manager(self):
        partner_obj = self.env['res.partner']
        partner_record = partner_obj.search([('sales_manager_id', '=', self.existing_manager_id.id)]) 
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in partner_record:
            if each.changes_history:
                history = "\n" + each.changes_history
            each.write({
            'sales_manager_id': self.new_manager_id and self.new_manager_id.id or False,
            'changes_history': 'Previous Manager ' + str(self.existing_manager_id.name) + ' has been changed to New Manager ' + str(self.new_manager_id.name) + ' Changed By ' +  str(self.env.user.name) + ' on '+ date + history
             })
        return True
        
    #@api.multi
    def action_update_sales_person(self):
        partner_obj = self.env['res.partner']
        partner_record = partner_obj.search([('user_id', '=', self.existing_sales_person_id.id)]) 
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in partner_record:
            if each.changes_history:
                history = "\n" + each.changes_history
            each.write({
            'user_id': self.new_sales_person_id and self.new_sales_person_id.id or False,
            'changes_history': 'Previous Salesperson ' + str(self.existing_sales_person_id.name) + ' has been changed to New Salesperson ' + str(self.new_sales_person_id.name) + ' Changed By ' +  str(self.env.user.name) + ' on '+ date + history
             })
        return True
        
    @api.onchange('existing_sales_person_id')
    def onchange_existing_sales_person_id(self):
        if self.existing_sales_person_id != True:
            self.new_sales_person_id = False
            
    @api.onchange('existing_manager_id')
    def onchange_existing_manager_id(self):
        if self.existing_manager_id != True:
            self.new_manager_id = False
        
