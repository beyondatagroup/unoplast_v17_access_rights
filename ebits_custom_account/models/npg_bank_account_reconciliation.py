# -*- coding: utf-8 -*-
# Part of EBITS TechCon

import time
from datetime import datetime
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.addons.ebits_custom_account.models.excel_styles import ExcelStyles
import xlwt
# import cStringIO
from io import StringIO
import base64
from odoo.exceptions import UserError

class BankAccountRecStatement(models.Model): 
    _name = "bank.account.rec.statement"
    _description = "Bank Account Reconciliation Statement"
    _order = "ending_date desc, id"
    
    #@api.one
    @api.depends('account_id', 'currency_id', 'company_currency_id', 'ledger_balance', 'ledger_balance_currency')
    def _get_ledger_currency(self):
        for each in self:
            if each.currency_id and each.company_currency_id and (each.currency_id != each.company_currency_id):
                each.ledger_currency = True
            else:
                each.ledger_currency = False
    
    #@api.one
    @api.depends('debit_move_line_ids', 'credit_move_line_ids', 'starting_balance', 'ending_balance')
    def _get_balance(self):
        for each in self:
            sum_of_credits_lines = sum_of_debits_lines = sum_of_credits = sum_of_debits = 0.00
            sum_of_credits_uncheck = sum_of_debits_uncheck = 0.00
            for credit_line in each.credit_move_line_ids:
                if each.currency_id != self.env.user.company_id.currency_id:
                    if credit_line.cleared_bank_account:
                       sum_of_credits += credit_line.amount_currency 
                       sum_of_credits_lines += 1.0
                    else:
                        sum_of_credits_uncheck += credit_line.amount_currency  
                else:
                    if credit_line.cleared_bank_account:
                       sum_of_credits += credit_line.amount 
                       sum_of_credits_lines += 1.0
                    else:
                        sum_of_credits_uncheck += credit_line.amount  
            for debit_line in each.debit_move_line_ids:
                if each.currency_id != self.env.user.company_id.currency_id:
                    if debit_line.cleared_bank_account:
                        sum_of_debits += debit_line.amount_currency
                        sum_of_debits_lines += 1.0 
                    else:
                        sum_of_debits_uncheck += debit_line.amount_currency
                else:
                    if debit_line.cleared_bank_account:
                        sum_of_debits += debit_line.amount
                        sum_of_debits_lines += 1.0 
                    else:
                        sum_of_debits_uncheck += debit_line.amount 
            each.update({
                'sum_of_debits_lines': sum_of_debits_lines,
                'sum_of_credits_lines': sum_of_credits_lines,
                'sum_of_debits': sum_of_debits,
                'sum_of_credits': sum_of_credits,
                'sum_of_debits_uncheck': sum_of_debits_uncheck,
                'sum_of_credits_uncheck': sum_of_credits_uncheck,
                'cleared_balance': (sum_of_debits - sum_of_credits),
                'difference': ((each.ending_balance - each.starting_balance) - (sum_of_debits - sum_of_credits)),
                })
        
    # @api.model
    # def _get_type(self):
    #     # type_obj = self.env['account.account.type']
    #     type_obj = self.env['account.account']
    #     print(">>>>>>>>>>>>>>type_obj>>>>>>>>>>>>",type_obj,type_obj.account_type)
    #     type_search = type_obj.account_type.search([('name', '=', 'Bank and Cash')])
    #     return type_search and type_search[0].id or False
        
    @api.model
    def _default_currency(self):
        return self.company_id.currency_id and self.company_id.currency_id.id or False 
            
    name = fields.Char(string='Name', size=32, required=True, readonly=True, copy=False)
    account_id = fields.Many2one('account.account', string='Account', required=True, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, readonly=True, default=_default_currency)
    ending_date = fields.Date(string='Ending Date', required=True, readonly=True)
    starting_balance = fields.Monetary(string='Statement Starting Balance', required=True, readonly=True, copy=False)
    ending_balance = fields.Monetary(string='Statement Ending Balance', required=True, readonly=True, copy=False)
    ledger_balance = fields.Float(string='Ledger Closing Balance(*)', readonly=True, copy=False)
    ledger_balance_currency = fields.Monetary(string='Ledger Closing Balance', readonly=True, copy=False)
    ledger_currency = fields.Boolean(compute='_get_ledger_currency', string='Other Currency', store=True, readonly=True, copy=False)
    company_id = fields.Many2one('res.company', 'Company', index=True, default=lambda self: self.env.user.company_id.id, readonly=True)
    company_currency_id = fields.Many2one('res.currency', 'Company Currency', index=True, default=lambda self: self.env.user.company_id.currency_id.id, readonly=True)
    notes = fields.Text('Notes')
    user_id = fields.Many2one('res.users', string='Created By', readonly=True, default=lambda self: self.env.user.id, copy=False)
    date = fields.Date(string='Created Date', readonly=True, default=fields.Date.context_today, copy=False)
    verified_by_user_id = fields.Many2one('res.users', string='Verified By', readonly=True, copy=False)
    verified_date = fields.Date(string='Verified Date', readonly=True, copy=False)
    credit_move_line_ids = fields.One2many('bank.account.rec.statement.move.line', 'statement_id', string='Credits', context={'default_types':'cr'}, domain=[('types', '=', 'cr')], copy=False)
    debit_move_line_ids = fields.One2many('bank.account.rec.statement.move.line', 'statement_id', string='Debits', context={'default_types':'dr'}, domain=[('types', '=', 'dr')], copy=False)
    suppress_ending_date_filter = fields.Boolean(string='Remove Ending Date Filter')
    cleared_balance = fields.Monetary(compute='_get_balance',  string='Cleared Balance', store=True, readonly=True, track_visibility='always')
    difference = fields.Monetary(compute='_get_balance', string='Difference', store=True, readonly=True, track_visibility='always')
    sum_of_credits = fields.Monetary(compute='_get_balance', string='Checks, Withdrawals, Debits, and Service Charges Amount', store=True, readonly=True, track_visibility='always')
    sum_of_debits = fields.Monetary(compute='_get_balance', string='Deposits, Credits, and Interest Amount', store=True, readonly=True, track_visibility='always')
    sum_of_credits_lines = fields.Monetary(compute='_get_balance', string='Checks, Withdrawals, Debits, and Service Charges # of Items', store=True, readonly=True, track_visibility='always')
    sum_of_debits_lines = fields.Monetary(compute='_get_balance', string='Deposits, Credits, and Interest # of Items', store=True, readonly=True, track_visibility='always')
    sum_of_debits_uncheck = fields.Monetary(compute='_get_balance', string='Deposits, Credits, and Interest Amount - Uncleared', store=True, readonly=True, track_visibility='always')
    sum_of_credits_uncheck = fields.Monetary(compute='_get_balance', string='Checks, Withdrawals, Debits, and Service Charges Amount - Uncleared', store=True, readonly=True, track_visibility='always') 
    # type_user_id = fields.Many2one('account.account.type', string='Type', default=_get_type, states={'done':[('readonly', True)], 'cancel':[('readonly', True)]}, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_be_reviewed', 'Ready for Review'),
        ('done', 'Done'),
        ('cancel', 'Cancel')], string='State', readonly=True, default='draft')
                
    @api.onchange('ending_date', 'account_id')
    def onchange_ending_date_account_id(self):
        warning = {}
        acc_move_line_obj = self.env['account.move.line']
        if self.account_id:
            self.currency_id = self.account_id.currency_id and self.account_id.currency_id.id or self.company_id.currency_id.id
        if self.ending_date and self.account_id:
            check_old_record = self.search([('ending_date', '<=', self.ending_date), ('account_id', '=', self.account_id.id), ('state', 'not in', ['done', 'cancel'])])
            if check_old_record:
                if len(check_old_record) > 1:
                    self.ending_date = False
                    self.account_id = False
                    self.currency_id = False
                    warning = {
                        'title': _("Warning"),
                        'message': _("Already form has been created for same date and account.\n Please review or cancel the old record")}
                    return {'warning': warning}
            brs_search = self.search([('ending_date', '<', self.ending_date), ('account_id', '=', self.account_id.id), ('state', '=', 'done')], order='ending_date desc, id desc')
            self.starting_balance = brs_search and brs_search[0].ending_balance or 0.00 
        return
        
    #@api.multi
    def recompute_dr_cr_lines(self):
        acc_move_line_obj = self.env['account.move.line']
        statement_obj = self.env['bank.account.rec.statement.move.line']
        for each in self:
            check_old_record = self.search([('ending_date', '<=', self.ending_date), ('account_id', '=', self.account_id.id), ('state', 'not in', ['done', 'cancel']), ('id', '!=', each.id)])
            if check_old_record:
                raise UserError(_("Warning! \n Already form has been created for same date and account.\n Please review or cancel the old record"))
            brs_search = self.search([('ending_date', '<', each.ending_date), ('account_id', '=', each.account_id.id), ('state', '=', 'done')], order='ending_date desc, id desc')
            each.starting_balance = brs_search and brs_search[0].ending_balance or 0.00 
            acc_move_line_bro = acc_move_line_obj.search([('account_id', '=', each.account_id.id), ('date', '<=', each.ending_date), ('cleared_bank_account', '=', False), ('move_id.state', '!=', 'draft'), ('move_id.journal_id.is_opening_journal', '!=', True)])
#            each.credit_move_line_ids.unlink()
#            each.debit_move_line_ids.unlink()
            for each_cr in each.credit_move_line_ids:
                if not each_cr.move_line_id:
                    each_cr.unlink()
                    continue
                if each_cr.move_line_id and each_cr.move_line_id.move_id.state != 'posted':
                    each_cr.unlink()
                    continue
                if each_cr.move_line_id and each_cr.move_line_id.bank_acc_rec_statement_id and each_cr.move_line_id.bank_acc_rec_statement_id != each:
                    each_cr.unlink()
            for each_dr in each.debit_move_line_ids:
                if not each_dr.move_line_id:
                    each_dr.unlink()
                    continue
                if each_dr.move_line_id and each_dr.move_line_id.move_id.state != 'posted':
                    each_dr.unlink()
                    continue
                if each_dr.move_line_id and each_dr.move_line_id.bank_acc_rec_statement_id and  each_dr.move_line_id.bank_acc_rec_statement_id != each:
                    each_dr.unlink()
            for line in acc_move_line_bro:
                available = False
                res = {
                       'reference': line.name,
                       'date': line.date,
                       'partner_id': line.partner_id.id,
                       'currency_id': line.company_currency_id.id,
                       'amount': line.credit or line.debit,
                       'amount_currency': abs(line.amount_currency),
                       'amount_currency_id': line.currency_id and line.currency_id.id or False,
                       'name': line.account_id.name,
                       'move_line_id': line.id,
                       'types': line.credit and 'cr' or 'dr',
                       'cheque_no': line.cheque_no or "",
                       'cheque_date': line.cheque_date and line.cheque_date or False,
                       'statement_id': each.id
                        }
                if res['types'] == 'cr':
                    for each_cr in each.credit_move_line_ids:
                        if line.id == each_cr.move_line_id.id:
                            available = True
                else:
                    for each_dr in each.debit_move_line_ids:
                        if line.id == each_dr.move_line_id.id:
                            available = True
                if not available:
                    statement_obj.create(res)
        return True
        
    #@api.multi
    def check_difference_balance(self):
        for statement in self:
            if statement.difference != 0.0:
                raise UserError(_("Warning! \n Prior to reconciling a statement, all differences must be accounted for and the Difference balance must be zero. \n Please review and make necessary changes"))
        return True
    
    #@api.multi
    def action_review(self):
        self.check_difference_balance()
        for each in self:
            check_old_record = self.search([('ending_date', '<=', self.ending_date), ('account_id', '=', self.account_id.id), ('state', 'not in', ['done', 'cancel']), ('id', '!=', each.id)])
            if check_old_record:
                raise UserError(_("Warning! \n Already form has been created for same date and account.\n Please review or cancel the old record"))
            each.write({'state': 'to_be_reviewed'})
        return True
    
    #@api.multi
    def action_process(self):
        self.check_difference_balance()
        for each in self:
            process = False
            each_line = each.credit_move_line_ids + each.debit_move_line_ids
            for line in each_line.filtered(lambda l: l.move_line_id and l.move_line_id.cleared_bank_account != True and (not l.move_line_id.bank_acc_rec_statement_id)):
                if line.cleared_bank_account:
                    process = True
                    line.move_line_id.cleared_bank_account = line.cleared_bank_account
                    line.move_line_id.clearing_date = line.clearing_date and line.clearing_date or False 
                    line.move_line_id.bank_acc_rec_statement_id = line.statement_id and line.statement_id.id or False
            if not process:
                raise UserError(_("You cannot cleare bank entries without selecting the entries"))    
            each.write({
                'state': 'done',
                'verified_by_user_id' : self.env.user.id,
                'verified_date': fields.Date.context_today(self),
                })
        return True
            
    #@api.multi
    def action_cancel(self):
        for each in self:
            each_line = each.credit_move_line_ids + each.debit_move_line_ids
            for statement_line in each_line.filtered(lambda l: l.move_line_id and l.move_line_id.bank_acc_rec_statement_id == each):
                statement_line.move_line_id.cleared_bank_account = False
                statement_line.move_line_id.bank_acc_rec_statement_id = False 
                statement_line.move_line_id.clearing_date = False 
                statement_line.cleared_bank_account = False
            each.credit_move_line_ids.unlink()
            each.debit_move_line_ids.unlink()
            each.write({'state': 'cancel'})
        return True
            
    #@api.multi
    def action_cancel_draft(self):
        for each in self:
            each_line = each.credit_move_line_ids + each.debit_move_line_ids
            for statement_line in each_line.filtered(lambda l: l.move_line_id and l.move_line_id.bank_acc_rec_statement_id == each):
                statement_line.move_line_id.cleared_bank_account = False
                statement_line.move_line_id.bank_acc_rec_statement_id = False
                statement_line.move_line_id.clearing_date = False
                statement_line.cleared_bank_account = False
            each.credit_move_line_ids.unlink()
            each.debit_move_line_ids.unlink()
            each.write({
                'state': 'draft',
                'verified_by_user_id': False,
                'verified_date': False
                })
        return True
        
    #@api.multi
    def action_recompute(self):
        MoveLine = self.env['account.move.line']
        tables, where_clause, where_params = MoveLine._query_get()
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        filters = " AND ".join(wheres)
        filters = filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')
        sql = ('''SELECT 
                    l.account_id AS account_id, 
                    COALESCE(SUM(l.debit),0) AS debit, 
                    COALESCE(SUM(l.credit),0) AS credit, 
                    COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) AS balance,
                    COALESCE(SUM(l.amount_currency),0) AS amount_currency \
                FROM account_move_line l\
                    JOIN account_move m ON (l.move_id=m.id)\
                WHERE m.state != 'draft' and l.account_id = %s and l.date <= %s ''' + filters + ''' GROUP BY l.account_id''')
        for each in self:
            params = (each.account_id.id, each.ending_date,) + tuple(where_params)
            self.env.cr.execute(sql, params)
            data = self.env.cr.dictfetchall()
            ledger_balance = 0.00
            ledger_balance_currency = 0.00
            for row in data:
                ledger_balance = row['debit'] - row['credit'] 
                ledger_balance_currency = row['amount_currency']
            each.ledger_balance = ledger_balance
            each.ledger_balance_currency = ledger_balance_currency
            each.recompute_dr_cr_lines()
        return True
        
    #@api.multi
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_("You can remove a form which is only in the draft state"))  
            each_line = each.credit_move_line_ids + each.debit_move_line_ids
            for statement_line in each_line:
                if statement_line.move_line_id.bank_acc_rec_statement_id == each: 
                    statement_line.move_line_id.cleared_bank_account = False
                    statement_line.move_line_id.bank_acc_rec_statement_id = False
                    statement_line.move_line_id.clearing_date = False
                    if statement_line.move_line_id.cleared_bank_account:
                        raise UserError(_("You cannot remove a form when the journal lines are still set as cleared"))
                    if statement_line.move_line_id.bank_acc_rec_statement_id:
                        raise UserError(_("You cannot remove a form when the journal lines are still set as cleared"))  
                    if statement_line.move_line_id.clearing_date:
                        raise UserError(_("You cannot remove a form when the journal lines are still set as cleared"))  
        return super(BankAccountRecStatement, self).unlink()
        
    #@api.multi
    def action_print_report(self):
        report_name = "Bank Account Reconciliation"
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3000
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 8500
        sheet1.col(5).width = 8500
        sheet1.col(6).width = 6500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3000
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 8000
        sheet1.col(12).width = 4000
        sheet1.col(13).width = 8000
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        r5 = 4
        r6 = 5
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 400
        sheet1.row(r4).height = 400
        sheet1.row(r5).height = 350
        sheet1.row(r6).height = 256 * 3
        title1 = self.company_id.name
        title2 = "Name : " + (self.name and self.name or '') 
        title3 = "Account : " + (self.account_id and self.account_id.name_get()[0][1])
        title4 = "Deposits, Credits, and Interest Amount"
        title5 = "Checks, Withdrawals, Debits, and Service Charges Amount"
        title = report_name 
        sheet1.write_merge(r1, r1, 0, 12, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 12, title, Style.main_title())
        sheet1.write_merge(r3, r3, 0, 12, title2, Style.sub_main_title())
        sheet1.write_merge(r4, r4, 0, 12, title3, Style.sub_main_title())
        sheet1.write_merge(r5, r5, 0, 12, title4, Style.subTitle())
        
        sheet1.write(r6, 0, "S.No", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 1, "Cleared?", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 2, "Clearing Date", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 3, "Date", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 4, "Name", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 5, "Reference", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 6, "Partner", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 7, "Amount in Company Currency", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 8, "Currency", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 9, "Amount", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r6, 10, "Account Currency", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write_merge(r6, r6, 11, 12, "Journal Item", Style.contentTextBold(r2, 'black', 'white'))

        row = r6
        s_no = 0
        for each in self:
            for debit_line in each.debit_move_line_ids:
                row += 1
                s_no += 1
                sheet1.row(row).height = 500
                sheet1.write(row, 0, s_no, Style.normal_left())
                sheet1.write(row, 1, (debit_line.cleared_bank_account and 'Yes' or 'No'), Style.normal_left())
                clearing_date = ""
                if debit_line.clearing_date:
                    clearing_date = time.strptime(debit_line.clearing_date, "%Y-%m-%d")
                    clearing_date = time.strftime("%d-%m-%Y", clearing_date)
                sheet1.write(row, 2, clearing_date, Style.normal_left())
                date = ""
                if debit_line.date:
                    date = time.strptime(debit_line.date, "%Y-%m-%d")
                    date = time.strftime("%d-%m-%Y", date)
                sheet1.write(row, 3, date, Style.normal_left())
                sheet1.write(row, 4, (debit_line.name and debit_line.name or ""), Style.normal_left())
                sheet1.write(row, 5, (debit_line.reference and debit_line.reference or ""), Style.normal_left())
                sheet1.write(row, 6, (debit_line.partner_id and debit_line.partner_id.name or ""), Style.normal_left())
                sheet1.write(row, 7, (debit_line.amount and debit_line.amount or 0.00), Style.normal_num_right())
                sheet1.write(row, 8, (debit_line.currency_id and debit_line.currency_id.name or ""), Style.normal_left())
                sheet1.write(row, 9, (debit_line.amount_currency and debit_line.amount_currency or 0.00), Style.normal_num_right())
                sheet1.write(row, 10, (debit_line.amount_currency_id and debit_line.amount_currency_id.name or ""), Style.normal_left())
                sheet1.write_merge(row, row, 11, 12, (debit_line.move_line_id and debit_line.move_line_id.name_get()[0][1] or ""), Style.normal_left())
        
#==============================================credit_move_line_ids================================================  
          
            sheet1.row(row+4).height = 350
            sheet1.write_merge(row+4, row+4, 0, 13, title5, Style.subTitle())
            row += 5
            sheet1.row(row).height = 256 * 3
            sheet1.write(row, 0, "S.No", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 1, "Cleared?", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 2, "Clearing Date", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 3, "Date", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 4, "Name", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 5, "Reference", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 6, "Partner", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 7, "Amount in Company Currency", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 8, "Currency", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 9, "Amount", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 10, "Account Currency", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 11, "Cheque No", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 12, "Cheque Date", Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(row, 13, "Journal Item", Style.contentTextBold(r2, 'black', 'white'))
            
            row += 1
            s_no = 0
            for credit_line in each.credit_move_line_ids:
                s_no += 1
                sheet1.row(row).height = 350
                sheet1.write(row, 0, s_no, Style.normal_left())
                sheet1.write(row, 1, (credit_line.cleared_bank_account and 'Yes' or 'No'), Style.normal_left())
                cr_clearing_date = ""
                if credit_line.clearing_date:
                    cr_clearing_date = time.strptime(credit_line.clearing_date, "%Y-%m-%d")
                    cr_clearing_date = time.strftime("%d-%m-%Y", cr_clearing_date)
                sheet1.write(row, 2, cr_clearing_date, Style.normal_left())
                cr_date = ""
                if credit_line.date:
                    cr_date = time.strptime(credit_line.date, "%Y-%m-%d")
                    cr_date = time.strftime("%d-%m-%Y", cr_date)
                sheet1.write(row, 3, cr_date, Style.normal_left())
                sheet1.write(row, 4, (credit_line.name and credit_line.name or ""), Style.normal_left())
                sheet1.write(row, 5, (credit_line.reference and credit_line.reference or ""), Style.normal_left())
                sheet1.write(row, 6, (credit_line.partner_id and credit_line.partner_id.name or ""), Style.normal_left())
                sheet1.write(row, 7, (credit_line.amount and credit_line.amount or 0.00), Style.normal_num_right())
                sheet1.write(row, 8, (credit_line.currency_id and credit_line.currency_id.name or ""), Style.normal_left())
                sheet1.write(row, 9, (credit_line.amount_currency and credit_line.amount_currency or 0.00), Style.normal_num_right())
                sheet1.write(row, 10, (credit_line.amount_currency_id and credit_line.amount_currency_id.name or ""), Style.normal_left())
                sheet1.write(row, 11, (credit_line.cheque_no and credit_line.cheque_no or ""), Style.normal_left())
                cr_cheque_date = ""
                if credit_line.cheque_date:
                    cr_cheque_date = time.strptime(credit_line.cheque_date, "%Y-%m-%d")
                    cr_cheque_date = time.strftime("%d-%m-%Y", cr_cheque_date)
                sheet1.write(row, 12, cr_cheque_date, Style.normal_left())
                sheet1.write(row, 13, (credit_line.move_line_id and credit_line.move_line_id.name_get()[0][1] or ""), Style.normal_left())
                row += 1
        # stream = cStringIO.StringIO()
        stream = StringIO()
        wbk.save(stream)
        view = self.env.ref('ebits_custom_account.bank_reconciliation_report_wizard_form')
        wiz = self.env['bank.reconciliation.report.wizard'].create({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
            'name': _("Bank Account Reconciliation"),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'res_model': 'bank.reconciliation.report.wizard',
            'target': 'new',
            'res_id': wiz.id,
            }
    
class BankAccountRecStatementMoveLine(models.Model):
    _name = 'bank.account.rec.statement.move.line'
    _description = "Bank Account Reconciliation Move Line"
    
    statement_id = fields.Many2one('bank.account.rec.statement', string='Statement', ondelete="cascade", required=True)
    name = fields.Char(string='Name', size=64, readonly=True, copy=False)
    reference = fields.Char(string='Reference', size=64, readonly=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True, copy=False)
    amount = fields.Float(string='Amount in Company Currency', readonly=True, copy=False, digits=dp.get_precision('Product Price'))
    amount_currency = fields.Float(string='Amount', readonly=True, copy=False, digits=dp.get_precision('Product Price'))
    date = fields.Date(string='Journal Entry Date', readonly=True, copy=False)
    move_line_id = fields.Many2one('account.move.line', string='Journal Item', readonly=True, copy=False, required=True)
    cleared_bank_account = fields.Boolean(string='Cleared?', copy=False)
    research_required = fields.Boolean('Research Required?', readonly=True, copy=False)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True, copy=False)
    amount_currency_id = fields.Many2one('res.currency', string='Account Currency', readonly=True, copy=False)
    clearing_date = fields.Date(string='Clearing Date', copy=False)
    types = fields.Selection([('dr', 'Debit'), ('cr', 'Credit')], string='Cr/Dr', readonly=True, copy=False)
    cheque_no = fields.Char(string='Cheque No', copy=False, readonly=True)
    cheque_date = fields.Date(string='Cheque Date', copy=False, readonly=True)
    
    #@api.multi
    def unlink(self):
        for each in self:
            if each.move_line_id and each.move_line_id.bank_acc_rec_statement_id == each.statement_id:
                each.move_line_id.cleared_bank_account = False
                each.move_line_id.bank_acc_rec_statement_id = False
                each.move_line_id.clearing_date = False
            if each.move_line_id.cleared_bank_account and each.move_line_id.bank_acc_rec_statement_id == each.statement_id:
                raise UserError(_("You cannot delete this entry.\nRelated entries are still in cleared state"))
            if each.move_line_id.bank_acc_rec_statement_id and each.move_line_id.bank_acc_rec_statement_id == each.statement_id:
                raise UserError(_("You cannot delete this entry.\nRelated entries are still in cleared state"))
            if each.move_line_id.clearing_date and each.move_line_id.bank_acc_rec_statement_id == each.statement_id:
                raise UserError(_("You cannot delete this entry.\nRelated entries are still in cleared state"))
        return super(BankAccountRecStatementMoveLine, self).unlink()
    
    @api.onchange('clearing_date')
    def onchange_clearing_date(self):
        warning = {}
        if self.clearing_date:
            if self.clearing_date < self.date:
                self.clearing_date = False
                warning = {
                    'title': _("Warning"),
                    'message': _("Given clearing date must be greater than the journal entry date"),
                    }   
        return {'warning': warning}      
