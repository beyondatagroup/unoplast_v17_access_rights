# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw
import time
from odoo import api, fields, models, _

class PaymentDueRmlReport(report_sxw.rml_parse):
    
    def set_context(self, objects, data, ids, report_type = None):
        super(PaymentDueRmlReport,self).set_context(objects, data, ids, report_type)
        self.localcontext.update({
            '_get_account_move_lines': self._get_account_move_lines,
            '_get_line_total': self._get_line_total,
        })
        
    @api.model 
    def _get_account_move_lines(self, partner_ids):
        list_rec = []
        self.cr.execute("""SELECT 
	                            m.name AS move_id, 
	                            to_char(l.date, 'dd-mm-yyyy') as date, 
	                            l.name, 
	                            l.ref, 
	                            to_char(l.date_maturity, 'dd-mm-yyyy') as date_maturity, 
	                            l.partner_id, l.blocked, 
	                            l.amount_currency, 
	                            l.currency_id as currency_id, 
	                            ap.customer_receipt as receipt_no,
	                            (CASE WHEN at.type = 'receivable' THEN SUM(l.debit) ELSE SUM(l.credit * -1) END) AS debit, 
                                    (CASE WHEN at.type = 'receivable' THEN SUM(l.credit) ELSE SUM(l.debit * -1) END) AS credit, 
                                    (CASE WHEN l.date_maturity < %s THEN SUM(l.debit - l.credit) ELSE 0 END) AS mat 
                            FROM account_move_line l 
                                LEFT JOIN account_account_type at ON (l.user_type_id = at.id) 
                                LEFT JOIN account_move m ON (l.move_id = m.id) 
                                LEFT JOIN account_payment ap ON (l.payment_id = ap.id) 
                            WHERE 
	                            l.partner_id = %s AND at.type IN ('receivable', 'payable') 
                            GROUP BY to_char(l.date, 'dd-mm-yyyy'), 
	                            l.name, 
	                            l.ref, 
	                            l.date_maturity, 
	                            to_char(l.date_maturity, 'dd-mm-yyyy'), 
	                            l.partner_id, 
	                            at.type, 
	                            l.blocked, 
	                            l.amount_currency, 
	                            l.currency_id, 
	                            l.move_id, 
	                            m.name, 
	                            ap.customer_receipt""", ((fields.date.today(),) + ((partner_ids.id),)))
        list_rec = self.cr.dictfetchall() 
        return list_rec
        
        
    @api.model
    def _get_line_total(self, partner_ids):
        list_rec = self._get_account_move_lines(partner_ids)
        grant_total = {'credit': 0.00, 'debit': 0.00, 'mat': 0.00, 'total': 0.00, 'balance': 0.00}
        currency = False
        company_currency = partner_ids.company_id.currency_id.id
        for item in list_rec:
            currency = item['currency_id'] and item['currency_id'] or company_currency 
            if not item['blocked']:
                grant_total['credit'] += item['credit'] 
                grant_total['debit'] += item['debit']
                grant_total['mat'] += item['mat']
                if company_currency == currency:
                    grant_total['total'] += item['debit'] - item['credit']
                else:
                    grant_total['total'] += item['debit'] - ( -1 * item['credit']) 
        grant_total['balance'] += (grant_total['debit'] - grant_total['credit'])
        return grant_total

report_sxw.report_sxw('report.payment.due.rml.report', 'res.partner',
      'addons_ebits/ebits_custom_account/report/payment_due_report_rml.rml', parser=PaymentDueRmlReport, header=False)
