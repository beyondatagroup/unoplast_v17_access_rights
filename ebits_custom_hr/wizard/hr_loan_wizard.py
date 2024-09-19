# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import time
import math
import pytz
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

class CancelReasonWizard(models.TransientModel):
    _name = "cancel.reason.hr.loan.wizard"
    _description = "Cancel Reason Wizard"
    
    name = fields.Text(string='Cancel Reason', required=True)
    loan_id = fields.Many2one('hr.loan', string="Loan", required=True)
    
     
    def action_cancel_reason(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            if each.loan_id.history:
                history = each.loan_id.history + "\n"
            each.loan_id.write({
                'state': 'cancel',
                'history': history + 'This document is cancelled by '+ str(self.env.user.name) + ' on '+ date +' for '+ each.name
            })
        return True
            

class ReeditReasonWizard(models.TransientModel):
    _name = "reedit.reason.hr.loan.wizard"
    _description = "Reedit Reason Wizard"
    
    name = fields.Text(string='Reason', required=True)
    loan_id = fields.Many2one('hr.loan', string="Loan", required=True)
    
     
    def action_reedit_reason(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            if each.loan_id.history:
                history = each.loan_id.history + "\n"
            each.loan_id.write({
                'state': 'draft',
                'history': history + 'This document is reedit by '+ str(self.env.user.name) + ' on '+ date +' for '+ each.name
            })
        return True
