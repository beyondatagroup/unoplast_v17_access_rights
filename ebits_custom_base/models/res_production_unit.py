# -*- coding: utf-8 -*-
# Part of EBITS TechCon.

from datetime import datetime
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp

class ResProductionUnit(models.Model):
    _name = "res.production.unit"
    _description = "Company Production Unit"
    
    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True, translate=True, size=10)
    description = fields.Text(string="Description", translate=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env['res.company']._company_default_get('res.production.unit'))
    earning_line = fields.One2many('employee.unit.earning.line', 'unit_id', string='Earnings')
    deduction_line = fields.One2many('employee.unit.deduction.line', 'unit_id', string='Deductions')
    account_id = fields.Many2one('account.account', 'Salary Payable')
           
class ResProductionUnitDivision(models.Model):
    _name = "res.production.unit.division"
    _description = "Company Production Unit Division"
    
    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True, translate=True, size=10)
    description = fields.Text(string="Description", translate=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env['res.company']._company_default_get('res.production.unit.division'))
    
class EmployeeUnitEarningLine(models.Model):
    _name = "employee.unit.earning.line"
    _description = "Employee Unit Earnings Line"
    
    unit_id = fields.Many2one('res.production.unit', string='Production Unit', ondelete='cascade')
    account_id = fields.Many2one('account.account', string='Account', required=True)
    earning_type = fields.Selection([
        ('basic', 'Basic'),
        ('transp', 'Transport'),
        ('hra_earnings', 'HRA'),
        ('prof_all', 'Professional'),
        ('misc_earnings', 'Misc'),
        ('over_time', 'OT'),
        ('child_education_earnings', 'Earnings Child Education'),
        ('bonus_earnings', 'Bonus'),
        ('night_allowance', 'Night Allownace'),
        ('arres', 'Arrears'),
        ('leave_allowance', 'Leave Allownace'),
        ], string='Earnings', required=True)
        
class EmployeeUnitDeductionLine(models.Model):
    _name = "employee.unit.deduction.line" 
    _description = "Employee Unit Deductions Lines"  
    
    unit_id = fields.Many2one('res.production.unit', string='Production Unit', ondelete='cascade')
    account_id = fields.Many2one('account.account', string='Account', required=True)
    deduction_type = fields.Selection([
        ('npf', 'NPF'),
        ('payee', 'Payee'),
        ('ppf', 'PPF'),
        ('tuico', 'Tuico'),
        ('salary_advance', 'Salary Advance'),
        ('loan', 'Loan'),
        ('child_education_deductions', 'Deductions Child Education'),
        ('hra_deductions', 'HRA Deduction'),
        ('bonus_deductions', 'Bonus Deduction'),
        ('misc', 'Misc Deduction'),
        ('absent', 'Absent'),
        ('coin_adjustment', 'Coin Adj')
        ], string='Deductions', required=True)  

class TruckDriverEmployee(models.Model):
    _name = "truck.driver.employee"
    _description = "Truck Driver Employee"
    
    name = fields.Char(string="Driver Name", size=64, required=True, translate=True)
    driver_licence = fields.Char(string="Driver Licence No", size=64, required=True)
    driver_licence_type = fields.Char(string="Driver Licence Type", size=64, required=True)
    driver_licence_place = fields.Char(string="Issued Licence Place", size=64, required=True)
    driver_phone = fields.Char(string="Driver Contact No", size=64, required=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env['res.company']._company_default_get('truck.driver.employee'))
