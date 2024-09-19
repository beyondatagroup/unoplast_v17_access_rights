# -*- coding: utf-8 -*-
# Part of EBITS TechCon

import time
from datetime import datetime
from odoo import api, fields, models, _
# from odoo.tools import amount_to_text_in
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import odoo.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class AccountMoveForex(models.Model):
    _name = "account.move.forex"
    _description = "Unrealised exchange Gain/Loss Entry"
    _order = "date desc, id"
    
    @api.model
    def _default_journal(self):
        company_id = self.env.user.company_id
        if company_id.currency_exchange_journal_id:
            return company_id.currency_exchange_journal_id
        else:
            return False
    
    name = fields.Char(string='Name', readonly=True, default='New #', copy=False)
    date = fields.Date(string='Entry Date', required=True, readonly=True,
                       copy=False)
    reverse_date = fields.Date(string='Reversal Date', required=True, readonly=True,
                               copy=False)
    date_created = fields.Date(string="Created Date", default=fields.Date.context_today, readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('post', 'Posted'),('reverse', 'Reversed'),('cancel', 'Cancelled')], string='Status', readonly=True, copy=False, default='draft')
    user_id = fields.Many2one('res.users', string='Created By', track_visibility='onchange', readonly=True, default=lambda self: self.env.user)
    customer_forex_lines = fields.One2many('account.move.forex.line', 'forex_id', string='Customer Unrealised Lines', readonly=True, domain=[('type', '=', 'receivable')])
    vendor_forex_lines = fields.One2many('account.move.forex.line', 'forex_id', string='Vendor Unrealised Lines', readonly=True, domain=[('type', '=', 'payable')])
    payment_forex_lines = fields.One2many('payment.account.move.forex.line', 'forex_id', string='Bank Payment Unrealised Lines', readonly=True, domain=[('bank_type', '=', 'asset_bank')])
    liability_payment_forex_lines = fields.One2many('payment.account.move.forex.line', 'forex_id', string='Bank Payment Unrealised  Lines', readonly=True, domain=[('bank_type', '=', 'liability_bank')])
    customer_gain_loss_lines = fields.One2many('forex.gain.loss.line', 'forex_id', string='Customer Unrealised Exchange Gain/Loss Lines', readonly=True, domain=[('type', '=', 'receivable')])
    vendor_gain_loss_lines = fields.One2many('forex.gain.loss.line', 'forex_id', string='Vendor Unrealised Exchange Gain/Loss Lines', readonly=True, domain=[('type', '=', 'payable')])
    bank_gain_loss_lines = fields.One2many('forex.gain.loss.line', 'forex_id', string='Asset Bank Unrealised Exchange Gain/Loss Lines', readonly=True, domain=[('type', '=', 'asset_bank')])
    liability_bank_gain_loss_lines = fields.One2many('forex.gain.loss.line', 'forex_id', string='Liability Bank Unrealised Exchange Gain/Loss Lines', readonly=True, domain=[('type', '=', 'liability_bank')])
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
        required=True, readonly=True,
        default=lambda self: self.env['res.company']._company_default_get('account.move.forex'))
    currency_exchange_journal_id = fields.Many2one('account.journal',
        string="Exchange Difference Journal", required=True, readonly=True, 
        copy=False,
        default=_default_journal)
    move_id = fields.Many2one('account.move', string='Unrealised Exchange Gain/Loss Accounting Entry', readonly=True)
    reverse_move_id = fields.Many2one('account.move', string='Reversal Forex Accounting Entry', readonly=True)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New #') == 'New #':
            vals['name'] = self.env['ir.sequence'].next_by_code('account.move.forex') or 'New #'
        result = super(AccountMoveForex, self).create(vals)
        return result
        
    #@api.multi
    def action_forex_remove_lines(self):
        if self.customer_forex_lines:
            self.customer_forex_lines.unlink()
        if self.vendor_forex_lines:
            self.vendor_forex_lines.unlink()
        if self.payment_forex_lines:
            self.payment_forex_lines.unlink()
        if self.liability_payment_forex_lines:
            self.liability_payment_forex_lines.unlink()
        if self.customer_gain_loss_lines:
            self.customer_gain_loss_lines.unlink()
        if self.vendor_gain_loss_lines:
            self.vendor_gain_loss_lines.unlink()
        if self.bank_gain_loss_lines:
            self.bank_gain_loss_lines.unlink()
        if self.liability_bank_gain_loss_lines:
            self.liability_bank_gain_loss_lines.unlink()
        return True
        
    #@api.multi
    def action_forex_inv_open_lines(self):
        forex_line_obj = self.env['account.move.forex.line']
        gain_loss_obj = self.env['forex.gain.loss.line']
        obj_partner = self.env['res.partner']
        obj_currency = self.env['res.currency']
        result = {}
        result = {
            'journal_ids': False,
            'state': 'posted',
            'date_from': False,
            'date_to': self.date,
            'strict_range': False,
            }
        used_context = result
        used_context = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        query_get_data = self.env['account.move.line'].with_context(used_context)._query_get()
        result['account_type'] = ['payable', 'receivable']
        result['reconciled'] = False
        self.env.cr.execute("""
            SELECT a.id
            FROM account_account a
            WHERE a.internal_type IN %s
            AND NOT a.deprecated""", (tuple(result['account_type']),))
        result['account_ids'] = [a for (a,) in self.env.cr.fetchall()]
        params = [result['state'], tuple(result['account_ids'])] + query_get_data[2]
        reconcile_clause = "" if result['reconciled'] else ' AND "account_move_line".reconciled = false '
        query = """
            SELECT "account_move_line".id, "account_move_line".partner_id,
                act.type, "account_move_line".amount_residual,
                "account_move_line".amount_residual_currency,
                "account_move_line".amount_currency,
                "account_move_line".credit,
                "account_move_line".debit,
                "account_move_line".currency_id,
                "account_move_line".name,
                "account_move_line".date,
                 m.name as move_name,
                 m.id as move_id
            FROM """ + query_get_data[0] + """ 
            left join account_account account on ("account_move_line".account_id=account.id)
            left join account_account_type act on (account.user_type_id=act.id)
            left join account_move m on ("account_move_line".move_id=m.id)
            WHERE "account_move_line".partner_id IS NOT NULL
                AND m.state = %s
                AND "account_move_line".account_id IN %s
                AND "account_move_line".currency_id IS NOT NULL
                AND """ + query_get_data[1] + reconcile_clause
        self.env.cr.execute(query, tuple(params))
        data = self.env.cr.dictfetchall()
        for res in data:
            if res['currency_id'] == self.company_id.currency_id.id:
                continue
            exchanged_rate = currency_rate = expected_local_balance = gain_loss = 0.00
            #exchanged_rate = each_invoice.currency_id_rate
            #obj_currency.with_context(date=self.date).browse(res['currency_id']).rate
            currency_rate = obj_currency.with_context(date=self.date).browse(res['currency_id']).rate
            if currency_rate:
                expected_local_balance = self.company_id.currency_id.round(res['amount_residual_currency'] / currency_rate)
                currency_rate = 1.00 / currency_rate
            if exchanged_rate:
                exchanged_rate = 1.00/ exchanged_rate
            gain_loss = expected_local_balance - res['amount_residual']
            
            forex_line_obj.create({
                'forex_id': self.id,
                'name': res['move_name'],
                'date': res['date'],
                #'move_id': res['move_id'],
                'type': res['type'] == 'receivable' and 'receivable' or 'payable',
                'debit_credit': res['debit'] and 'debit' or 'credit',
                'partner_id': res['partner_id'],
                'currency_id': res['currency_id'],
                'open_balance': res['amount_residual_currency'],
                'original_balance': res['amount_currency'],
                'exchanged_rate': round(exchanged_rate, 3),
                'local_balance': res['amount_residual'],
                'currency_rate': currency_rate,
                'expected_local_balance': expected_local_balance,
                'gain_loss': gain_loss,
                'company_currency_id': self.company_id.currency_id.id,
                })
        customer_forex_dict = {}
        vendor_forex_dict = {}
        for customer_forex in self.customer_forex_lines:
            if customer_forex.sudo().partner_id.id in customer_forex_dict:
                customer_forex_dict[customer_forex.sudo().partner_id.id]['gain_loss'] += customer_forex.gain_loss
            else:
                customer_forex_dict[customer_forex.sudo().partner_id.id] = {
                    'partner_id': customer_forex.sudo().partner_id,
                    'forex_id': self.id,
                    'type': customer_forex.type,
                    'company_currency_id': customer_forex.company_currency_id.id,
                    'gain_loss': customer_forex.gain_loss,
                    }
        for vendor_forex in self.vendor_forex_lines:
            if vendor_forex.sudo().partner_id.id in vendor_forex_dict:
                vendor_forex_dict[vendor_forex.sudo().partner_id.id]['gain_loss'] += vendor_forex.gain_loss
            else:
                vendor_forex_dict[vendor_forex.sudo().partner_id.id] = {
                    'partner_id': vendor_forex.sudo().partner_id,
                    'type': vendor_forex.type,
                    'company_currency_id': vendor_forex.company_currency_id.id,
                    'gain_loss': vendor_forex.gain_loss,
                    }
        for each_customer_forex_dict in customer_forex_dict:
            debit = credit = 0.00
            debit_account_id = credit_account_id = False
            if customer_forex_dict[each_customer_forex_dict]['gain_loss'] != abs(customer_forex_dict[each_customer_forex_dict]['gain_loss']):
                print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>...")
                debit = credit = abs(customer_forex_dict[each_customer_forex_dict]['gain_loss'])
                debit_account_id = self.currency_exchange_journal_id.default_debit_account_id.id
                credit_account_id = customer_forex_dict[each_customer_forex_dict]['partner_id'].sudo().property_account_receivable_id.id 
            else:
                debit = credit = abs(customer_forex_dict[each_customer_forex_dict]['gain_loss'])
                debit_account_id = customer_forex_dict[each_customer_forex_dict]['partner_id'].sudo().property_account_receivable_id.id 
                credit_account_id = self.currency_exchange_journal_id.default_credit_account_id.id
            gain_loss_obj.create({
                'partner_id': customer_forex_dict[each_customer_forex_dict]['partner_id'].sudo().id,
                'forex_id': self.id,
                'type': customer_forex_dict[each_customer_forex_dict]['type'],
                'company_currency_id': customer_forex_dict[each_customer_forex_dict]['company_currency_id'],
                'gain_loss': customer_forex_dict[each_customer_forex_dict]['gain_loss'],
                'credit': abs(customer_forex_dict[each_customer_forex_dict]['gain_loss']),
                'credit_account_id': credit_account_id,
                'debit': abs(customer_forex_dict[each_customer_forex_dict]['gain_loss']),
                'debit_account_id': debit_account_id,
                })
        for each_vendor_forex_dict in vendor_forex_dict:
            debit = credit = 0.00
            debit_account_id = credit_account_id = False
            if vendor_forex_dict[each_vendor_forex_dict]['gain_loss'] != abs(vendor_forex_dict[each_vendor_forex_dict]['gain_loss']):
                debit = credit = abs(vendor_forex_dict[each_vendor_forex_dict]['gain_loss'])
                debit_account_id = vendor_forex_dict[each_vendor_forex_dict]['partner_id'].sudo().property_account_payable_id.id 
                credit_account_id = self.currency_exchange_journal_id.default_debit_account_id.id
            else:
                debit = credit = abs(vendor_forex_dict[each_vendor_forex_dict]['gain_loss'])
                debit_account_id = self.currency_exchange_journal_id.default_credit_account_id.id
                credit_account_id = vendor_forex_dict[each_vendor_forex_dict]['partner_id'].sudo().property_account_payable_id.id
            gain_loss_obj.create({
                'partner_id': vendor_forex_dict[each_vendor_forex_dict]['partner_id'].sudo().id,
                'forex_id': self.id,
                'type': vendor_forex_dict[each_vendor_forex_dict]['type'],
                'company_currency_id': vendor_forex_dict[each_vendor_forex_dict]['company_currency_id'],
                'gain_loss': vendor_forex_dict[each_vendor_forex_dict]['gain_loss'],
                'credit': abs(vendor_forex_dict[each_vendor_forex_dict]['gain_loss']),
                'credit_account_id': credit_account_id,
                'debit': abs(vendor_forex_dict[each_vendor_forex_dict]['gain_loss']),
                'debit_account_id': debit_account_id,
                })
        return True
        
    #@api.multi
    def action_forex_asset_liability_payment_lines(self):
        payment_forex_line_obj = self.env['payment.account.move.forex.line']
        gain_loss_obj = self.env['forex.gain.loss.line']
        MoveLine = self.env['account.move.line']
        currency_obj = self.env['res.currency']
        account_obj = self.env['account.account']
        move_data = []
        forex_accounts = []
        asset_forex_accounts = self.env['account.account'].search([('forex_required', '=', True), ('currency_id', '!=', False), ('currency_id', '!=', self.company_id.currency_id.id)])
        liability_forex_accounts = self.env['account.account'].search([('liability_forex_required', '=', True), ('currency_id', '!=', False), ('currency_id', '!=', self.company_id.currency_id.id)])
        forex_accounts = asset_forex_accounts + liability_forex_accounts
        forex_accounts = list(set(forex_accounts))
        data = {'date_from': False, 'date_to': self.date, 'state': 'posted', 'strict_range': False}
        used_context = dict(data, lang=self.env.context.get('lang', 'en_US'))
        tables, where_clause, where_params = MoveLine.with_context(used_context)._query_get()
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        filters = " AND ".join(wheres)
        reconcile_sql = " "
        filters = filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')

        # Get move lines base on sql query and Calculate the total balance of move lines
        sql = ("""SELECT l.account_id AS account_id, 
                    COALESCE(SUM(l.debit),0) AS debit, 
                    COALESCE(SUM(l.credit),0) AS credit, 
                    COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) AS balance, 
                    COALESCE(SUM(l.amount_currency),0) AS amount_currency, 
                    l.currency_id as currency_id
            FROM account_move_line l
            JOIN account_move m ON (l.move_id=m.id)
            WHERE l.account_id = %s and l.currency_id is not null""" + reconcile_sql + filters + """ GROUP BY l.account_id, l.currency_id """)
        for normal_accounts in forex_accounts:
            all_accounts = normal_accounts._get_children_and_consol()

            for accounts in all_accounts:
                params = (accounts.id,) + tuple(where_params)
                self.env.cr.execute(sql, params)
                data = self.env.cr.dictfetchall()
                for row in data:
                    move_data.append(row)
        for each_move in move_data:
            #if each_move['balance'] and each_move['balance'] == abs(each_move['balance']):
            currency_rate = expected_local_balance = gain_loss = 0.00
            currency_rate = currency_obj.with_context(date=self.date).browse(each_move['currency_id']).rate
            if currency_rate:
                expected_local_balance = self.company_id.currency_id.round(each_move['amount_currency'] / currency_rate)
                currency_rate = 1.00 / currency_rate
            gain_loss = expected_local_balance - each_move['balance']
            account_bro = account_obj.browse(each_move['account_id'])
            bank_type = ''
            if account_bro.forex_required:
                bank_type = 'asset_bank'
            else:
                bank_type = 'liability_bank'
            payment_forex_line_obj.create({
                'forex_id': self.id,
                'account_id': each_move['account_id'],
                'currency_id': each_move['currency_id'],
                'open_balance': each_move['amount_currency'],
                'local_balance': each_move['balance'],
                'currency_rate': currency_rate,
                'expected_local_balance': expected_local_balance,
                'gain_loss': gain_loss,
                'company_currency_id': self.company_id.currency_id.id,
                'bank_type': bank_type,
                })
        asset_bank_forex_dict = {}
        for payment_forex in self.payment_forex_lines:
            if payment_forex.sudo().account_id.id in asset_bank_forex_dict:
                asset_bank_forex_dict[payment_forex.sudo().account_id.id]['gain_loss'] += payment_forex.gain_loss
            else:
                asset_bank_forex_dict[payment_forex.sudo().account_id.id] = {
                    'account_id': payment_forex.sudo().account_id.id,
                    'type': payment_forex.bank_type,
                    'company_currency_id': payment_forex.company_currency_id.id,
                    'gain_loss': payment_forex.gain_loss,
                    }
        for each_asset_bank_forex_dict in asset_bank_forex_dict:
            debit = credit = 0.00
            debit_account_id = credit_account_id = False
            if asset_bank_forex_dict[each_asset_bank_forex_dict]['gain_loss'] != abs(asset_bank_forex_dict[each_asset_bank_forex_dict]['gain_loss']):
                debit = credit = abs(asset_bank_forex_dict[each_asset_bank_forex_dict]['gain_loss'])
                credit_account_id = asset_bank_forex_dict[each_asset_bank_forex_dict]['account_id']
                debit_account_id = self.currency_exchange_journal_id.default_debit_account_id.id
            else:
                debit = credit = abs(asset_bank_forex_dict[each_asset_bank_forex_dict]['gain_loss'])
                credit_account_id = self.currency_exchange_journal_id.default_credit_account_id.id
                debit_account_id = asset_bank_forex_dict[each_asset_bank_forex_dict]['account_id']
            gain_loss_obj.create({
                'forex_id': self.id,
                'type': asset_bank_forex_dict[each_asset_bank_forex_dict]['type'],
                'company_currency_id': asset_bank_forex_dict[each_asset_bank_forex_dict]['company_currency_id'],
                'gain_loss': asset_bank_forex_dict[each_asset_bank_forex_dict]['gain_loss'],
                'credit': abs(asset_bank_forex_dict[each_asset_bank_forex_dict]['gain_loss']),
                'credit_account_id': credit_account_id,
                'debit': abs(asset_bank_forex_dict[each_asset_bank_forex_dict]['gain_loss']),
                'debit_account_id': debit_account_id,
                })
        liability_bank_forex_dict = {}
        for liability_payment_forex in self.liability_payment_forex_lines:
            if liability_payment_forex.sudo().account_id.id in liability_bank_forex_dict:
                liability_bank_forex_dict[liability_payment_forex.sudo().account_id.id]['gain_loss'] += liability_payment_forex.gain_loss
            else:
                liability_bank_forex_dict[liability_payment_forex.sudo().account_id.id] = {
                    'account_id': liability_payment_forex.sudo().account_id.id,
                    'type': liability_payment_forex.bank_type,
                    'company_currency_id': liability_payment_forex.company_currency_id.id,
                    'gain_loss': liability_payment_forex.gain_loss,
                    }
        for each_liability_bank_forex_dict in liability_bank_forex_dict:
            debit = credit = 0.00
            debit_account_id = credit_account_id = False
            if liability_bank_forex_dict[each_liability_bank_forex_dict]['gain_loss'] != abs(liability_bank_forex_dict[each_liability_bank_forex_dict]['gain_loss']):
                debit = credit = abs(liability_bank_forex_dict[each_liability_bank_forex_dict]['gain_loss'])
                credit_account_id = self.currency_exchange_journal_id.default_debit_account_id.id
                debit_account_id = liability_bank_forex_dict[each_liability_bank_forex_dict]['account_id']
            else:
                debit = credit = abs(liability_bank_forex_dict[each_liability_bank_forex_dict]['gain_loss'])
                credit_account_id = liability_bank_forex_dict[each_liability_bank_forex_dict]['account_id']
                debit_account_id = self.currency_exchange_journal_id.default_credit_account_id.id
            gain_loss_obj.create({
                'forex_id': self.id,
                'type': liability_bank_forex_dict[each_liability_bank_forex_dict]['type'],
                'company_currency_id': liability_bank_forex_dict[each_liability_bank_forex_dict]['company_currency_id'],
                'gain_loss': liability_bank_forex_dict[each_liability_bank_forex_dict]['gain_loss'],
                'credit': abs(liability_bank_forex_dict[each_liability_bank_forex_dict]['gain_loss']),
                'credit_account_id': credit_account_id,
                'debit': abs(liability_bank_forex_dict[each_liability_bank_forex_dict]['gain_loss']),
                'debit_account_id': debit_account_id,
                })
        return True
        
    #@api.multi
    def action_check_forex(self):
        for each in self:
            if not each.currency_exchange_journal_id.default_debit_account_id:
                raise UserError(_("Please define the default debit account on the exchange journal."))
            if not each.currency_exchange_journal_id.default_credit_account_id:
                raise UserError(_("Please define the default credit account on the exchange journal."))
            each.action_forex_remove_lines()
            each.action_forex_inv_open_lines()        
            each.action_forex_asset_liability_payment_lines()
        return True                

    #@api.multi
    def action_post(self):
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']
        obj_currency = self.env['res.currency']
        temp = []
        for each in self:
            for customer in each.customer_gain_loss_lines:
                debit_currency_id = False
                credit_currency_id = False
                if customer.partner_id.transaction_currency_id:
                    currency_bro = customer.partner_id.transaction_currency_id.with_context(date=each.date)
                    if customer.debit_account_id.internal_type == 'receivable':
                        debit_currency_id = currency_bro.id
                    if customer.credit_account_id.internal_type == 'receivable':
                        credit_currency_id = currency_bro.id
                temp.append({
                    'name': each.name,
                    'debit': customer.debit,
                    'credit': 0.00,
                    'account_id': customer.debit_account_id.id,
                    'partner_id': customer.partner_id.id,
                    'currency_id': debit_currency_id,
                })
                temp.append({
                    'name': each.name,
                    'debit': 0.00,
                    'credit': customer.credit,
                    'account_id': customer.credit_account_id.id,
                    'partner_id': customer.partner_id.id,
                    'currency_id': credit_currency_id,
                })
            for vendor in each.vendor_gain_loss_lines:
                debit_currency_id = False
                credit_currency_id = False
                if vendor.partner_id.transaction_currency_id:
                    currency_bro = vendor.partner_id.transaction_currency_id.with_context(date=each.date)
                    if vendor.debit_account_id.internal_type == 'payable':
                        debit_currency_id = currency_bro.id
                    if vendor.credit_account_id.internal_type == 'payable':
                        credit_currency_id = currency_bro.id
                temp.append({
                    'name': each.name,
                    'debit': vendor.debit,
                    'credit': 0.00,
                    'account_id': vendor.debit_account_id.id,
                    'partner_id': vendor.partner_id.id,
                    'currency_id': debit_currency_id,
                })
                temp.append({
                    'name': each.name,
                    'debit': 0.00,
                    'credit': vendor.credit,
                    'account_id': vendor.credit_account_id.id,
                    'partner_id': vendor.partner_id.id,
                    'currency_id': credit_currency_id,
                })
            for each_bank in each.bank_gain_loss_lines:
                temp.append({
                    'name': each.name,
                    'debit': each_bank.debit,
                    'credit': 0.00,
                    'account_id': each_bank.debit_account_id.id,
                })
                temp.append({
                    'name': each.name,
                    'debit': 0.00,
                    'credit': each_bank.credit,
                    'account_id': each_bank.credit_account_id.id,
                })
            for each_liability_bank in each.liability_bank_gain_loss_lines:
                temp.append({
                    'name': each.name,
                    'debit': each_liability_bank.debit,
                    'credit': 0.00,
                    'account_id': each_liability_bank.debit_account_id.id,
                })
                temp.append({
                    'name': each.name,
                    'debit': 0.00,
                    'credit': each_liability_bank.credit,
                    'account_id': each_liability_bank.credit_account_id.id,
                })
            move_line = []
            if not temp:
                raise UserError(_("There is no unrealised exchange gain/loss summary available to post."))
            for each_move_line in temp:
                move_line.append((0, 0, each_move_line))
            move = move_obj.create({
                'ref': each.name,
                'line_ids': move_line,
                'journal_id': each.currency_exchange_journal_id.id,
                'date': each.date,
                'narration': each.name,
                'company_id': each.company_id.id
                })
            move.with_context(move_reverse_cancel=cancel)._post(soft=False)
            each.write({'move_id': move.id, 'state': 'post'})
            each.action_reverse_post()
            account_id = []
            partner_id = []
            for line in each.move_id.line_ids:
                if not line.account_id.reconcile:
                    continue
                account_id.append(line.account_id)
                if line.partner_id:
                    partner_id.append(line.partner_id)
            account_id = list(set(account_id))
            partner_id = list(set(partner_id))
            for each_acc_id in account_id:
                for each_part_id in partner_id:
                    aml = each.move_id.line_ids.filtered(lambda m: m.account_id == each_acc_id and m.partner_id == each_part_id)
                    reverse_aml = each.reverse_move_id.line_ids.filtered(lambda r: r.account_id == each_acc_id and r.partner_id == each_part_id)
                    if aml and reverse_aml:
                        (aml + reverse_aml).reconcile()
                no_partner_aml = each.move_id.line_ids.filtered(lambda m: m.account_id == each_acc_id and m.partner_id == False)
                no_partner_reverse_aml = each.reverse_move_id.line_ids.filtered(lambda r: r.account_id == each_acc_id and r.partner_id == False)
                if no_partner_aml and no_partner_reverse_aml:
                    (no_partner_aml + no_partner_reverse_aml).reconcile()
        return True
            
    #@api.multi
    def action_reverse_post(self):
        date = False
        reversed_moves = self.env['account.move']
        for each in self:
            if each.move_id:
                date = each.reverse_date
                reversed_move = each.move_id._reverse_move(date=date, journal_id=each.currency_exchange_journal_id)
                reversed_moves += reversed_move
        if reversed_moves:
            reversed_moves._post_validate()
            reversed_moves.post()
            each.write({'reverse_move_id': reversed_moves.id, 'state': 'reverse'})
        return True
    
    #@api.multi
    def action_cancel(self):
        moves = self.env['account.move']
        for each in self:
            if each.move_id:
                moves += each.move_id
            each.state = 'cancel' 
        if moves:
            moves.button_cancel()
            moves.unlink()
        return True
        
    #@api.multi
    def unlink(self):
        for each in self:
            if each.state not in ('draft', 'cancel'):
                raise UserError(_("You cannot delete a form which is not in draft or cancel."))
        return super(AccountMoveForex, self).unlink()
        
class AccountMoveForexLine(models.Model):
    _name = "account.move.forex.line"
    _description = "Account Move Unrealised Lines"
    
    forex_id = fields.Many2one('account.move.forex', string='Unrealised Exchange Gain/Loss Entry', readonly=True, ondelete='cascade', copy=False)
    name = fields.Char(string='Ref', readonly=True, copy=False)
    date = fields.Date(string='Date', readonly=True, copy=False)
    move_id = fields.Many2one('account.move.line', string='Move Ref', readonly=True, copy=False)
    type = fields.Selection([('payable', 'Vendor'), ('receivable', 'Customer')],string='Type', readonly=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True, copy=False)
    currency_id = fields.Many2one('res.currency', string='Transaction Currency', readonly=True, copy=False)
    debit_credit = fields.Selection([('debit', 'Debit'), ('credit', 'Credit')],string='Dr/Cr', readonly=True, copy=False)
    original_balance = fields.Float(string='Original Value', digits=(12, 3), readonly=True, copy=False)
    open_balance = fields.Float(string='Open Balance', digits=(12, 3), readonly=True, copy=False)
    exchanged_rate = fields.Float(string='Exchange Rate', digits=(12, 3), readonly=True, copy=False)
    local_balance = fields.Float(string='Local Currency', digits=(12, 3), readonly=True, copy=False)
    currency_rate = fields.Float(string='Latest Cur. Rate', digits=(12, 3), readonly=True, copy=False)
    expected_local_balance = fields.Float(string='Expected Realization', digits=(12, 3), readonly=True, copy=False)
    gain_loss = fields.Float(string='Gain/Loss', digits=(12, 3), readonly=True, copy=False)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', readonly=True, copy=False)
    
class BankAccountMoveForexLine(models.Model):
    _name = "payment.account.move.forex.line"
    _description = "Payment Bank Account Move Unrealised Lines"
    
    forex_id = fields.Many2one('account.move.forex', string='Unrealised Exchange Gain/Loss Entry', readonly=True, ondelete='cascade', copy=False)
    bank_type = fields.Selection([('asset_bank', 'Asset Bank'), ('liability_bank', 'Liability Bank')],string='Bank Account Type', readonly=True, copy=False)
    account_id = fields.Many2one('account.account', string='Account', required=True, readonly=True, copy=False)
    currency_id = fields.Many2one('res.currency', string='Payment Currency', readonly=True, copy=False)
    open_balance = fields.Float(string='Open Balance', digits=(12, 3), readonly=True, copy=False)
    local_balance = fields.Float(string='Local Currency', digits=(12, 3), readonly=True, copy=False)
    currency_rate = fields.Float(string='Latest Currency Rate', digits=(12, 3), readonly=True, copy=False)
    expected_local_balance = fields.Float(string='Expected Realization', digits=(12, 3), readonly=True, copy=False)
    gain_loss = fields.Float(string='Gain/Loss', digits=(12, 3), readonly=True, copy=False)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', readonly=True, copy=False)


class ForexGainLossLine(models.Model):
    _name = "forex.gain.loss.line"
    _description = "Unrealised Exchange Gain/Loss Lines"
    _order = "type"
    
    forex_id = fields.Many2one('account.move.forex', string='Unrealised Exchange Gain/Loss Entry', readonly=True, ondelete='cascade', copy=False)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True, copy=False)
    gain_loss = fields.Float(string='Gain/Loss', digits=(12, 3), readonly=True, copy=False)
    company_currency_id = fields.Many2one('res.currency', required=True, string='Company Currency', readonly=True, copy=False)
    debit = fields.Float(string='Debit', digits=(12, 3), readonly=True, copy=False)
    credit = fields.Float(string='Credit', digits=(12, 3), readonly=True, copy=False)
    debit_account_id = fields.Many2one('account.account', string='Debit Account', required=True, readonly=True, copy=False)
    credit_account_id = fields.Many2one('account.account', string='Credit Account', required=True, readonly=True, copy=False)
    type = fields.Selection([('receivable', 'Customer'), ('payable', 'Vendor'), ('asset_bank', 'Asset Bank Account'),('liability_bank', 'Liability Bank Account')], required=True, string='Type', readonly=True, copy=False)
    
