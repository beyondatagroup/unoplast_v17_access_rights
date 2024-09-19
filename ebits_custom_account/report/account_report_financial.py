# -*- coding: utf-8 -*-

import time
from odoo import api, models
from datetime import datetime, timedelta

class ReportFinancial(models.AbstractModel):
    _inherit = 'report.account.report_financial'

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
        return self.env['report'].render('account.report_financial', docargs)
