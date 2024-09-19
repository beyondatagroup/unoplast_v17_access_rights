# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
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
import json
from lxml import etree

class SaleRegisterSummaryReportWizard(models.TransientModel):
    _name = 'sale.register.summary.report.wizard'
    _description = 'Sale Register Summary Report Wizard'
    
    date_from = fields.Date(string='From Date (Invoice Date)', required=True)
    date_to = fields.Date(string='To Date (Invoice Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'sale_register_sumry_partner', 'sale_wizard_sumry_id', 'res_partner_id', string='Customer')
    warehouse_ids = fields.Many2many('stock.warehouse', 'sale_register_sumry_warehouse', 'sale_wizard_sumry_id', 'warehouse_id', string='Warehouse')
    type_account = fields.Selection([('out_invoice', 'Regular'), ('out_refund', 'Refund')], string='Type')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sale.register.summary.report.wizard'))
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(SaleRegisterSummaryReportWizard, self).fields_view_get(
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
            raise UserError(_('Invalid Date Range.Try Using Different Values'))
        
        date_from = self.date_from
        date_to = self.date_to
        pos_order_obj = self.env['pos.order']
        invoice_obj = self.env['account.move']

        tz = self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'


        
        all_partners_children = {}
        all_partner_ids = []
        partner_ids = []
        customer_list = []
        customer_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        partner_sql = """ """
        warehouse_sql = """ """
        type_sql = """ """
        pos_sql = """ """
        filters = "Filtered Based On: Invoice Date | Invoice State (Includes Open And Paid State Only)"
        
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
                partner_sql += " and rp.id  = "+ str(all_partner_ids[0])
            filters += " | Customer:" + customer_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and wh.id in "+ str(tuple(warehouse_ids))
            else:
                if warehouse_ids:
                    warehouse_sql += "and wh.id = "+ str(warehouse_ids[0])
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
                    if warehouse_ids:
                        warehouse_sql += "and wh.id = "+ str(warehouse_ids[0])
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
        report_name = "Sale Register Summary"
        
        sql = """select * from ((select
                    rp.name as customer_name,
                    rp.partner_code as customer_code,
                    inv.number as invoice_number,
                    inv.invoice_date as invoice_date,
                    wh.name as delivery_warehouse,
                    inv.move_type as query_type,
                    inv.state,
                    inv.id
                from account_move inv
                    left join res_partner rp on (rp.id = inv.partner_id)
                    left join sale_order so on (so.id = inv.sale_order_id)
                    left join stock_warehouse wh on (wh.id = inv.warehouse_id)
                where 
                    inv.state_1 in ('open', 'paid')
                    and inv.move_type in ('out_invoice', 'out_refund')
                    and inv.invoice_date >= %s and inv.invoice_date <= %s""" + partner_sql + warehouse_sql + type_sql +"""
                group by
                    inv.invoice_date,
                    rp.name,
                    rp.partner_code,
                    inv.number,
                    inv.move_type,
                    wh.name,
                    inv.state,
                    inv.id
                order by
                    inv.move_type,
                    wh.name,
                    inv.invoice_date)
                    
                    UNION
                    
                    (select 
                        (case when pos.partner_id is not null then concat(rp.name, ' - ', pos.partner_id) else rp.name end) customer_name,
                        rp.partner_code as customer_code,
                        pos.name as invoice_number,
                        ((pos.date_order at time zone %s)::timestamp::date) as invoice_date,
                        wh.name as delivery_warehouse,
                        (case when pos.amount_untaxed_company_currency >= 0.00 then 'out_pos' else 'out_ref' end) as query_type,
                        pos.state,
                        pos.id
                     from pos_order pos
                         left join res_partner rp on (rp.id=pos.partner_id)
                         left join pos_order_line pol on (pol.order_id = pos.id)
                         left join pos_session session on (session.id = pos.session_id)
                         left join pos_config config on (config.id = session.config_id)
                         left join stock_warehouse wh on (wh.id = config.warehouse_id)
                     where 
                        pos.state in ('invoiced', 'paid', 'done')
                        and ((pos.date_order at time zone %s)::timestamp::date) >= %s and ((pos.date_order at time zone %s)::timestamp::date) <= %s""" + partner_sql + warehouse_sql + pos_sql +"""
                    order by
                        wh.name,
                        pos.date_order
                    )) x
                    order by
                        x.query_type, x.delivery_warehouse, x.invoice_number, x.invoice_date"""
        
        # tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        

        self.env.cr.execute(sql , ( date_from, date_to, tz, tz, date_from, tz, date_to, ))
        
        t = self.env.cr.dictfetchall()

        if len(t) == 0:
            raise UserError(_('No Records available on these Filter.Try Using Different Values'))
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 1500
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 5500
        sheet1.col(3).width = 6500
        sheet1.col(4).width = 3500
        sheet1.col(5).width = 9500
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 2000
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
        sheet1.write_merge(rc, rc, 0, 9, self.company_id.name, Style.title_ice_blue())
        sheet1.write_merge(r1, r1, 0, 9, title, Style.title_ice_blue())
        sheet1.write_merge(r2, r2, 0, 9, filters, Style.groupByTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 1, "Sale Type", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 2, "Warehouse", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 3, "Invoice Number", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 4, "Invoice Date", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 5, "Customer", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 6, "Untaxed Amount", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 7, "Tax Amount", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 8, "Total Amount", Style.contentTextBold(2,'black','white'))
        sheet1.write(r3, 9, "Status", Style.contentTextBold(2,'black','white'))
        row = 3
        s_no = 0
        reg_untaxed, reg_taxed, reg_total = 0.00, 0.00, 0.00
        ref_untaxed, ref_taxed, ref_total = 0.00, 0.00, 0.00
        subtotal_row = 0
        for each in t:
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
            sheet1.write(row, 3, each['invoice_number'], Style.normal_left())
            
            invoice_date = time.strptime(str(each['invoice_date']), "%Y-%m-%d")

            invoice_date = time.strftime('%d-%m-%Y', invoice_date)
            
            sheet1.write(row, 4, invoice_date, Style.normal_left())
            sheet1.write(row, 5, each['customer_name'], Style.normal_left())
            if each['query_type'] not in ('out_pos', 'out_ref'):
                inv_browse = invoice_obj.sudo().browse(each['id'])
                if each['query_type'] == 'out_refund':
                    sheet1.write(row, 6, (-1 * inv_browse.company_amount_untaxed), Style.normal_num_right_3separator())
                    sheet1.write(row, 7, (-1 * inv_browse.company_amount_tax), Style.normal_num_right_3separator())
                    sheet1.write(row, 8, (-1 * inv_browse.company_amount_total), Style.normal_num_right_3separator())
                    ref_untaxed += (-1 * inv_browse.company_amount_untaxed)
                    ref_taxed += (-1 * inv_browse.company_amount_tax)
                    ref_total += (-1 * inv_browse.company_amount_total)
                else:
                    sheet1.write(row, 6, inv_browse.company_amount_untaxed, Style.normal_num_right_3separator())
                    sheet1.write(row, 7, inv_browse.company_amount_tax, Style.normal_num_right_3separator())
                    sheet1.write(row, 8, inv_browse.company_amount_total, Style.normal_num_right_3separator())
                    reg_untaxed += inv_browse.company_amount_untaxed
                    reg_taxed += inv_browse.company_amount_tax
                    reg_total += inv_browse.company_amount_total
                subtotal_row = row
            else:
                pos_browse = pos_order_obj.sudo().browse(each['id'])
                if pos_browse.amount_untaxed_company_currency >= 0.00:
                    sheet1.write(row, 6, pos_browse.amount_untaxed_company_currency, Style.normal_num_right_3separator())
                    sheet1.write(row, 7, pos_browse.amount_tax_company_currency, Style.normal_num_right_3separator())
                    sheet1.write(row, 8, pos_browse.amount_total_company_currency, Style.normal_num_right_3separator())
                    reg_untaxed += pos_browse.amount_untaxed_company_currency
                    reg_taxed += pos_browse.amount_tax_company_currency
                    reg_total += pos_browse.amount_total_company_currency
                else:
                    sheet1.write(row, 6, pos_browse.amount_untaxed_company_currency, Style.normal_num_right_3separator())
                    sheet1.write(row, 7, pos_browse.amount_tax_company_currency, Style.normal_num_right_3separator())
                    sheet1.write(row, 8, pos_browse.amount_total_company_currency, Style.normal_num_right_3separator())
                    ref_untaxed += pos_browse.amount_untaxed_company_currency
                    ref_taxed += pos_browse.amount_tax_company_currency
                    ref_total += pos_browse.amount_total_company_currency
                subtotal_row = row
            if each['state'] == 'open':
                sheet1.write(row, 9, 'Open' , Style.normal_left())
            elif each['state'] == 'paid':
                sheet1.write(row, 9, 'Paid' , Style.normal_left())
            else:
                sheet1.write(row, 9, 'Done' , Style.normal_left())
        if self.type_account == 'out_invoice' or self.type_account == False: 
            subtotal_row += 1 
            sheet1.write_merge(subtotal_row, subtotal_row, 0, 5, "Regular Total" , Style.normal_left_ice_blue())
            sheet1.write( subtotal_row, 6, reg_untaxed , Style.normal_right_ice_blue())
            sheet1.write( subtotal_row, 7, reg_taxed , Style.normal_right_ice_blue())
            sheet1.write( subtotal_row, 8, reg_total , Style.normal_right_ice_blue())
        if self.type_account == 'out_refund' or self.type_account == False: 
            subtotal_row += 1 
            sheet1.write_merge(subtotal_row, subtotal_row, 0, 5, "Refund Total" , Style.normal_left_ice_blue())
            sheet1.write( subtotal_row, 6, ref_untaxed, Style.normal_right_ice_blue())
            sheet1.write( subtotal_row, 7, ref_taxed, Style.normal_right_ice_blue())
            sheet1.write( subtotal_row, 8, ref_total, Style.normal_right_ice_blue())
        if self.type_account == False:
            subtotal_row += 1 
            sheet1.write_merge(subtotal_row, subtotal_row, 0, 5, "Total" , Style.normal_left_ice_blue())
            sheet1.write( subtotal_row, 6, (reg_untaxed + ref_untaxed) , Style.normal_right_ice_blue())
            sheet1.write( subtotal_row, 7, (reg_taxed + ref_taxed) , Style.normal_right_ice_blue())
            sheet1.write( subtotal_row, 8, (reg_total + ref_total) , Style.normal_right_ice_blue())
        
        stream = BytesIO()
        wbk.save(stream)

        self.write({ 'name': report_name+'.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.register.summary.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }

