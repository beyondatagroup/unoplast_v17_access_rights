# -*- coding: utf-8 -*-
# Part of EBITS TechCon

import time
from datetime import datetime
from odoo import api, fields, models, _
#from odoo.tools import amount_to_text_in
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import odoo.addons.decimal_precision as dp
import logging
import pytz

_logger = logging.getLogger(__name__)

class account_register_payments(models.TransientModel):
    # _inherit = "account.register.payments"
    _inherit = "account.payment.register"

    cheque_no = fields.Char(string='Cheque No', copy=False)
    cheque_date = fields.Date(string='Cheque Date', copy=False)
    customer_receipt = fields.Char(string='Customer Receipt No', copy=False)
    sales_user_id = fields.Many2one('res.users', string="Received By", copy=False)
    manager_user_id = fields.Many2one('res.users', string="Sales Manager", copy=False)
    lc_no_id = fields.Many2one('purchase.order.lc.master', string='LC No', copy=False)
    
    # @api.model
    def default_get(self, fields):
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        rec = super(account_register_payments, self).default_get(fields)
        invoices = self.env[active_model].browse(active_ids)
        rec.update({
            # 'sales_user_id': invoices[0].commercial_partner_id.user_id
            #                  and invoices[0].commercial_partner_id.user_id.id or False,
            'sales_user_id': invoices[0].move_id.invoice_user_id
                         and invoices[0].move_id.invoice_user_id.id or False,
            # 'manager_user_id': invoices[0].commercial_partner_id.sales_manager_id
            #                    and invoices[0].commercial_partner_id.sales_manager_id.id or False
            'manager_user_id': invoices[0].move_id.sales_manager_id
                               and invoices[0].move_id.sales_manager_id.id or False
            })
        return rec
        
    # def get_payment_vals(self):
    def _create_payment_vals_from_wizard(self,batch_result):
        # result = super(account_register_payments, self).get_payment_vals()
        result = super(account_register_payments, self)._create_payment_vals_from_wizard(batch_result)
        result.update({
            'cheque_no': self.cheque_no or '',
            'cheque_date': self.cheque_date and self.cheque_date or False,
            'customer_receipt': self.customer_receipt or '',
            'sales_user_id': self.sales_user_id and self.sales_user_id.id or False,
            'manager_user_id': self.manager_user_id and self.manager_user_id.id or False,
            })
        return result

    # def _post_payments(self, to_process, edit_mode=False):
    #     print(">>>>>>>>>>_post_payments>>>>>>>>>>>>>>>")
    #     res = super(account_register_payments, self)._post_payments(to_process)
    #     return res

#     @api.onchange('journal_id')
#     def _onchange_journal(self):
#         if self.journal_id:
#             if not self.partner_id:
#                 warning = {
#                         'title': _("Warning"),
#                         'message': _("Kindly Select the Customer/Vendor!")}
#                 return {'warning': warning}
#             if self.journal_id.currency_id:
#                 if self.partner_id.transaction_currency_id:
#                     if self.partner_id.transaction_currency_id != self.journal_id.currency_id:
#                         self.journal_id = False
#                         warning = {
#                             'title': _("Warning"),
#                             'message': _("You cannot select other currency journal!")}
#                         return {'warning': warning}
#                 else:
#                     if self.env.user.company_id.currency_id != self.journal_id.currency_id:
#                         self.journal_id = False
#                         warning = {
#                             'title': _("Warning"),
#                             'message': _("You cannot select other currency journal!")}
#                         return {'warning': warning}
#             else:
#                 if self.partner_id.transaction_currency_id != self.env.user.company_id.currency_id:
#                     self.journal_id = False
#                     warning = {
#                         'title': _("Warning"),
#                         'message': _("You cannot select other currency journal!")}
#                     return {'warning': warning}
# #            if self.payment_type == 'transfer':
# #                self.currency_id = self.journal_id.currency_id or self.company_id.currency_id
#             # Set default payment method (we consider the first to be the default one)
#             # payment_methods = (self.payment_type == 'inbound' and
#             #                    self.journal_id.inbound_payment_method_ids or
#             #                    self.journal_id.outbound_payment_method_ids)
#
#             payment_methods = (self.payment_type == 'inbound' and
#                                self.journal_id.inbound_payment_method_line_ids or
#                                self.journal_id.outbound_payment_method_line_ids)
#
#             # self.payment_method_id = payment_methods and payment_methods[0] or False
#
#             # Set payment method domain (restrict to methods enabled for the journal and to selected payment type)
#             # payment_type = self.payment_type in ('outbound', 'transfer') and 'outbound' or 'inbound'
#             payment_type = self.payment_type in ('outbound') and 'outbound' or 'inbound'
#             return {'domain': {'payment_method_id': [('payment_type', '=', payment_type), ('id', 'in', payment_methods.ids)]}}
#         return {}
#
#     @api.onchange('currency_id')
#     def _onchange_currency_id(self):
#         warning = {}
#         if self.currency_id:
#             # if self.payment_type != 'transfer' and self.partner_id:
#             if self.partner_id:
#                 if self.partner_id.transaction_currency_id != self.currency_id:
#                     self.currency_id = self.partner_id.transaction_currency_id
#                     if self.payment_type == 'inbound':
#                         warning = {
#                             'title': _("Warning"),
#                             'message': _("You cannot change the customer currency configured in customer master")}
#                     else:
#                         warning = {
#                             'title': _("Warning"),
#                             'message': _("You cannot change the Vendor currency configured in Vendor master")}
#         return {'warning': warning}
        
class account_payment(models.Model):
    _inherit = "account.payment"
    
    # @api.one
    # @api.depends('amount', 'currency_id', 'company_id', 'payment_date')
    # def _get_amount_words(self):
    #     amount_in_words = ""
    #     amount_in_words_local = ""
    #     if self.amount and self.currency_id:
    #         amount_in_words = amount_to_text_in.amount_to_text(self.amount, 'en', self.currency_id.name, self.currency_id.subcurrency)
    #     self.amount_to_text_pay_currency = amount_in_words
    #     amount_company_signed = self.amount
    #     currency_id_rate = self.currency_id.rate
    #     currency_id_value = self.currency_id.rate and (1 / self.currency_id.rate) or 0.00
    #     if self.company_id.currency_id != self.currency_id:
    #         currency_id = self.currency_id.with_context(date=self.payment_date)
    #         amount_company_signed = currency_id.compute(self.amount, self.company_id.currency_id)
    #         amount_in_words_local = amount_to_text_in.amount_to_text(amount_company_signed, 'en', self.company_id.currency_id.name, self.company_id.currency_id.subcurrency)
    #         currency_id_rate = currency_id.rate
    #         currency_id_value = currency_id.rate and (1 / currency_id.rate) or 0.00
    #     self.amount_local_currency = amount_company_signed
    #     self.amount_to_text_local_currency = amount_in_words_local
    #     self.currency_id_rate = currency_id_rate
    #     self.currency_id_value = round(currency_id_value, 3)

    # state = fields.Selection([('draft', 'Draft'),
    #     ('waiting', 'Pending For Approval'),
    #     ('posted', 'Posted'),
    #     ('sent', 'Sent'),
    #     ('reconciled', 'Reconciled')], readonly=True, default='draft', copy=False, string="Status")
    user_id = fields.Many2one('res.users', string='Created By', readonly=True, default=lambda self: self.env.user, copy=False)
    approved_id = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False)
    approved_date = fields.Date(string='Approved Date', readonly=True, copy=False)
    cancel_requested = fields.Boolean(string='Cancellation Requested', readonly=False, copy=False)
    cancel_reason = fields.Text(string="History", readonly=True, copy=False)
    cancel_user_id = fields.Many2one('res.users', string="Cancelled By", readonly=True, copy=False)
    #edit_reason = fields.Text(string="Re-Edit Reason", readonly=True, copy=False)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency", readonly=True)
    # amount_to_text_pay_currency = fields.Char(compute='_get_amount_words', string="Amount In Words")
    amount_to_text_pay_currency = fields.Char(string="Amount In Words",compute='_get_amount_words',)
    # amount_to_text_local_currency = fields.Char(compute='_get_amount_words', string='Amount In Words(Local)')
    amount_to_text_local_currency = fields.Char(string='Amount In Words(Local)',compute='_get_amount_words')
    # amount_local_currency = fields.Monetary(compute='_get_amount_words', string='Amount In Company Currency',
    #     currency_field='company_currency_id', store=True, copy=False)

    amount_local_currency = fields.Monetary(string='Amount In Company Currency',compute='_get_amount_words',
                                            currency_field='company_currency_id', store=True, copy=False)

    # currency_id_rate = fields.Float(compute='_get_amount_words', string='Currency Rate', store=True, copy=False, digits=(12, 9))
    currency_id_rate = fields.Float(string='Currency Rate', store=True, copy=False, digits=(12, 9))
    # currency_id_value = fields.Float(compute='_get_amount_words', string='Currency Conversion Value', store=True, copy=False, digits=(12, 3))
    currency_id_value = fields.Float(string='Currency Conversion Value', store=True, copy=False)
    sales_user_id = fields.Many2one('res.users', string="Received By", copy=False)
    manager_user_id = fields.Many2one('res.users', string="Sales Manager", copy=False)
    cheque_no = fields.Char(string='Cheque No', copy=False)
    cheque_date = fields.Date(string='Cheque Date', copy=False)
    customer_receipt = fields.Char(string='Customer Receipt No', copy=False)
    lc_no_id = fields.Many2one('purchase.order.lc.master', string='LC No', copy=False)
    destination_move_name = fields.Char(string='Destination Journal Entry Name', readonly=True,
        default=False, copy=False,
        help="Technical field holding the number given to the journal entry, automatically set when the statement line is reconciled then stored to set the same number again if the line is cancelled, set to draft and re-processed again.")


    ######################
    @api.depends('amount', 'currency_id', 'company_id')
    def _get_amount_words(self):
        for amt in self:
            amount_in_words = ""
            amount_in_words_local = ""
            print(">>>>>>>>>>>>>>>amt.currency_id>>>>>>>>>>>>>>>>>>>>>", amt.currency_id.name)
            print(">>>>>>>>>>>>>>>amt.self.currency_id>>>>>>>>>>>>>>>>>>>>>", self.currency_id.rate_ids)
            if amt.amount_total and amt.currency_id:
                amount_in_words = str(amt.currency_id.amount_to_text(amt.amount))
            amt.amount_to_text_pay_currency = amount_in_words

            if amt.company_id.currency_id != amt.currency_id:
                if amt.company_id.currency_id:
                    amount_local_currency = amt.currency_id._convert(
                        amt.amount, amt.company_currency_id, amt.company_id,
                        amt.invoice_date or fields.Date.today()
                    )
                    print(">>>>>>>>>>amount_local_currency>>>>>>>>>>>>>>",amount_local_currency)
                    amount_in_words_local = str(amt.currency_id.amount_to_text(amount_local_currency))

                    amt.amount_local_currency = amount_local_currency

                    amt.amount_to_text_local_currency = amount_in_words_local
            else:
                amt.amount_to_text_local_currency = False


            if amt.currency_id.rate_ids:
                currency_id_value = amt.currency_id.rate_ids[0].company_rate
            else:
                currency_id_value = 1

            amt.currency_id_value = currency_id_value


    # def _post_payments(self, to_process, edit_mode=False):
    #     """ Post the newly created payments.
    #
    #     :param to_process:  A list of python dictionary, one for each payment to create, containing:
    #                         * create_vals:  The values used for the 'create' method.
    #                         * to_reconcile: The journal items to perform the reconciliation.
    #                         * batch:        A python dict containing everything you want about the source journal items
    #                                         to which a payment will be created (see '_get_batches').
    #     :param edit_mode:   Is the wizard in edition mode.
    #     """
    #     payments = self.env['account.payment']
    #     for vals in to_process:
    #         payments |= vals['payment']
    #     payments.action_post()






    # @api.multi
    @api.constrains('partner_id', 'customer_receipt', 'payment_type')
    def _check_customer_receipt(self):
        for payment in self:
            if payment.payment_type == 'inbound':
                domain = [
                    ('customer_receipt', '=', payment.customer_receipt),
                    ('payment_type', '=', payment.payment_type),
                    ('id', '!=', payment.id),
                    ('customer_receipt', '!=', ''),
                    ]
                all_payment = self.search_count(domain)
                if all_payment:
                    raise ValidationError(_("Customer receipt no duplication error!.\nKindly check the previous receipt no(s) for the same customer!"))
            else:
                continue
    
    @api.onchange('journal_id')
    def _onchange_journal(self):
        warning = {}
        if self.journal_id:
            # if self.payment_type == 'transfer':
            #     self.currency_id = self.journal_id.currency_id or self.company_id.currency_id
            # if self.payment_type != 'transfer':
            # if self.payment_type != 'transfer':
            if not self.partner_id:
                warning = {
                    'title': _("Warning"),
                    'message': _("Kindly Select the Customer/Vendor!")}
                return {'warning': warning}
            if self.journal_id.currency_id:
                if self.partner_id.transaction_currency_id:
                    if self.partner_id.transaction_currency_id != self.journal_id.currency_id:
                        self.journal_id = False
                        warning = {
                            'title': _("Warning"),
                            'message': _("You cannot select other currency journal!")}
                        return {'warning': warning}
                else:
                    if self.env.user.company_id.currency_id != self.journal_id.currency_id:
                        self.journal_id = False
                        warning = {
                            'title': _("Warning"),
                            'message': _("You cannot select other currency journal!")}
                        return {'warning': warning}
            else:
                if self.partner_id.transaction_currency_id != self.env.user.company_id.currency_id:
                    self.journal_id = False
                    warning = {
                        'title': _("Warning"),
                        'message': _("You cannot select other currency journal!")}
                    return {'warning': warning}
        # Set default payment method (we consider the first to be the default one)
        payment_methods = self.payment_type == 'inbound' and self.journal_id.inbound_payment_method_ids or self.journal_id.outbound_payment_method_ids
        self.payment_method_id = payment_methods and payment_methods[0] or False
        # Set payment method domain (restrict to methods enabled for the journal and to selected payment type)
        # payment_type = self.payment_type in ('outbound', 'transfer') and 'outbound' or 'inbound'
        payment_type = self.payment_type in ('outbound') and 'outbound' or 'inbound'
        return {'domain': {'payment_method_id': [('payment_type', '=', payment_type), ('id', 'in', payment_methods.ids)]}}
        # return {}
        
    @api.onchange('partner_type')
    def _onchange_partner_type(self):
        warning = {}
        if self.partner_type:
#            if self.payment_type == 'outbound' and self.partner_type == 'customer':
#                warning = {
#                    'title': _("Warning"),
#                    'message': _("You cannot select customer for sending the money")}
#                self.partner_type = 'supplier'
#                return {'warning': warning}
#            if self.payment_type == 'inbound' and self.partner_type == 'supplier':
#                warning = {
#                    'title': _("Warning"),
#                    'message': _("You cannot select supplier for receiving the money")}
#                self.partner_type = 'customer'
#                return {'warning': warning}
            return {'domain': {'partner_id': [(self.partner_type, '=', True), ('parent_id', '=', False)]}}
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        warning = {}
        if self.partner_id:
            if self.partner_id.transaction_currency_id:
                self.currency_id = self.partner_id.transaction_currency_id
            else:
                if self.payment_type == 'inbound':  
                    warning = {
                        'title': _("Warning"),
                        'message': _("You cannot change the customer currency configured in customer master.")} 
                else:
                    warning = {
                        'title': _("Warning"),
                        'message': _("You cannot change the Vendor currency configured in Vendor master.")} 
                self.currency_id = False
            if self.payment_type == 'inbound':
                self.sales_user_id = self.partner_id.user_id and self.partner_id.user_id.id or False
                self.manager_user_id = self.partner_id.sales_manager_id and self.partner_id.sales_manager_id.id or False
            else:
                self.sales_user_id = False
                self.manager_user_id = False
        else:
            self.sales_user_id = False
            self.manager_user_id = False
        return {'warning': warning} 
        
    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        warning = {}
        if self.currency_id:
            # if self.payment_type != 'transfer' and self.partner_id:
            if self.partner_id:
                if self.partner_id.transaction_currency_id != self.currency_id:
                    self.currency_id = self.partner_id.transaction_currency_id
                    if self.payment_type == 'inbound':
                        warning = {
                            'title': _("Warning"),
                            'message': _("You cannot change the customer currency configured in customer master.")}
                    else:
                        warning = {
                            'title': _("Warning"),
                            'message': _("You cannot change the Vendor currency configured in Vendor master.")}
        return {'warning': warning} 
                
    # @api.multi

    def send_for_approval(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        cancel_reason = ""
        for rec in self:
            if rec.state == 'draft':
                if rec.cancel_reason:
                    cancel_reason = '\n' + rec.cancel_reason
                rec.write({
                    'state': 'waiting',
                    'cancel_reason': "Payment entry has been sent for approval " + " by " + self.env.user.name +  " on " + date + cancel_reason})
            else:
                print(">>>>>>>>>>>>send_for_approval>>>>>>>>>>>>")
                rec.action_post()
                # pass
        return True
                
    # @api.multi
#     def post(self):
#         """ Create the journal items for the payment and update the payment's state to 'posted'.
#             A journal entry is created containing an item in the source liquidity account (selected journal's default_debit or default_credit)
#             and another in the destination reconciliable account (see _compute_destination_account_id).
#             If invoice_ids is not empty, there will be one reconciliable move line per invoice to reconcile with.
#             If the payment is a transfer, a second journal entry is created in the destination journal to receive money from the transfer account.
#         """
#         fmt = "%d-%m-%Y %H:%M:%S"
#         date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
#         cancel_reason = ""
#         for rec in self:
#
#             if rec.state not in ('draft', 'waiting'):
#                 raise UserError(_("Only a draft payment can be posted. Trying to post a payment in state %s.") % rec.state)
#
#             if any(inv.state != 'open' for inv in rec.invoice_ids):
#                 raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))
#
#             # Use the right sequence to set the name
#             if rec.payment_type in ('inbound', 'outbound'):
#                 journal = rec.journal_id
#                 if not journal.sequence_id:
#                     raise UserError(_('Configuration Error !'), _('The journal %s does not have a sequence, please specify one.') % journal.name)
#                 if not journal.sequence_id.active:
#                     raise UserError(_('Configuration Error !'), _('The sequence of journal %s is deactivated.') % journal.name)
#                 if not rec.move_name:
#                     name = journal.with_context(ir_sequence_date=rec.payment_date).sequence_id.next_by_id()
#                     rec.name = name
#                     rec.move_name = name
#             else:
#                 # if rec.payment_type == 'transfer':
#                 if rec.is_internal_transfer:
#                     sequence_code = 'account.payment.transfer'
# #                else:
# #                    if rec.partner_type == 'customer':
# #                        if rec.payment_type == 'inbound':
# #                            sequence_code = 'account.payment.customer.invoice'
# #                        if rec.payment_type == 'outbound':
# #                            sequence_code = 'account.payment.customer.refund'
# #                    if rec.partner_type == 'supplier':
# #                        if rec.payment_type == 'inbound':
# #                            sequence_code = 'account.payment.supplier.refund'
# #                        if rec.payment_type == 'outbound':
# #                            sequence_code = 'account.payment.supplier.invoice'
#                 if not rec.move_name:
#                     rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(sequence_code)
#
#             # Create the journal entry
#             # amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
#             amount = rec.amount * (rec.payment_type in ('outbound') and 1 or -1)
#             move = rec._create_payment_entry(amount)
#
#             # In case of a transfer, the first journal entry created debited the source liquidity account and credited
#             # the transfer account. Now we debit the transfer account and credit the destination liquidity account.
#             # if rec.payment_type == 'transfer':
#             if rec.is_internal_transfer:
#                 transfer_credit_aml = move.line_ids.filtered(lambda r: r.account_id == rec.company_id.transfer_account_id)
#                 transfer_debit_aml = rec._create_transfer_entry(amount)
#                 (transfer_credit_aml + transfer_debit_aml).reconcile()
#             if rec.cancel_reason:
#                 cancel_reason = '\n' + rec.cancel_reason
#             rec.write({'state': 'posted',
#                 'move_name': move.name,
#                 'approved_id': self.env.user.id,
#                 'approved_date': fields.Date.context_today(self),
#                 'cancel_reason': "Payment entry has been confirmed " + " by " + self.env.user.name +  " on " + date + cancel_reason})
#         # return True
        
    def _create_transfer_entry(self, amount):
        """ Create the journal entry corresponding to the 'incoming money' part of an internal transfer, return the reconciliable move line
        """
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        debit, credit, amount_currency, dummy = aml_obj.with_context(date=self.payment_date).compute_amount_fields(amount, self.currency_id, self.company_id.currency_id)
        amount_currency = self.destination_journal_id.currency_id and self.currency_id.with_context(date=self.payment_date).compute(amount, self.destination_journal_id.currency_id) or 0

        dst_move = self.env['account.move'].create(self._get_move_vals(self.destination_journal_id))

        dst_liquidity_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, dst_move.id)
        dst_liquidity_aml_dict.update({
            'name': _('%s Transfer from %s') % (self.name, self.journal_id.name),
            #'ref': self.name,
            'account_id': self.destination_journal_id.default_credit_account_id.id,
            'currency_id': self.destination_journal_id.currency_id.id,
            'payment_id': self.id,
            'journal_id': self.destination_journal_id.id})
        aml_obj.create(dst_liquidity_aml_dict)

        transfer_debit_aml_dict = self._get_shared_move_line_vals(credit, debit, 0, dst_move.id)
        transfer_debit_aml_dict.update({
            'name': self.name,
            'payment_id': self.id,
            'account_id': self.company_id.transfer_account_id.id,
            'journal_id': self.destination_journal_id.id})
        if self.currency_id != self.company_id.currency_id:
            transfer_debit_aml_dict.update({
                'currency_id': self.currency_id.id,
                'amount_currency': -self.amount,
            })
        transfer_debit_aml = aml_obj.create(transfer_debit_aml_dict)
        dst_move.post()
        self.write({'destination_move_name': dst_move.name})
        return transfer_debit_aml
        
    def _get_move_vals(self, journal=None):
        """ Return dict to create the payment move
        """
        print(">>>>>>>>>>>>>_get_move_vals>>>>>>>>>")
        #journal = journal or self.journal_id
        ref = ""
        name = ""
        if self.customer_receipt:
            ref = (self.communication or '') + "- CR No: " + self.customer_receipt

        if journal:
            if not journal.sequence_id:
                raise UserError(_('Configuration Error !'), _('The journal %s does not have a sequence, please specify one.') % journal.name)
            if not journal.sequence_id.active:
                raise UserError(_('Configuration Error !'), _('The sequence of journal %s is deactivated.') % journal.name)
            name = self.destination_move_name or journal.with_context(ir_sequence_date=self.payment_date).sequence_id.next_by_id()
            return {
                'name': name,
                'date': self.payment_date,
                'ref': ref,
                'company_id': self.company_id.id,
                'journal_id': journal.id,
                'cheque_no': self.cheque_no or '',
                'cheque_date': self.cheque_date or False,
                'lc_no_id': self.lc_no_id and self.lc_no_id.id or False,
                }
        else:
            if not self.journal_id.sequence_id:
                raise UserError(_('Configuration Error !'), _('The journal %s does not have a sequence, please specify one.') % self.journal_id.name)
            if not self.journal_id.sequence_id.active:
                raise UserError(_('Configuration Error !'), _('The sequence of journal %s is deactivated.') % self.journal_id.name)
            name = self.move_name or self.journal_id.with_context(ir_sequence_date=self.payment_date).sequence_id.next_by_id()
            return {
                'name': name,
                'date': self.payment_date,
                'ref': ref,
                'company_id': self.company_id.id,
                'journal_id': self.journal_id.id,
                'cheque_no': self.cheque_no or '',
                'cheque_date': self.cheque_date or False,
                'lc_no_id': self.lc_no_id and self.lc_no_id.id or False,
                }
        
    def _get_liquidity_move_line_vals(self, amount):
        print(">>>>>>>>_get_liquidity_move_line_vals>>>>>>")
        name = self.name
        # if self.payment_type == 'transfer':
        #     name = _('%s Transfer to %s') % (self.name, self.destination_journal_id.name)
        vals = {
            'name': name,
            # 'account_id': self.payment_type in ('outbound', 'transfer') and self.journal_id.default_debit_account_id.id or self.journal_id.default_credit_account_id.id,
            'account_id': self.payment_type in ('outbound') and self.journal_id.default_debit_account_id.id or self.journal_id.default_credit_account_id.id,
            'payment_id': self.id,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
            }

        # If the journal has a currency specified, the journal item need to be expressed in this currency
        if self.journal_id.currency_id and self.currency_id != self.journal_id.currency_id:
            amount = self.currency_id.with_context(date=self.payment_date).compute(amount, self.journal_id.currency_id)
            debit, credit, amount_currency, dummy = self.env['account.move.line'].with_context(date=self.payment_date).compute_amount_fields(amount, self.journal_id.currency_id, self.company_id.currency_id)
            vals.update({
                'amount_currency': amount_currency,
                'currency_id': self.journal_id.currency_id.id,
                })
        return vals
    
        
    # @api.multi
    def cancel(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        cancel_reason = ""
        res = super(account_payment, self).cancel()
        for rec in self:
            if rec.cancel_reason:
                cancel_reason = '\n' + rec.cancel_reason
            rec.write({
                'cancel_requested': False,
                'cancel_reason': "Payment entry has been cancelled " + " by " + self.env.user.name +  " on " + date + cancel_reason,})
        return True
        
    # @api.multi
    def payment_print(self):
        self.ensure_one()
        if self.payment_type == 'outbound':
            return self.env['report'].get_action(self, 'supplier.payment.voucher.rml.report')
        elif self.payment_type == 'inbound':
            return self.env['report'].get_action(self, 'payment.voucher.rml.report')
        # elif self.payment_type == 'transfer':
        #     return self.env['report'].get_action(self, 'internal.transfer.rml.report')

