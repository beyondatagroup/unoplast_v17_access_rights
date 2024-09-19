# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
import pytz
import datetime
import time

class AccountPaymentCancelWizard(models.TransientModel):
    _name = 'account.payment.cancel.wizard'
    _description = 'Account Payment Cancel Wizard'
    
    payment_id = fields.Many2one('account.payment', string='Payment Reference', required=False, copy=False, readonly=True)
    cancel_reason = fields.Text('Cancel Reason', required=True, copy=False)
    
    @api.model
    def default_get(self, fields):
        res = super(AccountPaymentCancelWizard, self).default_get(fields)
        payment_obj = self.env['account.payment']
        payment = payment_obj.sudo().browse(self.env.context.get('active_id'))
        if payment:
            res.update({'payment_id': payment.id})
            if payment.state in ['draft', 'waiting']:
                raise UserError("You cannot send cancel request in draft state!")
            move_ids = set()
            for line in payment.move_line_ids:
                err_msg = _('Move name (id): %s (%s)') % (line.move_id.name, str(line.move_id.id))
                if line.reconciled and not (line.debit == 0 and line.credit == 0):
                    raise UserError(_('You cannot do this modification on a reconciled entry. You can just change some non legal fields or you must unreconcile first.\n%s.') % err_msg)
                if line.move_id.id not in move_ids:
                    move_ids.add(line.move_id.id)
                self.env['account.move'].browse(list(move_ids))._check_lock_date()
        return res
        
    # @api.multi
    def action_cancel(self):
        cancel_reason = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            if each.payment_id.cancel_reason:
                cancel_reason = '\n' + each.payment_id.cancel_reason
            each.payment_id.write({
                'cancel_reason': "Payment entry cancellation requested" + " by " + self.env.user.name + " on " + date + "\nReason - " + each.cancel_reason + cancel_reason, 
                'cancel_user_id': self.env.user.id,
                'cancel_requested': True
                })
        return {'type': 'ir.actions.act_window_close'}   
        
# AccountPaymentCancelWizard()

class AccountPaymentReeditWizard(models.TransientModel):
    _name = 'account.payment.reedit.wizard'
    _description = 'Account Payment Re-Edit Wizard'
    
    payment_id = fields.Many2one('account.payment', string='Payment Reference', required=False, copy=False, readonly=True)
    edit_reason = fields.Text('Re-Edit Reason', required=True, copy=False)
    
    @api.model
    def default_get(self, fields):
        res = super(AccountPaymentReeditWizard, self).default_get(fields)
        payment_obj = self.env['account.payment']
        payment = payment_obj.sudo().browse(self.env.context.get('active_id'))
        if payment:
            res.update({'payment_id': payment.id})
            if payment.state not in ['draft', 'waiting']:
                raise UserError("You can re-edit the request only in draft/ pending for approval state!")
        return res
        
    # @api.multi
    def action_reedit(self):
        edit_reason = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            if each.payment_id.cancel_reason:
                edit_reason = '\n' + each.payment_id.cancel_reason
            each.payment_id.write({
                'cancel_reason': "Payment entry re-edited"+ " by " + self.env.user.name + " on " + date + "\nReason - " + each.edit_reason + edit_reason,
                })
            each.payment_id.cancel()
        return {'type': 'ir.actions.act_window_close'}   
        
# AccountPaymentReeditWizard()
