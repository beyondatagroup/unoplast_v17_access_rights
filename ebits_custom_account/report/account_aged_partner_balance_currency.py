# -*- coding: utf-8 -*-

import time
from odoo.tools import float_is_zero
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _


class ReportAgedPartnerBalance(models.AbstractModel):

    _name = 'report.ebits_custom_account.report_agedpartnerbalance_currency'
    
    def _get_partner_move_lines_company_currency(self, account_type, date_from, target_move, period_length, partner_bro_ids):
        periods = {}
        start = datetime.strptime(date_from, "%Y-%m-%d")
        for i in range(5)[::-1]:
            stop = start - relativedelta(days=period_length)
            periods[str(i)] = {
                'name': (i!=0 and (str((5-(i+1)) * period_length) + '-' + str((5-i) * period_length)) or ('+'+str(4 * period_length))),
                'stop': start.strftime('%Y-%m-%d'),
                'start': (i!=0 and stop.strftime('%Y-%m-%d') or False),
            }
            start = stop - relativedelta(days=1)

        res = []
        total = []
        cr = self.env.cr
        user_company = self.env.user.company_id.id
        move_state = ['draft', 'posted']
        if target_move == 'posted':
            move_state = ['posted']
        arg_list = (tuple(move_state), tuple(account_type))
        #build the reconciliation clause to see what partner needs to be printed
        reconciliation_clause = '(l.reconciled IS FALSE)'
        cr.execute('SELECT debit_move_id, credit_move_id FROM account_partial_reconcile where create_date > %s', (date_from,))
        reconciled_after_date = []
        for row in cr.fetchall():
            reconciled_after_date += [row[0], row[1]]
        if reconciled_after_date:
            reconciliation_clause = '(l.reconciled IS FALSE OR l.id IN %s)'
            arg_list += (tuple(reconciled_after_date),)
        arg_list += (date_from, user_company)
        partner_clause = ""
        if len(partner_bro_ids) > 1:
            partner_clause = " AND res_partner.id in " + str(tuple(partner_bro_ids))
        else:
            partner_clause = " AND res_partner.id = " + str(partner_bro_ids[0])
        query = '''
            SELECT DISTINCT l.partner_id, UPPER(res_partner.name)
            FROM account_move_line AS l left join res_partner on l.partner_id = res_partner.id, account_account, account_move am
            WHERE (l.account_id = account_account.id)
                AND (l.move_id = am.id)
                AND (am.state IN %s)
                AND (account_account.internal_type IN %s) ''' + partner_clause + '''
                AND ''' + reconciliation_clause + '''
                AND (l.date <= %s)
                AND l.company_id = %s
            ORDER BY UPPER(res_partner.name)'''
        cr.execute(query, arg_list)

        partners = cr.dictfetchall()
        # put a total of 0
        for i in range(7):
            total.append(0)

        # Build a string like (1,2,3) for easy use in SQL query
        partner_ids = [partner['partner_id'] for partner in partners]
        lines = dict((partner['partner_id'] or False, []) for partner in partners)
        if not partner_ids:
            return [], [], []
        # This dictionary will store the not due amount of all partners
        undue_amounts = {}
        if len(partner_ids) > 1:
            query = '''SELECT l.id
                    FROM account_move_line AS l, account_account, account_move am
                    WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                        AND (am.state IN %s)
                        AND (account_account.internal_type IN %s)
                        AND (COALESCE(l.date_maturity,l.date) > %s)\
                        AND ((l.partner_id IN %s) OR (l.partner_id IS NULL))
                    AND (l.date <= %s)
                    AND l.company_id = %s'''
            cr.execute(query, (tuple(move_state), tuple(account_type), date_from, tuple(partner_ids), date_from, user_company))
        else:
            query = '''SELECT l.id
                    FROM account_move_line AS l, account_account, account_move am
                    WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                        AND (am.state IN %s)
                        AND (account_account.internal_type IN %s)
                        AND (COALESCE(l.date_maturity,l.date) > %s)\
                        AND ((l.partner_id = %s) OR (l.partner_id IS NULL))
                    AND (l.date <= %s)
                    AND l.company_id = %s'''
            cr.execute(query, (tuple(move_state), tuple(account_type), date_from, partner_ids[0], date_from, user_company))
        aml_ids = cr.fetchall()
        aml_ids = aml_ids and [x[0] for x in aml_ids] or []
        for line in self.env['account.move.line'].browse(aml_ids):
            if line.partner_id:
                partner_id = line.partner_id.id or False
                if partner_id not in undue_amounts:
                    undue_amounts[partner_id] = 0.0
                line_amount = line.balance
                if line.balance == 0:
                    continue
                for partial_line in line.matched_debit_ids:
                    if partial_line.create_date[:10] <= date_from:
                        line_amount += partial_line.amount
                for partial_line in line.matched_credit_ids:
                    if partial_line.create_date[:10] <= date_from:
                        line_amount -= partial_line.amount
                if not self.env.user.company_id.currency_id.is_zero(line_amount):
                    undue_amounts[partner_id] += line_amount
                    lines[partner_id].append({
                        'line': line,
                        'amount': line_amount,
                        'period': 6,
                    })
        # Use one query per period and store results in history (a list variable)
        # Each history will contain: history[1] = {'<partner_id>': <partner_debit-credit>}
        history = []
        for i in range(5):
            if len(partner_ids) > 1:
                args_list = (tuple(move_state), tuple(account_type), tuple(partner_ids),)
            else:
                args_list = (tuple(move_state), tuple(account_type), partner_ids[0],)
            dates_query = '(COALESCE(l.date_maturity,l.date)'

            if periods[str(i)]['start'] and periods[str(i)]['stop']:
                dates_query += ' BETWEEN %s AND %s)'
                args_list += (periods[str(i)]['start'], periods[str(i)]['stop'])
            elif periods[str(i)]['start']:
                dates_query += ' >= %s)'
                args_list += (periods[str(i)]['start'],)
            else:
                dates_query += ' <= %s)'
                args_list += (periods[str(i)]['stop'],)
            args_list += (date_from, user_company)
            if len(partner_ids) > 1:
                query = '''SELECT l.id
                        FROM account_move_line AS l, account_account, account_move am
                        WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                            AND (am.state IN %s)
                            AND (account_account.internal_type IN %s)
                            AND ((l.partner_id IN %s) OR (l.partner_id IS NULL))
                            AND ''' + dates_query + '''
                        AND (l.date <= %s)
                        AND l.company_id = %s'''
            else:
                query = '''SELECT l.id
                        FROM account_move_line AS l, account_account, account_move am
                        WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                            AND (am.state IN %s)
                            AND (account_account.internal_type IN %s)
                            AND ((l.partner_id = %s) OR (l.partner_id IS NULL))
                            AND ''' + dates_query + '''
                        AND (l.date <= %s)
                        AND l.company_id = %s'''
            cr.execute(query, args_list)
            partners_amount = {}
            aml_ids = cr.fetchall()
            aml_ids = aml_ids and [x[0] for x in aml_ids] or []
            for line in self.env['account.move.line'].browse(aml_ids):
                if line.partner_id:
                    partner_id = line.partner_id.id or False
                    if partner_id not in partners_amount:
                        partners_amount[partner_id] = 0.0
                    line_amount = line.balance
                    if line.balance == 0:
                        continue
                    for partial_line in line.matched_debit_ids:
                        if partial_line.create_date[:10] <= date_from:
                            line_amount += partial_line.amount
                    for partial_line in line.matched_credit_ids:
                        if partial_line.create_date[:10] <= date_from:
                            line_amount -= partial_line.amount
                    if not self.env.user.company_id.currency_id.is_zero(line_amount):
                        partners_amount[partner_id] += line_amount
                        lines[partner_id].append({
                            'line': line,
                            'amount': line_amount,
                            'period': i + 1,
                        })
            history.append(partners_amount)
        for partner in partners:
            if partner['partner_id'] is None:
                partner['partner_id'] = False
            at_least_one_amount = False
            values = {}
            undue_amt = 0.0
            if partner['partner_id'] in undue_amounts:  # Making sure this partner actually was found by the query
                undue_amt = undue_amounts[partner['partner_id']]

            total[6] = total[6] + undue_amt
            values['direction'] = undue_amt
            if not float_is_zero(values['direction'], precision_rounding=self.env.user.company_id.currency_id.rounding):
                at_least_one_amount = True

            for i in range(5):
                during = False
                if partner['partner_id'] in history[i]:
                    during = [history[i][partner['partner_id']]]
                # Adding counter
                total[(i)] = total[(i)] + (during and during[0] or 0)
                values[str(i)] = during and during[0] or 0.0
                if not float_is_zero(values[str(i)], precision_rounding=self.env.user.company_id.currency_id.rounding):
                    at_least_one_amount = True
            values['total'] = sum([values['direction']] + [values[str(i)] for i in range(5)])
            ## Add for total
            total[(i + 1)] += values['total']
            values['partner_id'] = partner['partner_id']
            if partner['partner_id']:
                browsed_partner = self.env['res.partner'].browse(partner['partner_id'])
                values['name'] = browsed_partner.name_get()[0][1] and len(browsed_partner.name_get()[0][1]) >= 45 and browsed_partner.name_get()[0][1][0:40] + '...' or browsed_partner.name_get()[0][1]
                values['trust'] = browsed_partner.trust
            else:
                values['name'] = _('Unknown Partner')
                values['trust'] = False

            if at_least_one_amount:
                res.append(values)

        return res, total, lines
    
    def _get_partner_move_lines_other_currency(self, account_type, date_from, target_move, period_length, partner_bro_ids):
        periods = {}
        start = datetime.strptime(date_from, "%Y-%m-%d")
        for i in range(5)[::-1]:
            stop = start - relativedelta(days=period_length)
            periods[str(i)] = {
                'name': (i!=0 and (str((5-(i+1)) * period_length) + '-' + str((5-i) * period_length)) or ('+'+str(4 * period_length))),
                'stop': start.strftime('%Y-%m-%d'),
                'start': (i!=0 and stop.strftime('%Y-%m-%d') or False),
            }
            start = stop - relativedelta(days=1)

        res = []
        total = []
        cr = self.env.cr
        user_company = self.env.user.company_id.id
        move_state = ['draft', 'posted']
        if target_move == 'posted':
            move_state = ['posted']
        arg_list = (tuple(move_state), tuple(account_type))
        #build the reconciliation clause to see what partner needs to be printed
        reconciliation_clause = '(l.reconciled IS FALSE)'
        cr.execute('SELECT debit_move_id, credit_move_id FROM account_partial_reconcile where create_date > %s', (date_from,))
        reconciled_after_date = []
        for row in cr.fetchall():
            reconciled_after_date += [row[0], row[1]]
        if reconciled_after_date:
            reconciliation_clause = '(l.reconciled IS FALSE OR l.id IN %s)'
            arg_list += (tuple(reconciled_after_date),)
        arg_list += (date_from, user_company)
        partner_clause = ""
        if len(partner_bro_ids) > 1:
            partner_clause = " AND res_partner.id in " + str(tuple(partner_bro_ids))
        else:
            partner_clause = " AND res_partner.id = " + str(partner_bro_ids[0])
        query = '''
            SELECT DISTINCT l.partner_id, UPPER(res_partner.name)
            FROM account_move_line AS l left join res_partner on l.partner_id = res_partner.id, account_account, account_move am
            WHERE (l.account_id = account_account.id)
                AND (l.move_id = am.id)
                AND (am.state IN %s)
                AND (account_account.internal_type IN %s) ''' + partner_clause + '''
                AND ''' + reconciliation_clause + '''
                AND (l.date <= %s)
                AND l.company_id = %s
            ORDER BY UPPER(res_partner.name)'''
        cr.execute(query, arg_list)

        partners = cr.dictfetchall()
        # put a total of 0
        for i in range(7):
            total.append(0)

        # Build a string like (1,2,3) for easy use in SQL query
        partner_ids = [partner['partner_id'] for partner in partners if partner['partner_id']]
        lines = dict((partner['partner_id'] or False, []) for partner in partners)
        if not partner_ids:
            return [], [], []

        # This dictionary will store the not due amount of all partners
        undue_amounts = {}
        if len(partner_ids) > 1:
            query = '''SELECT l.id
                    FROM account_move_line AS l, account_account, account_move am
                    WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                        AND (am.state IN %s)
                        AND (account_account.internal_type IN %s)
                        AND (COALESCE(l.date_maturity,l.date) > %s)\
                        AND ((l.partner_id IN %s) OR (l.partner_id IS NULL))
                    AND (l.date <= %s)
                    AND l.company_id = %s'''
            cr.execute(query, (tuple(move_state), tuple(account_type), date_from, tuple(partner_ids), date_from, user_company))
        else:
            query = '''SELECT l.id
                    FROM account_move_line AS l, account_account, account_move am
                    WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                        AND (am.state IN %s)
                        AND (account_account.internal_type IN %s)
                        AND (COALESCE(l.date_maturity,l.date) > %s)\
                        AND ((l.partner_id = %s) OR (l.partner_id IS NULL))
                    AND (l.date <= %s)
                    AND l.company_id = %s'''
            cr.execute(query, (tuple(move_state), tuple(account_type), date_from, partner_ids[0], date_from, user_company))
        aml_ids = cr.fetchall()
        aml_ids = aml_ids and [x[0] for x in aml_ids] or []
        for line in self.env['account.move.line'].browse(aml_ids):
            partner_id = line.partner_id.id or False
            currency_id = line.partner_id.transaction_currency_id and line.partner_id.transaction_currency_id or self.env.user.company_id.currency_id
            if partner_id not in undue_amounts:
                undue_amounts[partner_id] = 0.0
            line_amount = line.amount_currency
            if line.amount_currency == 0:
                continue
            for partial_line in line.matched_debit_ids:
                if partial_line.create_date[:10] <= date_from:
                    line_amount += partial_line.amount_currency
            for partial_line in line.matched_credit_ids:
                if partial_line.create_date[:10] <= date_from:
                    line_amount -= partial_line.amount_currency
            if not currency_id.is_zero(line_amount):
                undue_amounts[partner_id] += line_amount
                lines[partner_id].append({
                    'line': line,
                    'amount': line_amount,
                    'period': 6,
                })

        # Use one query per period and store results in history (a list variable)
        # Each history will contain: history[1] = {'<partner_id>': <partner_debit-credit>}
        history = []
        for i in range(5):
            if len(partner_ids) > 1:
                args_list = (tuple(move_state), tuple(account_type), tuple(partner_ids),)
            else:
                args_list = (tuple(move_state), tuple(account_type), partner_ids[0],)
            #args_list = (tuple(move_state), tuple(account_type), tuple(partner_ids),)
            dates_query = '(COALESCE(l.date_maturity,l.date)'

            if periods[str(i)]['start'] and periods[str(i)]['stop']:
                dates_query += ' BETWEEN %s AND %s)'
                args_list += (periods[str(i)]['start'], periods[str(i)]['stop'])
            elif periods[str(i)]['start']:
                dates_query += ' >= %s)'
                args_list += (periods[str(i)]['start'],)
            else:
                dates_query += ' <= %s)'
                args_list += (periods[str(i)]['stop'],)
            args_list += (date_from, user_company)
            if len(partner_ids) > 1:
                query = '''SELECT l.id
                        FROM account_move_line AS l, account_account, account_move am
                        WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                            AND (am.state IN %s)
                            AND (account_account.internal_type IN %s)
                            AND ((l.partner_id IN %s) OR (l.partner_id IS NULL))
                            AND ''' + dates_query + '''
                        AND (l.date <= %s)
                        AND l.company_id = %s'''
            else:
                query = '''SELECT l.id
                        FROM account_move_line AS l, account_account, account_move am
                        WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                            AND (am.state IN %s)
                            AND (account_account.internal_type IN %s)
                            AND ((l.partner_id = %s) OR (l.partner_id IS NULL))
                            AND ''' + dates_query + '''
                        AND (l.date <= %s)
                        AND l.company_id = %s'''
            cr.execute(query, args_list)
            partners_amount = {}
            aml_ids = cr.fetchall()
            aml_ids = aml_ids and [x[0] for x in aml_ids] or []
            for line in self.env['account.move.line'].browse(aml_ids):
                partner_id = line.partner_id.id or False
                currency_id = line.partner_id.transaction_currency_id and line.partner_id.transaction_currency_id or self.env.user.company_id.currency_id
                if partner_id not in partners_amount:
                    partners_amount[partner_id] = 0.0
                line_amount = line.amount_currency
                if line.amount_currency == 0:
                    continue
                for partial_line in line.matched_debit_ids:
                    if partial_line.create_date[:10] <= date_from:
                        line_amount += partial_line.amount_currency
                for partial_line in line.matched_credit_ids:
                    if partial_line.create_date[:10] <= date_from:
                        line_amount -= partial_line.amount_currency

                if not currency_id.is_zero(line_amount):
                    partners_amount[partner_id] += line_amount
                    lines[partner_id].append({
                        'line': line,
                        'amount': line_amount,
                        'period': i + 1,
                        })
            history.append(partners_amount)

        for partner in partners:
            if partner['partner_id'] is None:
                partner['partner_id'] = False
            at_least_one_amount = False
            values = {}
            undue_amt = 0.0
            if partner['partner_id'] in undue_amounts:  # Making sure this partner actually was found by the query
                undue_amt = undue_amounts[partner['partner_id']]

            total[6] = total[6] + undue_amt
            values['direction'] = undue_amt
            if partner['partner_id']:
                partner_bro = self.env['res.partner'].browse(partner['partner_id'])
                currency_id = partner_bro.transaction_currency_id
            else:
                currency_id = self.env.user.company_id.currency_id
            if not float_is_zero(values['direction'], precision_rounding=currency_id.rounding):
                at_least_one_amount = True

            for i in range(5):
                during = False
                if partner['partner_id'] in history[i]:
                    during = [history[i][partner['partner_id']]]
                # Adding counter
                total[(i)] = total[(i)] + (during and during[0] or 0)
                values[str(i)] = during and during[0] or 0.0
                if not float_is_zero(values[str(i)], precision_rounding=currency_id.rounding):
                    at_least_one_amount = True
            values['total'] = sum([values['direction']] + [values[str(i)] for i in range(5)])
            ## Add for total
            total[(i + 1)] += values['total']
            values['partner_id'] = partner['partner_id']
            if partner['partner_id']:
                browsed_partner = self.env['res.partner'].browse(partner['partner_id'])
                values['name'] = browsed_partner.name_get()[0][1] and len(browsed_partner.name_get()[0][1]) >= 45 and browsed_partner.name_get()[0][1][0:40] + '...' or browsed_partner.name_get()[0][1]
                values['trust'] = browsed_partner.trust
                values['currency_id'] = line.partner_id.transaction_currency_id
            else:
                values['name'] = _('Unknown Partner')
                values['trust'] = False
                values['currency_id'] = self.env.user.company_id.currency_id

            if at_least_one_amount:
                res.append(values)
        return res, total, lines


    @api.model
    def render_html(self, docids, data=None):
        total = []
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_id'))

        target_move = data['form'].get('target_move', 'all')
        date_from_f = False
        if data['form']['date_from']:
            date_from_f = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")
            date_from_f = datetime.strftime(date_from_f, "%d-%m-%Y")
        data['form']['date_from_f'] = date_from_f
        
        date_from = data['form'].get('date_from', time.strftime('%Y-%m-%d'))

        if data['form']['result_selection'] == 'customer':
            account_type = ['receivable']
        elif data['form']['result_selection'] == 'supplier':
            account_type = ['payable']
        else:
            account_type = ['payable', 'receivable']
        partner_ids = []
        for each in data['form']['partner_ids']:
            partner_ids.append(each)
        #partner_bro = self.env['res.partner'].sudo().browse(data['form']['partner_id'][0])
        #currency_id = partner_bro.transaction_currency_id and partner_bro.transaction_currency_id or self.user.company_id.currency_id
        movelines, total, dummy = self._get_partner_move_lines_other_currency(account_type, date_from, target_move, data['form']['period_length'], partner_ids)
        movelines_company, total_company, dummy_company = self._get_partner_move_lines_company_currency(account_type, date_from, target_move, data['form']['period_length'], partner_ids)
#        movelines, total, dummy = self._get_partner_move_lines_company_currency(account_type, date_from, target_move, data['form']['period_length'])
        docargs = {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'time': time,
            'get_partner_lines': movelines,
            'get_direction': total,
            'get_partner_lines_company': movelines_company,
            'get_direction_company': total_company,
            'company_currency_id': self.env.user.company_id.currency_id
        }
        return self.env['report'].render('ebits_custom_account.report_agedpartnerbalance_currency', docargs)
