# -*- coding: utf-8 -*-
# Part of EBITS TechCon

import time
from lxml import etree
from datetime import datetime
from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare
# from odoo.tools import amount_to_text_in
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import odoo.addons.decimal_precision as dp
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # @api.one
    # @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id', 'date_invoice')
    # @api.depends('invoice_line_ids.price_subtotal','currency_id', 'company_id', 'invoice_date')
    # def _compute_amount(self):
    #     for value in self:
    #         if value.currency_id and value.company_id and value.currency_id != value.company_id.currency_id:
    #             currency_id = value.currency_id.with_context(date=value.invoice_date)
    #             print(">>>>>>>>>>>>currency_id>>>>>>>>>>>",currency_id)
    #             amount_total_company_signed = currency_id._convert(value.amount_total, value.company_id.currency_id)
    #             print(">>>>>>>>>>>>amount_total_company_signed>>>>>>>>>>>",amount_total_company_signed)
    #             amount_untaxed_signed = currency_id._convert(value.amount_untaxed, value.company_id.currency_id)
    #             print(">>>>>>>>>>>>amount_untaxed_signed>>>>>>>>>>>",amount_untaxed_signed)
    #             amount_tax_signed_company = currency_id._convert(value.amount_tax, value.company_id.currency_id)
    #             print(">>>>>>>>>>>>amount_tax_signed_company>>>>>>>>>>>",amount_tax_signed_company)
    #             # amount_roundoff_signed_company = currency_id._convert(value.amount_roundoff, value.company_id.currency_id)
    #             # print(">>>>>>>>>>>>amount_roundoff_signed_company>>>>>>>>>>>",amount_roundoff_signed_company)
    #             currency_id_rate = currency_id.rate
    #             # currency_id_rate =  currency_id.rate_ids[0].company_rate
    #             currency_id_value = currency_id.rate and (1 / currency_id.rate) or 0.00
    #             # currency_id_value = currency_id.rate_ids[0].company_rate and (1 / currency_id.rate_ids[0].company_rate) or 0.00
    #
    #             sign = value.move_type in ['in_refund', 'out_refund'] and -1 or 1
    #             value.amount_total_company_signed = amount_total_company_signed * sign
    #             # value.amount_total_company_signed = amount_total_company_signed
    #             value.amount_total_signed = value.amount_total * sign
    #             # value.amount_total_signed = value.amount_total
    #             value.amount_untaxed_signed = amount_untaxed_signed * sign
    #             # value.amount_untaxed_signed = amount_untaxed_signed
    #             value.amount_total_company_currency = amount_total_company_signed
    #             value.amount_untaxed_company_currency = amount_untaxed_signed
    #             value.amount_tax_company_currency = amount_tax_signed_company
    #             # value.amount_roundoff_company_currency = amount_roundoff_signed_company
    #             value.currency_id_rate = currency_id_rate
    #             value.currency_id_value = round(currency_id_value, 3)
    #
    #
    #         else:
    #             value.amount_total_company_signed = value.amount_total
    #             value.amount_untaxed_signed = value.amount_untaxed
    #             # amount_tax_signed_company = value.amount_tax
    #             # amount_roundoff_signed_company = value.amount_roundoff
    #             value.currency_id_rate = value.currency_id.rate
    #             # currency_id_rate = value.currency_id.rate_ids[0].company_rate
    #             value.currency_id_value = value.currency_id.rate and (1 / value.currency_id.rate) or 0.00

    # @api.one
    # @api.depends(
    #     'state', 'currency_id', 'invoice_line_ids.price_subtotal',
    #     'move_id.line_ids.amount_residual',
    #     'move_id.line_ids.currency_id')
    # @api.depends(
    #     'state', 'currency_id', 'invoice_line_ids.price_subtotal')
    # def _compute_residual(self):
    #     ############changed due to singleton value error
    #     for value in self:
    #         residual = 0.0
    #         residual_company_signed = 0.0
    #         sign = value.move_type in ['in_refund', 'out_refund'] and -1 or 1
    #         # for line in self.sudo().move_id.line_ids:
    #         for line in self.sudo().line_ids:
    #             # if line.account_id.internal_type in ('receivable', 'payable'):
    #             if line.account_id.account_type in ('asset_receivable', 'liability_payable'):
    #                 residual_company_signed += line.amount_residual
    #                 if line.currency_id == value.currency_id:
    #                     residual += line.amount_residual_currency if line.currency_id else line.amount_residual
    #                 else:
    #                     from_currency = (line.currency_id and line.currency_id.with_context(date=line.date)) or line.company_id.currency_id.with_context(date=line.date)
    #                     residual += from_currency.compute(line.amount_residual, value.currency_id)
    #         value.residual_company_signed = abs(residual_company_signed) * sign
    #         value.residual_company_currency = abs(residual_company_signed)
    #         value.residual_signed = abs(residual) * sign
    #         value.residual = abs(residual)
    #         digits_rounding_precision = value.currency_id.rounding
    #         if float_is_zero(value.residual, precision_rounding=digits_rounding_precision):
    #             value.reconciled = True
    #         else:
    #             value.reconciled = False

    ##############################################################################

    # @api.depends('currency_id', 'company_id', 'invoice_line_ids.price_subtotal')
    # def _compute_amount(self):
    #     for value in self:
    #         if value.currency_id and value.company_id and value.currency_id != value.company_id.currency_id:
    #             # currency_id = value.currency_id.with_context(date=value.invoice_date)
    #             currency_id = value.company_id.currency_id.with_context(date=value.invoice_date)
    #             print(">>>>>>>>>>>>currency_id>>>>>>>>>>>", currency_id.name)
    #             print(">>>>>>>>>>>>value.amount_total>>>>>>>>>>>", self.amount_total)
    #             print(">>>>>>>>>>>>value.amount_total>>>>>>>>>>>", value.amount_total)
    #             amount_total_company_signed = currency_id._convert(value.amount_total, value.company_id.currency_id)
    #             print(">>>>>>>>>>>>amount_total_company_signed>>>>>>>>>>>", amount_total_company_signed)
    #             amount_untaxed_signed = currency_id._convert(value.amount_untaxed, value.company_id.currency_id)
    #             print(">>>>>>>>>>>>amount_untaxed_signed>>>>>>>>>>>", amount_untaxed_signed)
    #             amount_tax_signed_company = currency_id._convert(value.amount_tax, value.company_id.currency_id)
    #             print(">>>>>>>>>>>>amount_tax_signed_company>>>>>>>>>>>", amount_tax_signed_company)
    #             # amount_roundoff_signed_company = currency_id._convert(value.amount_roundoff, value.company_id.currency_id)
    #             # print(">>>>>>>>>>>>amount_roundoff_signed_company>>>>>>>>>>>",amount_roundoff_signed_company)
    #             currency_id_rate = currency_id.rate
    #             # currency_id_rate =  currency_id.rate_ids[0].company_rate
    #             currency_id_value = currency_id.rate and (1 / currency_id.rate) or 0.00
    #             # currency_id_value = currency_id.rate_ids[0].company_rate and (1 / currency_id.rate_ids[0].company_rate) or 0.00
    #
    #             sign = value.move_type in ['in_refund', 'out_refund'] and -1 or 1
    #             print(">>>>>>>>>>>>>sign>>>>>>>>>>>>>", sign)
    #             value.amount_total_company_signed = amount_total_company_signed * sign
    #             # value.amount_total_company_signed = amount_total_company_signed
    #             # value.amount_total_signed = value.amount_total * sign
    #             # value.amount_total_signed = value.amount_total
    #             # value.amount_untaxed_signed = amount_untaxed_signed * sign
    #             # value.amount_untaxed_signed = amount_untaxed_signed
    #             value.amount_total_company_currency = amount_total_company_signed
    #             value.amount_untaxed_company_currency = amount_untaxed_signed
    #             value.amount_tax_company_currency = amount_tax_signed_company
    #             # value.amount_roundoff_company_currency = amount_roundoff_signed_company
    #             value.currency_id_rate = currency_id_rate
    #             value.currency_id_value = round(currency_id_value, 2)
    #
    #         # else:
    #         #     value.amount_total_company_signed = value.amount_total
    #         #     value.amount_untaxed_signed = value.amount_untaxed
    #         #     # amount_tax_signed_company = value.amount_tax
    #         #     # amount_roundoff_signed_company = value.amount_roundoff
    #         #     value.currency_id_rate = value.currency_id.rate
    #         #     # currency_id_rate = value.currency_id.rate_ids[0].company_rate
    #         #     value.currency_id_value = value.currency_id.rate and (1 / value.currency_id.rate) or 0.00

    # @api.one
    # as date_due is not in v17 added invoice_date_due
    # @api.depends('date_due')
    # @api.depends('invoice_date_due')
    # def _compute_due_days_from_due_date(self):
    #     due_diff_days = 0
    #     current_date = datetime.now()
    #     # if self.date_due and current_date:
    #     for data in self:
    #         print(">>>>>>>>>>>>>>data>>>>>>>>>>>>>>>",data)
    #         if data.invoice_date_due and current_date:
    #             # due_date = time.strftime(self.date_due)
    #             # due_date = time.strftime(data.invoice_date_due)
    #             due_date = data.invoice_date_due.strftime("%Y-%m-%d")
    #             due_date = datetime.strptime(due_date, '%Y-%m-%d')
    #             if current_date > due_date:
    #                 due_diff_days = (current_date - due_date).days
    #                 data.due_diff_days = due_diff_days

    # @api.one
    # @api.depends('amount_total', 'amount_total_company_signed', 'currency_id', 'company_id', 'date_invoice')
    # def _get_amount_words(self):
    #     amount_in_words = ""
    #     amount_in_words_local = ""
    #     if self.amount_total and self.currency_id:
    #         amount_in_words = amount_to_text_in.amount_to_text(self.amount_total, 'en', self.currency_id.name, self.currency_id.subcurrency)
    #     self.amount_to_text_inv_currency = amount_in_words
    #     if self.company_id.currency_id != self.currency_id:
    #         if self.amount_total_company_signed and self.company_id.currency_id:
    #             amount_in_words_local = amount_to_text_in.amount_to_text(self.amount_total_company_signed, 'en', self.company_id.currency_id.name, self.company_id.currency_id.subcurrency)
    #     self.amount_to_text_local_currency = amount_in_words_local

    # @api.depends('amount_total', 'amount_total_company_signed', 'currency_id', 'company_id')
    # @api.depends('amount_total', 'currency_id', 'company_id')
    # def _get_amount_words(self):
    #     for po in self:
    #         print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",self.currency_id,po.currency_id)
    #         amount_in_words = ""
    #         amount_in_words_local = ""
    #         if po.amount_total and po.currency_id:
    #             amount_in_words = str(po.currency_id.amount_to_text(po.amount_total))
    #         po.amount_to_text_inv_currency = amount_in_words
    #
    #         if po.company_id.currency_id != po.currency_id:
    #             if po.company_id.currency_id:
    #                 amount_in_words_local = str(po.currency_id.amount_to_text(po.amount_total))
    #         po.amount_to_text_local_currency = amount_in_words_local

    # @api.depends('amount_total', 'currency_id')
    # def _compute_amount_total_words(self):
    #     for move in self:
    #         move.amount_total_words = move.currency_id.amount_to_text(move.amount_total).replace(',', '')

    # @api.one
    # @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id', 'date_invoice')
    @api.depends('invoice_line_ids.price_subtotal', 'currency_id', 'company_id', 'invoice_date')
    def _compute_discount_amount(self):
        amount_discounted_value = sum(line.price_subtotal for line in self.invoice_line_ids)
        amount_actual_value = sum((line.price_unit * line.quantity) for line in self.invoice_line_ids)
        ####################changed due to singleton error
        for values in self:
            values.amount_discounted = amount_actual_value - amount_discounted_value
            amount_discounted_signed_company = values.amount_discounted
            # if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            if values.currency_id and values.company_id and values.currency_id != values.company_id.currency_id:
                # currency_id = self.currency_id.with_context(date=self.invoice_date)
                currency_id = values.currency_id.with_context(date=values.invoice_date)
                # amount_discounted_signed_company = currency_id.compute(self.amount_discounted, self.company_id.currency_id)
                # amount_discounted_signed_company = currency_id._convert(self.amount_discounted, self.company_id.currency_id)
                amount_discounted_signed_company = currency_id._convert(values.amount_discounted,
                                                                        values.company_id.currency_id)
            values.amount_discounted_company_currency = amount_discounted_signed_company

    # @api.one
    # @api.depends('invoice_line_ids.uom_id', 'invoice_line_ids.quantity')
    @api.depends('invoice_line_ids.product_uom_id', 'invoice_line_ids.quantity')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.invoice_line_ids:
            if line.product_uom_id.id in qty_dict:
                qty_dict[line.product_uom_id.id]['product_uom_qty'] += line.quantity
            else:
                qty_dict[line.product_uom_id.id] = {
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_uom_id and line.product_uom_id.name or ''
                }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (
                qty_dict[each]['product_uom'])
        self.total_quantity_based_uom = qty_string

    # @api.one
    @api.depends('invoice_line_ids.sales_user_id')
    def _get_line_salesman(self):
        salesman_list = []
        salesman_text = ""
        for line in self.invoice_line_ids:
            if line.sales_user_id:
                salesman_list.append(line.sales_user_id.name)
        if salesman_list:
            salesman_list = list(set(salesman_list))
            salesman_text = str(salesman_list).replace("[", "").replace("u'", "").replace("]", "").replace("'", "")
        self.salesman_name = salesman_text

    user_id = fields.Many2one('res.users', string='Created By', track_visibility='onchange',
                              readonly=True,
                              default=lambda self: self.env.user)
    sales_manager_id = fields.Many2one('res.users', string='Sales Manager', readonly=True,
                                       copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True,
                                   copy=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale', readonly=True, copy=False)
    from_sale_order = fields.Boolean('From Sale Order', readonly=True, default=False, copy=False)

    # amount_untaxed = fields.Monetary(string='Untaxed Amount',
    #     store=True, readonly=True, compute='_compute_amount', track_visibility='always')
    # amount_untaxed_signed = fields.Monetary(string='Untaxed Amount in Company Currency Sign', currency_field='company_currency_id',
    #     store=True, readonly=True, compute='_compute_amount')

    # amount_untaxed_company_currency = fields.Monetary(string='Untaxed Amount in Company Currency',
    #                                                   currency_field='company_currency_id',
    #                                                   store=True, readonly=True, compute='_compute_amount')
    # amount_untaxed_company_currency = fields.Monetary(string='Untaxed Amount in Company Currency',store=True)
    # # # amount_tax = fields.Monetary(string='Tax',
    # # #     store=True, readonly=True, compute='_compute_amount')
    #
    # # amount_tax_company_currency = fields.Monetary(string='Tax in Company Currency', currency_field='company_currency_id',
    # #     store=True, readonly=True, compute='_compute_amount')
    #
    # amount_tax_company_currency = fields.Monetary(string='Tax in Company Currency')
    #
    # # # amount_roundoff = fields.Monetary(string='Round Off',
    # # #     store=True, readonly=True, compute='_compute_amount')
    # # amount_roundoff_company_currency = fields.Monetary(string='Round Off in Company Currency', currency_field='company_currency_id',
    # #     store=True, readonly=True, compute='_compute_amount')
    #
    # amount_roundoff_company_currency = fields.Monetary(string='Round Off in Company Currency')
    #
    # # currency_id_rate = fields.Float(string='Currency Rate',  digits=(12, 9),
    # #     store=True, readonly=True, compute='_compute_amount')
    # # currency_id_value = fields.Float(string='Currency Conversion Value',  digits=(12, 3),
    # #     store=True, readonly=True, compute='_compute_amount')
    #
    # currency_id_rate = fields.Float(string='Currency Rate',
    #     store=True)
    # currency_id_value = fields.Float(string='Currency Conversion Value',
    #     store=True)
    #
    #
    # amount_total = fields.Monetary(string='Total',
    #     store=True)
    # # amount_total_signed = fields.Monetary(string='Total in Invoice Currency', currency_field='currency_id',
    # #     store=True, readonly=True, compute='_compute_amount',
    # #     help="Total amount in the currency of the invoice, negative for credit notes.")
    # # amount_total_company_signed = fields.Monetary(string='Total in Company Currency Sign', currency_field='company_currency_id',
    # #     store=True, readonly=True, compute='_compute_amount',
    # #     help="Total amount in the currency of the company, negative for credit notes.")
    #
    # amount_total_company_signed = fields.Monetary(string='Total in Company Currency Sign',
    #                                               help="Total amount in the currency of the company, "
    #                                                    "negative for credit notes.")
    #
    # # amount_total_company_currency= fields.Monetary(string='Total in Company Currency', currency_field='company_currency_id',
    # #     store=True, readonly=True, compute='_compute_amount')
    #
    # amount_total_company_currency= fields.Monetary(string='Total in Company Currency')

    # due_diff_days = fields.Integer('Due Days', compute='_compute_due_days_from_due_date')
    due_diff_days = fields.Integer('Due Days')
    # amount_to_text_inv_currency = fields.Char(compute='_get_amount_words', string="Amount In Words")
    amount_to_text_inv_currency = fields.Char(string="Amount In Words",compute='_get_amount_words')
    # amount_to_text_local_currency = fields.Char(compute='_get_amount_words', string='Amount In Words(Local)')
    amount_to_text_local_currency = fields.Char(string='Amount In Words(Local)',compute='_get_amount_words')
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Quantity')
    amount_discounted = fields.Monetary(string='Discounted Amount', store=True, readonly=True,
                                        compute='_compute_discount_amount', track_visibility='always')
    amount_discounted_company_currency = fields.Monetary(string='Discounted Amount in Company Currency',
                                                         currency_field='company_currency_id', store=True,
                                                         readonly=True, compute='_compute_discount_amount',
                                                         track_visibility='always')
    reconciled = fields.Boolean(string='Paid/Reconciled', store=True, readonly=True,
                                help="It indicates that the invoice has been paid and the journal entry of the invoice has been reconciled with one or several journal entries of payment.")
    residual = fields.Monetary(string='Amount Due',
                               store=True, help="Remaining amount due.")
    residual_signed = fields.Monetary(string='Amount Due in Invoice Currency', currency_field='currency_id',
                                      store=True, help="Remaining amount due in the currency of the invoice.")
    residual_company_signed = fields.Monetary(string='Amount Due in Company Currency Sign',
                                              currency_field='company_currency_id',
                                              store=True, help="Remaining amount due in the currency of the company.")
    # residual_company_currency = fields.Monetary(string='Amount Due in Company Currency',
    #                                             currency_field='company_currency_id',
    #                                             store=True, help="Remaining amount due in the currency of the company.")
    payment_ids = fields.Many2many('account.payment', 'account_invoice_payment_rel', 'invoice_id', 'payment_id',
                                   string="Payments", copy=False, readonly=True)
    despatch_through = fields.Char('Dispatch Through', readonly=True, copy=False)
    destination = fields.Char('Destination', readonly=True, copy=False)
    despatch_document = fields.Char('Dispatch Document', readonly=True, copy=False)
    despatch_date = fields.Datetime('Dispatch Date', readonly=True, copy=False)
    salesman_name = fields.Char(compute='_get_line_salesman', string="Salesperson", readonly=True)
    from_purchase_order = fields.Boolean('From Purchase Order', readonly=True, default=False, copy=False)
    # state = fields.Selection([
    #     ('draft', 'Draft'),
    #     ('proforma', 'Pro-forma'),
    #     ('proforma2', 'Pending For Approval'),
    #     ('open', 'Open'),
    #     ('paid', 'Paid'),
    #     ('posted', 'Post'),
    #     ('cancel', 'Cancelled'),
    # ], string='Status', index=True, readonly=True, default='draft',
    #     track_visibility='onchange', copy=False,
    #     help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Invoice.\n"
    #          " * The 'Pro-forma' status is used when the invoice does not have an invoice number.\n"
    #          " * The 'Waiting For Approval' status is used when the invoice is required for higher authority approval.\n"
    #          " * The 'Open' status is used when user creates invoice, an invoice number is generated. It stays in the open status till the user pays the invoice.\n"
    #          " * The 'Paid' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled.\n"
    #          " * The 'Cancelled' status is used when user cancel invoice.")
    refund_reason = fields.Text(string="Refund Reason", readonly=True, copy=False)
    lc_no_id = fields.Many2one('purchase.order.lc.master', string='LC No', copy=False)
    cancel_reason = fields.Text(string="Cancel Reason", readonly=True, copy=False)
    cash_sale = fields.Boolean(string='Cash Sales', default=False,
                               help="Check this box if this customer is a cash sale customer.", copy=False)
    billing_info = fields.Text(string="Billing Info", copy=False, readonly=True)
    shipping_info = fields.Text(string="Shipping Info", copy=False, readonly=True)
    number = fields.Char(store=True, readonly=True, copy=False)
    origin = fields.Char(string='Source Document',
                         help="Reference of the document that produced this invoice.")

    ###########################################added custom

    account_id = fields.Many2one('account.account', string='Account')

    #################################################
    # amount_total_inr = fields.Monetary(string='Total in INR')
    #
    company_amount_total = fields.Monetary(string='Total in Company Currency',
                                           store=True,
                                           currency_field='company_currency_id')

    company_amount_untaxed = fields.Monetary(string='Untaxed Amount in Company Currency',
                                              store=True,
                                             currency_field='company_currency_id')

    company_amount_tax = fields.Monetary(string='Tax in Company Currency',
                                          store=True,
                                         currency_field='company_currency_id')

    company_amount_residual = fields.Monetary(string='Amount Due in Company Currency',
                                               store=True,
                                              currency_field='company_currency_id')

#####################
    amount_untaxed_company_currency = fields.Monetary(string='Untaxed Amount in Company Currency', store=True,
                                                      compute='_compute_amount_in_company_currency',
                                                      currency_field='company_currency_id')

    amount_tax_company_currency = fields.Monetary(string='Tax in Company Currency',
                                                  compute='_compute_amount_in_company_currency', store=True,
                                                  currency_field='company_currency_id'
                                                  )

    amount_total_company_currency = fields.Monetary(string='Total in Company Currency',
                                                    compute='_compute_amount_in_company_currency', store=True,
                                                    currency_field='company_currency_id'
                                                    )
    residual_company_currency = fields.Monetary(string='Amount Due in Company Currency',
                                                compute='_compute_amount_in_company_currency',
                                                currency_field='company_currency_id',
                                                store=True)



    @api.depends('amount_total', 'currency_id')
    def _compute_amount_in_company_currency(self):
        # print(">>>>>>>>>>>>_compute_amount_total_inr>>>>>>>>>>>>>>")
        for record in self:
            company_currency = self.company_id.currency_id
            # print(">>>>>>>>>>>>>company_currency>>>>>>>>>>>>>>>>>>>>>>", company_currency)
            if company_currency != self.currency_id:
                # Compute the converted amount
                record.amount_total_company_currency = record.currency_id._convert(
                    record.amount_total, company_currency, record.company_id, record.invoice_date or fields.Date.today()
                )
                # print(">>>>>>>>>>>>>>record.company_amount_total>>>>>>ifff>>>>>>>>>>>>>>>>>>>>>",
                #       record.company_amount_total)
                record.amount_untaxed_company_currency = record.currency_id._convert(
                    record.amount_untaxed, company_currency, record.company_id,
                    record.invoice_date or fields.Date.today()
                )
                # print(">>>>>>>>>>>>>>>record.company_amount_untaxed>>>>>>>>>>>>>>>>>>>>>>>",
                #       record.company_amount_untaxed)

                record.amount_tax_company_currency = record.currency_id._convert(
                    record.amount_tax, company_currency, record.company_id,
                    record.invoice_date or fields.Date.today()
                )
                # print(">>>>>>>>>>>>>>record.company_amount_tax>>>>>>>>>>>>>>>>>",
                #       record.company_amount_tax)

                record.residual_company_currency = record.currency_id._convert(
                    record.amount_residual, company_currency, record.company_id,
                    record.invoice_date or fields.Date.today()
                )
                # print(">>>>>>>>>>>>>>record.company_amount_residual>>>>>>>>>>>>>>>>>",
                #       record.company_amount_residual)

            else:
                record.amount_total_company_currency = record.amount_total
                # print(">>>>>>>>>>>>>>record.company_amount_total>>>>>>elseee>>>>>>>>>>>>>>>>>>>>>",
                #       record.company_amount_total)

                record.amount_untaxed_company_currency = record.amount_untaxed
                # print(">>>>>>>>>>>>>record.company_amount_untaxed>>>>>>elseee>>>>>>>>>>>>>>>>>>>>>",
                #       record.company_amount_untaxed)

                record.amount_tax_company_currency = record.amount_tax
                # print(">>>>>>>>>>>>>record.company_amount_tax>>>>>>elseee>>>>>>>>>>>>>>>>>>>>>",
                #       record.company_amount_tax)

                record.residual_company_currency = record.amount_residual
                # print(">>>>>>>>>>>>>record.company_amount_residual>>>>>>elseee>>>>>>>>>>>>>>>>>>>>>",
                #       record.company_amount_residual)

    @api.depends('amount_total', 'currency_id', 'company_id')
    def _get_amount_words(self):
        for amt in self:
            amount_in_words = ""
            amount_in_words_local = ""
            print(">>>>>>>>>>>>>>>amt.currency_id>>>>>>>>>>>>>>>>>>>>>",amt.currency_id)
            if amt.amount_total and amt.currency_id:
                amount_in_words = str(amt.currency_id.amount_to_text(amt.amount_total))
            amt.amount_to_text_inv_currency = amount_in_words

            if amt.company_id.currency_id != amt.currency_id:
                if amt.company_id.currency_id:
                    amount_in_words_local = str(amt.currency_id.amount_to_text(amt.amount_total))
            amt.amount_to_text_local_currency = amount_in_words_local

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        warning = {}
        if self.journal_id:
            if self.partner_id:
                self.currency_id = self.partner_id.transaction_currency_id and self.partner_id.transaction_currency_id.id or self.partner_id.company_id.currency_id.id
            if self.warehouse_id:
                for each in self.journal_id.stock_warehouse_ids:
                    if self.warehouse_id.id != each.id:
                        self.journal_id = False
                        warning = {
                            'title': _("Warning"),
                            'message': _("Journal doesn't match with the respective warehouse")}
        return {'warning': warning}

    # @api.multi
    def invoice_print(self):
        """ Print the invoice and mark it as sent, so that we can see more
            easily the next step of the workflow
        """
        self.ensure_one()
        self.sent = True
        if self.type == 'out_invoice':
            if self.cash_sale:
                return self.env['report'].get_action(self, 'account.invoice.cash.rml.report')
            return self.env['report'].get_action(self, 'account.invoice.rml.report')
        if self.type == 'in_invoice':
            return self.env['report'].get_action(self, 'account.invoice.vendor.rml.report')
        elif self.type == 'out_refund':
            if self.cash_sale:
                return self.env['report'].get_action(self, 'credit.note.cash.rml.report')
            return self.env['report'].get_action(self, 'credit.note.rml.report')
        elif self.type == 'in_refund':
            return self.env['report'].get_action(self, 'debit.note.rml.report')

    # @api.multi
    def action_invoice_proforma2(self):
        if self.filtered(lambda inv: inv.state != 'draft'):
            raise UserError(_("Invoice must be a draft in order to send it to approval."))
        for each in self:
            if each.partner_id.transaction_currency_id != each.currency_id:
                if each.move_type in ['out_invoice', 'out_refund']:
                    raise UserError(_("Currency Mismatch, Customer transaction currency and invoice currency differs."))
                if each.move_type in ['in_invoice', 'in_refund']:
                    raise UserError(_("Currency Mismatch, Vendor transaction currency and invoice currency differs."))
            if each.move_type in ['in_refund', 'out_refund']:
                if not each.refund_reason:
                    raise UserError(_("You must specify the refund reason and send it to approval."))
        return self.write({'state': 'proforma2'})

    # @api.multi
    def action_invoice_open(self):
        print(">>>>>>>>action_invoice_open>>>>>>>>>>>>>>")
        # lots of duplicate calls to action_invoice_open, so we remove those already open
        to_open_invoices = self.filtered(lambda inv: inv.state != 'open')
        if to_open_invoices.filtered(lambda inv: inv.state not in ['proforma2', 'draft']):
            raise UserError(_("Invoice must be in draft or pending for approval state in order to validate it."))
        # to_open_invoices.action_date_assign()
        # to_open_invoices.action_move_create()
        # to_open_invoices.action_post()
        return to_open_invoices.action_post()

    # @api.multi
    def action_invoice_cancel(self):
        print(">>>>>>>>action_invoice_cancel>>>>>>>>>>>>>>")

        if self.filtered(lambda inv: inv.state not in ['proforma2', 'draft', 'open']):
            raise UserError(_("Invoice must be in draft, pending for approval or open state in order to be cancelled."))
        for each in self:
            view = self.env.ref('ebits_custom_account.invoice_cancel_reason_wizard_form')
            wiz = self.env['invoice.cancel.reason.wizard'].create({
                'name': ' '})
            return {
                'name': _('Enter Cancel Reason'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'invoice.cancel.reason.wizard',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
            }

    # @api.multi
    def action_invoice_draft(self):
        print(">>>>>>>>action_invoice_draft>>>>>>>>>>>>>>")

        if self.filtered(lambda inv: inv.state != 'cancel'):
            raise UserError(_("Invoice must be cancelled in order to reset it to draft."))
        self.write({'state': 'draft', 'date': False})
        try:
            if self.type == 'out_invoice':
                report_invoice = self.env['report']._get_report_from_name('account.invoice.rml.report')
            if self.type == 'in_invoice':
                report_invoice = self.env['report']._get_report_from_name('account.invoice.vendor.rml.report')
            elif self.type == 'out_refund':
                report_invoice = self.env['report']._get_report_from_name('credit.note.rml.report')
            elif self.type == 'in_refund':
                report_invoice = self.env['report']._get_report_from_name('debit.note.rml.report')
            else:
                report_invoice = self.env['report']._get_report_from_name('account.invoice.rml.report')
        except IndexError:
            report_invoice = False
        if report_invoice and report_invoice.attachment:
            for invoice in self:
                with invoice.env.do_in_draft():
                    invoice.number, invoice.state = invoice.move_name, 'open'
                    attachment = self.env['report']._attachment_stored(invoice, report_invoice)[invoice.id]
                if attachment:
                    attachment.unlink()
        return True

    @api.onchange('warehouse_id')
    def warehouse_id_change(self):
        warning = {}
        if self.warehouse_id:
            if self.journal_id:
                for each in self.journal_id.stock_warehouse_ids:
                    if self.warehouse_id.id != each.id:
                        self.warehouse_id = self.partner_id.delivery_warehouse_id.id
            if self.move_type in ['out_invoice', 'out_refund']:
                if self.partner_id.delivery_warehouse_id != self.warehouse_id:
                    self.warehouse_id = self.partner_id.delivery_warehouse_id.id
                    warning = {
                        'title': _("Warning"),
                        'message': _("You cannot change the customer warehouse/branch configured in customer master")}
        return {'warning': warning}

    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        warning = {}
        if self.currency_id:
            if self.partner_id:
                if self.partner_id.transaction_currency_id != self.currency_id:
                    self.currency_id = self.partner_id.transaction_currency_id
                    if self.move_type in ['out_invoice', 'out_refund']:
                        warning = {
                            'title': _("Warning"),
                            'message': _("You cannot change the customer currency configured in customer master!")}
                    else:
                        warning = {
                            'title': _("Warning"),
                            'message': _("You cannot change the Vendor currency configured in Vendor master!")}
                    return {'warning': warning}
            for line in self.invoice_line_ids.filtered(lambda r: r.purchase_line_id):
                # line.price_unit = line.purchase_id.currency_id.compute(line.purchase_line_id.price_unit,
                #                                                        self.currency_id, round=False)

                line.price_unit = line.purchase_id.currency_id._convert(line.purchase_line_id.price_unit,
                                                                       self.currency_id, round=False)

    @api.onchange('partner_id')
    def partner_id_change(self):
        warning = {}
        if self.partner_id:
            self.cash_sale = self.partner_id.cash_sale and self.partner_id.cash_sale or False
            if self.partner_id.transaction_currency_id:
                self.currency_id = self.partner_id.transaction_currency_id
            else:
                # if self.type in ['out_invoice', 'out_refund']:
                if self.move_type in ['out_invoice', 'out_refund']:
                    warning = {
                        'title': _("Warning"),
                        'message': _("You cannot change the customer currency configured in customer master!")}
                else:
                    warning = {
                        'title': _("Warning"),
                        'message': _("You cannot change the Vendor currency configured in Vendor master!")}
                self.currency_id = False
            self.warehouse_id = self.partner_id.delivery_warehouse_id.id
        else:
            self.cash_sale = False
            self.billing_info = ''
            self.shipping_info = ''
        return {'warning': warning}

    @api.onchange('purchase_id')
    def purchase_order_id_change(self):
        if not self.purchase_id:
            self.from_purchase_order = False
            return {}
        self.from_purchase_order = True
        return {}

    @api.onchange('state', 'partner_id', 'invoice_line_ids', 'warehouse_id')
    def _onchange_allowed_purchase_ids(self):
        '''
        The purpose of the method is to define a domain for the available
        purchase orders.
        '''
        result = {}
        purchase_line_ids = self.invoice_line_ids.mapped('purchase_line_id')
        # purchase_ids = self.invoice_line_ids.mapped('purchase_id').filtered(lambda r: r.order_line <= purchase_line_ids)
        purchase_ids = self.invoice_line_ids.mapped('purchase_order_id').filtered(
            lambda r: r.order_line <= purchase_line_ids)

        result['domain'] = {'purchase_id': [
            ('invoice_status', '=', 'to invoice'),
            ('partner_id', 'child_of', self.partner_id.id),
            ('id', 'not in', purchase_ids.ids),
            ('warehouse_id', '=', self.warehouse_id.id)
        ]}
        return result

    # @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_move = self.env['account.move']

        for inv in self:
            print(">>>>>>>>>>>>action_move_create>>>>>>>>>>>>>>>>>>")
            context = dict(self.env.context)
            if inv.partner_id.transaction_currency_id != inv.currency_id:
                if inv.move_type in ['out_invoice', 'out_refund']:
                    raise UserError(_("Currency Mismatch, Customer transaction currency and invoice currency differs."))
                if inv.move_type in ['in_invoice', 'in_refund']:
                    raise UserError(_("Currency Mismatch, Vendor transaction currency and invoice currency differs."))
            if not inv.journal_id.sequence_id:
                raise UserError(_("Please define sequence on the journal related to this invoice."))
            if not inv.invoice_line_ids:
                raise UserError(_("Please create some invoice lines."))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            date_invoice = inv.date_invoice
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml = inv.invoice_line_move_line_get()
            iml += inv.tax_line_move_line_get()

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, iml)
            if inv.amount_roundoff:
                if not inv.warehouse_id.round_off_account_id:
                    raise UserError(_("Please define round off account in the following warehouse/branch %s.") % (
                        inv.warehouse_id.name))
                round_total = round_total_currency = 0
                round_amount_currency = round_price = 0
                round_off_dict = {}
                round_off_dict = {
                    'type': 'dest',
                    'name': "Round Off",
                    'account_id': inv.warehouse_id.round_off_account_id.id,
                    # 'date_maturity': inv.date_due,
                    'invoice_id': inv.id
                }
                if inv.currency_id != company_currency:
                    currency = inv.currency_id.with_context(date=inv.date_invoice or fields.Date.context_today(self))
                    round_amount_currency = currency.round(inv.amount_roundoff)
                    round_price = currency.compute(inv.amount_roundoff, company_currency)
                else:
                    round_amount_currency = False
                    round_price = self.currency_id.round(inv.amount_roundoff)
                round_total_currency = round_amount_currency or round_price
                round_total = round_price
                round_off_dict['currency_id'] = diff_currency and inv.currency_id.id
                if inv.type in ['in_refund', 'out_refund']:
                    round_off_dict['price'] = round_total
                    round_off_dict['amount_currency'] = diff_currency and round_total_currency
                    total -= round_total
                    total_currency -= round_total_currency
                else:
                    round_off_dict['price'] = -round_total
                    round_off_dict['amount_currency'] = diff_currency and -round_total_currency
                    total += round_total
                    total_currency += round_total_currency
                iml.append(round_off_dict)
            name = inv.name or '/'
            if inv.payment_term_id:
                totlines = \
                inv.with_context(ctx).payment_term_id.with_context(currency_id=inv.currency_id.id).compute(total,
                                                                                                           date_invoice)[
                    0]
                res_amount_currency = total_currency
                ctx['date'] = date_invoice
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                    else:
                        amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })
            else:
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': inv.account_id.id,
                    # 'date_maturity': inv.date_due,
                    'date_maturity': inv.invoice_date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'invoice_id': inv.id
                })

            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            line = inv.group_lines(iml, line)
            journal = inv.journal_id.with_context(ctx)
            line = inv.finalize_invoice_move_lines(line)

            date = inv.date or date_invoice
            move_vals = {
                'ref': inv.reference,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
                'lc_no_id': inv.lc_no_id and inv.lc_no_id.id or False,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
            ##############Asset code#################
            context.pop('default_type', None)
            inv.invoice_line_ids.with_context(context).asset_create()
            ##############Asset code#################
        return True

    # @api.multi
    def unlink(self):
        for invoice in self:
            if invoice.from_sale_order:
                raise UserError(_("You cannot delete an invoice which is created from sale order as the origin"))
        res = super(AccountMove, self).unlink()
        return res

    def _prepare_invoice_line_from_po_line(self, line):
        data = super(AccountMove, self)._prepare_invoice_line_from_po_line(line)
        if line.product_id.purchase_method == 'receive':
            qty = (line.qty_received - line.qty_returned) - (line.qty_invoiced - line.qty_refunded)
            data['quantity'] = qty
        if self.type == 'in_refund':
            # invoice_line = self.env['account.invoice.line']
            invoice_line = self.env['account.move.line']
            data['quantity'] *= -1
            data['account_id'] = invoice_line.with_context(
                {'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account()
            account = invoice_line.get_invoice_line_account('in_invoice', line.product_id,
                                                            self.purchase_id.fiscal_position_id,
                                                            self.env.user.company_id)
            if account:
                data['account_id'] = account.id
        if data:
            data['from_purchase_order'] = True
        return data

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        values = super(AccountMove, self)._prepare_refund(invoice, date_invoice=date_invoice, date=date,
                                                          description=description, journal_id=journal_id)
        if invoice.warehouse_id:
            values.update({'warehouse_id': invoice.warehouse_id.id})
        # return values
        return values


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # @api.one
    # @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
    #     'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
    #     'invoice_id.date_invoice')
    # def _compute_price(self):
    #     for value in self:
    #         # currency = self.invoice_id and self.invoice_id.currency_id or None
    #         currency = value.move_id and value.move_id.currency_id or None
    #         price = value.price_unit * (1 - (value.discount or 0.0) / 100.0)
    #         taxes = False
    #         # if value.invoice_line_tax_ids:
    #         if value.invoice_line_tax_ids:
    #             taxes = value.invoice_line_tax_ids.compute_all(price, currency, value.quantity, product=value.product_id, partner=value.invoice_id.partner_id)
    #         value.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else value.quantity * price
    #         value.price_subtotal_incl = price_subtotal_incl_signed = taxes['total_included'] if taxes else value.quantity * price
    #         if value.invoice_id.currency_id and value.invoice_id.company_id and value.invoice_id.currency_id != value.invoice_id.company_id.currency_id:
    #             price_subtotal_signed = value.invoice_id.currency_id.with_context(date=value.invoice_id.date_invoice).compute(price_subtotal_signed, value.invoice_id.company_id.currency_id)
    #             price_subtotal_incl_signed = value.invoice_id.currency_id.with_context(date=value.invoice_id.date_invoice).compute(price_subtotal_incl_signed, value.invoice_id.company_id.currency_id)
    #         # sign = value.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
    #         sign = value.move_id.type in ['in_refund', 'out_refund'] and -1 or 1
    #         value.price_subtotal_signed = price_subtotal_signed * sign
    #         value.price_subtotal_incl_signed = price_subtotal_incl_signed * sign

    sales_user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange',
                                    copy=False)
    sale_order_line_id = fields.Many2one('sale.order.line', string='Sale Line', readonly=True, copy=False)
    from_sale_order = fields.Boolean('From Sale Order', readonly=True, default=False, copy=False)
    from_purchase_order = fields.Boolean('From Purchase Order', readonly=True, default=False, copy=False)
    price_unit = fields.Float(string='Unit Price', required=True, digits=dp.get_precision('Purchase Product Price'))

    # price_subtotal = fields.Monetary(string='Amount',
    #     store=True, readonly=True, compute='_compute_price')
    # price_subtotal_signed = fields.Monetary(string='Amount Signed', currency_field='company_currency_id',
    #     store=True, readonly=True, compute='_compute_price',
    #     help="Total amount in the currency of the company, negative for credit notes.")
    # price_subtotal_incl = fields.Float(string='Subtotal Incl',
    #     store=True, readonly=True,compute='_compute_price')
    # price_subtotal_incl_signed = fields.Float(string='Subtotal Incl Company', currency_field='company_currency_id',
    #     store=True, readonly=True,compute='_compute_price')

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(AccountMoveLine, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self._context.get('create_service'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='product_id']"):
                node.set('domain', "[('type', '=', 'service')]")
            res['arch'] = etree.tostring(doc)
        return res

    @api.onchange('product_id')
    def onchange_custom_product_id(self):
        warning = {}
        # if not self.invoice_id:
        if not self.move_id:
            return
        # type = self.move_id.type
        type = self.move_id.move_type
        if not self.product_id:
            self.price_unit = 0.0000
            self.account_id = False
            self.name = ''
            # self.uom_id = False
            self.product_uom_id = False
            self.quantity = 1.000
            # self.invoice_line_tax_ids = []
            self.tax_ids = []
            # self.account_analytic_id = False
            self.analytic_line_ids = False
            self.currency_id = self.move_id.currency_id
        if self.product_id:
            if self.product_id.detailed_type != 'service' and not self.from_purchase_order:
                if type in ('in_invoice', 'in_refund'):
                    warning = {
                        'title': _("Warning"),
                        'message': _("You cannot select a product manually!")}
                    self.product_id = False
                    self.name = ''
                    self.account_id = False
                    self.product_uom_id = False
                    self.quantity = 0.000
                    self.price_unit = 0.0000
                    self.tax_ids = []
                    # self.account_analytic_id = False
                    self.analytic_line_ids = False
                    # self.analytic_tag_ids = []
                    self.discount = 0.00
                    self.currency_id = self.move_id.currency_id
        return {'warning': warning}

    @api.onchange('price_unit')
    def onchange_price_unit(self):
        warning = {}
        if self.price_unit:
            if self.sudo().purchase_line_id:
                if self.price_unit > self.sudo().purchase_line_id.price_unit:
                    warning = {
                        'title': _("Warning"),
                        'message': _("Unit price must lesser or equal to the price defined in purchase order!")}
                    self.price_unit = self.sudo().purchase_line_id.price_unit
            if abs(self.price_unit) != self.price_unit:
                warning = {
                    'title': _("Warning"),
                    'message': _("Unit price must be positive value!")}
                if self.sudo().purchase_line_id:
                    self.price_unit = self.sudo().purchase_line_id.price_unit
        return {'warning': warning}

    @api.onchange('quantity')
    def onchange_quantity_custom(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        qty = 0.00
        if not self.quantity:
            return {}
        # type = self.invoice_id.type
        type = self.move_id.move_type
        if self.quantity and (not self.product_uom_id.allow_decimal_digits):
            integer, decimal = divmod(self.quantity, 1)
            if decimal:
                if self.purchase_line_id:
                    if self.product_id.purchase_method == 'purchase':
                        qty = self.purchase_line_id.product_qty - self.purchase_line_id.qty_invoiced
                    else:
                        qty = self.purchase_line_id.qty_received - self.purchase_line_id.qty_invoiced
                    if self.quantity > qty:
                        self.quantity = qty
                    else:
                        self.quantity = 0.000
                else:
                    self.quantity = 0.000
                warning = {
                    'title': _("Warning"),
                    'message': _(
                        "You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value") % (
                                   self.uom_id.name)}
                return {'warning': warning}
        if self.purchase_line_id:
            qty = 0.00
            if self.product_id.purchase_method == 'purchase':
                qty = self.purchase_line_id.product_qty - self.purchase_line_id.qty_invoiced
            else:
                qty = self.purchase_line_id.qty_received - self.purchase_line_id.qty_invoiced
            if self.quantity > qty:
                warning = {
                    'title': _("Warning"),
                    'message': _("Quantity must be lesser or equal to the GRN Quantity!")}
                self.quantity = qty
        if type not in ('out_refund', 'in_refund'):
            if abs(self.quantity) != self.quantity:
                warning = {
                    'title': _("Warning"),
                    'message': _("Quantity must be positive!")}
                if self.purchase_line_id:
                    qty = 0.000
                    if self.product_id.purchase_method == 'purchase':
                        qty = self.purchase_line_id.product_qty - self.purchase_line_id.qty_invoiced
                    else:
                        qty = self.purchase_line_id.qty_received - self.purchase_line_id.qty_invoiced
                    self.quantity = qty
                else:
                    self.quantity = 0.000
        return {'warning': warning}

    @api.onchange('discount')
    def onchange_discount_custom(self):
        warning = {}
        if not self.discount:
            return {}
        if self.product_id.type == 'service':
            warning = {
                'title': _("Warning"),
                'message': _("You cannot define discount for service items!")}
            self.discount = 0.00
            return {'warning': warning}
        if abs(self.discount) != self.discount:
            warning = {
                'title': _("Warning"),
                'message': _("Discount must be positive!")}
            self.discount = 0.00
            return {'warning': warning}

    # @api.multi
    def action_update_invoice_line(self):
        for each in self:
            print(">>>>>>action_update_invoice_line>>>>>>>>>>>")
            if self.env.context.get('default_invoice_id'):
                if not each.price_unit:
                    raise UserError(_("Kindly enter the unit price and proceed forward!"))
                if abs(each.price_unit) != each.price_unit:
                    raise UserError(_("Unit price must be positive value!"))
                if abs(each.quantity) != each.quantity:
                    raise UserError(_("Qty must be positive!"))
                if each.discount:
                    if each.product_id.type == 'service':
                        raise UserError(_("You cannot define discount for service items!"))
                    if abs(each.discount) != each.discount:
                        raise UserError(_("Discount must be positive!"))
                each.write({'invoice_id': self.env.context.get('invoice_id')})
                each.invoice_id.compute_taxes()
        return True

    # @api.multi
    def action_update_supplier_invoice_line(self):
        for each in self:
            print(">>>>>>action_update_supplier_invoice_line>>>>>>>>>>>")

            if self.env.context.get('default_invoice_id'):
                if not each.price_unit:
                    raise UserError(_("Kindly enter the unit price and proceed forward!"))
                if abs(each.price_unit) != each.price_unit:
                    raise UserError(_("Unit price must be positive value!"))
                if abs(each.quantity) != each.quantity:
                    raise UserError(_("Qty must be positive!"))
                if each.discount:
                    if each.product_id.type == 'service':
                        raise UserError(_("You cannot define discount for service items!"))
                    if abs(each.discount) != each.discount:
                        raise UserError(_("Discount must be positive!"))
                each.write({'invoice_id': self.env.context.get('invoice_id')})
                each.invoice_id.compute_taxes()
        return True

    # @api.multi
    def unlink(self):
        for line in self:
            if line.from_sale_order:
                raise UserError(_("You cannot delete an invoice line which is created from sale order as the origin."))
        return super(AccountMoveLine, self).unlink()
