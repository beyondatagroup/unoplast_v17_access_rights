# -*- coding: utf-8 -*-
# Part of EBITS TechCon

import time
from datetime import datetime
from odoo import api, fields, models, _
# from odoo.tools import amount_to_text_in
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    # @api.multi
    @api.depends('parent_id', 'parent_id.level')
    def _get_level(self):
        '''Returns a dictionary with key=the ID of a record and value = the level of this
           record in the tree structure.'''
        for report in self:
            level = 0
            if report.parent_id:
                level = report.parent_id.level + 1
            report.level = level

    # @api.multi
    def _get_children_and_consol(self):
        # this function search for all the children and all consolidated children (recursively) of the given account ids
        ids2 = ids3 = []
        for each in self:
            id_search = self.env['account.analytic.account'].search([('parent_id', 'child_of', each.id)])
            for each in id_search:
                ids2.append(each)
            ids3 = []
            for rec in ids2:
                for child in rec.children_ids:
                    ids3.append(child)
            if ids3:
                ids3 = ids3[0]._get_children_and_consol()
        return ids2 + ids3

    # @api.multi
    @api.depends('parent_id', 'children_ids', 'analytic_account_type')
    def _compute_debit_credit_balance(self):
        analytic_line_obj = self.env['account.analytic.line']
        domain = [('account_id', 'in', self.mapped('id'))]
        if self._context.get('from_date', False):
            domain.append(('date', '>=', self._context['from_date']))
        if self._context.get('to_date', False):
            domain.append(('date', '<=', self._context['to_date']))

        account_amounts = analytic_line_obj.search_read(domain, ['account_id', 'amount'])
        account_ids = set([line['account_id'][0] for line in account_amounts])
        data_debit = {account_id: 0.0 for account_id in account_ids}
        data_credit = {account_id: 0.0 for account_id in account_ids}
        for account_amount in account_amounts:
            if account_amount['amount'] < 0.0:
                data_debit[account_amount['account_id'][0]] += account_amount['amount']
            else:
                data_credit[account_amount['account_id'][0]] += account_amount['amount']

        for account in self:
            if account.analytic_account_type != 'view':
                account.debit = abs(data_debit.get(account.id, 0.0))
                account.credit = data_credit.get(account.id, 0.0)
                account.balance = account.credit - account.debit

        for view_account in self:
            if view_account.analytic_account_type == 'view':
                all_accounts = view_account._get_children_and_consol()
                for each_account in all_accounts:
                    if each_account.analytic_account_type == 'view':
                        debit = credit = balance = 0.00
                        for each_analytic_child in each_account.children_ids:
                            debit += each_analytic_child.debit
                            credit += each_analytic_child.credit
                        each_account.debit = debit
                        each_account.credit = credit
                        each_account.balance = credit - debit

    analytic_account_type = fields.Selection([
        ('view', 'View'),
        ('normal', 'Regular')], required=True, default='normal')
    children_ids = fields.One2many(
        'account.analytic.account',
        'parent_id',
        string="Children")
    parent_id = fields.Many2one(
        'account.analytic.account',
        string='Parent',
        domain=[('analytic_account_type', '=', 'view')])
    level = fields.Integer(compute='_get_level', string='Level', store=True)
    balance = fields.Monetary(compute='_compute_debit_credit_balance', string='Balance')
    debit = fields.Monetary(compute='_compute_debit_credit_balance', string='Debit')
    credit = fields.Monetary(compute='_compute_debit_credit_balance', string='Credit')