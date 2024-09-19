# -*- coding: utf-8 -*-

import time
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, AccessError, ValidationError

class AccountAnalyticAccountCOA(models.TransientModel):
    _name = "account.analytic.account.coa.view"
    _description = "Chart of Analytic Account View Wizard"
    
    company_id = fields.Many2one('res.company', string='Company', readonly=True, default=lambda self: self.env.user.company_id)
    date_from = fields.Date(string='Start Date')
    to_date = fields.Date(string='End Date')

    def _build_contexts(self, data):
        result = {}
        result['date_from'] = data['form']['date_from'] or False
        result['to_date'] = data['form']['to_date'] or False
        return result
        
    @api.multi
    def account_chart_open_window(self):
        self.ensure_one()
        ctx = dict(self.env.context or {})
        result = {}
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['date_from', 'to_date', 'company_id'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        if not data['form'].get('date_from'):
            raise UserError(_("You must define a Start Date"))
        ctx.update(data['form']['used_context'])
        action = self.env.ref('ebits_custom_account.action_account_analytic_account_drill')
        result = action.read()[0]
        result['context'] = ctx
        accounts = self.env['account.analytic.account'].sudo().search([])
        accounts.with_context(data['form'].get('used_context',{}))._compute_debit_credit_balance()
        return result
        
        
