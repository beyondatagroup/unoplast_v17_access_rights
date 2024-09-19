# -*- coding: utf-8 -*-
# Part of EBITS TechCon.

import time
import babel
import locale
import pytz
from datetime import datetime
from dateutil import relativedelta
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, tools, _

class IncomeTaxStructure(models.Model):
    _name = "income.tax.structure"
    _description = "Income Tax Structure"
    
    name = fields.Char('Name', required=True)
    active = fields.Boolean('Active', default=True)
    date_from = fields.Date('From Date', required=True)
    date_to = fields.Date('To Date', required=True)
    tax_line = fields.One2many('income.tax.structure.line', 'tax_id', string='Income Tax line')
    
    _sql_constraints = [
        ('number_uniq', 'unique(date_from, date_to)', "Tax structure from date and to date must be unique per Company!"),
        ]
    
     
    @api.constrains('date_from', 'date_to')
    def _check_date_from_to(self):
        for each in self:
            
            if not self.env.registry.in_test_mode():
                if each.date_from > each.date_to:
                    raise ValidationError(_("Tax structure end date must be greater than the start date"))
                
     
    def unlink(self):
        for structure in self:
            if not self.env.registry.in_test_mode():
                raise UserError(_("You cannot delete an income tax structure"))
        return super(IncomeTaxStructure, self).unlink()
    
class IncomeTaxStructureLine(models.Model):
    _name = "income.tax.structure.line"
    _description = "Income Tax Structure Line"
    
    tax_id = fields.Many2one('income.tax.structure', 'Tax Structure', ondelete="cascade")
    tax_value_from = fields.Float('Value From', required=True)
    tax_value_to = fields.Float('Value To', required=True)
    tax_percentage = fields.Float('Percentage', required=True)
    tax_amount = fields.Float('Amount', required=True)
    
    _sql_constraints = [
        ('number_uniq', 'unique(tax_value_from, tax_value_to, tax_id)', "Tax structure from value from and value to must be unique per Company!"),
        ]

class HrPayrollCustom(models.Model):
    _name = "hr.payroll.custom"
    _description = "HR Payroll Customized Management"
    _order = "date desc, id"
    
     
    def _compute_payslip_count(self):
        for payslip in self:
            payslip.payslip_count = len(payslip.payroll_lines)
    
    sequence = fields.Char(string='Sequence', readonly=True, states={'draft':[('readonly', False)]}, copy=False)
    user_id = fields.Many2one('res.users', string='Creator', default=lambda self: self.env.user, readonly=True, copy=False)
    date = fields.Date(string='Created Date', default=fields.Datetime.now, readonly=True, copy=False)
    approved_id = fields.Many2one('res.users', string='Approver', readonly=True, copy=False)
    approved_date = fields.Date(string='Approved Date', readonly=True, copy=False)
    date_from = fields.Date(string='Period Start', default=time.strftime('%Y-%m-01'), readonly=True, states={'draft':[('readonly', False)]}, required=True, copy=False)
    date_to = fields.Date(string='Period End', default=str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10], readonly=True, states={'draft':[('readonly', False)]}, required=True, copy=False)
    name = fields.Char(string='Name', readonly=True, states={'draft':[('readonly', False)]}, required=True, copy=False)
    payroll_lines = fields.One2many('hr.payroll.custom.line', 'payroll_id', 'Payroll Lines', readonly=True, states={'draft':[('readonly', False)]}, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'), 
        ('wait', 'Waiting For Approval'), 
        ('approved', 'Approved'), 
        ('done', 'Done'), 
        ('cancel', 'Cancelled')
        ], string='State', readonly=True, default='draft', copy=False)
    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False,
        default=lambda self: self.env['res.company']._company_default_get(),
        states={'draft': [('readonly', False)]})
    payslip_count = fields.Integer(compute='_compute_payslip_count', string="Payslip Count")
    history = fields.Text(string='History', readonly=True, copy=False)
    production_unit_id = fields.Many2one('res.production.unit', string='Unit', readonly=True, states={'draft':[('readonly', False)]}, required=True, copy=False)
    earning_line = fields.One2many('employee.payslip.earning.line', 'payroll_id', string='Earnings')
    deduction_line = fields.One2many('employee.payslip.deduction.line', 'payroll_id', string='Deductions')
    journal_id = fields.Many2one('account.journal', 'Journal', readonly=True, states={'draft': [('readonly', False)]}, copy=False)
    move_id = fields.Many2one('account.move', 'Journal Entry', readonly=True, copy=False)
    account_date = fields.Date('Accounting Date', copy=False)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', copy=False)
    
     
    @api.constrains('date_from', 'date_to')
    def _check_date_from_to(self):
        for each in self:
            
            if not self.env.registry.in_test_mode():
                if each.date_from > each.date_to:
                    raise ValidationError(_("Payroll period end date must be greater than the period start date"))
    
    @api.onchange('date_from', 'date_to')
    def onchange_period(self):
        if (not self.date_from) or (not self.date_to):
            self.name = ""
            return
        date_from = self.date_from
        date_to = self.date_to

        ttyme = datetime.fromtimestamp(time.mktime(time.strptime(date_from, "%Y-%m-%d")))
        locale = self.env.context.get('lang', 'en_US')
        self.name = _('Salary Slip for %s') % (tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale)))

     
    def action_send_for_approval(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:

            if not self.env.registry.in_test_mode():

                if not each.earning_line:
                    raise UserError(_("Earnings tab is empty.\nKindly fill the details to proceed!"))
                if not each.deduction_line:
                    raise UserError(_("Deductions tab is empty.\nKindly fill the details to proceed!"))
            
            if each.history:
                history = each.history + "\n" 
            each.write({
                'state': 'wait',
                'history': history + "This document is sent for approval by " + str(self.env.user.name) + " on " + date + " for " + each.name
                })
        return True
        
     
    def action_approve(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            if each.history:
                history = each.history + "\n" 
            each.write({
                'approved_id': self.env.user.id,
                'approved_date': fields.Date.context_today(self),
                'state': 'approved',
                'history': history + "This document is approved by " + str(self.env.user.name) + " on " + date + " for " + each.name
                })
        return True
        
     
    def action_set_draft(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            if each.history:
                history = each.history + "\n" 
            each.write({
                'approved_id': False,
                'approved_date': False,
                'state': 'draft',
                'history': history + "This document is set to draft by " + str(self.env.user.name) + " on " + date + " for " + each.name
                })
        return True
        
     
    def action_summary_total(self):
        earning_obj = self.env['employee.payslip.earning.line']
        dedection_obj = self.env['employee.payslip.deduction.line']
        earning_list = []
        deduction_list = []
        basic, transp, hra_earnings, prof_all, misc_earnings, over_time, child_education_earnings = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
        bonus_earnings, night_allowance, arres, leave_allowance = 0.00, 0.00, 0.00, 0.00
        npf, payee, ppf, tuico, salary_advance, loan, child_education_deductions = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
        hra_deductions, bonus_deductions, misc, absent, coin_adjustment = 0.00, 0.00, 0.00, 0.00, 0.00
        for each in self:
            models.Model.unlink(each.earning_line)
            models.Model.unlink(each.deduction_line)
            for line in each.payroll_lines:
                basic += line.basic
                transp += line.transp
                hra_earnings += line.hra_earnings
                prof_all += line.prof_all
                misc_earnings += line.misc_earnings
                over_time += line.over_time
                child_education_earnings += line.child_education_earnings
                bonus_earnings += line.bonus_earnings
                night_allowance += line.night_allowance
                arres += line.arres
                leave_allowance += line.leave_allowance
                npf += line.npf
                payee += line.payee
                ppf += line.ppf
                tuico += line.tuico
                salary_advance += line.salary_advance
                loan += line.loan
                child_education_deductions += line.child_education_deductions
                hra_deductions += line.hra_deductions
                bonus_deductions += line.bonus_deductions
                misc += line.misc
                absent += line.absent
                coin_adjustment += line.coin_adjustment
            for line_earn in each.production_unit_id.earning_line:
                if line_earn.earning_type == 'basic':
                    amount = basic
                elif line_earn.earning_type == 'transp':
                    amount = transp
                elif line_earn.earning_type == 'hra_earnings':
                    amount = hra_earnings
                elif line_earn.earning_type == 'prof_all':
                    amount = prof_all
                elif line_earn.earning_type == 'misc_earnings':
                    amount = misc_earnings
                elif line_earn.earning_type == 'over_time':
                    amount = over_time
                elif line_earn.earning_type == 'child_education_earnings':
                    amount = child_education_earnings
                elif line_earn.earning_type == 'bonus_earnings':
                    amount = bonus_earnings
                elif line_earn.earning_type == 'night_allowance':
                    amount = night_allowance
                elif line_earn.earning_type == 'arres':
                    amount = arres
                elif line_earn.earning_type == 'leave_allowance':
                    amount = leave_allowance
                else:
                    amount = 0.00  
                earning_obj.create({
                    'unit_id': each.production_unit_id and each.production_unit_id.id or False, 
                    'account_id': line_earn.account_id and line_earn.account_id.id or False,
                    'earning_type': line_earn.earning_type and line_earn.earning_type or '',
                    'payroll_id': each.id,
                    'amount': amount
                    })
            for line_deduc in each.production_unit_id.deduction_line:
                if line_deduc.deduction_type == 'npf':
                    amount = npf 
                elif line_deduc.deduction_type == 'payee':
                    amount = payee
                elif line_deduc.deduction_type == 'ppf':
                    amount = ppf 
                elif line_deduc.deduction_type == 'tuico':
                    amount = tuico 
                elif line_deduc.deduction_type == 'salary_advance':
                    amount = salary_advance 
                elif line_deduc.deduction_type == 'loan':
                    amount = loan 
                elif line_deduc.deduction_type == 'child_education_deductions':
                    amount = child_education_deductions 
                elif line_deduc.deduction_type == 'hra_deductions':
                    amount = hra_deductions 
                elif line_deduc.deduction_type == 'bonus_deductions':
                    amount = bonus_deductions 
                elif line_deduc.deduction_type == 'misc':
                    amount = misc 
                elif line_deduc.deduction_type == 'absent':
                    amount = absent 
                elif line_deduc.deduction_type == 'coin_adjustment':
                    amount = coin_adjustment
                else:
                    amount = 0.00
                dedection_obj.create({
                    'unit_id': each.production_unit_id and each.production_unit_id.id or False, 
                    'account_id': line_deduc.account_id and line_deduc.account_id.id or False,
                    'deduction_type': line_deduc.deduction_type and line_deduc.deduction_type or '',
                    'payroll_id': each.id,
                    'amount': amount
                    })
        return True 
        
     
    def action_create_journal_entries(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']
        earn_amount, deduc_amount, net_pay = 0.00, 0.00, 0.00
        move_id = False
        earning = ""
        deduction = ""
        for each in self:
            temp = []
            if each.history:
                history = each.history + "\n" 
            for earn_line in each.earning_line:
                if earn_line.earning_type == 'basic':
                    earning = 'Basic'
                elif earn_line.earning_type == 'transp':
                    earning = 'Transport'
                elif earn_line.earning_type == 'hra_earnings':
                    earning = 'HRA'
                elif earn_line.earning_type == 'prof_all':
                    earning = 'Professional'
                elif earn_line.earning_type == 'misc_earnings':
                    earning = 'Misc'
                elif earn_line.earning_type == 'over_time':
                    earning = 'OT'
                elif earn_line.earning_type == 'child_education_earnings':
                    earning = 'Earnings Child Education'
                elif earn_line.earning_type == 'bonus_earnings':
                    earning = 'Bonus'
                elif earn_line.earning_type == 'night_allowance':
                    earning = 'Night Allownace'
                elif earn_line.earning_type == 'arres':
                    earning = 'Arrears'
                elif earn_line.earning_type == 'leave_allowance':
                    earning = 'Leave Allownace'
                temp.append({
                        'name': each.name and each.name + " - " + earning or "",
                        'partner_id': False,
                        'account_id': earn_line.account_id and earn_line.account_id.id or False,
                        'debit': earn_line.amount and earn_line.amount or 0.00,
                        'credit': 0.00,
                        })
                earn_amount += earn_line.amount
            for deduc_line in each.deduction_line:
                deduc_amount += deduc_line.amount
                if deduc_line.deduction_type not in ('npf', 'ppf', 'salary_advance', 'loan'): 
                    if deduc_line.deduction_type == 'payee':
                        deduction = 'Payee'
                    elif deduc_line.deduction_type == 'tuico':
                        deduction = 'Tuico' 
                    elif deduc_line.deduction_type == 'child_education_deductions':
                        deduction = 'Deductions Child Education' 
                    elif deduc_line.deduction_type == 'hra_deductions':
                        deduction = 'HRA Deduction' 
                    elif deduc_line.deduction_type == 'bonus_deductions':
                        deduction = 'Bonus Deduction' 
                    elif deduc_line.deduction_type == 'misc':
                        deduction = 'Misc Deduction' 
                    elif deduc_line.deduction_type == 'absent':
                        deduction = 'Absent' 
                    elif deduc_line.deduction_type == 'coin_adjustment':
                        deduction = 'Coin Adj'
                    temp.append({
                            'name': each.name and each.name + " - " + deduction or "",
                            'partner_id': False,
                            'account_id': deduc_line.account_id and deduc_line.account_id.id or False,
                            'debit': 0.00,
                            'credit': deduc_line.amount and deduc_line.amount or 0.00,
                            })
            for line in each.payroll_lines:
                for line_deduc in line.production_unit_id.deduction_line:
                    deduction_type = ''
                    if line.npf > 0.00:
                        if line_deduc.deduction_type == 'npf':
                            deduction_type = 'NPF'
                            temp.append(each._fun_create_move_line_crdit(line.npf, line, line_deduc.account_id, deduction_type))
                    if line.ppf > 0.00:
                        if line_deduc.deduction_type == 'ppf':
                            deduction_type = 'PPF'
                            temp.append(each._fun_create_move_line_crdit(line.ppf, line, line_deduc.account_id, deduction_type))
                    if line.salary_advance > 0.00:
                        if line_deduc.deduction_type == 'salary_advance':
                            deduction_type = 'Salary Advance'
                            temp.append(each._fun_create_move_line_crdit(line.salary_advance, line, line_deduc.account_id, deduction_type)) 
                    if line.loan > 0.00:
                        if line_deduc.deduction_type == 'loan':
                            deduction_type = 'Loan'
                            temp.append(each._fun_create_move_line_crdit(line.loan, line, line_deduc.account_id, deduction_type)) 
            net_pay = (earn_amount - deduc_amount)
            if net_pay > 0.00:
                temp.append({
                        'name': each.name and each.name + " - " + each.production_unit_id.name or "",
                        'partner_id': False,
                        'account_id': each.production_unit_id.account_id and each.production_unit_id.account_id.id or 0.00,
                        'debit': 0.00,
                        'credit': net_pay and abs(net_pay) or 0.00,
                    })
            else:
                temp.append({
                        'name': each.name and each.name + " - " + each.production_unit_id.name or "",
                        'partner_id': False,
                        'account_id': each.production_unit_id.account_id and each.production_unit_id.account_id.id or 0.00,
                        'debit': net_pay and abs(net_pay) or 0.00,
                        'credit': 0.00,
                    })
            move_line_vals = []
            for each_move_line in temp:
                if each.analytic_account_id:
                    each_move_line.update({'analytic_account_id': each.analytic_account_id.id})
                move_line_vals.append((0, 0, each_move_line))
            move_vals = {
                'journal_id': each.journal_id and each.journal_id.id or False,
                'date': each.account_date and each.account_date or False,
                'ref': each.name and each.name + "/ " + each.production_unit_id.name or "",
                'line_ids': move_line_vals,
                }
            if each.sequence:
                move_vals.update({'name': each.sequence})
            move_id = move_obj.create(move_vals)
            move_id.post()
            if not each.sequence:
                each.sequence = move_id.name
            each.write({
                'state': 'done',
                'move_id': move_id.id, 
                'history': history + "This document is posted by " + str(self.env.user.name) + " on " + date + " for " + each.name
                })
        return True
                
    @api.model
    def _fun_create_move_line_crdit(self, amount, line_id, account_id, deduction_type):
        move_line_vals = {}
        move_line_vals = {
            'name': line_id.payroll_id.name and line_id.payroll_id.name + " - " + deduction_type or "",
            'partner_id': line_id.employee_id.address_home_id and line_id.employee_id.address_home_id.id or False,
            'account_id': account_id and account_id.id or False,
            'debit': 0.00,
            'credit': amount and amount or 0.00,
            }
        return move_line_vals
        
     
    def unlink(self):
        for each in self:
            
            if not self.env.registry.in_test_mode():
                if each.state != 'draft':
                    raise UserError(_("You can delete a payslip which is in draft state only"))
        return super(HrPayrollCustom, self).unlink()
        
class HrPayrollCustomLine(models.Model):
    _name = "hr.payroll.custom.line"
    _description = "HR Payroll Lines Customized"
    _order = "id desc"
    
     
    @api.depends(
        'basic', 'transp', 'hra_earnings', 'prof_all', 'misc_earnings', 'over_time', 'child_education_earnings', 'bonus_earnings', 'night_allowance',
        'arres', 'leave_allowance')
    def calculate_earnings_sum(self):
        for each in self:
            earnings_gross = 0.00
            earnings_gross = (each.basic + each.transp + each.hra_earnings + each.prof_all + each.misc_earnings + each.over_time + each.child_education_earnings + each.bonus_earnings + each.night_allowance + each.arres + each.leave_allowance)
            each.earnings_gross = earnings_gross
            
     
    @api.depends(
        'npf', 'payee', 'ppf', 'tuico', 'salary_advance', 'loan', 'child_education_deductions',
        'hra_deductions', 'bonus_deductions', 'misc', 'absent', 'coin_adjustment')
    def calculate_deductions_sum(self):
        for each in self:
            deductions_gross = 0.00
            deductions_gross = (each.npf + each.payee + each.ppf + each.tuico + each.salary_advance + each.loan + each.child_education_deductions + each.hra_deductions + each.bonus_deductions + each.misc + each.absent + each.coin_adjustment)
            each.deductions_gross = deductions_gross

     
    @api.depends('earnings_gross', 'deductions_gross')
    def calculate_net_pay(self):
        for each in self:
            each.net_pay = (each.earnings_gross - each.deductions_gross)
            
     
    @api.depends('employee_id.loan_balance', 'loan')
    def calculate_loan_balance(self):
        for each in self:
            each.loan_balance = each.employee_id.loan_balance

     
    @api.depends('employee_id', 'payroll_id.date_from', 'payroll_id.date_to')
    def get_employee_payslip_name(self):
        for each in self:
            if each.employee_id and (each.payroll_id.date_from) and (each.payroll_id.date_to):
                date_from = each.payroll_id.date_from
                date_to = each.payroll_id.date_to
                employee = each.employee_id
                ttyme = datetime.fromtimestamp(time.mktime(time.strptime(date_from, "%Y-%m-%d")))
                locale = self.env.context.get('lang', 'en_US')
                each.name = _("Salary Slip of %s for %s") % (employee.name_get()[0][1], tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale)))
                each.month = tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))
    
    payroll_id = fields.Many2one('hr.payroll.custom', string='Payroll', required=True, copy=False, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, copy=False)
    date_from = fields.Date(string='Period Start', required=True, copy=False)
    date_to = fields.Date(string='Period End', required=True, copy=False)
    production_unit_id = fields.Many2one('res.production.unit',string='Unit', readonly=True, related="payroll_id.production_unit_id", copy=False, store=True)
    name = fields.Char(compute='get_employee_payslip_name', string='Name', readonly=True, copy=False, store=True)
    month = fields.Char(compute='get_employee_payslip_name', string='Month', readonly=True, copy=False, store=True)
    basic = fields.Float(string='Basic', digits='Product Price')
    # basic = fields.Float(string='Basic', digits=dp.get_precision('Product Price'))
    transp = fields.Float(string='Transport', digits='Product Price')
    # transp = fields.Float(string='Transport', digits=dp.get_precision('Product Price'))
    hra_earnings = fields.Float(string='HRA.', digits='Product Price')
    # hra_earnings = fields.Float(string='HRA.', digits=dp.get_precision('Product Price'))
    prof_all = fields.Float(string='Professional', digits='Product Price')
    # prof_all = fields.Float(string='Professional', digits=dp.get_precision('Product Price'))
    misc_earnings = fields.Float(string='Misc.', digits='Product Price')
    # misc_earnings = fields.Float(string='Misc.', digits=dp.get_precision('Product Price'))
    over_time = fields.Float(string='OT', digits='Product Price')
    # over_time = fields.Float(string='OT', digits=dp.get_precision('Product Price'))
    child_education_earnings = fields.Float(string='Earnings Child Education', digits='Product Price')
    # child_education_earnings = fields.Float(string='Earnings Child Education', digits=dp.get_precision('Product Price'))
    bonus_earnings = fields.Float(string='Bonus.', digits='Product Price')
    # bonus_earnings = fields.Float(string='Bonus.', digits=dp.get_precision('Product Price'))
    # night_allowance = fields.Float(string='Night Allownace', digits=dp.get_precision('Product Price'))
    night_allowance = fields.Float(string='Night Allownace', digits='Product Price')
    arres = fields.Float(string='Arrears', digits='Product Price')
    # arres = fields.Float(string='Arrears', digits=dp.get_precision('Product Price'))
    leave_allowance = fields.Float(string='Leave Allownace', digits='Product Price')
    # leave_allowance = fields.Float(string='Leave Allownace', digits=dp.get_precision('Product Price'))
    earnings_gross = fields.Float(compute='calculate_earnings_sum', string='Gross Earnings', store=True, digits='Product Price')
    # earnings_gross = fields.Float(compute='calculate_earnings_sum', string='Gross Earnings', store=True, digits=dp.get_precision('Product Price'))
    npf = fields.Float(string='NPF', digits='Product Price')
    # npf = fields.Float(string='NPF', digits=dp.get_precision('Product Price'))
    payee = fields.Float(string='Payee', digits='Product Price')
    # payee = fields.Float(string='Payee', digits=dp.get_precision('Product Price'))
    ppf = fields.Float(string='PPF', digits='Product Price')
    # ppf = fields.Float(string='PPF', digits=dp.get_precision('Product Price'))
    tuico = fields.Float(string='Tuico', digits='Product Price')
    # tuico = fields.Float(string='Tuico', digits=dp.get_precision('Product Price'))
    salary_advance = fields.Float(string='Salary Advance', digits='Product Price')
    # salary_advance = fields.Float(string='Salary Advance', digits=dp.get_precision('Product Price'))
    loan = fields.Float(string='Loan.', digits='Product Price')
    # loan = fields.Float(string='Loan.', digits=dp.get_precision('Product Price'))
    child_education_deductions = fields.Float(string='Deductions Child Education', digits='Product Price')
    # child_education_deductions = fields.Float(string='Deductions Child Education', digits=dp.get_precision('Product Price'))
    hra_deductions = fields.Float(string='HRA Deduction', digits='Product Price')
    # hra_deductions = fields.Float(string='HRA Deduction', digits=dp.get_precision('Product Price'))
    bonus_deductions = fields.Float(string='Bonus Deduction', digits='Product Price')
    # bonus_deductions = fields.Float(string='Bonus Deduction', digits=dp.get_precision('Product Price'))
    misc = fields.Float(string='Misc Deduction', digits='Product Price')
    # misc = fields.Float(string='Misc Deduction', digits=dp.get_precision('Product Price'))
    absent = fields.Float(string='Absent', digits='Product Price')
    # absent = fields.Float(string='Absent', digits=dp.get_precision('Product Price'))
    # coin_adjustment = fields.Float(string='Coin Adj', digits=dp.get_precision('Product Price'))
    coin_adjustment = fields.Float(string='Coin Adj', digits='Product Price')
    loan_balance = fields.Float(compute='calculate_loan_balance', string='Loan Balance', copy=False, digits='Product Price')
    # loan_balance = fields.Float(compute='calculate_loan_balance', string='Loan Balance', copy=False, digits=dp.get_precision('Product Price'))
    deductions_gross = fields.Float(compute='calculate_deductions_sum', string='Gross Deductions', store=True, digits='Product Price')
    # deductions_gross = fields.Float(compute='calculate_deductions_sum', string='Gross Deductions', store=True, digits=dp.get_precision('Product Price'))
    net_pay = fields.Float(compute='calculate_net_pay', string='Net Pay', store=True, digits='Product Price')
    # net_pay = fields.Float(compute='calculate_net_pay', string='Net Pay', store=True, digits=dp.get_precision('Product Price'))
    state = fields.Selection([
        ('draft', 'Draft'), 
        ('wait', 'Waiting For Approval'), 
        ('approved', 'Approved'), 
        ('done', 'Done'), 
        ('cancel', 'Cancelled')
        ], string='State', readonly=True, default='draft', copy=False, related="payroll_id.state", store=True)
        
    _sql_constraints = [
        ('name_employee_uniq', 'unique(payroll_id, employee_id)', 'Employee must be unique in each payroll !'),
        ]
    
     
    @api.constrains('date_from', 'date_to')
    def _check_date_from_to(self):
        for line in self:
            if not self.env.registry.in_test_mode():
                if line.date_from > line.date_to:
                    raise ValidationError(_("Employee payroll 'period end date' must be greater than the period start date."))
        
    @api.onchange('employee_id')
    def onchange_employee_id(self):
        warning = {}
        if not self.payroll_id.production_unit_id:
            warning = {
                'title': _('Warning'),
                'message': _("Kindly select employee's respective unit and proceed!!!")}
            self.employee_id = False
        if not self.payroll_id.date_from:
            warning = {
                'title': _('Warning'),
                'message': _("Kindly select unit's period start and proceed!!!")}
            self.employee_id = False
        if not self.payroll_id.date_to:
            warning = {
                'title': _('Warning'),
                'message': _("Kindly select unit's period end and proceed!!!")}
            self.employee_id = False
        if self.employee_id:
            self.basic = self.employee_id.basic
            self.transp = self.employee_id.transp
            self.hra_earnings = self.employee_id.hra_earnings
            self.prof_all = self.employee_id.prof_all
            self.misc_earnings = self.employee_id.misc_earnings
            self.over_time = self.employee_id.over_time
            self.child_education_earnings = self.employee_id.child_education_earnings
            self.bonus_earnings = self.employee_id.bonus_earnings
            self.night_allowance = self.employee_id.night_allowance
            self.arres = self.employee_id.arres
            self.leave_allowance = self.employee_id.leave_allowance
            self.child_education_deductions = self.employee_id.child_education_deductions
            self.hra_deductions = self.employee_id.hra_deductions
            self.coin_adjustment = self.employee_id.coin_adjustment
        return {'warning': warning} 
        
    @api.onchange('date_from', 'date_to')
    def onchange_date_from(self):
        warning = {}
        if self.date_from and self.date_to and self.date_from > self.date_to:
            warning = {
                'title': _('Warning'),
                'message': _("Employee payroll 'period end date' must be greater than the period start date!!!")}
            self.date_from = False
            self.date_to = False
            return {'warning': warning}
        if self.date_from and (self.date_from < self.payroll_id.date_from) or (self.date_from > self.payroll_id.date_to):
            warning = {
                'title': _('Warning'),
                'message': _("Kindly select the correct 'period start date' from period selected in the form!!!")}
            self.date_from = self.payroll_id.date_from
            return {'warning': warning}
        if self.date_to and (self.date_to < self.payroll_id.date_from) or (self.date_to > self.payroll_id.date_to):
            warning = {
                'title': _('Warning'),
                'message': _("Kindly select the correct 'period end date' from period selected in the form!!!")}
            self.date_to = self.payroll_id.date_to
            return {'warning': warning} 
            
                    
     
    def unlink(self):
        for each in self:
            
            if not self.env.registry.in_test_mode():
                if each.state != 'draft':
                    raise UserError(_('You can delete a payslip which is in draft state only.'))
        return super(HrPayrollCustomLine, self).unlink()
        
class EmployeePayslipEarningLine(models.Model):
    _name = "employee.payslip.earning.line"
    _description = "Employee Payslip Earning Line"
    
    payroll_id = fields.Many2one('hr.payroll.custom', string='Payroll', ondelete='cascade')
    unit_id = fields.Many2one('res.production.unit', string='Production Unit')
    account_id = fields.Many2one('account.account', string='Account')
    earning_type = fields.Selection([
        ('basic', 'Basic'),
        ('transp', 'Transport'),
        ('hra_earnings', 'HRA'),
        ('prof_all', 'Professional'),
        ('misc_earnings', 'Misc'),
        ('over_time', 'OT'),
        ('child_education_earnings', 'Child Education'),
        ('bonus_earnings', 'Bonus'),
        ('night_allowance', 'Night Allownace'),
        ('arres', 'Arrears'),
        ('leave_allowance', 'Leave Allownace'),
        ], string='Earnings')
    amount = fields.Float('Amount')
    
class EmployeePayslipDeductionLine(models.Model):
    _name = "employee.payslip.deduction.line"
    _description = "Employee Payslip Deduction Line" 
    
    payroll_id = fields.Many2one('hr.payroll.custom', string='Payroll', ondelete='cascade')
    unit_id = fields.Many2one('res.production.unit', string='Production Unit')
    account_id = fields.Many2one('account.account', string='Account')
    deduction_type = fields.Selection([
        ('npf', 'NPF'),
        ('payee', 'Payee'),
        ('ppf', 'PPF'),
        ('tuico', 'Tuico'),
        ('salary_advance', 'Salary Advance'),
        ('loan', 'Loan'),
        ('child_education_deductions', 'Child Education'),
        ('hra_deductions', 'HRA Deduction'),
        ('bonus_deductions', 'Bonus Deduction'),
        ('misc', 'Misc Deduction'),
        ('absent', 'Absent'),
        ('coin_adjustment', 'Coin Adj')
        ], string='Deductions')
    amount = fields.Float('Amount')
    
