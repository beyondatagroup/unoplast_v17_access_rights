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

class LoanType(models.Model):
    _name = "loan.type"
    _description = "Loan Type"

    name = fields.Char(string="Loan Type", size=64, required=True)
    account_id = fields.Many2one('account.account', 'Account')

class HrLoan(models.Model):
    _name = "hr.loan"
    _description = "HR Loan Management"
    _order = "request_date desc, id"
    
    @api.depends('emi_line.paid_amt', 'approved_amt')
    def get_total_amt(self):
        amount = 0.00
        for each in self:
            amount = 0.00
            remaining_amt = 0.00
            for line in each.emi_line:
                amount += line.paid_amt
            each.total_amt = amount
            remaining_amt = each.approved_amt - amount
            if remaining_amt != abs(remaining_amt):
                each.remaining_amt = 0.00
            else:
                each.remaining_amt = remaining_amt
            
    name = fields.Char(string='Request No', size=64, readonly=True, copy=False, default=lambda self: _('New #'))
    user_id = fields.Many2one('res.users', string='Creator', default=lambda self: self.env.user, readonly=True, copy=False)
    request_date = fields.Date(string='Request Date', default=fields.Datetime.now, readonly=True, copy=False)
    employee_id = fields.Many2one('hr.employee', string='Requested By', required=True, readonly=True, copy=False)
    # employee_id = fields.Many2one('hr.employee', string='Requested By', required=True, readonly=True, copy=False)
    approved_id = fields.Many2one('res.users', string='Approver', readonly=True, copy=False)
    approved_date = fields.Date(string='Approved Date', readonly=True, copy=False)
    loan_type_id = fields.Many2one('loan.type', string='Loan Type', required=True, readonly=True, copy=False)
    production_unit_id = fields.Many2one('res.production.unit', string='Unit', required=True, readonly=True,  copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', required=True, readonly=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False,
        default=lambda self: self.env['res.company']._company_default_get())
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True, related="company_id.currency_id", copy=False, store=True)
    request_amt = fields.Monetary(string='Request Amount', required=True, readonly=True, copy=False, currency_field='currency_id')
    approved_amt = fields.Monetary(string='Approved Amount', readonly=True, copy=False, currency_field='currency_id')
    
    repay_period = fields.Integer(string='Repay Period', required=True, readonly=True, copy=False)
    
    approve_repay_period = fields.Integer(string='Approve Repay Period', readonly=True, copy=False)
    
    # approve_repay_period = fields.Integer(string='Repay Period', readonly=True, copy=False)
    deduction_date = fields.Date(string='First Deduction Date', readonly=True, copy=False)
    emi_line = fields.One2many('hr.loan.emi.line', 'loan_id', string='EMI Schedule',readonly=True)
    total_amt = fields.Monetary(compute='get_total_amt', string='Total Paid Amount', readonly=True, store=True, copy=False, currency_field='currency_id')
    remaining_amt = fields.Monetary(compute='get_total_amt', string='Remaining Amount', readonly=True, store=True, copy=False, currency_field='currency_id')
    history = fields.Text(string='History', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'), 
        ('wait', 'Waiting For Approval'), 
        ('approved', 'Approved'), 
        ('done', 'Closed'), 
        ('cancel', 'Cancelled')
        ], string='State', readonly=True, default='draft', copy=False)
    journal_id = fields.Many2one('account.journal', 'Payment Journal', copy=False)
    move_id = fields.Many2one('account.move', 'Journal Entry', readonly=True, copy=False)
        
    @api.onchange('production_unit_id')
    def onchange_production_unit_id(self):
        warning = {}
        if self.production_unit_id:
            if self.warehouse_id:
                self.production_unit_id = self.warehouse_id.production_unit_id
                warning = {
                    'title': 'warning',
                    'message': 'You cannot change the unit of the warehouse/branch',
                    }
        else:
            if self.warehouse_id:
                self.production_unit_id = self.warehouse_id.production_unit_id
        return {'warning': warning} 
        
     
    def move_to_wait(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            if each.name == 'New #': 
                each.name = self.env['ir.sequence'].next_by_code('hr.loan.code') or 'New #'
            each.write({
                'approved_id': self.env.user.employee_ids and ( self.env.user.employee_ids[0].parent_id and (self.env.user.employee_ids[0].parent_id.user_id and self.env.user.employee_ids[0].parent_id.user_id.id or False) or False) or False,
                'approved_amt': each.request_amt and each.request_amt or 0.00,
                'approve_repay_period': each.repay_period and each.repay_period or 0,
                'state': 'wait',
                'history': (each.history and each.history or "") + '\nThis document is sent for approval by ' + str(self.env.user.name) + ' on '+ date  
                })
        return True
            
     
    def move_to_approved(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.write({
                'approved_id': self.env.user.id,
                'approved_date': fields.Date.context_today(self),
                'state': 'approved',
                'history': (each.history and each.history or "") + '\nThis document is approved by ' + str(self.env.user.name) + ' on '+ date, 
                })
            each.action_calculate_emi_schedule()
        return True
        
     
    def action_create_journal_entry(self):
        move_obj = self.env['account.move']
        temp = []
        for each in self:

            if not self.env.registry.in_test_mode():
                if not each.journal_id:
                    raise UserError(_("Kindly map the journal and post entries!"))
            
            if not self.env.registry.in_test_mode():
                if not each.loan_type_id.account_id:
                    raise UserError(_("Kindly map the related account in loan type master!"))
            
            if not self.env.registry.in_test_mode():
                if not each.journal_id.default_credit_account_id:
                    raise UserError(_("Kindly map the related account in journal master!"))
                
            temp.append({
                'name': each.name and each.name or "",
                'partner_id': each.employee_id.address_home_id and each.employee_id.address_home_id.id or False,
                'account_id': each.loan_type_id.account_id and each.loan_type_id.account_id.id or False,
                'debit': each.approved_amt and each.approved_amt or 0.00,
                'credit': 0.00,
                })
            temp.append({
                'name': each.name and each.name or "",
                'partner_id': each.employee_id.address_home_id and each.employee_id.address_home_id.id or False,
                'account_id': each.journal_id.default_credit_account_id and each.journal_id.default_credit_account_id.id or False,
                'debit': 0.00,
                'credit': each.approved_amt and each.approved_amt or 0.00,
                })
            move_line_vals = []
            for each_move_line in temp:
                move_line_vals.append((0, 0, each_move_line))
            move_id = move_obj.create({
                'journal_id': each.journal_id and each.journal_id.id or False,
                'date': each.approved_date and each.approved_date or False,
                'ref': each.name and each.name or "",
                'line_ids': move_line_vals,
            })
            move_id.post()
            each.move_id = move_id
        return True
            
     
    def move_to_done(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            if not self.env.registry.in_test_mode():
                if not each.move_id:
                    raise UserError(_("Kindly post loan approved amount into accounts and close the loan form"))
            
            if not self.env.registry.in_test_mode():
                if each.remaining_amt:
                    raise UserError(_("EMI not paid.\nIn order to close the loan form, It must be fully paid"))
            
            each.write({
                'state': 'done',
                'history': (each.history and each.history or "") + '\nThis document is closed by ' + str(self.env.user.name) + ' on '+ date,
                })
        return True
            
     
    def action_calculate_emi_schedule(self):
        emi_obj = self.env['hr.loan.emi.line']
        deduc_date = datetime.strptime(self.deduction_date, "%Y-%m-%d")
        for each in self:
            each.emi_line.unlink()
            for month in range(0, each.approve_repay_period):
                date = False
                date = deduc_date + relativedelta(months =+ month)   
                emi_obj.create({
                    'date': date,
                    'emi_amt': (each.approved_amt / each.approve_repay_period),
                    'loan_id': each.id
                    })
        return True
        
     
    def action_pay_emi(self):
        for each in self:
            
            if not self.env.registry.in_test_mode():
                if not each.move_id:
                    raise UserError(_("Kindly post loan approved amount into accounts and proceed further"))
            view = self.env.ref('ebits_custom_hr.hr_loan_pay_emi_wizard_form')
            wiz = self.env['hr.loan.pay.emi.wizard'].create({'loan_id': each.id, 'remaining_amt': each.remaining_amt})
            return {
                'name': _('Pay Loan EMI'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'hr.loan.pay.emi.wizard',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                'context': self.env.context,
            }
                    
     
    def unlink(self):
        for each in self:
            
            if not self.env.registry.in_test_mode():
                if each.state != 'draft':
                    raise UserError(_('You can delete a form which is in draft state only.'))
        return super(HrLoan, self).unlink()

class HrLoanEmiLine(models.Model):
    _name = "hr.loan.emi.line"
    _description = "EMI Schedule"
    
    loan_id = fields.Many2one('hr.loan', string='Hr Loan', ondelete='cascade', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True, related="loan_id.employee_id", store=True, copy=False)
    production_unit_id = fields.Many2one('res.production.unit', string='Unit', readonly=True, related="loan_id.production_unit_id", store=True, copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse/Branch', readonly=True, related="loan_id.warehouse_id", store=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', readonly=True, related="loan_id.company_id", store=True, copy=False)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True, related="loan_id.currency_id", store=True, copy=False)
    date = fields.Date(string='Date', readonly=True)
    emi_amt = fields.Monetary(string='EMI Amount', readonly=True, currency_field='currency_id')
    paid_date = fields.Date(string='Paid Date', readonly=True)
    paid_amt = fields.Monetary(string='Paid Amount', currency_field='currency_id', readonly=True)
    # state = fields.Selection([
    #     ('draft', 'Draft'), 
    #     ('wait', 'Waiting For Approval'), 
    #     ('approved', 'Approved'), 
    #     ('done', 'Done'), 
    #     ('cancel', 'Cancelled')
    #     ], string='State', readonly=True, default='draft', related='loan_id.state')
     
    state = fields.Selection(string='State', readonly=True, related='loan_id.state')
     
