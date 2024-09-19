# -*- coding: utf-8 -*-

from datetime import datetime
import time
from odoo import api, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class ReportPartnerLedger(models.AbstractModel):
    _inherit = 'report.account.report_partnerledger'

    def _lines(self, data, partner):
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
#                if r['transaction_currency_id']:
#                    r['currency_id'] = r['transaction_currency_id']
#                    r['currency_code'] = r['transaction_currency_code']
                if r['transaction_currency_id'] != self.env.user.company_id.currency_id.id:
                    r['currency_id'] = r['transaction_currency_id']
                    r['currency_code'] = r['transaction_currency_code'] or ""
                else:
                    r['currency_id'] = False
                    r['currency_code'] = ""
            full_account.append(r)
        return full_account

    def _sum_currency_partner(self, data, partner, field):
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
        
    def _sum_balance_currency_partner(self, data, partner):
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
        
    def _sum_partner(self, data, partner, field):
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

    @api.model
    def render_html(self, docids, data=None):
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

        date_from = date_to = False
        if data['form']['date_from']:
            date_from = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")
            date_from = datetime.strftime(date_from, "%d-%m-%Y")
        if data['form']['date_to']:
            date_to = datetime.strptime(data['form']['date_to'], "%Y-%m-%d")
            date_to = datetime.strftime(date_to, "%d-%m-%Y")
        data['form']['date_from_f'] = date_from
        data['form']['date_to_f'] = date_to
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
        if data['form']['warehouse_ids'] and not data['form']['employee_report']:
            warehouse_clause = ""
            warehouse_ids = data['form']['warehouse_ids']
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
            if data['form']['contractor_report']:
                partner_clause = ""
                partner_ids = obj_partner.sudo().search([('customer', '!=', True), ('supplier', '!=', True), ('contractor', '=', True), ('parent_id', '=', False), ('id', 'not in', [1, 3])])
                partner_ids = partner_ids.ids
                if len(partner_ids) > 1:
                    partner_clause += """ AND res.id in """+ str(tuple(partner_ids))
                else:
                    partner_clause += """ AND res.id in ("""+ str(partner_ids[0]) + """)"""
            if data['form']['employee_report']:
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
            if data['form']['partner_report']:
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
        partners = obj_partner.browse(partner_ids)
        partners = sorted(partners, key=lambda x: (x.ref, x.name))

        docargs = {
            'doc_ids': partner_ids,
            'doc_model': self.env['res.partner'],
            'data': data,
            'docs': partners,
            'time': time,
            'lines': self._lines,
            'sum_partner': self._sum_partner,
            'sum_currency_partner': self._sum_currency_partner,
            'sum_balance_currency_partner': self._sum_balance_currency_partner
            }
        return self.env['report'].render('account.report_partnerledger', docargs)
            
class ReportPartnerLedgerCurrency(models.AbstractModel):
    _name = 'report.ebits_custom_account.report_partnerledger_currency'

    def _lines(self, data, partner):
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
#                if r['transaction_currency_id']:
#                    r['currency_id'] =  r['transaction_currency_id']
#                    r['currency_code'] =  r['transaction_currency_code']
                if r['transaction_currency_id'] != self.env.user.company_id.currency_id.id:
                    r['currency_id'] = r['transaction_currency_id']
                    r['currency_code'] = r['transaction_currency_code'] or ""
                else:
                    r['currency_id'] = False
                    r['currency_code'] = ""
            full_account.append(r)
        return full_account

    def _sum_currency_partner(self, data, partner, field):
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
        
    def _sum_balance_currency_partner(self, data, partner):
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
        
    def _sum_partner(self, data, partner, field):
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
        

    @api.model
    def render_html(self, docids, data=None):
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
        date_from = date_to = False
        if data['form']['date_from']:
            date_from = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")
            date_from = datetime.strftime(date_from, "%d-%m-%Y")
        if data['form']['date_to']:
            date_to = datetime.strptime(data['form']['date_to'], "%Y-%m-%d")
            date_to = datetime.strftime(date_to, "%d-%m-%Y")
        data['form']['date_from_f'] = date_from
        data['form']['date_to_f'] = date_to
        data['form']['warehouse_str'] = ""
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
        if data['form']['warehouse_ids'] and not data['form']['employee_report']:
            warehouse_clause = ""
            warehouse_ids = data['form']['warehouse_ids']
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
            if data['form']['contractor_report']:
                partner_clause = ""
                partner_ids = obj_partner.sudo().search([('customer', '!=', True), ('supplier', '!=', True), ('contractor', '=', True), ('parent_id', '=', False), ('id', 'not in', [1, 3])])
                partner_ids = partner_ids.ids
                if len(partner_ids) > 1:
                    partner_clause += """ AND res.id in """+ str(tuple(partner_ids))
                else:
                    partner_clause += """ AND res.id in ("""+ str(partner_ids[0]) + """)"""
            if data['form']['employee_report']:
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
            if data['form']['partner_report']:
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
        partners = obj_partner.browse(partner_ids)
        partners = sorted(partners, key=lambda x: (x.ref, x.name))

        docargs = {
            'doc_ids': partner_ids,
            'doc_model': self.env['res.partner'],
            'data': data,
            'docs': partners,
            'time': time,
            'lines': self._lines,
            'sum_partner': self._sum_partner,
            'sum_currency_partner': self._sum_currency_partner,
            'sum_balance_currency_partner': self._sum_balance_currency_partner
            }
        return self.env['report'].render('ebits_custom_account.report_partnerledger_currency', docargs)
