# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

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
import odoo.addons.decimal_precision as dp

class InvoiceCancelReasonWizard(models.TransientModel):
    _name = "invoice.cancel.reason.wizard"
    _description = "Account Invoice Cancel Reason"
    
    name = fields.Text(string='Cancel Reason', required=True)
    
    # @api.multi
    def action_cancel_reason(self):
        invoice_bro = self.env['account.move'].browse(self.env.context.get('active_id'))
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        cancel_reason = ""
        for each in self:
            if invoice_bro.cancel_reason:
                cancel_reason = invoice_bro.cancel_reason + "\n"  
            invoice_bro.cancel_reason = cancel_reason + 'This document is cancelled by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name 
        # invoice_bro.action_cancel()
        invoice_bro.button_cancel()
        return True
