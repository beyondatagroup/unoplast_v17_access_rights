# # -*- coding: utf-8 -*-
# # Part of Odoo. See LICENSE file for full copyright and licensing details.

# from dateutil.relativedelta import relativedelta
# from datetime import datetime, timedelta
# import time
# from odoo import api, fields, models, _
# from odoo.tools.translate import _
# from excel_styles import ExcelStyles
# import xlwt
# import cStringIO
# import base64
# import xlrd
# import parser
# from lxml import etree

# class HrLoanReportWizard(models.TransientModel):
#     _name = 'hr.loan.report.wizard'
#     _description = 'HR Loan Report Wizard'
    
#     date_from = fields.Date(string='From Date', required=True)
#     date_to = fields.Date(string='To Date', required=True)
#     loan_type_ids = fields.Many2many('loan.type', 'etc_hr_loan_type', 'hr_loan_wizard_id', 'loan_type_id', string='Loan Type')
#     warehouse_ids = fields.Many2many('stock.warehouse', 'etc_hr_loan_warehouse', 'hr_loan_wizard_id', 'warehouse_id', string='Warehouse')
#     employee_ids = fields.Many2many('hr.employee', 'etc_hr_loan_employee', 'hr_loan_wizard_id', 'employee_id', string='Employee')
#     unit_ids = fields.Many2many('res.production.unit', 'etc_hr_loan_production_unit', 'hr_loan_wizard_id', 'unit_id', string='Unit')
#     company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
#     state = fields.Selection([
#         ('draft', 'Draft'), 
#         ('wait', 'Waiting For Approval'), 
#         ('approved', 'Approved'), 
#         ('done', 'Done'), 
#         ('cancel', 'Cancelled')
#         ], string='State')
#     name = fields.Char(string='File Name', readonly=True)
#     output = fields.Binary(string='format', readonly=True)
    
#     @api.model
#     def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
#         res = super(HrLoanReportWizard, self).fields_view_get(
#             view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
#         if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
#             doc = etree.XML(res['arch'])
#             for node in doc.xpath("//field[@name='warehouse_ids']"):
#                 warehouse_id = []
#                 for each in self.env.user.sudo().default_warehouse_ids:
#                     warehouse_id.append(each.id)
#                 node.set('domain', "[('id', 'in', " + str(warehouse_id) + ")]")
#             res['arch'] = etree.tostring(doc)
#         return res
    
     
#     def action_report(self):
#         date_from = self.date_from
#         date_to = self.date_to
#         report_name = "Loan Report"
#         from_date = time.strptime(self.date_from, "%Y-%m-%d")
#         from_date = time.strftime('%d-%m-%Y', from_date)
#         to_date = time.strptime(self.date_to, "%Y-%m-%d")
#         to_date = time.strftime('%d-%m-%Y', to_date)
#         filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date)
#         loan_type_sql = """ """
#         state_sql = """ """
#         warehouse_sql = """ """
#         employee_sql = """ """
#         unit_sql = """ """
        
#         loan_type_ids = []
#         loan_type_list = []
#         loan_type_str = ""
        
#         warehouse_ids = []
#         warehouse_list = []
#         warehouse_str = ""
        
#         employee_ids = []
#         employee_list = []
#         employee_str = ""
        
#         unit_ids = []
#         unit_list = []
#         unit_str = ""
        
#         if self.loan_type_ids:
#             for each_id in self.loan_type_ids:
#                 loan_type_ids.append(each_id.id)
#                 loan_type_list.append(each_id.name)
#             loan_type_list = list(set(loan_type_list))
#             loan_type_str = str(loan_type_list).replace('[','').replace(']','').replace("u'","").replace("'","")
#             if len(loan_type_ids) > 1:
#                 loan_type_sql += "and hl.loan_type_id in "+ str(tuple(loan_type_ids))
#             else:
#                 loan_type_sql += "and hl.loan_type_id in ("+ str(loan_type_ids[0]) + ")"
#             filters += ", Loan Type: " + loan_type_str
#         if self.warehouse_ids:
#             for each_id in self.warehouse_ids:
#                 warehouse_ids.append(each_id.id)
#                 warehouse_list.append(each_id.name)
#             warehouse_list = list(set(warehouse_list))
#             warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
#             if len(warehouse_ids) > 1:
#                 warehouse_sql += "and hl.warehouse_id in "+ str(tuple(warehouse_ids))
#             else:
#                 warehouse_sql += "and hl.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
#             filters += ", warehouse: " + warehouse_str
#         if self.employee_ids:
#             for each_id in self.employee_ids:
#                 employee_ids.append(each_id.id)
#                 employee_list.append(each_id.name)
#             employee_list = list(set(employee_list))
#             employee_str = str(employee_list).replace('[','').replace(']','').replace("u'","").replace("'","")
#             if len(employee_ids) > 1:
#                 employee_sql += "and hl.employee_id in "+ str(tuple(employee_ids))
#             else:
#                 employee_sql += "and hl.employee_id in ("+ str(employee_ids[0]) + ")"
#             filters += ", Employee: " + employee_str
#         if self.unit_ids:
#             for each_id in self.unit_ids:
#                 unit_ids.append(each_id.id)
#                 unit_list.append(each_id.name)
#             unit_list = list(set(unit_list))
#             unit_str = str(unit_list).replace('[','').replace(']','').replace("u'","").replace("'","")
#             if len(unit_ids) > 1:
#                 unit_sql += "and hl.production_unit_id in "+ str(tuple(unit_ids))
#             else:
#                 unit_sql += "and hl.production_unit_id in ("+ str(unit_ids[0]) + ")"
#             filters += ", Unit: " + unit_str
#         if self.state:
#             state_sql = " and hl.state = " + "'" + str(self.state) + "'"
#             if self.state == 'draft':
#                 filters += ", State : Draft"
#             if self.state == 'wait':
#                 filters += ", State : Waiting For Approval"
#             if self.state == 'approved':
#                 filters += ", State : Approved"
#             if self.state == 'done':
#                 filters += ", State : Done"
#             if self.state == 'cancel':
#                 filters += ", State : Cancelled"
#         else:
#             state_sql = " and hl.state != 'cancel'" 
#         hr_loan_sql = """ select
#                                 hl.name as loan_no,
#                                 hl.id as id,
#                                 rp.name as creator,
#                                 to_char(hl.request_date, 'dd-mm-yyyy') as request_date,
#                                 hl.request_amt as request_amt,
#                                 hl.repay_period as repay_period,
#                                 hr.name_related as employee,
#                                 rpu.name as unit,
#                                 sw.name as warehouse,
#                                 partner.name as approved_by,
#                                 to_char(hl.approved_date, 'dd-mm-yyyy') as approved_date,
#                                 hl.approved_amt as approved_amt,
#                                 hl.approve_repay_period as approve_repay_period,
#                                 lt.name as loan_type,
#                                 to_char(hl.deduction_date, 'dd-mm-yyyy') as deduction_date,
#                                 (case when hl.state = 'draft' then 'Draft'
#                                  when hl.state = 'wait' then 'Waiting For Approval'
#                                  when hl.state = 'approved' then 'Approved'
#                                  when hl.state = 'done' then 'Done'
#                                  when hl.state = 'cancel' then 'Cancelled' else hl.state end) as state,
#                                  (case when sum(emil.paid_amt) is not null then sum(emil.paid_amt) else 0.00 end) as paid_amount,
#                                  hl.remaining_amt as remaining_amt
#                             from hr_loan hl
#                                 left join res_users ru on (ru.id = hl.user_id)
#                                 left join res_partner rp on (rp.id = ru.partner_id)
#                                 left join res_users res on (res.id = hl.approved_id)
#                                 left join res_partner partner on (partner.id = res.partner_id)
#                                 left join loan_type lt on (lt.id = hl.loan_type_id)
#                                 left join hr_loan_emi_line emil on (emil.loan_id = hl.id)
#                                 left join hr_employee hr on (hr.id = hl.employee_id)
#                                 left join res_production_unit rpu on (rpu.id = hl.production_unit_id)
#                                 left join stock_warehouse sw on (sw.id = hl.warehouse_id)
#                             where (hl.request_date between %s and %s) """ + loan_type_sql + state_sql + warehouse_sql + employee_sql + unit_sql +""" group by rp.name,
#                                     hl.id,
#                                     hl.name, 
#                                     hr.name_related,
#                                     rpu.name,
#                                     sw.name,
#                                     hl.request_date,
#                                     hl.request_amt, 
#                                     hl.repay_period,
#                                     partner.name,
#                                     hl.approved_date,
#                                     hl.approved_amt,
#                                     hl.approve_repay_period,
#                                     lt.name,hl.deduction_date,
#                                     hl.state, hl.remaining_amt 
#                                     order by hl.id asc"""
                                
#         emi_line_sql = """ select
#                                 to_char(emil.date, 'dd-mm-yyyy') as emi_date,
#                                 emil.emi_amt as emi_amount,
#                                 to_char(emil.paid_date, 'dd-mm-yyyy')as paid_date,
#                                 emil.paid_amt as paid_amount
#                             from hr_loan_emi_line emil
#                                 left join hr_loan hl on (hl.id = emil.loan_id)
#                             where hl.id = %s 
#                             order by emil.date asc"""
        
#         self.env.cr.execute(hr_loan_sql , (date_from, date_to,))
#         hr_loan_data = self.env.cr.dictfetchall()
        
#         Style = ExcelStyles()
#         wbk = xlwt.Workbook()
#         sheet1 = wbk.add_sheet(report_name)
#         #sheet1.show_grid = False 
#         sheet1.col(0).width = 2000
#         sheet1.col(1).width = 5000
#         sheet1.col(2).width = 5000
#         sheet1.col(3).width = 5000
#         sheet1.col(4).width = 5000
#         sheet1.col(5).width = 5000
#         sheet1.col(6).width = 5000
#         sheet1.col(7).width = 5000
#         sheet1.col(8).width = 5000
#         sheet1.col(9).width = 5000
#         sheet1.col(10).width = 5000
#         sheet1.col(11).width = 5000
#         sheet1.col(12).width = 5000
#         sheet1.col(13).width = 5000
#         sheet1.col(14).width = 5000
#         sheet1.col(15).width = 5000
#         sheet1.col(16).width = 5000
#         sheet1.col(17).width = 5000
#         sheet1.col(18).width = 5000
#         sheet1.col(19).width = 5000
#         sheet1.col(20).width = 5000
#         sheet1.col(21).width = 5000
    
#         rc = 0
#         r1 = 1
#         r2 = 2
#         r3 = 3
#         sheet1.row(rc).height = 500
#         sheet1.row(r1).height = 400
#         sheet1.row(r2).height = 200 * 2
#         sheet1.row(r3).height = 256 * 2
#         title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
#         title1 = self.company_id.name
#         title2 = filters 
#         title3 = 'EMI Schedule'
#         sheet1.write_merge(rc, rc, 0, 21, title1, Style.main_title())
#         sheet1.write_merge(r1, r1, 0, 21, title, Style.sub_main_title())
#         sheet1.write_merge(r2, r2, 0, 17, title2, Style.subTitle())
#         sheet1.write_merge(r2, r2, 18, 21, title3, Style.subTitle())
        
#         sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 1, "Loan Request No", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 2, "Creator", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 3, "Request By", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 4, "Unit", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 5, "Warehouse", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 6, "Request Date", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 7, "Request Amount", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 8, "Repay Period", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 9, "Approved By", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 10, "Approved Date", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 11, "Approved Amount", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 12, "Approved Repay Period", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 13, "Loan Type", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 14, "First Deduction Date", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 15, "Total Paid Amount", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 16, "Remaining Amount", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 17, "State", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 18, "EMI Date", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 19, "EMI Amount", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 20, "Paid Date", Style.contentTextBold(r2,'black','white'))
#         sheet1.write(r3, 21, "Paid Amount", Style.contentTextBold(r2,'black','white'))
        
        
#         row = r3
#         s_no = 0
#         request_amount, approved_amount, paid_amt, remaining_amt = 0.00, 0.00, 0.00, 0.00
#         for each in hr_loan_data:
#             row += 1
#             s_no = s_no + 1
#             sheet1.row(row).height = 500
#             sheet1.write(row, 0, s_no, Style.normal_left())
#             sheet1.write(row, 1, each['loan_no'], Style.normal_left())
#             sheet1.write(row, 2, each['creator'], Style.normal_left())
#             sheet1.write(row, 3, each['employee'], Style.normal_left())
#             sheet1.write(row, 4, each['unit'], Style.normal_left())
#             sheet1.write(row, 5, each['warehouse'], Style.normal_left())
#             sheet1.write(row, 6, each['request_date'], Style.normal_left())
#             sheet1.write(row, 7, each['request_amt'], Style.normal_num_right())
#             sheet1.write(row, 8, each['repay_period'], Style.normal_center())
#             sheet1.write(row, 9, each['approved_by'], Style.normal_left())
#             sheet1.write(row, 10, each['approved_date'], Style.normal_left())
#             sheet1.write(row, 11, each['approved_amt'], Style.normal_num_right())
#             sheet1.write(row, 12, each['approve_repay_period'], Style.normal_center())
#             sheet1.write(row, 13, each['loan_type'], Style.normal_left())
#             sheet1.write(row, 14, each['deduction_date'], Style.normal_left())
#             sheet1.write(row, 15, each['paid_amount'], Style.normal_num_right())
#             sheet1.write(row, 16, each['remaining_amt'], Style.normal_num_right())  
#             sheet1.write(row, 17, each['state'], Style.normal_left())
            
#             request_amount += each['request_amt'] 
#             approved_amount += each['approved_amt']
#             paid_amt += each['paid_amount']
#             remaining_amt += each['remaining_amt'] 
            
#             self.env.cr.execute(emi_line_sql , (each['id'],))
#             emi_line_data = self.env.cr.dictfetchall()
#             if emi_line_data:
#                 for line in emi_line_data:
#                     sheet1.row(row).height = 500
#                     sheet1.write(row, 18, line['emi_date'], Style.normal_left())
#                     sheet1.write(row, 19, line['emi_amount'], Style.normal_num_right())
#                     sheet1.write(row, 20, line['paid_date'], Style.normal_left())
#                     sheet1.write(row, 21, line['paid_amount'], Style.normal_num_right())
#                     row = row + 1
#                 row = row - 1 
#         row= row + 1
#         sheet1.write_merge(row, row, 0, 6, 'Total Request Amount', Style.groupByTitle())
#         sheet1.write_merge(row, row, 7, 7, request_amount, Style.groupByTotal())
#         sheet1.write_merge(row, row, 8, 10, 'Total Approved Amount', Style.groupByTitle())
#         sheet1.write(row, 11, approved_amount, Style.groupByTotal())
#         sheet1.write_merge(row, row, 12, 14, 'Total Repaid Amount', Style.groupByTitle())  
#         sheet1.write(row, 15, paid_amt, Style.groupByTotal()) 
#         balance_amt = approved_amount - paid_amt
#         sheet1.write(row, 16, balance_amt, Style.groupByTotal())   

#         stream = cStringIO.StringIO()
#         wbk.save(stream)

#         self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
#         return {
#                 'name': _('Notification'),
#                 'view_type': 'form',
#                 'view_mode': 'form',
#                 'res_model': 'hr.loan.report.wizard',
#                 'res_id': self.id,
#                 'type': 'ir.actions.act_window',
#                 'target':'new'
#                 }



# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
import xlsxwriter
import io
import base64
from lxml import etree

class HrLoanReportWizard(models.TransientModel):
    _name = 'hr.loan.report.wizard'
    _description = 'HR Loan Report Wizard'
    
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    loan_type_ids = fields.Many2many('loan.type', 'etc_hr_loan_type', 'hr_loan_wizard_id', 'loan_type_id', string='Loan Type')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_hr_loan_warehouse', 'hr_loan_wizard_id', 'warehouse_id', string='Warehouse')
    employee_ids = fields.Many2many('hr.employee', 'etc_hr_loan_employee', 'hr_loan_wizard_id', 'employee_id', string='Employee')
    unit_ids = fields.Many2many('res.production.unit', 'etc_hr_loan_production_unit', 'hr_loan_wizard_id', 'unit_id', string='Unit')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    state = fields.Selection([
        ('draft', 'Draft'), 
        ('wait', 'Waiting For Approval'), 
        ('approved', 'Approved'), 
        ('done', 'Done'), 
        ('cancel', 'Cancelled')
        ], string='State')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(HrLoanReportWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='warehouse_ids']"):
                warehouse_id = []
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                node.set('domain', "[('id', 'in', " + str(warehouse_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res
    
    def action_report(self):
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Loan Report"
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date)
        loan_type_sql = """ """
        state_sql = """ """
        warehouse_sql = """ """
        employee_sql = """ """
        unit_sql = """ """
        
        loan_type_ids = []
        loan_type_list = []
        loan_type_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        employee_ids = []
        employee_list = []
        employee_str = ""
        
        unit_ids = []
        unit_list = []
        unit_str = ""
        
        if self.loan_type_ids:
            for each_id in self.loan_type_ids:
                loan_type_ids.append(each_id.id)
                loan_type_list.append(each_id.name)
            loan_type_list = list(set(loan_type_list))
            loan_type_str = str(loan_type_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(loan_type_ids) > 1:
                loan_type_sql += "and hl.loan_type_id in "+ str(tuple(loan_type_ids))
            else:
                loan_type_sql += "and hl.loan_type_id in ("+ str(loan_type_ids[0]) + ")"
            filters += ", Loan Type: " + loan_type_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and hl.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and hl.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", warehouse: " + warehouse_str
        if self.employee_ids:
            for each_id in self.employee_ids:
                employee_ids.append(each_id.id)
                employee_list.append(each_id.name)
            employee_list = list(set(employee_list))
            employee_str = str(employee_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(employee_ids) > 1:
                employee_sql += "and hl.employee_id in "+ str(tuple(employee_ids))
            else:
                employee_sql += "and hl.employee_id in ("+ str(employee_ids[0]) + ")"
            filters += ", Employee: " + employee_str
        if self.unit_ids:
            for each_id in self.unit_ids:
                unit_ids.append(each_id.id)
                unit_list.append(each_id.name)
            unit_list = list(set(unit_list))
            unit_str = str(unit_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(unit_ids) > 1:
                unit_sql += "and hl.production_unit_id in "+ str(tuple(unit_ids))
            else:
                unit_sql += "and hl.production_unit_id in ("+ str(unit_ids[0]) + ")"
            filters += ", Unit: " + unit_str
        if self.state:
            state_sql = " and hl.state = " + "'" + str(self.state) + "'"
            if self.state == 'draft':
                filters += ", State : Draft"
            if self.state == 'wait':
                filters += ", State : Waiting For Approval"
            if self.state == 'approved':
                filters += ", State : Approved"
            if self.state == 'done':
                filters += ", State : Done"
            if self.state == 'cancel':
                filters += ", State : Cancelled"
        else:
            state_sql = " and hl.state != 'cancel'" 
        hr_loan_sql = """ select
                                hl.name as loan_no,
                                hl.id as id,
                                rp.name as creator,
                                to_char(hl.request_date, 'dd-mm-yyyy') as request_date,
                                hl.request_amt as request_amt,
                                hl.repay_period as repay_period,
                                hr.name_related as employee,
                                rpu.name as unit,
                                sw.name as warehouse,
                                partner.name as approved_by,
                                to_char(hl.approved_date, 'dd-mm-yyyy') as approved_date,
                                hl.approved_amt as approved_amt,
                                hl.approve_repay_period as approve_repay_period,
                                lt.name as loan_type,
                                to_char(hl.deduction_date, 'dd-mm-yyyy') as deduction_date,
                                (case when hl.state = 'draft' then 'Draft'
                                 when hl.state = 'wait' then 'Waiting For Approval'
                                 when hl.state = 'approved' then 'Approved'
                                 when hl.state = 'done' then 'Done'
                                 when hl.state = 'cancel' then 'Cancelled' else hl.state end) as state,
                                 (case when sum(emil.paid_amt) is not null then sum(emil.paid_amt) else 0.00 end) as paid_amount,
                                 hl.remaining_amt as remaining_amt
                            from hr_loan hl
                                left join res_users ru on (ru.id = hl.user_id)
                                left join res_partner rp on (rp.id = ru.partner_id)
                                left join res_users res on (res.id = hl.approved_id)
                                left join res_partner partner on (partner.id = res.partner_id)
                                left join loan_type lt on (lt.id = hl.loan_type_id)
                                left join hr_loan_emi_line emil on (emil.loan_id = hl.id)
                                left join hr_employee hr on (hr.id = hl.employee_id)
                                left join res_production_unit rpu on (rpu.id = hl.production_unit_id)
                                left join stock_warehouse sw on (sw.id = hl.warehouse_id)
                            where (hl.request_date between %s and %s) """ + loan_type_sql + state_sql + warehouse_sql + employee_sql + unit_sql +""" group by rp.name,
                                    hl.id,
                                    hl.name, 
                                    hr.name_related,
                                    rpu.name,
                                    sw.name,
                                    hl.request_date,
                                    hl.request_amt, 
                                    hl.repay_period,
                                    partner.name,
                                    hl.approved_date,
                                    hl.approved_amt,
                                    hl.approve_repay_period,
                                    lt.name,hl.deduction_date,
                                    hl.state, hl.remaining_amt 
                                    order by hl.name"""
        self.env.cr.execute(hr_loan_sql, (self.date_from, self.date_to,))
        hr_loan_res = self.env.cr.dictfetchall()
        
        if not hr_loan_res:
            raise ValidationError(_('No Record(s) Found'))
        fp = io.BytesIO()
        workbook = xlsxwriter.Workbook(fp)
        header_format = workbook.add_format({
                'bold': 1,
                'align': 'center',
                'valign': 'vcenter',
                'fg_color': 'gray',
                'border': 1})
        table_format = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'border': 1})
        table_format_left = workbook.add_format({
                'align': 'left',
                'valign': 'vcenter',
                'border': 1})
        worksheet = workbook.add_worksheet(report_name)
        worksheet.set_row(0, 20)
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 15)
        worksheet.set_column('F:F', 15)
        worksheet.set_column('G:G', 15)
        worksheet.set_column('H:H', 15)
        worksheet.set_column('I:I', 15)
        worksheet.set_column('J:J', 15)
        worksheet.set_column('K:K', 15)
        worksheet.set_column('L:L', 15)
        worksheet.set_column('M:M', 15)
        worksheet.set_column('N:N', 15)
        worksheet.set_column('O:O', 15)
        worksheet.set_column('P:P', 15)
        worksheet.set_column('Q:Q', 15)
        worksheet.set_column('R:R', 15)
        worksheet.set_column('S:S', 15)
        worksheet.set_column('T:T', 15)
        worksheet.set_column('U:U', 15)
        worksheet.set_column('V:V', 15)
        worksheet.set_column('W:W', 15)
        
        worksheet.write(0, 0, "Loan Report", header_format)
        worksheet.write(1, 0, filters, header_format)
        worksheet.write(3, 0, "Sr. No", header_format)
        worksheet.write(3, 1, "Loan No", header_format)
        worksheet.write(3, 2, "Request Date", header_format)
        worksheet.write(3, 3, "Request Amount", header_format)
        worksheet.write(3, 4, "Repayment Period", header_format)
        worksheet.write(3, 5, "Employee", header_format)
        worksheet.write(3, 6, "Production Unit", header_format)
        worksheet.write(3, 7, "Warehouse", header_format)
        worksheet.write(3, 8, "Creator", header_format)
        worksheet.write(3, 9, "Loan Type", header_format)
        worksheet.write(3, 10, "State", header_format)
        worksheet.write(3, 11, "Approved By", header_format)
        worksheet.write(3, 12, "Approved Date", header_format)
        worksheet.write(3, 13, "Approved Amount", header_format)
        worksheet.write(3, 14, "Approved Repayment Period", header_format)
        worksheet.write(3, 15, "Paid Amount", header_format)
        worksheet.write(3, 16, "Remaining Amount", header_format)
        worksheet.write(3, 17, "Deduction Date", header_format)
        
        row = 4
        counter = 1
        for each in hr_loan_res:
            worksheet.write(row, 0, counter, table_format)
            worksheet.write(row, 1, each['loan_no'], table_format)
            worksheet.write(row, 2, each['request_date'], table_format)
            worksheet.write(row, 3, each['request_amt'], table_format)
            worksheet.write(row, 4, each['repay_period'], table_format)
            worksheet.write(row, 5, each['employee'], table_format)
            worksheet.write(row, 6, each['unit'], table_format)
            worksheet.write(row, 7, each['warehouse'], table_format)
            worksheet.write(row, 8, each['creator'], table_format)
            worksheet.write(row, 9, each['loan_type'], table_format)
            worksheet.write(row, 10, each['state'], table_format)
            worksheet.write(row, 11, each['approved_by'], table_format)
            worksheet.write(row, 12, each['approved_date'], table_format)
            worksheet.write(row, 13, each['approved_amt'], table_format)
            worksheet.write(row, 14, each['approve_repay_period'], table_format)
            worksheet.write(row, 15, each['paid_amount'], table_format)
            worksheet.write(row, 16, each['remaining_amt'], table_format)
            worksheet.write(row, 17, each['deduction_date'], table_format)
            row += 1
            counter += 1
        
        workbook.close()
        
        output = base64.b64encode(fp.getvalue())
        self.write({'output': output, 'name': report_name + '.xlsx'})
        fp.close()
        
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/hr.loan.report.wizard/{}/output/{}/{}'.format(self.id, self.name, self.name),
            'target': 'new',
            'nodestroy': False,
        }

