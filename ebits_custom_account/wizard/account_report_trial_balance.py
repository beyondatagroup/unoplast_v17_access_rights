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

class AccountBalanceReportOutput(models.TransientModel):
    _name = "account.balance.report.output"
    _description = "Account Balance Report Output"
    
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='Format', readonly=True)

class AccountBalanceReport(models.TransientModel):
    _inherit = 'account.balance.report'
    
    def _get_accounts(self, accounts, display_account):
        """ compute the balance, debit and credit for the provided accounts
            :Arguments:
                `accounts`: list of accounts record,
                `display_account`: it's used to display either all accounts or those accounts which balance is > 0
            :Returns a list of dictionary of Accounts with following key and value
                `name`: Account name,
                `code`: Account code,
                `credit`: total amount of credit,
                `debit`: total amount of debit,
                `balance`: total amount of balance,
        """

        account_result = {}
        # Prepare sql query base on selected parameters from wizard
        tables, where_clause, where_params = self.env['account.move.line']._query_get()
        tables = tables.replace('"','')
        if not tables:
            tables = 'account_move_line'
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        filters = " AND ".join(wheres)
        # compute the balance, debit and credit for the provided accounts
        request = ("SELECT account_id AS id, SUM(debit) AS debit, SUM(credit) AS credit, (SUM(debit) - SUM(credit)) AS balance, SUM(amount_currency) AS amount_currency" +\
                   " FROM " + tables + " WHERE account_id IN %s " + filters + " GROUP BY account_id")
        params = (tuple(accounts.ids),) + tuple(where_params)
        self.env.cr.execute(request, params)
        for row in self.env.cr.dictfetchall():
            account_result[row.pop('id')] = row

        account_res = []
        for account in accounts:
            res = dict((fn, 0.0) for fn in ['credit', 'debit', 'balance', 'amount_currency'])
            currency = account.currency_id and account.currency_id or account.company_id.currency_id
            res['code'] = account.code
            res['name'] = account.name
            res['currency'] = currency
            if account.id in account_result.keys():
                res['debit'] = account_result[account.id].get('debit')
                res['credit'] = account_result[account.id].get('credit')
                res['balance'] = account_result[account.id].get('balance')
                res['amount_currency'] = account_result[account.id].get('amount_currency')
            if display_account == 'all':
                account_res.append(res)
            if display_account in ['movement', 'not_zero'] and not currency.is_zero(res['balance']):
                account_res.append(res)
        return account_res
    
    @api.multi
    def print_excel_report(self):
        self.ensure_one()
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['date_from', 'date_to', 'journal_ids', 'target_move', 'display_account'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        data = self.pre_print_report(data)
        display_account = data['form'].get('display_account')
        accounts = self.env['account.account'].search([('internal_type', '!=', 'view')])
        account_res = self.with_context(data['form'].get('used_context'))._get_accounts(accounts, display_account)
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet("Trial Balance")
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(6)
        sheet1.show_grid = False 
        sheet1.col(0).width = 4000
        sheet1.col(1).width = 9000
        sheet1.col(2).width = 5000
        sheet1.col(3).width = 5000
        sheet1.col(4).width = 5000
        sheet1.col(5).width = 1500
        sheet1.col(6).width = 5000
        sheet1.col(7).width = 1500

        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        r5 = 4
        sheet1.row(r1).height = 600
        sheet1.row(r2).height = 600
        sheet1.row(r3).height = 350
        sheet1.row(r4).height = 550 
        sheet1.row(r5).height = 256
        
        title = "Trial Balance"
        sheet1.write_merge(r1, r1, 0, 7, self.env.user.company_id.name, Style.title_color())
        sheet1.write_merge(r2, r2, 0, 7, title, Style.sub_title_color())
        
        sheet1.write_merge(r3, r3, 0, 1, "Display Account", Style.subTitle())
        if data['form']['display_account'] == 'all':
            sheet1.write_merge(r4, r4, 0, 1, "All accounts", Style.subTitle())
        if data['form']['display_account'] == 'movement':
            sheet1.write_merge(r4, r4, 0, 1, "With movements", Style.subTitle())
        if data['form']['display_account'] == 'not_zero':
            sheet1.write_merge(r4, r4, 0, 1, "With balance not equal to zero", Style.subTitle())
            
        sheet1.write_merge(r3, r3, 2, 3, "Target Move", Style.subTitle())
        if data['form']['target_move'] == 'all':
            sheet1.write_merge(r4, r4, 2, 3, "All Entries", Style.subTitle())
        if data['form']['target_move'] == 'posted':
            sheet1.write_merge(r4, r4, 2, 3, "All Posted Entries", Style.subTitle())
            
        
        date_from = date_to = False
        if data['form']['date_from']:
            date_from = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")
            date_from = datetime.strftime(date_from, "%d-%m-%Y")
            sheet1.write(r3, 4, "Date From", Style.subTitle())
            sheet1.write(r4, 4, date_from, Style.normal_date_alone())
        else:
            sheet1.write(r3, 4, "", Style.subTitle())
            sheet1.write(r4, 4, "", Style.subTitle())
        if data['form']['date_to']:
            date_to = datetime.strptime(data['form']['date_to'], "%Y-%m-%d")
            date_to = datetime.strftime(date_to, "%d-%m-%Y")
            sheet1.write(r3, 5, "Date To", Style.subTitle())
            sheet1.write(r4, 5, date_to, Style.normal_date_alone())
        else:
            sheet1.write(r3, 5, "", Style.subTitle())
            sheet1.write(r4, 5, "", Style.subTitle())
        sheet1.write_merge(r3, r3, 6, 7, "", Style.subTitle())
        sheet1.write_merge(r4, r4, 6, 7, "LC - Local Currency\nTC - Transaction Currency", Style.subTitle())
            
        row = r5 + 1
        sheet1.row(row).height = 256 * 3
        sheet1.write(row, 0, "Code", Style.subTitle_color())
        sheet1.write(row, 1, "Account", Style.subTitle_color())
        sheet1.write(row, 2, "Debit", Style.subTitle_color())
        sheet1.write(row, 3, "Credit", Style.subTitle_color())
        sheet1.write(row, 4, "Balance", Style.subTitle_color())
        sheet1.write(row, 5, "LC", Style.subTitle_color())
        sheet1.write(row, 6, "Balance", Style.subTitle_color())
        sheet1.write(row, 7, "TC", Style.subTitle_color())
        for each in account_res:
            row = row + 1
            sheet1.row(row).height = 400
            name = ""
            name = (each['code'] and each['code'] or "") + (each['name'] and each['name'] or "")
            sheet1.write(row, 0, each['code'], Style.normal_left())
            sheet1.write(row, 1, each['name'], Style.normal_left())
            sheet1.write(row, 2, each['debit'], Style.normal_num_right_3separator())
            sheet1.write(row, 3, each['credit'], Style.normal_num_right_3separator())
            sheet1.write(row, 4, each['balance'], Style.normal_num_right_3separator())
            sheet1.write(row, 5, self.env.user.company_id.currency_id.symbol, Style.normal_left())
            if each['currency'].id != self.env.user.company_id.currency_id.id:
                sheet1.write(row, 6, each['amount_currency'], Style.normal_num_right_3separator())
                sheet1.write(row, 7, each['currency'].symbol, Style.normal_left())
            else:
                sheet1.write(row, 6, "", Style.normal_left())
                sheet1.write(row, 7, "", Style.normal_left())
                
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.env.cr.execute(""" DELETE FROM account_balance_report_output""")
        attach_id = self.env['account.balance.report.output'].create({'name': "Trial Balance" + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.balance.report.output',
                'res_id': attach_id.id,
                'type': 'ir.actions.act_window',
                'target': 'new'
                }
