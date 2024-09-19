# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import models, fields, api, _



class ResPartner(models.Model):
    _inherit = 'res.partner'

    def server_act_account_partner_ledger_payable(self):
        active_id = self.env.context.get('active_id')
        print("\n\n ...........server_act_account_partner_ledger_payable",active_id)
        return {
            'name': _('Partner Ledger: Payable'),
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'domain': [('type', '=', self.type)],
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': {'search_default_partner_id':[active_id], 'search_default_unreconciled':1, 'search_default_payable':1}
        }
