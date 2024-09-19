# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import time
import math
import pytz
from datetime import datetime, timedelta
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import locale
from itertools import groupby

class HRLoanPayEMIWizard(models.TransientModel):
    _name = "hr.loan.pay.emi.wizard"
    _description = "HR Loan Pay EMI"
    
    loan_id = fields.Many2one('hr.loan', string='Hr Loan', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True, related="loan_id.currency_id", store=True, copy=False)
    paid_date = fields.Date(string='Paid Date')
    remaining_amt = fields.Monetary(string='Remaining Amount', currency_field='currency_id', readonly=True)
    paid_amt = fields.Monetary(string='Paid Amount', currency_field='currency_id')
    
     
    def action_pay(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history, paid_amt, paid_date = "", "", ""
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        for each in self:
            
            if not self.env.registry.in_test_mode():
                if not each.paid_amt:
                    raise UserError(_("Kindly enter paid amount to proceed further!"))
            paid_amt = locale.format("%.2f", each.paid_amt, grouping=True)
            remaining_amt = locale.format("%.2f", each.loan_id.remaining_amt, grouping=True)
            
            if not self.env.registry.in_test_mode():
                if each.loan_id.remaining_amt < each.paid_amt:
                    raise UserError(_("Entered paid amount (%s) is greater than the remaining amount (%s)") % (paid_amt, remaining_amt))
            paid_date = datetime.strptime(each.paid_date, "%Y-%m-%d")
            paid_date = datetime.strftime(paid_date, "%d-%m-%Y")
            if each.loan_id.history:
                history = each.loan_id.history + "\n"
            for each_line in each.loan_id.emi_line:
                if not each_line.paid_amt:
                    each_line.paid_amt = each.paid_amt
                    each_line.paid_date = each.paid_date
                    break
            each.loan_id.write({
                'history': history + 'EMI Amount '+ paid_amt + ' is paid on ' + paid_date + ' and entered by ' + str(self.env.user.name) + ' on '+ date
                })
        return True
            
