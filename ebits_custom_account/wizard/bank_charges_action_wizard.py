# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
import pytz
import datetime
import time
import parser
import json
from lxml import etree

class BankChargesReconciliationWizard(models.TransientModel):
    _name = 'bank.charges.reconciliation.wizard'
    _description = 'Bank Charges Reconciliation Wizard'
    
    @api.one
    @api.depends('currency_id', 'company_id', 'date')
    def _get_amount_words(self):
        currency_id_rate = self.currency_id.rate
        currency_id_value = self.currency_id.rate and (1 / self.currency_id.rate) or 0.00
        if self.company_id.currency_id != self.currency_id:
            currency_id = self.currency_id.with_context(date=self.date or fields.Date.context_today(self))
            currency_id_rate = currency_id.rate
            currency_id_value = currency_id.rate and (1 / currency_id.rate) or 0.00
        self.currency_id_rate = currency_id_rate
        self.currency_id_value = round(currency_id_value, 3)
    
    statement_id = fields.Many2one('bank.account.rec.statement', string='Reconciliation', copy=False, readonly=True)
    date = fields.Date('Date', required=True)
    reference = fields.Char('Reference', required=True)
    reconcile_id = fields.Many2one('account.reconcile.model', string='Reconcile Model', required=True)
    debit = fields.Monetary('Debit', required=True, digits=(16, 2))
    credit = fields.Monetary('Credit', required=True, digits=(16, 2))
    journal_id = fields.Many2one('account.journal', string='Journal', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, track_visibility='always')
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.user.company_id)
    currency_id_rate = fields.Float(compute='_get_amount_words', string='Currency Rate', store=True, copy=False, digits=(12, 9))
    currency_id_value = fields.Float(compute='_get_amount_words', string='Currency Conversion Value', store=True, copy=False, digits=(12, 3))
    
    @api.model
    def default_get(self, fields):
        res = super(BankChargesReconciliationWizard, self).default_get(fields)
        statement_obj = self.env['bank.account.rec.statement']
        statement = statement_obj.browse(self.env.context.get('active_id'))
        if statement:
            res.update({'statement_id': statement.id, 'currency_id': statement.currency_id.id })
        return res
        
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(BankChargesReconciliationWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            warehouse_id = []
            for each in self.env.user.sudo().default_warehouse_ids:
                warehouse_id.append(each.id)
            if warehouse_id:
                for node in doc.xpath("//field[@name='reconcile_id']"):
                    node.set('domain', "[('journal_id.stock_warehouse_ids', 'in', " + str(warehouse_id) + ")]")
                for node in doc.xpath("//field[@name='journal_id']"):
                    node.set('domain', "[('stock_warehouse_ids', 'in', " + str(warehouse_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res
        
    @api.onchange('reconcile_id')
    def onchange_reconcile_id(self):
        if self.reconcile_id:
            self.journal_id = self.reconcile_id.journal_id and self.reconcile_id.journal_id.id or False
            #self.currency_id = self.journal_id.currency_id and self.journal_id.currency_id.id or self.company_id.currency_id.id
        else:
            self.journal_id = False
            #self.currency_id = self.company_id.currency_id.id
            
    @api.onchange('journal_id')
    def onchange_journal_id(self):
        warning = {}
        if self.journal_id:
            if self.reconcile_id:
                if self.reconcile_id.journal_id != self.journal_id:
                    self.journal_id = self.reconcile_id.journal_id.id
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot change the journal which is configured in the reconcile model!!')}
            else:
                self.journal_id = False
        return {'warning': warning}
        
    def _get_shared_move_line_vals(self, debit, credit, amount_currency, move_id):
        """ Returns values common to both move lines (except for debit, credit and amount_currency which are reversed)
        """
        return {
            'move_id': move_id,
            'debit': debit,
            'credit': credit,
            'amount_currency': amount_currency or False,
        }
            
    @api.multi
    def action_update(self):
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        amount, amount_currency = 0.00, 0.00
        for each in self:
            if each.debit and each.credit:
                raise UserError(_("You cannot give both debit and credit at the same time"))
            if each.debit:  
                amount = each.debit * 1
            if each.credit:  
                amount = each.credit * -1
            move_vals = {
                'ref': each.reference,
                'journal_id': each.journal_id.id,
                'date': each.date,
                'narration': each.reconcile_id.label,
                'company_id': each.company_id.id,
                }
            move = move_obj.create(move_vals)
            debit, credit, amount_currency, dummy = aml_obj.with_context(date=each.date).compute_amount_fields(amount, each.currency_id, each.company_id.currency_id)
            amount_currency = each.journal_id.currency_id and each.currency_id.with_context(date=each.date).compute(amount, each.journal_id.currency_id) or 0
            
            dst_liquidity_aml_dict = each._get_shared_move_line_vals(debit, credit, amount_currency, move.id)
            dst_liquidity_aml_dict.update({
                'name': each.reconcile_id.label,
                'account_id': each.reconcile_id.account_id.id,
                'journal_id': each.journal_id.id,
                'analytic_account_id': each.reconcile_id.analytic_account_id and each.reconcile_id.analytic_account_id.id or False})
            if each.currency_id != each.company_id.currency_id:
                dst_liquidity_aml_dict.update({
                    'currency_id': each.currency_id.id,
                    'amount_currency': amount,
                })
            aml_obj.create(dst_liquidity_aml_dict)

            transfer_debit_aml_dict = each._get_shared_move_line_vals(credit, debit, 0, move.id)
            transfer_debit_aml_dict.update({
                'name': each.reconcile_id.label,
                'account_id': each.statement_id.account_id.id,
                'journal_id': each.journal_id.id,
                'analytic_account_id': each.reconcile_id.analytic_account_id and each.reconcile_id.analytic_account_id.id or False,})
            if each.currency_id != each.company_id.currency_id:
                transfer_debit_aml_dict.update({
                    'currency_id': each.currency_id.id,
                    'amount_currency': -amount,
                })
            transfer_debit_aml = aml_obj.create(transfer_debit_aml_dict)
            move.post()
            each.statement_id.action_recompute()
        return {'type': 'ir.actions.act_window_close'}   
            
            
BankChargesReconciliationWizard()
