# # -*- coding: utf-8 -*-
# # EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

# import time
# import babel
# import locale
# import math
# import pytz
# from datetime import datetime, timedelta
# from dateutil import relativedelta
# from odoo.osv import expression
# from odoo.tools.float_utils import float_round as round
# from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
# from odoo.tools.misc import formatLang
# import odoo.addons.decimal_precision as dp
# from odoo.exceptions import UserError, ValidationError
# from odoo import api, fields, models, tools, _
# from odoo.tools.safe_eval import safe_eval

# from excel_styles import ExcelStyles
# import xlwt
# import cStringIO
# import base64
# import xlrd
# import parser

# class HRPayrollCancelWizard(models.TransientModel):
#     _name = "hr.payroll.custom.upload.template"
#     _description = "HR Payroll Custom Upload Template Wizard"
    
#     production_unit_id = fields.Many2one('res.production.unit', string='Unit', required=True, copy=False)
#     date_from = fields.Date(string='Period Start', default=time.strftime('%Y-%m-01'), required=True, copy=False)
#     date_to = fields.Date(string='Period End', default=str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10], required=True, copy=False)
#     name = fields.Char(string='Name', required=True, copy=False)
#     company_id = fields.Many2one('res.company', string='Company', copy=False, default=lambda self: self.env['res.company']._company_default_get())
#     report_name = fields.Char(string='File Name', readonly=True)
#     output = fields.Binary(string='format', readonly=True)
    
     
#     @api.constrains('date_from', 'date_to')
#     def _check_date_from_to(self):
#         for each in self:
#             if each.date_from > each.date_to:
#                 raise ValidationError(_('Payroll period end date must be greater than the period start date.'))
    
#     @api.onchange('date_from', 'date_to')
#     def onchange_period(self):
#         if (not self.date_from) or (not self.date_to):
#             self.name = ""
#             return
#         date_from = self.date_from
#         date_to = self.date_to
#         ttyme = datetime.fromtimestamp(time.mktime(time.strptime(date_from, "%Y-%m-%d")))
#         locale = self.env.context.get('lang', 'en_US')
#         self.name = _('Salary Slip for %s') % (tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale)))
        
        
#     def action_download_payroll_template(self):
#         employee_obj = self.env['hr.employee']
#         income_tax_obj = self.env['income.tax.structure']
#         for each in self:
#             employee_search = employee_obj.sudo().search([('production_unit_id', '=', each.production_unit_id.id)])
#             income_tax_search = income_tax_obj.search([('date_from', '<=', each.date_from),('date_to', '>=', each.date_to)]) 
#             if len(income_tax_search) > 1:
#                 raise UserError(_('Only one income tax period can be active!.'))
#             if not income_tax_search:
#                 raise UserError(_('Check whether payroll period is correctly entered\n (or)\n check whether income tax structure is active or not!.'))
#             Style = ExcelStyles()
#             wbk = xlwt.Workbook()
#             sheet1 = wbk.add_sheet(each.name)
#             #sheet1.show_grid = False
#             sheet1.col(0).width = 4000
#             sheet1.col(1).width = 3000
#             sheet1.col(2).width = 3000
#             sheet1.col(3).width = 7000
#             sheet1.col(4).width = 6000
#             sheet1.col(5).width = 5800
#             sheet1.col(6).width = 5800
#             sheet1.col(7).width = 4000
#             sheet1.col(8).width = 4000
#             sheet1.col(9).width = 4000
#             sheet1.col(10).width = 4000
#             sheet1.col(11).width = 4000
#             sheet1.col(12).width = 4000
#             sheet1.col(13).width = 4000
#             sheet1.col(14).width = 4000
#             sheet1.col(15).width = 4000
#             sheet1.col(16).width = 4000
#             sheet1.col(17).width = 4000
#             sheet1.col(18).width = 4000
#             sheet1.col(19).width = 4000
#             sheet1.col(20).width = 4000
#             sheet1.col(21).width = 4000
#             sheet1.col(22).width = 4000
#             sheet1.col(23).width = 4000
#             sheet1.col(24).width = 4000
#             sheet1.col(25).width = 4000
#             sheet1.col(26).width = 4000
#             sheet1.col(27).width = 4000
#             sheet1.col(28).width = 4000
#             sheet1.col(29).width = 4000
        
#             row = 0
#             sheet1.row(row).height = 700
#             sheet1.write(row, 0, "Unit", Style.normal_left())
#             sheet1.write(row, 1, "Period Start", Style.normal_left())
#             sheet1.write(row, 2, "Period End", Style.normal_left())
#             sheet1.write(row, 3, "Name", Style.normal_left())
#             sheet1.write(row, 4, "Payroll Lines/Employee", Style.normal_left())
#             sheet1.write(row, 5, "Payroll Lines/Period Start", Style.normal_left())
#             sheet1.write(row, 6, "Payroll Lines/Period End", Style.normal_left())
#             sheet1.write(row, 7, "Payroll Lines/Basic", Style.normal_left())
#             sheet1.write(row, 8, "Payroll Lines/Transport", Style.normal_left())
#             sheet1.write(row, 9, "Payroll Lines/HRA.", Style.normal_left())
#             sheet1.write(row, 10, "Payroll Lines/Professional", Style.normal_left())
#             sheet1.write(row, 11, "Payroll Lines/Misc.", Style.normal_left())
#             sheet1.write(row, 12, "Payroll Lines/OT", Style.normal_left())
#             sheet1.write(row, 13, "Payroll Lines/Earnings Child Education", Style.normal_left())
#             sheet1.write(row, 14, "Payroll Lines/Bonus.", Style.normal_left())
#             sheet1.write(row, 15, "Payroll Lines/Night Allownace", Style.normal_left())
#             sheet1.write(row, 16, "Payroll Lines/Arrears", Style.normal_left())
#             sheet1.write(row, 17, "Payroll Lines/Leave Allownace", Style.normal_left())
# #            sheet1.write(row, 18, "Payroll Lines/House.", Style.normal_left())
# #            sheet1.write(row, 18, "Payroll Lines/Gross Earnings", Style.normal_left())
#             sheet1.write(row, 18, "Payroll Lines/NPF", Style.normal_left())
#             sheet1.write(row, 19, "Payroll Lines/Payee", Style.normal_left())
#             sheet1.write(row, 20, "Payroll Lines/PPF", Style.normal_left())
#             sheet1.write(row, 21, "Payroll Lines/Tuico", Style.normal_left())
#             sheet1.write(row, 22, "Payroll Lines/Salary Advance", Style.normal_left())
#             sheet1.write(row, 23, "Payroll Lines/Loan.", Style.normal_left())
#             sheet1.write(row, 24, "Payroll Lines/Deductions Child Education", Style.normal_left())
# #            sheet1.write(row, 27, "Payroll Lines/House Deduction", Style.normal_left())
#             sheet1.write(row, 25, "Payroll Lines/HRA Deduction", Style.normal_left())
#             sheet1.write(row, 26, "Payroll Lines/Bonus Deduction", Style.normal_left())
#             sheet1.write(row, 27, "Payroll Lines/Misc Deduction", Style.normal_left())
#             sheet1.write(row, 28, "Payroll Lines/Absent", Style.normal_left())
#             sheet1.write(row, 29, "Payroll Lines/Coin Adj", Style.normal_left())
# #            sheet1.write(row, 31, "Payroll Lines/Gross Deductions", Style.normal_left())
# #            sheet1.write(row, 32, "Payroll Lines/Net Pay", Style.normal_left())
            
#             for each_employee in employee_search:
#                 employee_name = ""
#                 gross_earning, npf, ppf, tuico, kodi_on, tax_amount = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
#                 row = row + 1
#                 sheet1.row(row).height = 500
#                 if row == 1:
#                     sheet1.write(row, 0, each.production_unit_id.name, Style.normal_left())
#                     sheet1.write(row, 1, each.date_from, Style.normal_left())
#                     sheet1.write(row, 2, each.date_to, Style.normal_left())
#                     sheet1.write(row, 3, each.name, Style.normal_left())
#                 else:
#                     sheet1.write(row, 0, "", Style.normal_left())
#                     sheet1.write(row, 1, "", Style.normal_left())
#                     sheet1.write(row, 2, "", Style.normal_left())
#                     sheet1.write(row, 3, "", Style.normal_left())
#                 gross_earning = (each_employee.basic +
#                                  each_employee.transp + 
#                                  each_employee.hra_earnings + 
#                                  each_employee.prof_all + 
#                                  each_employee.misc_earnings + 
#                                  each_employee.over_time +
#                                  each_employee.child_education_earnings + 
#                                  each_employee.bonus_earnings + 
#                                  each_employee.night_allowance + 
#                                  each_employee.arres + 
#                                  each_employee.leave_allowance) 
#                 if each_employee.pf_type == 'npf': 
#                     npf = (gross_earning * (each_employee.pf_value / 100.00))
#                     kodi_on = gross_earning - npf 
#                 else:
#                     ppf = (gross_earning * (each_employee.pf_value / 100.00)) 
#                     kodi_on = gross_earning - ppf
#                 if each_employee.tuico:
#                     tuico = (each_employee.basic * (each_employee.tuico_value / 100.00))
#                 for tax_each in income_tax_search:
#                     for line_tax in tax_each.tax_line:
#                         if (kodi_on >= line_tax.tax_value_from) and (kodi_on <= line_tax.tax_value_to):
#                             tax_amount = (line_tax.tax_amount + ((kodi_on - line_tax.tax_value_from) * line_tax.tax_percentage))
#                             break    
# #                        elif (kodi_on >= line_tax.tax_value_from):
# #                            tax_amount = (line_tax.tax_amount + (kodi_on - line_tax.tax_value_from) * line_tax.tax_percentage)
#                 employee_name = each_employee.name_get()[0][1]
#                 sheet1.write(row, 4, employee_name, Style.normal_left())
#                 sheet1.write(row, 5, each.date_from, Style.normal_left())
#                 sheet1.write(row, 6, each.date_to, Style.normal_left())
#                 sheet1.write(row, 7, each_employee.basic and each_employee.basic or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 8, each_employee.transp and each_employee.transp or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 9, each_employee.hra_earnings and each_employee.hra_earnings or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 10, each_employee.prof_all and each_employee.prof_all or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 11, each_employee.misc_earnings and each_employee.misc_earnings or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 12, each_employee.over_time and each_employee.over_time or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 13, each_employee.child_education_earnings and each_employee.child_education_earnings or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 14, each_employee.bonus_earnings and each_employee.bonus_earnings or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 15, each_employee.night_allowance and each_employee.night_allowance or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 16, each_employee.arres and each_employee.arres or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 17, each_employee.leave_allowance and each_employee.leave_allowance or 0.00, Style.normal_num_right())
# #                sheet1.write(row, 18, 0.00, Style.normal_num_right())
# #                sheet1.write(row, 18, gross_earning, Style.normal_num_right())
#                 sheet1.write(row, 18, npf, Style.normal_num_right())
#                 sheet1.write(row, 19, tax_amount, Style.normal_num_right())
#                 sheet1.write(row, 20, ppf, Style.normal_num_right())
#                 sheet1.write(row, 21, tuico, Style.normal_num_right())
#                 sheet1.write(row, 22, 0.00, Style.normal_num_right())
#                 sheet1.write(row, 23, 0.00, Style.normal_num_right())
#                 sheet1.write(row, 24, each_employee.child_education_deductions and each_employee.child_education_deductions or 0.00, Style.normal_num_right())
# #                sheet1.write(row, 27, 0.00, Style.normal_num_right())
#                 sheet1.write(row, 25, each_employee.hra_deductions and each_employee.hra_deductions or 0.00, Style.normal_num_right())
#                 sheet1.write(row, 26, 0.00, Style.normal_num_right())
#                 sheet1.write(row, 27, 0.00, Style.normal_num_right())
#                 sheet1.write(row, 28, 0.00, Style.normal_num_right())
#                 sheet1.write(row, 29, each_employee.coin_adjustment and each_employee.coin_adjustment or 0.00, Style.normal_num_right())
# #                sheet1.write(row, 31, 0.00, Style.normal_num_right())
# #                sheet1.write(row, 32, 0.00, Style.normal_num_right())
                
#             stream = cStringIO.StringIO()
#             wbk.save(stream)

#             each.write({'report_name': each.name + "_Template"+ '.xls', 'output': base64.encodestring(stream.getvalue())})
#             return {
#                     'name': _('Payroll Template'),
#                     'view_type': 'form',
#                     'view_mode': 'form',
#                     'res_model': 'hr.payroll.custom.upload.template',
#                     'res_id': each.id,
#                     'type': 'ir.actions.act_window',
#                     'target':'new'
#                     }




# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import time
import babel
import locale
import math
import pytz
from datetime import datetime, timedelta
from dateutil import relativedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, tools, _
from odoo.tools.safe_eval import safe_eval

import io
import base64
import xlsxwriter

class HRPayrollCancelWizard(models.TransientModel):
    _name = "hr.payroll.custom.upload.template"
    _description = "HR Payroll Custom Upload Template Wizard"
    
    production_unit_id = fields.Many2one('res.production.unit', string='Unit', required=True, copy=False)
    date_from = fields.Date(string='Period Start', default=lambda self: fields.Date.today().replace(day=1), required=True, copy=False)
    date_to = fields.Date(string='Period End', default=lambda self: (datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1)).strftime('%Y-%m-%d'), required=True, copy=False)
    name = fields.Char(string='Name', required=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', copy=False, default=lambda self: self.env['res.company']._company_default_get())
    report_name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.constrains('date_from', 'date_to')
    def _check_date_from_to(self):
        for each in self:
            
            if not self.env.registry.in_test_mode():
                if each.date_from > each.date_to:
                    raise ValidationError(_('Payroll period end date must be greater than the period start date.'))
    
    @api.onchange('date_from', 'date_to')
    def onchange_period(self):
        if (not self.date_from) or (not self.date_to):
            self.name = ""
            return
        date_from = fields.Date.from_string(self.date_from)
        date_to = fields.Date.from_string(self.date_to)
        locale = self.env.context.get('lang', 'en_US')
        self.name = _('Salary Slip for %s') % (tools.ustr(babel.dates.format_date(date=date_from, format='MMMM-y', locale=locale)))
        
    def action_download_payroll_template(self):
        employee_obj = self.env['hr.employee']
        income_tax_obj = self.env['income.tax.structure']
        for each in self:
            employee_search = employee_obj.sudo().search([('production_unit_id', '=', each.production_unit_id.id)])
            income_tax_search = income_tax_obj.search([('date_from', '<=', each.date_from), ('date_to', '>=', each.date_to)])
            
            if not self.env.registry.in_test_mode():
                if len(income_tax_search) > 1:
                    raise UserError(_('Only one income tax period can be active!.'))
                if not income_tax_search:
                    raise UserError(_('Check whether payroll period is correctly entered\n (or)\n check whether income tax structure is active or not!.'))
            
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet1 = workbook.add_worksheet(each.name)
            
            # Define cell formats with xlsxwriter
            title_format = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1'})
            header_format = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
            data_format = workbook.add_format({'align': 'left'})
            numeric_format = workbook.add_format({'num_format': '#,##0.00'})
            
            # Set column widths
            columns_width = [4000, 3000, 3000, 7000, 6000, 5800, 5800, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000]
            for i, width in enumerate(columns_width):
                sheet1.set_column(i, i, width)
            
            row = 0
            
            # Write headers
            headers = ["Unit", "Period Start", "Period End", "Name", "Payroll Lines/Employee", "Payroll Lines/Period Start", "Payroll Lines/Period End", "Payroll Lines/Basic", "Payroll Lines/Transport", "Payroll Lines/HRA.", "Payroll Lines/Professional", "Payroll Lines/Misc.", "Payroll Lines/OT", "Payroll Lines/Earnings Child Education", "Payroll Lines/Bonus.", "Payroll Lines/Night Allownace", "Payroll Lines/Arrears", "Payroll Lines/Leave Allownace", "Payroll Lines/NPF", "Payroll Lines/Payee", "Payroll Lines/PPF", "Payroll Lines/Tuico", "Payroll Lines/Salary Advance", "Payroll Lines/Loan.", "Payroll Lines/Deductions Child Education", "Payroll Lines/HRA Deduction", "Payroll Lines/Bonus Deduction", "Payroll Lines/Misc Deduction", "Payroll Lines/Absent", "Payroll Lines/Coin Adj"]
            for col, header in enumerate(headers):
                sheet1.write(row, col, header, header_format)
            
            row += 1
            
            # Write data rows
            for each_employee in employee_search:
                employee_name = ""
                gross_earning, npf, ppf, tuico, kodi_on, tax_amount = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
                
                if row == 1:
                    sheet1.write(row, 0, each.production_unit_id.name, data_format)
                    sheet1.write(row, 1, each.date_from, data_format)
                    sheet1.write(row, 2, each.date_to, data_format)
                    sheet1.write(row, 3, each.name, data_format)
                else:
                    sheet1.write(row, 0, "", data_format)
                    sheet1.write(row, 1, "", data_format)
                    sheet1.write(row, 2, "", data_format)
                    sheet1.write(row, 3, "", data_format)
                
                gross_earning = (each_employee.basic +
                                 each_employee.transp +
                                 each_employee.hra_earnings +
                                 each_employee.prof_all +
                                 each_employee.misc_earnings +
                                 each_employee.over_time +
                                 each_employee.child_education_earnings +
                                 each_employee.bonus_earnings +
                                 each_employee.night_allowance +
                                 each_employee.arres +
                                 each_employee.leave_allowance)
                
                if each_employee.pf_type == 'npf':
                    npf = (gross_earning * (each_employee.pf_value / 100.00))
                    kodi_on = gross_earning - npf
                else:
                    ppf = (gross_earning * (each_employee.pf_value / 100.00))
                    kodi_on = gross_earning - ppf
                
                if each_employee.tuico:
                    tuico = (each_employee.basic * (each_employee.tuico_value / 100.00))
                
                for tax_each in income_tax_search:
                    for line_tax in tax_each.tax_line:
                        if (kodi_on >= line_tax.tax_value_from) and (kodi_on <= line_tax.tax_value_to):
                            tax_amount = (line_tax.tax_amount + ((kodi_on - line_tax.tax_value_from) * line_tax.tax_percentage))
                            break
                
                employee_name = each_employee.name_get()[0][1]
                sheet1.write(row, 4, employee_name, data_format)
                sheet1.write(row, 5, each.date_from, data_format)
                sheet1.write(row, 6, each.date_to, data_format)
                sheet1.write(row, 7, each_employee.basic or 0.00, numeric_format)
                sheet1.write(row, 8, each_employee.transp or 0.00, numeric_format)
                sheet1.write(row, 9, each_employee.hra_earnings or 0.00, numeric_format)
                sheet1.write(row, 10, each_employee.prof_all or 0.00, numeric_format)
                sheet1.write(row, 11, each_employee.misc_earnings or 0.00, numeric_format)
                sheet1.write(row, 12, each_employee.over_time or 0.00, numeric_format)
                sheet1.write(row, 13, each_employee.child_education_earnings or 0.00, numeric_format)
                sheet1.write(row, 14, each_employee.bonus_earnings or 0.00, numeric_format)
                sheet1.write(row, 15, each_employee.night_allowance or 0.00, numeric_format)
                sheet1.write(row, 16, each_employee.arres or 0.00, numeric_format)
                sheet1.write(row, 17, each_employee.leave_allowance or 0.00, numeric_format)
                sheet1.write(row, 18, npf, numeric_format)
                sheet1.write(row, 19, tax_amount, numeric_format)
                sheet1.write(row, 20, ppf, numeric_format)
                sheet1.write(row, 21, tuico, numeric_format)
                sheet1.write(row, 22, 0.00, numeric_format)
                sheet1.write(row, 23, 0.00, numeric_format)
                sheet1.write(row, 24, each_employee.child_education_deductions or 0.00, numeric_format)
                sheet1.write(row, 25, each_employee.hra_deductions or 0.00, numeric_format)
                sheet1.write(row, 26, 0.00, numeric_format)
                sheet1.write(row, 27, 0.00, numeric_format)
                sheet1.write(row, 28, 0.00, numeric_format)
                sheet1.write(row, 29, each_employee.coin_adjustment or 0.00, numeric_format)
                
                row += 1
            
            workbook.close()
            output.seek(0)
            workbook_data = output.read()
            output.close()
            
            # Save the workbook as base64 to the model
            each.write({'report_name': each.name + "_Template.xlsx", 'output': base64.b64encode(workbook_data)})
            
            return {
                'name': _('Payroll Template'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'hr.payroll.custom.upload.template',
                'res_id': each.id,
                'type': 'ir.actions.act_window',
                'target': 'new'
            }
