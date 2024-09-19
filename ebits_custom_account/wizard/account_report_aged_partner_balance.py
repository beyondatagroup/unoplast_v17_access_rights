# -*- coding: utf-8 -*-

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountAgedTrialBalance(models.TransientModel):

    _inherit = 'account.aged.trial.balance'

    other_currency = fields.Boolean(string='Partner Currency')
    partner_ids = fields.Many2many('res.partner', 'account_aged_balance_res_partner_rele', 'balance_id', 'partner_id', string="Partner(s)")

    def _print_report(self, data):
        res = {}
        data = self.pre_print_report(data)
        data['form'].update(self.read(['period_length', 'other_currency', 'partner_ids'])[0])
        period_length = data['form']['period_length']
        if period_length<=0:
            raise UserError(_('You must set a period length greater than 0.'))
        if not data['form']['date_from']:
            raise UserError(_('You must set a start date.'))

        start = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")

        for i in range(5)[::-1]:
            stop = start - relativedelta(days=period_length - 1)
            res[str(i)] = {
                'name': (i!=0 and (str((5-(i+1)) * period_length) + '-' + str((5-i) * period_length)) or ('+'+str(4 * period_length))),
                'stop': start.strftime('%Y-%m-%d'),
                'start': (i!=0 and stop.strftime('%Y-%m-%d') or False),
            }
            start = stop - relativedelta(days=1)
        data['form'].update(res)
        if data['form']['other_currency']:
            return self.env['report'].with_context(landscape=True).get_action(self, 'ebits_custom_account.report_agedpartnerbalance_currency', data=data)
        else:
            return self.env['report'].with_context(landscape=True).get_action(self, 'account.report_agedpartnerbalance', data=data) 
