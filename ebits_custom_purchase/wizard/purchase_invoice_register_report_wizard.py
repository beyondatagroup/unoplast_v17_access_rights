# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
import xlwt
# import cStringIO
import base64
# import xlrd
# import parser
from lxml import etree
from odoo.addons.ebits_custom_purchase.wizard.excel_styles import ExcelStyles
import io

class PurchaseInvoiceRegisterReportWizard(models.TransientModel):
    _name = 'purchase.invoice.register.report.wizard'
    _description = 'Purchase Invoice Register Report Wizard'
    
    date_from = fields.Date(string='From Date(Bill Date)', required=True)
    date_to = fields.Date(string='To Date(Bill Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_pur_inv_register_partner', 'pur_inv_register_wizard_id', 'partner_id', string='Vendor')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_pur_inv_register_warehouse', 'pur_inv_register_wizard_id', 'warehouse_id', string='Warehouse')
    currency_ids = fields.Many2many('res.currency', 'etc_pur_inv_register_currency', 'pur_inv_register_wizard_id', 'currency_id', string='Currency')
    journal_ids = fields.Many2many('account.journal', 'etc_pur_inv_register_journal', 'pur_inv_register_wizard_id', 'journal_id', string='Journal')
    type_account = fields.Selection([
        ('in_invoice', 'Regular'), 
        ('in_refund', 'Refund')
        ], string='Type')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PurchaseInvoiceRegisterReportWizard, self).fields_view_get(
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
    
    # @api.multi
    def action_print_report(self):
        invoice_obj = self.env['account.move']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Purchase Invoice Register Report"
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
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
        
        all_journal_ids = []
        journal_list = []
        journal_str = ""
        
        domain_default = []
        domain_default = [('invoice_date', '>=',  self.date_from), ('invoice_date', '<=',  self.date_to), ('move_type', 'in', ('in_invoice', 'in_refund')),('state_1', 'in', ('open', 'paid'))]
        if self.partner_ids:
            for each_id in self.partner_ids:
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id] 
                partner_list.append(each_id.name)
                partner_str = str(partner_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                domain_default = domain_default + [('partner_id', 'in', tuple(all_partner_ids))]
                filters += ", Vendor : "+ partner_str
            else:
                domain_default = domain_default + [('partner_id', '=', all_partner_ids[0])]
                filters += ", Vendor : "+ partner_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                all_warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_warehouse_ids) > 1:
                domain_default = domain_default + [('warehouse_id', 'in', tuple(all_warehouse_ids))]
                filters += ", Warehouse : "+ warehouse_str
            else:
                domain_default = domain_default + [('warehouse_id', '=', all_warehouse_ids[0])]
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
                    filters += ", Warehouse : "+ warehouse_str
                else:
                    domain_default = domain_default + [('warehouse_id', '=', all_warehouse_ids[0])]
                    filters += ", Warehouse : "+ warehouse_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                all_currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
                currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_currency_ids) > 1:
                domain_default = domain_default + [('currency_id', 'in', tuple(all_currency_ids))]
                filters += ", currency : "+ currency_str
            else:
                domain_default = domain_default + [('currency_id', '=', all_currency_ids[0])]
                filters += ", currency : "+ currency_str
        if self.journal_ids:
            for each_id in self.journal_ids:
                all_journal_ids.append(each_id.id)
                journal_list.append(each_id.name)
                journal_str = str(journal_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_journal_ids) > 1:
                domain_default = domain_default + [('journal_id', 'in', tuple(all_journal_ids))]
                filters += ", Journal : "+ journal_str
            else:
                domain_default = domain_default + [('journal_id', '=', all_journal_ids[0])]
                filters += ", Journal : "+ journal_str
        if self.type_account:
            domain_default = domain_default + [('move_type', '=', self.type_account)]
            if self.type_account == 'in_invoice':
                filters += ", State : Regular"
            if self.type_account == 'in_refund':
                filters += ", State : Refund"
        print("\n\n\n...........domain_default",domain_default)
        invoice_records = invoice_obj.sudo().search(domain_default, order="move_type, invoice_date, number")
        print("n\\n..........invoice_records",invoice_records)
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3000
        sheet1.col(2).width = 5500
        sheet1.col(3).width = 3000
        sheet1.col(4).width = 9500
        sheet1.col(5).width = 5000
        sheet1.col(6).width = 5000
        sheet1.col(7).width = 3000
        sheet1.col(8).width = 5500
        sheet1.col(9).width = 5500
        sheet1.col(10).width = 5000
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 4000
        sheet1.col(13).width = 4000
        sheet1.col(14).width = 4000
        sheet1.col(15).width = 4000
        sheet1.col(16).width = 4000
        sheet1.col(17).width = 4000
        sheet1.col(18).width = 4000
        sheet1.col(19).width = 4000
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 200 * 3
        title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
        title1 = self.company_id.name
        title2 = filters 
        title4 = 'Local Currency' + ' ( ' + str(self.company_id.currency_id.name) + ' )'
        sheet1.write_merge(r1, r1, 0, 19, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 19, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 10, title2, Style.subTitle())
        sheet1.write_merge(r3, r3, 11, 15, 'Transaction Currency', Style.subTitle())
        sheet1.write_merge(r3, r3, 16, 19, title4, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Internal Reference No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "Internal Reference Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Vendor", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Responsible", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Due Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Journal", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Source Document", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Vendor Reference", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 11, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 12, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 13, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 14, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 15, "Due Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 16, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 17, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 18, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 19, "Due Amount", Style.contentTextBold(r2,'black','white'))
        
        row = r4
        s_no = 0
        local_amt, local_tax, local_total, local_due = 0.00, 0.00, 0.00, 0.00
        ref_local_amt, ref_local_tax, ref_local_total, ref_local_due = 0.00, 0.00, 0.00, 0.00
        for each in invoice_records:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 350
            sheet1.write(row, 0, s_no, Style.normal_left())
            if each.move_type == 'in_invoice':
                sheet1.write(row, 1, 'Regular', Style.normal_left())
            else:
                sheet1.write(row, 1, 'Refund', Style.normal_left())
            sheet1.write(row, 2, each.name, Style.normal_left())
            invoice_date = ""
            if each.invoice_date:
                invoice_date = each.invoice_date
                invoice_date = invoice_date.strftime('%d-%m-%Y')
                # invoice_date = time.strptime(each.invoice_date, "%Y-%m-%d")
                # invoice_date = time.strftime('%d-%m-%Y', invoice_date)
            sheet1.write(row, 3, invoice_date, Style.normal_left())
            sheet1.write(row, 4, (each.partner_id and each.partner_id.name_get()[0][1] or ""), Style.normal_left())
            sheet1.write(row, 5, (each.warehouse_id and each.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(row, 6, (each.user_id and each.user_id.name or ""), Style.normal_left())
            invoice_date_due = ""
            if each.invoice_date_due:
                invoice_date_due = each.invoice_date_due
                invoice_date_due = invoice_date_due.strftime('%d-%m-%Y')
                # invoice_date_due = time.strptime(each.invoice_date_due, "%Y-%m-%d")
                # invoice_date_due = time.strftime('%d-%m-%Y', invoice_date_due)
            sheet1.write(row, 7, invoice_date_due, Style.normal_left())
            sheet1.write(row, 8, (each.journal_id and each.journal_id.name or ""), Style.normal_left())
            sheet1.write(row, 9, (each.invoice_origin and each.invoice_origin or ""), Style.normal_left())
            sheet1.write(row, 10, (each.ref and each.ref or ""), Style.normal_left())
            sheet1.write(row, 11, (each.currency_id and each.currency_id.name or ""), Style.normal_left())
            if each.move_type == 'in_invoice':
                sheet1.write(row, 12, each.amount_untaxed and each.amount_untaxed or 0.00, Style.normal_num_right_3separator())
                sheet1.write(row, 13, each.amount_tax and each.amount_tax or 0.00, Style.normal_num_right_3separator())
                sheet1.write(row, 14, each.amount_total and each.amount_total or 0.00, Style.normal_num_right_3separator())
                sheet1.write(row, 15, each.amount_residual and each.amount_residual or 0.00, Style.normal_num_right_3separator())
                sheet1.write(row, 16, abs(each.company_amount_untaxed), Style.normal_num_right_3separator())
                sheet1.write(row, 17, abs(each.company_amount_tax), Style.normal_num_right_3separator())
                sheet1.write(row, 18, abs(each.company_amount_total), Style.normal_num_right_3separator())
                sheet1.write(row, 19, abs(each.company_amount_residual), Style.normal_num_right_3separator())
                local_amt += abs(each.company_amount_untaxed)
                local_tax += abs(each.company_amount_tax)
                local_total += abs(each.company_amount_total)
                local_due += abs(each.company_amount_residual)
            else:
                sheet1.write(row, 12, each.amount_untaxed and (-1 * each.amount_untaxed) or 0.00, Style.normal_num_right_3separator())
                sheet1.write(row, 13, each.amount_tax and (-1 * each.amount_tax) or 0.00, Style.normal_num_right_3separator())
                sheet1.write(row, 14, each.amount_total and (-1 * each.amount_total) or 0.00, Style.normal_num_right_3separator())
                sheet1.write(row, 15, each.amount_residual and (-1 * each.amount_residual) or 0.00, Style.normal_num_right_3separator())
                sheet1.write(row, 16, (-1 * abs(each.company_amount_untaxed)), Style.normal_num_right_3separator())
                sheet1.write(row, 17, (-1 * abs(each.company_amount_tax)), Style.normal_num_right_3separator())
                sheet1.write(row, 18, (-1 * abs(each.company_amount_total)), Style.normal_num_right_3separator())
                sheet1.write(row, 19, (-1 * abs(each.company_amount_residual)), Style.normal_num_right_3separator())
                ref_local_amt += -1 * abs(each.company_amount_untaxed)
                ref_local_tax += -1 * abs(each.company_amount_tax)
                ref_local_total += -1 * abs(each.company_amount_total)
                ref_local_due += -1 * abs(each.company_amount_residual)
        if self.type_account == 'in_invoice' or self.type_account == False: 
            row += 1
            sheet1.write_merge(row, row, 11, 15, 'Invoice Total', Style.groupByTitle())
            sheet1.write(row, 16, local_amt, Style.groupByTotal3Separator())
            sheet1.write(row, 17, local_tax, Style.groupByTotal3Separator())
            sheet1.write(row, 18, local_total, Style.groupByTotal3Separator())
            sheet1.write(row, 19, local_due, Style.groupByTotal3Separator())
        if self.type_account == 'in_refund' or self.type_account == False: 
            row += 1
            sheet1.write_merge(row, row, 11, 15, 'Refund Total', Style.groupByTitle())
            sheet1.write(row, 16, ref_local_amt, Style.groupByTotal3Separator())
            sheet1.write(row, 17, ref_local_tax, Style.groupByTotal3Separator())
            sheet1.write(row, 18, ref_local_total, Style.groupByTotal3Separator())
            sheet1.write(row, 19, ref_local_due, Style.groupByTotal3Separator())
        if self.type_account == False: 
            row += 1
            sheet1.write_merge(row, row, 11, 15, 'Grand Total', Style.groupByTitle())
            sheet1.write(row, 16, (local_amt + ref_local_amt), Style.groupByTotal3Separator())
            sheet1.write(row, 17, (local_tax + ref_local_tax), Style.groupByTotal3Separator())
            sheet1.write(row, 18, (local_total + ref_local_total), Style.groupByTotal3Separator())
            sheet1.write(row, 19, (local_due + ref_local_due), Style.groupByTotal3Separator())
        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()
        self.write({'name': report_name + '.xls', 'output':base64.encodebytes(binary_data)})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'purchase.invoice.register.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
