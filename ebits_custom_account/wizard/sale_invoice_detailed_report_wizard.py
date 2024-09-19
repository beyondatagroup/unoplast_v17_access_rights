# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
import xlwt
from xlwt import * 
import cStringIO
import base64
import xlrd
from collections import OrderedDict
import parser
from lxml import etree

class SaleInvoiceDetailedReportWizard(models.TransientModel):
    _name = 'sale.invoice.detailed.report.wizard'
    _description = "Sale Invoice Detailed Report Wizard"
    
    date_from = fields.Date(string='From Date (Invoice Date)', required=True)
    date_to = fields.Date(string='To Date (Invoice Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_sale_inv_detailed_partner', 'sale_inv_detailed_wizard_id', 'partner_id', string='Customer')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_sale_inv_detailed_warehouse', 'sale_inv_detailed_wizard_id', 'warehouse_id', string='Warehouse')
    user_ids = fields.Many2many('res.users', 'etc_sale_inv_detailed_users', 'sale_inv_detailed_wizard_id', 'user_id', string = 'Sales Manager')
    currency_ids = fields.Many2many('res.currency', 'etc_sale_inv_detailed_currency', 'sale_inv_detailed_wizard_id', 'currency_id', string='Currency')
    journal_ids = fields.Many2many('account.journal', 'etc_sale_inv_detailed_journal', 'sale_inv_detailed_wizard_id', 'journal_id', string='Journal')
    product_ids = fields.Many2many('product.product', 'etc_sale_inv_detailed_product', 'sale_inv_detailed_wizard_id', 'product_id', string='Product')
    team_ids = fields.Many2many('crm.team', 'etc_sale_inv_detailed_team', 'sale_inv_detailed_wizard_id', 'team_id', string='Sales Team')
    account_analytic_ids = fields.Many2many('account.analytic.account', 'etc_sale_inv_detailed_analytic_account', 'sale_inv_detailed_wizard_id', 'account_analytic_id', string='Analytic Account')
    area_ids = fields.Many2many('res.state.area', 'etc_sale_inv_detailed_res_area', 'sale_inv_detailed_wizard_id', 'area_id', string='Area')
    region_ids = fields.Many2many('res.state.region', 'etc_sale_inv_detailed_res_region', 'sale_wizard_id', 'res_state_region_id', string='Region')
    category_ids = fields.Many2many('product.category', 'etc_sale_inv_detailed_category', 'sale_inv_detailed_wizard_id', 'category_id', string='Product Category')
    type_account = fields.Selection([('out_invoice', 'Regular'), ('out_refund', 'Refund')], string='Type')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    show_weight = fields.Boolean(string='Show Weight Report')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='Format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(SaleInvoiceDetailedReportWizard, self).fields_view_get(
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
        invoice_obj = self.env['account.invoice']
        pos_obj = self.env['pos.order']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Sales Register Detailed Report"
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime("%d-%m-%Y", from_date)
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime("%d-%m-%Y", to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date) 
        
        all_partners_children = {}
        all_partner_ids = []
        partner_list = []
        partner_str = ""
        
        all_warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        all_currency_ids = []
        currency_list = []
        currency_str = ""
        
        all_journal_ids = []
        journal_list = []
        journal_str = ""
        
        all_product_ids = []
        product_list = []
        product_str = ""
        
        all_user_ids = []
        user_list = []
        user_str = ""
        
        all_team_ids = []
        team_list = []
        team_str = ""
        
        all_area_ids = []
        area_list = []
        area_str = ""
        
        all_region_ids = []
        region_list = []
        region_str = ""
        
        all_category_ids = []
        category_list = []
        category_str = ""
        
        all_account_analytic_ids = []
        account_analytic_list = []
        account_analytic_str = ""
        
        domain_default = []
        domain_default = [('date_invoice', '>=',  self.date_from), ('date_invoice', '<=',  self.date_to), ('type', 'in', ('out_invoice', 'out_refund')),('state', 'in', ('open', 'paid'))]
        domain_pos = []
        domain_pos = [('date_order', '>=',  self.date_from), ('date_order', '<=',  self.date_to), ('state', 'in', ('paid', 'done'))]
        if self.partner_ids:
            for each_id in self.partner_ids:
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id] 
                partner_list.append(each_id.name)
            partner_str = str(partner_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                domain_default = domain_default + [('partner_id', 'in', tuple(all_partner_ids))]
                domain_pos = domain_pos + [('partner_id', 'in', tuple(all_partner_ids))]
                filters += ", Customer : "+ partner_str
            else:
                domain_default = domain_default + [('partner_id', '=', all_partner_ids[0])]
                domain_pos = domain_pos + [('partner_id', '=', all_partner_ids[0])]
                filters += ", Customer : "+ partner_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                all_warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_warehouse_ids) > 1:
                domain_default = domain_default + [('warehouse_id', 'in', tuple(all_warehouse_ids))]
                domain_pos = domain_pos + [('session_id.config_id.warehouse_id', 'in', tuple(all_warehouse_ids))]
                filters += ", Warehouse : "+ warehouse_str
            else:
                domain_default = domain_default + [('warehouse_id', '=', all_warehouse_ids[0])]
                domain_pos = domain_pos + [('session_id.config_id.warehouse_id', '=', all_warehouse_ids[0])]
                filters += ", Warehouse : "+ warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    all_warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace("[","").replace("]","").replace("u'","").replace("'","")
                if len(all_warehouse_ids) > 1:
                    domain_default = domain_default + [('warehouse_id', 'in', tuple(all_warehouse_ids))]
                    domain_pos = domain_pos + [('session_id.config_id.warehouse_id', 'in', tuple(all_warehouse_ids))]
                    filters += ", Warehouse : "+ warehouse_str
                else:
                    domain_default = domain_default + [('warehouse_id', '=', all_warehouse_ids[0])]
                    domain_pos = domain_pos + [('session_id.config_id.warehouse_id', '=', all_warehouse_ids[0])]
                    filters += ", Warehouse : "+ warehouse_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                all_currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_str = str(currency_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_currency_ids) > 1:
                domain_default = domain_default + [('currency_id', 'in', tuple(all_currency_ids))]
                domain_pos = domain_pos + [('pricelist_id.currency_id', 'in', tuple(all_currency_ids))]
                filters += ", currency : "+ currency_str
            else:
                domain_default = domain_default + [('currency_id', '=', all_currency_ids[0])]
                domain_pos = domain_pos + [('pricelist_id.currency_id', '=', all_currency_ids[0])]
                filters += ", currency : "+ currency_str
        if self.journal_ids:
            for each_id in self.journal_ids:
                all_journal_ids.append(each_id.id)
                journal_list.append(each_id.name)
            journal_str = str(journal_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_journal_ids) > 1:
                domain_default = domain_default + [('journal_id', 'in', tuple(all_journal_ids))]
                domain_pos = domain_pos + [('sale_journal', 'in', tuple(all_journal_ids))]
                filters += ", Journal : "+ journal_str
            else:
                domain_default = domain_default + [('journal_id', '=', all_journal_ids[0])]
                domain_pos = domain_pos + [('sale_journal', '=', all_journal_ids[0])]
                filters += ", Journal : "+ journal_str
        if self.product_ids:
            for each_id in self.product_ids:
                all_product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_str = str(product_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_product_ids) > 1:
                domain_default = domain_default + [('invoice_line_ids.product_id', 'in', tuple(all_product_ids))]
                domain_pos = domain_pos + [('lines.product_id', 'in', tuple(all_product_ids))]
                filters += ", product : "+ product_str
            else:
                domain_default = domain_default + [('invoice_line_ids.product_id', '=', all_product_ids[0])]
                domain_pos = domain_pos + [('lines.product_id', '=', all_product_ids[0])]
                filters += ", product : "+ product_str
        if self.user_ids:
            for each_id in self.user_ids:
                all_user_ids.append(each_id.id)
                user_list.append(each_id.name)
            user_str = str(user_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_user_ids) > 1:
                domain_default = domain_default + [('sales_manager_id', 'in', tuple(all_user_ids))]
                domain_pos = domain_pos + [('user_id', 'in', tuple(all_user_ids))]
                filters += ", Sales Manager : "+ user_str
            else:
                domain_default = domain_default + [('sales_manager_id', '=', all_user_ids[0])]
                domain_pos = domain_pos + [('user_id', '=', all_user_ids[0])]
                filters += ", Sales Manager : "+ user_str
        if self.team_ids:
            for each_id in self.team_ids:
                all_team_ids.append(each_id.id)
                team_list.append(each_id.name)
            team_str = str(team_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_team_ids) > 1:
                domain_default = domain_default + [('team_id', 'in', tuple(all_team_ids))]
                filters += ", Sales Team : "+ team_str
            else:
                domain_default = domain_default + [('team_id', '=', all_team_ids[0])]
                filters += ", Sales Team : "+ team_str
        if self.area_ids:
            for each_id in self.area_ids:
                all_area_ids.append(each_id.id)
                area_list.append(each_id.name)
            area_str = str(area_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_area_ids) > 1:
                domain_default = domain_default + [('partner_id.area_id', 'in', tuple(all_area_ids))]
                domain_pos = domain_pos + [('partner_id.area_id', 'in', tuple(all_area_ids))]
                filters += ", Area : "+ area_str
            else:
                domain_default = domain_default + [('partner_id.area_id', '=', all_area_ids[0])]
                domain_pos = domain_pos + [('partner_id.area_id', '=', all_area_ids[0])]
                filters += ", Area : "+ area_str
                
        if self.region_ids:
            for each_id in self.region_ids:
                all_region_ids.append(each_id.id)
                region_list.append(each_id.name)
            region_str = str(region_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_region_ids) > 1:
                domain_default = domain_default + [('partner_id.region_id', 'in', tuple(all_region_ids))]
                domain_pos = domain_pos + [('partner_id.region_id', 'in', tuple(all_region_ids))]
                filters += ", Region : "+ region_str
            else:
                domain_default = domain_default + [('partner_id.region_id', '=', all_region_ids[0])]
                domain_pos = domain_pos + [('partner_id.region_id', '=', all_region_ids[0])]
                filters += ", Region : "+ region_str
            
        if self.category_ids:
            for each_id in self.category_ids:
                all_category_ids.append(each_id.id)
                category_list.append(each_id.name)
            category_str = str(category_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_category_ids) > 1:
                domain_default = domain_default + [('invoice_line_ids.product_id.categ_id', 'in', tuple(all_category_ids))]
                domain_pos = domain_pos + [('lines.product_id.categ_id', 'in', tuple(all_category_ids))]
                filters += ", Product Category : "+ category_str
            else:
                domain_default = domain_default + [('invoice_line_ids.product_id.categ_id', '=', all_category_ids[0])]
                domain_pos = domain_pos + [('lines.product_id.categ_id', '=', all_category_ids[0])]
                filters += ", product Category : "+ category_str
        if self.account_analytic_ids:
            for each_id in self.account_analytic_ids:
                all_account_analytic_ids.append(each_id.id)
                account_analytic_list.append(each_id.name)
            account_analytic_str = str(account_analytic_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_account_analytic_ids) > 1:
                domain_default = domain_default + [('invoice_line_ids.account_analytic_id', 'in', tuple(all_account_analytic_ids))]
                filters += ", Analytic Account : "+ account_analytic_str
            else:
                domain_default = domain_default + [('invoice_line_ids.account_analytic_id', '=', all_account_analytic_ids[0])]
                filters += ", Analytic Account : "+ account_analytic_str
        if self.type_account:
            domain_default = domain_default + [('type', '=', self.type_account)]
            if self.type_account == 'out_invoice':
                domain_pos = domain_pos + [('amount_untaxed_company_currency', '>=', 0.00)]
                filters += ", State : Regular"
            if self.type_account == 'out_refund':
                domain_pos = domain_pos + [('amount_untaxed_company_currency', '<', 0.00)]
                filters += ", State : Refund"
       
        invoice_records = invoice_obj.sudo().search(domain_default, order="type, warehouse_id, date_invoice, number")
        pos_record = pos_obj.sudo().search(domain_pos, order="amount_untaxed_company_currency desc, date_order, name")
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3000
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 4000
        sheet1.col(4).width = 3000
        sheet1.col(5).width = 3000
        sheet1.col(6).width = 6000
        sheet1.col(7).width = 6000
        sheet1.col(8).width = 12000
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 4000
        sheet1.col(11).width = 4500
        sheet1.col(12).width = 3000
        sheet1.col(13).width = 4000
        sheet1.col(14).width = 3000
        sheet1.col(15).width = 2500
        sheet1.col(16).width = 6500
        sheet1.col(17).width = 7000
        sheet1.col(18).width = 3000
        sheet1.col(19).width = 3000
        sheet1.col(20).width = 3000
        sheet1.col(21).width = 4500
        sheet1.col(22).width = 4800
        sheet1.col(23).width = 4800
        sheet1.col(24).width = 4000
        sheet1.col(25).width = 4000
        sheet1.col(26).width = 4800
        sheet1.col(27).width = 4800
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 256 * 3
        title = report_name + " ( Date From " + from_date + " To " + to_date + " )"
        title1 = self.company_id.name
        title2 = filters 
        title4 = "Local Currency" + " ( " + str(self.company_id.currency_id.name) + " )"
        sheet1.write_merge(r1, r1, 0, 27, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 27, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 14, title2, Style.subTitle())
        sheet1.write_merge(r3, r3, 15, 25, "Transaction Currency", Style.subTitle())
        sheet1.write_merge(r3, r3, 26, 27, title4, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 1, "Type", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 2, "Warehouse", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 3, "Invoice No", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 4, "Invoice Date", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 5, "Customer", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 6, "Area", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 7, "Region", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 8, "Delivery Address", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 9, "Created By", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 10, "Sales Team", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 11, "Sales Manager", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 12, "Journal", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 13, "Reference", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 14, "Source Document", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 15, "Currency", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 16, "Product Category", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 17, "Product", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 18, "Quantity", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 19, "UOM", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 20, "Unit Price", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 21, "Discount (%)", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 22, "Subtotal W/O TAX Amount", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 23, "Subtotal With TAX Amount", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 24, "Sales Person", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 25, "Analytic Account", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 26, "Subtotal W/O TAX Amount", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 27, "Subtotal With TAX Amount", Style.contentTextBold(r2, 'black', 'white'))
        
        row = r4
        s_no = 0
        local_inv_amt_without_tax, local_inv_amt_with_tax = 0.00, 0.00
        local_refund_amt_without_tax, local_refund_amt_with_tax = 0.00, 0.00
        
        pos_local_inv_amt_without_tax, pos_local_inv_amt_with_tax = 0.00, 0.00
        pos_local_refund_amt_without_tax, pos_local_refund_amt_with_tax = 0.00, 0.00
        
        grand_total_inv_amt_without_tax, grand_total_inv_amt_with_tax = 0.00, 0.00
        grand_total_refund_amt_without_tax, grand_total_refund_amt_with_tax = 0.00, 0.00
        
        summary = {}
        for each in invoice_records:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 500
            address = ((each.partner_shipping_id and each.partner_shipping_id.street or "") 
                                + " " + (each.partner_shipping_id.city or "") 
                                + " " + (each.partner_shipping_id.area_id and each.partner_shipping_id.area_id.name or "") 
                                + " " + (each.partner_shipping_id.region_id and each.partner_shipping_id.region_id.name or "") 
                                + " " + (each.partner_shipping_id.country_id and each.partner_shipping_id.country_id.name or ""))
            sheet1.write(row, 0, s_no, Style.normal_left())
            if each.type == 'out_invoice':
                sheet1.write(row, 1, "Regular", Style.normal_left())
            else:
                sheet1.write(row, 1, "Refund", Style.normal_left())
            sheet1.write(row, 2, (each.warehouse_id and each.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(row, 3, each.number, Style.normal_left())
            date_invoice = ""
            if each.date_invoice:
                date_invoice = time.strptime(each.date_invoice, "%Y-%m-%d")
                date_invoice = time.strftime("%d-%m-%Y", date_invoice)
            sheet1.write(row, 4, date_invoice, Style.normal_left())
            sheet1.write(row, 5, (each.partner_id and each.partner_id.name_get()[0][1] or ""), Style.normal_left())
            sheet1.write(row, 6, (each.partner_id.area_id and each.partner_id.area_id.name or ""), Style.normal_left())
            sheet1.write(row, 7, (each.partner_id.region_id and each.partner_id.region_id.name or ""), Style.normal_left())
            sheet1.write(row, 8, address, Style.normal_left())
            sheet1.write(row, 9, (each.user_id and each.user_id.name or ""), Style.normal_left())
            sheet1.write(row, 10, (each.team_id and each.team_id.name or ""), Style.normal_left())
            sheet1.write(row, 11, (each.sales_manager_id and each.sales_manager_id.name  or ""), Style.normal_left())
            sheet1.write(row, 12, (each.journal_id and each.journal_id.name or ""), Style.normal_left())
            sheet1.write(row, 13, (each.name and each.name or ""), Style.normal_left())
            sheet1.write(row, 14, (each.origin and each.origin or ""), Style.normal_left())
            sheet1.write(row, 15, (each.currency_id and each.currency_id.name or ""), Style.normal_left())
            for line in each.invoice_line_ids:
                if self.product_ids and line.product_id.id not in all_product_ids:
                    continue
                if self.account_analytic_ids and line.account_analytic_id.id not in all_account_analytic_ids:
                    continue
                if self.category_ids and line.product_id.categ_id.id not in all_category_ids:
                    continue
                sheet1.row(row).height = 500
                if self.show_weight:
                    summary_key = (each.warehouse_id and each.warehouse_id.name or "no warehouse") + " " + (line.product_id and line.product_id.name_get()[0][1] or line.name)
                    weight, quantity, product_weight = 0.00, 0.00, 0.00
                    if line.product_id:
                        categ_id = line.product_id.categ_id.with_context(x_density_date=each.date_invoice)
                        product_weight = line.product_id.volume * categ_id.x_density

                    if each.type == 'out_invoice':
                        weight = line.product_id and (product_weight * line.quantity) or 0.00
                        quantity = line.quantity and line.quantity or 0.00
                    else:
                        weight = line.product_id and (-1 * product_weight * line.quantity) or 0.00
                        quantity = line.quantity and (-1 * line.quantity) or 0.00
                    if not summary_key in summary:
                        summary[summary_key] = {
                            'warehouse': each.warehouse_id and each.warehouse_id.name or "",
                            'category': line.product_id.categ_id and line.product_id.categ_id.name or "",
                            'product': line.product_id and line.product_id.name_get()[0][1] or "",
                            'quantity': quantity,
                            'weight': weight,
                            'amount': each.type == 'out_invoice' and abs(line.price_subtotal_signed) or (-1 * abs(line.price_subtotal_signed)),
                            }
                    else:
                        summary[summary_key]['quantity'] += quantity
                        summary[summary_key]['weight'] += weight
                        summary[summary_key]['amount'] += (each.type == 'out_invoice' and abs(line.price_subtotal_signed) or (-1 * abs(line.price_subtotal_signed)))
                sheet1.write(row, 16, (line.product_id.categ_id and line.product_id.categ_id.name or ""), Style.normal_left())
                sheet1.write(row, 17, (line.product_id and line.product_id.name_get()[0][1] or ""), Style.normal_left())
                if each.type == 'out_invoice':
                    sheet1.write(row, 18, line.quantity, Style.normal_num_right_3digits())
                    sheet1.write(row, 19, (line.product_id.uom_id and line.product_id.uom_id.name or ""), Style.normal_left())
                    sheet1.write(row, 20, line.price_unit, Style.normal_num_right_3separator())
                    sheet1.write(row, 21, line.discount, Style.normal_right())
                    sheet1.write(row, 22, line.price_subtotal, Style.normal_num_right_3separator())
                    sheet1.write(row, 23, line.price_subtotal_incl, Style.normal_num_right_3separator())
                    sheet1.write(row, 24, (line.sales_user_id and line.sales_user_id.name or ""), Style.normal_left())
                    sheet1.write(row, 25, (line.account_analytic_id and line.account_analytic_id.name or ""), Style.normal_left())
                    sheet1.write(row, 26, abs(line.price_subtotal_signed), Style.normal_num_right_3separator())
                    sheet1.write(row, 27, abs(line.price_subtotal_incl_signed), Style.normal_num_right_3separator())
                    local_inv_amt_without_tax += abs(line.price_subtotal_signed)
                    local_inv_amt_with_tax += abs(line.price_subtotal_incl_signed)
                    row = row + 1
                else:
                    sheet1.write(row, 18, (-1 * line.quantity), Style.normal_num_right_3digits())
                    sheet1.write(row, 19, (line.product_id.uom_id and line.product_id.uom_id.name or ""), Style.normal_left())
                    sheet1.write(row, 20, (-1 * line.price_unit), Style.normal_num_right_3separator())
                    sheet1.write(row, 21, line.discount, Style.normal_right())
                    sheet1.write(row, 22, -1 * line.price_subtotal, Style.normal_num_right_3separator())
                    sheet1.write(row, 23, -1 * line.price_subtotal_incl, Style.normal_num_right_3separator())
                    sheet1.write(row, 24, (line.sales_user_id and line.sales_user_id.name or ""), Style.normal_left())
                    sheet1.write(row, 25, (line.account_analytic_id and line.account_analytic_id.name or ""), Style.normal_left())
                    sheet1.write(row, 26, -1 * abs(line.price_subtotal_signed), Style.normal_num_right_3separator())
                    sheet1.write(row, 27, -1 * abs(line.price_subtotal_incl_signed), Style.normal_num_right_3separator())
                    local_refund_amt_without_tax += -1 * abs(line.price_subtotal_signed)
                    local_refund_amt_with_tax += -1 * abs(line.price_subtotal_incl_signed)  
                    row = row + 1
            row = row - 1
        for each_pos in pos_record:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 500
            sheet1.write(row, 0, s_no, Style.normal_left())
            if each_pos.amount_untaxed >= 0.00:
                sheet1.write(row, 1, "POS", Style.normal_left())
            else:
                sheet1.write(row, 1, "POS Refund", Style.normal_left())
            sheet1.write(row, 2, (each_pos.session_id.config_id.warehouse_id and each_pos.session_id.config_id.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(row, 3, (each_pos.name and each_pos.name or ""), Style.normal_left())
            update_order_date = ""
            if each_pos.date_order:
                order_date = time.strftime(each_pos.date_order) 
                order_date = datetime.strptime(order_date, "%Y-%m-%d %H:%M:%S").date() 
                update_order_date = datetime.strftime(order_date, "%d-%m-%Y")
            sheet1.write(row, 4, update_order_date, Style.normal_left())
            partner_name = ""
            partner_name = (each_pos.partner_id and each_pos.partner_id.name or "") + " - " + (each_pos.partner_name and each_pos.partner_name or "")
            sheet1.write(row, 5, partner_name, Style.normal_left())
            sheet1.write(row, 6, (each_pos.partner_id.area_id and each_pos.partner_id.area_id.name or ""), Style.normal_left())
            sheet1.write(row, 7, (each_pos.partner_id.region_id and each_pos.partner_id.region_id.name or ""), Style.normal_left())
            sheet1.write(row, 8, (each_pos.partner_address and each_pos.partner_address or ""), Style.normal_left())
            sheet1.write(row, 9, (each_pos.user_id and each_pos.user_id.name or ""), Style.normal_left())
            sheet1.write(row, 10, "", Style.normal_left())
            sheet1.write(row, 11, (each_pos.partner_id.sales_manager_id and each_pos.partner_id.sales_manager_id.name or ""), Style.normal_left())
            sheet1.write(row, 12, (each_pos.sale_journal and each_pos.sale_journal.name or ""), Style.normal_left())
            sheet1.write(row, 13, (each_pos.session_id and each_pos.session_id.name or ""), Style.normal_left())
            sheet1.write(row, 14, "", Style.normal_left())
            sheet1.write(row, 15, (each_pos.pricelist_id.currency_id and each_pos.pricelist_id.currency_id.name or ""), Style.normal_left())
            for line_pos in each_pos.lines:
                if self.product_ids and line_pos.product_id.id not in all_product_ids:
                    continue
                if self.category_ids and line_pos.product_id.categ_id.id not in all_category_ids:
                    continue
                sheet1.row(row).height = 500
                if self.show_weight:
                    summary_key = (each_pos.session_id.config_id.warehouse_id and each_pos.session_id.config_id.warehouse_id.name or "no warehouse") + " " + (line_pos.product_id.name and line_pos.product_id.name_get()[0][1] or "")
#                    if each_pos.amount_untaxed >= 0.00:
#                        weight = line_pos.product_id and (line_pos.product_id.weight * line_pos.qty) or 0.00
#                        quantity = line_pos.qty and line_pos.qty or 0.00
#                    else:
#                        weight = line_pos.product_id and (-1 * line_pos.product_id.weight * line_pos.qty) or 0.00
#                        quantity = line_pos.qty and (-1 * line_pos.qty) or 0.00
                    product_weight = 0.00
                    if line_pos.product_id:
                        categ_id = line_pos.product_id.categ_id.with_context(x_density_date=each_pos.date_order)
                        product_weight = line_pos.product_id.volume * categ_id.x_density

                    if not summary_key in summary:
                        summary[summary_key] = {
                            'warehouse': each_pos.session_id.config_id.warehouse_id and each_pos.session_id.config_id.warehouse_id.name or "",
                            'category': line_pos.product_id.categ_id and line_pos.product_id.categ_id.name or "",
                            'product': line_pos.product_id and line_pos.product_id.name_get()[0][1] or "",
                            'quantity': line_pos.qty and line_pos.qty or 0.00,
                            'weight': line_pos.product_id and (product_weight * line_pos.qty) or 0.00,
                            'amount': each_pos.amount_untaxed >= 0.00 and abs(line_pos.price_subtotal_company_currency) or (-1 * abs(line_pos.price_subtotal_company_currency)),
                            }
                    else:
                        summary[summary_key]['quantity'] += line_pos.qty and line_pos.qty or 0.00
                        summary[summary_key]['weight'] += line_pos.product_id and (product_weight * line_pos.qty) or 0.00
                        summary[summary_key]['amount'] += (each_pos.amount_untaxed >= 0.00 and abs(line_pos.price_subtotal_company_currency) or (-1 * abs(line_pos.price_subtotal_company_currency)))
                sheet1.write(row, 16, (line_pos.product_id.categ_id and line_pos.product_id.categ_id.name or ""), Style.normal_left())
                sheet1.write(row, 17, (line_pos.product_id and line_pos.product_id.name_get()[0][1] or ""), Style.normal_left())
                if each_pos.amount_untaxed >= 0.00:
                    sheet1.write(row, 18, line_pos.qty, Style.normal_num_right_3digits())
                    sheet1.write(row, 19, (line_pos.product_id.uom_id and line_pos.product_id.uom_id.name or ""), Style.normal_left())
                    sheet1.write(row, 20, line_pos.price_unit, Style.normal_num_right_3separator())
                    sheet1.write(row, 21, line_pos.discount, Style.normal_right())
                    sheet1.write(row, 22, line_pos.price_subtotal, Style.normal_num_right_3separator())
                    sheet1.write(row, 23, line_pos.price_subtotal_incl, Style.normal_num_right_3separator())
                    sheet1.write(row, 24, (each_pos.user_id and each_pos.user_id.name or ""), Style.normal_left())
                    sheet1.write(row, 25, "", Style.normal_left())
                    sheet1.write(row, 26, abs(line_pos.price_subtotal_company_currency), Style.normal_num_right_3separator())
                    sheet1.write(row, 27, abs(line_pos.price_subtotal_incl_company_currency), Style.normal_num_right_3separator())
                    pos_local_inv_amt_without_tax += abs(line_pos.price_subtotal_company_currency)
                    pos_local_inv_amt_with_tax += abs(line_pos.price_subtotal_incl_company_currency)
                    row = row + 1
                else:
                    sheet1.write(row, 18, line_pos.qty, Style.normal_num_right_3digits())
                    sheet1.write(row, 19, (line_pos.product_id.uom_id and line_pos.product_id.uom_id.name or ""), Style.normal_left())
                    sheet1.write(row, 20, (-1 * line_pos.price_unit), Style.normal_num_right_3separator())
                    sheet1.write(row, 21, line_pos.discount, Style.normal_right())
                    sheet1.write(row, 22, line_pos.price_subtotal, Style.normal_num_right_3separator())
                    sheet1.write(row, 23, line_pos.price_subtotal_incl, Style.normal_num_right_3separator())
                    sheet1.write(row, 24, (each_pos.user_id and each_pos.user_id.name or ""), Style.normal_left())
                    sheet1.write(row, 25, "", Style.normal_left())
                    sheet1.write(row, 26, -1 * abs(line_pos.price_subtotal_company_currency), Style.normal_num_right_3separator())
                    sheet1.write(row, 27, -1 * abs(line_pos.price_subtotal_incl_company_currency), Style.normal_num_right_3separator())
                    pos_local_refund_amt_without_tax += -1 * abs(line_pos.price_subtotal_company_currency)
                    pos_local_refund_amt_with_tax += -1 * abs(line_pos.price_subtotal_incl_company_currency)
                    row = row + 1
            row = row - 1
        grand_total_inv_amt_without_tax = local_inv_amt_without_tax + pos_local_inv_amt_without_tax  
        grand_total_inv_amt_with_tax = local_inv_amt_with_tax + pos_local_inv_amt_with_tax    
        
        grand_total_refund_amt_without_tax = local_refund_amt_without_tax + pos_local_refund_amt_without_tax  
        grand_total_refund_amt_with_tax = local_refund_amt_with_tax + pos_local_refund_amt_with_tax 
        if self.type_account == 'out_invoice' or self.type_account == False: 
            row = row + 1
            sheet1.write_merge(row, row, 16, 25, "Invoice Total", Style.groupByTitle())
            sheet1.write(row, 26, grand_total_inv_amt_without_tax, Style.groupByTotal3Separator())
            sheet1.write(row, 27, grand_total_inv_amt_with_tax, Style.groupByTotal3Separator())
        if self.type_account == 'out_refund' or self.type_account == False: 
            row = row + 1
            sheet1.write_merge(row, row, 16, 25, "Refund Total", Style.groupByTitle())
            sheet1.write(row, 26, grand_total_refund_amt_without_tax, Style.groupByTotal3Separator())
            sheet1.write(row, 27, grand_total_refund_amt_with_tax, Style.groupByTotal3Separator())
        if self.type_account == False: 
            row = row + 1
            sheet1.write_merge(row, row, 16, 25, "Grand Total", Style.groupByTitle())
            sheet1.write(row, 26, (grand_total_inv_amt_without_tax + grand_total_refund_amt_without_tax), Style.groupByTotal3Separator())
            sheet1.write(row, 27, (grand_total_inv_amt_with_tax + grand_total_refund_amt_with_tax), Style.groupByTotal3Separator())
            
#**********************************************************Weight Report****************************************************************

        if self.show_weight and summary:
            summary = OrderedDict(sorted(summary.items(), key=lambda t: t[0]))
            pg_title = "Product Weight Summary"
            sheet2 = wbk.add_sheet(pg_title)
            sheet2.set_panes_frozen(True)
            sheet2.set_horz_split_pos(4)
            sheet2.col(0).width = 2000
            sheet2.col(1).width = 6000
            sheet2.col(2).width = 9000
            sheet2.col(3).width = 10000
            sheet2.col(4).width = 3000
            sheet2.col(5).width = 3000
            sheet2.col(6).width = 4500
            
            sheet2.row(r1).height = 500
            sheet2.row(r2).height = 400
            sheet2.row(r3).height = 200 * 2
            sheet2.row(r4).height = 256 * 3
            title = report_name + " - " + pg_title + " ( Date From " + from_date + " To " + to_date + " )"
            title1 = self.company_id.name
            title2 = filters 
            title4 = "Local Currency" + " ( " + str(self.company_id.currency_id.name) + " )"
            sheet2.write_merge(r1, r1, 0, 6, title1, Style.main_title())
            sheet2.write_merge(r2, r2, 0, 6, title, Style.sub_main_title())
            sheet2.write_merge(r3, r3, 0, 5, title2, Style.subTitle())
            sheet2.write_merge(r3, r3, 6, 6, "Local Currency", Style.subTitle())
            
            sheet2.write(r4, 0, "S.No", Style.contentTextBold(r2, 'black', 'white'))
            sheet2.write(r4, 1, "Warehouse", Style.contentTextBold(r2, 'black', 'white'))
            sheet2.write(r4, 2, "Product Category", Style.contentTextBold(r2, 'black', 'white'))
            sheet2.write(r4, 3, "Product", Style.contentTextBold(r2, 'black', 'white'))
            sheet2.write(r4, 4, "Quantity", Style.contentTextBold(r2, 'black', 'white'))
            sheet2.write(r4, 5, "Total Weight", Style.contentTextBold(r2, 'black', 'white'))
            sheet2.write(r4, 6, "Subtotal W/o Tax", Style.contentTextBold(r2, 'black', 'white'))
            
            row = r4
            s_no = 0
            ct_summary = {}
            for each in summary:
                dt = summary[each]
                ct_summary_key = (dt['warehouse'] and dt['warehouse'] or "no warehouse") + " " + dt['category']
                if not ct_summary_key in ct_summary:
                    ct_summary[ct_summary_key] = {
                        'warehouse': dt['warehouse'] and dt['warehouse'] or "",
                        'category': dt['category'] and dt['category'] or "",
                        'quantity': dt['quantity'] and dt['quantity'] or 0.00,
                        'weight': dt['weight'] and dt['weight'] or 0.00,
                        'amount': dt['amount'] and dt['amount'] or 0.00,
                        }
                else:
                    ct_summary[ct_summary_key]['quantity'] += dt['quantity'] and dt['quantity'] or 0.00
                    ct_summary[ct_summary_key]['weight'] += dt['weight'] and dt['weight'] or 0.00
                    ct_summary[ct_summary_key]['amount'] += dt['amount'] and dt['amount'] or 0.00
                    
                row += 1
                s_no += 1
                sheet2.write(row, 0, s_no, Style.normal_left())
                sheet2.write(row, 1, dt['warehouse'], Style.normal_left())
                sheet2.write(row, 2, dt['category'], Style.normal_left())
                sheet2.write(row, 3, dt['product'], Style.normal_left())
                sheet2.write(row, 4, dt['quantity'], Style.normal_left())
                sheet2.write(row, 5, dt['weight'], Style.normal_left())
                sheet2.write(row, 6, dt['amount'], Style.normal_left())
            sheet2.write_merge(row + 1, row + 1, 0, 3, "Total", Style.normal_right_ice_blue())
            for i in range(4, 7):
                start_v = xlwt.Utils.rowcol_to_cell(4, i)
                end_v = xlwt.Utils.rowcol_to_cell(row, i)
                sheet2.write(row + 1, i, Formula(('sum(' + str(start_v) + ':' + str(end_v) + ')')), Style.normal_right_ice_blue())
            if ct_summary:
                pg_title = "Category Weight Summary"       
                sheet3 = wbk.add_sheet(pg_title)
                sheet3.set_panes_frozen(True)
                sheet3.set_horz_split_pos(4)
                sheet3.col(0).width = 2000
                sheet3.col(1).width = 6000
                sheet3.col(2).width = 9000
                sheet3.col(3).width = 4000
                sheet3.col(4).width = 4000
                sheet3.col(5).width = 4500
                
                sheet3.row(r1).height = 500
                sheet3.row(r2).height = 400
                sheet3.row(r3).height = 200 * 2
                sheet3.row(r4).height = 256 * 3
                title = report_name + " - " + pg_title + " ( Date From " + from_date + " To " + to_date + " )"
                title1 = self.company_id.name
                title2 = filters 
                title4 = "Local Currency" + " ( " + str(self.company_id.currency_id.name) + " )"
                sheet3.write_merge(r1, r1, 0, 5, title1, Style.main_title())
                sheet3.write_merge(r2, r2, 0, 5, title, Style.sub_main_title())
                sheet3.write_merge(r3, r3, 0, 4, title2, Style.subTitle())
                sheet3.write_merge(r3, r3, 5, 5, "Local Currency", Style.subTitle())
                
                sheet3.write(r4, 0, "S.No", Style.contentTextBold(r2, 'black', 'white'))
                sheet3.write(r4, 1, "Warehouse", Style.contentTextBold(r2, 'black', 'white'))
                sheet3.write(r4, 2, "Product Category", Style.contentTextBold(r2, 'black', 'white'))
                sheet3.write(r4, 3, "Quantity", Style.contentTextBold(r2, 'black', 'white'))
                sheet3.write(r4, 4, "Total Weight", Style.contentTextBold(r2, 'black', 'white'))
                sheet3.write(r4, 5, "Subtotal W/o Tax", Style.contentTextBold(r2, 'black', 'white'))
                
                row = r4
                s_no = 0
                categ = ""
                wh = ""
                qty, wt, amt = 0.00, 0.00, 0.00
                ct_summary = OrderedDict(sorted(ct_summary.items(), key=lambda t: t[0]))
                for rec in ct_summary:
                    row += 1
                    s_no += 1
                    sheet3.write(row, 0, s_no, Style.normal_left())
                    sheet3.write(row, 1, ct_summary[rec]['warehouse'], Style.normal_left())
                    sheet3.write(row, 2, ct_summary[rec]['category'], Style.normal_left())
                    sheet3.write(row, 3, ct_summary[rec]['quantity'], Style.normal_left())
                    sheet3.write(row, 4, ct_summary[rec]['weight'], Style.normal_left())
                    sheet3.write(row, 5, ct_summary[rec]['amount'], Style.normal_left())
                sheet3.write_merge(row + 1, row + 1, 0, 2, "Total", Style.normal_right_ice_blue())
                for i in range(3, 6):
                    start_v = xlwt.Utils.rowcol_to_cell(4, i)
                    end_v = xlwt.Utils.rowcol_to_cell(row, i)
                    sheet3.write(row + 1, i, Formula(('sum(' + str(start_v) + ':' + str(end_v) + ')')), Style.normal_right_ice_blue())
            
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.invoice.detailed.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
