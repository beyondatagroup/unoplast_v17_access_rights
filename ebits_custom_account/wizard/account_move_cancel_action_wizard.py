# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
import pytz
import datetime
import time

class AccountMoveCancelWizard(models.TransientModel):
    _name = 'account.move.cancel.wizard'
    _description = 'Account Move Cancel Wizard'
    
    move_id = fields.Many2one('account.move', string='Move Reference', required=False, copy=False, readonly=True)
    cancel_reason = fields.Text('Cancel Reason', required=True, copy=False)
    
    @api.model
    def default_get(self, fields):
        res = super(AccountMoveCancelWizard, self).default_get(fields)
        move_obj = self.env['account.move']
        move = move_obj.browse(self.env.context.get('active_id'))
        if move:
            res.update({'move_id': move.id})
            if move.state != 'posted':
                raise UserError("You cannot send cancel request in unposted state!")
        return res
        
    # @api.multi
    def action_cancel(self):
        cancel_reason = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            if each.move_id.cancel_reason:
                cancel_reason = '\n' + each.move_id.cancel_reason
            each.move_id.write({
                'cancel_reason': each.cancel_reason + "\nby " + self.env.user.name + " on " + date + cancel_reason, 
                'cancel_approval': True
                })
        return {'type': 'ir.actions.act_window_close'}   
        
# AccountMoveCancelWizard()

class AccountMoveReversal(models.TransientModel):

    _inherit = "account.move.reversal"
    
    # @api.multi
    def reverse_moves(self):
        res = super(AccountMoveReversal, self).reverse_moves()
        move = self.env['account.move'].browse(self.env.context.get('active_id'))
        history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in move:
            if each.history:
                history = each.history + "\n"
            each.write({
                'history': history + 'Reverse Entry Created by '+ self.env.user.name + ' on this date '+ date
                })
        return res
