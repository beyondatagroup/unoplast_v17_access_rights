# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
# from excel_styles import ExcelStyles
from odoo.addons.ebits_custom_sale.wizard.excel_styles import ExcelStyles
from odoo.exceptions import UserError
import xlwt
from io import BytesIO
import base64
import xlrd
# import parser
import json
from lxml import etree


class SaleRegisterReportWizard(models.TransientModel):
    _name = "sale.register.report.wizard"
    _description = "Sale Register Report Wizard"

    date_from = fields.Date(string='From Date (Invoice Date)', required=True)
    date_to = fields.Date(string='To Date (Invoice Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'sale_register_partner', 'sale_wizard_id', 'res_partner_id',
                                   string='Customer')
    country_ids = fields.Many2many('res.country', 'sale_register_country', 'sale_wizard_id', 'res_country_id',
                                   string='Country')
    area_ids = fields.Many2many('res.state.area', 'sale_register_area', 'sale_wizard_id', 'res_state_area_id',
                                string='Area')
    region_ids = fields.Many2many('res.state.region', 'sale_register_region', 'sale_wizard_id', 'res_state_region_id',
                                  string='Region')
    user_ids = fields.Many2many('res.users', 'sale_register_user', 'sale_register_wizard_id', 'res_users_id',
                                string='Sales Manager')
    currency_ids = fields.Many2many('res.currency', 'sale_register_currency', 'sale_register_wizard_id',
                                    'res_currency_id', string='Currency')
    warehouse_ids = fields.Many2many('stock.warehouse', 'sale_register_warehouse', 'sale_register_wizard_id',
                                     'warehouse_id', string='Warehouse')
    type_account = fields.Selection([('out_invoice', 'Regular'), ('out_refund', 'Refund')], string='Type')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='Format', readonly=True)
    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env['res.company']._company_default_get(
                                     'sale.register.report.wizard'))

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(SaleRegisterReportWizard, self).fields_view_get(
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
            raise UserError(_("Invalid Date Range.Try Using Different Values"))
        date_from = self.date_from
        date_to = self.date_to
        pos_order_obj = self.env['pos.order']
        invoice_obj = self.env['account.move']
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
        country_sql = """ """
        partner_sql = """ """
        region_sql = """ """
        area_sql = """ """
        manager_user_sql = """ """
        currency_sql = """ """
        warehouse_sql = """ """
        type_sql = """ """
        pos_sql = """ """
        filters = "Filtered Based On: Invoice Date | Invoice State (Includes Open And Paid State Only)"
        if self.partner_ids:
            for each_id in self.partner_ids:
                partner_ids.append(each_id.id)
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search(
                    [('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id]
                customer_list.append(each_id.name)
            customer_list = list(set(customer_list))
            customer_str = str(customer_list).replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
            if len(all_partner_ids) > 1:
                all_partner_ids = tuple(all_partner_ids)
                partner_sql += " and rp.id in " + str(all_partner_ids)
            else:
                partner_sql += " and rp.id  = " + str(all_partner_ids[0])
            filters += " | Customer:" + customer_str

        if self.country_ids:
            for each_id in self.country_ids:
                country_ids.append(each_id.id)
                country_list.append(each_id.name)
            country_list = list(set(country_list))
            country_str = str(country_list).replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
            if len(country_ids) > 1:
                country_sql += " and country.id in " + str(tuple(self.country_ids))
            else:
                country_sql += " and country.id = " + str(country_ids[0])
            filters += " | Country: " + country_str
        if self.area_ids:
            for each_id in self.area_ids:
                area_ids.append(each_id.id)
                area_list.append(each_id.name)
            area_list = list(set(area_list))
            area_str = str(area_list).replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
            if len(area_ids) > 1:
                area_sql += " and area.id in " + str(tuple(area_ids))
            else:
                area_sql += " and area.id  = " + str(area_ids[0])
            filters += " | Area: " + area_str
        if self.region_ids:
            for each_id in self.region_ids:
                region_ids.append(each_id.id)
                region_list.append(each_id.name)
            region_list = list(set(region_list))
            region_str = str(region_list).replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
            if len(region_ids) > 1:
                region_sql += " and region.id in " + str(tuple(region_ids))
            else:
                region_sql += " and region.id = " + str(region_ids[0])
            filters += " | Region: " + region_str
        if self.user_ids:
            for each_id in self.user_ids:
                user_ids.append(each_id.id)
                manager_list.append(each_id.partner_id.name)
            manager_list = list(set(manager_list))
            manager_str = str(manager_list).replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
            if len(user_ids) > 1:
                manager_user_sql += "and ser.id in " + str(tuple(user_ids))
            else:
                manager_user_sql += "and ser.id =" + str(user_ids[0])
            filters += " | Sales Manager: " + manager_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
            if len(currency_ids) > 1:
                currency_sql += "and curr.id in " + str(tuple(currency_ids))
            else:
                currency_sql += "and curr.id = " + str(currency_ids[0])
            filters += " | Currency: " + currency_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and wh.id in " + str(tuple(warehouse_ids))
            # else:
            #     #warehouse_sql += "and wh.id = "+ str(warehouse_ids[0])
            filters += " | Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each_id in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each_id.id)
                    warehouse_list.append(each_id.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
                if len(warehouse_ids) > 1:
                    warehouse_sql += "and wh.id in " + str(tuple(warehouse_ids))
                # else:
                #     #warehouse_sql += "and wh.id = "+ str(warehouse_ids[0])
                filters += " | Warehouse: " + warehouse_str
        if self.type_account:
            type_sql += "and inv.move_type = " + "'" + str(self.type_account) + "'"
            if self.type_account == 'out_invoice':
                pos_sql += "and pos.amount_untaxed_company_currency >= 0.00 "
                filters += ", Type : Regular"
            if self.type_account == 'out_refund':
                pos_sql += "and pos.amount_untaxed_company_currency < 0.00 "
                filters += ", Type : Refund"
        report_name = ""
        report_name = "Sale Register"
        sql = """select * from ((select
                    rp.name as customer_name,
                    rp.partner_code as customer_code,
                    rp.vat as tin,
                    rp.vrn_no as vrn_no,
                    rp.business_no as business_no,
                    inv.name as invoice_number,
                    inv.invoice_date as invoice_date,
                    curr.name as invoice_currency,
                    manager.name as sales_manager,
                    so.name as sale_order_no,
                    ((so.date_order at time zone %s)::timestamp::date) as sale_order_date,
                    region.name as region,
                    area.name as area,
                    country.name as country,
                    wh.name as delivery_warehouse,
                    inv.move_type as query_type,
                    payment.name as payment_term,
                    inv.invoice_date_due as payment_due_date,
                    so.client_order_ref as customer_reference,
                    analytic.name as analytic_account,
                    inv.company_amount_untaxed as amount,
                    inv.state,
                    inv.id
                from account_move inv
                    left join res_partner rp on (rp.id = inv.partner_id)
                    left join res_currency curr on (curr.id = inv.currency_id)
                    left join sale_order so on (so.id = inv.sale_order_id)
                    left join res_state_region region on (region.id = rp.region_id)
                    left join res_state_area area on (area.id = rp.area_id)
                    left join res_country country on (country.id = rp.country_id)
                    left join stock_warehouse wh on (wh.id = inv.warehouse_id)
                    left join account_payment_term payment on (payment.id = inv.invoice_payment_term_id)
                    left join account_analytic_account analytic on (analytic.id = so.analytic_account_id)
                    left join res_users ser on (ser.id = inv.sales_manager_id)
                    left join res_partner manager on (manager.id = ser.partner_id)
                where 
                    inv.state_1 in ('open', 'paid')
                    and inv.move_type in ('out_invoice', 'out_refund')
                    and inv.invoice_date >= %s and inv.invoice_date <= %s""" + country_sql + partner_sql + area_sql + region_sql + manager_user_sql + currency_sql + warehouse_sql + type_sql + """
                group by
                    inv.invoice_date,
                    rp.name,
                    rp.partner_code,
                    curr.name,
                    rp.vat,
                    rp.vrn_no,
                    rp.business_no,
                    inv.name,
                    inv.move_type,
                    so.name,
                    sale_order_date,
                    region.name,
                    area.name,
                    country.name,
                    wh.name,
                    payment.name,
                    payment_due_date,
                    so.client_order_ref,
                    analytic.name,
                    inv.state,
                    manager.name,
                    inv.id
                order by
                    inv.move_type,
                    wh.name,
                    inv.invoice_date)                   

                    UNION             

                (select 
                    (case when pos.partner_name is not null then concat(rp.name, ' - ', pos.partner_name) else rp.name end) customer_name,
                    rp.partner_code as customer_code,
                    rp.vat as tin,
                    rp.vrn_no as vrn_no,
                    rp.business_no as business_no,
                    pos.name as invoice_number,
                    ((pos.date_order at time zone %s)::timestamp::date) as invoice_date,
                    curr.name as invoice_currency,
                    manager.name as sales_manager,
                    pos.pos_reference as sale_order_no,
                    ((pos.date_order at time zone %s)::timestamp::date) as sale_order_date,
                    region.name as region,
                    area.name as area,
                    country.name as country,
                    wh.name as delivery_warehouse,
                    (case when pos.amount_untaxed_company_currency >= 0.00 then 'out_pos' else 'out_ref' end) as query_type,
                    null as payment_term,
                    null as payment_due_date,
                    null as customer_reference,
                    null as analytic_account,
                    pos.amount_untaxed_company_currency as amount,
                    pos.state,
                    pos.id
                from 
                    pos_order pos
                         left join res_partner rp on (rp.id=pos.partner_id)
                         left join pos_order_line pol on (pol.order_id = pos.id)
                         left join product_pricelist price on (price.id = pos.pricelist_id)
                         left join res_currency curr on (curr.id = price.currency_id)
                         left join res_state_region region on (region.id = rp.region_id)
                         left join res_state_area area on (area.id = rp.area_id)
                         left join res_country country on (country.id = rp.country_id)
                         left join pos_session session on (session.id = pos.session_id)
                         left join pos_config config on (config.id = session.config_id)
                         left join stock_warehouse wh on (wh.id = config.warehouse_id)
                         left join res_users ser on (ser.id = rp.sales_manager_id)
                         left join res_partner manager on (manager.id = ser.partner_id)
                     where 
                        pos.state in ('invoiced', 'paid', 'done')
                        and ((pos.date_order at time zone %s)::timestamp::date) >= %s and ((pos.date_order at time zone %s)::timestamp::date) <= %s""" + country_sql + partner_sql + area_sql + region_sql + manager_user_sql + currency_sql + warehouse_sql + pos_sql + """
                    order by
                        wh.name,
                        pos.date_order
                    )) x
                    order by
                        x.query_type, x.delivery_warehouse, x.invoice_number, x.invoice_date"""
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(sql, (tz, date_from, date_to, tz, tz, tz, date_from, tz, date_to,))
        t = self.env.cr.dictfetchall()
        if len(t) == 0:
            raise UserError(_("No Records available on these Filter.Try  Using Different Values"))
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 5500
        sheet1.col(3).width = 5500
        sheet1.col(4).width = 4500
        sheet1.col(5).width = 3500
        sheet1.col(6).width = 5500
        sheet1.col(7).width = 5500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 3500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 4500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500
        sheet1.col(18).width = 3500
        sheet1.col(19).width = 3500
        sheet1.col(20).width = 3500
        sheet1.col(21).width = 4500
        sheet1.col(22).width = 3500
        sheet1.col(23).width = 3500
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
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)
        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        title = report_name + " ( Date from " + from_date + " to " + to_date + " )"
        sheet1.write_merge(rc, rc, 0, 30, self.company_id.name, Style.title_ice_blue())
        sheet1.write_merge(r1, r1, 0, 30, title, Style.title_ice_blue())
        sheet1.write_merge(r2, r2, 0, 10, filters, Style.groupByTitle())
        sheet1.write_merge(r2, r2, 11, 16, 'Invoice Currency', Style.groupByTitle())
        sheet1.write_merge(r2, r2, 17, 20, 'Local Currency', Style.groupByTitle())

        sheet1.write(r3, 0, "S.No", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 1, "Sale Type", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 2, "Warehouse", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 3, "Account", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 4, "Invoice Number", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 5, "Invoice Date", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 6, "Customer", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 7, "Sales Manager", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 8, "Region", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 9, "Area", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 10, "Country", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 11, "Invoice Currency", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 12, "Untaxed Amount", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 13, "Tax Amount", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 14, "Tax %", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 15, "Total Amount", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 16, "Payment Due Amount", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 17, "Untaxed Amount", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 18, "Tax Amount", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 19, "Total Amount", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 20, "Payment Due Amount", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 21, "Sale Order No", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 22, "Sale Order Date", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 23, "Customer Reference", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 24, "Payment Term", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 25, "Payment Due Date", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 26, "TIN", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 27, "VAT", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 28, "Business No", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 29, "Analytic Account", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 30, "Status", Style.contentTextBold(2, 'black', 'white'))
        row = 3
        s_no = 0
        due_amount_subtotal_lc = 0.00
        reg_untaxed, reg_taxed, reg_total, reg_residual = 0.00, 0.00, 0.00, 0.00
        ref_untaxed, ref_taxed, ref_total, ref_residual = 0.00, 0.00, 0.00, 0.00
        subtotal_row = 0
        for each in t:
            print('>>>>>>>>>>------------->>>>>>>>>>>>>>', each)
            country_info = each.get('country')
            payment_term = each.get('payment_term')
            if country_info is not None and 'en_US' in country_info:
                country_name = country_info['en_US']
            else:
                country_name = 'Unknown'

            if payment_term is not None and 'en_US' in payment_term:
                payment_term_name = payment_term['en_US']
            else:
                payment_term_name = 'Unknown'

            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 450
            sheet1.write(row, 0, s_no, Style.normal_left())
            if each['query_type'] == 'out_invoice':
                sheet1.write(row, 1, 'Regular', Style.normal_left())
            elif each['query_type'] == 'out_refund':
                sheet1.write(row, 1, 'Invoice Refund', Style.normal_left())
            elif each['query_type'] == 'out_pos':
                sheet1.write(row, 1, 'POS', Style.normal_left())
            elif each['query_type'] == 'out_ref':
                sheet1.write(row, 1, 'POS Refund', Style.normal_left())
            sheet1.write(row, 2, each['delivery_warehouse'], Style.normal_left())
            sheet1.write(row, 4, each['invoice_number'], Style.normal_left())
            invoice_date_str = each['invoice_date'].strftime('%Y-%m-%d')
            invoice_date = time.strptime(invoice_date_str, "%Y-%m-%d")
            invoice_date = time.strftime("%d-%m-%Y", invoice_date)
            sheet1.write(row, 5, invoice_date, Style.normal_left())
            sheet1.write(row, 6, each['customer_name'], Style.normal_left())
            sheet1.write(row, 7, each['sales_manager'], Style.normal_left())
            sheet1.write(row, 8, each['region']['en_US'], Style.normal_left())
            sheet1.write(row, 9, each['area']['en_US'], Style.normal_left())
            sheet1.write(row, 10, country_name, Style.normal_left())
            sheet1.write(row, 11, each['invoice_currency'], Style.normal_left())
            if each['query_type'] not in ('out_pos', 'out_ref'):
                inv_browse = invoice_obj.sudo().browse(each['id'])
                tax_des = []
                account_des = []
                for each_line in inv_browse.invoice_line_ids:
                    if each_line.account_id.account_type == 'income':
                        account_des.append(each_line.account_id.name)
                    for tax_id in each_line.tax_ids:
                        print('>>>>>>>>>>>>>>>>>>>>>',tax_id)
                        tax_des.append(tax_id.name)
                tax_des = list(set(tax_des))
                account_des = list(set(account_des))
                tax_percentage = ""
                account_ref = ""
                if tax_des:
                    tax_des = str(tax_des)
                    tax_percentage = tax_des.replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
                if account_des:
                    account_des = str(account_des)
                    account_ref = account_des.replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
                sheet1.write(row, 3, account_ref, Style.normal_left())
                if each['query_type'] == 'out_refund':
                    sheet1.write(row, 12, (-1 * inv_browse.amount_untaxed), Style.normal_num_right_3separator())
                    sheet1.write(row, 13, (-1 * inv_browse.amount_tax), Style.normal_num_right_3separator())
                    sheet1.write(row, 14, tax_percentage, Style.normal_left())
                    sheet1.write(row, 15, (-1 * inv_browse.amount_total), Style.normal_num_right_3separator())
                    sheet1.write(row, 16, (-1 * inv_browse.residual), Style.normal_num_right_3separator())
                    sheet1.write(row, 17, (-1 * inv_browse.company_amount_untaxed),
                                 Style.normal_num_right_3separator())
                    sheet1.write(row, 18, (-1 * inv_browse.company_amount_tax),
                                 Style.normal_num_right_3separator())
                    sheet1.write(row, 19, (-1 * inv_browse.company_amount_total),
                                 Style.normal_num_right_3separator())
                    sheet1.write(row, 20, (-1 * inv_browse.residual_company_currency),
                                 Style.normal_num_right_3separator())
                    ref_untaxed += (-1 * inv_browse.company_amount_untaxed)
                    ref_taxed += (-1 * inv_browse.company_amount_tax)
                    ref_total += (-1 * inv_browse.company_amount_total)
                    ref_residual += (-1 * inv_browse.residual_company_currency)
                else:
                    sheet1.write(row, 12, inv_browse.amount_untaxed, Style.normal_num_right_3separator())
                    sheet1.write(row, 13, inv_browse.amount_tax, Style.normal_num_right_3separator())
                    sheet1.write(row, 14, tax_percentage, Style.normal_left())
                    sheet1.write(row, 15, inv_browse.amount_total, Style.normal_num_right_3separator())
                    sheet1.write(row, 16, inv_browse.residual, Style.normal_num_right_3separator())
                    sheet1.write(row, 17, inv_browse.company_amount_untaxed,
                                 Style.normal_num_right_3separator())
                    sheet1.write(row, 18, inv_browse.company_amount_tax, Style.normal_num_right_3separator())
                    sheet1.write(row, 19, inv_browse.company_amount_total, Style.normal_num_right_3separator())
                    sheet1.write(row, 20, inv_browse.residual_company_currency, Style.normal_num_right_3separator())
                    reg_untaxed += inv_browse.company_amount_untaxed
                    reg_taxed += inv_browse.company_amount_tax
                    reg_total += inv_browse.company_amount_total
                    reg_residual += inv_browse.residual_company_currency
                subtotal_row = row
            else:
                pos_browse = pos_order_obj.sudo().browse(each['id'])
                tax_des = []
                account_des = []
                for each_move_line in pos_browse.account_move.line_ids:
                    if each_move_line.account_id.account_type == 'income':
                        account_des.append(each_move_line.account_id.name)
                for each_line in pos_browse.lines:
                    for tax_id in each_line.tax_ids:
                        tax_des.append(tax_id.name)
                tax_des = list(set(tax_des))
                account_des = list(set(account_des))
                tax_percentage = ""
                account_ref = ""
                if tax_des:
                    tax_des = str(tax_des)
                    tax_percentage = tax_des.replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
                if account_des:
                    account_des = str(account_des)
                    account_ref = account_des.replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
                sheet1.write(row, 3, account_ref, Style.normal_left())
                sheet1.write(row, 12, pos_browse.amount_untaxed, Style.normal_num_right_3separator())
                sheet1.write(row, 13, pos_browse.amount_tax, Style.normal_num_right_3separator())
                sheet1.write(row, 14, tax_percentage, Style.normal_left())
                sheet1.write(row, 15, pos_browse.amount_total, Style.normal_num_right_3separator())
                sheet1.write(row, 16, 0.00, Style.normal_num_right_3separator())
                sheet1.write(row, 17, pos_browse.amount_untaxed_company_currency, Style.normal_num_right_3separator())
                sheet1.write(row, 18, pos_browse.amount_tax_company_currency, Style.normal_num_right_3separator())
                sheet1.write(row, 19, pos_browse.amount_total_company_currency, Style.normal_num_right_3separator())
                sheet1.write(row, 20, 0.00, Style.normal_num_right_3separator())
                if pos_browse.amount_untaxed_company_currency >= 0.00:
                    reg_untaxed += pos_browse.amount_untaxed_company_currency
                    reg_taxed += pos_browse.amount_tax_company_currency
                    reg_total += pos_browse.amount_total_company_currency
                else:
                    ref_untaxed += pos_browse.amount_untaxed_company_currency
                    ref_taxed += pos_browse.amount_tax_company_currency
                    ref_total += pos_browse.amount_total_company_currency
                subtotal_row = row
            sheet1.write(row, 21, each['sale_order_no'], Style.normal_left())
            if each['sale_order_date']:
                sale_order_date_str = each['sale_order_date'].strftime('%Y-%m-%d')
                sale_order_date = time.strptime(sale_order_date_str, "%Y-%m-%d")
                sale_order_date = time.strftime("%d-%m-%Y", sale_order_date)
                sheet1.write(row, 22, sale_order_date, Style.normal_left())
            else:
                sheet1.write(row, 22, "", Style.normal_left())
            sheet1.write(row, 23, each['customer_reference'], Style.normal_left())
            sheet1.write(row, 24, payment_term_name, Style.normal_left())
            if each['payment_due_date']:
                payment_due_date_str = each['payment_due_date'].strftime('%Y-%m-%d')
                payment_due_date = time.strptime(payment_due_date_str, "%Y-%m-%d")
                payment_due_date = time.strftime("%d-%m-%Y", payment_due_date)
                sheet1.write(row, 25, payment_due_date, Style.normal_left())
            else:
                sheet1.write(row, 25, "", Style.normal_left())
            sheet1.write(row, 26, each['tin'], Style.normal_left())
            sheet1.write(row, 27, each['vrn_no'], Style.normal_left())
            sheet1.write(row, 28, each['business_no'], Style.normal_left())
            sheet1.write(row, 29, each['analytic_account'], Style.normal_left())
            if each['state'] == 'open':
                sheet1.write(row, 30, 'Open', Style.normal_left())
            elif each['state'] == 'paid':
                sheet1.write(row, 30, 'Paid', Style.normal_left())
            else:
                sheet1.write(row, 30, 'Done', Style.normal_left())

        if self.type_account == 'out_invoice' or self.type_account == False:
            subtotal_row += 1
            sheet1.write_merge(subtotal_row, subtotal_row, 0, 16, "Regular Total", Style.normal_left_ice_blue())
            sheet1.write(subtotal_row, 17, reg_untaxed, Style.normal_right_ice_blue())
            sheet1.write(subtotal_row, 18, reg_taxed, Style.normal_right_ice_blue())
            sheet1.write(subtotal_row, 19, reg_total, Style.normal_right_ice_blue())
            sheet1.write(subtotal_row, 20, reg_residual, Style.normal_right_ice_blue())
        if self.type_account == 'out_refund' or self.type_account == False:
            subtotal_row += 1
            sheet1.write_merge(subtotal_row, subtotal_row, 0, 16, "Refund Total", Style.normal_left_ice_blue())
            sheet1.write(subtotal_row, 17, ref_untaxed, Style.normal_right_ice_blue())
            sheet1.write(subtotal_row, 18, ref_taxed, Style.normal_right_ice_blue())
            sheet1.write(subtotal_row, 19, ref_total, Style.normal_right_ice_blue())
            sheet1.write(subtotal_row, 20, ref_residual, Style.normal_right_ice_blue())
        if self.type_account == False:
            subtotal_row += 1
            sheet1.write_merge(subtotal_row, subtotal_row, 0, 16, "Total", Style.normal_left_ice_blue())
            sheet1.write(subtotal_row, 17, (reg_untaxed + ref_untaxed), Style.normal_right_ice_blue())
            sheet1.write(subtotal_row, 18, (reg_taxed + ref_taxed), Style.normal_right_ice_blue())
            sheet1.write(subtotal_row, 19, (reg_total + ref_total), Style.normal_right_ice_blue())
            sheet1.write(subtotal_row, 20, (reg_residual + ref_residual), Style.normal_right_ice_blue())

        stream = BytesIO()
        wbk.save(stream)

        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
            'name': _("Notification"),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.register.report.wizard',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new'
        }
# commented as not in v17
# inv.amount_untaxed_company_currency as amount,
