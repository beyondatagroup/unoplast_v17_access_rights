# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import re
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
from odoo.modules.module import get_module_resource
import odoo.addons.decimal_precision as dp

class Employee(models.Model):
    _inherit = "hr.employee"
    
    @api.depends('loan_lines.remaining_amt', 'loan_lines')
    def _get_loan_balance(self):
        amount = 0.00
        for each in self:
            amount = 0.00
            for line in each.loan_lines:
                amount += line.remaining_amt
            each.loan_balance = amount
    
    doj = fields.Date('Date of Join')
    ppf_no = fields.Char('PPF No')
    nssf_no = fields.Char('NSSF No')
    employee_code = fields.Char('Employee Code')
    job_id = fields.Many2one('hr.job', string='Designation')
    production_unit_id = fields.Many2one('res.production.unit', string='Unit')
    loan_lines = fields.One2many('hr.loan', 'employee_id' , string='Loan EMI Lines', copy=False)
    loan_balance = fields.Float(compute='_get_loan_balance', string='Loan Balance', readonly=True, store=True, copy=False, digits='Product Price')
    # loan_balance = fields.Float(compute='_get_loan_balance', string='Loan Balance', readonly=True, store=True, copy=False, digits=dp.get_precision('Product Price'))
    basic = fields.Float(string='Basic', digits='Product Price')
    # basic = fields.Float(string='Basic', digits=dp.get_precision('Product Price'))
    transp = fields.Float(string='Transport', digits='Product Price')
    # transp = fields.Float(string='Transport', digits=dp.get_precision('Product Price'))
    hra_earnings = fields.Float(string='HRA', digits='Product Price')
    # hra_earnings = fields.Float(string='HRA', digits=dp.get_precision('Product Price'))
    prof_all = fields.Float(string='Professional', digits='Product Price')
    # prof_all = fields.Float(string='Professional', digits=dp.get_precision('Product Price'))
    misc_earnings = fields.Float(string='Misc', digits='Product Price')
    # misc_earnings = fields.Float(string='Misc', digits=dp.get_precision('Product Price'))
    over_time = fields.Float(string='OT', digits='Product Price')
    # over_time = fields.Float(string='OT', digits=dp.get_precision('Product Price'))
    child_education_earnings = fields.Float(string='Earnings Child Education', digits='Product Price')
    # child_education_earnings = fields.Float(string='Earnings Child Education', digits=dp.get_precision('Product Price'))
    bonus_earnings = fields.Float(string='Bonus', digits='Product Price')
    # bonus_earnings = fields.Float(string='Bonus', digits=dp.get_precision('Product Price'))
    night_allowance = fields.Float(string='Night Allownace', digits='Product Price')
    # night_allowance = fields.Float(string='Night Allownace', digits=dp.get_precision('Product Price'))
    arres = fields.Float(string='Arrears', digits='Product Price')
    # arres = fields.Float(string='Arrears', digits=dp.get_precision('Product Price'))
    leave_allowance = fields.Float(string='Leave Allownace', digits='Product Price')
    # leave_allowance = fields.Float(string='Leave Allownace', digits=dp.get_precision('Product Price'))
    child_education_deductions = fields.Float(string='Deductions Child Education', digits='Product Price')
    # child_education_deductions = fields.Float(string='Deductions Child Education', digits=dp.get_precision('Product Price'))
    hra_deductions = fields.Float(string='HRA Deduction', digits='Product Price')
    # hra_deductions = fields.Float(string='HRA Deduction', digits=dp.get_precision('Product Price'))
    coin_adjustment = fields.Float(string='Coin Adj', digits='Product Price')
    # coin_adjustment = fields.Float(string='Coin Adj', digits=dp.get_precision('Product Price'))
    pf_type = fields.Selection([('npf', 'NPF'), ('ppf', 'PPF')], string='PF Type', default='npf')
    pf_value = fields.Float('PF Percentage')
    tuico = fields.Boolean('Tuico Applicable?', default=False)
    tuico_value = fields.Float('Tuico Percentage')
    
    address_home_id = fields.Many2one('res.partner', string='Home Address')

    is_usr_button_visible = fields.Boolean()

     
    def write(self, vals):
        if 'partner_id' in vals:
            partner_id = vals.get('partner_id')
            if partner_id:
                self.env['res.partner'].browse(partner_id).employee = True
        return super(Employee, self).write(vals)
    
    
    # # logic to have create user button invisible when we open a new record if it has related user then button will be 
    # # invisible
    # def web_read(self, specification):
    #     for rec in self:            
    #         if rec.user_id:
    #             rec.is_usr_button_visible = True

    #     res = super(Employee, self).web_read(specification)
    #     return res
        
    # def bd_create_user(self):

    #     # when this button is clicked what events needs to be performed ? 
    #     # 1. If the user is not created then crete the user 
    #     # 2. If user of same name and email is created then do not create new user 
    #     # 3. If user is already created then hide the button for the record

    #     user_obj = self.env['res.users']

    #     # print("\n button clicked !!")

    #     for res in self:

    #         if not res.work_email:
    #             raise UserError(_("Working email address is mandatory to create home address of employee!."))
            
    #         # work email and work mob is not persistant after creating user so storing them in variables 
    #         per_work_email = res.work_email
    #         per_work_mob = res.mobile_phone

    #         print("\n working email ---- ", res.work_email)

    #         is_user = user_obj.search([("name", "ilike", res.name), ("login", "ilike", res.work_email)], limit=1)

    #         if not is_user:

    #             # need to create the user
    #             user_id_new = user_obj.create({
    #                 "name": res.name,
    #                 "login": res.work_email
    #             })

    #             # and put the newly created user in related user 
    #             res.user_id = user_id_new.id

    #             # and then hide the button 
    #             res.is_usr_button_visible = True

    #             # when user gets created assigning the values to the record variables 
    #             res.work_email = per_work_email
    #             res.mobile_phone = per_work_mob

                
    #     # for each in self:
            
    #     #     if not each.work_email:
    #     #         raise UserError(_("Working email address is mandatory to create User!."))
            
    #     #     same_user = user_obj.search([("name", "ilike", each.name), ("login", "ilike", each.work_email)], limit=1)

    #     #     user_id = False

    #     #     if each.user_id:

    #     #         each.work_email = each.user_id.login

    #     #         raise UserError(_("You can not have two users with the same login !"))

            
    #     #     if not same_user:

    #     #         # create user   
                
    #     #         user_id = user_obj.create({
    #     #             "name":each.name, 
    #     #             "login": each.work_email
    #     #         })

    #     #         each.work_email = user_id.login

    #     #     else:
    #     #         raise UserError(_("You can not have two users with the same login !"))
                        
    #     #     if user_id:
    #     #         each.user_id = user_id.id
            
        
    #     #     if each.address_home_id:

    #     #         user_id = user_obj.create({
    #     #             'name': each.name, 
    #     #             'login': each.work_email, 
    #     #             })
    #     #     else:
    #     #         partner_id = each.create_partner()
    #     #         user_id = user_obj.create({
    #     #             'name': each.name, 
    #     #             'login': each.work_email,
    #     #             })
    #     #     each.user_id = user_id and user_id.id or False
    #     # return True
        
     
    # def create_partner(self):
    #     partner_obj = self.env['res.partner']
    #     partner_id = False
    #     for each in self:
    #         if not each.work_email:
    #             raise UserError(_("Working email address is mandatory to create home address of employee!."))
    #         if not each.address_home_id:
    #             address_home_id = partner_obj.create({
    #                 'name': each.name, 
    #                 'customer': False,
    #                 'supplier': False,
    #                 'employee': True,
    #                 'image': each.image,
    #                 'is_company': False,
    #                 'email': each.work_email,
    #                 'phone': each.work_phone,
    #                 'mobile': each.mobile_phone,
    #                 'partner_code': 'EMP-' + (each.employee_code and each.employee_code or ''),
    #                 'transaction_currency_id': each.company_id.currency_id.id,
    #                 })
    #             each.address_home_id = address_home_id and address_home_id.id or False
    #             partner_id = address_home_id and address_home_id.id or False
    #     return partner_id

    @api.model
    def get_birthday(self):
        birthday_wishes = ""
        today = datetime.now()
        today_month_day = '%-' + today.strftime('%m') + '-' + today.strftime('%d')
        ids = self.search([('birthday', 'like', today_month_day)])
        if not ids:
            return birthday_wishes
        for each_id in ids:
            if birthday_wishes:
                birthday_wishes += ', \n'
            birthday_wishes += "Happy Birthday " + each_id.name + " !!!."
        if birthday_wishes:
            company = self.env.user.company_id.name
            birthday_wishes = company + ' Wishes You !!! ' + '\n' + birthday_wishes
        return birthday_wishes

    def _compute_display_name(self):
        if self.check_access_rights('read', raise_exception=False):
            return super()._compute_display_name()
        for employee in self:
            name = employee.name
            if employee.employee_code:
                name = "[%s] %s" % (employee.employee_code, employee.name)
            employee.display_name = name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if not args:
            args = []
        if name:
            positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
            employee = self.env['hr.employee']
            if operator in positive_operators:
                employee = self.search([('employee_code', '=', name)] + args, limit=limit)
            if not employee and operator not in expression.NEGATIVE_TERM_OPERATORS:
                employee = self.search(args + [('employee_code', operator, name)], limit=limit)
                if not limit or len(employee) < limit:
                    limit2 = (limit - len(employee)) if limit else False
                    employee += self.search(args + [('name', operator, name), ('id', 'not in', employee.ids)], limit=limit2)
            elif not employee and operator in expression.NEGATIVE_TERM_OPERATORS:
                employee = self.search(args + ['&', ('employee_code', operator, name), ('name', operator, name)], limit=limit)
            if not employee and operator in positive_operators:
                ptrn = re.compile(r'(\[(.*?)\])')
                res = ptrn.search(name)
                if res:
                    employee = self.search([('employee_code', '=', res.group(2))] + args, limit=limit)
        else:
            employee = self.search(args, limit=limit)
        return employee.name_get()
        
    @api.constrains('parent_id')
    def _check_parent_id(self):
        for employee in self:
            
            if not self.env.registry.in_test_mode():
                if not employee._check_recursion():
                    raise UserError(_('Error! You cannot create recursive hierarchy of same Employee(s) as manager.'))
                
class Department(models.Model):
    _inherit = "hr.department"
            
    @api.constrains('parent_id')
    def _check_parent_id(self):
        
        if not self.env.registry.in_test_mode():
            if not self._check_recursion():
                raise UserError(_('Error! You cannot create recursive same departments as parent department.'))

