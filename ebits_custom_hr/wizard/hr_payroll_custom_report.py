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

# class HRPayrollCustomWizard(models.TransientModel):
#     _name = "hr.payroll.custom.report"
#     _description = "HR Payroll Custom Report Wizard"
    
#     production_unit_id = fields.Many2one('res.production.unit', string='Unit', required=True, copy=False)
#     date_from = fields.Date(string='Period Start', default=time.strftime('%Y-%m-01'), required=True, copy=False)
#     date_to = fields.Date(string='Period End', default=str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10], required=True, copy=False)
#     name = fields.Char(string='Name', required=True, copy=False)
#     company_id = fields.Many2one('res.company', string='Company', copy=False, default=lambda self: self.env['res.company']._company_default_get())
#     report_name = fields.Char(string='File Name', readonly=True)
#     output = fields.Binary(string='format', readonly=True)
    
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
        
        
#     def action_print_report(self):
#         payroll_obj = self.env['hr.payroll.custom']
#         payroll_line_obj = self.env['hr.payroll.custom.line']
#         report_name = "Employee Salary Slip Report"
#         report_summary_name = "Employee Salary Slip Summary"
#         from_date = time.strptime(self.date_from, "%Y-%m-%d")
#         from_date = time.strftime('%d-%m-%Y', from_date)
#         to_date = time.strptime(self.date_to, "%Y-%m-%d")
#         to_date = time.strftime('%d-%m-%Y', to_date)
#         for each in self:
#             payroll_employee_search = payroll_line_obj.sudo().search([('payroll_id.production_unit_id', '=', each.production_unit_id.id), ('date_from', '>=', each.date_from), ('date_to', '<=', each.date_to), ('payroll_id.state', 'in', ('approved', 'done'))])
            
#             Style = ExcelStyles()
#             wbk = xlwt.Workbook()
#             sheet1 = wbk.add_sheet(each.name)
#             sheet1.set_panes_frozen(True)
#             sheet1.set_horz_split_pos(3)
#             sheet1.col(0).width = 4000
#             sheet1.col(1).width = 3000
#             sheet1.col(2).width = 3000
#             sheet1.col(3).width = 5500
#             sheet1.col(4).width = 9000
#             sheet1.col(5).width = 4000
#             sheet1.col(6).width = 4000
#             sheet1.col(7).width = 4000
#             sheet1.col(8).width = 4000
#             sheet1.col(9).width = 4000
#             sheet1.col(10).width = 4000
#             sheet1.col(11).width = 4000
#             sheet1.col(12).width = 4000
#             sheet1.col(13).width = 4000
#             sheet1.col(14).width = 4000
#             sheet1.col(15).width = 4000
# #            sheet1.col(16).width = 4000
#             sheet1.col(16).width = 4000
#             sheet1.col(17).width = 4000
#             sheet1.col(18).width = 4000
#             sheet1.col(19).width = 4000
#             sheet1.col(20).width = 4000
#             sheet1.col(21).width = 4000
#             sheet1.col(22).width = 4000
#             sheet1.col(23).width = 4000
# #            sheet1.col(25).width = 4000
#             sheet1.col(24).width = 4000
#             sheet1.col(25).width = 4000
#             sheet1.col(26).width = 4000
#             sheet1.col(27).width = 4000
#             sheet1.col(28).width = 4000
#             sheet1.col(29).width = 4000
#             sheet1.col(30).width = 4000
#             sheet1.col(31).width = 4000
#             sheet1.col(32).width = 4000
        
#             rc = 0
#             row = 1
#             sheet1.row(rc).height = 700
#             sheet1.row(row).height = 700

#             title = report_name +' ( Period Start :' + from_date + ' , End :' + to_date + ' )'
#             sheet1.write_merge(rc, rc, 0, 30, (self.company_id and self.company_id.name or ' '), Style.title_ice_blue())
#             sheet1.write_merge(row, row, 0, 30, title, Style.title_ice_blue())
#             row = 2
#             sheet1.row(row).height = 700
#             sheet1.write(row, 0, "Unit", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 1, "Period Start", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 2, "Period End", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 3, "Name", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 4, "Employee", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 5, "Basic", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 6, "Transport", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 7, "HRA", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 8, "Professional", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 9, "Misc", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 10, "OT", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 11, "Earnings Child Education", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 12, "Bonus", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 13, "Night Allownace", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 14, "Arrears", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 15, "Leave Allownace", Style.contentTextBold(row, 'black', 'white'))
# #            sheet1.write(row, 16, "House", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 16, "Gross Earnings", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 17, "NPF", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 18, "Payee", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 19, "PPF", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 20, "Tuico", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 21, "Salary Advance", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 22, "Loan", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 23, "Deductions Child Education", Style.contentTextBold(row, 'black', 'white'))
# #            sheet1.write(row, 25, "House Deduction", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 24, "HRA Deduction", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 25, "Bonus Deduction", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 26, "Misc Deduction", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 27, "Absent", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 28, "Coin Adj", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 29, "Gross Deductions", Style.contentTextBold(row, 'black', 'white'))
#             sheet1.write(row, 30, "Net Pay", Style.contentTextBold(row, 'black', 'white'))
            
#             basic, transp, hra_earnings, prof_all, misc_earnings, over_time, child_education_earnings = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
#             bonus_earnings, night_allowance, arres, leave_allowance, house_earnings, earnings_gross = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
#             npf, payee, ppf, tuico, salary_advance, loan, child_education_deductions = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
#             house_deductions, hra_deductions, bonus_deductions, misc, absent, coin_adjustment, deductions_gross, net_pay = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00 
            
#             for each_employee in payroll_employee_search:
#                 row += 1
#                 sheet1.row(row).height = 500
#                 sheet1.write(row, 0, each.production_unit_id.name, Style.normal_left())
#                 sheet1.write(row, 1, from_date, Style.normal_left())
#                 sheet1.write(row, 2, to_date, Style.normal_left())
#                 sheet1.write(row, 3, each.name, Style.normal_left())
#                 #for line in each_employee.payroll_lines:
#                 sheet1.write(row, 4, each_employee.employee_id and each_employee.employee_id.name_get()[0][1] or '', Style.normal_left())
#                 sheet1.write(row, 5, each_employee.basic and each_employee.basic or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 6, each_employee.transp and each_employee.transp or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 7, each_employee.hra_earnings and each_employee.hra_earnings or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 8, each_employee.prof_all and each_employee.prof_all or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 9, each_employee.misc_earnings and each_employee.misc_earnings or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 10, each_employee.over_time and each_employee.over_time or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 11, each_employee.child_education_earnings and each_employee.child_education_earnings or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 12, each_employee.bonus_earnings and each_employee.bonus_earnings or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 13, each_employee.night_allowance and each_employee.night_allowance or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 14, each_employee.arres and each_employee.arres or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 15, each_employee.leave_allowance and each_employee.leave_allowance or 0.00, Style.normal_num_right_3separator())
# #                sheet1.write(row, 16, each_employee.house_earnings and each_employee.house_earnings or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 16, each_employee.earnings_gross and each_employee.earnings_gross or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 17, each_employee.npf and each_employee.npf or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 18, each_employee.payee and each_employee.payee or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 19, each_employee.ppf and each_employee.ppf or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 20, each_employee.tuico and each_employee.tuico or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 21, each_employee.salary_advance and each_employee.salary_advance or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 22, each_employee.loan and each_employee.loan or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 23, each_employee.child_education_deductions and each_employee.child_education_deductions or 0.00, Style.normal_num_right_3separator())
# #                sheet1.write(row, 25, each_employee.house_deductions and each_employee.house_deductions or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 24, each_employee.hra_deductions and each_employee.hra_deductions or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 25, each_employee.bonus_deductions and each_employee.bonus_deductions or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 26, each_employee.misc and each_employee.misc or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 27, each_employee.absent and each_employee.absent or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 28, each_employee.coin_adjustment and each_employee.coin_adjustment or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 29, each_employee.deductions_gross and each_employee.deductions_gross or 0.00, Style.normal_num_right_3separator())
#                 sheet1.write(row, 30, each_employee.net_pay and each_employee.net_pay or 0.00, Style.normal_num_right_3separator())
#                 basic += each_employee.basic
#                 transp += each_employee.transp
#                 hra_earnings += each_employee.hra_earnings
#                 prof_all += each_employee.prof_all
#                 misc_earnings += each_employee.misc_earnings
#                 over_time += each_employee.over_time
#                 child_education_earnings += each_employee.child_education_earnings
#                 bonus_earnings += each_employee.bonus_earnings
#                 night_allowance += each_employee.night_allowance
#                 arres += each_employee.arres
#                 leave_allowance += each_employee.leave_allowance
# #                house_earnings += each_employee.house_earnings
#                 earnings_gross += each_employee.earnings_gross
#                 npf += each_employee.npf
#                 payee += each_employee.payee
#                 ppf += each_employee.ppf
#                 tuico += each_employee.tuico
#                 salary_advance += each_employee.salary_advance
#                 loan += each_employee.loan
#                 child_education_deductions += each_employee.child_education_deductions
# #                house_deductions += each_employee.house_deductions
#                 hra_deductions += each_employee.hra_deductions
#                 bonus_deductions += each_employee.bonus_deductions
#                 misc += each_employee.misc
#                 absent += each_employee.absent
#                 coin_adjustment += each_employee.coin_adjustment
#                 deductions_gross += each_employee.deductions_gross
#                 net_pay += each_employee.net_pay
#             row +=1
#             sheet1.write_merge(row, row, 0, 4, 'Total', Style.groupByTitle())
#             sheet1.write(row, 5, basic, Style.groupByTotal3Separator())
#             sheet1.write(row, 6, transp, Style.groupByTotal3Separator())
#             sheet1.write(row, 7, hra_earnings, Style.groupByTotal3Separator())
#             sheet1.write(row, 8, prof_all, Style.groupByTotal3Separator())
#             sheet1.write(row, 9, misc_earnings, Style.groupByTotal3Separator())
#             sheet1.write(row, 10, over_time, Style.groupByTotal3Separator())
#             sheet1.write(row, 11, child_education_earnings, Style.groupByTotal3Separator())
#             sheet1.write(row, 12, bonus_earnings, Style.groupByTotal3Separator())
#             sheet1.write(row, 13, night_allowance, Style.groupByTotal3Separator())
#             sheet1.write(row, 14, arres, Style.groupByTotal3Separator())
#             sheet1.write(row, 15, leave_allowance, Style.groupByTotal3Separator())
# #            sheet1.write(row, 16, house_earnings, Style.groupByTotal3Separator())
#             sheet1.write(row, 16, earnings_gross, Style.groupByTotal3Separator())
#             sheet1.write(row, 17, npf, Style.groupByTotal3Separator())
#             sheet1.write(row, 18, payee, Style.groupByTotal3Separator())
#             sheet1.write(row, 19, ppf, Style.groupByTotal3Separator())
#             sheet1.write(row, 20, tuico, Style.groupByTotal3Separator())
#             sheet1.write(row, 21, salary_advance, Style.groupByTotal3Separator())
#             sheet1.write(row, 22, loan, Style.groupByTotal3Separator())
#             sheet1.write(row, 23, child_education_deductions, Style.groupByTotal3Separator())
# #            sheet1.write(row, 25, house_deductions, Style.groupByTotal3Separator())
#             sheet1.write(row, 24, hra_deductions, Style.groupByTotal3Separator())
#             sheet1.write(row, 25, bonus_deductions, Style.groupByTotal3Separator())
#             sheet1.write(row, 26, misc, Style.groupByTotal3Separator())
#             sheet1.write(row, 27, absent, Style.groupByTotal3Separator())
#             sheet1.write(row, 28, coin_adjustment, Style.groupByTotal3Separator())
#             sheet1.write(row, 29, deductions_gross, Style.groupByTotal3Separator())
#             sheet1.write(row, 30, net_pay, Style.groupByTotal3Separator())
                
# #==============================Employee Salary Slip Summary=============================================

#             sheet2 = wbk.add_sheet(report_summary_name)
#             sheet2.col(0).width = 4000
#             sheet2.col(1).width = 3000
#             sheet2.col(2).width = 8000
#             sheet2.col(3).width = 5500
#             sheet2.col(4).width = 6000
#             sheet2.col(5).width = 8000
#             sheet2.col(6).width = 8000
#             sheet2.col(7).width = 5500
#             sheet2.col(8).width = 4000
#             sheet2.col(9).width = 4000
#             sheet2.col(10).width = 4000
#             sheet2.col(11).width = 4000
#             sheet2.col(12).width = 4000
#             sheet2.col(13).width = 4000
#             sheet2.col(14).width = 4000
#             sheet2.col(15).width = 4000
#             sheet2.col(16).width = 4000
#             sheet2.col(17).width = 4000
#             sheet2.col(18).width = 4000
#             sheet2.col(19).width = 4000
#             sheet2.col(20).width = 4000
#             sheet2.col(21).width = 4000
#             sheet2.col(22).width = 4000
#             sheet2.col(23).width = 4000
#             sheet2.col(24).width = 4000
#             sheet2.col(25).width = 4000
#             sheet2.col(26).width = 4000
#             sheet2.col(27).width = 4000
#             sheet2.col(28).width = 4000
#             sheet2.col(29).width = 4000
#             sheet2.col(30).width = 4000
#             sheet2.col(31).width = 4000
#             sheet2.col(32).width = 4000
        
#             sheet2.row(0).height = 700
#             sheet2.row(1).height = 700
#             title = report_summary_name +' ( Period Start :' + from_date + ' , End :' + to_date + ' )' + ' - Unit : ' + str(self.production_unit_id and self.production_unit_id.name or '')
#             sheet2.write_merge(0, 0, 0, 7, (self.company_id and self.company_id.name or ' '), Style.title_ice_blue())
#             sheet2.write_merge(1, 1, 0, 7, title, Style.title_ice_blue())
#             row = 2
#             sheet2.row(2).height = 700
#             sheet2.write_merge(2, 2,  2, 3,  "EARNINGS", Style.subTitle())
#             sheet2.write_merge(2, 2,  5, 6,  "DEDUCTIONS", Style.subTitle())
#             sheet2.write(3, 2, "Basic", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(4, 2, "Transport", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(5, 2, "HRA", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(6, 2, "Professional", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(7, 2, "Misc", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(8, 2, "OT", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(9, 2, "Child Education", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(10, 2, "Bonus", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(11, 2, "Night Allownace", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(12, 2, "Arrears", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(13, 2, "Leave Allownace", Style.contentTextBold(row, 'black', 'white'))
# #            sheet2.write(14, 2, "House", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(17, 2, "Gross Earnings", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(3, 5, "NPF", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(4, 5, "Payee", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(5, 5, "PPF", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(6, 5, "Tuico", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(7, 5, "Salary Advance", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(8, 5, "Loan", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(9, 5, "Child Education", Style.contentTextBold(row, 'black', 'white'))
# #            sheet2.write(10, 5, "House Deduction", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(10, 5, "HRA Deduction", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(11, 5, "Bonus Deduction", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(12, 5, "Misc Deduction", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(13, 5, "Absent", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(14, 5, "Coin Adj", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(17, 5, "Gross Deductions", Style.contentTextBold(row, 'black', 'white'))
#             sheet2.write(19, 2, "Net Pay", Style.contentTextBold(row, 'black', 'white'))
            
#             sheet2.write(3, 3, basic, Style.normal_num_right_3separator())
#             sheet2.write(4, 3, transp, Style.normal_num_right_3separator())
#             sheet2.write(5, 3, hra_earnings, Style.normal_num_right_3separator())
#             sheet2.write(6, 3, prof_all, Style.normal_num_right_3separator())
#             sheet2.write(7, 3, misc_earnings, Style.normal_num_right_3separator())
#             sheet2.write(8, 3, over_time, Style.normal_num_right_3separator())
#             sheet2.write(9, 3, child_education_earnings, Style.normal_num_right_3separator())
#             sheet2.write(10, 3, bonus_earnings, Style.normal_num_right_3separator())
#             sheet2.write(11, 3, night_allowance, Style.normal_num_right_3separator())
#             sheet2.write(12, 3, arres, Style.normal_num_right_3separator())
#             sheet2.write(13, 3, leave_allowance, Style.normal_num_right_3separator())
# #            sheet2.write(14, 3, house_earnings, Style.normal_num_right_3separator())
#             sheet2.write(17, 3, earnings_gross, Style.groupByTotal3Separator())
#             sheet2.write(3, 6, npf, Style.normal_num_right_3separator())
#             sheet2.write(4, 6, payee, Style.normal_num_right_3separator())
#             sheet2.write(5, 6, ppf, Style.normal_num_right_3separator())
#             sheet2.write(6, 6, tuico, Style.normal_num_right_3separator())
#             sheet2.write(7, 6, salary_advance, Style.normal_num_right_3separator())
#             sheet2.write(8, 6, loan, Style.normal_num_right_3separator())
#             sheet2.write(9, 6, child_education_deductions, Style.normal_num_right_3separator())
# #            sheet2.write(10, 6, house_deductions, Style.normal_num_right_3separator())
#             sheet2.write(10, 6, hra_deductions, Style.normal_num_right_3separator())
#             sheet2.write(11, 6, bonus_deductions, Style.normal_num_right_3separator())
#             sheet2.write(12, 6, misc, Style.normal_num_right_3separator())
#             sheet2.write(13, 6, absent, Style.normal_num_right_3separator())
#             sheet2.write(14, 6, coin_adjustment, Style.normal_num_right_3separator())
#             sheet2.write(17, 6, deductions_gross, Style.groupByTotal3Separator())
#             sheet2.write(19, 3, net_pay, Style.groupByTotal3Separator())
            
#             stream = cStringIO.StringIO()
#             wbk.save(stream)

#             each.write({'report_name': each.name + '.xls', 'output': base64.encodestring(stream.getvalue())})
#             return {
#                     'name': _('Payroll Report'),
#                     'view_type': 'form',
#                     'view_mode': 'form',
#                     'res_model': 'hr.payroll.custom.report',
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

class HRPayrollCustomWizard(models.TransientModel):
    _name = "hr.payroll.custom.report"
    _description = "HR Payroll Custom Report Wizard"
    
    production_unit_id = fields.Many2one('res.production.unit', string='Unit', required=True, copy=False)
    date_from = fields.Date(string='Period Start', default=lambda self: fields.Date.today().replace(day=1), required=True, copy=False)
    date_to = fields.Date(string='Period End', default=lambda self: (datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1)).strftime('%Y-%m-%d'), required=True, copy=False)
    name = fields.Char(string='Name', required=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', copy=False, default=lambda self: self.env['res.company']._company_default_get())
    report_name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.onchange('date_from', 'date_to')
    def onchange_period(self):
        if (not self.date_from) or (not self.date_to):
            self.name = ""
            return
        date_from = fields.Date.from_string(self.date_from)
        date_to = fields.Date.from_string(self.date_to)
        locale = self.env.context.get('lang', 'en_US')
        self.name = _('Salary Slip for %s') % (tools.ustr(babel.dates.format_date(date=date_from, format='MMMM-y', locale=locale)))
        
    def action_print_report(self):
        payroll_line_obj = self.env['hr.payroll.custom.line']
        report_name = "Employee Salary Slip Report"
        report_summary_name = "Employee Salary Slip Summary"
        from_date = fields.Date.from_string(self.date_from).strftime('%d-%m-%Y')
        to_date = fields.Date.from_string(self.date_to).strftime('%d-%m-%Y')
        
        payroll_employee_search = payroll_line_obj.sudo().search([
            ('payroll_id.production_unit_id', '=', self.production_unit_id.id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('payroll_id.state', 'in', ('approved', 'done'))
        ])
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet1 = workbook.add_worksheet(self.name)
        
        # Define cell formats with xlsxwriter
        title_format = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        data_format = workbook.add_format({'align': 'left'})
        numeric_format = workbook.add_format({'num_format': '#,##0.00'})
        
        # Set column widths
        columns_width = [4000, 3000, 3000, 5500, 9000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000]
        for i, width in enumerate(columns_width):
            sheet1.set_column(i, i, width)
        
        rc = 0
        row = 1
        
        # Write title and headers
        sheet1.merge_range(rc, 0, rc, 30, (self.company_id.name if self.company_id else ''), title_format)
        sheet1.merge_range(row, 0, row, 30, f'{report_name} ( Period Start: {from_date}, End: {to_date} )', title_format)
        row = 2
        headers = ["Unit", "Period Start", "Period End", "Name", "Employee", "Basic", "Transport", "HRA", "Professional", "Misc", "OT", "Earnings Child Education", "Bonus", "Night Allownace", "Arrears", "Leave Allownace", "Gross Earnings", "NPF", "Payee", "PPF", "Tuico", "Salary Advance", "Loan", "Deductions Child Education", "HRA Deduction", "Bonus Deduction", "Misc Deduction", "Absent", "Coin Adj", "Gross Deductions", "Net Pay"]
        for col, header in enumerate(headers):
            sheet1.write(row, col, header, header_format)
        
        row += 1
        total_row = row
        
        # Initialize totals
        totals = {header: 0.00 for header in headers[5:]}
        
        # Write data rows
        for each_employee in payroll_employee_search:
            row += 1
            data = [
                each.production_unit_id.name,
                from_date,
                to_date,
                each.name,
                each_employee.employee_id.name_get()[0][1] if each_employee.employee_id else '',
                each_employee.basic or 0.00,
                each_employee.transp or 0.00,
                each_employee.hra_earnings or 0.00,
                each_employee.prof_all or 0.00,
                each_employee.misc_earnings or 0.00,
                each_employee.over_time or 0.00,
                each_employee.child_education_earnings or 0.00,
                each_employee.bonus_earnings or 0.00,
                each_employee.night_allowance or 0.00,
                each_employee.arres or 0.00,
                each_employee.leave_allowance or 0.00,
                each_employee.earnings_gross or 0.00,
                each_employee.npf or 0.00,
                each_employee.payee or 0.00,
                each_employee.ppf or 0.00,
                each_employee.tuico or 0.00,
                each_employee.salary_advance or 0.00,
                each_employee.loan or 0.00,
                each_employee.child_education_deductions or 0.00,
                each_employee.hra_deductions or 0.00,
                each_employee.bonus_deductions or 0.00,
                each_employee.misc or 0.00,
                each_employee.absent or 0.00,
                each_employee.coin_adjustment or 0.00,
                each_employee.deductions_gross or 0.00,
                each_employee.net_pay or 0.00
            ]
            sheet1.write_row(row, 0, data, data_format)
            
            # Update totals
            for i in range(5, len(headers)):
                totals[headers[i]] += data[i]
        
        # Write totals row
        row += 1
        sheet1.merge_range(row, 0, row, 4, 'Total', header_format)
        for col, header in enumerate(headers[5:]):
            sheet1.write(row, col + 5, totals[header], numeric_format)
        
        # Save workbook and generate output
        workbook.close()
        output.seek(0)
        self.write({
            'output': base64.b64encode(output.read()),
            'report_name': f'{report_name}_{self.date_from}_{self.date_to}.xlsx'
        })
        
        return {
            'name': 'Download Payslip Report',
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=hr.payroll.custom.report&id={}&field=output&filename={}'.format(
                self.id, self.report_name),
            'target': 'self',
        }
