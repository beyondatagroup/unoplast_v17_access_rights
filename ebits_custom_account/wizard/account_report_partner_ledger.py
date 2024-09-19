# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

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

class AccountPartnerLedgerOutput(models.TransientModel):
    _name = "account.report.partner.ledger.output"
    
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='Format', readonly=True)

class AccountPartnerLedger(models.TransientModel):
    _inherit = "account.report.partner.ledger"

    warehouse_ids = fields.Many2many('stock.warehouse', string="Warehouse/Branch")
    partner_ids = fields.Many2many('res.partner', string="Select Partner")
    initial_balance = fields.Boolean(string='Include Initial Balances',
                                    help='If you selected date, this field allow you to add a row to display the amount of debit/credit/balance that precedes the filter you\'ve set.', default=True)
    reconciled = fields.Boolean('Reconciled Entries', default=True)
    partner_account_ids = fields.Many2many('account.account', 'etc_partner_ledger_account_account_rel', 'partner_ledger_id', 'account_id', string="Account")
                                    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(AccountPartnerLedger, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.env.context.get('partner'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='partner_ids']"):
                node.set('domain', "['|', ('customer', '=', True), ('supplier', '=', True), ('parent_id', '=', False)]")
            res['arch'] = etree.tostring(doc)
        if self.env.context.get('employee'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='partner_ids']"):
                if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                    hr_employee = self.env['hr.employee'].search([])
                    emp_partner_id = []
                    for each_emp in hr_employee:
                        emp_partner_id.append(each_emp.address_home_id.id)
                    node.set('domain', "[('id', 'in', " + str(emp_partner_id) + ")]")
                else:
                    node.set('domain', "[('customer', '!=', True), ('supplier', '!=', True), ('contractor', '!=', True), ('parent_id', '=', False), ('id', 'not in', [1, 3])]")
            res['arch'] = etree.tostring(doc)
        if self.env.context.get('contractor'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='partner_ids']"):
                node.set('domain', "[('customer', '!=', True), ('supplier', '!=', True), ('contractor', '=', True), ('parent_id', '=', False), ('id', 'not in', [1, 3])]")
            res['arch'] = etree.tostring(doc)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='warehouse_ids']"):
                warehouse_id = []
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                if warehouse_id:
                    node.set('domain', "[('id', 'in', " + str(warehouse_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res
        
    @api.onchange('result_selection')
    def onchange_journal_id(self):
        domain = {'partner_account_ids': []}
        if self.result_selection == 'customer':
            domain['partner_account_ids'] = [('internal_type', '=', 'receivable')]
        elif self.result_selection == 'supplier':
            domain['partner_account_ids'] = [('internal_type', '=', 'payable')]
        elif self.result_selection == 'customer_supplier':
            domain['partner_account_ids'] = [('internal_type', 'in', ['receivable', 'payable'])]
        return {'domain': domain}
        
    def _build_contexts_custom(self, data):
        result = {}
        result['journal_ids'] = 'journal_ids' in data['form'] and data['form']['journal_ids'] or False
        result['state'] = 'target_move' in data['form'] and data['form']['target_move'] or ''
        result['date_from'] = False
        result['date_to'] = data['form']['date_to'] or False
        result['strict_range'] = True if result['date_from'] else False
        return result
        
    def _print_report(self, data):
        data = self.pre_print_report(data)
        data['form'].update(self.read(['warehouse_ids', 'partner_ids', 'initial_balance', 'partner_account_ids'])[0])
        data['form'].update({'reconciled': self.reconciled, 'amount_currency': self.amount_currency})
        used_context_custom = self._build_contexts_custom(data)
        data['form']['used_context_custom'] = dict(used_context_custom, lang=self.env.context.get('lang', 'en_US'))
        if self.env.context.get('contractor'):
            data['form'].update({'partner_report': False, 'employee_report': False, 'contractor_report': True})
        if self.env.context.get('employee'):
            data['form'].update({'partner_report': False, 'employee_report': True, 'contractor_report': False})
        if self.env.context.get('partner'):
            data['form'].update({'partner_report': True, 'employee_report': False, 'contractor_report': False})
        warehouse_list = []
        warehouse_str = ""
        if data['form']['warehouse_ids']:
            for each in self.warehouse_ids:
                warehouse_list.append(each.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace("[", "").replace("]", "").replace("u'", "").replace("'", "")
        data['form'].update({'warehouse_name': warehouse_str})
        if data['form']['initial_balance']:
            if not data['form']['date_from']:
                raise UserError(_("You must define a Start Date, If you want to print the inital balance"))
        if self.amount_currency:
            return self.env['report'].with_context(landscape=True).get_action(self, 'ebits_custom_account.report_partnerledger_currency', data=data)
        else:
            return self.env['report'].get_action(self, 'account.report_partnerledger', data=data)
        
        
    def _sum_partner_excel(self, data, partner, field):
        if field not in ['debit', 'credit', 'debit - credit']:
            return
        result = result_init = 0.00
        if data['form']['initial_balance']:
            query_get_data_init = self.env['account.move.line'].with_context(date_from=data['form']['date_from'], date_to=False, initial_bal=True, strict_range=True)._query_get()
            reconcile_clause_init = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '

            params_init = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data_init[2]
            query_init = """SELECT sum(""" + field + """)
                    FROM """ + query_get_data_init[0] + """, account_move AS m
                    WHERE "account_move_line".partner_id = %s
                        AND m.id = "account_move_line".move_id
                        AND m.state IN %s
                        AND account_id IN %s
                        AND """ + query_get_data_init[1] + reconcile_clause_init
            self.env.cr.execute(query_init, tuple(params_init))

            contemp_init = self.env.cr.fetchone()
            if contemp_init is not None:
                result_init = contemp_init[0] or 0.0
        
        
        query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()
        reconcile_clause = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '

        params = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        query = """SELECT sum(""" + field + """)
                FROM """ + query_get_data[0] + """, account_move AS m
                WHERE "account_move_line".partner_id = %s
                    AND m.id = "account_move_line".move_id
                    AND m.state IN %s
                    AND account_id IN %s
                    AND """ + query_get_data[1] + reconcile_clause
        self.env.cr.execute(query, tuple(params))

        contemp = self.env.cr.fetchone()
        if contemp is not None:
            result = contemp[0] or 0.0
        return result + result_init
        
    def _lines_excel(self, data, partner):
        full_account = []
        debit_opening = credit_opening = progress_opening = 0.00
        debit_currency_opening = credit_currency_opening = progress_currency_opening = 0.00
        if data['form']['initial_balance']:
            query_get_data_init = self.env['account.move.line'].with_context(date_from=data['form']['date_from'], date_to=False, initial_bal=True, strict_range=True)._query_get()
            reconcile_clause_init = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '
            params_init = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data_init[2]
            query_init = """
                SELECT "account_move_line".id, "account_move_line".date, j.code, acc.code as a_code, acc.name as a_name, "account_move_line".ref, m.name as move_name, "account_move_line".name, "account_move_line".debit, "account_move_line".credit, "account_move_line".amount_currency,"account_move_line".currency_id, c.symbol AS currency_code
                FROM """ + query_get_data_init[0] + """
                LEFT JOIN account_journal j ON ("account_move_line".journal_id = j.id)
                LEFT JOIN account_account acc ON ("account_move_line".account_id = acc.id)
                LEFT JOIN res_currency c ON ("account_move_line".currency_id=c.id)
                LEFT JOIN account_move m ON (m.id="account_move_line".move_id)
                WHERE "account_move_line".partner_id = %s
                    AND m.state IN %s
                    AND "account_move_line".account_id IN %s AND """ + query_get_data_init[1] + reconcile_clause_init + """
                    ORDER BY "account_move_line".date"""
            self.env.cr.execute(query_init, tuple(params_init))
            res_init = self.env.cr.dictfetchall()
            sum_init = sum_currency_init = 0.0
            for r_init in res_init:
                debit_opening += r_init['debit']
                credit_opening += r_init['credit']
                if r_init['amount_currency']:
                    if r_init['debit']:
                        debit_currency_opening += abs(r_init['amount_currency'])
                    if r_init['credit']:
                        credit_currency_opening += abs(r_init['amount_currency'])
            progress_opening = debit_opening - credit_opening
            progress_currency_opening = debit_currency_opening - credit_currency_opening
            full_account.append({'date': '', 'code': '', 'a_code': '',
                'a_name': '', 'displayed_name': 'Opening Balance',
                'debit': debit_opening, 'credit': credit_opening,
                'progress': progress_opening, 'debit_currency': debit_currency_opening,
                'credit_currency': credit_currency_opening, 'progress_currency': progress_currency_opening,
                'currency_code': ''
                })
        
        query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()

        reconcile_clause = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '
        params = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        query = """
            SELECT "account_move_line".id, "account_move_line".date, j.code, acc.code as a_code, acc.name as a_name, "account_move_line".ref, m.name as move_name, "account_move_line".name, "account_move_line".debit, "account_move_line".credit, "account_move_line".amount_currency,"account_move_line".currency_id, c.symbol AS currency_code, res_p.transaction_currency_id AS transaction_currency_id, res_c.symbol AS transaction_currency_code
            FROM """ + query_get_data[0] + """
            LEFT JOIN account_journal j ON ("account_move_line".journal_id = j.id)
            LEFT JOIN account_account acc ON ("account_move_line".account_id = acc.id)
            LEFT JOIN res_currency c ON ("account_move_line".currency_id=c.id)
            LEFT JOIN account_move m ON (m.id="account_move_line".move_id)
            LEFT JOIN res_partner res_p ON (res_p.id="account_move_line".partner_id)
            LEFT JOIN res_currency res_c ON (res_c.id=res_p.transaction_currency_id)
            WHERE "account_move_line".partner_id = %s
                AND m.state IN %s
                AND "account_move_line".account_id IN %s AND """ + query_get_data[1] + reconcile_clause + """
                ORDER BY "account_move_line".date"""
        self.env.cr.execute(query, tuple(params))
        res = self.env.cr.dictfetchall()
        sum = sum_currency = 0.0
        lang_code = self.env.context.get('lang') or 'en_US'
        lang = self.env['res.lang']
        lang_id = lang._lang_get(lang_code)
        date_format = lang_id.date_format
        sum += progress_opening
        sum_currency += progress_currency_opening
        for r in res:
            r['date'] = datetime.strptime(r['date'], DEFAULT_SERVER_DATE_FORMAT).strftime(date_format)
            r['displayed_name'] = '-'.join(
                r[field_name] for field_name in ('move_name', 'ref', 'name')
                if r[field_name] not in (None, '', '/')
            )
            sum += r['debit'] - r['credit']
            r['progress'] = sum
            r['progress_currency'] = sum_currency
            r['debit_currency'] = r['credit_currency'] = 0.00
            if r['amount_currency']:
                if r['debit']:
                    r['debit_currency'] = abs(r['amount_currency'])
                if r['credit']:
                    r['credit_currency'] = abs(r['amount_currency'])
                sum_currency += r['debit_currency'] - r['credit_currency']
                r['progress_currency'] = sum_currency
            else:
                if r['transaction_currency_id'] != self.env.user.company_id.currency_id.id:
                    r['currency_id'] = r['transaction_currency_id']
                    r['currency_code'] = r['transaction_currency_code'] or ""
                else:
                    r['currency_id'] = False
                    r['currency_code'] = ""
            full_account.append(r)
        return full_account

    def _sum_currency_partner_excel(self, data, partner, field):
        if field not in ['debit', 'credit']:
            return
        result = result_init = 0.00
        
        if data['form']['initial_balance']:
            query_get_data_init = self.env['account.move.line'].with_context(date_from=data['form']['date_from'], date_to=False, initial_bal=True, strict_range=True)._query_get()
            reconcile_clause_init = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '

            params_init = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data_init[2]
            query_init = """SELECT """ + field + """ , abs(amount_currency) as amount_currency
                    FROM """ + query_get_data_init[0] + """, account_move AS m
                    WHERE "account_move_line".partner_id = %s
                        AND m.id = "account_move_line".move_id
                        AND m.state IN %s
                        AND account_id IN %s
                        AND """ + query_get_data_init[1] + reconcile_clause_init
            self.env.cr.execute(query_init, tuple(params_init))
            contemp_init = self.env.cr.dictfetchall()
            for r_init in contemp_init:
                if r_init[field]:
                    result_init += r_init['amount_currency']
        
        query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()
        reconcile_clause = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '

        params = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        query = """SELECT """ + field + """ , abs(amount_currency) as amount_currency
                FROM """ + query_get_data[0] + """, account_move AS m
                WHERE "account_move_line".partner_id = %s
                    AND m.id = "account_move_line".move_id
                    AND m.state IN %s
                    AND account_id IN %s
                    AND """ + query_get_data[1] + reconcile_clause
        self.env.cr.execute(query, tuple(params))
        contemp = self.env.cr.dictfetchall()
        for r in contemp:
            if r[field]:
                result += r['amount_currency']
        return result + result_init
        
    def _sum_balance_currency_partner_excel(self, data, partner):
        credit = debit = result = 0.0
        credit_init = debit_init = result_init = 0.0
        if data['form']['initial_balance']:
            query_get_data_init = self.env['account.move.line'].with_context(date_from=data['form']['date_from'], date_to=False, initial_bal=True, strict_range=True)._query_get()
            reconcile_clause_init = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '

            params_init = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data_init[2]
            query_init = """SELECT credit as credit, debit as debit , abs(amount_currency) as amount_currency
                    FROM """ + query_get_data_init[0] + """, account_move AS m
                    WHERE "account_move_line".partner_id = %s
                        AND m.id = "account_move_line".move_id
                        AND m.state IN %s
                        AND account_id IN %s
                        AND """ + query_get_data_init[1] + reconcile_clause_init
            self.env.cr.execute(query_init, tuple(params_init))

            contemp_init = self.env.cr.dictfetchall()
            for r_init in contemp_init:
                if r_init['credit']:
                    credit_init += r_init['amount_currency']
                if r_init['debit']:
                    debit_init += r_init['amount_currency']
            result_init += debit_init - credit_init
        
        
        query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()
        reconcile_clause = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '

        params = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        query = """SELECT credit as credit, debit as debit , abs(amount_currency) as amount_currency
                FROM """ + query_get_data[0] + """, account_move AS m
                WHERE "account_move_line".partner_id = %s
                    AND m.id = "account_move_line".move_id
                    AND m.state IN %s
                    AND account_id IN %s
                    AND """ + query_get_data[1] + reconcile_clause
        self.env.cr.execute(query, tuple(params))

        contemp = self.env.cr.dictfetchall()
        for r in contemp:
            if r['credit']:
                credit += r['amount_currency']
            if r['debit']:
                debit += r['amount_currency']
        result += debit - credit
        return result + result_init
        
    @api.multi
    def print_excel_report(self):
        self.ensure_one()
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['date_from', 'date_to', 'journal_ids', 'target_move', 'initial_balance'])[0]
        if data['form']['initial_balance']:
            if not data['form']['date_from']:
                raise UserError(_("You must define a Start Date, If you want to print the inital balance"))
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        if data['form']['initial_balance']:
            used_context_custom = self._build_contexts_custom(data)
            data['form']['used_context_custom'] = dict(used_context_custom, lang=self.env.context.get('lang', 'en_US'))
        data = self.pre_print_report(data)
        data['form'].update(self.read(['result_selection', 'warehouse_ids', 'partner_ids', 'partner_account_ids'])[0])
        data['form'].update({'reconciled': self.reconciled, 'amount_currency': self.amount_currency})
        data['computed'] = {}

        obj_partner = self.env['res.partner']
        if data['form']['initial_balance']:
            query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context_custom', {}))._query_get()
        else:
            query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()
        data['computed']['move_state'] = ['draft', 'posted']
        if data['form'].get('target_move', 'all') == 'posted':
            data['computed']['move_state'] = ['posted']
        result_selection = data['form'].get('result_selection', 'customer')
        if result_selection == 'supplier':
            data['computed']['ACCOUNT_TYPE'] = ['payable']
        elif result_selection == 'customer':
            data['computed']['ACCOUNT_TYPE'] = ['receivable']
        else:
            data['computed']['ACCOUNT_TYPE'] = ['payable', 'receivable']
            
        if data['form']['partner_account_ids']:
            data['computed']['account_ids'] = data['form']['partner_account_ids']
        else:
            self.env.cr.execute("""
                SELECT a.id
                FROM account_account a
                WHERE a.internal_type IN %s
                AND NOT a.deprecated""", (tuple(data['computed']['ACCOUNT_TYPE']),))
            data['computed']['account_ids'] = [a for (a,) in self.env.cr.fetchall()]
        params = [tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        reconcile_clause = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '
        warehouse_clause = ""
        warehouse_ids = []
        if data['form']['warehouse_ids']:
            warehouse_clause = ""
            warehouse_ids = data['form']['warehouse_ids']
            if len(warehouse_ids) > 1:
                warehouse_clause += " AND res.delivery_warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_clause += " AND res.delivery_warehouse_id = "+ str(warehouse_ids[0])
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed') and not self.env.context.get('employee'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                if len(warehouse_ids) > 1:
                    warehouse_clause += " AND res.delivery_warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_clause += " AND res.delivery_warehouse_id = "+ str(warehouse_ids[0])
        partner_clause = ""
        partner_ids = []
        if data['form']['partner_ids']:
            partner_clause = ""
            partner_ids = data['form']['partner_ids']
            if len(partner_ids) > 1:
                partner_clause += """ AND res.id in """+ str(tuple(partner_ids))
            else:
                partner_clause += """ AND res.id in ("""+ str(partner_ids[0]) + """)"""
        else:
            if self.env.context.get('contractor'):
                partner_clause = ""
                partner_ids = obj_partner.sudo().search([('customer', '!=', True), ('supplier', '!=', True), ('contractor', '=', True), ('parent_id', '=', False), ('id', 'not in', [1, 3])])
                partner_ids = partner_ids.ids
                if len(partner_ids) > 1:
                    partner_clause += """ AND res.id in """+ str(tuple(partner_ids))
                else:
                    partner_clause += """ AND res.id in ("""+ str(partner_ids[0]) + """)"""
            if self.env.context.get('employee'):
                partner_clause = ""
                if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                    hr_employee = self.env['hr.employee'].search([])
                    partner_ids = []
                    for each_emp in hr_employee:
                        partner_ids.append(each_emp.address_home_id.id)
                else:
                    partner_ids = obj_partner.sudo().search([('customer', '!=', True), ('supplier', '!=', True), ('contractor', '!=', True), ('parent_id', '=', False), ('id', 'not in', [1, 3])])
                    partner_ids = partner_ids.ids
                if len(partner_ids) > 1:
                    partner_clause += """ AND res.id in """+ str(tuple(partner_ids))
                else:
                    partner_clause += """ AND res.id in ("""+ str(partner_ids[0]) + """)"""
            if self.env.context.get('partner'):
                partner_clause = ""
                partner_ids = obj_partner.sudo().search(['|', ('customer', '=', True), ('supplier', '=', True), ('parent_id', '=', False)])
                partner_ids = partner_ids.ids
                if len(partner_ids) > 1:
                    partner_clause += """ AND res.id in """+ str(tuple(partner_ids))
                else:
                    partner_clause += """ AND res.id in ("""+ str(partner_ids[0]) + """)"""
        query = """
            SELECT DISTINCT "account_move_line".partner_id
            FROM """ + query_get_data[0] + """, account_account AS account, account_move AS am, res_partner res
            WHERE "account_move_line".partner_id IS NOT NULL
                AND res.id = "account_move_line".partner_id
                AND "account_move_line".account_id = account.id
                AND am.id = "account_move_line".move_id
                AND am.state IN %s
                AND "account_move_line".account_id IN %s
                AND NOT account.deprecated
                AND """ + query_get_data[1] + reconcile_clause + warehouse_clause + partner_clause
        self.env.cr.execute(query, tuple(params))
        partner_ids = [res['partner_id'] for res in self.env.cr.dictfetchall()]
        partners = obj_partner.sudo().browse(partner_ids)
        partners = sorted(partners, key=lambda x: (x.ref, x.name))
        if not partners:
            raise ValidationError(_('Entries not available to print.'))
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        if self.env.context.get('employee'):
            sheet1 = wbk.add_sheet("Employee Ledger")
        elif self.env.context.get('contractor'):
            sheet1 = wbk.add_sheet("Contractor Ledger")
        else:
            sheet1 = wbk.add_sheet("Partner Ledger")
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(6)
        sheet1.show_grid = False 
        sheet1.col(0).width = 3000
        sheet1.col(1).width = 3000
        sheet1.col(2).width = 9000
        sheet1.col(3).width = 9000
        sheet1.col(4).width = 4000
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 4000
        sheet1.col(7).width = 1000
        sheet1.col(8).width = 4000
        sheet1.col(9).width = 4000
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
        
        if self.env.context.get('employee'):
            title = "Employee Ledger"
        elif self.env.context.get('contractor'):
            title = "Contractor Ledger"
        else:
            title = "Partner Ledger"
        if data['form']['amount_currency']:
            sheet1.write_merge(r1, r1, 0, 11, self.env.user.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 11, title, Style.sub_title_color())
        else:
            sheet1.write_merge(r1, r1, 0, 7, self.env.user.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 7, title, Style.sub_title_color())
        sheet1.write_merge(r3, r3, 0, 1, "Target Moves", Style.subTitle())
        if data['form']['target_move'] == 'all':
            sheet1.write_merge(r4, r4, 0, 1, "All Entries", Style.subTitle())
        if data['form']['target_move'] == 'posted':
            sheet1.write_merge(r4, r4, 0, 1, "All Posted Entries", Style.subTitle())
        date_from = date_to = False
        if data['form']['date_from']:
            date_from = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")
            date_from = datetime.strftime(date_from, "%d-%m-%Y")
            sheet1.write(r3, 2, "Date From", Style.subTitle())
            sheet1.write(r4, 2, date_from, Style.normal_date_alone())
        else:
            sheet1.write(r3, 2, "", Style.subTitle())
            sheet1.write(r4, 2, "", Style.subTitle())
        if data['form']['date_to']:
            date_to = datetime.strptime(data['form']['date_to'], "%Y-%m-%d")
            date_to = datetime.strftime(date_to, "%d-%m-%Y")
            sheet1.write(r3, 3, "Date To", Style.subTitle())
            sheet1.write(r4, 3, date_to, Style.normal_date_alone())
        else:
            sheet1.write(r3, 3, "", Style.subTitle())
            sheet1.write(r4, 3, "", Style.subTitle())
        
        if data['form']['amount_currency']:
            sheet1.write_merge(r3, r3, 4, 5, "LC - Local Currency", Style.subTitle())
            sheet1.write_merge(r4, r4, 4, 5, "TC - Transaction Currency", Style.subTitle())
            sheet1.write_merge(r3, r3, 6, 11, "", Style.subTitle())
            sheet1.write_merge(r4, r4, 6, 11, "", Style.subTitle())
        else:
            sheet1.write_merge(r3, r3, 4, 7, "", Style.subTitle())
            sheet1.write_merge(r4, r4, 4, 7, "", Style.subTitle())
            
        row = r5 +1
        sheet1.row(row).height = 256 * 3
        sheet1.write(row, 0, "Date", Style.subTitle_color())
        sheet1.write(row, 1, "JNRL", Style.subTitle_color())
        sheet1.write(row, 2, "Account", Style.subTitle_color())
        sheet1.write(row, 3, "Ref", Style.subTitle_color())
        if data['form']['amount_currency']:
            sheet1.write(row, 4, "Debit (LC*)", Style.subTitle_color())
            sheet1.write(row, 5, "Credit (LC*)", Style.subTitle_color())
            sheet1.write(row, 6, "Balance (LC*)", Style.subTitle_color())
            sheet1.write(row, 7, "", Style.subTitle_color())
            sheet1.write(row, 8, "Debit (TC*)", Style.subTitle_color())
            sheet1.write(row, 9, "Credit (TC*)", Style.subTitle_color())
            sheet1.write(row, 10, "Balance (TC*)", Style.subTitle_color())
            sheet1.write(row, 11, "", Style.subTitle_color())
        else:
            sheet1.write(row, 4, "Debit", Style.subTitle_color())
            sheet1.write(row, 5, "Credit", Style.subTitle_color())
            sheet1.write(row, 6, "Balance", Style.subTitle_color())
            sheet1.write(row, 7, "", Style.subTitle_color())
        tot_debit = tot_credit = tot_balance = tot_debit_currency = tot_credit_currency = tot_balance_currency = 0.00
        for each in partners:
            row = row + 1
            sheet1.row(row).height = 500
            name = ""
            tot_debit = tot_credit = tot_balance = tot_debit_currency = tot_credit_currency = tot_balance_currency = 0.00
            name = (each.ref or "") + (each.name and " - " + each.name or "") + (each.transaction_currency_id and " ( " + each.transaction_currency_id.symbol + " )"or "")
            sheet1.write_merge(row, row, 0, 3, name, Style.subTitle_sub_color_left())
            tot_debit = self._sum_partner_excel(data, each, 'debit')
            tot_credit = self._sum_partner_excel(data, each, 'credit')
            tot_balance = self._sum_partner_excel(data, each, 'debit - credit')
            sheet1.write(row, 4, tot_debit, Style.subTitle_float_sub_color())
            sheet1.write(row, 5, tot_credit, Style.subTitle_float_sub_color())
            sheet1.write(row, 6, tot_balance, Style.subTitle_float_sub_color())
            sheet1.write(row, 7, "", Style.subTitle())
            if data['form']['amount_currency']:
                tot_debit_currency = self._sum_currency_partner_excel(data, each, 'debit')
                tot_credit_currency = self._sum_currency_partner_excel(data, each, 'credit')
                tot_balance_currency = self._sum_balance_currency_partner_excel(data, each)
                sheet1.write(row, 8, tot_debit_currency, Style.subTitle_float_sub_color())
                sheet1.write(row, 9, tot_credit_currency, Style.subTitle_float_sub_color())
                sheet1.write(row, 10, tot_balance_currency, Style.subTitle_float_sub_color())
                sheet1.write(row, 11, "", Style.subTitle_sub_color_left())
            for line in self._lines_excel(data, each):
                row = row + 1
                sheet1.row(row).height = 500
                sheet1.write(row, 0, line['date'], Style.normal_date_alone())
                sheet1.write(row, 1, line['code'], Style.normal_left())
                sheet1.write(row, 2, (line['a_code'] and line['a_code'] or "") + " " + (line['a_name'] and line['a_name'] or ""), Style.normal_left())
                sheet1.write(row, 3, line['displayed_name'], Style.normal_left())
                sheet1.write(row, 4, line['debit'], Style.normal_num_right_3separator())
                sheet1.write(row, 5, line['credit'], Style.normal_num_right_3separator())
                sheet1.write(row, 6, line['progress'], Style.normal_num_right_3separator())
                sheet1.write(row, 7, self.env.user.company_id.currency_id.symbol, Style.normal_right())
                if data['form']['amount_currency']:
                    sheet1.write(row, 8, line['debit_currency'], Style.normal_num_right_3separator())
                    sheet1.write(row, 9, line['credit_currency'], Style.normal_num_right_3separator())
                    sheet1.write(row, 10, line['progress_currency'], Style.normal_num_right_3separator())
                    sheet1.write(row, 11, line['currency_code'], Style.normal_right())
                    
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.env.cr.execute(""" DELETE FROM account_report_partner_ledger_output""")
        
        attach_id = self.env['account.report.partner.ledger.output'].create({'name': title + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.report.partner.ledger.output',
                'res_id': attach_id.id,
                'type': 'ir.actions.act_window',
                'target': 'new'
                }
