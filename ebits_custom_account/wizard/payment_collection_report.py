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
from lxml import etree

class PaymentCollectionReportWizard(models.TransientModel):
    _name = 'payment.collection.report.wizard'
    _description = 'Payment Collection Report Wizard'
    
    date_from= fields.Date(string='From Date(Payment Date)', required=True)
    date_to= fields.Date(string='To Date(Payment Date)', required=True)
    journal_ids = fields.Many2many('account.journal', 'etc_payment_collection_journal', 'payment_collec_wizard_id', 'journal_id', string='Payment Journal')
    partner_ids = fields.Many2many('res.partner', 'etc_payment_collection_partner', 'payment_collec_wizard_id', 'partner_id', string='Customer')
    user_ids = fields.Many2many('res.users', 'etc_payment_collection_users', 'payment_collec_wizard_id', 'user_id', string='Sales Person')
    sales_manager_ids = fields.Many2many('res.users', 'etc_payment_collection_manger_users', 'payment_collec_wizard_id', 'manager_id', string='Sales Manager')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_payment_collection_warehouse', 'payment_collec_wizard_id', 'warehouse_id', string='Warehouse')
    currency_ids = fields.Many2many('res.currency', 'etc_payment_collection_currency', 'payment_collec_wizard_id', 'currency_id', string='Payment Currency')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    payment_type = fields.Selection([
            ('sale', 'Sale'),
            ('purchase', 'Purchase'),
            ('cash', 'Cash'),
            ('bank', 'Bank'),
            ('general', 'Miscellaneous'),
        ])
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PaymentCollectionReportWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='warehouse_ids']"):
                warehouse_id = []
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                if warehouse_id:
                    node.set('domain', "[('id', 'in', " + str(warehouse_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res
    
    @api.multi
    def action_report(self):
        payment_obj = self.env['account.payment']
        pos_conf_obj = self.env['pos.config']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Collection Report"
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date)
        journal_sql = """ """
        partner_sql = """ """
        user_sql = """ """
        sales_manager_sql = """ """
        warehouse_sql = """ """
        currency_sql = """ """
        payment_type_sql = """ """
        
        journal_ids = []
        journal_list = []
        journal_str = ""
        
        user_ids = []
        user_list = []
        user_str = ""
        
        sales_manager_ids = []
        sales_manager_list = []
        sales_manager_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        currency_ids = []
        currency_list = []
        currency_str = ""
        
        all_partners_children = {}
        all_partner_ids = []
        customer_list = []
        customer_str = ""
        
        if self.partner_ids:
            for each_id in self.partner_ids:
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id]
                customer_list.append(each_id.name)
            customer_list = list(set(customer_list))
            customer_str = str(customer_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                all_partner_ids = tuple(all_partner_ids)
                partner_sql += " and ap.partner_id in "+ str(all_partner_ids)
            else:
                partner_sql += " and ap.partner_id in ("+ str(all_partner_ids[0]) + ")"
            filters += ", Customer:" + customer_str
        if self.journal_ids:
            for each_id in self.journal_ids:
                journal_ids.append(each_id.id)
                journal_list.append(each_id.name)
            journal_list = list(set(journal_list))
            journal_str = str(journal_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(journal_ids) > 1:
                journal_sql += "and ap.journal_id in "+ str(tuple(journal_ids))
            else:
                journal_sql += "and ap.journal_id in ("+ str(journal_ids[0]) + ")"
            filters += ", Payment Journal: " + journal_str
        if self.user_ids:
            for each_id in self.user_ids:
                user_ids.append(each_id.id)
                user_list.append(each_id.name)
            user_list = list(set(user_list))
            user_str = str(user_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(user_ids) > 1:
                user_sql += "and rp.user_id in "+ str(tuple(user_ids))
            else:
                user_sql += "and rp.user_id in ("+ str(user_ids[0]) + ")"
            filters += ", Sales Man: " + user_str
        if self.sales_manager_ids:
            for each_id in self.sales_manager_ids:
                sales_manager_ids.append(each_id.id)
                sales_manager_list.append(each_id.name)
            sales_manager_list = list(set(sales_manager_list))
            sales_manager_str = str(sales_manager_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(sales_manager_ids) > 1:
                sales_manager_sql += "and rp.sales_manager_id in "+ str(tuple(sales_manager_ids))
            else:
                sales_manager_sql += "and rp.sales_manager_id in ("+ str(sales_manager_ids[0]) + ")"
            filters += ", Sales Manager: " + sales_manager_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and rp.delivery_warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and rp.delivery_warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += "and rp.delivery_warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += "and rp.delivery_warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                filters += ", Warehouse: " + warehouse_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(currency_ids) > 1:
                currency_sql += "and ap.currency_id in "+ str(tuple(currency_ids))
            else:
                currency_sql += "and ap.currency_id in ("+ str(currency_ids[0]) + ")"
            filters += ", Currency: " + currency_str
        if self.payment_type:
            payment_type_sql = " and aj.type = " + "'" + str(self.payment_type) + "'"
            if self.payment_type == 'sale':
                filters += ", Payment Type : Sale"
            if self.payment_type == 'purchase':
                filters += ", Payment Type : Purchase"
            if self.payment_type == 'cash':
                filters += ", Payment Type : Cash"
            if self.payment_type == 'bank':
                filters += ", Payment Type : Bank"
            if self.payment_type == 'general':
                filters += ", Payment Type : Miscellaneous"
        payment_coll_sql = """ select 
	                            ap.id as id,
	                            to_char(ap.payment_date , 'dd-mm-yyyy') as payment_date,
	                            ap.name as name,
	                            aj.name as payment_journal,
	                            ap.journal_id as journal_id, 
	                            rp.display_name as partner,
	                            partner.name as sales_man,
	                            urp.name as sales_manager,
	                            ap.customer_receipt as customer_receipt,
	                            ap.communication as communication,
	                            sw.name as warehouse,
		                        rsa.name as area, 
	                            cur.name as payment_currency,
	                            ap.amount as payment_amount,
	                            ap.amount_local_currency as payment_amount_local,
	                            (case when aj.type = 'sale' then 'Sale'
	                             when aj.type = 'purchase' then 'Purchase'  
	                             when aj.type = 'cash' then 'Cash' 
	                             when aj.type = 'bank' then 'Bank' 
	                             when aj.type = 'general' then 'Miscellaneous' else aj.type end) as payment_type,
	                             hr.name_related as received_by 
                            from account_payment ap 
	                            left join account_journal aj on (aj.id = ap.journal_id)
	                            left join res_partner rp on (rp.id = ap.partner_id)
	                            left join res_users ru on (ru.id = ap.sales_user_id)
	                            left join res_partner partner on (partner.id = ru.partner_id) 
	                            left join res_users users on (users.id = ap.manager_user_id)
	                            left join res_partner urp on (urp.id = users.partner_id)
	                            left join stock_warehouse sw on (sw.id = rp.delivery_warehouse_id)
	                            left join res_state_area rsa on(rsa.id = rp.area_id)
	                            left join res_currency cur on (cur.id = ap.currency_id)
	                            left join hr_employee hr on (hr.id = ap.employee_id)
                            where
	                            (ap.payment_date between %s and %s) 
	                            and ap.partner_type = 'customer' """ + journal_sql + partner_sql + user_sql + sales_manager_sql + warehouse_sql + currency_sql + payment_type_sql + """ group by
	                                ap.payment_date,
	                                aj.name,
	                                rp.display_name,
	                                partner.name,
	                                ap.customer_receipt,
	                                urp.name,
	                                ap.communication,
	                                sw.name,
	                                hr.name_related,
	                                ap.id,
	                                area,
	                                cur.name,
	                                ap.amount,
	                                ap.name,
	                                ap.journal_id,
	                                aj.type
                                order by 
                                    ap.payment_date,
                                    aj.name"""
        self.env.cr.execute(payment_coll_sql ,(date_from, date_to,))
        payment_coll_data = self.env.cr.dictfetchall()
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 5000
        sheet1.col(2).width = 5500
        sheet1.col(3).width = 5000
        sheet1.col(4).width = 4000
        sheet1.col(5).width = 8000
        sheet1.col(6).width = 6000
        sheet1.col(7).width = 6000
        sheet1.col(8).width = 6000
        sheet1.col(9).width = 5000
        sheet1.col(10).width = 4500
        sheet1.col(11).width = 4500
        sheet1.col(12).width = 4500
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 6000
    
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 500
        sheet1.row(r1).height = 400
        sheet1.row(r2).height = 200 * 2
        sheet1.row(r3).height = 200 * 2
        title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
        title1 = self.company_id.name
        title2 = filters 
        sheet1.write_merge(rc, rc, 0, 14, title1, Style.main_title())
        sheet1.write_merge(r1, r1, 0, 14, title, Style.sub_main_title())
        sheet1.write_merge(r2, r2, 0, 14, title2, Style.subTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Payment Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Payment No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Payment Journal", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Customer", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Received by(Sales Person)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Sales Manager", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Area", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Payment Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Payment Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "Amount in Local Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 13, "Customer Receipt No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 14, "Memo", Style.contentTextBold(r2,'black','white'))
        
        row = r3
        s_no = 0
        total_amount = 0.00
        for each in payment_coll_data:
            row += 1
            s_no += 1
            sheet1.row(row).height = 400
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['payment_date'], Style.normal_left())
            sheet1.write(row, 2, each['name'], Style.normal_left())
            sheet1.write(row, 3, each['payment_journal'], Style.normal_left())
            pos_search = pos_conf_obj.search([('journal_ids', 'in', (each['journal_id']))])
            if pos_search:
                 sheet1.write(row, 4, 'POS', Style.normal_left())
            else:
                sheet1.write(row, 4, 'Regular', Style.normal_left())
            sheet1.write(row, 5, each['partner'], Style.normal_left())
            sheet1.write(row, 6, each['sales_man'], Style.normal_left())
            sheet1.write(row, 7, each['sales_manager'], Style.normal_left())
            sheet1.write(row, 8, each['warehouse'], Style.normal_left())
            sheet1.write(row, 9, each['area'], Style.normal_left())
            sheet1.write(row, 10, each['payment_currency'], Style.normal_left())
            sheet1.write(row, 11, each['payment_amount'], Style.normal_num_right_3separator())
            sheet1.write(row, 12, each['payment_amount_local'], Style.normal_num_right_3separator())
            sheet1.write(row, 13, each['customer_receipt'], Style.normal_left())
            sheet1.write(row, 14, each['communication'], Style.normal_left())
            total_amount += each['payment_amount_local']
        row += 1
        sheet1.write_merge(row, row, 0, 11, 'Total', Style.groupByTitle())
        sheet1.write(row, 12, total_amount, Style.groupByTotal3Separator())
        stream = cStringIO.StringIO()
        wbk.save(stream)

        self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'payment.collection.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
