# -*- coding: utf-8 -*-
# Part of EBITS TechCon

import time
import pytz
from datetime import datetime, timedelta
from odoo import api, fields, models, _

class HRPayrollCancelWizard(models.TransientModel):
    _name = "hr.payroll.custom.cancel"
    _description = "HR Payroll Custom Cancel"
    
    name = fields.Text(string='Cancel Reason', required=True)
    payroll_id = fields.Many2one('hr.payroll.custom', string="Payroll", required=True)
    
     
    def action_cancel_reason(self):
        moves = self.env['account.move']
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            if each.payroll_id.move_id:
                moves += each.payroll_id.move_id
            if each.payroll_id.history:
                history = each.payroll_id.history + "\n"
            each.payroll_id.write({
                'state': 'cancel',
                'history': history + "This document is cancelled by " + str(self.env.user.name) + " on " + date + " for " + each.name
                })
        if moves:
            moves.button_cancel()
            moves.unlink()
        return True
            

class HRPayrollReeditWizard(models.TransientModel):
    _name = "hr.payroll.custom.reedit"
    _description = "HR Payroll Custom Reedit"
    
    name = fields.Text(string='Reason', required=True)
    payroll_id = fields.Many2one('hr.payroll.custom', string="Payroll", required=True)
    
     
    def action_reedit_reason(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            if each.payroll_id.history:
                history = each.payroll_id.history + "\n"
            each.payroll_id.write({
                'state': 'draft',
                'history': history + "This document is Reedit by " + str(self.env.user.name) + " on " + date + " for " + each.name 
                })
        return True
