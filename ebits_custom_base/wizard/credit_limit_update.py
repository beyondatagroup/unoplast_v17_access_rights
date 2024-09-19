# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import pytz
import datetime
import time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import odoo.addons.decimal_precision as dp

class PartnerCreditLimitUpdate(models.TransientModel):
    _name = 'partner.credit.limit.update'
    _description = 'Partner Credit Limit Update'


    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    # old_credit_limit = fields.Float(readonly=True, string="Old Credit Limit", digits=dp.get_precision('Product Price'))
    old_credit_limit = fields.Float(readonly=True, string="Old Credit Limit", digits='Product Price')
    credit_limit = fields.Float(required=True, string="Credit Limit", digits='Product Price')
    # credit_limit = fields.Float(required=True, string="Credit Limit", digits=dp.get_precision('Product Price'))
    

    #@api.multi
    def update(self):
        #partner = self.env['res.partner'].browse(self.env.context.get('active_id', False))
        old_history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = ''
        for each in self:
            if each.partner_id.changes_history:
                old_history = "\n" + each.partner_id.changes_history
            date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
            history = "Credit Limit has been updated from "+ str(each.old_credit_limit) + " to "+ str(each.credit_limit) + " By " + self.env.user.name + " on " + date
            each.partner_id.write({'credit_limit': each.credit_limit, 'changes_history': history + old_history})        
        return {'type': 'ir.actions.act_window_close'}
