# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_sale.wizard.excel_styles import ExcelStyles
from odoo.exceptions import UserError
import xlwt
from io import BytesIO
import base64
import xlrd
#import parser
#from itertools import ifilterfalse

import json
from lxml import etree

class SaleOrdersDetailedReportWizard(models.TransientModel):
    _name = 'sale.orders.detailed.report.wizard'
    _description = 'Sale Orders Detailed Report Wizard'
    
    date_from = fields.Date(string='From Date(Order Date)', required=True)
    date_to = fields.Date(string='To Date(Order Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'so_detailed_register_partner', 'so_detailed_wizard_id', 'res_partner_id', string='Customer')
    user_ids = fields.Many2many('res.users', 'so_detailed_register_user', 'so_detailed_wizard_id', 'res_users_id', string='Sales Manager')
    currency_ids = fields.Many2many('res.currency', 'so_detailed_register_currency', 'so_detailed_wizard_id', 'res_currency_id', string='Currency')
    team_ids = fields.Many2many('crm.team', 'so_detailed_register_team', 'so_detailed_wizard_id', 'team_id', string='Sales Team')
    warehouse_ids = fields.Many2many('stock.warehouse', 'so_detailed_register_warehouse', 'so_detailed_wizard_id', 'warehouse_id', string='Warehouse')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sale.orders.detailed.report.wizard'))
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('waiting', 'Waiting For Approval'),
        ('waiting_higher', 'Waiting For Higher Authority Approval'),
        ('done', 'Approved'),
        ('cancel', 'Cancelled'),
        ], string='Order Status')
    invoice_status = fields.Selection([
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status')
        
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(SaleOrdersDetailedReportWizard, self).fields_view_get(
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
        
    #@api.multi
    def action_report(self):
        date_from = self.date_from
        date_to = self.date_to
        filters = "Filtered Based On: Sale Order Date"
        partner_ids = []
        customer = []
        customer_str = ""
        user_ids = []
        manager = []
        manager_str = ""
        currency_ids = []
        currency = []
        currency_str = ""
        team_ids = []
        teams = []
        teams_str = ""
        warehouse_ids = []
        warehouse = []
        warehouse_list = []
        warehouse_str = ""
        manager_user_sql = """ """
        partner_sql = """ """
        currency_sql = """ """
        team_sql = """ """
        warehouse_sql = """ """
        state_sql = """ """
        invoice_status_sql = """ """
        if self.partner_ids:
            for each_id in self.partner_ids:
                partner_ids.append(each_id.id)
                customer.append(each_id.name)
            customer = list(set(customer))
            customer_str = str(customer).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(partner_ids) > 1:
                partner_ids = tuple(partner_ids)
                partner_sql += " and rp.id in "+ str(partner_ids)
            else:
                partner_sql += " and rp.id in ("+ str(partner_ids[0]) + ")"
            filters += ", Customer: " + customer_str
        if self.user_ids:
            for each_id in self.user_ids:
                user_ids.append(each_id.id)
                manager.append(each_id.partner_id.name)
            manager = list(set(manager))
            manager_str = str(manager).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(user_ids) > 1:
                manager_user_sql += "and rp.sales_manager_id in " + str(tuple(user_ids))
            else:
                manager_user_sql += "and rp.sales_manager_id in (" + str(user_ids[0]) + ")" 
            filters += ", Sales Manager: " + manager_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                currency_ids.append(each_id.id)
                currency.append(each_id.name)
            currency = list(set(currency))
            currency_str = str(currency).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(currency_ids) > 1:
                currency_sql += "and price.currency_id in "+ str(tuple(currency_ids))
            else:
                currency_sql += "and price.currency_id in ("+ str(currency_ids[0]) + ")"
            filters += ", Currency: " + currency_str
        if self.team_ids:
            for each_id in self.team_ids:
                team_ids.append(each_id.id)
                teams.append(each_id.name)
            teams = list(set(teams))
            teams_str = str(teams).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(team_ids) > 1:
                team_sql += "and rp.team_id in "+ str(tuple(team_ids))
            else:
                team_sql += "and rp.team_id in ("+ str(team_ids[0]) + ")"
            filters += ", Sales Team: " + teams_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse.append(each_id.name)
            warehouse = list(set(warehouse))
            warehouse_str = str(warehouse).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and so.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and so.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each_id in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each_id.id)
                    warehouse_list.append(each_id.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")    
                if len(warehouse_ids) > 1:
                    warehouse_sql += "and so.warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += "and so.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                filters += ", Warehouse: " + warehouse_str
        if self.state:
            state_sql += "and so.state = '"+ str(self.state) + "'"
            filters += ", Sale Order State: " + str(self.state)
        if self.invoice_status:
            invoice_status_sql += "and so.invoice_status = '"+ str(self.invoice_status) + "'"
            filters += ", Invoice Status: " + str(self.invoice_status)
        report_name = ""
        report_name = "Sale Orders List Detailed"
        sql = """select
                     rp.name as customer,
                     so.name as sales_order_no,
                     so.id as order_id,
                     ((so.date_order at time zone %s)::timestamp::date) as sale_order_date,
                     so.client_order_ref as customer_reference,
                     price.name as pricelist,
                     payment.name as payment,
                     currency.name as currency,
                     invoice.name as invoice_address,
                     delivery.name as delivery_address,
                     warehouse.name as warehouse,
                     manager.name as sales_manager,
                     so.amount_untaxed as untaxed_amount,
                     so.amount_discounted as discounted_amount,
                     so.amount_tax as tax_amount,
                     so.amount_total as total_amount,
                     so.state,
                     so.invoice_status
                 from 
                     sale_order so
                     left join res_partner rp on (rp.id = so.partner_id)
                     left join product_pricelist price on (price.id = so.pricelist_id)
                     left join account_payment_term payment on (payment.id = so.payment_term_id)
                     left join res_currency currency on (currency.id = price.currency_id)
                     left join res_partner invoice on (invoice.id = so.partner_invoice_id)
                     left join res_partner delivery on (delivery.id = so.partner_shipping_id)
                     left join stock_warehouse warehouse on (warehouse.id = so.warehouse_id)
                     left join res_users ser on(ser.id = rp.sales_manager_id)
                     left join res_partner manager on(manager.id = ser.partner_id) 
                 where
                    ((so.date_order at time zone %s)::timestamp::date) >= %s  and ((so.date_order at time zone %s)::timestamp::date) <= %s"""+ partner_sql + manager_user_sql + team_sql + currency_sql + warehouse_sql + state_sql+ invoice_status_sql +"""
                 group by 
                     so.state,
                     so.invoice_status,
                     rp.name,
                     so.id,
                     ((so.date_order at time zone %s)::timestamp::date),
                     so.client_order_ref,
                     price.name,
                     payment.name,
                     currency.name,
                     invoice.name,
                     delivery.name,
                     warehouse.name,
                     manager.name,
                     so.amount_untaxed,
                     so.amount_discounted,
                     so.amount_tax,
                     so.amount_total
                 order by
                     warehouse.name, so.name, so.date_order
                    """
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(sql , ( tz, tz, date_from, tz, date_to, tz,))
        t = self.env.cr.dictfetchall()
        if len(t) == 0:
            raise UserError(_('No Records available on these Filter.Try  Using Different Values'))
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
#        sheet1.show_grid = False 
        sheet1.col(0).width = 3500
        sheet1.col(1).width = 5500
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 5500
        sheet1.col(5).width = 3500
        sheet1.col(6).width = 5500
        sheet1.col(7).width = 6000
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 5500
        sheet1.col(11).width = 4500
        sheet1.col(12).width = 6000
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500
        sheet1.col(18).width = 5000
        sheet1.col(19).width = 3500
        sheet1.col(20).width = 3500
        sheet1.col(21).width = 3500
        sheet1.col(22).width = 3500
        sheet1.col(23).width = 5000
        sheet1.col(24).width = 4500
        sheet1.col(25).width = 5500
        sheet1.col(26).width = 3500
        sheet1.col(27).width = 3500
        sheet1.col(28).width = 3500
        sheet1.col(29).width = 3500
        sheet1.col(30).width = 4500
        sheet1.col(31).width = 3500
        sheet1.col(32).width = 3500
        sheet1.col(33).width = 4500
        
        
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        date_from = time.strptime(str(date_from), "%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y', date_from)
        date_to = time.strptime(str(date_to), "%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y', date_to)
        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to + ' )'
        sheet1.write_merge(rc, rc, 0, 33, (self.company_id.name), Style.title_ice_blue())
        sheet1.write_merge(r1, r1, 0, 33, title, Style.title_ice_blue())
        sheet1.write_merge(r2, r2, 0, 12, filters, Style.groupByTitle())
        sheet1.write_merge(r2, r2, 13, 17, 'Order Currency', Style.groupByTitle())
        sheet1.write_merge(r2, r2, 18, 21, 'Local Currency (Company Currency)', Style.groupByTitle())
        sheet1.write_merge(r2, r2, 22, 23, '', Style.groupByTitle())
        sheet1.write_merge(r2, r2, 24, 33, 'Sale Order Lines', Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 1, "Warehouse", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 2, "Sale Order Number", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 3, "Sale Order Date", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 4, "Customer", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 5, "Customer Reference", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 6, "Invoice Adddress", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 7, "Delivery Address", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 8, "Pricelist", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 9, "Payment Term", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 10, "Sales Team", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 11, "Sales Manager", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 12, "Sales Person", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 13, "Currency", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 14, "Untaxed Amount", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 15, "Discount Amount", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 16, "Tax Amount", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 17, "Total Amount", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 18, "Untaxed Amount", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 19, "Discount Amount", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 20, "Tax Amount", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 21, "Total Amount", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 22, "Order Status", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 23, "Invoice Status", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 24, "Product", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 25, "Description", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 26, "Ordered Qty", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 27, "Delivered Qty", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 28, "Invoice Qty", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 29, "UOM", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 30, "Sales Person", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 31, "Unit Price", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 32, "Discount (%)", Style.contentTextBold(r3,'black','white'))
        sheet1.write(r3, 33, "Subtotal w/o Tax", Style.contentTextBold(r3,'black','white'))
        
        amount_untaxed_cc_subtotal, discount_amount_cc_subtotal = 0.00, 0.00
        tax_amount_cc_subtotal, total_amount_cc_subtotal = 0.00, 0.00
        subtotal_row = 0
        row = 3
        s_no = 0
        so_obj = self.env['sale.order']
        sales_team = ""
        for each in t:
            so_browse = so_obj.sudo().browse(each['order_id'])
            payment = each.get('payment')
            price_list = each.get('pricelist')
            if payment is not None and 'en_US' in payment:
                requested_payment = payment['en_US']
            else:
                requested_payment = 'Unknown'
            if price_list is not None and 'en_US' in price_list:
                requested_price_list = price_list['en_US']
            else:
                requested_price_list = 'Unknown'
            row = row + 1
            s_no = s_no + 1
            sale_line_search = self.env['sale.order.line'].sudo().search_read([('order_id', '=', each['order_id'])],['sales_user_id'])
            sales_person_list = []
            sales_person_list_str = ""
            for each_user in sale_line_search:
                sales_person_list.append(each_user['sales_user_id'][1] if each_user['sales_user_id'] else '')
            if sales_person_list:
                sales_person_list = list(set(sales_person_list))
                sales_person_list_str = str(sales_person_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            sheet1.row(row).height = 450
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['warehouse'], Style.normal_left())
            sheet1.write(row, 2, each['sales_order_no'], Style.normal_left())
            sale_order_date_str = each['sale_order_date'].strftime('%Y-%m-%d')
            sale_order_date = time.strptime(sale_order_date_str, "%Y-%m-%d")
            sale_order_date = time.strftime('%d-%m-%Y', sale_order_date)
            sheet1.write(row, 3, sale_order_date, Style.normal_left())
            sheet1.write(row, 4, each['customer'], Style.normal_left())
            sheet1.write(row, 5, each['customer_reference'], Style.normal_left())
            sheet1.write(row, 6, each['invoice_address'], Style.normal_left())
            sheet1.write(row, 7, each['delivery_address'], Style.normal_left())
            sheet1.write(row, 8, requested_price_list, Style.normal_left())
            sheet1.write(row, 9, requested_payment, Style.normal_left())
            sales_team = so_browse.team_id and so_browse.team_id.name or ""
            sheet1.write(row, 10, sales_team, Style.normal_left())
            sheet1.write(row, 11, each['sales_manager'], Style.normal_left())
            sheet1.write(row, 12, sales_person_list_str, Style.normal_left())
            sheet1.write(row, 13, each['currency'], Style.normal_left())
            sheet1.write(row, 14, each['untaxed_amount'], Style.normal_num_right_3separator())
            sheet1.write(row, 15, each['discounted_amount'], Style.normal_num_right_3separator())
            sheet1.write(row, 16, each['tax_amount'], Style.normal_num_right_3separator())
            sheet1.write(row, 17, each['total_amount'], Style.normal_num_right_3separator())
            amount_untaxed_company_currency = each['untaxed_amount']
            tax_amount_company_currency = each['tax_amount']
            total_amount_company_currency = each['total_amount']
            discount_amount_company_currency = each['discounted_amount']
            if so_browse.currency_id and so_browse.company_id and so_browse.currency_id != so_browse.company_id.currency_id:
                    currency_id = so_browse.currency_id.with_context(date=so_browse.date_order)
                    amount_untaxed_company_currency = currency_id._convert(each['untaxed_amount'], so_browse.company_id.currency_id)
                    tax_amount_company_currency = currency_id._convert(each['tax_amount'], so_browse.company_id.currency_id)
                    total_amount_company_currency = currency_id._convert(each['total_amount'], so_browse.company_id.currency_id)
                    discount_amount_company_currency =  currency_id._convert(each['discounted_amount'], so_browse.company_id.currency_id)
            amount_untaxed_cc_subtotal += amount_untaxed_company_currency or 0.0
            discount_amount_cc_subtotal += discount_amount_company_currency or 0.0
            tax_amount_cc_subtotal += tax_amount_company_currency or 0.0
            total_amount_cc_subtotal += total_amount_company_currency or 0.0
            sheet1.write(row, 18, amount_untaxed_company_currency, Style.normal_num_right_3separator())
            sheet1.write(row, 19, discount_amount_company_currency, Style.normal_num_right_3separator())
            sheet1.write(row, 20, tax_amount_company_currency, Style.normal_num_right_3separator())
            sheet1.write(row, 21, total_amount_company_currency, Style.normal_num_right_3separator())
            if each['state'] == 'draft':
                sheet1.write(row, 22, 'Quotation', Style.normal_left())
            elif each['state'] == 'sent':
                sheet1.write(row, 22, 'Quotation Sent', Style.normal_left())
            elif each['state'] == 'waiting':
                sheet1.write(row, 22, 'Waiting For Approval', Style.normal_left())
            elif each['state'] == 'waiting_higher':
                sheet1.write(row, 22, 'Waiting For Higher Authority Approval', Style.normal_left())
            elif each['state'] == 'sale':
                sheet1.write(row, 22, 'Sales Order', Style.normal_left())
            elif each['state'] == 'done':
                sheet1.write(row, 22, 'Approved', Style.normal_left())
            elif each['state'] == 'cancel':
                sheet1.write(row, 22,'Cancelled', Style.normal_left())
            if each['invoice_status'] == 'upselling':
                sheet1.write(row, 23, 'Upselling Opportunity', Style.normal_left())
            if each['invoice_status'] == 'invoiced':
                sheet1.write(row, 23, 'Fully Invoiced', Style.normal_left())
            if each['invoice_status'] == 'to invoice':
                sheet1.write(row, 23, 'To Invoice', Style.normal_left())
            if each['invoice_status'] == 'no':
                sheet1.write(row, 23, 'Nothing to Invoice', Style.normal_left())
            count = 0
            for line in sale_line_search:
                line_browse = self.env['sale.order.line'].sudo().browse(line['id'])
                if count > 0:
                    row += 1
                sheet1.row(row).height = 450
                sheet1.write(row, 24, line_browse.product_id.name, Style.normal_left())
                sheet1.write(row, 25, line_browse.name, Style.normal_left())
                sheet1.write(row, 26, line_browse.product_uom_qty, Style.normal_num_right_3digits())
                sheet1.write(row, 27, line_browse.qty_delivered, Style.normal_num_right_3digits())
                sheet1.write(row, 28, line_browse.qty_invoiced, Style.normal_num_right_3digits())
                sheet1.write(row, 29, line_browse.product_uom.name, Style.normal_left())
                sheet1.write(row, 30, line_browse.sales_user_id.name, Style.normal_left())
                sheet1.write(row, 31, line_browse.price_unit, Style.normal_num_right_3separator())
                sheet1.write(row, 32, line_browse.discount, Style.normal_num_right_3separator())
                sheet1.write(row, 33, line_browse.price_subtotal, Style.normal_num_right_3separator())
                count += 1
                
        subtotal_row = row + 1
        sheet1.write_merge(subtotal_row, subtotal_row, 0, 17, "Total", Style.normal_right_ice_blue())
        sheet1.write_merge(subtotal_row, subtotal_row, 22, 33, " ", Style.normal_right_ice_blue())
        sheet1.write(subtotal_row, 18, amount_untaxed_cc_subtotal, Style.normal_right_ice_blue())
        sheet1.write(subtotal_row, 19, discount_amount_cc_subtotal, Style.normal_right_ice_blue())
        sheet1.write(subtotal_row, 20, tax_amount_cc_subtotal, Style.normal_right_ice_blue())
        sheet1.write(subtotal_row, 21, total_amount_cc_subtotal, Style.normal_right_ice_blue())
        stream = BytesIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.orders.detailed.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
