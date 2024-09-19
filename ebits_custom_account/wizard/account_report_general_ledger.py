# -*- coding: utf-8 -*-
# Part of EBITS TechCon

from datetime import datetime
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
import xlwt
import cStringIO
import base64

class AccountGeneralLedgerOutput(models.TransientModel):
    _name = "account.report.general.ledger.output"
    _description = "Account General Ledger Output"
    
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='Format', readonly=True)

class AccountReportGeneralLedger(models.TransientModel):
    _inherit = "account.report.general.ledger"
    
    general_account_ids = fields.Many2many('account.account', 'account_acc_report_general_ledger_account_rel', 'ledger_id', 'account_id', string='Individual Account(s)')
    
    @api.model
    def default_get(self, fields):
        res = super(AccountReportGeneralLedger, self).default_get(fields)
        if self.env.context.get('active_ids'):
            account_obj = self.env['account.account']
            account = account_obj.browse(self.env.context.get('active_ids'))
            if account:
                res.update({'general_account_ids': [(6, 0, account.ids)],})
        return res
    
    def _print_report(self, data):
        data = self.pre_print_report(data)
        data['form'].update(self.read(['initial_balance', 'sortby', 'general_account_ids'])[0])
        if data['form'].get('initial_balance') and not data['form'].get('date_from'):
            raise UserError(_("You must define a Start Date"))
        records = self.env[data['model']].browse(data.get('ids', []))
        return self.env['report'].with_context(landscape=True).get_action(records, 'account.report_generalledger', data=data)
    
    def _get_account_move_entry(self, accounts, init_balance, sortby, display_account):
        """
        :param:
                accounts: the recordset of accounts
                init_balance: boolean value of initial_balance
                sortby: sorting by date or partner and journal
                display_account: type of account(receivable, payable and both)

        Returns a dictionary of accounts with following key and value {
                'code': account code,
                'name': account name,
                'debit': sum of total debit amount,
                'credit': sum of total credit amount,
                'balance': total balance,
                'amount_currency': sum of amount_currency,
                'move_lines': list of move line
        }
        """
        cr = self.env.cr
        MoveLine = self.env['account.move.line']
        AccountObj = self.env['account.account']
        move_lines = dict(map(lambda x: (x, []), accounts.ids))

        # Prepare initial sql query and Get the initial move lines
        if init_balance:
            init_tables, init_where_clause, init_where_params = MoveLine.with_context(date_from=self.env.context.get('date_from'), date_to=False, initial_bal=True)._query_get()
            init_wheres = [""]
            if init_where_clause.strip():
                init_wheres.append(init_where_clause.strip())
            init_filters = " AND ".join(init_wheres)
            filters = init_filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')
            #NULL AS amount_currency
            sql = ("""SELECT 0 AS lid, l.account_id AS account_id, '' AS ldate, '' AS lcode, COALESCE(SUM(l.amount_currency),0.0) AS amount_currency, '' AS lref, 'Initial Balance' AS lname, COALESCE(SUM(l.debit),0.0) AS debit, COALESCE(SUM(l.credit),0.0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) as balance, '' AS lpartner_id,\
                '' AS move_name, '' AS mmove_id, '' AS currency_code,\
                NULL AS currency_id,\
                '' AS invoice_id, '' AS invoice_type, '' AS invoice_number,\
                '' AS partner_name\
                FROM account_move_line l\
                LEFT JOIN account_move m ON (l.move_id=m.id)\
                LEFT JOIN res_currency c ON (l.currency_id=c.id)\
                LEFT JOIN res_partner p ON (l.partner_id=p.id)\
                LEFT JOIN account_invoice i ON (m.id =i.move_id)\
                JOIN account_journal j ON (l.journal_id=j.id)\
                WHERE l.account_id IN %s""" + filters + ' GROUP BY l.account_id')
            params = (tuple(accounts.ids),) + tuple(init_where_params)
            cr.execute(sql, params)
            for row in cr.dictfetchall():
                account_browse = AccountObj.browse(row['account_id'])
                if account_browse.currency_id:
                    row['currency_id'] = account_browse.currency_id
                    row['currency_code'] = account_browse.currency_id.symbol
                else:
                    row['amount_currency'] = 0.00
                move_lines[row.pop('account_id')].append(row)

        sql_sort = 'l.date, l.move_id'
        if sortby == 'sort_journal_partner':
            sql_sort = 'j.code, p.name, l.move_id'

        # Prepare sql query base on selected parameters from wizard
        tables, where_clause, where_params = MoveLine._query_get()
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        filters = " AND ".join(wheres)
        filters = filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')

        # Get move lines base on sql query and Calculate the total balance of move lines
        sql = ('''SELECT l.id AS lid, l.account_id AS account_id, l.date AS ldate, j.code AS lcode, l.currency_id, l.amount_currency, l.ref AS lref, l.name AS lname, COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) AS balance,\
            m.name AS move_name, c.symbol AS currency_code, p.name AS partner_name\
            FROM account_move_line l\
            JOIN account_move m ON (l.move_id=m.id)\
            LEFT JOIN res_currency c ON (l.currency_id=c.id)\
            LEFT JOIN res_partner p ON (l.partner_id=p.id)\
            JOIN account_journal j ON (l.journal_id=j.id)\
            JOIN account_account acc ON (l.account_id = acc.id) \
            WHERE l.account_id IN %s ''' + filters + ''' GROUP BY l.id, l.account_id, l.date, j.code, l.currency_id, l.amount_currency, l.ref, l.name, m.name, c.symbol, p.name ORDER BY ''' + sql_sort)
        params = (tuple(accounts.ids),) + tuple(where_params)
        cr.execute(sql, params)

        for row in cr.dictfetchall():
            balance = 0
            for line in move_lines.get(row['account_id']):
                balance += line['debit'] - line['credit']
            row['balance'] += balance
            move_lines[row.pop('account_id')].append(row)

        # Calculate the debit, credit and balance for Accounts
        account_res = []
        for account in accounts:
            currency = account.currency_id and account.currency_id or account.company_id.currency_id
            res = dict((fn, 0.0) for fn in ['credit', 'debit', 'balance', 'amount_currency'])
            res['code'] = account.code
            res['name'] = account.name
            res['move_lines'] = move_lines[account.id]
            res['amount_currency'] = 0.00
            if account.currency_id:
                res['currency_id'] = account.currency_id
                res['currency_code'] = account.currency_id.symbol
                for line in res.get('move_lines'):
                    res['debit'] += line['debit']
                    res['credit'] += line['credit']
                    res['balance'] = line['balance']
                    res['amount_currency'] += line['amount_currency']
            else:
                res['currency_id'] = False
                res['currency_code'] = ''
                for line in res.get('move_lines'):
                    res['debit'] += line['debit']
                    res['credit'] += line['credit']
                    res['balance'] = line['balance']
#            for line in res.get('move_lines'):
#                res['debit'] += line['debit']
#                res['credit'] += line['credit']
#                res['balance'] = line['balance']
                
            if display_account == 'all':
                account_res.append(res)
            if display_account == 'movement' and res.get('move_lines'):
                account_res.append(res)
            if display_account == 'not_zero' and not currency.is_zero(res['balance']):
                account_res.append(res)

        return account_res

    @api.multi
    def print_excel_report(self):
        self.ensure_one()
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['date_from', 'date_to', 'journal_ids', 'target_move', 'initial_balance', 'sortby', 'display_account', 'general_account_ids'])[0]
        if data['form']['initial_balance']:
            if not data['form']['date_from']:
                raise UserError(_("You must define a Start Date, If you want to print the inital balance"))
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        
        data = self.pre_print_report(data)
        data['form'].update(self.read(['initial_balance', 'sortby'])[0])
        if data['form'].get('initial_balance') and not data['form'].get('date_from'):
            raise UserError(_("You must define a Start Date"))
            
        init_balance = data['form'].get('initial_balance', True)
        sortby = data['form'].get('sortby', 'sort_date')
        display_account = data['form']['display_account']
        codes = []
        if data['form'].get('journal_ids', False):
            codes = [journal.code for journal in self.env['account.journal'].search([('id', 'in', data['form']['journal_ids'])])]
        if data['form'].get('general_account_ids', False):
            accounts = self.env['account.account'].search([('id', 'in', data['form']['general_account_ids'])])
        else:
            accounts = self.env['account.account'].search([('internal_type', '!=', 'view')])
        accounts_res = self.with_context(data['form'].get('used_context',{}))._get_account_move_entry(accounts, init_balance, sortby, display_account)
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet("General Ledger")
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(6)
        sheet1.show_grid = False 
        sheet1.col(0).width = 3000
        sheet1.col(1).width = 3000
        sheet1.col(2).width = 9000
        sheet1.col(3).width = 9000
        sheet1.col(4).width = 4500
        sheet1.col(5).width = 6500
        sheet1.col(6).width = 4000
        sheet1.col(7).width = 4000
        sheet1.col(8).width = 4000
        sheet1.col(9).width = 1500
        sheet1.col(10).width = 4000
        sheet1.col(11).width = 4000
        sheet1.col(12).width = 1500

        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        r5 = 4
        sheet1.row(r1).height = 600
        sheet1.row(r2).height = 600
        sheet1.row(r3).height = 400
        sheet1.row(r4).height = 800 
        sheet1.row(r5).height = 200
        
        title = "General Ledger"
        sheet1.write_merge(r1, r1, 0, 12, self.env.user.company_id.name, Style.title_color())
        sheet1.write_merge(r2, r2, 0, 12, title, Style.sub_title_color())
        date_from = date_to = False
        if data['form']['date_from']:
            date_from = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")
            date_from = datetime.strftime(date_from, "%d-%m-%Y")
            sheet1.write(r3, 0, "Date From", Style.subTitle())
            sheet1.write(r4, 0, date_from, Style.normal_date_alone())
        else:
            sheet1.write(r3, 0, "", Style.subTitle())
            sheet1.write(r4, 0, "", Style.subTitle())
        if data['form']['date_to']:
            date_to = datetime.strptime(data['form']['date_to'], "%Y-%m-%d")
            date_to = datetime.strftime(date_to, "%d-%m-%Y")
            sheet1.write(r3, 1, "Date To", Style.subTitle())
            sheet1.write(r4, 1, date_to, Style.normal_date_alone())
        else:
            sheet1.write(r3, 1, "", Style.subTitle())
            sheet1.write(r4, 1, "", Style.subTitle())
        sheet1.write_merge(r3, r3, 2, 3, "Journals", Style.subTitle())
        journal = ""
        for each in codes:
            if journal:
                journal += each and ", " + each or ""
            else:
                journal += each and each or ""
        sheet1.write_merge(r4, r4, 2, 3, journal, Style.subTitle())
        
        sheet1.write_merge(r3, r3, 4, 5, "Display Account", Style.subTitle())
        if data['form']['display_account'] == 'all':
            sheet1.write_merge(r4, r4, 4, 5, "All accounts", Style.subTitle())
        if data['form']['display_account'] == 'movement':
            sheet1.write_merge(r4, r4, 4, 5, "With movements", Style.subTitle())
        if data['form']['display_account'] == 'not_zero':
            sheet1.write_merge(r4, r4, 4, 5, "With balance not equal to zero", Style.subTitle())
            
        sheet1.write_merge(r3, r3, 6, 7, "Target Move", Style.subTitle())
        if data['form']['target_move'] == 'all':
            sheet1.write_merge(r4, r4, 6, 7, "All Entries", Style.subTitle())
        if data['form']['target_move'] == 'posted':
            sheet1.write_merge(r4, r4, 6, 7, "All Posted Entries", Style.subTitle())
            
        sheet1.write_merge(r3, r3, 8, 9, "Sorted By", Style.subTitle())
        if data['form']['sortby'] == 'sort_date':
            sheet1.write_merge(r4, r4, 8, 9, "Date", Style.subTitle())
        if data['form']['sortby'] == 'sort_journal_partner':
            sheet1.write_merge(r4, r4, 8, 9, "Journal and Partner", Style.subTitle())
        sheet1.write_merge(r3, r3, 10, 12, "", Style.subTitle())
        sheet1.write_merge(r4, r4, 10, 12, "LC - Local Currency\nTC - Transaction Currency", Style.subTitle())
        
        row = r5 +1
        sheet1.row(row).height = 256 * 3
        sheet1.write(row, 0, "Date", Style.subTitle_color())
        sheet1.write(row, 1, "JNRL", Style.subTitle_color())
        sheet1.write(row, 2, "Partner", Style.subTitle_color())
        sheet1.write(row, 3, "Ref", Style.subTitle_color())
        sheet1.write(row, 4, "Move", Style.subTitle_color())
        sheet1.write(row, 5, "Entry Label", Style.subTitle_color())
        sheet1.write(row, 6, "Debit", Style.subTitle_color())
        sheet1.write(row, 7, "Credit", Style.subTitle_color())
        sheet1.write(row, 8, "Balance", Style.subTitle_color())
        sheet1.write(row, 9, "LC", Style.subTitle_color())
        sheet1.write(row, 10, "TC Value", Style.subTitle_color())
        sheet1.write(row, 11, "Balance", Style.subTitle_color())
        sheet1.write(row, 12, "TC", Style.subTitle_color())
        for each in accounts_res:
            row = row + 1
            sheet1.row(row).height = 400
            name = ""
            name = (each['code'] and each['code'] or "") + " --- " + (each['name'] and each['name'] or "")
            sheet1.write_merge(row, row, 0, 5, name, Style.subTitle_sub_color_left())
            sheet1.write(row, 6, each['debit'], Style.subTitle_float_sub_color())
            sheet1.write(row, 7, each['credit'], Style.subTitle_float_sub_color())
            sheet1.write(row, 8, each['balance'], Style.subTitle_float_sub_color())
            sheet1.write(row, 9, self.env.user.company_id.currency_id.symbol, Style.subTitle_float_sub_color())
            sheet1.write(row, 10, each['amount_currency'] and each['amount_currency'] or "", Style.subTitle_float_sub_color())
            sheet1.write(row, 12, each['currency_code'] and each['currency_code'] or "", Style.subTitle_float_sub_color())
            amount_currency = 0.00
            heading_row = row
            for line in each['move_lines']:
                amount_currency += line['amount_currency'] and line['amount_currency'] or 0.00
                row = row + 1
                sheet1.row(row).height = 400
                ldate = False
                if line['ldate']:
                    ldate = datetime.strptime(line['ldate'], "%Y-%m-%d")
                    ldate = datetime.strftime(ldate, "%d-%m-%Y")
                    sheet1.write(row, 0, ldate, Style.normal_date_alone())
                else:
                    sheet1.write(row, 0, "", Style.normal_left())
                sheet1.write(row, 1, line['lcode'], Style.normal_left())
                sheet1.write(row, 2, line['partner_name'], Style.normal_left())
                sheet1.write(row, 3, line['lref'], Style.normal_left())
                sheet1.write(row, 4, line['move_name'], Style.normal_left())
                sheet1.write(row, 5, line['lname'], Style.normal_left())
                sheet1.write(row, 6, line['debit'], Style.normal_num_right_3separator())
                sheet1.write(row, 7, line['credit'], Style.normal_num_right_3separator())
                sheet1.write(row, 8, line['balance'], Style.normal_num_right_3separator())
                sheet1.write(row, 9, self.env.user.company_id.currency_id.symbol, Style.normal_right())
                sheet1.write(row, 10, line['amount_currency'] and line['amount_currency'] or "-", Style.normal_num_right_3separator())
                sheet1.write(row, 11, amount_currency and amount_currency or "-", Style.normal_num_right_3separator())
                sheet1.write(row, 12, amount_currency and line['currency_code'] or "-", Style.normal_right())
            sheet1.write(heading_row, 11, amount_currency, Style.subTitle_float_sub_color())
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.env.cr.execute(""" DELETE FROM account_report_general_ledger_output""")
        attach_id = self.env['account.report.general.ledger.output'].create({'name': "General Ledger" + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.report.general.ledger.output',
                'res_id': attach_id.id,
                'type': 'ir.actions.act_window',
                'target': 'new'
                }
            
