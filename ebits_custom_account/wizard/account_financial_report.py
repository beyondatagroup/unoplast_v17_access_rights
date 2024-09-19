# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
import xlwt
import cStringIO
import base64
import xlrd
import parser
import json
from lxml import etree

class AccountingreportOutput(models.TransientModel):
    _name = "accounting.report.output"
    _description = "Account Balance Report Output"
    
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='Format', readonly=True)

class AccountingReport(models.TransientModel):
    _inherit = "accounting.report"
    
    hierarchy_type = fields.Selection([('hierarchy', 'Hierarchy Print'), ('normal', 'Normal Print')], string='Print Type', default="hierarchy")
    other_currency = fields.Boolean(string='Show Other Currency')
    
    @api.multi
    @api.onchange('hierarchy_type')
    def _onchange_hierarchy_type(self):
        if self.hierarchy_type != 'hierarchy':
            self.other_currency = False
    
    @api.multi
    @api.onchange('enable_filter')
    def _onchange_enable_filter(self):
        if self.enable_filter:
            self.debit_credit = False
    
    def _print_report(self, data):
        data['form'].update(self.read(['date_from_cmp', 'debit_credit', 'date_to_cmp', 'filter_cmp', 'account_report_id', 'enable_filter', 'label_filter', 'target_move', 'hierarchy_type', 'other_currency'])[0])
        if data['form']['hierarchy_type'] == 'hierarchy':
            return self.env['report'].with_context(landscape=True).get_action(self, 'ebits_custom_account.report_financial_custom_hierarchy', data=data)
        else:
            return self.env['report'].with_context(landscape=True).get_action(self, 'account.report_financial', data=data)
    
    def _compute_account_balance(self, accounts):
        """ compute the balance, debit and credit for the provided accounts
        """
        mapping = {
            'balance': "COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance",
            'debit': "COALESCE(SUM(debit), 0) as debit",
            'credit': "COALESCE(SUM(credit), 0) as credit",
        }

        res = {}
        for account in accounts:
            res[account.id] = dict((fn, 0.0) for fn in mapping.keys())
        if accounts:
            tables, where_clause, where_params = self.env['account.move.line']._query_get()
            tables = tables.replace('"', '') if tables else "account_move_line"
            wheres = [""]
            if where_clause.strip():
                wheres.append(where_clause.strip())
            filters = " AND ".join(wheres)
            request = "SELECT account_id as id, " + ', '.join(mapping.values()) + \
                       " FROM " + tables + \
                       " WHERE account_id IN %s " \
                            + filters + \
                       " GROUP BY account_id"
            params = (tuple(accounts._ids),) + tuple(where_params)
            self.env.cr.execute(request, params)
            for row in self.env.cr.dictfetchall():
                res[row['id']] = row
        return res

    def _compute_report_balance(self, reports):
        '''returns a dictionary with key=the ID of a record and value=the credit, debit and balance amount
           computed for this record. If the record is of type :
               'accounts' : it's the sum of the linked accounts
               'account_type' : it's the sum of leaf accoutns with such an account_type
               'account_report' : it's the amount of the related report
               'sum' : it's the sum of the children of this record (aka a 'view' record)'''
        res = {}
        fields = ['credit', 'debit', 'balance']
        for report in reports:
            if report.id in res:
                continue
            res[report.id] = dict((fn, 0.0) for fn in fields)
            if report.type == 'accounts':
                # it's the sum of the linked accounts
                res[report.id]['account'] = self._compute_account_balance(report.account_ids)
                for value in res[report.id]['account'].values():
                    for field in fields:
                        res[report.id][field] += value.get(field)
            elif report.type == 'account_type':
                # it's the sum the leaf accounts with such an account type
                accounts = self.env['account.account'].search([('user_type_id', 'in', report.account_type_ids.ids)])
                res[report.id]['account'] = self._compute_account_balance(accounts)
                for value in res[report.id]['account'].values():
                    for field in fields:
                        res[report.id][field] += value.get(field)
            elif report.type == 'account_report' and report.account_report_id:
                # it's the amount of the linked report
                res2 = self._compute_report_balance(report.account_report_id)
                for key, value in res2.items():
                    for field in fields:
                        res[report.id][field] += value[field]
            elif report.type == 'sum':
                # it's the sum of the children of this account.report
                res2 = self._compute_report_balance(report.children_ids)
                for key, value in res2.items():
                    for field in fields:
                        res[report.id][field] += value[field]
        return res

    def get_account_lines(self, data):
        lines = []
        account_report = self.env['account.financial.report'].search([('id', '=', data['account_report_id'][0])])
        child_reports = account_report._get_children_by_order()
        res = self.with_context(data.get('used_context'))._compute_report_balance(child_reports)
        if data['enable_filter']:
            comparison_res = self.with_context(data.get('comparison_context'))._compute_report_balance(child_reports)
            for report_id, value in comparison_res.items():
                res[report_id]['comp_bal'] = value['balance']
                report_acc = res[report_id].get('account')
                if report_acc:
                    for account_id, val in comparison_res[report_id].get('account').items():
                        report_acc[account_id]['comp_bal'] = val['balance']

        for report in child_reports:
            vals = {
                'name': report.name,
                'balance': res[report.id]['balance'] * report.sign,
                'type': 'report',
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type or False, #used to underline the financial report balances
            }
            if data['debit_credit']:
                vals['debit'] = res[report.id]['debit']
                vals['credit'] = res[report.id]['credit']

            if data['enable_filter']:
                vals['balance_cmp'] = res[report.id]['comp_bal'] * report.sign

            lines.append(vals)
            if report.display_detail == 'no_detail':
                #the rest of the loop is used to display the details of the financial report, so it's not needed here.
                continue

            if res[report.id].get('account'):
                sub_lines = []
                for account_id, value in res[report.id]['account'].items():
                    #if there are accounts to display, we add them to the lines with a level equals to their level in
                    #the COA + 1 (to avoid having them with a too low level that would conflicts with the level of data
                    #financial reports for Assets, liabilities...)
                    flag = False
                    account = self.env['account.account'].browse(account_id)
                    vals = {
                        'name': account.code + ' ' + account.name,
                        'balance': value['balance'] * report.sign or 0.0,
                        'type': 'account',
                        'level': report.display_detail == 'detail_with_hierarchy' and 4,
                        'account_type': account.internal_type,
                    }
                    if data['debit_credit']:
                        vals['debit'] = value['debit']
                        vals['credit'] = value['credit']
                        if not account.company_id.currency_id.is_zero(vals['debit']) or not account.company_id.currency_id.is_zero(vals['credit']):
                            flag = True
                    if not account.company_id.currency_id.is_zero(vals['balance']):
                        flag = True
                    if data['enable_filter']:
                        vals['balance_cmp'] = value['comp_bal'] * report.sign
                        if not account.company_id.currency_id.is_zero(vals['balance_cmp']):
                            flag = True
                    if flag:
                        sub_lines.append(vals)
                lines += sorted(sub_lines, key=lambda sub_line: sub_line['name'])
        return lines
        
    def get_account_lines_hierarchy(self, data):
        account_obj = self.env['account.account']
        currency_obj = self.env['res.currency']
        lines = []
        account_report = self.env['account.financial.report'].search([('id', '=', data['account_report_id'][0])])
        child_reports = account_report.with_context(data.get('used_context'))._get_children_by_order()
        for report in child_reports:
            vals = {
                'name': report.name,
                'balance': report.balance * report.sign or 0.0,
                'type': 'report',
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type =='sum' and 'view' or False,
            }
            if data['other_currency']:
                vals['amount_currency'] = 0.00
                vals['currency_symbol'] = ""
            if data['debit_credit']:
                vals['debit'] = report.debit
                vals['credit'] = report.credit
                
            if data['enable_filter']:
                vals['balance_cmp'] = report.with_context(data.get('comparison_context')).balance * report.sign
                if data['other_currency']:
                    vals['balance_cmp_amount_currency'] = 0.00
                    vals['balance_cmp_currency_symbol'] = ""
                
            lines.append(vals)
            
            account_ids = []
            if report.display_detail == 'no_detail':
                continue
                
            if report.type == 'accounts' and report.account_ids:
                account_ids = account_obj.with_context(data.get('used_context'))._get_children_and_consol([x.id for x in report.account_ids])
            elif report.type == 'account_type' and report.account_type_ids:
                account_ids = account_obj.with_context(data.get('used_context')).search([('user_type_id','in', [x.id for x in report.account_type_ids])])
            if account_ids:
                sub_lines = []
                for account in account_ids:
                    if report.display_detail == 'detail_flat' and account.internal_type == 'view':
                        continue
                    flag = False
                    vals = {
                        'name': account.code + ' ' + account.name,
                        'balance':  account.balance != 0 and account.balance * report.sign or account.balance,
                        'type': 'account',
                        'level': report.display_detail == 'detail_with_hierarchy' and min(account.level + 1,6) or 6, #account.level + 1
                        'account_type': account.internal_type,
                    }
                    
                    if data['other_currency']:
                        vals['amount_currency'] = account.balance_amount_currency
                        vals['currency_symbol'] = account.currency_id and account.currency_id.symbol or ""
                        
                    if data['debit_credit']:
                        vals['debit'] = account.debit
                        vals['credit'] = account.credit
                        if not account.company_id.currency_id.is_zero(vals['debit']) or not account.company_id.currency_id.is_zero(vals['credit']):
                            flag = True
                    if not account.company_id.currency_id.is_zero(vals['balance']):
                        flag = True
                    if data['enable_filter']:
                        vals['balance_cmp'] = account.balance * report.sign
                        if data['other_currency']:
                            vals['balance_cmp_amount_currency'] = account.balance_amount_currency
                            vals['balance_cmp_currency_symbol'] = account.currency_id and account.currency_id.symbol or ""
                        if not account.company_id.currency_id.is_zero(vals['balance_cmp']):
                            flag = True
                    if flag:
                        sub_lines.append(vals)
                lines += sorted(sub_lines, key=lambda sub_line: sub_line['name'])
        return lines
    

    @api.multi
    def print_excel_report(self):
        self.ensure_one()
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['date_from', 'date_to', 'journal_ids', 'target_move'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        res = self.check_report()
        data['form'].update(self.read(['debit_credit', 'enable_filter', 'label_filter', 'account_report_id', 'date_from_cmp', 'date_to_cmp', 'journal_ids', 'filter_cmp', 'target_move', 'hierarchy_type', 'other_currency'])[0])
#        for field in ['account_report_id']:
#            if isinstance(data['form'][field], tuple):
#                data['form'][field] = data['form'][field][0]
        comparison_context = self._build_comparison_context(data)
        data['form']['comparison_context'] = comparison_context
        if data['form']['hierarchy_type'] == 'hierarchy':
            report_lines = self.get_account_lines_hierarchy(data['form'])
        else:
            report_lines = self.get_account_lines(data['form'])
        
        report_name = data['form']['account_report_id'][1]
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(6)
        sheet1.show_grid = False 
        sheet1.col(0).width = 15000
        sheet1.col(1).width = 5000
        sheet1.col(2).width = 5000
        sheet1.col(3).width = 5000
        sheet1.col(4).width = 1500
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 4000
        sheet1.col(7).width = 4000
        sheet1.col(8).width = 4000
        sheet1.col(9).width = 1000
        sheet1.col(10).width = 4000
        sheet1.col(11).width = 1000
        sheet1.col(12).width = 4000
        sheet1.col(13).width = 4000
        sheet1.col(14).width = 4000
        sheet1.col(15).width = 4000
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        r5 = 4
        sheet1.row(r1).height = 600
        sheet1.row(r2).height = 600
        sheet1.row(r3).height = 350
        sheet1.row(r4).height = 350 
        sheet1.row(r5).height = 256
        
        title = report_name
        sheet1.write(r3, 0, "Target Move", Style.subTitle())
        if data['form']['target_move'] == 'all':
            sheet1.write(r4, 0, "All Entries", Style.subTitle())
        if data['form']['target_move'] == 'posted':
            sheet1.write(r4, 0, "All Posted Entries", Style.subTitle())
        date_from = date_to = False
        if data['form']['date_from']:
            date_from = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")
            date_from = datetime.strftime(date_from, "%d-%m-%Y")
            sheet1.write(r3, 1, "Date From", Style.subTitle())
            sheet1.write(r4, 1, date_from, Style.normal_date_alone())
        else:
            sheet1.write(r3, 1, "", Style.subTitle())
            sheet1.write(r4, 1, "", Style.subTitle())
        if data['form']['date_to']:
            date_to = datetime.strptime(data['form']['date_to'], "%Y-%m-%d")
            date_to = datetime.strftime(date_to, "%d-%m-%Y")
            sheet1.write(r3, 2, "Date To", Style.subTitle())
            sheet1.write(r4, 2, date_to, Style.normal_date_alone())
        else:
            sheet1.write(r3, 2, "", Style.subTitle())
            sheet1.write(r4, 2, "", Style.subTitle())
        row = r5
        if data['form']['debit_credit'] == True and data['form']['other_currency'] == True:
            sheet1.write_merge(r1, r1, 0, 6, self.env.user.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 6, title, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 3, 6, "", Style.subTitle())
            sheet1.write_merge(r4, r4, 3, 6, "", Style.subTitle())
            row = row + 1
            sheet1.row(row).height = 256 * 3
            sheet1.write(row, 0, "Account", Style.subTitle_color())
            sheet1.write(row, 1, "Debit", Style.subTitle_color())
            sheet1.write(row, 2, "Credit", Style.subTitle_color())
            sheet1.write(row, 3, "Balance(Tsh)", Style.subTitle_color())
            sheet1.write(row, 4, "", Style.subTitle_color())
            sheet1.write(row, 5, "Balance(Other)", Style.subTitle_color())
            sheet1.write(row, 6, "", Style.subTitle_color())
            for each in report_lines:
                if each['level'] != 0:
                    name = ""
                    gap = " "
                    name = each['name']
                    left = Style.normal_left()
                    right = Style.normal_num_right_3separator()
                    if each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.normal_left()
                        right = Style.normal_num_right_3separator()
                    if not each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    if each.get('level') == 1:
                        gap = " " * each['level']
                    if each.get('account_type') == 'view':
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    row = row + 1
                    sheet1.row(row).height = 400
                    name = gap + name
                    sheet1.write(row, 0, name, left)
                    sheet1.write(row, 1, each['debit'], right)
                    sheet1.write(row, 2, each['credit'], right)
                    sheet1.write(row, 3, each['balance'], right)
                    sheet1.write(row, 4, self.env.user.company_id.currency_id.symbol, left)
                    if each['currency_symbol']:
                        sheet1.write(row, 5, each['amount_currency'], right)
                        sheet1.write(row, 6, each['currency_symbol'], left)
                    else:
                        sheet1.write(row, 5, "", right)
                        sheet1.write(row, 6, "", left)
                        
        if data['form']['debit_credit'] == True and not data['form']['other_currency']:
            sheet1.write_merge(r1, r1, 0, 4, self.env.user.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 4, title, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 3, 4, "", Style.subTitle())
            sheet1.write_merge(r4, r4, 3, 4, "", Style.subTitle())
            row = row + 1
            sheet1.row(row).height = 256 * 3
            sheet1.write(row, 0, "Account", Style.subTitle_color())
            sheet1.write(row, 1, "Debit", Style.subTitle_color())
            sheet1.write(row, 2, "Credit", Style.subTitle_color())
            sheet1.write(row, 3, "Balance", Style.subTitle_color())
            sheet1.write(row, 4, "", Style.subTitle_color())
            for each in report_lines:
                if each['level'] != 0:
                    name = ""
                    gap = " "
                    name = each['name']
                    left = Style.normal_left()
                    right = Style.normal_num_right_3separator()
                    if each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.normal_left()
                        right = Style.normal_num_right_3separator()
                    if not each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    if each.get('level') == 1:
                        gap = " " * each['level']
                    if each.get('account_type') == 'view':
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    row = row + 1
                    sheet1.row(row).height = 400
                    name = gap + name
                    sheet1.write(row, 0, name, left)
                    sheet1.write(row, 1, each['debit'], right)
                    sheet1.write(row, 2, each['credit'], right)
                    sheet1.write(row, 3, each['balance'], right)
                    sheet1.write(row, 4, self.env.user.company_id.currency_id.symbol, left)
            
        if not data['form']['enable_filter'] and not data['form']['debit_credit'] and data['form']['other_currency'] == True:
            sheet1.write_merge(r1, r1, 0, 4, self.env.user.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 4, title, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 3, 4, "", Style.subTitle())
            sheet1.write_merge(r4, r4, 3, 4, "", Style.subTitle())
            row = row + 1
            sheet1.row(row).height = 256 * 3
            sheet1.write(row, 0, "Name", Style.subTitle_color())
            sheet1.write(row, 1, "Balance(Tsh)", Style.subTitle_color())
            sheet1.write(row, 2, "", Style.subTitle_color())
            sheet1.write(row, 3, "Balance(Other)", Style.subTitle_color())
            sheet1.write(row, 4, "", Style.subTitle_color())
            for each in report_lines:
                if each['level'] != 0:
                    name = ""
                    gap = " "
                    name = each['name']
                    left = Style.normal_left()
                    right = Style.normal_num_right_3separator()
                    if each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.normal_left()
                        right = Style.normal_num_right_3separator()
                    if not each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    if each.get('level') == 1:
                        gap = " " * each['level']
                    if each.get('account_type') == 'view':
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    row = row + 1
                    sheet1.row(row).height = 400
                    name = gap + name
                    sheet1.write(row, 0, name, left)
                    sheet1.write(row, 1, each['balance'], right)
                    sheet1.write(row, 2, self.env.user.company_id.currency_id.symbol, left)
                    if each['currency_symbol']:
                        sheet1.write(row, 3, each['amount_currency'], right)
                        sheet1.write(row, 4, each['currency_symbol'], left)
                    else:
                        sheet1.write(row, 3, "", right)
                        sheet1.write(row, 4, "", left)
                    
        if not data['form']['enable_filter'] and not data['form']['debit_credit'] and not data['form']['other_currency']:
            sheet1.write_merge(r1, r1, 0, 2, self.env.user.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 2, title, Style.sub_title_color())
            row = row + 1
            sheet1.row(row).height = 256 * 3
            sheet1.write(row, 0, "Name", Style.subTitle_color())
            sheet1.write(row, 1, "Balance", Style.subTitle_color())
            sheet1.write(row, 2, "", Style.subTitle_color())
            for each in report_lines:
                if each['level'] != 0:
                    name = ""
                    gap = " "
                    name = each['name']
                    left = Style.normal_left()
                    right = Style.normal_num_right_3separator()
                    if each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.normal_left()
                        right = Style.normal_num_right_3separator()
                    if not each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    if each.get('level') == 1:
                        gap = " " * each['level']
                    if each.get('account_type') == 'view':
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    row = row + 1
                    sheet1.row(row).height = 400
                    name = gap + name
                    sheet1.write(row, 0, name, left)
                    sheet1.write(row, 1, each['balance'], right)
                    sheet1.write(row, 2, self.env.user.company_id.currency_id.symbol, left)
                    
        if data['form']['enable_filter'] and not data['form']['debit_credit'] and data['form']['other_currency'] == True:
            sheet1.write_merge(r1, r1, 0, 7, self.env.user.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 7, title, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 3, 7, "", Style.subTitle())
            sheet1.write_merge(r4, r4, 3, 7, "", Style.subTitle())
            row = row + 1
            sheet1.row(row).height = 256 * 3
            sheet1.write(row, 0, "Name", Style.subTitle_color())
            sheet1.write(row, 1, "Balance(Tsh)", Style.subTitle_color())
            sheet1.write(row, 2, "", Style.subTitle_color())
            sheet1.write(row, 3, "Balance(Other)", Style.subTitle_color())
            sheet1.write(row, 4, "", Style.subTitle_color())
            sheet1.write(row, 5, data['form']['label_filter'] + "(Tsh)", Style.subTitle_color())
            sheet1.write(row, 6, data['form']['label_filter'] + "(Other)", Style.subTitle_color())
            sheet1.write(row, 7, "", Style.subTitle_color())
            for each in report_lines:
                if each['level'] != 0:
                    name = ""
                    gap = " "
                    name = each['name']
                    left = Style.normal_left()
                    right = Style.normal_num_right_3separator()
                    if each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.normal_left()
                        right = Style.normal_num_right_3separator()
                    if not each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    if each.get('level') == 1:
                        gap = " " * each['level']
                    if each.get('account_type') == 'view':
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    row = row + 1
                    sheet1.row(row).height = 400
                    name = gap + name
                    sheet1.write(row, 0, name, left)
                    sheet1.write(row, 1, each['balance'], right)
                    sheet1.write(row, 2, self.env.user.company_id.currency_id.symbol, left)
                    if each['currency_symbol']:
                        sheet1.write(row, 3, each['amount_currency'], right)
                        sheet1.write(row, 4, each['currency_symbol'], left)
                    else:
                        sheet1.write(row, 3, "", right)
                        sheet1.write(row, 4, "", left)
                    sheet1.write(row, 5, each['balance_cmp'], right)
                    if each['balance_cmp_currency_symbol']:
                        sheet1.write(row, 6, each['balance_cmp_amount_currency'], right)
                        sheet1.write(row, 7, each['balance_cmp_currency_symbol'], left)
                    else:
                        sheet1.write(row, 6, "", right)
                        sheet1.write(row, 7, "", left)
                    
        if data['form']['enable_filter'] and not data['form']['debit_credit'] and not data['form']['other_currency']:
            sheet1.write_merge(r1, r1, 0, 3, self.env.user.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 3, title, Style.sub_title_color())
            sheet1.write(r3, 3, "", Style.subTitle())
            sheet1.write(r4, 3, "", Style.subTitle())
            row = row + 1
            sheet1.row(row).height = 256 * 3
            sheet1.write(row, 0, "Name", Style.subTitle_color())
            sheet1.write(row, 1, "Balance", Style.subTitle_color())
            sheet1.write(row, 2, "", Style.subTitle_color())
            sheet1.write(row, 3, data['form']['label_filter'], Style.subTitle_color())
            for each in report_lines:
                if each['level'] != 0:
                    name = ""
                    gap = " "
                    name = each['name']
                    left = Style.normal_left()
                    right = Style.normal_num_right_3separator()
                    if each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.normal_left()
                        right = Style.normal_num_right_3separator()
                    if not each.get('level') > 3:
                        gap = " " * (each['level'] * 5)
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    if each.get('level') == 1:
                        gap = " " * each['level']
                    if each.get('account_type') == 'view':
                        left = Style.subTitle_sub_color_left()
                        right = Style.subTitle_float_sub_color()
                    row = row + 1
                    sheet1.row(row).height = 400
                    name = gap + name
                    sheet1.write(row, 0, name, left)
                    sheet1.write(row, 1, each['balance'], right)
                    sheet1.write(row, 2, self.env.user.company_id.currency_id.symbol, left)
                    sheet1.write(row, 3, each['balance_cmp'], right)
                    
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.env.cr.execute(""" DELETE FROM accounting_report_output""")
        attach_id = self.env['accounting.report.output'].create({'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'accounting.report.output',
                'res_id': attach_id.id,
                'type': 'ir.actions.act_window',
                'target': 'new'
                }
