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

class CustomerSaleInvoiceReportWizard(models.TransientModel):
    _name = 'customer.sale.invoice.report.wizard'
    _description = 'Customer Based Sales And Invoice Report'
    
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(CustomerSaleInvoiceReportWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            warehouse_id = []
            for each in self.env.user.sudo().default_warehouse_ids:
                warehouse_id.append(each.id)
            if warehouse_id:
                for node in doc.xpath("//field[@name='partner_id']"):
                    node.set('domain', "[('customer', '=', True), ('delivery_warehouse_id', 'in', " + str(warehouse_id) + "), ('parent_id', '=', False)]")
            res['arch'] = etree.tostring(doc)
        else:
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='partner_id']"):
                node.set('domain', "[('customer', '=', True), ('parent_id', '=', False)]")
            res['arch'] = etree.tostring(doc)
        return res
    
    @api.multi
    def action_report(self):
        sale_obj = self.env['sale.order']
        invoice_obj = self.env['account.invoice']
        pos_obj = self.env['pos.order']
        payment_obj = self.env['account.payment']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Customer 360 Report"
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        domain_default = []
        domain_default = [('date_order', '>=', self.date_from), ('date_order', '<=', self.date_to), ('partner_id', '=', self.partner_id.id), ('state', 'not in', ('cancel', 'draft'))]
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
#        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4000
        sheet1.col(2).width = 4000
        sheet1.col(3).width = 15000
        sheet1.col(4).width = 5800
        sheet1.col(5).width = 4800
        sheet1.col(6).width = 5500
        sheet1.col(7).width = 4000
        sheet1.col(8).width = 4000
        sheet1.col(9).width = 4000
        sheet1.col(10).width = 4000
        sheet1.col(11).width = 4000
        sheet1.col(12).width = 4000
        sheet1.col(13).width = 4000
        sheet1.col(14).width = 4000
        sheet1.col(15).width = 4000
        sheet1.col(16).width = 4500
        sheet1.col(17).width = 4000
        sheet1.col(18).width = 4000
        sheet1.col(19).width = 4000
        sheet1.col(20).width = 4000
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 256 * 3
        title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' ) - ' + str(self.partner_id.name_get()[0][1])
        title1 = self.company_id.name
        title2 = 'Sale Order' 
        sheet1.write_merge(r1, r1, 0, 19, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 19, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 16, title2, Style.title_left())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Sale Order No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Order Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "Delivery Address", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Expected Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Customer Ref", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Sales Manager", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Sales Team", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Pricelist", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Payment Terms", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 11, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 12, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 13, "Discount Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 14, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 15, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 16, "Status", Style.contentTextBold(r2,'black','white'))
        
        row = r4
        s_no = 0
        sale_record = sale_obj.sudo().search(domain_default, order="name asc, date_order asc")
        sal_amount_untaxed = sal_amount_discounted = sal_amount_tax = sal_amount_total = 0.00
        for each in sale_record:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 400
            address = ((each.partner_shipping_id and each.partner_shipping_id.street or "") 
                            + ' ' + (each.partner_shipping_id.city or "") 
                            + ' ' + (each.partner_shipping_id.area_id and each.partner_shipping_id.area_id.name or "") 
                            + ' ' + (each.partner_shipping_id.region_id and each.partner_shipping_id.region_id.name or "") 
                            + ' ' + (each.partner_shipping_id.country_id and each.partner_shipping_id.country_id.name or ""))
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each.name, Style.normal_left())
            update_so_date = ""
            if each.date_order:
                so_date = time.strftime(each.date_order) 
                so_date = datetime.strptime(so_date, '%Y-%m-%d %H:%M:%S').date() 
                update_so_date = datetime.strftime(so_date, '%d-%m-%Y') 
            sheet1.write(row, 2, update_so_date, Style.normal_left())
            sheet1.write(row, 3, address, Style.normal_left())
            exp_delivery_date = ""
            if each.exp_delivery_date:
                exp_delivery_date = time.strptime(each.exp_delivery_date, "%Y-%m-%d")
                exp_delivery_date = time.strftime('%d-%m-%Y', exp_delivery_date) 
            sheet1.write(row, 4, exp_delivery_date, Style.normal_left())
            sheet1.write(row, 5, (each.client_order_ref and each.client_order_ref or ""), Style.normal_left())
            sheet1.write(row, 6, (each.warehouse_id and each.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(row, 7, (each.sales_manager_id and each.sales_manager_id.name  or ""), Style.normal_left())
            sheet1.write(row, 8, (each.team_id and each.team_id.name  or ""), Style.normal_left())
            sheet1.write(row, 9, (each.pricelist_id and each.pricelist_id.name or ""), Style.normal_left())
            sheet1.write(row, 10, (each.payment_term_id and each.payment_term_id.name or ""), Style.normal_left())
            sheet1.write(row, 11, (each.currency_id and each.currency_id.name or ""), Style.normal_left())
            sheet1.write(row, 12, each.amount_untaxed, Style.normal_num_right_3separator())
            sheet1.write(row, 13, each.amount_discounted, Style.normal_num_right_3separator())
            sheet1.write(row, 14, each.amount_tax, Style.normal_num_right_3separator())
            sheet1.write(row, 15, each.amount_total, Style.normal_num_right_3separator())
            state = ""
            if each.state == 'draft':
                state = "Quotation"
            if each.state == 'sent':
                state = "Quotation Sent"
            if each.state == 'waiting':
                state = "Waiting For Approval"
            if each.state == 'waiting_higher':
                state = "Waiting For Higher Authority Approval"
            if each.state in ['sale', 'done']:
                state = "Sales Order"
            sheet1.write(row, 16, state, Style.normal_left())
            sal_amount_untaxed += each.amount_untaxed
            sal_amount_discounted += each.amount_discounted
            sal_amount_tax += each.amount_tax
            sal_amount_total += each.amount_total 
        
        row = row + 1
        sheet1.write_merge(row, row, 0, 11, 'Grand Total', Style.groupByTitle())
        sheet1.write_merge(row, row, 12, 12, sal_amount_untaxed, Style.groupByTotal3Separator())
        sheet1.write_merge(row, row, 13, 13, sal_amount_discounted, Style.groupByTotal3Separator())
        sheet1.write_merge(row, row, 14, 14, sal_amount_tax, Style.groupByTotal3Separator())
        sheet1.write_merge(row, row, 15, 15, sal_amount_total, Style.groupByTotal3Separator())
            
        # Account Invoice Report
        row = row + 4
        invoice_records = invoice_obj.sudo().search([('date_invoice', '>=',  self.date_from), ('date_invoice', '<=', self.date_to), ('partner_id', '=', self.partner_id.id),('state', 'in', ('open', 'paid'))], order="number, date_invoice, date_due")
        
        title_row = row 
        heading_row = title_row + 1 
        sheet1.row(title_row).height = 200 * 2
        sheet1.row(heading_row).height = 256 * 3
        title1 = 'Account Invoice'
        title2 = 'Local Currency' + ' ( ' + str(self.company_id.currency_id.name) + ' )'
        sheet1.write_merge(title_row, title_row, 0, 8, title1, Style.title_left())
        sheet1.write_merge(title_row, title_row, 9, 14, 'Transaction Currency', Style.subTitle())
        sheet1.write_merge(title_row, title_row, 15, 19, title2, Style.subTitle())
        
        sheet1.write(heading_row, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 1, "Invoice No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 2, "Invoice Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 3, "Delivery Address", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 4, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 5, "Sales Manager", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 6, "Sales Team", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 7, "Due Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 8, "Due Days", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 9, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 10, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 11, "Discount Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 12, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 13, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 14, "Due Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 15, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 16, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 17, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 18, "Due Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 19, "Status", Style.contentTextBold(r2,'black','white'))
        
        each_row = heading_row
        each_no = 0
        local_acc_invoice_amount = local_acc_tax_amount = local_acc_total_amount = local_acc_due_amount = 0.00
        for each_inv in invoice_records:
            each_row = each_row + 1
            each_no = each_no + 1
            sheet1.row(each_row).height = 300
            inv_address = ((each_inv.partner_shipping_id and each_inv.partner_shipping_id.street or "") 
                            + ' ' + (each_inv.partner_shipping_id.city or "") 
                            + ' ' + (each_inv.partner_shipping_id.area_id and each_inv.partner_shipping_id.area_id.name or "") 
                            + ' ' + (each_inv.partner_shipping_id.region_id and each_inv.partner_shipping_id.region_id.name or "") 
                            + ' ' + (each_inv.partner_shipping_id.country_id and each_inv.partner_shipping_id.country_id.name or ""))
            sheet1.write(each_row, 0, each_no, Style.normal_left())
            sheet1.write(each_row, 1, each_inv.number, Style.normal_left())
            date_invoice = ""
            if each_inv.date_invoice:
                date_invoice = time.strptime(each_inv.date_invoice, "%Y-%m-%d")
                date_invoice = time.strftime('%d-%m-%Y', date_invoice)
            sheet1.write(each_row, 2, date_invoice, Style.normal_left())
            sheet1.write(each_row, 3, inv_address, Style.normal_left())
            sheet1.write(each_row, 4, (each_inv.warehouse_id and each_inv.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 5, (each_inv.sales_manager_id and each_inv.sales_manager_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 6, (each_inv.team_id and each_inv.team_id.name or ""), Style.normal_left())
            date_due = ""
            if each_inv.date_due:
                date_due = time.strptime(each_inv.date_due, "%Y-%m-%d")
                date_due = time.strftime('%d-%m-%Y', date_due)
            sheet1.write(each_row, 7, date_due, Style.normal_left())
            due_diff_days = 0
            current_date = datetime.now()
            if each_inv.date_due and current_date:
                due_date = time.strftime(each_inv.date_due)
                due_date = datetime.strptime(due_date, '%Y-%m-%d')
                if current_date > due_date:
                    due_diff_days = (current_date - due_date).days
            sheet1.write(each_row, 8, due_diff_days, Style.normal_right())
            sheet1.write(each_row, 9, (each_inv.currency_id and each_inv.currency_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 10, each_inv.amount_untaxed, Style.normal_num_right_3separator())
            sheet1.write(each_row, 11, each_inv.amount_discounted, Style.normal_num_right_3separator())
            sheet1.write(each_row, 12, each_inv.amount_tax, Style.normal_num_right_3separator())
            sheet1.write(each_row, 13, each_inv.amount_total, Style.normal_num_right_3separator())
            sheet1.write(each_row, 14, each_inv.residual, Style.normal_num_right_3separator())
            
            sheet1.write(each_row, 15, abs(each_inv.amount_untaxed_signed), Style.normal_num_right_3separator())
            sheet1.write(each_row, 16, abs(each_inv.amount_tax_company_currency), Style.normal_num_right_3separator())
            sheet1.write(each_row, 17, abs(each_inv.amount_total_company_signed), Style.normal_num_right_3separator())
            sheet1.write(each_row, 18, abs(each_inv.residual_company_signed), Style.normal_num_right_3separator())
            state = ""
            if each_inv.state == 'open':
                state = "Open"
            if each_inv.state == 'paid':
                state = "Paid"
            sheet1.write(each_row, 19, state, Style.normal_left())
            
            local_acc_invoice_amount += abs(each_inv.amount_untaxed_signed)
            local_acc_tax_amount += abs(each_inv.amount_tax_company_currency)
            local_acc_total_amount += abs(each_inv.amount_total_company_signed)
            local_acc_due_amount += abs(each_inv.residual_company_signed)
            
        each_row = each_row + 1
        sheet1.write_merge(each_row, each_row, 0, 14, 'Invoice Total', Style.groupByTitle())
        sheet1.write_merge(each_row, each_row, 15, 15, local_acc_invoice_amount, Style.groupByTotal3Separator())
        sheet1.write_merge(each_row, each_row, 16, 16, local_acc_tax_amount, Style.groupByTotal3Separator())
        sheet1.write_merge(each_row, each_row, 17, 17, local_acc_total_amount, Style.groupByTotal3Separator())
        sheet1.write_merge(each_row, each_row, 18, 18, local_acc_due_amount, Style.groupByTotal3Separator())
        
        # POS Invoice Report
        each_row = each_row + 4
        pos_records = pos_obj.sudo().search([('date_order', '>=',  self.date_from), ('date_order', '<=',  self.date_to), ('partner_id', '=', self.partner_id.id), ('state', 'in', ('paid', 'done'))], order="date_order asc")
        
        title_row = each_row 
        heading_row = title_row + 1 
        sheet1.row(title_row).height = 200 * 2
        sheet1.row(heading_row).height = 256 * 3
        title1 = 'POS Invoice'
        title2 = 'Local Currency' + ' ( ' + str(self.company_id.currency_id.name) + ' )'
        sheet1.write_merge(title_row, title_row, 0, 6, title1, Style.title_left())
        sheet1.write_merge(title_row, title_row, 7, 10, 'Transaction Currency', Style.subTitle())
        sheet1.write_merge(title_row, title_row, 11, 14, title2, Style.subTitle())
        
        sheet1.write(heading_row, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 1, "Invoice No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 2, "Invoice Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 3, "Delivery Address", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 4, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 5, "Location", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 6, "Salesman", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 7, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 8, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 9, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 10, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 11, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 12, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 13, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 14, "Status", Style.contentTextBold(r2,'black','white'))
        
        each_row = heading_row
        each_pos_no = 0
        pos_invoice_amount = pos_tax_amount = pos_total_amount = 0.00
        for each_pos in pos_records:
            each_row = each_row + 1
            each_pos_no = each_pos_no + 1
            sheet1.row(each_row).height = 300
            sheet1.write(each_row, 0, each_pos_no, Style.normal_left())
            sheet1.write(each_row, 1, (each_pos.name and each_pos.name or ""), Style.normal_left())
            update_order_date = ""
            if each_pos.date_order:
                order_date = time.strftime(each_pos.date_order) 
                order_date = datetime.strptime(order_date, '%Y-%m-%d %H:%M:%S').date() 
                update_order_date = datetime.strftime(order_date, '%d-%m-%Y')
            sheet1.write(each_row, 2, update_order_date, Style.normal_left())
            partner_address = ""
            partner_address = (each_pos.partner_id and each_pos.partner_id.name or "") + " - " + (each_pos.partner_name and each_pos.partner_name or "") + "\n" + (each_pos.partner_address and each_pos.partner_address or "")
            sheet1.write(each_row, 3, partner_address, Style.normal_left())
            sheet1.write(each_row, 4, (each_pos.session_id.config_id.warehouse_id and each_pos.session_id.config_id.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 5, (each_pos.location_id and each_pos.location_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 6, (each_pos.user_id and each_pos.user_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 7, (each_pos.pricelist_id.currency_id and each_pos.pricelist_id.currency_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 8, each_pos.amount_untaxed, Style.normal_num_right_3separator())
            sheet1.write(each_row, 9, each_pos.amount_tax, Style.normal_num_right_3separator())
            sheet1.write(each_row, 10, each_pos.amount_total, Style.normal_num_right_3separator())
            sheet1.write(each_row, 11, each_pos.amount_untaxed_company_currency, Style.normal_num_right_3separator())
            sheet1.write(each_row, 12, each_pos.amount_tax_company_currency, Style.normal_num_right_3separator())
            sheet1.write(each_row, 13, each_pos.amount_total_company_currency, Style.normal_num_right_3separator())
            state = ""
            if each_pos.state == 'open':
                state = "Open"
            if each_pos.state == 'paid':
                state = "Paid"
            sheet1.write(each_row, 14, state, Style.normal_left())
            
            pos_invoice_amount += each_pos.amount_untaxed_company_currency
            pos_tax_amount += each_pos.amount_tax_company_currency
            pos_total_amount += each_pos.amount_total_company_currency
            
        each_row = each_row + 1
        sheet1.write_merge(each_row, each_row, 0, 10, 'POS Total', Style.groupByTitle())
        sheet1.write_merge(each_row, each_row, 11, 11, pos_invoice_amount, Style.groupByTotal3Separator())
        sheet1.write_merge(each_row, each_row, 12, 12, pos_tax_amount, Style.groupByTotal3Separator())
        sheet1.write_merge(each_row, each_row, 13, 13, pos_total_amount, Style.groupByTotal3Separator())
        if pos_records and invoice_records:
            each_row = each_row + 1
            sheet1.write_merge(each_row, each_row, 0, 10, 'Grand Total', Style.groupByTitle())
            sheet1.write_merge(each_row, each_row, 11, 11, (local_acc_invoice_amount + pos_invoice_amount), Style.groupByTotal3Separator())
            sheet1.write_merge(each_row, each_row, 12, 12, (local_acc_tax_amount + pos_tax_amount), Style.groupByTotal3Separator())
            sheet1.write_merge(each_row, each_row, 13, 13, (local_acc_total_amount + pos_total_amount), Style.groupByTotal3Separator())
            
        # Payment Collection Report
        each_row = each_row + 4
        payment_records = payment_obj.sudo().search([('payment_date', '>=',  self.date_from), ('payment_date', '<=',  self.date_to), ('partner_id', '=', self.partner_id.id)], order="payment_date asc")
        
        title_row = each_row 
        heading_row = title_row + 1 
        sheet1.row(title_row).height = 200 * 2
        sheet1.row(heading_row).height = 256 * 3
        title1 = 'Payment Collection'
        sheet1.write_merge(title_row, title_row, 0, 11, title1, Style.title_left())
        
        sheet1.write(heading_row, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 1, "Payment Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 2, "Payment Journal", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 3, "Sales Person", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 4, "Sales Manager", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 5, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 6, "Area", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 7, "Payment Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 8, "Payment Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 9, "Amount in Local Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 10, "Customer Receipt No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(heading_row, 11, "Memo", Style.contentTextBold(r2,'black','white'))
        
        each_row = heading_row
        pay_no = 0
        payment_amt = payment_local_amt = 0.00 
        for each_pay in payment_records:
            each_row = each_row + 1
            pay_no = pay_no + 1
            sheet1.row(each_row).height = 300
            sheet1.write(each_row, 0, pay_no, Style.normal_left())
            payment_date = ""
            if each_pay.payment_date:
                payment_date = time.strptime(each_pay.payment_date, "%Y-%m-%d")
                payment_date = time.strftime('%d-%m-%Y', payment_date)
            sheet1.write(each_row, 1, payment_date, Style.normal_left())
            sheet1.write(each_row, 2, (each_pay.journal_id and each_pay.journal_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 3, "", Style.normal_left())
            sheet1.write(each_row, 4, "", Style.normal_left())
            sheet1.write(each_row, 5, (each_pay.partner_id.delivery_warehouse_id and each_pay.partner_id.delivery_warehouse_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 6, (each_pay.partner_id.area_id and each_pay.partner_id.area_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 7, (each_pay.currency_id and each_pay.currency_id.name or ""), Style.normal_left())
            sheet1.write(each_row, 8, each_pay.amount, Style.normal_num_right_3separator())
            sheet1.write(each_row, 9, each_pay.amount_local_currency, Style.normal_num_right_3separator())
            sheet1.write(each_row, 10, (each_pay.customer_receipt and each_pay.customer_receipt or ""), Style.normal_num_right_3separator())
            sheet1.write(each_row, 11, (each_pay.communication and each_pay.communication or ""), Style.normal_left())
            payment_amt += each_pay.amount
            payment_local_amt += each_pay.amount_local_currency
        each_row = each_row + 1
        sheet1.write_merge(each_row, each_row, 0, 7, 'Payment Total', Style.groupByTitle())
        sheet1.write_merge(each_row, each_row, 8, 8, payment_amt, Style.groupByTotal3Separator())
        sheet1.write_merge(each_row, each_row, 9, 9, payment_local_amt, Style.groupByTotal3Separator()) 
         
        stream = cStringIO.StringIO()
        wbk.save(stream)

        self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'customer.sale.invoice.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
