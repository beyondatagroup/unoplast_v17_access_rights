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
from odoo.exceptions import UserError, AccessError, ValidationError
from lxml import etree

class InvoiceOutstandingReportWizard(models.TransientModel):
    _name = 'invoice.outstanding.report.wizard'
    _description = 'Customer Outstanding Report Wizard'
    
    due_date= fields.Date(string='Due Date')
    invoice_date= fields.Date(string='Invoice Date')
    partner_ids = fields.Many2many('res.partner', 'etc_cust_inv_out_partner', 'cust_out_wizard_id', 'partner_id', string='Customer')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_cust_inv_out_warehouse', 'cust_out_wizard_id', 'warehouse_id', string='Warehouse')
    user_ids = fields.Many2many('res.users', 'etc_cust_inv_out_users', 'cust_out_wizard_id', 'user_id', string = 'Sales Manager')
    currency_ids = fields.Many2many('res.currency', 'etc_cust_inv_out_currency', 'cust_out_wizard_id', 'currency_id', string='Currency')
    team_ids = fields.Many2many('crm.team', 'etc_cust_inv_out_team', 'cust_out_wizard_id', 'team_id', string='Sales Team')
    inv_date_type = fields.Selection([('invoice_date', 'Invoice Date'), ('due_date', 'Due Date')], required=True, string='Filter Based on')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(InvoiceOutstandingReportWizard, self).fields_view_get(
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
        
    @api.model
    def default_get(self, fields):
        if len(self.env.context.get('active_ids', list())) > 1:
            raise UserError("You may print one at a time!")
        res = super(InvoiceOutstandingReportWizard, self).default_get(fields)
        if self.env.context.get('active_id'):
            partner_obj = self.env['res.partner']
            partner = partner_obj.sudo().browse(self.env.context.get('active_id'))
            if partner:
                if not partner.customer:
                    raise UserError("Selected partner is not a customer")
                res.update({'partner_ids': [(6, 0, [p.id for p in partner])]})
                if partner.delivery_warehouse_id:
                    res.update({'warehouse_ids': [(6, 0, [p.delivery_warehouse_id.id for p in partner])]})
        return res
    
    @api.onchange('inv_date_type')
    def _onchange_inv_date_type(self):
        if self.inv_date_type == 'invoice_date':
            self.due_date = False
        else:
            self.invoice_date = False
    
    @api.multi
    def action_report(self):
        invoice_obj = self.env['account.invoice']
        domain_default = []
        invoice_date = self.invoice_date
        due_date = self.due_date
        report_name = "Customer Invoice Outstanding"
        filters = "Filter Based on " 
        partner_sql = """ """
        warehouse_sql = """ """
        sales_manager_sql = """ """
        currency_sql = """ """
        sales_team_sql = """ """
        due_date_sql = """ """
        invoice_date_sql = """ """
        
        all_partners_children = {}
        all_partner_ids = []
        partner_ids = []
        customer_list = []
        customer_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        user_ids = []
        manager_list = []
        manager_str = ""
        
        currency_ids = []
        currency_list = []
        currency_str = ""
        
        team_ids = []
        team_list = []
        team_str = ""
        
        if self.invoice_date:
            invoice_date_sql += "and ai.date_invoice <= " + "'" + str(self.invoice_date) + "'" 
            inv_date = time.strptime(self.invoice_date, "%Y-%m-%d")
            inv_date = time.strftime('%d-%m-%Y', inv_date)
            filters += " Invoice Date : "+ str(inv_date)
        if self.due_date:
            due_date_sql += "and ai.date_due <= " + "'" + str(self.due_date) + "'" 
            date_due = time.strptime(self.due_date, "%Y-%m-%d")
            date_due = time.strftime('%d-%m-%Y', date_due)
            filters += " Due Date : "+ str(date_due)
        if self.partner_ids:
            for each_id in self.partner_ids:
                partner_ids.append(each_id.id)
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id]
                customer_list.append(each_id.name)
            customer_list = list(set(customer_list))
            customer_str = str(customer_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                all_partner_ids = tuple(all_partner_ids)
                partner_sql += " and ai.partner_id in "+ str(all_partner_ids)
            else:
                partner_sql += " and ai.partner_id in ("+ str(all_partner_ids[0]) + ")"
            filters += ", Customer: " + customer_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and ai.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and ai.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += "and ai.warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += "and ai.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                filters += ", Warehouse: " + warehouse_str
        if self.user_ids:
            for each_id in self.user_ids:
                user_ids.append(each_id.id)
                manager_list.append(each_id.partner_id.name)
            manager_list = list(set(manager_list))
            manager_str = str(manager_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(user_ids) > 1:
                sales_manager_sql += "and ai.sales_manager_id in " + str(tuple(user_ids))
            else:
                sales_manager_sql += "and ai.sales_manager_id in (" + str(user_ids[0]) + ")" 
            filters += ", Sales Manager: " + manager_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(currency_ids) > 1:
                currency_sql += "and ai.currency_id in "+ str(tuple(currency_ids))
            else:
                currency_sql += "and ai.currency_id in ("+ str(currency_ids[0]) + ")"
            filters += ", Currency: " + currency_str
        if self.team_ids:
            for each_id in self.team_ids:
                team_ids.append(each_id.id)
                team_list.append(each_id.name)
            team_list = list(set(team_list))
            team_str = str(team_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(team_ids) > 1:
                sales_team_sql += "and ai.team_id in "+ str(tuple(team_ids))
            else:
                sales_team_sql += "and ai.team_id in ("+ str(team_ids[0]) + ")"
            filters += ", Sales Team : " + team_str
        
        customer_sql = """select ai.partner_id as partner_id
                                from account_invoice ai
                                left join res_partner rp on (rp.id = ai.partner_id)
                                where ai.state = 'open' 
                                and  ai.type = 'out_invoice'""" + partner_sql + warehouse_sql + sales_manager_sql + currency_sql + sales_team_sql + invoice_date_sql + due_date_sql + """
                                group by ai.partner_id order by ai.partner_id asc"""         
        
        self.env.cr.execute(customer_sql)
        customer_data = self.env.cr.dictfetchall()
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
#        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 7500
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 4500
        sheet1.col(4).width = 4500
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 4500
        sheet1.col(7).width = 15000
        sheet1.col(8).width = 4000
        sheet1.col(9).width = 4000
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 4000
        sheet1.col(12).width = 4500
        sheet1.col(13).width = 3000
        sheet1.col(14).width = 3000
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500
        sheet1.col(18).width = 3500
        sheet1.col(19).width = 3500
        sheet1.col(20).width = 5000
        sheet1.col(21).width = 4200
        sheet1.col(22).width = 4200
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 256 * 3
        if self.invoice_date:
            inv_date = time.strptime(self.invoice_date, "%Y-%m-%d")
            inv_date = time.strftime('%d-%m-%Y', inv_date)
            title = report_name +' ( As on Invoice Date : ' + inv_date + ' )'
        else:
            date_due = time.strptime(self.due_date, "%Y-%m-%d")
            date_due = time.strftime('%d-%m-%Y', date_due)
            title = report_name +' ( As on Due Date : ' + date_due + ' )'
        title1 = self.company_id.name
        title2 = filters 
        title3 = 'Transaction Currency'
        title4 = 'Local Currency' + ' ( ' + str(self.company_id.currency_id.name) + ' )'
        sheet1.write_merge(r1, r1, 0, 22, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 22, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 10, title2, Style.subTitle())
        sheet1.write_merge(r3, r3, 11, 15, title3, Style.subTitle())
        sheet1.write_merge(r3, r3, 16, 19, title4, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Customer", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "Region", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Area", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Sales Manager", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Invoice No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Delivery Address", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Invoice Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Due Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Due Days", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 11, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 12, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 13, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 14, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 15, "Due Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 16, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 17, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 18, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 19, "Due Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 20, "Sales Team", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 21, "Source Document", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 22, "Customer Order Reference", Style.contentTextBold(r2,'black','white'))
        
        row = r4
        s_no = 0
        local_amt = local_tax = local_total = local_due = 0.00
        amt_local = tax_local = total_local = due_local = 0.00
        for each in customer_data:
            domain_default = [('state', '=', 'open'), ('type', '=', 'out_invoice'), ('partner_id', '=', each['partner_id'])] 
            invoice_records = invoice_obj.sudo().search(domain_default, order="number, date_invoice, date_due") 
            local_amt = local_tax = local_total = local_due = 0.00
            for line in invoice_records:
                row = row + 1
                s_no = s_no + 1
                sheet1.row(row).height = 400
                address = ((line.partner_shipping_id and line.partner_shipping_id.street or "") 
                                + ' ' + (line.partner_shipping_id.city or "") 
                                + ' ' + (line.partner_shipping_id.area_id and line.partner_shipping_id.area_id.name or "") 
                                + ' ' + (line.partner_shipping_id.region_id and line.partner_shipping_id.region_id.name or "") 
                                + ' ' + (line.partner_shipping_id.country_id and line.partner_shipping_id.country_id.name or ""))
                sheet1.write(row, 0, s_no, Style.normal_left())
                sheet1.write(row, 1, line.partner_id.name_get()[0][1], Style.normal_left())
                sheet1.write(row, 2, (line.warehouse_id and line.warehouse_id.name or ""), Style.normal_left())
                sheet1.write(row, 3, (line.partner_id.region_id and line.partner_id.region_id.name or ""), Style.normal_left())
                sheet1.write(row, 4, (line.partner_id.area_id and line.partner_id.area_id.name or ""), Style.normal_left())
                sheet1.write(row, 5, (line.sales_manager_id and line.sales_manager_id.name or ""), Style.normal_left())
                sheet1.write(row, 6, line.number, Style.normal_left())
                sheet1.write(row, 7, address, Style.normal_left())
                date_invoice = ""
                if line.date_invoice:
                    date_invoice = time.strptime(line.date_invoice, "%Y-%m-%d")
                    date_invoice = time.strftime('%d-%m-%Y', date_invoice)
                sheet1.write(row, 8, date_invoice, Style.normal_left())
                date_due = ""
                if line.date_due:
                    date_due = time.strptime(line.date_due, "%Y-%m-%d")
                    date_due = time.strftime('%d-%m-%Y', date_due)
                sheet1.write(row, 9, date_due, Style.normal_left())
                due_diff_days = 0
                current_date = datetime.now()
                if line.date_due and current_date:
                    due_date = time.strftime(line.date_due)
                    due_date = datetime.strptime(due_date, '%Y-%m-%d')
                    if current_date > due_date:
                        due_diff_days = (current_date - due_date).days
                sheet1.write(row, 10, due_diff_days, Style.normal_left())
                sheet1.write(row, 11, line.currency_id.name, Style.normal_left())
                sheet1.write(row, 12, line.amount_untaxed, Style.normal_num_right_3separator())
                sheet1.write(row, 13, line.amount_tax, Style.normal_num_right_3separator())
                sheet1.write(row, 14, line.amount_total, Style.normal_num_right_3separator())
                sheet1.write(row, 15, line.residual, Style.normal_num_right_3separator())
                sheet1.write(row, 16, abs(line.amount_untaxed_signed), Style.normal_num_right_3separator())
                sheet1.write(row, 17, abs(line.amount_tax_company_currency), Style.normal_num_right_3separator())
                sheet1.write(row, 18, abs(line.amount_total_company_signed), Style.normal_num_right_3separator())
                sheet1.write(row, 19, abs(line.residual_company_signed), Style.normal_num_right_3separator())
                sheet1.write(row, 20, (line.team_id and line.team_id.name or ""), Style.normal_left())
                sheet1.write(row, 21, (line.origin and line.origin or ""), Style.normal_left())
                sheet1.write(row, 22, (line.name and line.name or ""), Style.normal_left())
                local_amt += abs(line.amount_untaxed_signed)
                local_tax += abs(line.amount_tax_company_currency)
                local_total += abs(line.amount_total_company_signed)
                local_due += abs(line.residual_company_signed)
            row = row + 1
            sheet1.write(row, 16, local_amt, Style.groupByTotal3Separator())
            sheet1.write(row, 17, local_tax, Style.groupByTotal3Separator())
            sheet1.write(row, 18, local_total, Style.groupByTotal3Separator())
            sheet1.write(row, 19, local_due, Style.groupByTotal3Separator())
            amt_local += local_amt
            tax_local += local_tax
            total_local += local_total
            due_local += local_due
        row = row + 1
        sheet1.write_merge(row, row, 0, 15, 'Grand Total', Style.groupByTitle())
        sheet1.write(row, 16, amt_local, Style.groupByTotal3Separator())
        sheet1.write(row, 17, tax_local, Style.groupByTotal3Separator())
        sheet1.write(row, 18, total_local, Style.groupByTotal3Separator())
        sheet1.write(row, 19, due_local, Style.groupByTotal3Separator())
        
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'invoice.outstanding.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
