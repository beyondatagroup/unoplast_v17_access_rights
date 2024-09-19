# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_sale.wizard.excel_styles import ExcelStyles

import xlwt
from io import StringIO
import base64
import xlrd
#import parser

class SaleTargetReportWizard(models.TransientModel):
    _name = 'sale.target.report.wizard'
    _description = 'Sale Target Report Wizard'
    
    target_id = fields.Many2one('sales.target', string='Target')
    date_from= fields.Date(string='From Date(Target Start Date)', required=True)
    date_to= fields.Date(string='To Date(Target End Date)', required=True)
    based_product = fields.Selection([('product', 'Product'), ('product_category', 'Product Category'), ('parent_category', 'Parent Category')], string='Based on', required=True)
    based_team = fields.Selection([('sales_team', 'Sales Team'), ('sales_person', 'Sales Person')], string='Based on')
    group_by = fields.Selection([('summary', 'Summary'), ('detailed', 'Detailed')], string='Group By')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name= fields.Char(string='File Name', readonly=True)
    output= fields.Binary(string='format', readonly=True)
    
    
    @api.onchange('based_team')
    def onchange_based_team(self):
        if self.based_team:
            self.group_by = False
            
    @api.onchange('based_product')
    def onchange_based_product(self):
        if self.based_product == 'product':
            self.group_by = False
            
    #@api.multi
    def action_report(self):
        # These functions run based on Parent Category:
        if self.date_from and self.date_to and self.based_product == 'parent_category' and self.group_by == 'summary':
            return self.action_report_parent_category()
        if self.date_from and self.date_to and self.based_product == 'parent_category' and self.group_by == 'detailed':
            return self.action_report_parent_category_detailed()
        if self.date_from and self.date_to and self.based_product == 'parent_category' and self.based_team == 'sales_person':
            return self.action_report_parent_category_salesperson()
        if self.date_from and self.date_to and self.based_product == 'parent_category' and self.based_team == 'sales_team':
            return self.action_report_parent_category_salesteam()
            
        # These functions run based on Product Category:
        if self.date_from and self.date_to and self.based_product == 'product_category' and self.group_by == 'summary':
            return self.action_report_product_category()
        if self.date_from and self.date_to and self.based_product == 'product_category' and self.group_by == 'detailed':
            return self.action_report_product_category_detailed()
        if self.date_from and self.date_to and self.based_product == 'product_category' and self.based_team == 'sales_person':
            return self.action_report_product_category_salesperson()
        if self.date_from and self.date_to and self.based_product == 'product_category' and self.based_team == 'sales_team':
            return self.action_report_product_category_salesteam()
            
        # These functions run based on Product:
        if self.date_from and self.date_to and self.based_product == 'product' and self.based_team == False:
            return self.action_report_product()
        if self.date_from and self.date_to and self.based_product == 'product' and self.based_team == 'sales_person':
            return self.action_report_product_salesperson()
        if self.date_from and self.date_to and self.based_product == 'product' and self.based_team == 'sales_team':
            return self.action_report_product_salesteam()
            
    #@api.multi
    def action_report_parent_category(self):
        parent_category_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        parent_categ_sql = """select	
                    st.name as target_name,
                    st.date_start as date_start,
                    st.date_end as date_end,
                    sw.name as warehouse,
                    stl.id as stl_id,
                    (select string_agg(pc.name, ', ') 
	                    from sales_target_parent_category_relation stpc 
	                    left join product_category pc on (pc.id = stpc.parent_categ_id)
	                    where stpc.target_line_id = stl.id ) as category_name,
                    rc.name as currency,
                    sum(stl.target_qty) as target_qty,
                    sum(stl.target_value) as target_value
                from sales_target_line stl
                    left join sales_target st on (st.id = stl.target_id)
                    left join stock_warehouse sw on (sw.id = st.warehouse_id)
                    left join res_currency rc on (rc.id = stl.currency_id)
                where st.date_start = %s and st.date_end = %s and st.based_product = %s""" + target_sql + """group by st.name,
                        stl.id,
                        st.date_start,
                        st.date_end,
                        sw.name,
                        rc.name
                order by st.name"""
		            
        parent_categ_sql_sub = """select (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                    from account_invoice_line ail
	                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                    left join product_product pp on(pp.id = ail.product_id)
	                    left join product_template pt on(pt.id = pp.product_tmpl_id) 
	                    left join product_category pc on(pc.id = pt.categ_id)
	                    left join product_category p_categ on (p_categ.id = pc.parent_id)
                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                    and ai.state in ('open', 'paid')
	                    and p_categ.id = %s"""
                        
        self.env.cr.execute(parent_categ_sql , (date_from,date_to,self.based_product,))
        parent_categ_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 5500
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 2500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 4500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        title1 = self.company_id.name
        sheet1.write_merge(r1, r1, 0, 11, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 11, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Parent Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Parent Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in parent_categ_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            parent_category_line_bro = parent_category_line_obj.browse(each['stl_id'])
            inv_qty = sub_total = 0.00
            for each_categ_id in parent_category_line_bro.parent_category_ids:
                self.env.cr.execute(parent_categ_sql_sub , (each['date_start'], each['date_end'], each_categ_id.id))
                inv_data = self.env.cr.dictfetchall()
                for each_inv_data in inv_data:
                    sheet1.row(row).height = 350
                    sheet1.write(row, 9, each_categ_id.name, Style.normal_left())
                    sheet1.write(row, 10, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                    sheet1.write(row, 11, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['category_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 6, 6, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 7, 7, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 8, 8, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty
            total_sub_total += sub_total  
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 4, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 5, 5, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 6, 6, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 7, 7, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 8, 8, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 9, 10, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 11, 11, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    #@api.multi
    def action_report_parent_category_detailed(self):
        parent_category_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        parent_categ_sql = """select	
                    st.name as target_name,
                    st.date_start as date_start,
                    st.date_end as date_end,
                    sw.name as warehouse,
                    stl.id as stl_id,
                    (select string_agg(pc.name, ', ') 
	                    from sales_target_parent_category_relation stpc 
	                    left join product_category pc on (pc.id = stpc.parent_categ_id)
	                    where stpc.target_line_id = stl.id ) as category_name,
                    rc.name as currency,
                    sum(stl.target_qty) as target_qty,
                    sum(stl.target_value) as target_value
                from sales_target_line stl
                    left join sales_target st on (st.id = stl.target_id)
                    left join stock_warehouse sw on (sw.id = st.warehouse_id)
                    left join res_currency rc on (rc.id = stl.currency_id)
                where st.date_start = %s and st.date_end = %s and st.based_product = %s """ + target_sql + """group by st.name,
                        stl.id,
                        st.date_start,
                        st.date_end,
                        sw.name,
                        rc.name"""
		            
        parent_categ_sql_sub = """select 
                                    concat('[',pt.default_code,'] ', pt.name) as product,
                                    (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                                (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                    from account_invoice_line ail
	                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                    left join product_product pp on(pp.id = ail.product_id)
	                    left join product_template pt on(pt.id = pp.product_tmpl_id) 
	                    left join product_category pc on(pc.id = pt.categ_id)
	                    left join product_category p_categ on (p_categ.id = pc.parent_id)
                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                    and ai.state in ('open', 'paid')
	                    and p_categ.id = %s
	                group by pt.name,pt.default_code"""
                        
        self.env.cr.execute(parent_categ_sql , (date_from,date_to,self.based_product,))
        parent_categ_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 6000
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 5500
        sheet1.col(4).width = 2500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 7000
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        title1 = self.company_id.name
        sheet1.write_merge(r1, r1, 0, 11, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 11, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Parent Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in parent_categ_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            inv_qty = sub_total = 0.00
            parent_category_line_bro = parent_category_line_obj.browse(each['stl_id'])
            for each_categ_id in parent_category_line_bro.parent_category_ids:
                self.env.cr.execute(parent_categ_sql_sub , (each['date_start'], each['date_end'], each_categ_id.id))
                inv_data = self.env.cr.dictfetchall()
                if not inv_data:
                    row = row + 1     
                for each_inv_data in inv_data:
                    if each_inv_data: 
                        sheet1.row(row).height = 450
                        sheet1.write(row, 9, each_inv_data['product'], Style.normal_left())
                        sheet1.write(row, 10, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                        sheet1.write(row, 11, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                        inv_qty += each_inv_data['inv_qty']
                        sub_total += each_inv_data['price_subtotal']  
                        row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['category_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 6, 6, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 7, 7, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 8, 8, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty
            total_sub_total += sub_total
            row = row + 1
        if self.target_id:    
            sheet1.write_merge(row, row, 0, 4, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 5, 5, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 6, 6, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 7, 7, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 8, 8, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 9, 10, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 11, 11, total_sub_total, Style.groupByTotal3Separator())

        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    #@api.multi
    def action_report_parent_category_salesperson(self):
        parent_category_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        parent_categ_salesperson_sql = """select	
                                            st.name as target_name,
                                            st.date_start as date_start,
                                            st.date_end as date_end,
                                            sw.name as warehouse,
                                            stl.id as stl_id,
                                            ru.id as user_id,
                                            rp.name as sales_person,
                                            (select string_agg(pc.name, ', ') 
	                                            from sales_target_parent_category_relation stpc 
	                                            left join product_category pc on (pc.id = stpc.parent_categ_id)
	                                            where stpc.target_line_id = stl.id ) as category_name,
                                            rc.name as currency,
                                            sum(stl.target_qty) as target_qty,
                                            sum(stl.target_value) as target_value
                                        from sales_target_line stl
                                            left join sales_target st on (st.id = stl.target_id)
                                            left join stock_warehouse sw on (sw.id = st.warehouse_id)
                                            left join res_currency rc on (rc.id = stl.currency_id)
                                            left join res_users ru on (ru.id = stl.user_id)
	                                        left join res_partner rp on (rp.id = ru.partner_id)
                                        where st.date_start = %s and st.date_end = %s and st.based_team = %s and st.based_product = %s """ + target_sql +"""group by st.name,
                                                stl.id,
                                                st.date_start,
                                                st.date_end,
                                                sw.name,
                                                rc.name,
                                                ru.id,
                                                rp.name
                                            order by st.name"""
		            
        parent_categ_sql_sub = """select (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                    from account_invoice_line ail
	                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                    left join product_product pp on(pp.id = ail.product_id)
	                    left join product_template pt on(pt.id = pp.product_tmpl_id) 
	                    left join product_category pc on(pc.id = pt.categ_id)
	                    left join product_category p_categ on (p_categ.id = pc.parent_id)
                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                    and ail.sales_user_id = %s
	                    and ai.state in ('open', 'paid')
	                    and p_categ.id = %s"""
                        
        self.env.cr.execute(parent_categ_salesperson_sql , (date_from,date_to,self.based_team,self.based_product,))
        parent_categ_salesperson_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 6000
        sheet1.col(2).width = 6500
        sheet1.col(3).width = 5500
        sheet1.col(4).width = 4500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 2500
        sheet1.col(10).width = 4500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        title1 = self.company_id.name
        sheet1.write_merge(r1, r1, 0, 12, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 12, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Parent Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Sales Person", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Parent Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in parent_categ_salesperson_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            inv_qty = sub_total = 0.00
            parent_category_line_bro = parent_category_line_obj.browse(each['stl_id'])
            for each_categ_id in parent_category_line_bro.parent_category_ids:
                self.env.cr.execute(parent_categ_sql_sub , (each['date_start'], each['date_end'], each['user_id'], each_categ_id.id))
                inv_data = self.env.cr.dictfetchall()
                for each_inv_data in inv_data:
                    sheet1.write(row, 10, each_categ_id.name, Style.normal_left())
                    sheet1.write(row, 11, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                    sheet1.write(row, 12, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['category_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['sales_person'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 6, 6, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 7, 7, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 8, 8, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 9, 9, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty
            total_sub_total += sub_total 
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 5, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 6, 6, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 7, 7, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 8, 8, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 9, 9, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 10, 11, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 12, 12, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    #@api.multi
    def action_report_parent_category_salesteam(self):
        parent_category_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        parent_categ_salesteam_sql = """select	
                                            st.name as target_name,
                                            st.date_start as date_start,
                                            st.date_end as date_end,
                                            sw.name as warehouse,
                                            stl.id as stl_id,
                                            (select string_agg(pc.name, ', ') 
                                                from sales_target_parent_category_relation stpc 
                                                left join product_category pc on (pc.id = stpc.parent_categ_id)
                                                where stpc.target_line_id = stl.id ) as category_name,
                                            ct.id as team_id,
                                            ct.name as sales_team,
                                            rc.name as currency,
                                            sum(stl.target_qty) as target_qty,
                                            sum(stl.target_value) as target_value
                                        from sales_target_line stl
                                            left join sales_target st on (st.id = stl.target_id)
                                            left join stock_warehouse sw on (sw.id = st.warehouse_id)
                                            left join res_currency rc on (rc.id = stl.currency_id)
                                            left join crm_team ct on (ct.id = stl.team_id)
                                        where st.date_start = %s and st.date_end = %s and st.based_team = %s and st.based_product = %s """ + target_sql +"""group by st.name,
                                            stl.id,
                                            st.date_start,
                                            st.date_end,
                                            sw.name,
                                            rc.name,
                                            ct.id,
                                            ct.name"""
		            
        parent_categ_sql_sub = """select (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                    from account_invoice_line ail
	                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                    left join product_product pp on(pp.id = ail.product_id)
	                    left join product_template pt on(pt.id = pp.product_tmpl_id) 
	                    left join product_category pc on(pc.id = pt.categ_id)
	                    left join product_category p_categ on (p_categ.id = pc.parent_id)
                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                    and ai.team_id = %s
	                    and ai.state in ('open', 'paid')
	                    and p_categ.id = %s"""
                        
        self.env.cr.execute(parent_categ_salesteam_sql , (date_from,date_to,self.based_team,self.based_product,))
        parent_categ_salesteam_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 7000
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 5500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 2500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title1 = self.company_id.name
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        sheet1.write_merge(r1, r1, 0, 12, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 12, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Parent Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Sales Team", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Parent Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in parent_categ_salesteam_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            inv_qty = sub_total = 0.00
            parent_category_line_bro = parent_category_line_obj.browse(each['stl_id'])
            for each_categ_id in parent_category_line_bro.parent_category_ids:
                self.env.cr.execute(parent_categ_sql_sub , (each['date_start'], each['date_end'], each['team_id'], each_categ_id.id))
                inv_data = self.env.cr.dictfetchall()
                for each_inv_data in inv_data:
                    sheet1.write(row, 10, each_categ_id.name, Style.normal_left())
                    sheet1.write(row, 11, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                    sheet1.write(row, 12, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['category_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['sales_team'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 6, 6, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 7, 7, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 8, 8, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 9, 9, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty
            total_sub_total += sub_total
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 5, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 6, 6, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 7, 7, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 8, 8, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 9, 9, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 10, 11, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 12, 12, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    #@api.multi
    def action_report_product_category(self):
        product_category_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        product_categ_sql = """select	
                    st.name as target_name,
                    st.date_start as date_start,
                    st.date_end as date_end,
                    sw.name as warehouse,
                    stl.id as stl_id,
                    (select string_agg(pc.name, ', ') 
	                    from sales_target_category_relation stc 
	                    left join product_category pc on (pc.id = stc.category_id)
	                    where stc.target_line_id = stl.id ) as category_name,
                    rc.name as currency,
                    sum(stl.target_qty) as target_qty,
                    sum(stl.target_value) as target_value
                from sales_target_line stl
                    left join sales_target st on (st.id = stl.target_id)
                    left join stock_warehouse sw on (sw.id = st.warehouse_id)
                    left join res_currency rc on (rc.id = stl.currency_id)
                where st.date_start = %s and st.date_end = %s and st.based_product = %s """ + target_sql +"""group by st.name,
                        stl.id,
                        st.date_start,
                        st.date_end,
                        sw.name,
                        rc.name
                    order by st.name"""
		            
        product_categ_sql_sub = """select (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                    from account_invoice_line ail
	                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                    left join product_product pp on(pp.id = ail.product_id)
	                    left join product_template pt on(pt.id = pp.product_tmpl_id) 
	                    left join product_category pc on(pc.id = pt.categ_id)
                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                    and ai.state in ('open', 'paid')
	                    and pc.id = %s"""
                        
        self.env.cr.execute(product_categ_sql , (date_from,date_to,self.based_product,))
        product_categ_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 7000
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 2500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title1 = self.company_id.name
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        sheet1.write_merge(r1, r1, 0, 11, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 11, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in product_categ_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            inv_qty = sub_total = 0.00
            product_category_line_bro = product_category_line_obj.browse(each['stl_id'])
            for each_categ_id in product_category_line_bro.product_category_ids:
                self.env.cr.execute(product_categ_sql_sub , (each['date_start'], each['date_end'], each_categ_id.id))
                inv_data = self.env.cr.dictfetchall()
                if not inv_data:
                    row = row + 1 
                for each_inv_data in inv_data:
                    sheet1.write(row, 9, each_categ_id.name, Style.normal_left())
                    sheet1.write(row, 10, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                    sheet1.write(row, 11, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['category_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 6, 6, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 7, 7, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 8, 8, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty
            total_sub_total += sub_total 
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 4, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 5, 5, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 6, 6, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 7, 7, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 8, 8, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 9, 10, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 11, 11, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    #@api.multi
    def action_report_product_category_detailed(self):
        product_category_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        product_categ_detailed_sql = """select	
                                            st.name as target_name,
                                            st.date_start as date_start,
                                            st.date_end as date_end,
                                            sw.name as warehouse,
                                            stl.id as stl_id,
                                            (select string_agg(pc.name, ', ') 
	                                            from sales_target_category_relation stc 
	                                            left join product_category pc on (pc.id = stc.category_id)
	                                            where stc.target_line_id = stl.id ) as category_name,
                                            rc.name as currency,
                                            sum(stl.target_qty) as target_qty,
                                            sum(stl.target_value) as target_value
                                        from sales_target_line stl
                                            left join sales_target st on (st.id = stl.target_id)
                                            left join stock_warehouse sw on (sw.id = st.warehouse_id)
                                            left join res_currency rc on (rc.id = stl.currency_id)
                                        where st.date_start = %s and st.date_end = %s and st.based_product = %s """ + target_sql +"""group by st.name,
                                                stl.id,
                                                st.date_start,
                                                st.date_end,
                                                sw.name,
                                                rc.name
                                        order by st.name"""
		            
        product_categ_sql_sub = """select 
                                        concat('[',pt.default_code,'] ', pt.name) as product,
                                        (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                                    from account_invoice_line ail
	                                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                                    left join product_product pp on(pp.id = ail.product_id)
	                                    left join product_template pt on(pt.id = pp.product_tmpl_id) 
	                                    left join product_category pc on(pc.id = pt.categ_id)
                                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                                    and ai.state in ('open', 'paid')
	                                    and pc.id = %s
	                                group by pt.name,pt.default_code"""
                        
        self.env.cr.execute(product_categ_detailed_sql , (date_from,date_to,self.based_product,))
        product_categ_detailed_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 7000
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 2500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 7000
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title1 = self.company_id.name
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        sheet1.write_merge(r1, r1, 0, 11, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 11, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in product_categ_detailed_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            inv_qty = sub_total = 0.00
            product_category_line_bro = product_category_line_obj.browse(each['stl_id'])
            for each_categ_id in product_category_line_bro.product_category_ids:
                self.env.cr.execute(product_categ_sql_sub , (each['date_start'], each['date_end'], each_categ_id.id))
                inv_data = self.env.cr.dictfetchall()
                if not inv_data:
                    row = row + 1 
                for each_inv_data in inv_data:
                    sheet1.write(row, 9, each_inv_data['product'], Style.normal_left())
                    sheet1.write(row, 10, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                    sheet1.write(row, 11, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['category_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 6, 6, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 7, 7, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 8, 8, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty 
            total_sub_total += sub_total 
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 4, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 5, 5, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 6, 6, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 7, 7, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 8, 8, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 9, 10, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 11, 11, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    #@api.multi
    def action_report_product_category_salesperson(self):
        product_category_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        product_categ_salesperson_sql = """select	
                                            st.name as target_name,
                                            st.date_start as date_start,
                                            st.date_end as date_end,
                                            sw.name as warehouse,
                                            stl.id as stl_id,
                                            ru.id as user_id,
                                            rp.name as sales_person,
                                            (select string_agg(pc.name, ', ') 
	                                            from sales_target_category_relation stc 
	                                            left join product_category pc on (pc.id = stc.category_id)
	                                            where stc.target_line_id = stl.id ) as category_name,
                                            rc.name as currency,
                                            sum(stl.target_qty) as target_qty,
                                            sum(stl.target_value) as target_value
                                        from sales_target_line stl
                                            left join sales_target st on (st.id = stl.target_id)
                                            left join stock_warehouse sw on (sw.id = st.warehouse_id)
                                            left join res_currency rc on (rc.id = stl.currency_id)
                                            left join res_users ru on (ru.id = stl.user_id)
                                            left join res_partner rp on (rp.id = ru.partner_id)
                                        where st.date_start = %s and st.date_end = %s and st.based_product = %s and st.based_team = %s """ + target_sql +"""group by st.name,
                                                stl.id,
                                                st.date_start,
                                                st.date_end,
                                                sw.name,
                                                rc.name,
                                                ru.id,
	                                            rp.name
	                                   order by st.name"""
		            
        product_categ_sql_sub = """select 
                                        (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                                    from account_invoice_line ail
	                                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                                    left join product_product pp on(pp.id = ail.product_id)
	                                    left join product_template pt on(pt.id = pp.product_tmpl_id) 
	                                    left join product_category pc on(pc.id = pt.categ_id)
                                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                                    and ail.sales_user_id = %s
	                                    and ai.state in ('open', 'paid')
	                                    and pc.id = %s"""
                        
        self.env.cr.execute(product_categ_salesperson_sql , (date_from,date_to,self.based_product,self.based_team,))
        product_categ_salesperson_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 7000
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 5500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 2500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title1 = self.company_id.name
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        sheet1.write_merge(r1, r1, 0, 12, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 12, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Sales Person", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in product_categ_salesperson_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            inv_qty = sub_total = 0.00
            product_category_line_bro = product_category_line_obj.browse(each['stl_id'])
            for each_categ_id in product_category_line_bro.product_category_ids:
                self.env.cr.execute(product_categ_sql_sub , (each['date_start'], each['date_end'], each['user_id'], each_categ_id.id))
                inv_data = self.env.cr.dictfetchall()
                if not inv_data:
                    row = row + 1 
                for each_inv_data in inv_data:
                    sheet1.write(row, 10, each_categ_id.name, Style.normal_left())
                    sheet1.write(row, 11, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                    sheet1.write(row, 12, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['category_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['sales_person'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 6, 6, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 7, 7, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 8, 8, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 9, 9, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty 
            total_sub_total += sub_total 
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 5, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 6, 6, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 7, 7, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 8, 8, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 9, 9, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 10, 11, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 12, 12, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    #@api.multi
    def action_report_product_category_salesteam(self):
        product_category_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        product_categ_salesteam_sql = """select	
                                            st.name as target_name,
                                            st.date_start as date_start,
                                            st.date_end as date_end,
                                            sw.name as warehouse,
                                            stl.id as stl_id,
                                            ct.id as team_id,
                                            ct.name as sales_team,
                                            (select string_agg(pc.name, ', ') 
	                                            from sales_target_category_relation stc 
	                                            left join product_category pc on (pc.id = stc.category_id)
	                                            where stc.target_line_id = stl.id ) as category_name,
                                            rc.name as currency,
                                            sum(stl.target_qty) as target_qty,
                                            sum(stl.target_value) as target_value
                                        from sales_target_line stl
                                            left join sales_target st on (st.id = stl.target_id)
                                            left join stock_warehouse sw on (sw.id = st.warehouse_id)
                                            left join res_currency rc on (rc.id = stl.currency_id)
                                            left join crm_team ct on (ct.id = stl.team_id)
                                        where st.date_start = %s and st.date_end = %s and st.based_product = %s and st.based_team = %s """ + target_sql +"""group by st.name,
                                                stl.id,
                                                st.date_start,
                                                st.date_end,
                                                sw.name,
                                                rc.name,
                                                ct.id,
                                                ct.name
                                        order by st.name"""
		            
        product_categ_sql_sub = """select 
                                        (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                                    from account_invoice_line ail
	                                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                                    left join product_product pp on(pp.id = ail.product_id)
	                                    left join product_template pt on(pt.id = pp.product_tmpl_id) 
	                                    left join product_category pc on(pc.id = pt.categ_id)
                                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                                    and ai.team_id = %s
	                                    and ai.state in ('open', 'paid')
	                                    and pc.id = %s"""
                        
        self.env.cr.execute(product_categ_salesteam_sql , (date_from,date_to,self.based_product,self.based_team,))
        product_categ_salesteam_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 7000
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 5500
        sheet1.col(4).width = 5500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 2500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        title1 = self.company_id.name
        sheet1.write_merge(r1, r1, 0, 12, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 12, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Sales Team", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in product_categ_salesteam_data:
            s_no = s_no + 1
            sheet1.row(row).height = 450
            start_row = row
            inv_qty = sub_total = 0.00
            product_category_line_bro = product_category_line_obj.browse(each['stl_id'])
            for each_categ_id in product_category_line_bro.product_category_ids:
                self.env.cr.execute(product_categ_sql_sub , (each['date_start'], each['date_end'], each['team_id'], each_categ_id.id))
                inv_data = self.env.cr.dictfetchall()
                if not inv_data:
                    row = row + 1 
                for each_inv_data in inv_data:
                    sheet1.write(row, 10, each_categ_id.name, Style.normal_left())
                    sheet1.write(row, 11, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                    sheet1.write(row, 12, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['category_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['sales_team'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 6, 6, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 7, 7, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 8, 8, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 9, 9, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty
            total_sub_total += sub_total  
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 5, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 6, 6, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 7, 7, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 8, 8, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 9, 9, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 10, 11, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 12, 12, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
                
    #@api.multi
    def action_report_product(self):
        product_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        product_sql = """select	
                    st.name as target_name,
                    st.date_start as date_start,
                    st.date_end as date_end,
                    sw.name as warehouse,
                    stl.id as stl_id,
                    (select string_agg('[' || '' ||pt.default_code || '' || '] ' || '' ||pt.name, ', ') 
	                    from sales_target_product_relation stp 
	                    left join product_product pp on (pp.id = stp.product_id)
	                    left join product_template pt on (pt.id = pp.product_tmpl_id)
	                    where stp.target_line_id = stl.id) as product_name,
                    rc.name as currency,
                    sum(stl.target_qty) as target_qty,
                    sum(stl.target_value) as target_value
                from sales_target_line stl
                    left join sales_target st on (st.id = stl.target_id)
                    left join stock_warehouse sw on (sw.id = st.warehouse_id)
                    left join res_currency rc on (rc.id = stl.currency_id)
                where st.date_start = %s and st.date_end = %s and st.based_product = %s """ + target_sql +"""group by st.name,
                        stl.id,
                        st.date_start,
                        st.date_end,
                        sw.name,
                        rc.name
                order by st.name"""
		            
        product_sql_sub = """select (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                    from account_invoice_line ail
	                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                    left join product_product pp on(pp.id = ail.product_id)
                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                    and ai.state in ('open', 'paid')
	                    and pp.id = %s"""
                        
        self.env.cr.execute(product_sql , (date_from,date_to,self.based_product,))
        product_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 6500
        sheet1.col(2).width = 9500
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 2500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 8500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        title1 = self.company_id.name
        sheet1.write_merge(r1, r1, 0, 11, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 11, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in product_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            inv_qty = sub_total = 0.00
            product_line_bro = product_line_obj.browse(each['stl_id'])
            for each_id in product_line_bro.product_ids:
                self.env.cr.execute(product_sql_sub , (each['date_start'], each['date_end'], each_id.id))
                inv_data = self.env.cr.dictfetchall()
                if not inv_data:
                    row = row + 1 
                for each_inv_data in inv_data:
                    product = '[' + each_id.default_code + '] ' + each_id.name
                    sheet1.write(row, 9, product, Style.normal_left())
                    sheet1.write(row, 10, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                    sheet1.write(row, 11, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['product_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 6, 6, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 7, 7, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 8, 8, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty
            total_sub_total += sub_total 
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 4, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 5, 5, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 6, 6, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 7, 7, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 8, 8, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 9, 10, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 11, 11, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    #@api.multi
    def action_report_product_salesperson(self):
        product_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        product_salesperson_sql = """select	
                    st.name as target_name,
                    st.date_start as date_start,
                    st.date_end as date_end,
                    sw.name as warehouse,
                    stl.id as stl_id,
                    ru.id as user_id,
                    rp.name as sales_person,
                    (select string_agg('[' || '' ||pt.default_code || '' || '] ' || '' ||pt.name, ', ') 
	                    from sales_target_product_relation stp 
	                    left join product_product pp on (pp.id = stp.product_id)
	                    left join product_template pt on (pt.id = pp.product_tmpl_id)
	                    where stp.target_line_id = stl.id) as product_name,
                    rc.name as currency,
                    sum(stl.target_qty) as target_qty,
                    sum(stl.target_value) as target_value
                from sales_target_line stl
                    left join sales_target st on (st.id = stl.target_id)
                    left join stock_warehouse sw on (sw.id = st.warehouse_id)
                    left join res_currency rc on (rc.id = stl.currency_id)
                    left join res_users ru on (ru.id = stl.user_id)
                    left join res_partner rp on (rp.id = ru.partner_id)
                where st.date_start = %s and st.date_end = %s and st.based_product = %s and st.based_team = %s """ + target_sql +"""group by st.name,
                        stl.id,
                        st.date_start,
                        st.date_end,
                        sw.name,
                        rc.name,
                        ru.id,
                        rp.name
                order by st.name"""
		            
        product_sql_sub = """select (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                    from account_invoice_line ail
	                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                    left join product_product pp on(pp.id = ail.product_id)
                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                    and ail.sales_user_id = %s
	                    and ai.state in ('open', 'paid')
	                    and pp.id = %s"""
                        
        self.env.cr.execute(product_salesperson_sql , (date_from,date_to,self.based_product,self.based_team,))
        product_salesperson_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 6500
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 4500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 2500
        sheet1.col(10).width = 6500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        title1 = self.company_id.name
        sheet1.write_merge(r1, r1, 0, 12, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 12, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Sales Person", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in product_salesperson_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            inv_qty = sub_total = 0.00
            product_line_bro = product_line_obj.browse(each['stl_id'])
            for each_id in product_line_bro.product_ids:
                self.env.cr.execute(product_sql_sub , (each['date_start'], each['date_end'], each['user_id'], each_id.id))
                inv_data = self.env.cr.dictfetchall()
                if not inv_data:
                    row = row + 1 
                for each_inv_data in inv_data:
                    product = '[' + each_id.default_code + '] ' + each_id.name
                    sheet1.write(row, 10, product, Style.normal_left())
                    sheet1.write(row, 11, each_inv_data['inv_qty'], Style.normal_num_right_3digits())
                    sheet1.write(row, 12, each_inv_data['price_subtotal'], Style.normal_num_right_3separator())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['product_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['sales_person'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 6, 6, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 7, 7, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 8, 8, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 9, 9, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty
            total_sub_total += sub_total  
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 5, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 6, 6, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 7, 7, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 8, 8, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 9, 9, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 10, 11, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 12, 12, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    #@api.multi
    def action_report_product_salesteam(self):
        product_line_obj = self.env['sales.target.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sale Target"
        target_sql = """ """
        if self.target_id:
            target_sql += " and stl.target_id  = " + str(self.target_id.id)
        product_salesteam_sql = """select	
                                    st.name as target_name,
                                    st.date_start as date_start,
                                    st.date_end as date_end,
                                    sw.name as warehouse,
                                    stl.id as stl_id,
                                    ct.id as team_id,
                                    ct.name as sales_team,
                                    (select string_agg('[' || '' ||pt.default_code || '' || '] ' || '' ||pt.name, ', ') 
	                                    from sales_target_product_relation stp 
	                                    left join product_product pp on (pp.id = stp.product_id)
	                                    left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                    where stp.target_line_id = stl.id) as product_name,
                                    rc.name as currency,
                                    sum(stl.target_qty) as target_qty,
                                    sum(stl.target_value) as target_value
                                from sales_target_line stl
                                    left join sales_target st on (st.id = stl.target_id)
                                    left join stock_warehouse sw on (sw.id = st.warehouse_id)
                                    left join res_currency rc on (rc.id = stl.currency_id)
                                    left join crm_team ct on (ct.id = stl.team_id)
                                where st.date_start = %s and st.date_end = %s and st.based_product = %s and st.based_team = %s """ + target_sql +"""group by st.name,
                                        stl.id,
                                        st.date_start,
                                        st.date_end,
                                        sw.name,
                                        rc.name,
                                        ct.id,
                                        ct.name
                                order by st.name"""
		            
        product_sql_sub = """select (case when sum(ail.quantity) is not null then sum(ail.quantity) else 0.00 end ) as inv_qty,
	                    (case when sum(ail.price_subtotal) is not null then sum(ail.price_subtotal) else 0.00 end) as price_subtotal	
                    from account_invoice_line ail
	                    left join account_invoice ai on (ai.id = ail.invoice_id)
	                    left join product_product pp on(pp.id = ail.product_id)
                    where ai.date_invoice >= %s and ai.date_invoice <= %s 	
	                    and ai.team_id = %s
	                    and ai.state in ('open', 'paid')
	                    and pp.id = %s"""
                        
        self.env.cr.execute(product_salesteam_sql , (date_from,date_to,self.based_product,self.based_team,))
        product_salesteam_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 6500
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 6500
        sheet1.col(4).width = 4500
        sheet1.col(5).width = 2500
        sheet1.col(6).width = 2500
        sheet1.col(7).width = 2500
        sheet1.col(8).width = 2500
        sheet1.col(9).width = 2500
        sheet1.col(10).width = 6500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        
        r1 = 0
        r2 = 1
        r3 = 2
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(date_from,"%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y',date_from)
        date_to = time.strptime(date_to,"%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y',date_to)
        title1 = self.company_id.name
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to +  ' )'
        sheet1.write_merge(r1, r1, 0, 12, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 12, title, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Target Name", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Sales Team", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Target Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Target Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Actual Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Actual Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Actual Sale Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "Actual Value Untaxed", Style.contentTextBold(r2,'black','white'))
        row = 3
        s_no = 0
        total_inv_qty = total_sub_total = target_qty = target_value = 0.00
        for each in product_salesteam_data:
            s_no = s_no + 1
            sheet1.row(row).height = 350
            start_row = row
            inv_qty = sub_total = 0.00
            product_line_bro = product_line_obj.browse(each['stl_id'])
            for each_id in product_line_bro.product_ids:
                self.env.cr.execute(product_sql_sub , (each['date_start'], each['date_end'], each['team_id'], each_id.id))
                inv_data = self.env.cr.dictfetchall()
                if not inv_data:
                    row = row + 1 
                for each_inv_data in inv_data:
                    product = '[' + each_id.default_code + '] ' + each_id.name
                    sheet1.write(row, 10, product, Style.normal_left())
                    sheet1.write(row, 11, each_inv_data['inv_qty'], Style.normal_right())
                    sheet1.write(row, 12, each_inv_data['price_subtotal'], Style.normal_right())
                    inv_qty += each_inv_data['inv_qty']
                    sub_total += each_inv_data['price_subtotal']
                    row = row + 1
            row = row - 1 
            sheet1.write_merge(start_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(start_row, row, 1, 1, each['target_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 2, 2, each['product_name'], Style.normal_left())
            sheet1.write_merge(start_row, row, 3, 3, each['warehouse'], Style.normal_left())
            sheet1.write_merge(start_row, row, 4, 4, each['sales_team'], Style.normal_left())
            sheet1.write_merge(start_row, row, 5, 5, each['currency'], Style.normal_left())
            sheet1.write_merge(start_row, row, 6, 6, each['target_qty'], Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 7, 7, each['target_value'], Style.normal_num_right_3separator())
            sheet1.write_merge(start_row, row, 8, 8, inv_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(start_row, row, 9, 9, sub_total, Style.normal_num_right_3separator())
            target_qty += each['target_qty']
            target_value += each['target_value']
            total_inv_qty += inv_qty
            total_sub_total += sub_total  
            row = row + 1
        if self.target_id:
            sheet1.write_merge(row, row, 0, 5, "Total", Style.groupByTitle())
            sheet1.write_merge(row, row, 6, 6, target_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 7, 7, target_value, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 8, 8, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 9, 9, total_sub_total, Style.groupByTotal3Separator())
            sheet1.write_merge(row, row, 10, 11, total_inv_qty, Style.groupByTotal3Digits())
            sheet1.write_merge(row, row, 12, 12, total_sub_total, Style.groupByTotal3Separator())
        stream = StringIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.target.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
