# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class AccountInvoiceConfirm(models.TransientModel):
    _inherit = "account.invoice.confirm"

    @api.multi
    def invoice_confirm(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['account.invoice'].browse(active_ids):
            if record.state not in ('draft', 'proforma', 'proforma2'):
                raise UserError(_("Selected invoice(s) cannot be confirmed as they are not in 'Draft' or 'Pending For Approval' state."))
            record.action_invoice_open()
        return {'type': 'ir.actions.act_window_close'}

