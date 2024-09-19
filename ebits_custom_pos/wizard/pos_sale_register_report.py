# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.addons.ebits_custom_pos.wizard.excel_styles import ExcelStyles
import xlwt
import base64
from io import BytesIO
import xlrd
import json
from lxml import etree

class PosSaleRegisterReportWizard(models.TransientModel):
    _name = 'pos.sale.register.report.wizard'
    _description = 'Pos Sale Register Report Wizard'
    
    date_from = fields.Date(string='From Date(Invoice Date)', required=True)
    date_to = fields.Date(string='To Date(Invoice Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'pos_sale_register_partner', 'pos_sale_wizard_id', 'res_partner_id', string='Customer')
    create_user_ids = fields.Many2many('res.users', 'pos_sale_register_users', 'pos_sale_wizard_id', 'create_user_id', string = 'Created By')
    journal_ids = fields.Many2many('account.journal', 'pos_sale_register_journal', 'pos_sale_wizard_id', 'journal_id', string='Journal')
    country_ids = fields.Many2many('res.country', 'pos_sale_register_country', 'pos_sale_wizard_id', 'res_country_id', string='Country')
    area_ids = fields.Many2many('res.state.area','pos_sale_register_area', 'pos_sale_wizard_id', 'res_state_area_id', string='Area')
    region_ids = fields.Many2many('res.state.region', 'pos_sale_register_region', 'pos_sale_wizard_id', 'res_state_region_id', string='Region')
    user_ids = fields.Many2many('res.users', 'pos_sale_register_user', 'pos_sale_register_wizard_id', 'res_users_id', string='Sales Manager')
    currency_ids = fields.Many2many('res.currency', 'pos_sale_register_currency', 'pos_sale_register_wizard_id', 'res_currency_id', string='Currency')
    warehouse_ids = fields.Many2many('stock.warehouse', 'pos_sale_register_warehouse', 'pos_sale_register_wizard_id', 'warehouse_id', string='Warehouse')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('pos.sale.register.report.wizard'))
    
    # @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PosSaleRegisterReportWizard, self).fields_view_get(
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
            raise UserError(_('Invalid Date Range.Try Using Different Values'))
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
        all_create_user_ids = []
        user_list = []
        user_str = ""
        all_journal_ids = []
        journal_list = []
        journal_str = ""
        country_sql = """ """
        partner_sql = """ """
        region_sql = """ """
        area_sql = """ """
        manager_user_sql = """ """
        currency_sql = """ """
        warehouse_sql = """ """
        user_sql = """ """
        journal_sql = """ """
        filters = "Filtered Based On: Invoice Date | Invoice State (Includes Open and Paid State Only)"
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
                partner_sql += " and rp.id in "+ str(all_partner_ids)
            else:
                partner_sql += " and rp.id in ("+ str(all_partner_ids[0]) + ")"
            filters += " | Customer:" + customer_str
                
        if self.country_ids:
            for each_id in self.country_ids:
                country_ids.append(each_id.id)
                country_list.append(each_id.name)
            country_list = list(set(country_list))
            country_str = str(country_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(country_ids) > 1:
                country_sql += " and country.id in "+ str(tuple(self.country_ids))
            else:
                country_sql += " and country.id in ("+ str(country_ids[0]) + ")"
            filters += " | Country: " + country_str
        if self.area_ids:
            for each_id in self.area_ids:
                area_ids.append(each_id.id)
                area_list.append(each_id.name)
            area_list = list(set(area_list))
            area_str = str(area_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(area_ids) > 1:
                area_sql += " and area.id in "+ str(tuple(area_ids))
            else:
                area_sql += " and area.id in ("+ str(area_ids[0]) + ")"
            filters += " | Area: " + area_str
        if self.region_ids:
            for each_id in self.region_ids:
                region_ids.append(each_id.id)
                region_list.append(each_id.name)
            region_list = list(set(region_list))
            region_str = str(region_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(region_ids) > 1:
                region_sql += " and region.id in "+ str(tuple(region_ids))
            else:
                region_sql += " and region.id in ("+ str(region_ids[0]) + ")"
            filters += " | Region: " + region_str
        if self.user_ids:
            for each_id in self.user_ids:
                user_ids.append(each_id.id)
                manager_list.append(each_id.partner_id.name)
            manager_list = list(set(manager_list))
            manager_str = str(manager_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(user_ids) > 1:
                manager_user_sql += "and rp.sales_manager_id in " + str(tuple(user_ids))
            else:
                manager_user_sql += "and rp.sales_manager_id in (" + str(user_ids[0]) + ")" 
            filters += " | Sales Manager: " + manager_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(currency_ids) > 1:
                currency_sql += "and curr.id in "+ str(tuple(currency_ids))
            else:
                currency_sql += "and curr.id in ("+ str(currency_ids[0]) + ")"
            filters += " | Currency: " + currency_str
        if self.create_user_ids:
            for each_id in self.create_user_ids:
                all_create_user_ids.append(each_id.id)
                user_list.append(each_id.name)
            user_list = list(set(user_list))
            user_str = str(user_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_create_user_ids) > 1:
                user_sql += "and pos.user_id in "+ str(tuple(all_create_user_ids))
            else:
                user_sql += "and pos.user_id in ("+ str(all_create_user_ids[0]) + ")"
            filters += " | Created By: " + user_str
        if self.journal_ids:
            for each_id in self.journal_ids:
                all_journal_ids.append(each_id.id)
                journal_list.append(each_id.name)
            journal_list = list(set(journal_list))
            journal_str = str(journal_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_journal_ids) > 1:
                journal_sql += "and aj.id in "+ str(tuple(all_journal_ids))
            else:
                journal_sql += "and aj.id in ("+ str(all_journal_ids[0]) + ")"
            filters += " | Journal: " + journal_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and wh.id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and wh.id in ("+ str(warehouse_ids[0]) + ")"
            filters += " | Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each_id in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each_id.id)
                    warehouse_list.append(each_id.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")    
                if len(warehouse_ids) > 1:
                    warehouse_sql += "and wh.id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += "and wh.id in ("+ str(warehouse_ids[0]) + ")"
                filters += " | Warehouse: " + warehouse_str
        report_name = ""
        report_name = "POS Sale Register"
        sql = """   select 
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
                        wh.name as warehouse,
                        pos.amount_untaxed_company_currency as amount_untaxed,
                        pos.state,
                        pos.partner_address as address,
                        rpa.name as creator,
                        aj.name as journal,
                        session.name as reference,
                        pos.id
                    from pos_order pos
                         left join res_partner rp on (rp.id=pos.partner_id)
                         left join product_pricelist price on (price.id = pos.pricelist_id)
                         left join res_currency curr on (curr.id=price.currency_id)
                         left join res_state_region region on (region.id=rp.region_id)
                         left join res_state_area area on (area.id=rp.area_id)
                         left join res_country country on (country.id=rp.country_id)
                         left join pos_session session on (session.id = pos.session_id)
                         left join pos_config config on (config.id = session.config_id)
                         left join stock_warehouse wh on (wh.id = config.warehouse_id)
                         left join res_users ser on (ser.id = rp.sales_manager_id)
                         left join res_partner manager on (manager.id = ser.partner_id)
                         left join res_users ru on (ru.id = pos.user_id)
                         left join res_partner rpa on (rpa.id = ru.partner_id)
                         left join account_journal aj on (aj.id = pos.sale_journal)
                     where 
                        pos.state in ('invoiced', 'paid', 'done')
                        and ((pos.date_order at time zone %s)::timestamp::date) >= %s and ((pos.date_order at time zone %s)::timestamp::date) <= %s""" + country_sql + partner_sql + area_sql + region_sql + manager_user_sql + currency_sql + warehouse_sql + user_sql + journal_sql +"""
                    group by
                        pos.id,
                        rp.name,
                        pos.partner_name,
                        rp.partner_code,
                        rp.vat,
                        rp.vrn_no,
                        rp.business_no,
                        pos.name,
                        ((pos.date_order)::timestamp::date),
                        curr.name,
                        manager.name,
                        pos.pos_reference,
                        ((pos.date_order)::timestamp::date),
                        region.name,
                        area.name,
                        country.name,
                        wh.name,
                        pos.amount_untaxed_company_currency,
                        pos.state,
                        pos.partner_address,
                        rpa.name,
                        aj.name,
                        session.name
                    order by
                        wh.name,
                        pos.name,
                        pos.date_order
                    """
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(sql , ( tz, tz, tz, date_from, tz, date_to, ))
        t = self.env.cr.dictfetchall()
        print('>>>>>>>>>>>tttttttttttttttttttt>>>>>>>>>>>>>>',t)
        if len(t) == 0:
            raise UserError(_('No Records available on these Filter.Try  Using Different Values'))
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 5000
        sheet1.col(3).width = 4500
        sheet1.col(4).width = 4500
        sheet1.col(5).width = 7500
        sheet1.col(6).width = 9500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 6500
        sheet1.col(11).width = 6500
        sheet1.col(12).width = 6500
        sheet1.col(13).width = 6500
        sheet1.col(14).width = 4500
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500
        sheet1.col(18).width = 3500
        sheet1.col(19).width = 3500
        sheet1.col(20).width = 4500
        sheet1.col(21).width = 3500
        sheet1.col(22).width = 3500
        sheet1.col(23).width = 3500
        sheet1.col(24).width = 3500
#        sheet1.col(25).width = 3500
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
        sheet1.write_merge(rc, rc, 0, 24, self.company_id.name, Style.title_ice_blue())
        sheet1.write_merge(r1, r1, 0, 24, title, Style.title_ice_blue())
        sheet1.write_merge(r2, r2, 0, 24, filters, Style.groupByTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 1, "Sale Type", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 2, "Warehouse", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 3, "Invoice Number", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 4, "Invoice Date", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 5, "Customer", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 6, "Customer Address", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 7, "Created By", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 8, "Sales Manager", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 9, "Sales Person", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 10, "Journal", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 11, "Reference", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 12, "Region", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 13, "Area", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 14, "Country", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 15, "Invoice Currency", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 16, "Discount Amount", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 17, "Untaxed Amount", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 18, "Tax Amount", Style.contentTextBold(2,'black','white'))
#        sheet1.write(r3, 19, "Tax %", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 19, "Round Off Amount", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 20, "Total Amount", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 21, "TIN", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 22, "VAT", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 23, "Business No", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 24, "Status", Style.contentTextBold(2,'black','white'))
        row = 3
        s_no = 0
        untaxed_amount_subtotal_inv = 0.00
        tax_amount_subtotal_inv = 0.00
        total_amount_subtotal_inv = 0.00
        amount_discount_subtotal_inv = 0.00
        amount_roundoff_subtotal_inv = 0.00
        subtotal_row = 0
        for each in t:
            region = each.get('region')
            if region is not None and 'en_US' in region:
                requested_region = region['en_US']
            else:
                requested_region = ' '

            area = each.get('area')
            if area is not None and 'en_US' in area:
                requested_area = area['en_US']
            else:
                requested_area = ' '

            country = each.get('country')
            if country is not None and 'en_US' in country:
                requested_country = country['en_US']
            else:
                requested_country = ' '

            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 450
            pos_browse = pos_order_obj.sudo().browse(each['id'])
            untaxed_amount = pos_browse.amount_untaxed
            tax_amount = pos_browse.amount_tax
            amount_discount = pos_browse.amount_discount
            amount_roundoff = pos_browse.amount_roundoff
            total_amount = pos_browse.amount_total
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, pos_browse.amount_untaxed >= 0.00 and 'POS Regular' or 'POS Refund', Style.normal_left())
            sheet1.write(row, 2, each['warehouse'], Style.normal_left())
            sheet1.write(row, 3, each['invoice_number'], Style.normal_left())
            invoice_date_str = each['invoice_date'].strftime('%Y-%m-%d')
            invoice_date = time.strptime(invoice_date_str, "%Y-%m-%d")
            invoice_date = time.strftime('%d-%m-%Y', invoice_date)
            sheet1.write(row, 4, invoice_date, Style.normal_left())
            sheet1.write(row, 5, each['customer_name'], Style.normal_left())
            sheet1.write(row, 6, each['address'], Style.normal_left())
            sheet1.write(row, 7, each['creator'], Style.normal_left())
            sheet1.write(row, 8, each['sales_manager'], Style.normal_left())
            sheet1.write(row, 9, each['creator'], Style.normal_left())
            sheet1.write(row, 10, each['journal']['en_US'], Style.normal_left())
            sheet1.write(row, 11, each['reference'], Style.normal_left())
            sheet1.write(row, 12, requested_region, Style.normal_left())
            sheet1.write(row, 13, requested_area, Style.normal_left())
            sheet1.write(row, 14, requested_country, Style.normal_left())
            sheet1.write(row, 15, each['invoice_currency'], Style.normal_left())
#            tax_des = []
#            for each_line in pos_browse.lines:
#                for tax_id in each_line.tax_ids:
#                    tax_des.append(tax_id.description)
#            tax_des = list(set(tax_des))
#            tax_percentage = ""
#            if tax_des:
#                tax_des = str(tax_des)
#                tax_percentage = tax_des.replace('[', '').replace(']', '').replace("u'","").replace("'","")
            sheet1.write(row, 16, amount_discount, Style.normal_num_right_3separator())
            sheet1.write(row, 17, untaxed_amount, Style.normal_num_right_3separator())
            sheet1.write(row, 18, tax_amount, Style.normal_num_right_3separator())
#            sheet1.write(row, 19, tax_percentage, Style.normal_num_right())
            sheet1.write(row, 19, amount_roundoff, Style.normal_num_right_3separator())
            sheet1.write(row, 20, total_amount, Style.normal_num_right_3separator())
            
            sheet1.write(row, 21, (each['tin'] and each['tin'] or ""), Style.normal_left())
            sheet1.write(row, 22, (each['vrn_no'] and each['vrn_no'] or ""), Style.normal_left())
            sheet1.write(row, 23, (each['business_no'] and each['business_no'] or ""), Style.normal_left())
            if each['state'] == 'invoiced':
                sheet1.write(row, 24, 'Invoiced' , Style.normal_left())
            elif each['state'] == 'paid':
                sheet1.write(row, 24, 'Paid' , Style.normal_left())
            else:
                sheet1.write(row, 24, 'Posted' , Style.normal_left())
            
            amount_discount_subtotal_inv += amount_discount
            amount_roundoff_subtotal_inv += amount_roundoff
            untaxed_amount_subtotal_inv += untaxed_amount
            tax_amount_subtotal_inv += tax_amount
            total_amount_subtotal_inv += total_amount
            subtotal_row = row

        sheet1.write(subtotal_row + 1, 16, amount_discount_subtotal_inv , Style.normal_right_ice_blue_num())
        sheet1.write(subtotal_row + 1, 17, untaxed_amount_subtotal_inv , Style.normal_right_ice_blue_num())
        sheet1.write(subtotal_row + 1, 18, tax_amount_subtotal_inv , Style.normal_right_ice_blue_num())
        sheet1.write(subtotal_row + 1, 19, amount_roundoff_subtotal_inv , Style.normal_right_ice_blue_num())
        sheet1.write(subtotal_row + 1, 20, total_amount_subtotal_inv , Style.normal_right_ice_blue_num())
        
        stream = BytesIO()
        wbk.save(stream)

        self.write({'name': report_name+'.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'pos.sale.register.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }

