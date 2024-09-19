# -*- coding: utf-8 -*-

import time
from odoo import api, models
from datetime import datetime, timedelta


class ReportFinancial(models.AbstractModel):
    _name = 'report.ebits_custom_account.report_financial_custom_hierarchy'
    
    def get_account_lines(self, data):
        account_obj = self.env['account.account']
        currency_obj = self.env['res.currency']
        lines = []
        account_report = self.env['account.financial.report'].search([('id', '=', data['account_report_id'][0])])
        child_reports = account_report.with_context(data.get('used_context'))._get_children_by_order()
        for report in child_reports:
            vals = {
                'name': report.name,
                'balance': report.balance * report.sign or 0.0,
                'type': 'report',
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type =='sum' and 'view' or False,
            }
            if data['other_currency']:
                vals['amount_currency'] = 0.00
                vals['currency_symbol'] = ""
            
            if data['debit_credit']:
                vals['debit'] = report.debit
                vals['credit'] = report.credit
                
            if data['enable_filter']:
                vals['balance_cmp'] = report.with_context(data.get('comparison_context')).balance * report.sign
                if data['other_currency']:
                    vals['balance_cmp_amount_currency'] = 0.00
                    vals['balance_cmp_currency_symbol'] = ""
                
            lines.append(vals)
            
            account_ids = []
            if report.display_detail == 'no_detail':
                continue
                
            if report.type == 'accounts' and report.account_ids:
                account_ids = account_obj.with_context(data.get('used_context'))._get_children_and_consol([x.id for x in report.account_ids])
            elif report.type == 'account_type' and report.account_type_ids:
                account_ids = account_obj.with_context(data.get('used_context')).search([('user_type_id','in', [x.id for x in report.account_type_ids])])
            if account_ids:
                sub_lines = []
                for account in account_ids:
                    if report.display_detail == 'detail_flat' and account.internal_type == 'view':
                        continue
                    flag = False
                    vals = {
                        'name': account.code + ' ' + account.name,
                        'balance':  account.balance != 0 and account.balance * report.sign or account.balance,
                        'type': 'account',
                        'level': report.display_detail == 'detail_with_hierarchy' and min(account.level + 1,6) or 6, #account.level + 1
                        'account_type': account.internal_type,
                    }
                    if data['other_currency']:
                        vals['amount_currency'] = account.balance_amount_currency
                        vals['currency_symbol'] = account.currency_id and account.currency_id.symbol or ""
                    
                    if data['debit_credit']:
                        vals['debit'] = account.debit
                        vals['credit'] = account.credit
                        if not account.company_id.currency_id.is_zero(vals['debit']) or not account.company_id.currency_id.is_zero(vals['credit']):
                            flag = True
                    if not account.company_id.currency_id.is_zero(vals['balance']):
                        flag = True
                    if data['enable_filter']:
                        vals['balance_cmp'] = account.balance * report.sign
                        if data['other_currency']:
                            vals['balance_cmp_amount_currency'] = account.balance_amount_currency
                            vals['balance_cmp_currency_symbol'] = account.currency_id and account.currency_id.symbol or ""
                        if not account.company_id.currency_id.is_zero(vals['balance_cmp']):
                            flag = True
                    if flag:
                        sub_lines.append(vals)
                lines += sorted(sub_lines, key=lambda sub_line: sub_line['name'])
        return lines

    @api.model
    def render_html(self, docids, data=None):
        self.model = self.env.context.get('active_model')
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        date_from = date_to = False
        if data['form']['date_from']:
            date_from = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")
            date_from = datetime.strftime(date_from, "%d-%m-%Y")
        if data['form']['date_to']:
            date_to = datetime.strptime(data['form']['date_to'], "%Y-%m-%d")
            date_to = datetime.strftime(date_to, "%d-%m-%Y")
        data['form']['date_from_f'] = date_from
        data['form']['date_to_f'] = date_to
        report_lines = self.get_account_lines(data.get('form'))
        docargs = {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'data': data['form'],
            'docs': docs,
            'time': time,
            'get_account_lines': report_lines,
        }
        return self.env['report'].render('ebits_custom_account.report_financial_custom_hierarchy', docargs)
