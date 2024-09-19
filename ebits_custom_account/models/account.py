# -*- coding: utf-8 -*-
# Part of EBITS TechCon

import time
import pytz
import json
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang
from babel.dates import format_datetime, format_date
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import odoo.addons.decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
import logging

_logger = logging.getLogger(__name__)

#commented as not in v17
# class AccountAccountType(models.Model):
#     _inherit = "account.account.type"
#
#     type = fields.Selection([
#         ('view', 'View'),
#         ('other', 'Regular'),
#         ('receivable', 'Receivable'),
#         ('payable', 'Payable'),
#         ('liquidity', 'Liquidity'),], required=True, default='other',
#         help="The 'Internal Type' is used for features available on "\
#         "different types of accounts: liquidity type is for cash or bank accounts"\
#         ", payable/receivable is for vendor/customer accounts.")

class AccountAccount(models.Model):
    _inherit = "account.account"

    # @api.multi
    @api.depends('parent_id', 'parent_id.level')
    def _get_level(self):
        '''Returns a dictionary with key=the ID of a record and value = the level of this
           record in the tree structure.'''
        for account in self:
            level = 0
            if account.parent_id:
                level = account.parent_id.level + 1
            account.level = level

#    @api.multi
#    def _get_children_and_consol(self):
#        #this function search for all the children and all consolidated children (recursively) of the given account ids
#        ids2 = ids3 = []
#        for each in self:
#            id_search = self.env['account.account'].search([('parent_id', 'child_of', each.id)])
#            for each in id_search:
#                ids2.append(each)
#            ids3 = []
#            for rec in ids2:
#                for child in rec.children_ids:
#                    ids3.append(child)
#            if ids3:
#                ids3 = ids3[0]._get_children_and_consol()
#        return ids2 + ids3
#
#    @api.multi
#    @api.depends('parent_id', 'children_ids')
#    def _get_credit_debit_balance(self):
#        MoveLine = self.env['account.move.line']
#        tables, where_clause, where_params = MoveLine._query_get()
#        wheres = [""]
#        if where_clause.strip():
#            wheres.append(where_clause.strip())
#        filters = " AND ".join(wheres)
#        filters = filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')

#        # Get move lines base on sql query and Calculate the total balance of move lines
#        sql = ('''SELECT l.account_id AS account_id, COALESCE(SUM(l.debit),0) AS debit, COALESCE(SUM(l.credit),0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) AS balance\
#            FROM account_move_line l\
#            JOIN account_move m ON (l.move_id=m.id)\
#            WHERE l.account_id = %s ''' + filters + ''' GROUP BY l.account_id''')
#        for normal_accounts in self:
#            all_accounts = normal_accounts._get_children_and_consol()
#            for accounts in all_accounts:
#                params = (accounts.id,) + tuple(where_params)
#                self.env.cr.execute(sql, params)
#                data = self.env.cr.dictfetchall()
#                for row in data:
#                    accounts.credit = row['credit']
#                    accounts.debit = row['debit']
#                    accounts.balance = row['balance']

#        for each_view_acc in self:
#            if each_view_acc.internal_type == 'view':
#                all_accounts = each_view_acc._get_children_and_consol()
#                for view_accounts in all_accounts:
#                    if view_accounts.internal_type == 'view':
#                        credit = debit = balance = 0.00
#                        for each in view_accounts.children_ids:
#                            credit += each.credit
#                            debit += each.debit
#                            balance += each.balance
#                        view_accounts.credit = credit
#                        view_accounts.debit = debit
#                        view_accounts.balance = balance

    # @api.multi
    def _get_children_and_consol(self):
        account_obj = self.env['account.account']
        #this function search for all the children and all consolidated children (recursively) of the given account ids
        ids3 = account_obj
        ids2 = account_obj.search([('parent_id', 'child_of', self.ids)], order="id desc")
        for each in ids2:
            ids3 = self.env['account.account']
            if each.children_ids:
                ids3 += each.children_ids
        if ids3:
            ids3 = ids3._get_children_and_consol()
        return ids2 + ids3

    # @api.multi
    @api.depends('parent_id', 'children_ids')
    def _get_credit_debit_balance(self):
        context = dict(self._context or {})
        MoveLine = self.env['account.move.line']
        tables, where_clause, where_params = MoveLine._query_get()
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        filters = " AND ".join(wheres)
        filters = filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')

        # Get move lines base on sql query and Calculate the total balance of move lines
        sql = ('''SELECT l.account_id AS account_id, COALESCE(SUM(l.debit),0) AS debit, COALESCE(SUM(l.credit),0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) AS balance, COALESCE(SUM(l.amount_currency),0) AS balance_amount_currency\
            FROM account_move_line l\
            JOIN account_move m ON (l.move_id=m.id)\
            WHERE l.account_id = %s ''' + filters + ''' GROUP BY l.account_id''')
        for normal_accounts in self:
            if normal_accounts.internal_type != 'view':
                params = (normal_accounts.id,) + tuple(where_params)
                self.env.cr.execute(sql, params)
                data = self.env.cr.dictfetchall()
                for row in data:
                    normal_accounts.credit = row['credit']
                    normal_accounts.debit = row['debit']
                    normal_accounts.balance = row['balance']
                    if normal_accounts.currency_id:
                        normal_accounts.balance_amount_currency = row['balance_amount_currency']
                    else:
                        normal_accounts.balance_amount_currency = row['balance_amount_currency']
        account_ids = list(self._ids)
        account_ids.reverse()
        for each_view_acc in account_ids:
            each_view = self.env['account.account'].browse(each_view_acc)
            if each_view.internal_type == 'view':
                all_accounts = each_view._get_children_and_consol()
                for view_accounts in all_accounts:
                    if view_accounts.internal_type == 'view':
                        credit, debit, balance = 0.00, 0.00, 0.00
                        for each in view_accounts.children_ids:
                            credit += each.credit
                            debit += each.debit
                            balance += each.balance
                        view_accounts.credit = credit
                        view_accounts.debit = debit
                        view_accounts.balance = balance
                        view_accounts.balance_amount_currency = 0.00

    parent_id = fields.Many2one('account.account', string="Parent Account", ondelete='cascade')
    children_ids = fields.One2many('account.account', 'parent_id', 'Children')
    sequence = fields.Integer('Sequence')
    level = fields.Integer(compute='_get_level', string='Level', store=True)
    credit = fields.Float(string='Credit', default=0.0, compute='_get_credit_debit_balance', digits=dp.get_precision('Product Price'))
    debit = fields.Float(string='Debit', default=0.0, compute='_get_credit_debit_balance', digits=dp.get_precision('Product Price'))
    balance = fields.Float(string='Balance', default=0.0, compute='_get_credit_debit_balance', digits=dp.get_precision('Product Price'))
    balance_amount_currency = fields.Float(string='Balance in Currency', default=0.0, compute='_get_credit_debit_balance', digits=dp.get_precision('Product Price'))
    forex_required = fields.Boolean('Asset Forex Gain/Loss Required?', default=False)
    liability_forex_required = fields.Boolean('Liability Forex Gain/Loss Required?', default=False)
    reconcile = fields.Boolean(string='Allow Reconciliation (Matching)', default=False,
        help="Check this box if this account allows invoices & payments matching of journal items.")

class AccountJournal(models.Model):
    _inherit = "account.journal"

    # @api.one
    # def _kanban_dashboard_graph(self):
    #     for data in self:
    #
    #         if (data.type in ['sale', 'purchase']):
    #             data.kanban_dashboard_graph = json.dumps(data.get_bar_graph_datas())
    #         elif (data.type == 'cash'):
    #             data.kanban_dashboard_graph = json.dumps(data.get_line_graph_datas())
    #         elif (data.type == 'bank'):
    #             data.kanban_dashboard_graph = json.dumps(data.get_line_custom_graph_datas())

    stock_warehouse_ids = fields.Many2many('stock.warehouse', 'account_journal_stock_warehouse_rela', 'journal_id', 'warehouse_id', string='Warehouse/Branch')
    journal_entry_approval = fields.Boolean(string="Journal Entry Approval Before Posting", copy=False, default=False)
    # kanban_dashboard_graph = fields.Text(compute='_kanban_dashboard_graph')
    allow_future_date_entry = fields.Boolean(string="Allow Future Date Posting On Journal Entry")
    active = fields.Boolean('Active', default=True)
    is_opening_journal = fields.Boolean('Is Opening Journal', default=False)

    # @api.multi
    def get_line_custom_graph_datas(self):
        data = []
        today = datetime.today()
        last_month = today + timedelta(days=-30)
        bank_stmt = []
        # Query to optimize loading of data for bank statement graphs
        # Return a list containing the latest bank statement balance per day for the
        # last 30 days for current journal
        if self.default_debit_account_id:
            query = """SELECT a.ending_date, a.ending_balance 
                            FROM bank_account_rec_statement AS a, 
                                (SELECT c.ending_date, max(c.id) AS stmt_id 
                                    FROM bank_account_rec_statement AS c 
                                    WHERE c.account_id = %s 
                                        AND c.ending_date > %s 
                                        AND c.ending_date <= %s 
                                        GROUP BY ending_date, id 
                                        ORDER BY ending_date, id) AS b 
                            WHERE a.id = b.stmt_id;"""

            self.env.cr.execute(query, (self.default_debit_account_id.id, last_month, today))
            bank_stmt = self.env.cr.dictfetchall()

            last_bank_stmt = self.env['bank.account.rec.statement'].search([('account_id', '=', self.default_debit_account_id.id),('ending_date', '<=', last_month.strftime(DF))], order="ending_date desc, id desc", limit=1)
            start_balance = last_bank_stmt and last_bank_stmt[0].ending_balance or 0

            locale = self._context.get('lang', 'en_US')
            show_date = last_month
            #get date in locale format
            name = format_date(show_date, 'd LLLL Y', locale=locale)
            short_name = format_date(show_date, 'd MMM', locale=locale)
            data.append({'x':short_name, 'y':start_balance, 'name':name})

            for stmt in bank_stmt:
                #fill the gap between last data and the new one
                number_day_to_add = (datetime.strptime(stmt.get('ending_date'), DF) - show_date).days
                last_balance = data[len(data) - 1]['y']
                for day in range(0,number_day_to_add + 1):
                    show_date = show_date + timedelta(days=1)
                    #get date in locale format
                    name = format_date(show_date, 'd LLLL Y', locale=locale)
                    short_name = format_date(show_date, 'd MMM', locale=locale)
                    data.append({'x': short_name, 'y':last_balance, 'name': name})
                #add new stmt value
                data[len(data) - 1]['y'] = stmt.get('balance_end')

            #continue the graph if the last statement isn't today
            if show_date != today:
                number_day_to_add = (today - show_date).days
                last_balance = data[len(data) - 1]['y']
                for day in range(0,number_day_to_add):
                    show_date = show_date + timedelta(days=1)
                    #get date in locale format
                    name = format_date(show_date, 'd LLLL Y', locale=locale)
                    short_name = format_date(show_date, 'd MMM', locale=locale)
                    data.append({'x': short_name, 'y':last_balance, 'name': name})

        return [{'values': data, 'area': True}]

    # @api.multi
    def create_bank_account_rec_statement(self):
        """return action to create a bank statements. This button should be called only on journals with type =='bank'"""
        if not self.default_debit_account_id:
            raise UserError(_("Kindly map respective bank account in the selected journal master"))
        self.bank_statements_source = 'manual'
        action = self.env.ref('ebits_custom_account.action_bank_account_rec_statement').read()[0]
        action.update({
            'views': [[False, 'form']],
            'context': "{'default_account_id': " + str(self.default_debit_account_id.id) + "}",
            'domain': [('account_id', '=', self.default_debit_account_id.id)]
            })
        return action

    # @api.multi
    def open_action(self):
        """return action based on type for related journals"""
        action_name = self._context.get('action_name', False)
        if not action_name:
            if self.type == 'bank':
                action_name = 'action_bank_account_rec_statement'
            elif self.type == 'cash':
                action_name = 'action_view_bank_statement_tree'
            elif self.type == 'sale':
                action_name = 'action_invoice_tree1'
            elif self.type == 'purchase':
                action_name = 'action_invoice_tree2'
            else:
                action_name = 'action_move_journal_line'

        _journal_invoice_type_map = {
            ('sale', None): 'out_invoice',
            ('purchase', None): 'in_invoice',
            ('sale', 'refund'): 'out_refund',
            ('purchase', 'refund'): 'in_refund',
            ('bank', None): 'bank',
            ('cash', None): 'cash',
            ('general', None): 'general',
        }
        invoice_type = _journal_invoice_type_map[(self.type, self._context.get('invoice_type'))]

        ctx = self._context.copy()
        ctx.pop('group_by', None)
        if self.type == 'bank':
            if not self.default_debit_account_id:
                raise UserError(_("Kindly map respective bank account in the selected journal master"))
            ctx.update({
                'default_account_id': self.default_debit_account_id and self.default_debit_account_id.id or False,
                'account_id': self.default_debit_account_id and self.default_debit_account_id.id or False,
                })
            [action] = self.env.ref('ebits_custom_account.%s' % action_name).read()
            action['context'] = ctx
            action['domain'] = [('account_id', '=', self.default_debit_account_id.id)]
        else:
            ctx.update({
                'journal_type': self.type,
                'default_journal_id': self.id,
                'search_default_journal_id': self.id,
                'default_type': invoice_type,
                'type': invoice_type
                })
            [action] = self.env.ref('account.%s' % action_name).read()
            action['context'] = ctx
            action['domain'] = self._context.get('use_domain', [])
        return action

    # @api.multi
    def get_journal_dashboard_datas(self):
        currency = self.currency_id or self.company_id.currency_id
        last_balance = 0.00
        result = super(AccountJournal, self).get_journal_dashboard_datas()
        if self.type == 'bank':
            last_bank_stmt = self.env['bank.account.rec.statement'].search([('account_id', '=', self.default_debit_account_id.id),('state', '=', 'done')], order="ending_date desc, id desc", limit=1)
            if last_bank_stmt:
                result['last_balance'] = formatLang(self.env, last_bank_stmt[0].ending_balance, currency_obj=last_bank_stmt[0].currency_id or self.company_id.currency_id)
        return result

class AccountMove(models.Model):
    _inherit = "account.move"

    approval_required = fields.Boolean(string="Waiting for Approval", copy=False, default=False)
    requested_approval = fields.Boolean(string="Requested Approval", copy=False, default=False)
    cancel_approval = fields.Boolean(string="Requested for Cancellation", copy=False, default=False)
    user_id = fields.Many2one('res.users', string="Created User", default=lambda self: self.env.user, copy=False, readonly=True)
    approved_user_id = fields.Many2one('res.users', string="Approved Person", copy=False, readonly=True)
    cancel_reason = fields.Text(string="Cancellation Reason", copy=False, readonly=True)
    cheque_no = fields.Char(string='Cheque No', copy=False)
    cheque_date = fields.Date(string='Cheque Date', copy=False)
    lc_no_id = fields.Many2one('purchase.order.lc.master', string='LC No', copy=False)
    history = fields.Text('History', readonly=True, copy=False)

    @api.onchange('journal_id')
    def onchange_journal_id(self):
        if self.journal_id:
            self.approval_required = self.journal_id.journal_entry_approval and self.journal_id.journal_entry_approval or False
        else:
            self.approval_required = False

    # @api.multi
    def action_requested_approval(self):
        history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for move in self:
            if move.history:
                history = move.history + "\n"
            move.write({
                'requested_approval': True,
                'history': history + "This document is request for Approval by " + self.env.user.name + " on this date " + date
                })
        return True

    # @api.multi
    def action_requested_cancellation(self):
        for move in self:
            move.write({'cancel_approval': True})
        return True

    # @api.multi
    def button_cancel(self):
        res = super(AccountMove, self).button_cancel()
        history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for move in self:
            if move.history:
                history = move.history + "\n"
            if move.approval_required:
                move.write({'requested_approval': False})
            move.write({
                'cancel_approval': False,
                'history': history + "This document is Cancelled by " + self.env.user.name + " on this date " + date
                })
        return res

    # @api.multi
    def _post_validate(self):
        for move in self:
            if not move.journal_id.allow_future_date_entry:
                if move.date > fields.Date.today():
                    raise UserError(_("You cannot post a journal entry on future date"))
            for line in move.line_ids:
                if line.account_id.internal_type == 'view':
                    raise UserError(_("You cannot post a value on view account (%s %s).") % (line.account_id.code, line.account_id.name))
        res = super(AccountMove, self)._post_validate()
        return res

    # @api.multi
    def post(self):
        history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for move in self:
            if move.history:
                history = move.history + "\n"
            move.write({
                'approved_user_id': self.env.user.id,
                'history': history + "This document is Approved by " + self.env.user.name + " on this date " + date
                })
        res = super(AccountMove, self).post()
        return res

    # @api.multi
    def journal_print(self):
        self.ensure_one()
        return self.env['report'].get_action(self, 'journal.entries.rml.report')

class AccountMoveLine(models.Model):
    _inherit='account.move.line'

    # @api.multi
    @api.depends('partner_id')
    def _compute_partner_region(self):
        for move in self:
            if move.partner_id:
                move.region_id = move.partner_id.region_id and move.partner_id.region_id.id or False

    # @api.multi
    @api.depends('partner_id')
    def _compute_partner_area(self):
        for move in self:
            if move.partner_id:
                move.area_id = move.partner_id.area_id and move.partner_id.area_id.id or False

    cleared_bank_account = fields.Boolean('Cleared? ', help='Check if the transaction has cleared from the bank', default=False, copy=False)
    bank_acc_rec_statement_id = fields.Many2one('bank.account.rec.statement', 'Bank Account Rec Statement', help="The Bank Acc Rec Statement linked with the journal item", copy=False)
    clearing_date = fields.Date(string='Clearing Date', copy=False)
    cheque_no = fields.Char(string='Cheque No', related='move_id.cheque_no', store=True, readonly=True, copy=False)
    cheque_date = fields.Date(string='Cheque Date', related='move_id.cheque_date', store=True, readonly=True, copy=False)
    lc_no_id = fields.Many2one('purchase.order.lc.master', string='LC No', related='move_id.lc_no_id', store=True, readonly=True, copy=False)
    user_id = fields.Many2one('res.users', string="Created User", related='move_id.user_id', store=True, readonly=True, copy=False)
    reconcilation_check = fields.Selection(compute='_compute_reconcilation_check', string='Reconcile Status', selection=[
        ('unreconciled', 'Unreconciled'),
        ('reconciled', 'Reconciled'),
        ('partial_reconciled', 'Partially Reconciled'),
        ('na', 'Not Applicable'),
        ], readonly=True, store=True, copy=False)
    region_id = fields.Many2one("res.state.region", compute='_compute_partner_region', string='Region', store=True, readonly=True, copy=False)
    area_id = fields.Many2one("res.state.area", compute='_compute_partner_area', string='Area', store=True, readonly=True, copy=False)

    # @api.multi
    @api.depends('reconciled', 'account_id.reconcile', 'matched_debit_ids', 'matched_credit_ids')
    def _compute_reconcilation_check(self):
        reconcilation_check = 'na'
        for move_line in self:
            if move_line.reconciled and move_line.account_id.reconcile:
                reconcilation_check = 'reconciled'
            if not move_line.full_reconcile_id and move_line.account_id.reconcile and not (move_line.matched_debit_ids or move_line.matched_credit_ids):
                reconcilation_check = 'unreconciled'
            if not move_line.reconciled and move_line.account_id.reconcile and (move_line.matched_debit_ids or move_line.matched_credit_ids):
                reconcilation_check = 'partial_reconciled'
            if not move_line.account_id.reconcile:
                reconcilation_check = 'na'
            move_line.reconcilation_check = reconcilation_check

    # remove as error in account.move.line
    # @api.onchange('currency_id')
    # def onchange_currency_id(self):
    #     if self.currency_id:
    #         print(">>>>>>>>>>>>>>self.currency_id>>>>>>>>>>>>>>",self.currency_id)
    #         if self.env.user.company_id.currency_id:
    #             print(">>>>>>>>>>>>>>self.env.user.company_id.currency_id>>>>>>>>>>>>>", self.env.user.company_id.currency_id)
    #             if self.env.user.company_id.currency_id == self.currency_id:
    #                 print(">>>>>>>>>>>>>self.env.user.company_id.currency_id>>>>>>>11>>>>>>>", self.currency_id)
    #                 self.currency_id = False
    #                 print(">>>>>>>>>>>>>>self.currency_id>>>>>111>>>>>>>>>", self.currency_id)

class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def create_exchange_rate_entry(self, aml_to_fix, amount_diff, diff_in_currency, currency, move_date):
        """ Automatically create a journal entry to book the exchange rate difference.
            That new journal entry is made in the company `currency_exchange_journal_id` and one of its journal
            items is matched with the other lines to balance the full reconciliation.
        """
        for rec in self:
            if not rec.company_id.currency_exchange_journal_id:
                raise UserError(_("You should configure the 'Exchange Rate Journal' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
            if not self.company_id.income_currency_exchange_account_id.id:
                raise UserError(_("You should configure the 'Gain Exchange Rate Account' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
            if not self.company_id.expense_currency_exchange_account_id.id:
                raise UserError(_("You should configure the 'Loss Exchange Rate Account' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
            move_vals = {'journal_id': rec.company_id.currency_exchange_journal_id.id}

            # The move date should be the maximum date between payment and invoice (in case
            # of payment in advance). However, we should make sure the move date is not
            # recorded after the end of year closing.
#            if move_date > rec.company_id.fiscalyear_lock_date:
#                move_vals['date'] = move_date
            move_vals['date'] = fields.Date.context_today(self)
            move = rec.env['account.move'].create(move_vals)
            amount_diff = rec.company_id.currency_id.round(amount_diff)
            diff_in_currency = currency.round(diff_in_currency)
            line_to_reconcile = rec.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': _('Currency exchange rate difference'),
                'debit': amount_diff < 0 and -amount_diff or 0.0,
                'credit': amount_diff > 0 and amount_diff or 0.0,
                'account_id': rec.debit_move_id.account_id.id,
                'move_id': move.id,
                'currency_id': currency.id,
                'amount_currency': -diff_in_currency,
                'partner_id': rec.debit_move_id.partner_id.id,
            })
            rec.env['account.move.line'].create({
                'name': _('Currency exchange rate difference'),
                'debit': amount_diff > 0 and amount_diff or 0.0,
                'credit': amount_diff < 0 and -amount_diff or 0.0,
                'account_id': amount_diff > 0 and rec.company_id.currency_exchange_journal_id.default_debit_account_id.id or rec.company_id.currency_exchange_journal_id.default_credit_account_id.id,
                'move_id': move.id,
                'currency_id': currency.id,
                'amount_currency': diff_in_currency,
                'partner_id': rec.debit_move_id.partner_id.id,
            })
            for aml in aml_to_fix:
                partial_rec = rec.env['account.partial.reconcile'].create({
                    'debit_move_id': aml.credit and line_to_reconcile.id or aml.id,
                    'credit_move_id': aml.debit and line_to_reconcile.id or aml.id,
                    'amount': abs(aml.amount_residual),
                    'amount_currency': abs(aml.amount_residual_currency),
                    'currency_id': currency.id,
                })
            move.post()
            if rec.full_reconcile_id:
                for each in move:
                    for line in each.line_ids:
                        line.name = rec.full_reconcile_id.name + " - " + line.name
        return line_to_reconcile, partial_rec

class AccountReconcileModel(models.Model):
    _inherit = "account.reconcile.model"

    name = fields.Char(string='Name', required=True)
    amount_type = fields.Selection([
        ('fixed', 'Fixed'),
        ('percentage', 'Percentage of balance')
        ], required=True, default='fixed')
    amount = fields.Float(default=0.0, help="Fixed amount will count as a debit if it is negative, as a credit if it is positive.", digits=dp.get_precision('Product Price'))


# class account_financial_report(models.Model):
#     # _inherit = "account.financial.report"
#     _inherit = "account.financial.report"
#
#     # @api.multi
#     @api.depends('parent_id', 'children_ids')
#     def _get_balance(self):
#         account_obj = self.env['account.account']
#         res = {}
#         for report in self:
#             credit, debit, balance = 0.00, 0.00, 0.00
#             if report.type == 'accounts':
#                 for a in report.account_ids:
#                     a._get_credit_debit_balance()
#                     credit += a.credit
#                     debit += a.debit
#                     balance += a.balance
#             elif report.type == 'account_type':
#                 report_types = [x.id for x in report.account_type_ids]
#                 account_ids = account_obj.search([('user_type_id', 'in', report_types), ('internal_type', '!=', 'view')])
#                 for a in account_ids:
#                     a._get_credit_debit_balance()
#                     credit += a.credit
#                     debit += a.debit
#                     balance += a.balance
#             elif report.type == 'account_report' and report.account_report_id:
#                 report.account_report_id._get_balance()
#                 credit += report.account_report_id.credit
#                 debit += report.account_report_id.debit
#                 balance += report.account_report_id.balance
#             elif report.type == 'sum':
#                 for each_report in report.children_ids:
#                     each_report._get_balance()
#                     credit += each_report.credit
#                     debit += each_report.debit
#                     balance += each_report.balance
#             report.credit = credit
#             report.debit = debit
#             report.balance = balance
#
#     hierarchy_type = fields.Selection([('hierarchy', 'Hierarchy Print'), ('normal', 'Normal Print')], string='Print Type')
#     credit = fields.Float(string='Credit', default=0.0, compute='_get_balance', digits=dp.get_precision('Product Price'))
#     debit = fields.Float(string='Debit', default=0.0, compute='_get_balance', digits=dp.get_precision('Product Price'))
#     balance = fields.Float(string='Balance', default=0.0, compute='_get_balance', digits=dp.get_precision('Product Price'))


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def process_reconciliation(self, counterpart_aml_dicts=None, payment_aml_rec=None, new_aml_dicts=None):
        """ Match statement lines with existing payments (eg. checks) and/or payables/receivables (eg. invoices and refunds) and/or new move lines (eg. write-offs).
            If any new journal item needs to be created (via new_aml_dicts or counterpart_aml_dicts), a new journal entry will be created and will contain those
            items, as well as a journal item for the bank statement line.
            Finally, mark the statement line as reconciled by putting the matched moves ids in the column journal_entry_ids.

            :param self: browse collection of records that are supposed to have no accounting entries already linked.
            :param (list of dicts) counterpart_aml_dicts: move lines to create to reconcile with existing payables/receivables.
                The expected keys are :
                - 'name'
                - 'debit'
                - 'credit'
                - 'move_line'
                    # The move line to reconcile (partially if specified debit/credit is lower than move line's credit/debit)

            :param (list of recordsets) payment_aml_rec: recordset move lines representing existing payments (which are already fully reconciled)

            :param (list of dicts) new_aml_dicts: move lines to create. The expected keys are :
                - 'name'
                - 'debit'
                - 'credit'
                - 'account_id'
                - (optional) 'tax_ids'
                - (optional) Other account.move.line fields like analytic_account_id or analytics_id

            :returns: The journal entries with which the transaction was matched. If there was at least an entry in counterpart_aml_dicts or new_aml_dicts, this list contains
                the move created by the reconciliation, containing entries for the statement.line (1), the counterpart move lines (0..*) and the new move lines (0..*).
        """
        counterpart_aml_dicts = counterpart_aml_dicts or []
        payment_aml_rec = payment_aml_rec or self.env['account.move.line']
        new_aml_dicts = new_aml_dicts or []

        aml_obj = self.env['account.move.line']

        company_currency = self.journal_id.company_id.currency_id
        statement_currency = self.journal_id.currency_id or company_currency
        st_line_currency = self.currency_id or statement_currency

        counterpart_moves = self.env['account.move']

        # Check and prepare received data
        if any(rec.statement_id for rec in payment_aml_rec):
            raise UserError(_('A selected move line was already reconciled.'))
        for aml_dict in counterpart_aml_dicts:
            if aml_dict['move_line'].reconciled:
                raise UserError(_('A selected move line was already reconciled.'))
            if isinstance(aml_dict['move_line'], (int, long)):
                aml_dict['move_line'] = aml_obj.browse(aml_dict['move_line'])
        for aml_dict in (counterpart_aml_dicts + new_aml_dicts):
            if aml_dict.get('tax_ids') and aml_dict['tax_ids'] and isinstance(aml_dict['tax_ids'][0], (int, long)):
                # Transform the value in the format required for One2many and Many2many fields
                aml_dict['tax_ids'] = map(lambda id: (4, id, None), aml_dict['tax_ids'])

        # Fully reconciled moves are just linked to the bank statement
        total = self.amount
        for aml_rec in payment_aml_rec:
            total -= aml_rec.debit-aml_rec.credit
            aml_rec.write({'statement_id': self.statement_id.id})
            aml_rec.move_id.write({'statement_line_id': self.id})
            counterpart_moves = (counterpart_moves | aml_rec.move_id)

        # Create move line(s). Either matching an existing journal entry (eg. invoice), in which
        # case we reconcile the existing and the new move lines together, or being a write-off.
        if counterpart_aml_dicts or new_aml_dicts:
            st_line_currency = self.currency_id or statement_currency
            st_line_currency_rate = self.currency_id and (self.amount_currency / self.amount) or False

            # Create the move
            self.sequence = self.statement_id.line_ids.ids.index(self.id) + 1
            move_vals = self._prepare_reconciliation_move(self.statement_id.name)
            move = self.env['account.move'].create(move_vals)
            counterpart_moves = (counterpart_moves | move)

            # Create The payment
            payment = False
            if abs(total)>0.00001:
                partner_id = self.partner_id and self.partner_id.id or False
                partner_type = False
                if partner_id:
                    if total < 0:
                        partner_type = 'supplier'
                    else:
                        partner_type = 'customer'

                payment_methods = (total>0) and self.journal_id.inbound_payment_method_ids or self.journal_id.outbound_payment_method_ids
                currency = self.journal_id.currency_id or self.company_id.currency_id
                payment = self.env['account.payment'].create({
                    'payment_method_id': payment_methods and payment_methods[0].id or False,
                    'payment_type': total >0 and 'inbound' or 'outbound',
                    'partner_id': self.partner_id and self.partner_id.id or False,
                    'partner_type': partner_type,
                    'journal_id': self.statement_id.journal_id.id,
                    'payment_date': self.date,
                    'state': 'reconciled',
                    'currency_id': currency.id,
                    'amount': abs(total),
                    'communication': self.name or '',
                    'name': self.statement_id.name,
                    'user_id': self.statement_id.user_id and self.statement_id.user_id.id or self.env.user.id,
                })

            # Complete dicts to create both counterpart move lines and write-offs
            to_create = (counterpart_aml_dicts + new_aml_dicts)
            ctx = dict(self._context, date=self.date)
            for aml_dict in to_create:
                aml_dict['move_id'] = move.id
                aml_dict['partner_id'] = self.partner_id.id
                aml_dict['statement_id'] = self.statement_id.id
                if st_line_currency.id != company_currency.id:
                    aml_dict['amount_currency'] = aml_dict['debit'] - aml_dict['credit']
                    aml_dict['currency_id'] = st_line_currency.id
                    if self.currency_id and statement_currency.id == company_currency.id and st_line_currency_rate:
                        # Statement is in company currency but the transaction is in foreign currency
                        aml_dict['debit'] = company_currency.round(aml_dict['debit'] / st_line_currency_rate)
                        aml_dict['credit'] = company_currency.round(aml_dict['credit'] / st_line_currency_rate)
                    elif self.currency_id and st_line_currency_rate:
                        # Statement is in foreign currency and the transaction is in another one
                        aml_dict['debit'] = statement_currency.with_context(ctx).compute(aml_dict['debit'] / st_line_currency_rate, company_currency)
                        aml_dict['credit'] = statement_currency.with_context(ctx).compute(aml_dict['credit'] / st_line_currency_rate, company_currency)
                    else:
                        # Statement is in foreign currency and no extra currency is given for the transaction
                        aml_dict['debit'] = st_line_currency.with_context(ctx).compute(aml_dict['debit'], company_currency)
                        aml_dict['credit'] = st_line_currency.with_context(ctx).compute(aml_dict['credit'], company_currency)
                elif statement_currency.id != company_currency.id:
                    # Statement is in foreign currency but the transaction is in company currency
                    prorata_factor = (aml_dict['debit'] - aml_dict['credit']) / self.amount_currency
                    aml_dict['amount_currency'] = prorata_factor * self.amount
                    aml_dict['currency_id'] = statement_currency.id

            # Create write-offs
            # When we register a payment on an invoice, the write-off line contains the amount
            # currency if all related invoices have the same currency. We apply the same logic in
            # the manual reconciliation.
            counterpart_aml = self.env['account.move.line']
            for aml_dict in counterpart_aml_dicts:
                counterpart_aml |= aml_dict.get('move_line', self.env['account.move.line'])
            new_aml_currency = False
            if counterpart_aml\
                    and len(counterpart_aml.mapped('currency_id')) == 1\
                    and counterpart_aml[0].currency_id\
                    and counterpart_aml[0].currency_id != company_currency:
                new_aml_currency = counterpart_aml[0].currency_id
            for aml_dict in new_aml_dicts:
                aml_dict['payment_id'] = payment and payment.id or False
                if new_aml_currency and not aml_dict.get('currency_id'):
                    aml_dict['currency_id'] = new_aml_currency.id
                    aml_dict['amount_currency'] = company_currency.with_context(ctx).compute(aml_dict['debit'] - aml_dict['credit'], new_aml_currency)
                aml_obj.with_context(check_move_validity=False, apply_taxes=True).create(aml_dict)

            # Create counterpart move lines and reconcile them
            for aml_dict in counterpart_aml_dicts:
                if aml_dict['move_line'].partner_id.id:
                    aml_dict['partner_id'] = aml_dict['move_line'].partner_id.id
                aml_dict['account_id'] = aml_dict['move_line'].account_id.id
                aml_dict['payment_id'] = payment and payment.id or False

                counterpart_move_line = aml_dict.pop('move_line')
                if counterpart_move_line.currency_id and counterpart_move_line.currency_id != company_currency and not aml_dict.get('currency_id'):
                    aml_dict['currency_id'] = counterpart_move_line.currency_id.id
                    aml_dict['amount_currency'] = company_currency.with_context(ctx).compute(aml_dict['debit'] - aml_dict['credit'], counterpart_move_line.currency_id)
                new_aml = aml_obj.with_context(check_move_validity=False).create(aml_dict)

                (new_aml | counterpart_move_line).reconcile()

            # Create the move line for the statement line using the bank statement line as the remaining amount
            # This leaves out the amount already reconciled and avoids rounding errors from currency conversion
            st_line_amount = -sum([x.balance for x in move.line_ids])
            aml_dict = self._prepare_reconciliation_move_line(move, st_line_amount)
            aml_dict['payment_id'] = payment and payment.id or False
            aml_obj.with_context(check_move_validity=False).create(aml_dict)

            move.post()
            #record the move name on the statement line to be able to retrieve it in case of unreconciliation
            self.write({'move_name': move.name})
            payment.write({'payment_reference': move.name})
        elif self.move_name:
            raise UserError(_('Operation not allowed. Since your statement line already received a number, you cannot reconcile it entirely with existing journal entries otherwise it would make a gap in the numbering. You should book an entry and make a regular revert of it in case you want to cancel it.'))
        counterpart_moves.assert_balanced()
        return counterpart_moves

