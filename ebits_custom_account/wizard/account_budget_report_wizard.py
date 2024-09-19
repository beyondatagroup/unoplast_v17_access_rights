# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
import xlwt
import cStringIO
import base64
import xlrd
import parser

class AccountBudgetReportWizard(models.TransientModel):
    _name = 'account.budget.report.wizard'
    _description = 'Account Budget Report Wizard'
    
    budget_ids = fields.Many2many('crossovered.budget', 'etc_account_budget_crossovered_budget', 'acc_budget_wizard_id', 'budget_id', string='Budget', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name= fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.multi
    def action_report(self):
        budget_sql = """ """
        filters = ""
        budget_ids = []
        budget_list = []
        budget_str = ""
        if self.budget_ids:
            for each_id in self.budget_ids:
                budget_ids.append(each_id.id)
                budget_list.append(each_id.name)
            budget_list = list(set(budget_list))
            budget_str = str(budget_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(budget_ids) > 1:
                budget_sql += "where cb.id in "+ str(tuple(budget_ids))
            else:
                budget_sql += "where cb.id in ("+ str(budget_ids[0]) + ")"
            filters += "Filter Based on Budget : " + budget_str
        report_name = "Budget Vs Actual Report"
        crossovered_budget_sql = """select
                                    cb.name as budget_name,
                                    cb.id as budget_id,
                                    rp.name as responsible,
                                    res.name as approved_by,
                                    to_char(cb.date_approved, 'dd-mm-yyyy') as approved_date,
                                    to_char(cb.date_from, 'dd-mm-yyyy') as from_date,
                                    to_char(cb.date_to, 'dd-mm-yyyy') as from_to
                                from crossovered_budget cb
                                    left join res_users ru on (ru.id = cb.creating_user_id)
                                    left join res_partner rp on (rp.id = ru.partner_id)
                                    left join res_users users on (users.id = cb.approved_user_id)
                                    left join res_partner res on (res.id = users.partner_id)"""+budget_sql
                                    
        account_budget_sql = """select
	                                concat( '[' , ac.code, '] ', ac.name) as account_name,
	                                cb.id as budget_id,
	                                abl.planned_amount as planned_amount,
	                                (select (case when sum(aml.debit) is not null then sum(aml.debit) else 0.00 end) 
		                                from account_move_line aml
			                                left join account_move am on (am.id = aml.move_id) 
		                                where aml.account_id = abl.account_id and am.date >= cb.date_from and am.date <= cb.date_to and am.state='posted') as actual_amount
                                from account_budget_lines abl
	                                left join crossovered_budget cb on (cb.id = abl.crossovered_budget_id)
	                                left join account_account ac on (ac.id = abl.account_id)
                                where cb.id = %s order by ac.code asc """
        
        self.env.cr.execute(crossovered_budget_sql)
        crossovered_budget_data = self.env.cr.dictfetchall()
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4000
        sheet1.col(2).width = 4000
        sheet1.col(3).width = 4000
        sheet1.col(4).width = 4300
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 4000
        sheet1.col(7).width = 8000
        sheet1.col(8).width = 4200
        sheet1.col(9).width = 4200
        sheet1.col(10).width = 4000
    
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 500
        sheet1.row(r1).height = 400
        sheet1.row(r2).height = 256 * 2
        sheet1.row(r3).height = 256 * 2
        title = report_name 
        title1 = self.company_id.name
        title2 = filters 
        sheet1.write_merge(rc, rc, 0, 10, title1, Style.main_title())
        sheet1.write_merge(r1, r1, 0, 10, title, Style.sub_main_title())
        sheet1.write_merge(r2, r2, 0, 10, title2, Style.subTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Budget", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Responsible", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Approved By", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "From Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "To Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Account", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Planned Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Actual Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Percentage", Style.contentTextBold(r2,'black','white'))
        
        row = r3
        s_no = 0
        for each in crossovered_budget_data:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 350
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['budget_name'], Style.normal_left())
            sheet1.write(row, 2, each['responsible'], Style.normal_left())
            sheet1.write(row, 3, each['approved_by'], Style.normal_left())
            sheet1.write(row, 4, each['approved_date'], Style.normal_left())
            sheet1.write(row, 5, each['from_date'], Style.normal_left())
            sheet1.write(row, 6, each['from_to'], Style.normal_left())
            
            self.env.cr.execute(account_budget_sql , (each['budget_id'],))
            account_budget_data = self.env.cr.dictfetchall()
            planned_amount = actual_amount = 0.00 
            for line in account_budget_data:
                sheet1.row(row).height = 600
                sheet1.write(row, 7, line['account_name'], Style.normal_left())
                sheet1.write(row, 8, line['planned_amount'], Style.normal_num_right_3separator())
                sheet1.write(row, 9, line['actual_amount'], Style.normal_num_right_3separator())
                percentage = (((line['actual_amount'] or 0.00) / (line['planned_amount'] and line['planned_amount'] or 1.00)) * 100)
                sheet1.write(row, 10, percentage, Style.normal_num_right())
                planned_amount += (line['planned_amount'] or 0.00)
                actual_amount += (line['actual_amount'] or 0.00)
                row = row + 1
            row = row - 1
            if planned_amount and actual_amount:
                row = row + 1
                sheet1.write(row, 7, "Total", Style.groupByTitle())
                sheet1.write(row, 8, planned_amount, Style.groupByTotal3Separator())
                sheet1.write(row, 9, actual_amount, Style.groupByTotal3Separator())
                total_percentage = ((actual_amount/planned_amount) * 100)
                sheet1.write(row, 10, total_percentage, Style.groupByTotal())
            
        stream = cStringIO.StringIO()
        wbk.save(stream)

        self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.budget.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
