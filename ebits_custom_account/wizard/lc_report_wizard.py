# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
import xlwt
import cStringIO
import base64
import xlrd
import parser
from lxml import etree

class LcReportWizard(models.TransientModel):
    _name = 'lc.report.wizard'
    _description = 'LC Report Wizard'
    
    lc_no_id = fields.Many2one('purchase.order.lc.master', string='LC No')
    account_id = fields.Many2one('account.account', string='Account')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    
    @api.multi
    def action_print_report_rml(self):
        lc_no_sql = """ """
        account_sql = """ """
        if self.lc_no_id:
            lc_no_sql += " and aml.lc_no_id = " + str(self.lc_no_id.id)
        if self.account_id:
            account_sql += " and aml.account_id  = " + str(self.account_id.id)
        lc_sql = """select 
	                    to_char(aml.date, 'dd-mm-yyyy') as date,
	                    aj.name as journal,
	                    aml.ref as reference,
	                    aa.name as account,
	                    rp.name as partner,
	                    aml.name as label,
	                    aml.debit as debit,
	                    aml.credit as credit
                    from account_move_line aml
	                    left join account_journal aj on (aj.id = aml.journal_id)
	                    left join account_account aa on (aa.id = aml.account_id)
	                    left join res_partner rp on (rp.id = aml.partner_id)
	                    left join account_move am on (am.id = aml.move_id)
                    where am.state = 'posted'"""+ lc_no_sql + account_sql + """ order by aml.date"""
        
        self.env.cr.execute(lc_sql)
        lc_data = self.env.cr.dictfetchall()
        return lc_data
        
    @api.multi
    def get_total(self):
        credit = debit = 0.00
        total = self.action_print_report_rml()
        for each in total:
            credit += each['credit']
            debit += each['debit']
        return {
            'credit': credit, 
            'debit': debit
            }
    
    
    @api.multi
    def action_print_report_pdf(self):
        self.ensure_one()
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['lc_no_id', 'account_id'])[0]
        return self.env['report'].get_action(self, 'lc.rml.report', data=data)                
                
