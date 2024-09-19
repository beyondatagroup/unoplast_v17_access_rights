# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_pos.wizard.excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
import xlwt
import base64
from io import BytesIO
import xlrd
from lxml import etree


class PosInvoiceSaleRegisterReportWizard(models.TransientModel):
    _name = 'pos.invoice.sale.register.report.wizard'
    _description = 'Pos Invoice Sale Register Report Wizard'
    
    date_from = fields.Date(string='From Date(Invoice Date)', required=True)
    date_to = fields.Date(string='To Date(Invoice Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'pos_invoice_sale_register_partner', 'pos_sale_wizard_id', 'res_partner_id', string='Customer')
    country_ids = fields.Many2many('res.country', 'pos_invoice_sale_register_country', 'pos_sale_wizard_id', 'res_country_id', string='Country')
    area_ids = fields.Many2many('res.state.area','pos_invoice_sale_register_area', 'pos_sale_wizard_id', 'res_state_area_id', string='Area')
    region_ids = fields.Many2many('res.state.region', 'pos_invoice_sale_register_region', 'pos_sale_wizard_id', 'res_state_region_id', string='Region')
    user_ids = fields.Many2many('res.users', 'pos_invoice_sale_register_user', 'pos_invoice_sale_register_wizard_id', 'res_users_id', string='Sales Manager')
    currency_ids = fields.Many2many('res.currency', 'pos_invoice_sale_register_currency', 'pos_invoice_sale_register_wizard_id', 'res_currency_id', string='Currency')
    warehouse_ids = fields.Many2many('stock.warehouse', 'pos_invoice_sale_register_warehouse', 'pos_invoice_sale_register_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'pos_invoice_sale_register_product', 'pos_invoice_sale_register_wizard_id', 'product_id', string='Product')
    create_user_ids = fields.Many2many('res.users', 'pos_invoice_sale_register_create_user', 'pos_invoice_sale_register_wizard_id', 'res_users_id', string='Created By')
    journal_ids = fields.Many2many('account.journal', 'pos_invoice_sale_register_journal', 'pos_invoice_sale_register_wizard_id', 'journal_id', string='Journal')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('pos.invoice.sale.register.report.wizard'))
    
    # @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PosInvoiceSaleRegisterReportWizard, self).fields_view_get(
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
    
    # @api.multi
    def action_report(self):
        if self.date_from > self.date_to:
            raise UserError(_('Invlaid date range.Please check the from and to dates that you have entered'))
        pos_obj = self.env['pos.order']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "POS Sale Register Order Wise"
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date)
        domain_default = []
        domain_default = [('state', 'in', ('invoiced', 'paid', 'done')), ('date_order', '>=',  self.date_from), ('date_order', '<=',  self.date_to)]
        partner_ids = []
        customer_list = []
        customer_str = ""
        country_ids = []
        country_list = []
        country_str = ""
        area_ids = []
        area_list = []
        area_str = ""
        region_ids = []
        region_list = []
        region_str = ""
        user_ids = []
        manager_list = []
        manager_str = ""
        currency_ids = []
        currency_list = []
        currency_str = ""
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        all_partners_children = {}
        all_partner_ids = []
        product_ids = []
        product_list = []
        product_str = ""
        all_create_user_ids = []
        user_list = []
        user_str = ""
        all_journal_ids = []
        journal_list = []
        journal_str = ""
#        country_sql = """ """
#        partner_sql = """ """
#        region_sql = """ """
#        area_sql = """ """
#        manager_user_sql = """ """
#        currency_sql = """ """
#        warehouse_sql = """ """
        filters = "Filtered Based On: Invoice Date | Invoice State (Includes Posted, Paid and Done State Only)"
        
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            filters += " | Product:" + product_str
        
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
                domain_default = domain_default + [('partner_id', 'in', all_partner_ids)]
            else:
                 domain_default = domain_default + [('partner_id', '=', all_partner_ids[0])]
            filters += " | Customer:" + customer_str
                
        if self.country_ids:
            for each_id in self.country_ids:
                country_ids.append(each_id.id)
                country_list.append(each_id.name)
            country_list = list(set(country_list))
            country_str = str(country_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(country_ids) > 1:
                domain_default = domain_default + [('partner_id.country_id', 'in', tuple(x.id for x in self.country_ids))]
            else:
                domain_default = domain_default + [('partner_id.country_id', '=', self.country_ids.id)]
            filters += " | Country: " + country_str
        if self.area_ids:
            for each_id in self.area_ids:
                area_ids.append(each_id.id)
                area_list.append(each_id.name)
            area_list = list(set(area_list))
            area_str = str(area_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(area_ids) > 1:
                domain_default = domain_default + [('partner_id.area_id', 'in', tuple(x.id for x in self.area_ids))]
            else:
                domain_default = domain_default + [('partner_id.area_id', '=',self.area_ids.id)]
            filters += " | Area: " + area_str
        if self.region_ids:
            for each_id in self.region_ids:
                region_ids.append(each_id.id)
                region_list.append(each_id.name)
            region_list = list(set(region_list))
            region_str = str(region_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(region_ids) > 1:
                domain_default = domain_default + [('partner_id.region_id', 'in', tuple(x.id for x in self.region_ids))]
            else:
                domain_default = domain_default + [('partner_id.region_id', '=',self.region_ids.id)]
            filters += " | Region: " + region_str
        if self.user_ids:
            for each_id in self.user_ids:
                user_ids.append(each_id.id)
                manager_list.append(each_id.partner_id.name)
            manager_list = list(set(manager_list))
            manager_str = str(manager_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(user_ids) > 1:
                domain_default = domain_default + [('partner_id.sales_manager_id', 'in', tuple(x.id for x in self.user_ids))]
            else:
                domain_default = domain_default + [('partner_id.sales_manager_id', '=', self.user_ids.id)]
            filters += " | Sales Manager: " + manager_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(currency_ids) > 1:
                domain_default = domain_default + [('pricelist_id.currency_id', 'in', tuple(x.id for x in self.currency_ids))]
            else:
                domain_default = domain_default + [('pricelist_id.currency_id', '=', self.currency_ids.id)]
            filters += " | Currency: " + currency_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                domain_default = domain_default + [('session_id.config_id.warehouse_id', 'in', warehouse_ids)]
            else:
                domain_default = domain_default + [('session_id.config_id.warehouse_id', '=', warehouse_ids[0])]
            filters += " | Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each_id in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each_id.id)
                    warehouse_list.append(each_id.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    domain_default = domain_default + [('session_id.config_id.warehouse_id', 'in', warehouse_ids)]
                else:
                    domain_default = domain_default + [('session_id.config_id.warehouse_id', '=', warehouse_ids[0])]
                filters += " | Warehouse: " + warehouse_str
        if self.create_user_ids:
            for each_id in self.create_user_ids:
                all_create_user_ids.append(each_id.id)
                user_list.append(each_id.name)
            user_list = list(set(user_list))
            user_str = str(user_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_create_user_ids) > 1:
                domain_default = domain_default + [('user_id', 'in', tuple(all_create_user_ids))]
            else:
                domain_default = domain_default + [('user_id', '=', all_create_user_ids[0])]
            filters += " | Created By : "+ user_str
        if self.journal_ids:
            for each_id in self.journal_ids:
                all_journal_ids.append(each_id.id)
                journal_list.append(each_id.name)
            journal_list = list(set(journal_list))
            journal_str = str(journal_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_journal_ids) > 1:
                domain_default = domain_default + [('sale_journal', 'in', tuple(all_journal_ids))]
            else:
                domain_default = domain_default + [('sale_journal', '=', all_journal_ids[0])]
            filters += " | Journal : "+ journal_str
                
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
#        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 5000
        sheet1.col(3).width = 4500
        sheet1.col(4).width = 4500
        sheet1.col(5).width = 6500
        sheet1.col(6).width = 10500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 7500
        sheet1.col(11).width = 7500
        sheet1.col(12).width = 7500
        sheet1.col(13).width = 7500
        sheet1.col(14).width = 4500
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 4500
        sheet1.col(18).width = 6500
        sheet1.col(19).width = 3500
        sheet1.col(20).width = 4500
        sheet1.col(21).width = 3500
        sheet1.col(22).width = 3500
        sheet1.col(23).width = 7500
        sheet1.col(24).width = 3500
        sheet1.col(25).width = 3500
        sheet1.col(26).width = 3500
        sheet1.col(27).width = 3500
        sheet1.col(28).width = 3500
        sheet1.col(29).width = 3500
        sheet1.col(30).width = 3500
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        date_from = time.strptime(from_date_str, "%Y-%m-%d")
        date_from = time.strftime('%d-%m-%Y', date_from)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        date_to = time.strptime(to_date_str, "%Y-%m-%d")
        date_to = time.strftime('%d-%m-%Y', date_to)

        title = report_name + ' ( Date from ' + date_from + ' to ' + date_to + ' )'
        sheet1.write_merge(rc, rc, 0, 30, self.company_id.name, Style.title_ice_blue())
        sheet1.write_merge(r1, r1, 0, 30, title, Style.title_ice_blue())
        sheet1.write_merge(r2, r2, 0, 30, filters, Style.groupByTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 1, "Sale Type", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 2, "Warehouse", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 3, "Invoice Number", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 4, "Invoice Date", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 5, "Customer", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 6, "Customer Address", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 7, "Created By", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 8, "Sales Manager", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 9, "Sales Person", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 10, "Journal", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 11, "Reference", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 12, "Region", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 13, "Area", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 14, "Country", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 15, "Invoice Currency", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 16, "Discount Amount", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 17, "Untaxed Amount", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 18, "Tax Amount", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 19, "Round Off Amount", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 20, "Total Amount", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 21, "Payment Received", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 22, "Status", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 23, "Product", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 24, "Quantity", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 25, "UOM", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 26, "Unit Price", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 27, "Discount %", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 28, "Tax Amount", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 29, "Untaxed Amount", Style.contentTextBold(2, 'black','white'))
        sheet1.write(r3, 30, "Total Amount", Style.contentTextBold(2, 'black','white'))
        row = 3
        s_no = 0
        
        untaxed_total,discount_total,tax_total,roundoff_total,total_amount_total,payment_received_total = 0.00,0.00,0.00,0.00,0.00,0.00
        total_with_tax, total_without_tax = 0.00, 0.00    
        pos_search_records = []
        pos_records = pos_obj.sudo().search(domain_default, order='date_order,name')
        if self.product_ids:
            for each in pos_records:
                for line in each.lines:
                    if self.product_ids and line.product_id.id not in product_ids:
                        continue
                    pos_search_records.append(line.order_id.id)
            pos_search_records = set(pos_search_records)
        else:
            for each in pos_records:
                pos_search_records.append(each.id)
                    
        if len(pos_records) < 1:
            raise UserError(_('There are no data matching this filter.Please try using different inputs.'))
            
        for each in pos_records:
            if each.id in pos_search_records: 
                row += 1
                s_no += 1
                discount_total += each.amount_discount and each.amount_discount or 0.00
                untaxed_total += each.amount_untaxed and each.amount_untaxed or 0.00
                tax_total += each.amount_tax and each.amount_tax or 0.00
                roundoff_total += each.amount_roundoff and each.amount_roundoff or 0.00
                total_amount_total += each.amount_total and each.amount_total or 0.00
                payment_received_total += sum(x.amount for x in each.payment_ids)
                
                sheet1.write(row, 0, s_no, Style.normal_left())
                sheet1.write(row, 1, each.amount_untaxed >= 0.00 and 'POS Regular' or 'POS Refund', Style.normal_left())
                sheet1.write(row, 2, (each.session_id.config_id.warehouse_id and each.session_id.config_id.warehouse_id.name or ''), Style.normal_left())
                sheet1.write(row, 3, each.name, Style.normal_left())
                date_order_str = each.date_order.strftime('%Y-%m-%d %H:%M:%S')
                date_order = time.strptime(date_order_str, "%Y-%m-%d %H:%M:%S")
                date_order = time.strftime('%d-%m-%Y', date_order)
                sheet1.write(row, 4, date_order, Style.normal_left())
                partner_name = ""
                partner_name = (each.partner_id and each.partner_id.name or "") + " - " + (each.partner_name and each.partner_name or "")
                sheet1.write(row, 5, partner_name, Style.normal_left())
                sheet1.write(row, 6, (each.partner_address and each.partner_address or ""), Style.normal_left())
                sheet1.write(row, 7, (each.user_id and each.user_id.name or ""), Style.normal_left())
                sheet1.write(row, 8, (each.partner_id.sales_manager_id.partner_id and each.partner_id.sales_manager_id.partner_id.name or ''), Style.normal_left())
                sheet1.write(row, 9, (each.user_id and each.user_id.name or ""), Style.normal_left())
                sheet1.write(row, 10, (each.sale_journal and each.sale_journal.name or ""), Style.normal_left())
                sheet1.write(row, 11, (each.session_id and each.session_id.name or ""), Style.normal_left())
                sheet1.write(row, 12, (each.partner_id.region_id and each.partner_id.region_id.name or ''), Style.normal_left())
                sheet1.write(row, 13, (each.partner_id.area_id and each.partner_id.area_id.name or ''), Style.normal_left())
                sheet1.write(row, 14, (each.partner_id.country_id and each.partner_id.country_id.name or ''), Style.normal_left())
                sheet1.write(row, 15, (each.pricelist_id.currency_id and each.pricelist_id.currency_id.name or ''), Style.normal_left())
                sheet1.write(row, 16, (each.amount_discount and each.amount_discount or 0.00), Style.normal_num_right_3separator())
                sheet1.write(row, 17, (each.amount_untaxed and each.amount_untaxed or 0.00), Style.normal_num_right_3separator())
                sheet1.write(row, 18, (each.amount_tax and each.amount_tax or 0.00), Style.normal_num_right_3separator())
                sheet1.write(row, 19,(each.amount_roundoff and each.amount_roundoff or 0.00), Style.normal_num_right_3separator())
                sheet1.write(row, 20, (each.amount_total and each.amount_total or 0.00), Style.normal_num_right_3separator())
                sheet1.write(row, 21, (sum(x.amount for x in each.payment_ids)), Style.normal_num_right_3separator())
                if each.state == 'invoiced':
                    sheet1.write(row, 22, "Invoiced", Style.normal_left())
                elif each.state == 'paid':
                    sheet1.write(row, 22, "Paid", Style.normal_left())
                else:
                    sheet1.write(row, 22, "Posted", Style.normal_left())
                for eachline in each.lines:
                    if self.product_ids and eachline.product_id.id not in product_ids:
                        continue
                    sheet1.write(row, 23, (eachline.product_id.name_get()[0][1]), Style.normal_left())
                    sheet1.write(row, 24, (eachline.qty and eachline.qty or 0.00), Style.normal_num_right_3digits())
                    sheet1.write(row, 25, (eachline.product_id.uom_id and eachline.product_id.uom_id.name or ''), Style.normal_left())
                    sheet1.write(row, 26, (eachline.price_unit and eachline.price_unit or 0.00), Style.normal_num_right_3digits())
                    sheet1.write(row, 27, (eachline.discount and eachline.discount or 0.00), Style.normal_num_right())
                    sheet1.write(row, 28, (eachline.price_subtotal_incl_company_currency - eachline.price_subtotal_company_currency), Style.normal_num_right_3separator())
                    sheet1.write(row, 29, (eachline.price_subtotal_company_currency), Style.normal_num_right_3separator())
                    sheet1.write(row, 30, (eachline.price_subtotal_incl_company_currency), Style.normal_num_right_3separator())
                    total_with_tax += eachline.price_subtotal_incl_company_currency
                    total_without_tax += eachline.price_subtotal_company_currency  
                    row += 1
                row -= 1
        row += 1
        if not self.product_ids:
            sheet1.write_merge(row, row, 0, 15, 'Total', Style.normal_right_ice_blue())
            sheet1.write(row, 16, discount_total, Style.normal_right_ice_blue_num())
            sheet1.write(row, 17, untaxed_total, Style.normal_right_ice_blue_num())
            sheet1.write(row, 18, tax_total, Style.normal_right_ice_blue_num())
            sheet1.write(row, 19, roundoff_total, Style.normal_right_ice_blue_num())
            sheet1.write(row, 20, total_amount_total, Style.normal_right_ice_blue_num())
            sheet1.write(row, 21, payment_received_total, Style.normal_right_ice_blue_num())
        else:
            sheet1.write_merge(row, row, 23, 28, 'Total', Style.normal_right_ice_blue())
            sheet1.write(row, 29, total_without_tax, Style.normal_right_ice_blue_num())
            sheet1.write(row, 30, total_with_tax, Style.normal_right_ice_blue_num())
            
        stream = BytesIO()
        wbk.save(stream)

        self.write({'name': report_name+'.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'pos.invoice.sale.register.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
        
