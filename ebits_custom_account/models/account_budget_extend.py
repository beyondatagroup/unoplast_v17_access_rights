# -*- coding: utf-8 -*-
# Part of EBITS TechCon

import time
import pytz
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp


class CrossoveredBudget(models.Model):
    _inherit = "crossovered.budget"

    approved_user_id = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False)
    date_approved = fields.Date(string='Approved Date', readonly=True, copy=False)
    account_budget_line = fields.One2many('account.budget.lines', 'crossovered_budget_id', string='Account Budget Line',
                                          readonly=True)
    history = fields.Text(string='History', readonly=True, copy=False)

    # @api.multi
    def action_budget_confirm(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        approved_user_id = False
        if self.env.user.employee_ids:
            if self.env.user.employee_ids[0].parent_id:
                if self.env.user.employee_ids[0].parent_id.user_id:
                    approved_user_id = self.env.user.employee_ids[0].parent_id.user_id.id
        if not approved_user_id:
            raise UserError(_("Manager is not mapped for you.\nKindly contact your administrator!"))
        for each in self:
            if not each.account_budget_line:
                raise UserError(_("The Account Budget is empty!"))
            for line in each.account_budget_line:
                if line.planned_amount <= 0.00:
                    raise UserError(_("%s planned amount must be greater than zero") % (line.account_id.name))
            each.write({
                'approved_user_id': approved_user_id,
                'state': 'confirm',
                'history': (each.history and each.history or "") + "\n This document is sent for approval by " + str(
                    self.env.user.name) + " on " + date
            })
        return True

    def action_budget_draft(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.write({
                'state': 'draft',
                'history': (each.history and each.history or "") + "\n This document is sent to draft by " + str(
                    self.env.user.name) + " on " + date
            })
        return True

    def action_budget_validate(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.write({
                'state': 'validate',
                'history': (each.history and each.history or "") + "\n This document is approved by " + str(
                    self.env.user.name) + " on " + date,
                'date_approved': fields.Date.context_today(self)
            })
        return True

    def action_budget_cancel(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.write({
                'state': 'cancel',
                'history': (each.history and each.history or "") + "\n This document is cancelled by " + str(
                    self.env.user.name) + " on " + date
            })
        return True

    def action_budget_done(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.write({
                'state': 'done',
                'history': (each.history and each.history or "") + "\n This document is completed by " + str(
                    self.env.user.name) + " on " + date
            })
        return True

    def action_check_actual_amount(self):
        move_obj = self.env['account.move']
        for each in self:
            amount = 0.00
            for line in each.account_budget_line:
                amount = 0.00
                move_bro = move_obj.search(
                    [('date', '>=', each.date_from), ('date', '<=', each.date_to), ('state', '=', 'posted')])
                for move in move_bro:
                    for move_line in move.line_ids:
                        if line.account_id.id == move_line.account_id.id:
                            amount += move_line.debit
                line.write({'actual_amount': amount})
        return True


class AccountBudgetLines(models.Model):
    _name = 'account.budget.lines'
    _description = "Account Budget Lines"

    @api.depends('actual_amount', 'planned_amount')
    def _compute_percentage(self):
        for line in self:
            if line.actual_amount != 0.00:
                line.percentage = float((line.actual_amount) / line.planned_amount) * 100
            else:
                line.percentage = 0.00

    crossovered_budget_id = fields.Many2one('crossovered.budget', string='Budget Name', ondelete='cascade',
                                            required=True)
    account_id = fields.Many2one('account.account', string='Account', required=True)
    planned_amount = fields.Float(string='Planned Amount', required=True, digits=dp.get_precision('Product Price'))
    date_from = fields.Date(string='Start Date', readonly=True)
    date_to = fields.Date(string='End Date', readonly=True)
    actual_amount = fields.Float(string='Actual Amount', readonly=True, digits=dp.get_precision('Product Price'))
    percentage = fields.Float(compute='_compute_percentage', string='Percentage(%)')
