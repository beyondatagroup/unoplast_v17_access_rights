# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright (C) 2004-2008 PC Solutions (<http://pcsol.be>). All Rights Reserved
from odoo import fields, models

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    # def _prepare_reconciliation_move(self, move_ref):
    #     data = super(AccountBankStatementLine, self)._prepare_reconciliation_move(move_ref)
    #     if self.sudo().pos_statement_id:
    #         if self.sudo().pos_statement_id.user_id:
    #             data.update(user_id=self.sudo().pos_statement_id.user_id.id)
    #     return data
