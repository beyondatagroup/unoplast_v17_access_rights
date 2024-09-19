# -*- coding: utf-8 -*-
# Part of EBITS TechCon

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    lc_account_ids = fields.Many2many('account.account', string="LC Account(s)",
                                      help="This is the default account which will be used in the LC form journal entries filter.")


class AccountConfigSettings(models.TransientModel):
    # _inherit = 'account.config.settings'
    _inherit = 'res.config.settings'

    # group_proforma_invoices = fields.Boolean(string='Allow Approval in invoices',
    #                                          implied_group='account.group_proforma_invoices',
    #                                          help="Allows you to put invoices in pending for approval state.")
    # lc_account_ids = fields.Many2many('account.account', related='company_id.lc_account_ids', string="LC Account(s)",
    #                                   help="This is the default account which will be used in the LC form journal entries filter.")

    lc_account_ids = fields.Many2many('account.account', string="LC Account(s)",compute='_compute_lc_account_ids', help="This is the default account which will be used in the LC form journal entries filter.")

    @api.depends('company_id')
    def _compute_lc_account_ids(self):
        for res_config in self:
            if res_config.company_id:
                res_config.lc_account_ids = res_config.company_id.lc_account_ids
                # res_config.pos_fiscal_position_ids = res_config.pos_config_id.fiscal_position_ids
            # else:
            #     res_config.pos_default_fiscal_position_id = False
            #     res_config.pos_fiscal_position_ids = [(5, 0, 0)]