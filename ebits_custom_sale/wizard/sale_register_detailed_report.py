# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_sale.wizard.excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
import xlwt
from io import BytesIO
import base64
import xlrd
# import parser
import json
from lxml import etree

class SaleDetailedReportWizard(models.TransientModel):
    _name = 'sale.detailed.report.wizard'
    _description = "Sale Detailed Report Wizard"

    date_from = fields.Date(string='From Date (Invoice Date)', required=True)
    date_to = fields.Date(string='To Date (Invoice Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'sale_register_detail_partner', 'sale_wizard_id', 'res_partner_id', string='Customer')
    area_ids = fields.Many2many('res.state.area','sale_register_detail_area', 'sale_wizard_id', 'res_state_area_id', string='Area')
    region_ids = fields.Many2many('res.state.region', 'sale_register_detail_region', 'sale_wizard_id', 'res_state_region_id', string='Region')
    warehouse_ids = fields.Many2many('stock.warehouse', 'sale_register_detail_warehouse', 'sale_register_detail_wizard_id', 'warehouse_id', string='Warehouse')
    user_ids = fields.Many2many('res.users', 'sale_register_detail_user', 'sale_register_detail_wizard_id', 'res_users_id', string='Sales Manager')
    product_ids = fields.Many2many('product.product', 'sale_register_detail_product', 'sale_register_detail_wizard_id', 'product_id', string='Product')
    categ_ids = fields.Many2many('product.category', 'sale_register_detail_category', 'sale_register_detail_wizard_id', 'category_id', string='Product Category')
    sales_user_ids = fields.Many2many('res.users', 'sale_register_detail_res_users', 'sale_register_detail_wizard_id', 'res_users_id', string='Sales Person')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='Format', readonly=True)
    include_sales_person = fields.Boolean(string='Include Sales Person')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sale.detailed.report.wizard'))

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(SaleDetailedReportWizard, self).fields_view_get(
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
        if self.date_from > self.date_to:
            raise UserError(("Invalid date range.Try  Using Different Values"))
        inv_obj = self.env['account.move']
        pos_obj  = self.env['pos.order']
        date_from = self.date_from
        date_to = self.date_to
        sales_person_sql = """ """
        sales_person_join_sql = """ """
        sales_person_group_sql = """ """
        pos_sales_person_sql = """ """
        pos_sales_person_join_sql = """ """
        pos_sales_person_group_sql = """ """
        partner_sql = """ """
        region_sql = """ """
        area_sql = """ """
        manager_user_sql = """ """
        warehouse_sql = """ """
        sales_person_where_sql = """ """
        pos_sales_person_where_sql = """ """
        product_sql = """ """
        category_sql = """ """
        partner_ids = []
        customer_list = []
        customer_str = ""
        area_ids = []
        area_list = []
        area_str = ""
        category_ids = []
        category_list = []
        category_str = ""
        product_ids = []
        product_list = []
        product_str = ""
        region_ids = []
        region_list = []
        region_str = ""
        user_ids = []
        manager_list = []
        manager_str = ""
        sales_user_ids = []
        sp_list = []
        sp_str  = ""
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        all_partners_children = {}
        all_partner_ids = []
        sale_value_subtotal = 0.00
        filters = "Filtered Based On: Invoice Date"
        if self.partner_ids:
            for each_id in self.partner_ids:
                partner_ids.append(each_id.id)
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id]
                customer_list.append(each_id.name)
            customer_list = list(set(customer_list))
            customer_str = str(customer_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                all_partner_ids = tuple(all_partner_ids)
                partner_sql += " and rp.id in "+ str(all_partner_ids)
            else:
                partner_sql += " and rp.id ="+ str(all_partner_ids[0])
            filters += " | Customer:" + customer_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and wh.id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and wh.id = "+ str(warehouse_ids[0])
            filters += " | Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each_id in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each_id.id)
                    warehouse_list.append(each_id.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace("[","").replace("]","").replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += "and wh.id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += "and wh.id = "+ str(warehouse_ids[0])
                filters += " | Warehouse: " + warehouse_str
        if self.area_ids:
            for each_id in self.area_ids:
                area_ids.append(each_id.id)
                area_list.append(each_id.name)
            area_list = list(set(area_list))
            area_str = str(area_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(area_ids) > 1:
                area_sql += " and area.id in "+ str(tuple(area_ids))
            else:
                area_sql += " and area.id = "+ str(area_ids[0])
            filters += " | Area: " + area_str
        if self.region_ids:
            for each_id in self.region_ids:
                region_ids.append(each_id.id)
                region_list.append(each_id.name)
            region_list = list(set(region_list))
            region_str = str(region_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(region_ids) > 1:
                region_sql += " and region.id in "+ str(tuple(region_ids))
            else:
                region_sql += " and region.id = "+ str(region_ids[0])
            filters += " | Region: " + region_str
        if self.user_ids:
            for each_id in self.user_ids:
                user_ids.append(each_id.id)
                manager_list.append(each_id.partner_id.name)
            manager_list = list(set(manager_list))
            manager_str = str(manager_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(user_ids) > 1:
                manager_user_sql += "and ser.id in " + str(tuple(user_ids))
            else:
                manager_user_sql += "and ser.id = " + str(user_ids[0])
            filters += " | Sales Manager: " + manager_str
        if self.sales_user_ids:
            for each_id in self.sales_user_ids:
                sales_user_ids.append(each_id.id)
                sp_list.append(each_id.partner_id.name)
            sp_list = list(set(sp_list))
            sp_str = str(sp_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(sales_user_ids) > 1:
                sales_person_where_sql += "and invline.sales_user_id in " + str(tuple(sales_user_ids))
                pos_sales_person_where_sql += "and pos.user_id in " + str(tuple(sales_user_ids))
            else:
                sales_person_where_sql += "and invline.sales_user_id = " + str(sales_user_ids[0])
                pos_sales_person_where_sql += "and pos.user_id = " + str(sales_user_ids[0])
            filters += " | Sales Person: " + sp_str
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.product_tmpl_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(product_ids) > 1:
                product_sql += "and product.id in "+ str(tuple(product_ids))
            else:
                product_sql += "and product.id = "+ str(product_ids[0])
            filters += " | Product: " + product_str
        if self.categ_ids:
            for each_id in self.categ_ids:
                category_ids.append(each_id.id)
                category_list.append(each_id.name)
            category_list = list(set(category_list))
            category_str = str(category_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            if len(category_ids) > 1:
                category_sql += " and category.id in "+ str(tuple(category_ids))
            else:
                category_sql += " and category.id = "+ str(category_ids[0])
            filters += " | Product Category: " + category_str
        if self.include_sales_person:
            sales_person_sql +=" sales_person.name as sales_person,\ninvline.sales_user_id as sales_user_id,"
            sales_person_join_sql += " left join res_users sales_user on(sales_user.id = invline.sales_user_id)\nleft join res_partner sales_person on(sales_person.id = sales_user.partner_id)"
            sales_person_group_sql += " sales_person.name, invline.sales_user_id,"
            pos_sales_person_sql +=" sales_person.name as sales_person,\npos.user_id as sales_user_id,"
            pos_sales_person_join_sql += " left join res_users sales_user on(sales_user.id = pos.user_id)\nleft join res_partner sales_person on(sales_person.id = sales_user.partner_id)"
            pos_sales_person_group_sql += " sales_person.name, pos.user_id,"
        dates = []
        dates.append(date_from)
        dates.append(date_to)
        start, end = [datetime.combine(date, datetime.min.time()) for date in dates]
        if date_from != date_to:
            months = OrderedDict(((start + timedelta(_)).strftime(r"%b-%y"), None) for _ in range((end - start).days)).keys()
            print('>>>>>>>>>>>>>>>>>>>>>>months>>>>>>>>>>>>>>>>>>', months, type(months))
        else:
            end = end + relativedelta(days = +1)
            months = OrderedDict(((start + timedelta(_)).strftime(r"%b-%y"), None) for _ in range((end - start).days)).keys()
            print(">>>>>>>>>>>>>>>>>>>>>>months>>>>>>>12222222222>>>>>>>>>>>", months)
            if len(months) > 1:
                del months[-1]
        report_name = ""
        report_name = "Sale Register - Product Summary"
        sql = """select * from ((select
                    rp.name as customer_name,
                    rp.id as partner_id,
                    rp.vat as tin,
                    rp.vrn_no as vrn_no,
                    rp.business_no as business_no,
                    area.name as area,
                    region.name as region,
                    country.name as country,
                    wh.name as delivery_warehouse,
                    invline.product_id as product_id,
                    inv.partner_id as partner_id,
                    inv.warehouse_id as warehouse_id,
                    category.name as category,
                    template.name as product,
                    uom.name as uom,
                    manager.name as sales_manager,
                    inv.sales_manager_id as sales_manager_id,""" + sales_person_sql + """
                    currency.name as customer_currency,
                    inv_currency.name as invoice_currency,
                    invline.currency_id as currency_id,
                    'invoice' as query_type
                from account_move_line invline
                    left join account_move inv on (inv.id = invline.move_id)
                    left join res_partner rp on (rp.id = inv.partner_id)
                    left join res_state_area area on (area.id = rp.area_id)
                    left join res_state_region region on (region.id = rp.region_id)
                    left join res_country country on (country.id = rp.country_id)
                    left join stock_warehouse wh on (wh.id = inv.warehouse_id)
                    left join product_product product on (product.id = invline.product_id)
                    left join product_template template on (template.id = product.product_tmpl_id)
                    left join product_category category on (category.id = template.categ_id)
                    left join uom_uom uom on (uom.id = invline.product_uom_id)
                    left join res_currency currency on (currency.id = rp.transaction_currency_id)
                    left join res_currency inv_currency on (inv_currency.id = invline.currency_id)
                    left join res_users ser on (ser.id = inv.sales_manager_id)
                    left join res_partner manager on (manager.id = ser.partner_id)""" + sales_person_join_sql + """
                where
                    inv.invoice_date >= %s and inv.invoice_date <= %s and inv.move_type = 'out_invoice'
                    and inv.state in ('open', 'paid') """+ partner_sql + area_sql + region_sql+ manager_user_sql + warehouse_sql + sales_person_where_sql + product_sql + category_sql + """
                group by
                    template.name,
                    invline.product_id,
                    category.name,
                    inv.partner_id,
                    inv.currency_id,
                    invline.currency_id,
                    currency.name,
                    inv_currency.name,
                    rp.name,
                    rp.id,
                    rp.vat,
                    rp.vrn_no,
                    rp.business_no,
                    manager.name,
                    inv.sales_manager_id,""" + sales_person_group_sql + """
                    area.name,
                    region.name,
                    country.name,
                    wh.name,
                    uom.name,
                    inv.warehouse_id
                order by
                    wh.name,
                    rp.name,
                    template.name,
                    inv.currency_id)
                    UNION
                (select
                    (case when pos.partner_name is not null then concat(rp.name, ' - ', pos.partner_name) else rp.name end) customer_name,
                    rp.id as partner_id,
                    rp.vat as tin,
                    rp.vrn_no as vrn_no,
                    rp.business_no as business_no,
                    area.name as area,
                    region.name as region,
                    country.name as country,
                    wh.name as delivery_warehouse,
                    pol.product_id as product_id,
                    pos.partner_id as partner_id,
                    wh.id as warehouse_id,
                    category.name as category,
                    template.name as product,
                    uom.name as uom,
                    manager.name as sales_manager,
                    rp.sales_manager_id as sales_manager_id,""" + pos_sales_person_sql + """
                    currency.name as customer_currency,
                    ' ' as invoice_currency,
                    price.currency_id as currency_id,
                    'pos' as query_type
                from
                    pos_order_line pol
                        left join pos_order pos on(pos.id = pol.order_id)
                        left join res_partner rp on(rp.id = pos.partner_id)
                        left join res_state_area area on(area.id = rp.area_id)
                        left join res_state_region region on(region.id = rp.region_id)
                        left join res_country country on (country.id = rp.country_id)
                        left join stock_picking picking on(picking.pos_order_id = pos.id)
                        left join stock_picking_type picking_type on (picking_type.id = picking.picking_type_id)
                    left join stock_warehouse wh on(wh.id = picking_type.warehouse_id)
                    left join product_product product on(product.id = pol.product_id)
                    left join product_template template on(template.id = product.product_tmpl_id)
                    left join product_category category on (category.id = template.categ_id)
                    left join uom_uom uom on(uom.id = template.uom_id)
                    left join product_pricelist price on (price.id = pos.pricelist_id)
                    left join res_currency currency on(currency.id = price.currency_id)
                    left join res_users ser on(ser.id = rp.sales_manager_id)
                    left join res_partner manager on(manager.id = ser.partner_id)""" + pos_sales_person_join_sql + """
                where
                    ((pos.date_order at time zone %s)::timestamp::date) >= %s
                    and ((pos.date_order at time zone %s)::timestamp::date) <= %s
                    and pos.state in ('invoiced', 'paid', 'done')"""+ partner_sql + area_sql + region_sql+ manager_user_sql + warehouse_sql + product_sql + category_sql + pos_sales_person_where_sql + """
                group by
                    template.name,
                    pol.product_id,
                    category.name,
                    wh.id,
                    pos.partner_id,
                    price.currency_id,
                    rp.name,
                    pos.partner_name,
                    rp.id,
                    rp.vat,
                    rp.vrn_no,
                    rp.business_no,
                    manager.name,
                    rp.sales_manager_id,""" + pos_sales_person_group_sql + """
                    area.name,
                    region.name,
                    country.name,
                    wh.name,
                    uom.name,
                    currency.name
                order by
                    wh.name,
                    rp.name,
                    template.name)) x order by x.query_type, x.delivery_warehouse
                    """
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(sql , ( date_from, date_to, tz, date_from, tz, date_to, ))
        t = self.env.cr.dictfetchall()
        if len(t) == 0:
            raise UserError(('No Data Available.Try using different values'))
        person_sql = """ """
        pos_person_sql = """ """
        if self.include_sales_person:
            person_sql += " and invline.sales_user_id = %s"
            pos_person_sql += " and pos.user_id = %s"
        month_sql = """ select x.month_year, x.year, x.mm, x.month, 
                        x.product_id, x.product, x.uom, sum(x.qty) as qty, sum(x.sale_weight) as sale_weight, sum(x.sale_value) as sale_value, sum(x.sale_value_company_currency) as sale_value_company_currency, x.warehouse_id, x.currency_id from 
                        ((select
                           concat(to_char(inv.invoice_date,'Mon'), '-', to_char(inv.invoice_date,'YY')) as month_year,
                           to_char(inv.invoice_date,'YYYY') as year,
                           to_char(inv.invoice_date,'MM') as mm,
                           to_char(inv.invoice_date,'Mon') as month,
                           product.id as product_id,
                           template.name as product,
                           uom.name as uom,
                           sum(invline.quantity) as qty,
                           (sum(invline.quantity) * product.weight) as sale_weight,
                           sum(round(invline.price_subtotal, 2)) as sale_value,
                           sum(round(invline.price_subtotal_signed, 2)) as sale_value_company_currency,
                           inv.warehouse_id as warehouse_id,
                           inv.currency_id
                       from
                           account_move_line invline
                           left join account_move inv on (inv.id = invline.move_id)
                           left join product_product product on (product.id = invline.product_id)
                           left join product_template template on (template.id = product.product_tmpl_id)
                           left join uom_uom uom on (uom.id = invline.product_uom_id)
                       where
                           inv.invoice_date >= %s and inv.invoice_date <= %s
                           and product.id = %s""" + person_sql + """ 
                           and invline.currency_id = %s
                           and inv.partner_id = %s 
                           and inv.warehouse_id = %s 
                           and inv.sales_manager_id = %s
                           and inv.state in ('open', 'paid')
                           and inv.move_type = 'out_invoice'
                       group by
                           to_char(inv.invoice_date, 'YYYY'),
                           to_char(inv.invoice_date, 'MM'),
                           to_char(inv.invoice_date, 'Mon'),
                           product.id,
                           template.name,
                           uom.name,
                           inv.warehouse_id,
                           inv.sales_manager_id,
                           concat(to_char(inv.invoice_date, 'Mon'), '-', to_char(inv.invoice_date, 'YY')),
                           inv.currency_id
                       order by 
                           to_char(inv.invoice_date,'YYYY'),
                           to_char(inv.invoice_date, 'MM'))
                       UNION
                       (select
                           concat(to_char((pos.date_order at time zone %s)::timestamp::date,'Mon'), '-', to_char((pos.date_order at time zone %s)::timestamp::date,'YY')) as month_year,
                           to_char(((pos.date_order at time zone %s)::timestamp::date),'YYYY') as year,
                           to_char(((pos.date_order at time zone %s)::timestamp::date),'MM') as mm,
                           to_char(((pos.date_order at time zone %s)::timestamp::date),'Mon') as month,
                           product.id as product_id,
                           template.name as product,
                           uom.name as uom,
                           sum(pol.qty) as qty,
                           (sum(pol.qty) * product.weight) as sale_weight,
                           sum(round(pol.price_subtotal,2)) as sale_value,
                           sum(round(pol.price_subtotal_company_currency,2)) as sale_value_company_currency,
                           picking_type.warehouse_id as warehouse_id,
                           price.currency_id
                        from
                           pos_order_line pol
                           left join pos_order pos on (pos.id = pol.order_id)
                           left join res_partner rp on(rp.id = pos.partner_id)
                           left join res_users ser on(ser.id = rp.sales_manager_id)
                           left join res_partner manager on(manager.id = ser.partner_id)
                           left join product_pricelist price on (price.id = pos.pricelist_id)
                           left join product_product product on (product.id = pol.product_id)
                           left join product_template template on (template.id = product.product_tmpl_id)
                           left join product_uom uom on (uom.id = template.uom_id)
                           left join pos_session session on (session.id = pos.session_id)
                           left join pos_config config on (config.id = session.config_id)
                           left join stock_picking_type picking_type on (picking_type.id = config.picking_type_id)
                        where
                           ((pos.date_order at time zone %s)::timestamp::date) >= %s 
                           and ((pos.date_order at time zone %s)::timestamp::date) <= %s
                           and product.id = %s """ + pos_person_sql +"""
                           and price.currency_id = %s
                           and pos.partner_id = %s 
                           and picking_type.warehouse_id = %s 
                           and rp.sales_manager_id = %s
                           and pos.state in ('invoiced', 'paid', 'done')
                        group by
                           to_char(((pos.date_order at time zone %s)::timestamp::date), 'YYYY'),
                           to_char(((pos.date_order at time zone %s)::timestamp::date), 'MM'),
                           to_char(((pos.date_order at time zone %s)::timestamp::date), 'Mon'),
                           product.id,
                           template.name,
                           uom.name,
                           concat(to_char(((pos.date_order at time zone %s)::timestamp::date), 'Mon'), '-', to_char(((pos.date_order at time zone %s)::timestamp::date), 'YY')),
                           picking_type.warehouse_id,
                           price.currency_id
                        order by 
                           to_char(((pos.date_order at time zone %s)::timestamp::date),'YYYY'),
                           to_char(((pos.date_order at time zone %s)::timestamp::date),'MM'))) x 
                   group by  x.month_year, x.year, x.mm, x.month, 
                        x.product_id, x.product, x.uom, x.warehouse_id, x.currency_id
                   
                        """

        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4500
        sheet1.col(2).width = 5500
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 3500
        sheet1.col(5).width = 4500
        sheet1.col(6).width = 4500
        sheet1.col(7).width = 5500
        sheet1.col(8).width = 4500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 3500
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        from_date_str = self.date_from.strftime('%Y-%m-%d')
        date_from_title = time.strptime(from_date_str, "%Y-%m-%d")
        date_from_title = time.strftime('%d-%m-%Y', date_from_title)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        date_to_title = time.strptime(to_date_str, "%Y-%m-%d")
        date_to_title = time.strftime('%d-%m-%Y', date_to_title)

        # date_from_title = time.strptime(date_from, "%Y-%m-%d")
        # date_from_title = time.strftime('%d-%m-%Y', date_from_title)
        # date_to_title = time.strptime(date_to, "%Y-%m-%d")
        # date_to_title = time.strftime('%d-%m-%Y', date_to_title)
        title = report_name +' ( From ' + date_from_title + ' To ' + date_to_title + ' )'
        if not self.include_sales_person:
            sheet1.write_merge(r2, r2, 0, 10, filters, Style.groupByTitle())
        else:
            sheet1.write_merge(r2, r2, 0, 11, filters, Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Sale Type", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Customer", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Area", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Region", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Country", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Sales Manager", Style.contentTextBold(r3, 'black', 'white'))
        if self.include_sales_person:
            sheet1.write(r3, 8, "Sales Person", Style.contentTextBold(r3,'black', 'white'))
            sheet1.write(r3, 9, "Product Category", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 10, "Product", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 11, "Unit Of Measure", Style.contentTextBold(r3, 'black', 'white'))
            months_col = 11
        else:
            sheet1.write(r3, 8, "Product Category", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 9, "Product", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 10, "Unit Of Measure", Style.contentTextBold(r3, 'black', 'white'))
            months_col = 10
        month_index = {}
        for month in range(len(months)):
            print("\n\nm................month", month)
            print("\n\nm................months", months)
            # print("\n\nm................months", months[0])
            months_col += 1
            print("\n\nm................months_col", months_col)
            sheet1.write_merge(r2, r2, months_col, (months_col+4), list(months)[0], Style.groupByTitle())
            # sheet1.write_merge(r2, r2, months_col, (months_col+4), months[month], Style.groupByTitle())
            month_index[list(months)[0]] = months_col
            print("\n\n......month_index........", month_index)
            sheet1.col(months_col).width = 3500
            sheet1.write(r3, months_col, "Sale Quantity", Style.contentTextBold(r3,'black', 'white'))
            months_col += 1
            sheet1.col(months_col).width = 3500
            sheet1.write(r3, months_col, "Sale Weight", Style.contentTextBold(r3,'black', 'white'))
            months_col += 1
            sheet1.col(months_col).width = 3500
            sheet1.write(r3, months_col, "Invoice Currency", Style.contentTextBold(r3, 'black', 'white'))
            months_col += 1
            sheet1.col(months_col).width = 5500
            sheet1.write(r3, months_col, "Untaxed Sale Value - Invoice Currency", Style.contentTextBold(r3,'black', 'white'))
            months_col += 1
            sheet1.col(months_col).width = 4500
            sheet1.write(r3, months_col, "Untaxed Sale Value - local Currency ", Style.contentTextBold(r3,'black', 'white'))
        sheet1.write(r3, months_col+1, "TIN", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, months_col+2, "VAT", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, months_col+3, "Business License NO", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write_merge(rc, rc, 0, months_col + 3, self.company_id.name, Style.title_ice_blue())
        sheet1.write_merge(r1, r1, 0, months_col + 3, title, Style.title_ice_blue())
        row = 3
        s_no = 0
        data_col = False
        month_dict = {}
        subtotal_dict = {}
        country_name = ""
        for each in t:
            if each['product_id'] and self.include_sales_person:
                self.env.cr.execute(month_sql , (date_from, date_to, each['product_id'], each['sales_user_id'],each['currency_id'], each['partner_id'], each['warehouse_id'], each['sales_manager_id'], tz, tz, tz, tz, tz, tz, date_from, tz, date_to, each['product_id'], each['sales_user_id'],each['currency_id'],  each['partner_id'], each['warehouse_id'], each['sales_manager_id'], tz, tz, tz, tz, tz, tz, tz,))
                month_dict = self.env.cr.dictfetchall()
            else:
                self.env.cr.execute(month_sql , (date_from, date_to, each['product_id'], each['currency_id'], each['partner_id'], each['warehouse_id'], each['sales_manager_id'], tz, tz, tz, tz, tz, tz, date_from, tz, date_to, each['product_id'],each['currency_id'], each['partner_id'], each['warehouse_id'], each['sales_manager_id'], tz, tz, tz, tz, tz, tz, tz, ))
                month_dict = self.env.cr.dictfetchall()
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 450
            sheet1.write(row, 0, s_no, Style.normal_left())
            if each['query_type'] == 'invoice':
                sheet1.write(row, 1, "Regular", Style.normal_left())
            else:
                sheet1.write(row, 1, "POS", Style.normal_left())
            sheet1.write(row, 2, each['delivery_warehouse'], Style.normal_left())
            sheet1.write(row, 3, each['customer_name'], Style.normal_left())
            sheet1.write(row, 4, each['area'], Style.normal_left())
            sheet1.write(row, 5, each['region'], Style.normal_left())
            sheet1.write(row, 6, country_name, Style.normal_left())
            sheet1.write(row, 7, each['sales_manager'], Style.normal_left())
            sale_col = 8
            if self.include_sales_person:
                sheet1.write(row, sale_col, each['sales_person'], Style.normal_left())
                sale_col += 1
            sheet1.write(row, sale_col, each['category'], Style.normal_left())
            sheet1.write(row, sale_col+1, each['product'], Style.normal_left())
            sheet1.write(row, sale_col+2, each['uom'], Style.normal_left())
            sheet1.write(row, months_col+1, each['tin'], Style.normal_left())
            sheet1.write(row, months_col+2, each['vrn_no'], Style.normal_left())
            sheet1.write(row, months_col+3, each['business_no'], Style.normal_left())

            for data in month_dict:
                data_col = month_index[data['month_year']]
                if not subtotal_dict.has_key(data['month_year']):
                    subtotal_dict[data['month_year']] = {'col': data_col, 'qty': 0.00, 'sale_weight': 0.00, 'sale_value_company_currency': 0.00}
                sheet1.write(row, data_col, data['qty'], Style.normal_num_right_3digits())
                subtotal_dict[data['month_year']]['qty'] += data['qty'] and data['qty'] or 0.00
                data_col = data_col + 1
                sheet1.write(row, data_col, data['sale_weight'], Style.normal_num_right())
                subtotal_dict[data['month_year']]['sale_weight'] += data['sale_weight'] and data['sale_weight'] or 0.00
                data_col = data_col + 1
                sheet1.write(row, data_col, each['customer_currency'], Style.normal_num_right_3separator())
                data_col = data_col + 1
                sheet1.write(row, data_col, data['sale_value'], Style.normal_num_right_3separator())
                data_col = data_col + 1
                sheet1.write(row, data_col, data['sale_value_company_currency'], Style.normal_num_right_3separator())
                subtotal_dict[data['month_year']]['sale_value_company_currency'] += data['sale_value_company_currency'] and data['sale_value_company_currency'] or 0.00
        if data_col:
            for each in subtotal_dict:
                sheet1.write_merge(row+1, row+1, 0, subtotal_dict[each]['col']-1, "Total", Style.normal_left_ice_blue())
                sheet1.write(row+1, subtotal_dict[each]['col'], subtotal_dict[each]['qty'], Style.normal_left_ice_blue())
                sheet1.write(row+1, subtotal_dict[each]['col']+1, subtotal_dict[each]['sale_weight'], Style.normal_left_ice_blue())
                sheet1.write(row+1, subtotal_dict[each]['col']+4, subtotal_dict[each]['sale_value_company_currency'], Style.normal_left_ice_blue())
        print(">>>>>>>>>>>>>>stream>>>111>>>>>>")
        stream = BytesIO()
        print(">>>>>>>>>>>>>>stream>>>>>>>>>",stream)
        wbk.save(stream)
        print(">>>>>>>>>>>>>>wbk>>>>>>>>>", wbk)
        self.write({ 'name': report_name+'.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.detailed.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
