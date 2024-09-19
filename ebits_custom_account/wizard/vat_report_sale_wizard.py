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

class VatReportSaletWizard(models.TransientModel):
    _name = 'vat.report.sale.wizard'
    _description = 'Sale VAT Report Wizard'
    
    date_from= fields.Date(string='From Date(Invoice Date)', required=True)
    date_to= fields.Date(string='To Date(Invoice Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_vat_report_sale_partner', 'vat_report_sale_wizard_id', 'partner_id', string='Customer')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_vat_report_sale_warehouse', 'vat_report_sale_wizard_id', 'warehouse_id', string='Warehouse')
    currency_ids = fields.Many2many('res.currency', 'etc_vat_report_sale_currency', 'vat_report_sale_wizard_id', 'currency_id', string='Currency')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output= fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(VatReportSaletWizard, self).fields_view_get(
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
        report_name = "Sale VAT Report"
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
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
        
        domain_default = []
        domain_default = [('state', 'in', ('open', 'paid')), ('type', 'in', ('out_invoice','out_refund')), ('date_invoice', '>=',  self.date_from), ('date_invoice', '<=',  self.date_to)]
        domain_pos = []
        domain_pos = [('date_order', '>=',  self.date_from), ('date_order', '<=',  self.date_to), ('state', 'in', ('paid', 'done'))]
        if self.partner_ids:
            for each_id in self.partner_ids:
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id] 
                partner_list.append(each_id.name)
                partner_str = str(partner_list).replace('[','').replace(']','').replace("u'","").replace("'","")
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
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
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
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
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
                currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_currency_ids) > 1:
                domain_default = domain_default + [('currency_id', 'in', tuple(all_currency_ids))]
                domain_pos = domain_pos + [('pricelist_id.currency_id', 'in', tuple(all_currency_ids))]
                filters += ", currency : "+ currency_str
            else:
                domain_default = domain_default + [('currency_id', '=', all_currency_ids[0])]
                domain_pos = domain_pos + [('pricelist_id.currency_id', '=', all_currency_ids[0])]
                filters += ", currency : "+ currency_str

        invoice_records = invoice_obj.sudo().search(domain_default, order="type, date_invoice, number")
        pos_record = pos_obj.sudo().search(domain_pos, order="date_order, name")

        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4000
        sheet1.col(2).width = 4000
        sheet1.col(3).width = 6500
        sheet1.col(4).width = 14000
        sheet1.col(5).width = 5500
        sheet1.col(6).width = 4000
        sheet1.col(7).width = 3000
        sheet1.col(8).width = 3000
        sheet1.col(9).width = 2500
        sheet1.col(10).width = 4000
        sheet1.col(11).width = 4000
        sheet1.col(12).width = 4000
        sheet1.col(13).width = 4000
        sheet1.col(14).width = 4000
        sheet1.col(15).width = 4000
        sheet1.col(16).width = 4000
        sheet1.col(17).width = 4000
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 380
        sheet1.row(r4).height = 256 * 3
        title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
        title1 = self.company_id.name
        title2 = filters 
        title3 = 'Transaction Currency'
        title4 = 'Local Currency' + ' ( ' + str(self.company_id.currency_id.name) + ' )'
        sheet1.write_merge(r1, r1, 0, 17, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 17, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 7, title2, Style.subTitle())
        sheet1.write_merge(r3, r3, 8, 11, title3, Style.subTitle())
        sheet1.write_merge(r3, r3, 12, 14, title4, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Customer Invoice No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Customer Invoice Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "Customer", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Delivery Address", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Source Document", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 11, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 12, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 13, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 14, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 15, "TIN", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 16, "VAT", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 17, "Business Licence", Style.contentTextBold(r2,'black','white'))
        
        row = r4
        s_no = 0
        
        invoice_untaxed = invoice_tax = invoice_total = invoice_residual =0.00
        refund_untaxed = refund_tax = refund_total = refund_residual =0.00
        
        l_invoice_untaxed = l_invoice_tax = l_invoice_total = l_invoice_residual =0.00
        l_refund_untaxed = l_refund_tax = l_refund_total = l_refund_residual =0.00
        for each in invoice_records:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 300
            address = ((each.partner_shipping_id and each.partner_shipping_id.street or "") 
                                + ' ' + (each.partner_shipping_id.city or "") 
                                + ' ' + (each.partner_shipping_id.area_id and each.partner_shipping_id.area_id.name or "") 
                                + ' ' + (each.partner_shipping_id.region_id and each.partner_shipping_id.region_id.name or "") 
                                + ' ' + (each.partner_shipping_id.country_id and each.partner_shipping_id.country_id.name or ""))
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each.number, Style.normal_left())
            date_invoice = ""
            if each.date_invoice:
                date_invoice = time.strptime(each.date_invoice, "%Y-%m-%d")
                date_invoice = time.strftime('%d-%m-%Y', date_invoice)
            sheet1.write(row, 2, date_invoice, Style.normal_left())
            partner_name = ""
            partner_name = (each.partner_id and each.partner_id.name or "")
            sheet1.write(row, 3, partner_name, Style.normal_left())
            sheet1.write(row, 4, address, Style.normal_left())
            sheet1.write(row, 5, (each.warehouse_id.name and each.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(row, 6, (each.origin and each.origin or ""), Style.normal_left())
            sheet1.write(row, 7, (each.type == 'out_invoice' and 'Regular' or 'Refund'), Style.normal_left())
            sheet1.write(row, 8, each.currency_id.name, Style.normal_left())
            if each.type == 'out_invoice':
                sheet1.write(row, 9, each.amount_untaxed, Style.normal_num_right_3separator())
                sheet1.write(row, 10, each.amount_tax, Style.normal_num_right_3separator())
                sheet1.write(row, 11, each.amount_total, Style.normal_num_right_3separator())
                sheet1.write(row, 12, abs(each.amount_untaxed_signed), Style.normal_num_right_3separator())
                sheet1.write(row, 13, abs(each.amount_tax_company_currency), Style.normal_num_right_3separator())
                sheet1.write(row, 14, abs(each.amount_total_company_signed), Style.normal_num_right_3separator())
                sheet1.write(row, 15, each.partner_id.vat and each.partner_id.vat or '', Style.normal_left())
                sheet1.write(row, 16, each.partner_id.vrn_no and each.partner_id.vrn_no or '', Style.normal_left())
                sheet1.write(row, 17, each.partner_id.business_no and each.partner_id.business_no or '', Style.normal_left())
                l_invoice_untaxed += each.amount_untaxed_signed
                l_invoice_tax += abs(each.amount_tax_company_currency)
                l_invoice_total += each.amount_total_company_signed
            else:
                sheet1.write(row, 9, -1 * each.amount_untaxed, Style.normal_num_right_3separator())
                sheet1.write(row, 10, -1 * each.amount_tax, Style.normal_num_right_3separator())
                sheet1.write(row, 11, -1 * each.amount_total, Style.normal_num_right_3separator())
                sheet1.write(row, 12, -1 * abs(each.amount_untaxed_signed), Style.normal_num_right_3separator())
                sheet1.write(row, 13, -1 * abs(each.amount_tax_company_currency), Style.normal_num_right_3separator())
                sheet1.write(row, 14, -1 * abs(each.amount_total_company_signed), Style.normal_num_right_3separator())
                sheet1.write(row, 15, each.partner_id.vat and each.partner_id.vat or '', Style.normal_left())
                sheet1.write(row, 16, each.partner_id.vrn_no and each.partner_id.vrn_no or '', Style.normal_left())
                sheet1.write(row, 17, each.partner_id.business_no and each.partner_id.business_no or '', Style.normal_left())
                
                l_refund_untaxed += abs(each.amount_untaxed_signed)
                l_refund_tax += abs(each.amount_tax_company_currency)
                l_refund_total += abs(each.amount_total_company_signed)
                
        pos_l_invoice_untaxed = pos_l_invoice_tax = pos_l_invoice_total = pos_l_invoice_residual =0.00
        pos_l_refund_untaxed = pos_l_refund_tax = pos_l_refund_total = pos_l_refund_residual =0.00
        for each_pos in pos_record:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 500
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, (each_pos.name and each_pos.name or ""), Style.normal_left())
            update_order_date = ""
            if each_pos.date_order:
                order_date = time.strftime(each_pos.date_order) 
                order_date = datetime.strptime(order_date, '%Y-%m-%d %H:%M:%S').date() 
                update_order_date = datetime.strftime(order_date, '%d-%m-%Y')
            sheet1.write(row, 2, update_order_date, Style.normal_left())
            partner_name = ""
            partner_name = (each_pos.partner_id and each_pos.partner_id.name or "") + " - " + (each_pos.partner_name and each_pos.partner_name or "")
            sheet1.write(row, 3, partner_name, Style.normal_left())
            sheet1.write(row, 4, (each_pos.partner_address and each_pos.partner_address or ""), Style.normal_left())
            sheet1.write(row, 5, (each_pos.session_id.config_id.warehouse_id and each_pos.session_id.config_id.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(row, 6, (each_pos.session_id and each_pos.session_id.name or ""), Style.normal_left())
            if each_pos.amount_untaxed >= 0.00:
                sheet1.write(row, 7, 'POS Regular', Style.normal_left())
                sheet1.write(row, 8, (each_pos.pricelist_id.currency_id and each_pos.pricelist_id.currency_id.name or ""), Style.normal_left())
                sheet1.write(row, 9, each_pos.amount_untaxed, Style.normal_num_right_3separator())
                sheet1.write(row, 10, each_pos.amount_tax, Style.normal_num_right_3separator())
                sheet1.write(row, 11, each_pos.amount_total, Style.normal_num_right_3separator())
                sheet1.write(row, 12, each_pos.amount_untaxed_company_currency, Style.normal_num_right_3separator())
                sheet1.write(row, 13, each_pos.amount_tax_company_currency, Style.normal_num_right_3separator())
                sheet1.write(row, 14, each_pos.amount_total_company_currency, Style.normal_num_right_3separator())
                sheet1.write(row, 15, each_pos.partner_id.vat and each_pos.partner_id.vat or '', Style.normal_left())
                sheet1.write(row, 16, each_pos.partner_id.vrn_no and each_pos.partner_id.vrn_no or '', Style.normal_left())
                sheet1.write(row, 17, each_pos.partner_id.business_no and each_pos.partner_id.business_no or '', Style.normal_left())
                
                pos_l_invoice_untaxed += each_pos.amount_untaxed_company_currency
                pos_l_invoice_tax += each_pos.amount_tax_company_currency
                pos_l_invoice_total += each_pos.amount_total_company_currency
            else:
                sheet1.write(row, 7, 'POS Refund', Style.normal_left())
                sheet1.write(row, 8, (each_pos.pricelist_id.currency_id and each_pos.pricelist_id.currency_id.name or ""), Style.normal_left())
                sheet1.write(row, 9, each_pos.amount_untaxed, Style.normal_num_right_3separator())
                sheet1.write(row, 10, each_pos.amount_tax, Style.normal_num_right_3separator())
                sheet1.write(row, 11, each_pos.amount_total, Style.normal_num_right_3separator())
                sheet1.write(row, 12, each_pos.amount_untaxed_company_currency, Style.normal_num_right_3separator())
                sheet1.write(row, 13, each_pos.amount_tax_company_currency, Style.normal_num_right_3separator())
                sheet1.write(row, 14, each_pos.amount_total_company_currency, Style.normal_num_right_3separator())
                sheet1.write(row, 15, each_pos.partner_id.vat and each_pos.partner_id.vat or '', Style.normal_left())
                sheet1.write(row, 16, each_pos.partner_id.vrn_no and each_pos.partner_id.vrn_no or '', Style.normal_left())
                sheet1.write(row, 17, each_pos.partner_id.business_no and each_pos.partner_id.business_no or '', Style.normal_left())
                
                pos_l_refund_untaxed += abs(each_pos.amount_untaxed_company_currency)
                pos_l_refund_tax += abs(each_pos.amount_tax_company_currency)
                pos_l_refund_total += abs(each_pos.amount_total_company_currency)

        invoice_untaxed = l_invoice_untaxed + pos_l_invoice_untaxed
        invoice_tax = l_invoice_tax + pos_l_invoice_tax
        invoice_total = l_invoice_total + pos_l_invoice_total
        refund_untaxed = l_refund_untaxed + pos_l_refund_untaxed
        refund_tax = l_refund_tax + pos_l_refund_tax
        refund_total = l_refund_total + pos_l_refund_total
            
        row = row + 1
        sheet1.write_merge(row, row, 0, 11, 'Invoice Grand Total', Style.groupByTitle())
        sheet1.write(row, 12, invoice_untaxed, Style.groupByTotal3Separator())
        sheet1.write(row, 13, invoice_tax, Style.groupByTotal3Separator())
        sheet1.write(row, 14, invoice_total, Style.groupByTotal3Separator())
        
        row = row + 1
        sheet1.write_merge(row, row, 0, 11, 'Refund Grand Total', Style.groupByTitle())
        sheet1.write(row, 12, -1 * refund_untaxed, Style.groupByTotal3Separator())
        sheet1.write(row, 13, -1 * refund_tax, Style.groupByTotal3Separator())
        sheet1.write(row, 14, -1 * refund_total, Style.groupByTotal3Separator())
        
        row = row + 1
        sheet1.write_merge(row, row, 0, 11,  'Grand Total', Style.groupByTitle())
        sheet1.write(row, 12, (invoice_untaxed - refund_untaxed), Style.groupByTotal3Separator())
        sheet1.write(row, 13, (invoice_tax - refund_tax), Style.groupByTotal3Separator())
        sheet1.write(row, 14, (invoice_total - refund_total), Style.groupByTotal3Separator())
      
        stream = cStringIO.StringIO()
        wbk.save(stream)
        
        self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'vat.report.sale.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
