# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero
from odoo.tools import float_round
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp
# from odoo.tools import amount_to_text_in
from odoo.addons.base.models.res_currency import Currency
import time

from odoo.tools.populate import compute

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    branch_id = fields.Many2one('res.partner', string="Branch")
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse/Branch")

    # ***
    # close by vaidik
    # in default available
    # sequence_id = fields.Many2one('ir.sequence', string='Order Sequence', readonly=False,
    #     help="This sequence is automatically created by Odoo but you can change it "
    #     "to customize the reference numbers of your orders.", copy=False)
    # refund_sequence_id = fields.Many2one('ir.sequence', string='Refund Sequence',
    #     help="This sequence is automatically created by Odoo but you can change it "
    #     "to customize the reference numbers of your orders.", copy=False)
    
    # Methods to open the POS
    # ***

    #***
    #close by vaidik
    # @api.multi
    # def open_custom_ui(self):
    #     assert len(self.ids) == 1, "you can open only one session at a time"
    #     if not self.current_session_id:
    #         self.current_session_id = self.env['pos.session'].create({
    #             'user_id': self.env.uid,
    #             'config_id': self.id
    #         })
    #         if self.current_session_id.state == 'opened':
    #             return self._open_session(self.current_session_id.id)
    #         return self._open_session(self.current_session_id.id)
    #     return self._open_session(self.current_session_id.id)


    # @api.multi
    # def open_existing_session_cb_close_custom(self):
    #     assert len(self.ids) == 1, "you can open only one session at a time"
    #     if self.current_session_id.cash_control:
    #         self.current_session_id.action_pos_session_closing_control()
    #     return self.open_custom_ui()
    # ***
        
# class PosSession(models.Model):
#     _inherit = 'pos.session'

    # **
    # close by vaidik
    # def _confirm_orders(self):
    #     for session in self:
    #         company_id = session.config_id.journal_id.company_id.id
    #         orders = session.order_ids.filtered(lambda order: order.state == 'paid')
    #         journal_id = self.env['ir.config_parameter'].sudo().get_param(
    #             'pos.closing.journal_id_%s' % company_id, default=session.config_id.journal_id.id)
    #
    #         move = self.env['pos.order'].with_context(force_company=company_id)._create_account_move(session.start_at, session.name, int(journal_id), company_id)
    #         orders.with_context(force_company=company_id)._create_account_move_line(session, move)
    #         for order in session.order_ids.filtered(lambda o: o.state not in ['done', 'invoiced', 'cancel']):
    #             if order.state not in ('paid'):
    #                 raise UserError(_("You cannot confirm all orders of this session, because they have not the 'paid' status"))
    #             order.action_pos_order_done()
    #         reconcile_orders = session.order_ids.filtered(lambda order: order.state in ['invoiced', 'done'])
    #         reconcile_orders.sudo()._reconcile_payments()
    #     return True

    
    # @api.multi
    # def open_frontend_cb_custom(self):
    #     if not self.ids:
    #         return {}
    #     for session in self.filtered(lambda s: s.user_id.id != self.env.uid):
    #         raise UserError(_("You cannot use the session of another users. This session is owned by %s. "
    #                           "Please first close this one to use this point of sale.") % session.user_id.name)
    #     return {
    #         'name': _('Sale Order'),
    #         'view_type': 'form',
    #         'view_mode': 'form,tree',
    #         'res_model': 'pos.order',
    #         'view_id': False,
    #         'type': 'ir.actions.act_window',
    #         'context': {'session_id': self.ids[0], 'default_session_id': self.ids[0]},
    #     }
    # ***

    
        
class PosOrder(models.Model):
    _inherit = "pos.order"

    # close by vaidik
    # @api.one
    # @api.depends('lines')
    # def _get_line_length(self):
    #     self.line_len = len(self.lines)

    # **
    # close by vaidik
    # @api.depends('line_len', 'lines.price_subtotal', 'lines.product_id')
    # def _check_discount(self):
    #     category_obj = self.env['product.category']
    #     product_dict = {}
    #     discount = []
    #     for order in self:
    #         product_dict = {}
    #         for categ_line in order.lines:
    #             parent_of_search = category_obj.search([('id', 'parent_of', categ_line.product_id.categ_id.id)])
    #             if parent_of_search:
    #                 if parent_of_search[0].id in product_dict:
    #                     product_dict[parent_of_search[0].id] += categ_line.qty
    #                 else:
    #                     product_dict[parent_of_search[0].id] = categ_line.qty
    #         for each_prod in product_dict:
    #             category_bro = category_obj.browse(each_prod)
    #             for each_discount in category_bro.discount_lines:
    #                 if each_discount.min_qty <= product_dict[each_prod] and each_discount.max_qty >= product_dict[each_prod] and each_discount.date_from <= time.strftime(DEFAULT_SERVER_DATE_FORMAT) and each_discount.date_to >= time.strftime(DEFAULT_SERVER_DATE_FORMAT):
    #                     discount.append('available')
    #                     break
    #         if 'available' in discount:
    #             order.update({'discount_available': 'available'})
    #         else:
    #             order.update({'discount_available': 'not_available'})
    # **

# in all payment_ids	is replace by statement_ids--vaidik
    @api.depends('payment_ids', 'lines.price_subtotal_incl', 'lines.discount', 'pricelist_id', 'date_order')
    def _compute_amount_all(self):
        for order in self:
            total = round_total = round_off = 0.00
            total_excluded_discount = amount_total_company_currency = amount_untaxed_company_currency = amount_tax_company_currency = 0.00
            amount_discount_company_currency = amount_roundoff_company_currency = 0.00
            order.amount_untaxed = order.amount_paid = order.amount_return = order.amount_tax = order.amount_discount = 0.00
            currency = order.pricelist_id.currency_id
            order.amount_paid = sum(payment.amount for payment in order.payment_ids)
            order.amount_return = sum(payment.amount < 0 and payment.amount or 0 for payment in order.payment_ids)
            order.amount_tax = round(sum(order._amount_line_tax(line, order.fiscal_position_id) for line in order.lines),2)
            order.amount_untaxed = round(sum(line.price_subtotal for line in order.lines),2)
            total_excluded_discount = round(sum((line.price_unit * line.qty) for line in order.lines),2)
            total = (order.amount_tax + order.amount_untaxed)
            round_total = round(total)
            round_off = round_total - total
            order.amount_total = round_total
            order.amount_discount = total_excluded_discount - order.amount_untaxed
            order.amount_roundoff = round_off
            amount_total_company_currency = order.amount_total
            amount_untaxed_company_currency = order.amount_untaxed
            amount_tax_company_currency = order.amount_tax
            amount_discount_company_currency = order.amount_discount
            amount_roundoff_company_currency = order.amount_roundoff
            # currency_id_rate = Currency.rate
            #due  to  already in v 17
            # currency_id_value = Currency.rate and (1 / currency_id_rate) or 0.00
            if order.pricelist_id.currency_id and order.company_id and order.pricelist_id.currency_id != order.company_id.currency_id:
                currency_id = order.pricelist_id.currency_id.with_context(date=order.date_order)
                amount_total_company_currency = currency_id._convert(order.amount_total, order.company_id.currency_id)
                amount_untaxed_company_currency = currency_id._convert(order.amount_untaxed, order.company_id.currency_id)
                amount_tax_company_currency = currency_id._convert(order.amount_tax, order.company_id.currency_id)
                amount_discount_company_currency = currency_id._convert(order.amount_discount, order.company_id.currency_id)
                amount_roundoff_company_currency = currency_id._convert(order.amount_roundoff, order.company_id.currency_id)
                # currency_id_rate = Currency.rate
                # currency_id_value = Currency.rate and (1 / Currency.rate) or 0.00
            order.amount_total_company_currency = amount_total_company_currency
            order.amount_untaxed_company_currency = amount_untaxed_company_currency
            order.amount_tax_company_currency = amount_tax_company_currency
            order.amount_discount_company_currency = amount_discount_company_currency
            order.amount_roundoff_company_currency = amount_roundoff_company_currency
            # order.currency_id_rate = currency_id_rate
            # order.currency_id_value = round(currency_id_value, 3)

    # @api.one
    # for field calclulation oftotal_quantity_based_uom
    @api.depends('lines.qty', 'lines.product_id')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.lines:
            if line.product_id.uom_id.id in qty_dict:
                qty_dict[line.product_id.uom_id.id]['product_uom_qty'] += line.qty
            else:
                qty_dict[line.product_id.uom_id.id] = {
                    'product_uom_qty': line.qty,
                    'product_uom': line.product_id.uom_id and line.product_id.uom_id.name or ''
                }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        self.total_quantity_based_uom = qty_string

    # @api.one
    @api.depends('amount_total', 'lines.price_subtotal_incl', 'pricelist_id')
    def _get_amount_words(self):
        amount_in_words = ""
        amount_in_words_local = ""
        for order in self:
            amount_in_words = ""
            amount_in_words_local = ""
            if order.amount_total and order.pricelist_id.currency_id:
                amount_in_words = order.currency_id.amount_to_text(order.amount_total)
                # amount_in_words = Currency.amount_to_text(order.amount_total, 'en', order.pricelist_id.currency_id.symbol, order.pricelist_id.currency_id.subcurrency)
            order.amount_to_text = amount_in_words
            if order.company_id.currency_id != order.pricelist_id.currency_id:
                if order.amount_total_company_currency and order.company_id.currency_id:
                    amount_in_words_local = order.currency_id.amount_to_text(order.amount_total_company_currency)
                    # amount_in_words_local = Currency.amount_to_text(order.amount_total_company_currency, 'en', order.company_id.currency_id.symbol, order.company_id.currency_id.subcurrency)
            order.amount_to_text_local_currency = amount_in_words_local

    name = fields.Char(string='Invoice No', required=True, readonly=True, copy=False, default='/')
    date_order = fields.Datetime(string='Invoice Date', readonly=True, index=True, default=fields.Datetime.now)
    currency_id = fields.Many2one("res.currency", related='pricelist_id.currency_id', string="Currency", readonly=True)
    partner_name = fields.Char("Customer Name")
    partner_address = fields.Text("Customer Address", compute='_compute_partner_address' ,store=True)
    amount_tax = fields.Float(compute='_compute_amount_all', string='Taxes', digits=0)
    amount_total = fields.Float(compute='_compute_amount_all', string='Total', digits=0)
    # amount_paid = fields.Float(compute='_compute_amount_all', string='Paid', states={'draft': [('readonly', False)]}, readonly=True, digits=0)
    amount_paid = fields.Float(compute='_compute_amount_all', string='Paid', digits=0)
    amount_return = fields.Float(compute='_compute_amount_all', string='Returned', digits=0)
    amount_untaxed = fields.Float(compute='_compute_amount_all', string='Untaxed Amount', digits=0)
    amount_discount = fields.Float(compute='_compute_amount_all', string='Discounted Amount', digits=0)
    amount_roundoff = fields.Float(compute='_compute_amount_all', string='Round Off', digits=0)
    amount_total_company_currency = fields.Monetary(string='Total in Company Currency', currency_field='company_currency_id',
                                                    store=True, readonly=True, compute='_compute_amount_all')
    amount_untaxed_company_currency = fields.Monetary(string='Untaxed Amount in Company Currency', currency_field='company_currency_id',
                                                      store=True, readonly=True, compute='_compute_amount_all')
    amount_tax_company_currency = fields.Monetary(string='Tax Amount in Company Currency', currency_field='company_currency_id',
                                                  store=True, readonly=True, compute='_compute_amount_all')
    amount_discount_company_currency = fields.Monetary(string='Discounted Amount in Company Currency', currency_field='company_currency_id',
                                                       store=True, readonly=True, compute='_compute_amount_all')
    amount_roundoff_company_currency = fields.Monetary(string='Round Off Amount in Company Currency', currency_field='company_currency_id',
                                                       store=True, readonly=True, compute='_compute_amount_all')
    currency_id_rate = fields.Float(string='Currency Rate',  digits=(12, 9),
                                    store=True, readonly=True, compute='_compute_amount_all')
    currency_id_value = fields.Float(string='Currency Conversion Value',  digits=(12, 3),
                                     store=True, readonly=True, compute='_compute_amount_all')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency", readonly=True)
    amount_to_text = fields.Char(compute='_get_amount_words', string='In Words')
    amount_to_text_local_currency = fields.Char(compute='_get_amount_words', string='In Words(Local)')
    line_len = fields.Integer(string="Lines Length", compute='_get_line_length')
    discount_available = fields.Selection([('available', 'Applicable'), ('not_available', 'Not Applicable')],  string="Global Discount Applicability", store=True, readonly=True, track_visibility='always')
    # discount_available = fields.Selection([('available', 'Applicable'), ('not_available', 'Not Applicable')], compute='_check_discount', string="Global Discount Applicability", store=True, readonly=True, track_visibility='always')
    pos_refund = fields.Boolean(string="POS Refund", default=False)
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Quantity')
# vaidik
    # @api.model
    # def create(self, values):
    #     if values.get('session_id'):
    #         # set name based on the sequence specified on the config
    #         session = self.env['pos.session'].browse(values['session_id'])
    #         #if values.get('name') == '/':
    #         #    values['name'] = session.config_id.sequence_id._next()
    #         values.setdefault('pricelist_id', session.config_id.pricelist_id.id)
    #     #else:
    #     # fallback on any pos.order sequence
    #     #if values.get('name') == '/':
    #     #    values['name'] = self.env['ir.sequence'].next_by_code('pos.order')
    #     return super(PosOrder, self).create(values)
###
    @api.onchange('discount_available')
    def onchange_order_line_discount(self):
        print('------------onchange_order_line_discount-------------')
        if self.discount_available:
            #order.lines._compute_discount_line()
            self.button_compute_discount()

    # @api.multi
    def button_compute_discount(self):
        return True

    # @api.multi
    def action_apply_global_discount(self):
        print('action_apply_global_discount---------------------')
        category_obj = self.env['product.category']
        product_dict = {}
        for order in self:
            product_dict = {}
            if order.discount_available == 'available':
                for categ_line in order.lines:
                    parent_of_search = category_obj.search([('id', 'parent_of', categ_line.product_id.categ_id.id)])
                    if parent_of_search:
                        if parent_of_search[0].id in product_dict:
                            product_dict[parent_of_search[0].id] += categ_line.qty
                        else:
                            product_dict[parent_of_search[0].id] = categ_line.qty
                for each_prod in product_dict:
                    category_bro = category_obj.browse(each_prod)
                    for each_discount in category_bro.discount_lines:
                        if each_discount.min_qty <= product_dict[each_prod] and each_discount.max_qty >= product_dict[each_prod] and each_discount.date_from <= time.strftime(DEFAULT_SERVER_DATE_FORMAT) and each_discount.date_to >= time.strftime(DEFAULT_SERVER_DATE_FORMAT):
                            for line in order.lines:
                                product_parent_of_search = category_obj.search([('id', 'parent_of', line.product_id.categ_id.id)])
                                if each_prod in product_parent_of_search.ids:
                                    line.discount = each_discount.discount
                            break
        return True

# vaidik
    # def _prepare_invoice(self):
    #     res = super(PosOrder, self)._prepare_invoice()
    #     res['warehouse_id'] = self.session_id.config_id.picking_type_id.warehouse_id and self.session_id.config_id.picking_type_id.warehouse_id.id or False
    #     #        res['from_sale'] = True
    #     return res

    # @api.multi
    def _get_tax_amount_by_group(self):
        print("______--_get_tax_amount_by_group________call_")
        self.ensure_one()
        res = {}
        currency = self.pricelist_id.currency_id or self.company_id.currency_id
        for line in self.lines:
            print("---------line-------",line)
            base_tax = price_reduce = 0
            price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
            for tax in line.tax_ids:
                group = tax.tax_group_id
                res.setdefault(group, 0.0)
                amount = tax.compute_all(price_reduce + base_tax, quantity=line.qty)['taxes'][0]['amount']
                res[group] += amount
                if tax.include_base_amount:
                    base_tax += tax.compute_all(price_reduce + base_tax, quantity=1)['taxes'][0]['amount']
        res = sorted(res.items(), key=lambda l: l[0].sequence)
        res = map(lambda l: (l[0].name, l[1]), res)
        return res

    # @api.multi
    # vaidik
    # def print_pos_report(self):
    #     self.filtered(lambda s: s.state == 'draft').write({'state': 'sent'})
    #     return self.env['report'].get_action(self, 'pos.sale.rml.report')

    # @api.onchange('partner_id')
    @api.depends('partner_id')
    def _compute_partner_address(self):
        print("______--_onchange_partner_id________call_")
        address = ""
        if self.partner_id:
            print('---------------if partnerocnage call------------')
            self.pricelist_id = self.partner_id.property_product_pricelist.id
            self.partner_name = self.partner_id.name_get()[0][1]
            address = (self.partner_id.street and self.partner_id.street + ', ' or '') + (self.partner_id.street2 and self.partner_id.street2 + ',\n' or '') + (self.partner_id.city and self.partner_id.city + ', ' or '') + (self.partner_id.region_id and self.partner_id.region_id.name + ', ' or '') + (self.partner_id.area_id and self.partner_id.area_id.name + ',\n' or '') + (self.partner_id.country_id and self.partner_id.country_id.name + '.\n' or '') + (self.partner_id.zip and " PO Box - " + self.partner_id.zip + '.' or '')
            self.partner_address = address
        else:
            print('---------------if partnerocnage call------------')
            self.partner_name = ""
            self.partner_address = ""


    # def _create_account_move(self, dt, ref, journal_id, company_id):
    #     move = super(PosOrder, self)._create_account_move(dt, ref, journal_id, company_id)
    #     move.user_id = self.env.user.id
    #     return move

    # vaidik***

    # def _create_account_move_line(self, session=None, move=None):
    #     # Tricky, via the workflow, we only have one id in the ids variable
    #     """Create a account move line of order grouped by products or not."""
    #     IrProperty = self.env['ir.property']
    #     ResPartner = self.env['res.partner']
    #
    #     if session and not all(session.id == order.session_id.id for order in self):
    #         raise UserError(_('Selected orders do not have the same session!'))
    #
    #     grouped_data = {}
    #     have_to_group_by = session and session.config_id.group_by or False
    #
    #     for order in self.filtered(lambda o: not o.account_move or order.state == 'paid'):
    #         current_company = order.sale_journal.company_id
    #         account_def = IrProperty.get(
    #             'property_account_receivable_id', 'res.partner')
    #         order_account = order.partner_id.property_account_receivable_id.id or account_def and account_def.id
    #         partner_id = ResPartner._find_accounting_partner(order.partner_id).id or False
    #         if move is None:
    #             # Create an entry for the sale
    #             journal_id = self.env['ir.config_parameter'].sudo().get_param(
    #                 'pos.closing.journal_id_%s' % current_company.id, default=order.sale_journal.id)
    #             move = self._create_account_move(
    #                 order.session_id.start_at, order.name, int(journal_id), order.company_id.id)
    #
    #         def insert_data(data_type, values):
    #             # if have_to_group_by:
    #             values.update({
    #                 'partner_id': partner_id,
    #                 'move_id': move.id,
    #             })
    #
    #             if data_type == 'product':
    #                 key = ('product', values['partner_id'], (values['product_id'], tuple(values['tax_ids'][0][2]), values['name']), values['analytic_account_id'], values['debit'] > 0)
    #             elif data_type == 'tax':
    #                 key = ('tax', values['partner_id'], values['tax_line_id'], values['debit'] > 0)
    #             elif data_type == 'counter_part':
    #                 key = ('counter_part', values['partner_id'], values['account_id'], values['debit'] > 0)
    #             elif data_type == 'round_off':
    #                 key = ('counter_part', values['account_id'], values['debit'] > 0)
    #             else:
    #                 return
    #
    #             grouped_data.setdefault(key, [])
    #
    #             if have_to_group_by:
    #                 if not grouped_data[key]:
    #                     grouped_data[key].append(values)
    #                 else:
    #                     current_value = grouped_data[key][0]
    #                     current_value['quantity'] = current_value.get('quantity', 0.0) + values.get('quantity', 0.0)
    #                     current_value['credit'] = current_value.get('credit', 0.0) + values.get('credit', 0.0)
    #                     current_value['debit'] = current_value.get('debit', 0.0) + values.get('debit', 0.0)
    #             else:
    #                 grouped_data[key].append(values)
    #
    #         # because of the weird way the pos order is written, we need to make sure there is at least one line,
    #         # because just after the 'for' loop there are references to 'line' and 'income_account' variables (that
    #         # are set inside the for loop)
    #         # TOFIX: a deep refactoring of this method (and class!) is needed
    #         # in order to get rid of this stupid hack
    #         assert order.lines, _('The POS order must have lines when calling this method')
    #         # Create an move for each order line
    #         cur = order.pricelist_id.currency_id
    #         for line in order.lines:
    #             amount = line.price_subtotal
    #
    #             # Search for the income account
    #             if line.product_id.property_account_income_id.id:
    #                 income_account = line.product_id.property_account_income_id.id
    #             elif line.product_id.categ_id.property_account_income_categ_id.id:
    #                 income_account = line.product_id.categ_id.property_account_income_categ_id.id
    #             else:
    #                 raise UserError(_('Please define income '
    #                                   'account for this product: "%s" (id:%d).')
    #                                 % (line.product_id.name, line.product_id.id))
    #
    #             name = line.product_id.name
    #             if line.notice:
    #                 # add discount reason in move
    #                 name = name + ' (' + line.notice + ')'
    #
    #             # Create a move for the line for the order line
    #             insert_data('product', {
    #                 'name': name,
    #                 'quantity': line.qty,
    #                 'product_id': line.product_id.id,
    #                 'account_id': income_account,
    #                 'analytic_account_id': self._prepare_analytic_account(line),
    #                 'credit': ((amount > 0) and amount) or 0.0,
    #                 'debit': ((amount < 0) and -amount) or 0.0,
    #                 'tax_ids': [(6, 0, line.tax_ids_after_fiscal_position.ids)],
    #                 'partner_id': partner_id
    #             })
    #
    #             # Create the tax lines
    #             taxes = line.tax_ids_after_fiscal_position.filtered(lambda t: t.company_id.id == current_company.id)
    #             if not taxes:
    #                 continue
    #             for tax in taxes.compute_all(line.price_unit * (100.0 - line.discount) / 100.0, cur, line.qty)['taxes']:
    #                 insert_data('tax', {
    #                     'name': _('Tax') + ' ' + tax['name'],
    #                     'product_id': line.product_id.id,
    #                     'quantity': line.qty,
    #                     'account_id': tax['account_id'] or income_account,
    #                     'credit': ((tax['amount'] > 0) and tax['amount']) or 0.0,
    #                     'debit': ((tax['amount'] < 0) and -tax['amount']) or 0.0,
    #                     'tax_line_id': tax['id'],
    #                     'partner_id': partner_id
    #                 })
    #         if order.amount_roundoff:
    #             if not order.session_id.config_id.warehouse_id.round_off_account_id:
    #                 raise UserError(_('Kindly map the round off account in the warehouse master or \nContact your Administrator!!!'))
    #             #counterpart
    #             insert_data('round_off', {
    #                 'name': _("Round Off"),
    #                 'account_id': order.session_id.config_id.warehouse_id.round_off_account_id.id,
    #                 'credit': ((order.amount_roundoff > 0) and abs(order.amount_roundoff)) or 0.0,
    #                 'debit': ((order.amount_roundoff < 0) and abs(order.amount_roundoff)) or 0.0,
    #                 #'partner_id': partner_id
    #             })
    #         insert_data('counter_part', {
    #             'name': _("Trade Receivables"),  # order.name,
    #             'account_id': order_account,
    #             'credit': ((order.amount_total < 0) and -order.amount_total) or 0.0,
    #             'debit': ((order.amount_total > 0) and order.amount_total) or 0.0,
    #             'partner_id': partner_id
    #         })
    #
    #         order.write({'state': 'done', 'account_move': move.id})
    #
    #     all_lines = []
    #     for group_key, group_data in grouped_data.iteritems():
    #         for value in group_data:
    #             all_lines.append((0, 0, value),)
    #     if move:  # In case no order was changed
    #         move.sudo().write({'line_ids': all_lines})
    #         move.sudo().post()
    #     return True



    # @api.multi
    # def action_pos_order_paid(self):
    #     for order in self:
    #         if not order.test_paid():
    #             raise UserError(_("Order is not paid."))
    #         order.write({'state': 'paid'})
    #         order.create_picking()
    #     return True
# vaidik
#     def create_picking(self):
#         """Create a picking for each order and validate it."""
#         Picking = self.env['stock.picking']
#         Move = self.env['stock.move']
#         StockWarehouse = self.env['stock.warehouse']
#         for order in self:
#             if order.picking_id:
#                 raise UserError(_('Duplicate entries are creating.\n Please try again.'))
#             if not order.lines.filtered(lambda l: l.product_id.type in ['product', 'consu']):
#                 continue
#             address = order.partner_id.address_get(['delivery']) or {}
#             picking_type = order.picking_type_id
#             return_pick_type = order.picking_type_id.return_picking_type_id or order.picking_type_id
#             order_picking = Picking
#             return_picking = Picking
#             moves = Move
#             location_id = order.location_id.id
#             if order.partner_id:
#                 destination_id = order.partner_id.property_stock_customer.id
#             else:
#                 if (not picking_type) or (not picking_type.default_location_dest_id):
#                     customerloc, supplierloc = StockWarehouse._get_partner_locations()
#                     destination_id = customerloc.id
#                 else:
#                     destination_id = picking_type.default_location_dest_id.id
#
#             if picking_type:
#                 message = _(
#                     "This transfer has been created from the point of sale session: <a href=# data-oe-model=pos.order data-oe-id=%d>%s</a>") % (
#                           order.id, order.name)
#                 available_picking = Picking.search([('origin', '=', order.name)])
#                 if available_picking:
#                     raise UserError(
#                         _('Duplicate entries are creating.\n Please try again or check your internet connection.'))
#                 picking_vals = {
#                     'origin': order.name,
#                     'partner_id': address.get('delivery', False),
#                     'date_done': order.date_order,
#                     'picking_type_id': picking_type.id,
#                     'company_id': order.company_id.id,
#                     'move_type': 'direct',
#                     'note': order.note or "",
#                     'location_id': location_id,
#                     'location_dest_id': destination_id,
#                 }
#                 pos_qty = any([x.qty > 0 for x in order.lines if x.product_id.type in ['product', 'consu']])
#                 if pos_qty:
#                     order_picking = Picking.create(picking_vals.copy())
#                     order_picking.message_post(body=message)
#                 neg_qty = any([x.qty < 0 for x in order.lines if x.product_id.type in ['product', 'consu']])
#                 if neg_qty:
#                     return_vals = picking_vals.copy()
#                     return_vals.update({
#                         'location_id': destination_id,
#                         'location_dest_id': return_pick_type != picking_type and return_pick_type.default_location_dest_id.id or location_id,
#                         'picking_type_id': return_pick_type.id,
#                         'to_refund': True,
#                         'refund_sent_approval': True,
#                         'refund_approved': True
#                     })
#                     return_picking = Picking.create(return_vals)
#                     return_picking.message_post(body=message)
#
#             for line in order.lines.filtered(
#                     lambda l: l.product_id.type in ['product', 'consu'] and not float_is_zero(l.qty,
#                                                                                               precision_rounding=l.product_id.uom_id.rounding)):
#                 moves |= Move.create({
#                     'name': (line.product_id and line.product_id.name_get()[0][1] or "") + " / " + order.name,
#                     'product_uom': line.product_id.uom_id.id,
#                     'picking_id': order_picking.id if line.qty >= 0 else return_picking.id,
#                     'picking_type_id': picking_type.id if line.qty >= 0 else return_pick_type.id,
#                     'product_id': line.product_id.id,
#                     'product_uom_qty': abs(line.qty),
#                     'state': 'draft',
#                     'location_id': location_id if line.qty >= 0 else destination_id,
#                     'location_dest_id': destination_id if line.qty >= 0 else return_pick_type != picking_type and return_pick_type.default_location_dest_id.id or location_id,
#                 })
#             if order.picking_id:
#                 raise UserError(_('Duplicate entries are creating.\n Please try again.'))
#             # prefer associating the regular order picking, not the return
#             order.write({'picking_id': order_picking.id or return_picking.id})
#
#             if return_picking:
#                 order._force_picking_done(return_picking)
#             if order_picking:
#                 order._force_picking_done(order_picking)
#
#             # when the pos.config has no picking_type_id set only the moves will be created
#             if moves and not return_picking and not order_picking:
#                 tracked_moves = moves.filtered(lambda move: move.product_id.tracking != 'none')
#                 untracked_moves = moves - tracked_moves
#                 tracked_moves.action_confirm()
#                 untracked_moves.action_assign()
#                 moves.filtered(lambda m: m.state in ['confirmed', 'waiting']).force_assign()
#                 moves.filtered(lambda m: m.product_id.tracking == 'none').action_done()
#
#         return True
###
    #    def create_picking(self):
    #        """Create a picking for each order and validate it."""
    #        Picking = self.env['stock.picking']
    #        Move = self.env['stock.move']
    #        StockWarehouse = self.env['stock.warehouse']
    #        for order in self:
    #            address = order.partner_id.address_get(['delivery']) or {}
    #            picking_type = order.picking_type_id
    #            return_pick_type = order.picking_type_id.return_picking_type_id or order.picking_type_id
    #            order_picking = Picking
    #            return_picking = Picking
    #            moves = Move
    #            location_id = order.location_id.id
    #            if order.partner_id:
    #                destination_id = order.partner_id.property_stock_customer.id
    #            else:
    #                if (not picking_type) or (not picking_type.default_location_dest_id):
    #                    customerloc, supplierloc = StockWarehouse._get_partner_locations()
    #                    destination_id = customerloc.id
    #                else:
    #                    destination_id = picking_type.default_location_dest_id.id

    #            if picking_type:
    #                message = _("This transfer has been created from the point of sale session: <a href=# data-oe-model=pos.order data-oe-id=%d>%s</a>") % (order.id, order.name)
    #                picking_vals = {
    #                    'origin': order.name,
    #                    'partner_id': address.get('delivery', False),
    #                    'date_done': order.date_order,
    #                    'picking_type_id': picking_type.id,
    #                    'company_id': order.company_id.id,
    #                    'move_type': 'direct',
    #                    'note': order.note or "",
    #                    'location_id': location_id,
    #                    'location_dest_id': destination_id,
    #                }
    #                pos_qty = any([x.qty >= 0 for x in order.lines])
    #                if pos_qty:
    #                    order_picking = Picking.create(picking_vals.copy())
    #                    order_picking.message_post(body=message)
    #                neg_qty = any([x.qty < 0 for x in order.lines])
    #                if neg_qty:
    #                    return_vals = picking_vals.copy()
    #                    return_vals.update({
    #                        'location_id': destination_id,
    #                        'location_dest_id': return_pick_type != picking_type and return_pick_type.default_location_dest_id.id or location_id,
    #                        'picking_type_id': return_pick_type.id,
    #                        'to_refund': True,
    #                        'refund_sent_approval': True,
    #                        'refund_approved': True
    #                    })
    #                    return_picking = Picking.create(return_vals)
    #                    return_picking.message_post(body=message)

    #            for line in order.lines.filtered(lambda l: l.product_id.type in ['product', 'consu']):
    #                moves |= Move.create({
    #                    'name': (line.product_id and line.product_id.name_get()[0][1] or "") + " / " + order.name,
    #                    'product_uom': line.product_id.uom_id.id,
    #                    'picking_id': order_picking.id if line.qty >= 0 else return_picking.id,
    #                    'picking_type_id': picking_type.id if line.qty >= 0 else return_pick_type.id,
    #                    'product_id': line.product_id.id,
    #                    'product_uom_qty': abs(line.qty),
    #                    'state': 'draft',
    #                    'location_id': location_id if line.qty >= 0 else destination_id,
    #                    'location_dest_id': destination_id if line.qty >= 0 else return_pick_type != picking_type and return_pick_type.default_location_dest_id.id or location_id,
    #                })

    #            # prefer associating the regular order picking, not the return
    #            order.write({'picking_id': order_picking.id or return_picking.id})

    #            if return_picking:
    #                order._force_picking_done(return_picking)
    #            if order_picking:
    #                order._force_picking_done(order_picking)

    #            # when the pos.config has no picking_type_id set only the moves will be created
    #            if moves and not return_picking and not order_picking:
    #                moves.action_confirm()
    #                moves.force_assign()
    #                moves.filtered(lambda m: m.product_id.tracking == 'none').action_done()

    #        return True

# Vaidik
    # @api.multi
    # def _reconcile_payments(self):
    #     for order in self:
    #         aml = order.payment_ids.mapped('journal_entry_ids').mapped(
    #             'line_ids') | order.account_move.line_ids | \
    #               order.invoice_id.move_id.line_ids
    #         aml = aml.filtered(lambda r: not r.reconciled
    #                                      and not r.full_reconcile_id
    #                                      and r.account_id.internal_type == 'receivable'
    #                                      and r.partner_id == order.partner_id
    #                            .commercial_partner_id)
    #         try:
    #             aml.reconcile()
    #         except:
    #             # There might be unexpected situations where the automatic
    #             # reconciliation won't work. We don't want the user to be
    #             # blocked because of this, since the automatic reconciliation
    #             # is introduced for convenience, not for mandatory accounting
    #             # reasons.
    #             _logger.error('Reconciliation did not work for order %s',
    #                           order.name)
    #             continue

    # @api.multi
    # vaidik
    # def refund(self):
    #     """Create a copy of order  for refund order"""
    #     PosOrder = self.env['pos.order']
    #     current_session = self.env['pos.session'].search([('state', '!=', 'closed'), ('user_id', '=', self.env.uid)], limit=1)
    #     if not current_session:
    #         raise UserError(_('To return product(s), you need to open a session that will be used to register the refund.'))
    #     if not current_session.config_id.refund_sequence_id:
    #         raise UserError(_('To return product(s), you need to set a refund sequence in pos configuration.'))
    #     for order in self:
    #         pos_refund = True
    #         if order.pos_refund:
    #             pos_refund = False
    #         clone = order.copy({
    #             # ot used, name forced by create
    #             'name': "/",
    #             'session_id': current_session.id,
    #             'date_order': fields.Datetime.now(),
    #             'pos_reference': order.pos_reference,
    #             'note': "Refund of " + order.name,
    #             'pos_refund': pos_refund,
    #         })
    #         PosOrder += clone
    #
    #     for clone in PosOrder:
    #         for order_line in clone.lines:
    #             order_line.write({'qty': -order_line.qty})
    #     return {
    #         'name': _('Return Products'),
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_model': 'pos.order',
    #         'res_id': PosOrder.ids[0],
    #         'view_id': False,
    #         'context': self.env.context,
    #         'type': 'ir.actions.act_window',
    #         'target': 'current',
    #     }


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    tax_ids = fields.Many2many('account.tax', string='Taxes', readonly=False)
    price_subtotal = fields.Float(compute='_compute_amount_line_all', digits=0, string='Subtotal w/o Tax', store=True, copy=False)
    price_subtotal_incl = fields.Float(compute='_compute_amount_line_all', digits=0, string='Subtotal', store=True, copy=False)
    price_subtotal_company_currency = fields.Float(compute='_compute_amount_line_all', digits=0, string='Subtotal w/o Tax in Company Currency', store=True, copy=False)
    price_subtotal_incl_company_currency = fields.Float(compute='_compute_amount_line_all', digits=0, string='Subtotal in Company Currency', store=True, copy=False)

    @api.depends('price_unit', 'tax_ids', 'qty', 'discount', 'product_id')
    def _compute_amount_line_all(self):
        for line in self:
            price_subtotal_company_currency = price_subtotal_incl_company_currency = 0.00
            currency = line.order_id.pricelist_id.currency_id
            taxes = line.tax_ids.filtered(lambda tax: tax.company_id.id == line.order_id.company_id.id)
            fiscal_position_id = line.order_id.fiscal_position_id
            if fiscal_position_id:
                taxes = fiscal_position_id.map_tax(taxes, line.product_id, line.order_id.partner_id)
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.price_subtotal = line.price_subtotal_incl = price * line.qty
            price_subtotal_company_currency = price_subtotal_incl_company_currency = price * line.qty
            if taxes:
                taxes = taxes.compute_all(price, currency, line.qty, product=line.product_id, partner=line.order_id.partner_id or False)
                line.price_subtotal = taxes['total_excluded']
                line.price_subtotal_incl = taxes['total_included']

            #add round pre as 3 in round
            line.price_subtotal = round(line.price_subtotal,3)
            line.price_subtotal_incl = round(line.price_subtotal_incl,3)
            price_subtotal_company_currency = line.price_subtotal
            price_subtotal_incl_company_currency = line.price_subtotal_incl
            if currency and line.order_id.company_id and currency != line.order_id.company_id.currency_id:
                # price_subtotal_company_currency = Currency.with_context(self,date=line.order_id.date_order).compute(line.price_subtotal, line.order_id.company_id.currency_id)
                # price_subtotal_incl_company_currency = Currency.with_context(self,date=line.order_id.date_order).compute(line.price_subtotal_incl, line.order_id.company_id.currency_id)
                price_subtotal_company_currency = line.order_id.company_id.currency_id.with_context(
                    date=line.order_id.date_order)._convert(line.price_subtotal, line.order_id.currency_id)
                price_subtotal_incl_company_currency = line.order_id.company_id.currency_id.with_context(
                    date=line.order_id.date_order)._convert(line.price_subtotal_incl,
                                                            line.order_id.company_id.currency_id)
            line.price_subtotal_company_currency = price_subtotal_company_currency
            line.price_subtotal_incl_company_currency = price_subtotal_incl_company_currency

# vaidik
    # @api.multi
    # def _get_display_price(self, product):
    #     if self.order_id.pricelist_id.discount_policy == 'without_discount':
    #         from_currency = self.order_id.company_id.currency_id
    #         return from_currency.compute(product.lst_price, self.order_id.pricelist_id.currency_id)
    #     return product.with_context(pricelist=self.order_id.pricelist_id.id).price

    # vaidik

    # @api.multi
    # @api.onchange('product_id')
    # def _onchange_product_id(self):
    #     warning = {}
    #     quant_obj = self.env['stock.quant']
    #     if not self.product_id:
    #         return {'domain': {}}
    #     if self.qty and self.order_id and self.product_id:
    #         if self.product_id.type != 'service':
    #             qty_available = 0.00
    #             quant_search = quant_obj.search_read([('location_id','=', self.order_id.location_id.id),('product_id','=', self.product_id.id)],['qty'])
    #             for each_quant_qty in quant_search:
    #                 qty_available += each_quant_qty['qty']
    #             if qty_available < self.qty:
    #                 warning = {
    #                     'title': _('Warning'),
    #                     'message': _("Stock is not available for selected product '%s'!.") % (self.product_id.name,)}
    #                 self.product_id = False
    #                 return {'warning': warning}
    #     vals = {}
    #     product = self.product_id.with_context(
    #         lang=self.order_id.partner_id.lang,
    #         partner=self.order_id.partner_id.id,
    #         quantity=vals.get('qty') or self.qty,
    #         date=self.order_id.date_order,
    #         pricelist=self.order_id.pricelist_id.id,
    #         uom=self.product_id.uom_id.id
    #     )
    #     #if self.order_id.pricelist_id.discount_policy == 'with_discount':
    #     price = self.order_id.pricelist_id.price_get(self.product_id.id, vals.get('qty') or self.qty, self.order_id.partner_id)
    #     if price:
    #         if (self.order_id.pricelist_id.id in price) and price[self.order_id.pricelist_id.id] is False:
    #             #if not price[self.order_id.pricelist_id.id]:
    #             warning = {
    #                 'title': _('Warning'),
    #                 'message': _("""Selected product "%s" not configured in customer pricelist "%s".\nKindly contact your administrator!!!.""") % (product.name_get()[0][1], self.order_id.pricelist_id.name)}
    #             self.product_id = False
    #             return {'warning': warning}
    #
    #     name = product.name_get()[0][1]
    #
    #     if self.order_id.pricelist_id:
    #         self.price_unit = self.env['account.tax']._fix_tax_included_price(self._get_display_price(product), product.taxes_id, self.tax_ids)
    #     self.tax_ids = self.product_id.taxes_id
    #     self._onchange_qty()
    #
    #     title = False
    #     message = False
    #     warning = {}
    #     if product.sale_line_warn != 'no-message':
    #         title = _("Warning for %s") % product.name
    #         message = product.sale_line_warn_msg
    #         warning['title'] = title
    #         warning['message'] = message
    #         if product.sale_line_warn == 'block':
    #             self.product_id = False
    #         return {'warning': warning}
    #     return {'domain': {}}

# vaidik
    # @api.onchange('qty')
    # def product_uom_change(self):
    #     quant_obj = self.env['stock.quant']
    #     warning = {}
    #     integer, decimal, qty_available = 0.00, 0.00, 0.00
    #     if self.qty and self.order_id and self.product_id:
    #         if self.product_id.type != 'service':
    #             quant_search = quant_obj.search_read([('location_id','=', self.order_id.location_id.id),('product_id','=', self.product_id.id)],['qty'])
    #             for each_quant_qty in quant_search:
    #                 qty_available += each_quant_qty['qty']
    #             if qty_available < self.qty:
    #                 warning = {
    #                     'title': _('Warning'),
    #                     'message': _("Stock is available for the selected product '%s'. \n Available stock is %s") % (self.product_id.name, qty_available)}
    #                 self.product_id = False
    #                 self.qty = 1.00
    #                 return {'warning': warning}
    #     if self.qty and (not self.product_id.uom_id.allow_decimal_digits):
    #         integer, decimal = divmod(self.qty, 1)
    #         if decimal:
    #             self.qty = 0.00
    #             warning = {
    #                 'title': _('Warning'),
    #                 'message': _('You cannot enter the decimal value on the following uom %s. \nKindly make sure that the quantity should not contains decimal value') % (self.product_id.uom_id.name)}
    #         return {'warning': warning}
    #     if self.order_id.pricelist_id:
    #         product = self.product_id.with_context(
    #             lang=self.order_id.partner_id.lang,
    #             partner=self.order_id.partner_id.id,
    #             quantity=self.qty,
    #             date_order=self.order_id.date_order,
    #             pricelist=self.order_id.pricelist_id.id,
    #             uom=self.product_id.uom_id.id,
    #             fiscal_position=self.env.context.get('fiscal_position')
    #         )
    #         self.price_unit = self.env['account.tax']._fix_tax_included_price(self._get_display_price(product), product.taxes_id, self.tax_ids)
    #     return {'warning': warning}


    # def _get_real_price_currency(self, product, rule_id, qty, uom, pricelist_id):
    #     PricelistItem = self.env['product.pricelist.item']
    #     field_name = 'lst_price'
    #     currency_id = None
    #     if rule_id:
    #         pricelist_item = PricelistItem.browse(rule_id)
    #         if pricelist_item.base == 'standard_price':
    #             field_name = 'standard_price'
    #         currency_id = pricelist_item.pricelist_id.currency_id
    #
    #     product_currency = (product.company_id and product.company_id.currency_id) or self.env.user.company_id.currency_id
    #     if not currency_id:
    #         currency_id = product_currency
    #         cur_factor = 1.0
    #     else:
    #         if currency_id.id == product_currency.id:
    #             cur_factor = 1.0
    #         else:
    #             cur_factor = currency_id._get_conversion_rate(product_currency, currency_id)
    #
    #     product_uom = self.env.context.get('uom') or product.uom_id.id
    #     if uom and uom.id != product_uom:
    #         # the unit price is in a different uom
    #         uom_factor = uom._compute_price(1.0, product.uom_id)
    #     else:
    #         uom_factor = 1.0
    #     return product[field_name] * uom_factor * cur_factor, currency_id.id

    # @api.onchange('product_id', 'price_unit', 'qty', 'tax_ids', 'tax_ids_after_fiscal_position')
    # def _onchange_discount(self):
    #     PricelistItem = self.env['product.pricelist.item']
    #     self.discount = 0.0
    #     context_partner = dict(self.env.context, partner_id=self.order_id.partner_id.id)
    #     pricelist_context = dict(context_partner, uom=self.product_id.uom_id.id, date=self.order_id.date_order)
    #     if not (self.product_id and self.order_id.pricelist_id and
    #             self.order_id.pricelist_id.discount_policy == 'without_discount' and
    #             self.env.user.has_group('sale.group_discount_per_so_line')):
    #         if self.order_id.pricelist_id and self.product_id:
    #             price, rule_id = self.order_id.pricelist_id.with_context(pricelist_context).get_product_price_rule(self.product_id, self.qty or 1.0, self.order_id.partner_id)
    #             if rule_id:
    #                 pricelist_item = PricelistItem.browse(rule_id)
    #                 if pricelist_item.compute_price == 'percentage':
    #                     self.discount = pricelist_item.percent_price
    #                 if pricelist_item.compute_price == 'formula':
    #                     self.discount = pricelist_item.price_discount
    #         return
    #     price, rule_id = self.order_id.pricelist_id.with_context(pricelist_context).get_product_price_rule(self.product_id, self.qty or 1.0, self.order_id.partner_id)
    #     new_list_price, currency_id = self.with_context(context_partner)._get_real_price_currency(self.product_id, rule_id, self.qty, self.product_id.uom_id, self.order_id.pricelist_id.id)
    #     new_list_price = self.env['account.tax']._fix_tax_included_price(new_list_price, self.product_id.taxes_id, self.tax_ids)
    #     if price != 0 and new_list_price != 0:
    #         if self.product_id.company_id and self.order_id.pricelist_id.currency_id != self.product_id.company_id.currency_id:
    #             # new_list_price is in company's currency while price in pricelist currency
    #             ctx = dict(context_partner, date=self.order_id.date_order)
    #             new_list_price = self.env['res.currency'].browse(currency_id).with_context(ctx).compute(new_list_price, self.order_id.pricelist_id.currency_id)
    #         discount = (new_list_price - price) / new_list_price * 100
    #         if discount > 0:
    #             self.discount = discount

    # @api.multi
    # def _compute_discount_line(self):
    #     for line in self:
    #         line.write({'discount': 0.00})

            # currency_rate_value = Currency.rate.get_value()
