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

class AnalyticEntriesReportWizard(models.TransientModel):
    _name = 'analytic.entries.report.wizard'
    _description = 'Analytic Enteries Report Wizard'
    
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    journal_ids = fields.Many2many('account.journal', 'etc_analytic_entries_journal', 'analytic_entries_wizard_id', 'journal_id', string='Journal') 
    partner_ids = fields.Many2many('res.partner', 'etc_analytic_entries_partner', 'analytic_entries_wizard_id', 'partner_id', string='Partner')
    account_ids = fields.Many2many('account.account', 'etc_analytic_entries_account', 'analytic_entries_wizard_id', 'account_id', string='Account')
    analytic_account_ids = fields.Many2many('account.analytic.account', 'etc_analytic_entries_analytic_acc', 'analytic_entries_wizard_id', 'analytic_account_id', string='Analytic Account')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(AnalyticEntriesReportWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            warehouse_id = []
            for each in self.env.user.sudo().default_warehouse_ids:
                warehouse_id.append(each.id)
            if warehouse_id:
                for node in doc.xpath("//field[@name='partner_ids']"):
                    node.set('domain', "['|', ('supplier', '=', True), ('customer', '=', True), ('delivery_warehouse_id', 'in', " + str(warehouse_id) + "), ('parent_id', '=', False)]")
            res['arch'] = etree.tostring(doc)
        else:
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='partner_ids']"):
                node.set('domain', "['|', ('customer', '=', True), ('supplier', '=', True), ('parent_id', '=', False)]")
            res['arch'] = etree.tostring(doc)
        return res
    
    @api.multi
    def action_report(self):
        move_obj = self.env['account.move.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Analytic Entries Report"
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date) 
        
        all_journal_ids = []
        journal_list = []
        journal_str = ""
        
        all_partners_children = {}
        all_partner_ids = []
        partner_list = []
        partner_str = ""
        
        all_account_ids = []
        account_list = []
        account_str = ""
        
        all_analytic_account_ids = []
        analytic_account_list = []
        analytic_account_str = ""
        
        domain_default = []
        domain_default = [('date', '>=', self.date_from), ('date', '<=', self.date_to), ('analytic_account_id', '!=', False), ('move_id.state', '=', 'posted')]
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
        if self.partner_ids:
            for each_id in self.partner_ids:
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id] 
                partner_list.append(each_id.name)
                partner_str = str(partner_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                domain_default = domain_default + [('partner_id', 'in', tuple(all_partner_ids))]
                filters += ", Partner : "+ partner_str
            else:
                domain_default = domain_default + [('partner_id', '=', all_partner_ids[0])]
                filters += ", Partner : "+ partner_str
        if self.account_ids:
            for each_id in self.account_ids:
                all_account_ids.append(each_id.id)
                account_list.append(each_id.name)
                account_str = str(account_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_account_ids) > 1:
                domain_default = domain_default + [('account_id', 'in', tuple(all_account_ids))]
                filters += ", Account : "+ account_str
            else:
                domain_default = domain_default + [('account_id', '=', all_account_ids[0])]
                filters += ", Account : "+ account_str
        if self.analytic_account_ids:
            for each_id in self.analytic_account_ids:
                all_analytic_account_ids.append(each_id.id)
                analytic_account_list.append(each_id.name)
                analytic_account_str = str(analytic_account_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_analytic_account_ids) > 1:
                domain_default = domain_default + [('analytic_account_id', 'in', tuple(all_analytic_account_ids))]
                filters += ", Analytic Account : "+ analytic_account_str
            else:
                domain_default = domain_default + [('analytic_account_id', '=', all_analytic_account_ids[0])]
                filters += ", Analytic Account : "+ analytic_account_str

        move_records = move_obj.sudo().search(domain_default, order="date asc")

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
        sheet1.col(4).width = 7500
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 5000
        sheet1.col(7).width = 7000
        sheet1.col(8).width = 5500
        sheet1.col(9).width = 4000
        sheet1.col(10).width = 4000
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 4000
    
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
        sheet1.write_merge(r1, r1, 0, 12, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 12, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 12, title2, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Journal Entry", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "Journal", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Label", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Reference", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Partner", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Account", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Analytic Account", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Debit", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Credit", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 11, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 12, "Amount Currency", Style.contentTextBold(r2,'black','white'))

        row = r4
        s_no = 0
        debit, credit, amount_currency = 0.00, 0.00, 0.00
        for each in move_records:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 300
            sheet1.write(row, 0, s_no, Style.normal_left())
            date = ""
            if each.date:
                date = time.strptime(each.date, "%Y-%m-%d")
                date = time.strftime('%d-%m-%Y', date)
            sheet1.write(row, 1, date, Style.normal_left())
            sheet1.write(row, 2, (each.move_id and each.move_id.name or ""), Style.normal_left())
            sheet1.write(row, 3, (each.journal_id and each.journal_id.name or ""), Style.normal_left())
            sheet1.write(row, 4, (each.name and each.name or ""), Style.normal_left())
            sheet1.write(row, 5, (each.ref and each.ref or ""), Style.normal_left())
            sheet1.write(row, 6, (each.partner_id and each.partner_id.name or ""), Style.normal_left())
            sheet1.write(row, 7, (each.account_id and (each.account_id.code + ' ' + each.account_id.name) or ""), Style.normal_left())
            sheet1.write(row, 8, (each.analytic_account_id and each.analytic_account_id.name or ""), Style.normal_left())
            sheet1.write(row, 9, (each.debit and each.debit or 0.00), Style.normal_num_right_3separator())
            sheet1.write(row, 10, (each.credit and each.credit or 0.00), Style.normal_num_right_3separator())
            sheet1.write(row, 11, (each.currency_id and each.currency_id.name or ""), Style.normal_left())
            sheet1.write(row, 12, each.amount_currency, Style.normal_num_right_3separator())
            date_maturity = ""
            if each.date_maturity:
                date_maturity = time.strptime(each.date_maturity, "%Y-%m-%d")
                date_maturity = time.strftime('%d-%m-%Y', date_maturity)
            debit += each.debit
            credit += each.credit
            amount_currency += each.amount_currency
        row += 1
        sheet1.write_merge(row, row, 0, 8, 'Total', Style.groupByTitle())
        sheet1.write(row, 9, debit, Style.groupByTotal3Separator())
        sheet1.write(row, 10, credit, Style.groupByTotal3Separator())
        sheet1.write_merge(row, row, 11, 12, amount_currency, Style.groupByTotal3Separator())
            
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'analytic.entries.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
