# -*- coding: utf-8 -*-
# Part of EBITS TechCon

from datetime import datetime, timedelta
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import odoo.addons.decimal_precision as dp
# from odoo.tools import amount_to_text_en
#from odoo.addons.res_currency import Currency
#from odoo. import amount_to_text
from odoo.addons.base.models.res_currency import Currency
import time
import locale

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    @api.depends('state', 'order_line.invoice_status')
    def _get_invoiced(self):
        """
        Compute the invoice status of a SO. Possible statuses:
        - no: if the SO is not in status 'sale' or 'done', we consider that there is nothing to
          invoice. This is also hte default value if the conditions of no other status is met.
        - to invoice: if any SO line is 'to invoice', the whole SO is 'to invoice'
        - invoiced: if all SO lines are invoiced, the SO is invoiced.
        - upselling: if all SO lines are invoiced or upselling, the status is upselling.

        The invoice_ids are obtained thanks to the invoice lines of the SO lines, and we also search
        for possible refunds created directly from existing invoices. This is necessary since such a
        refund is not directly linked to the SO.
        """
        for order in self:
            # replaced invoice_id with move_id
            invoice_ids = (order.order_line.mapped('invoice_lines').mapped('move_id').filtered
                           (lambda r: r.move_type in ['out_invoice', 'out_refund']))
            print(">>>>>>>>>>>>>>invoice_ids>>>>>>>>>>>",invoice_ids)
            # Search for invoices which have been 'cancelled' (filter_refund = 'modify' in
            # 'account.invoice.refund')
            # use like as origin may contains multiple references (e.g. 'SO01, SO02')
            # replaced origin with invoice_origin
            refunds = invoice_ids.search([('invoice_origin', 'like', order.name),
                                          ('warehouse_id', '=', order.warehouse_id.id)])
            # invoice_ids |= refunds.filtered(lambda r: order.name in [origin.strip() for origin in r.origin.split(',')])

            # Search for refunds as well
            # replaced account.invoice with account.move
            refund_ids = self.env['account.move'].browse()
            if invoice_ids:
                for inv in invoice_ids:
                    print(">>>>>>>>>>>>>>>>>>>>inv>>>>>>>>>>>>>>>>>>>>>>>>",inv)
                    refund_ids += refund_ids.search([('move_type', '=', 'out_refund'),
                                                     ('origin', '=', inv.number),
                                                     ('origin', '!=', False),
                                                     ('journal_id', '=', inv.journal_id.id)])

            line_invoice_status = [line.invoice_status for line in order.order_line]

            if order.state not in ('sale', 'done'):
                invoice_status = 'no'
            elif any(invoice_status == 'to invoice' for invoice_status in line_invoice_status):
                invoice_status = 'to invoice'
            elif all(invoice_status == 'invoiced' for invoice_status in line_invoice_status):
                invoice_status = 'invoiced'
            elif all(invoice_status in ['invoiced', 'upselling'] for invoice_status in line_invoice_status):
                invoice_status = 'upselling'
            else:
                invoice_status = 'no'

            order.update({
                'invoice_count': len(set(invoice_ids.ids + refund_ids.ids)),
                'invoice_ids': invoice_ids.ids + refund_ids.ids,
                'invoice_status': invoice_status
            })
            
    @api.depends('line_len', 'order_line.price_total', 'order_line.product_id')
    def _check_discount(self):
        category_obj = self.env['product.category']
        product_dict = {}
        discount = []
        for order in self:
            product_dict = {}
            for categ_line in order.order_line:
                parent_of_search = category_obj.search([('id', 'parent_of', categ_line.product_id.categ_id.id)])
                if parent_of_search:
                    if parent_of_search[0].id in product_dict:
                        product_dict[parent_of_search[0].id] += categ_line.product_uom_qty
                    else:
                        product_dict[parent_of_search[0].id] = categ_line.product_uom_qty
            for each_prod in product_dict:
                category_bro = category_obj.browse(each_prod)
                for each_discount in category_bro.discount_lines:
                    if each_discount.min_qty <= product_dict[each_prod] and each_discount.max_qty >= product_dict[each_prod] and each_discount.date_from <= time.strftime(DEFAULT_SERVER_DATE_FORMAT) and each_discount.date_to >= time.strftime(DEFAULT_SERVER_DATE_FORMAT):
                        discount.append('available')
                        break
            if 'available' in discount:
                order.update({'discount_available': 'available'})
            else:
                order.update({'discount_available': 'not_available'})



    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = total = round_total = round_off = 0.0
            amount_actual_value = amount_discounted_value = amount_total_signed = amount_total_company_signed = 0.00
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                # FORWARDPORT UP TO 10.0
                if order.company_id.tax_calculation_rounding_method == 'round_globally':
                    price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                    taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_id)
                    amount_tax += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                else:
                    amount_tax += line.price_tax
            amount_discounted_value = sum(line.price_subtotal for line in order.order_line)
            amount_actual_value = sum((line.price_unit * line.product_uom_qty) for line in order.order_line)
            #print("????????????????????????????", order.pricelist_id.currency_id)
            #total = order.pricelist_id.currency_id.round(amount_untaxed) + order.pricelist_id.currency_id.round(amount_tax)

            for currency in order.pricelist_id.currency_id:
                total = currency.round(amount_untaxed) + currency.round(amount_tax)
                round_total = round(total)
                round_off = round_total - total
                amount_total_signed = round_total
                amount_total_company_signed = round_total
                if order.currency_id and order.company_id and order.currency_id != order.company_id.currency_id:
                    currency_id = order.currency_id.with_context(date=order.date_order)
                    amount_total_company_signed = currency_id._convert(round_total, order.company_id.currency_id)
                amount_total_company_signed = amount_total_company_signed * 1
                amount_total_signed = round_total * 1
                order.update({
                    'amount_untaxed': currency.round(amount_untaxed),
                    'amount_tax': currency.round(amount_tax),
                    'amount_total': round_total,
                    'amount_roundoff': round_off,
                    'amount_discounted': amount_actual_value - amount_discounted_value,
                    'amount_total_company_signed': amount_total_company_signed,
                    'amount_total_signed': amount_total_signed,
                })
            
    #@api.one
    # @api.depends('amount_total', 'amount_total_company_signed', 'currency_id', 'company_id')
    # def _get_amount_words(self):
    #     amount_in_words = ""
    #     amount_in_words_local = ""
    #     if self.amount_total and self.currency_id:
    #         amount_in_words = Currency.amount_to_text(self.amount_total, 'en', self.currency_id.name, self.currency_id.subcurrency)
    #     self.amount_to_text = amount_in_words
    #     if self.company_id.currency_id != self.currency_id:
    #         if self.amount_total_company_signed and self.company_id.currency_id:
    #             amount_in_words_local = Currency.amount_to_text(self.amount_total_company_signed, 'en', self.company_id.currency_id.name, self.company_id.currency_id.subcurrency)
    #     self.amount_to_text_local_currency = amount_in_words_local

    @api.depends('amount_total', 'amount_total_company_signed', 'currency_id', 'company_id')
    def _get_amount_words(self):
        for po in self:
            amount_in_words = ""
            amount_in_words_local = ""
            if po.amount_total and po.currency_id:
                amount_in_words = str(po.currency_id.amount_to_text(po.amount_total))
            po.amount_to_text = amount_in_words

            if po.company_id.currency_id != po.currency_id:
                if po.amount_total_company_signed and po.company_id.currency_id:
                    amount_in_words_local = str(po.currency_id.amount_to_text(po.amount_total))
            po.amount_to_text_local_currency = amount_in_words_local


    #@api.one
    @api.depends('order_line.sales_user_id')
    def _get_line_salesman(self):
        salesman_list = []
        salesman_text = ""
        for line in self.order_line:
            if line.sales_user_id:
                salesman_list.append(line.sales_user_id.name)
        if salesman_list:
            salesman_list = list(set(salesman_list))
            salesman_text = str(salesman_list).replace("[", "").replace("u'", "").replace("]", "").replace("'", "")
        self.salesman_name = salesman_text
        
    #@api.one
    @api.depends('order_line')
    def _get_line_length(self):
        self.line_len = len(self.order_line)
        
    #@api.one
    @api.depends('order_line.product_uom', 'order_line.product_uom_qty')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.order_line:
            if line.product_uom.id in qty_dict:
                qty_dict[line.product_uom.id]['product_uom_qty'] += line.product_uom_qty
            else:
                qty_dict[line.product_uom.id] = {
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_uom and line.product_uom.name or '' 
                    }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
        self.total_quantity_based_uom = qty_string
    
    #added in V17 as no default found
    confirmation_date = fields.Datetime(string='Confirmation Date', copy=False, readonly=True)
    name = fields.Char(string='Order Reference', required=True, copy=False, index=True, default='Order #')

    # removed states={'draft': [('readonly', False)]}
    sales_manager_id = fields.Many2one('res.users', string='Sales Manager', copy=False, readonly=True,
                                       )
    user_id = fields.Many2one('res.users', string='Created User', index=True, tracking=True,
                              default=lambda self: self.env.user)
    state = fields.Selection(selection_add=[
        ('waiting', 'Waiting For Approval'),
        ('waiting_higher', 'Waiting For Higher Authority Approval'),
        ('sale',),
        ('done', 'Approved'),
    ])
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True, required=True,
                                  copy=False)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', copy=False)
    credit_limit = fields.Float(string='Initial Credit Limit', readonly=True, copy=False, help="Initial Credit Limit in Customer Master", digits='Product Price')
    avail_credit_limit = fields.Float(string='Availabile Credit Limit', readonly=True, copy=False, help="Availabile Credit Limit = Initial Credit Limit - (Total Invoiced Due amount) - (Total Confirmed Sales Amount Yet To Be Invoiced)", digits='Product Price')
    invoice_due = fields.Float(string='Balance Due', readonly=True, copy=False, help="Invoice Balance Due", digits='Product Price')
    approved_so_value = fields.Float(string='Approved SO Value', readonly=True, copy=False, help="Approved So Value", digits='Product Price')
    credit_limit_invisible = fields.Float(string='Credit Limit(Dup)', copy=False, digits='Product Price')
    avail_credit_limit_invisible = fields.Float(string='Availabile Credit Limit(Dup)', copy=False, digits='Product Price')
    invoice_due_invisible = fields.Float(string='Balance Due(Dup)', copy=False, digits='Product Price')
    approved_so_value_invisible = fields.Float(string='Approved SO Value(Dup)', copy=False, digits='Product Price')
    sale_revision_no = fields.Integer(string='Revision', copy=False, readonly=True)
    revision_reason = fields.Text('Revision Reason', copy=False, readonly=True)
    revision_user_id = fields.Many2one('res.users', string='Revision User', copy=False, readonly=True)
    sale_amendment_no = fields.Integer(string='Amendment', copy=False, readonly=True)
    amendment_reason = fields.Text('Amendment Reason', copy=False, readonly=True)
    amendment_user_id = fields.Many2one('res.users', string='Amendment User', copy=False, readonly=True)
    cancel_reason = fields.Text('Cancel Reason', copy=False, readonly=True)
    higher_reason = fields.Text('Higher Approval Requested Reason', copy=False, readonly=True)
    cancel_user_id = fields.Many2one('res.users', string='Cancelled User', copy=False, readonly=True)
    sale_history = fields.Text('History', copy=False, readonly=True)
    approved_user_id = fields.Many2one('res.users', string='Approved User', copy=False, readonly=True)
    approved_date = fields.Datetime(string='Approved Date', copy=False, readonly=True)
    exp_delivery_date = fields.Date(string='Expected Delivery Date', copy=False, readonly=True,
                                    )
    credit_limit_check = fields.Selection([
        ('achieved', 'Achieved'),
        ('not_achieved', 'Not Achieved'),
        ('none', 'Not Required'),
        ], string='Credit Limit Check', readonly=True, copy=False)
    payment_term_check = fields.Selection([
        ('achieved', 'Achieved'),
        ('not_achieved', 'Not Achieved'),
        ('none', 'Not Required'),
        ], string='Payment Terms Check', readonly=True, copy=False)
    split_sale_id = fields.Many2one('sale.order', string='Base Sale Order', copy=False, readonly=True)
    discount_available = fields.Selection([('available', 'Applicable'), ('not_available', 'Not Applicable')], compute='_check_discount', string="Global Discount Applicability", store=True, readonly=True, tracking=True)
    amount_to_text = fields.Char(compute='_get_amount_words', string="In Words")
    amount_to_text_local_currency = fields.Char(compute='_get_amount_words', string="In Words(Local)")
    amount_discounted = fields.Monetary(string='Discounted Amount', store=True, readonly=True, compute='_amount_all', tracking=True)

    # removed , states={'cancel': [('readonly', True)], 'sale': [('readonly', True)],'done': [('readonly', True)]}
    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines', copy=True)

    # removed , states={'cancel': [('readonly', True)], 'sale': [('readonly', True)],'done': [('readonly', True)]}
    despatch_through = fields.Char('Despatch Through', copy=False)

    # removed states={'cancel': [('readonly', True)], 'sale': [('readonly', True)],'done': [('readonly', True)]},
    destination = fields.Char('Despatched', copy=False, )

    #removed states={'cancel': [('readonly', True)], 'sale': [('readonly', True)]
    partner_invoice_id = fields.Many2one('res.partner', string='Billing Address', readonly=True, required=True,help="Invoice address for current sales order.")

    # removed states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}
    # removed required=True,readonly=True,default=False
    warehouse_id = fields.Many2one('stock.warehouse', string='Delivery Warehouse', required=False)

    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all', tracking=True)
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all', tracking=True)
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', tracking=True)
    amount_roundoff = fields.Monetary(string='Round Off', store=True, readonly=True, compute='_amount_all', tracking=True)
    amount_total_signed = fields.Monetary(string='Total in Sale Currency', currency_field='currency_id', tracking=True,
        store=True, readonly=True, compute='_amount_all',
        help="Total amount in the currency of the sale, negative for credit notes.")
    amount_total_company_signed = fields.Monetary(string='Total in Company Currency', currency_field='company_currency_id',
        store=True, readonly=True, compute='_amount_all', tracking=True,
        help="Total amount in the currency of the company, negative for credit notes.")
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency", readonly=True)
    salesman_name = fields.Char(compute='_get_line_salesman', string="Salesperson")

    # removed states={'cancel': [('readonly', True)], 'sale': [('readonly', True)],'done': [('readonly', True)]}
    sale_remarks = fields.Text(string="Remarks", copy=False)

    # removed states={'cancel': [('readonly', True)], 'sale': [('readonly', True)],'done': [('readonly', True)]}
    internal_remarks = fields.Text(string="Internal Remarks", copy=False, )

    line_len = fields.Integer(string="Lines Length", compute='_get_line_length')
    cash_sale = fields.Boolean(string='Cash Sales', default=False,
                           help="Check this box if this customer is a cash sale customer.", copy=False)
    # removed , states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}
    billing_info = fields.Text(string="Billing Info", copy=False, readonly=True)

    # removed states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}
    shipping_info = fields.Text(string="Shipping Info", copy=False, readonly=True)

    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Ordered Qty')

    def _can_be_confirmed(self):
        result = super(SaleOrder, self)._can_be_confirmed()

        self.ensure_one()
        print(">>>>>>>>>result>>>>>>>>>>>", self.state)
        # return self.state in {'draft', 'sent'}

        result = self.state in {'draft', 'sent','waiting','waiting_higher'}
        return result


    def action_draft(self):
        result = super(SaleOrder, self).action_draft()

        self.ensure_one()
        print(">>>>>>>>>result>>>>>>>>>>>", self.state)
        # return self.state in {'draft', 'sent'}

        # result = self.state in {'draft', 'sent','waiting','waiting_higher'}

        result = self.filtered(lambda s: s.state in ['cancel', 'sent','sale'])
        return result


    # @api.model
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals.update({'name': 'Order #'})
        result = super(SaleOrder, self).create(vals_list)
        # if any(f not in vals for f in ['credit_limit', 'avail_credit_limit', 'invoice_due', 'approved_so_value']):
        #     result.credit_limit = vals['credit_limit_invisible']
        #     result.avail_credit_limit = vals['avail_credit_limit_invisible']
        #     result.invoice_due = vals['invoice_due_invisible']
        #     result.approved_so_value = vals['approved_so_value_invisible']
        return result

    #@api.multi
    def write(self, values):
        payment_term_check = 'achieved'
        residual = 0.00
        amount_total = 0.00
        result = super(SaleOrder, self).write(values)
        all_partners_children = {}
        all_partner_ids = []
        all_partners_children[self.partner_id.id] = self.env['res.partner'].search([('id', 'child_of', self.partner_id.id)]).ids
        all_partner_ids += all_partners_children[self.partner_id.id]
        if self.partner_id.transaction_currency_id:
            if self.partner_id.transaction_currency_id != self.env.user.company_id.currency_id:
                residual = self.partner_id.credit_transaction
            else:
                residual = self.partner_id.credit 
        else:
            residual = self.partner_id.credit
        if 'invoice_due_invisible' in values:
            for each_inv in self.env['account.move'].sudo().search_read([('state', '=', 'open'),
                                                                         ('partner_id', 'in', all_partner_ids),
                                                                         ('move_type', 'in', ('out_invoice', 'out_refund'))],['move_type' ,'amount_residual_signed', 'id']):
                for line in self.env['account.move'].sudo().browse(each_inv['id']).move_id.line_ids:
                    if line.account_id.internal_type == 'receivable':
                        if fields.Date.context_today(self) > line.date_maturity:
                            payment_term_check = 'not_achieved'
            self.payment_term_check = payment_term_check
        if 'approved_so_value_invisible' in values:
            for each_sale in self.env['sale.order'].sudo().search([('invoice_status', '!=', 'invoiced'),('state', 'in', ('sale', 'done')),('partner_id', 'in', all_partner_ids)]):
                sale_line = False
                for each_sale_line in each_sale.order_line:
                    if each_sale_line.invoice_status != 'invoiced':
                        qty_consider, amount_total_per_unit, do_cancel_qty, product_uom_qty = 0.00, 0.00, 0.00, 0.00
                        #for move in each_sale_line.sudo().procurement_ids.mapped('move_ids').filtered(lambda r: r.state == 'cancel'):
                        # for move in each_sale_line.sudo().procurement_ids.mapped('move_ids'):
                        for move in each_sale_line.sudo().mapped('move_ids'):
                            if move.location_dest_id.usage == "customer":
                                if move.state == 'cancel':
                                    do_cancel_qty += move.product_uom._compute_quantity(move.product_uom_qty, each_sale_line.product_uom)
                                else:
                                    product_uom_qty += move.product_uom._compute_quantity(move.product_uom_qty, each_sale_line.product_uom)
                        qty_consider = product_uom_qty - each_sale_line.qty_invoiced - do_cancel_qty
                        amount_total_per_unit = product_uom_qty and (each_sale_line.price_total / product_uom_qty) or 0
                        if qty_consider:
                            amount_total += (amount_total_per_unit * qty_consider)
                            sale_line = True
                if sale_line and each_sale.amount_roundoff:
                    amount_total += each_sale.amount_roundoff
            self.approved_so_value = amount_total
        if 'avail_credit_limit_invisible' in values:
            self.avail_credit_limit = ((self.partner_id.credit_limit and self.partner_id.credit_limit or 0.00) - residual - amount_total)
        if 'credit_limit_invisible' in values:
            if self.credit_limit != self.partner_id.credit_limit:
                self.credit_limit = self.partner_id.credit_limit and self.partner_id.credit_limit or 0.00
        return result
        
        
    #@api.multi
    def action_apply_global_discount(self):
        category_obj = self.env['product.category']
        product_dict = {}
        for order in self:
            product_dict = {}
            if order.discount_available == 'available':
                for categ_line in order.order_line:
                    parent_of_search = category_obj.search([('id', 'parent_of', categ_line.product_id.categ_id.id)])
                    if parent_of_search:
                        if parent_of_search[0].id in product_dict:
                            product_dict[parent_of_search[0].id] += categ_line.product_uom_qty
                        else:
                            product_dict[parent_of_search[0].id] = categ_line.product_uom_qty
                for each_prod in product_dict:
                    category_bro = category_obj.browse(each_prod)
                    for each_discount in category_bro.discount_lines:
                        if each_discount.min_qty <= product_dict[each_prod] and each_discount.max_qty >= product_dict[each_prod] and each_discount.date_from <= time.strftime(DEFAULT_SERVER_DATE_FORMAT) and each_discount.date_to >= time.strftime(DEFAULT_SERVER_DATE_FORMAT):
                            for line in order.order_line:     
                                product_parent_of_search = category_obj.search([('id', 'parent_of', line.product_id.categ_id.id)])
                                if each_prod in product_parent_of_search.ids:
                                    line.discount = each_discount.discount
                            break
        return True
        
    #@api.multi
    def action_check_credit_limit(self):
        residual = 0.00
        amount_total = 0.00
        avail_credit_limit = 0.00
        payment_term_check = 'achieved'
        all_partners_children = {}
        all_partner_ids = []
        for each in self:
            all_partners_children = {}
            all_partner_ids = []
            all_partners_children[each.partner_id.id] = self.env['res.partner'].search([('id', 'child_of', each.partner_id.id)]).ids
            all_partner_ids += all_partners_children[each.partner_id.id]
            if each.partner_id.transaction_currency_id:
                if each.partner_id.transaction_currency_id != self.env.user.company_id.currency_id:
                    residual = each.partner_id.credit_transaction
                else:
                    residual = each.partner_id.credit 
            else:
                residual = each.partner_id.credit
            for each_inv in self.env['account.move'].sudo().search_read([('state', '=', 'open'),('partner_id', 'in', all_partner_ids),('move_type', 'in', ('out_invoice', 'out_refund'))],['move_type', 'amount_residual_signed', 'id']):
                for line in self.env['account.move'].sudo().browse(each_inv['id']).move_id.line_ids:
                    if line.account_id.internal_type == 'receivable':
                        if fields.Date.context_today(self) > line.date_maturity:
                            payment_term_check = 'not_achieved'
            for each_sale in self.env['sale.order'].sudo().search([('invoice_status', '!=', 'invoiced'),('state', 'in', ('sale', 'done')),('partner_id', 'in', all_partner_ids)]):
                sale_line = False
                for each_sale_line in each_sale.order_line:
                    if each_sale_line.invoice_status != 'invoiced':
                        qty_consider, amount_total_per_unit, do_cancel_qty, product_uom_qty = 0.00, 0.00, 0.00, 0.00
                        #for move in each_sale_line.sudo().procurement_ids.mapped('move_ids').filtered(lambda r: r.state == 'cancel'):
                        # for move in each_sale_line.sudo().procurement_ids.mapped('move_ids'):
                        for move in each_sale_line.sudo().mapped('move_ids'):
                            if move.location_dest_id.usage == "customer":
                                if move.state == 'cancel':
                                    do_cancel_qty += move.product_uom._compute_quantity(move.product_uom_qty, each_sale_line.product_uom)
                                else:
                                    product_uom_qty += move.product_uom._compute_quantity(move.product_uom_qty, each_sale_line.product_uom)
                        qty_consider = product_uom_qty - each_sale_line.qty_invoiced - do_cancel_qty
                        amount_total_per_unit = product_uom_qty and (each_sale_line.price_total / product_uom_qty) or 0
                        if qty_consider:
                            amount_total += (amount_total_per_unit * qty_consider)
                            sale_line = True
                if sale_line and each_sale.amount_roundoff:
                    amount_total += each_sale.amount_roundoff
            avail_credit_limit = ((each.partner_id.credit_limit and each.partner_id.credit_limit or 0.00) - residual - amount_total)
            each.write({
                    'credit_limit': each.partner_id.credit_limit and each.partner_id.credit_limit or 0.00,
                    'avail_credit_limit': avail_credit_limit, 
                    'approved_so_value': amount_total,
                    'invoice_due': residual,
                    'credit_limit_check': 'achieved',
                    'payment_term_check': payment_term_check 
                    })
            if each.partner_id.credit_applicable == 'no':
                each.write({'credit_limit_check': 'none'})
            else:
                if avail_credit_limit >= each.amount_total:
                    each.write({'credit_limit_check': 'achieved'})
                else:
                    each.write({'credit_limit_check': 'not_achieved'})
        return True
            
    
    #@api.multi
    def action_send_for_approval(self):
        sale_history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            if each.sale_history:
                sale_history = '\n' + each.sale_history
            if not each.order_line:
                raise UserError(_('Kindly fill the products and move forward'))
            #commented due to in stock module
            if each.name == 'Order #':
                if each.warehouse_id.sale_sequence_id:
                    each.write({'name': each.warehouse_id.sale_sequence_id.next_by_id()})
                else:
                    raise UserError(_('Sale Sequence not defined in warehouse (%s)') % (each.warehouse_id.name))
            each.action_check_credit_limit()
            each.write({'state': 'waiting', 
                'sale_history': "Requested for approval by " + self.env.user.name + " on " + date + sale_history})
        return True
            
    #@api.multi
    def action_send_for_higher_approval(self):
        for each in self:
            each.write({'state': 'waiting_higher'})
        return True
        
    #@api.multi
    def action_send_revise(self):
        sale_revision_no = 0
        for each in self:
            sale_revision_no = each.sale_revision_no + 1
            each.write({'state': 'draft', 'sale_revision_no': sale_revision_no})
        return True
        
    # @api.onchange('discount_available')
    # def onchange_order_line_discount(self):
    #     for order in self:
    #         #order.order_line._compute_discount_line()
    #         order.button_dummy()
            

    @api.onchange('currency_id')
    def onchange_currency_id(self):
        if self.currency_id and self.partner_id:
            if self.currency_id != self.partner_id.transaction_currency_id:
                title = ("Currency Warning")
                message = "You cannot change the transaction currency of customer, which is already mapped in customer master"
                warning = {
                    'title': title,
                    'message': message,
                    }
                self.update({
                    'currency_id': self.partner_id.transaction_currency_id and self.partner_id.transaction_currency_id.id or False,
                    })
                return {'warning': warning}
                
#    @api.onchange('payment_term_id')
#    def onchange_payment_term_id(self):
#        if self.payment_term_id and self.partner_id:
#            if self.payment_term_id != self.partner_id.property_payment_term_id:
#                title = ("Payment Term Warning")
#                message = "You cannot change the payment term of customer, Which is already mapped in customer master"
#                warning = {
#                    'title': title,
#                    'message': message,
#                    }
#                self.update({
#                    'payment_term_id': self.partner_id.property_payment_term_id and self.partner_id.property_payment_term_id.id or False,
#                    })
#                return {'warning': warning}
                
    @api.onchange('pricelist_id')
    def onchange_pricelist_id(self):
        if self.pricelist_id and self.partner_id:
            if self.pricelist_id != self.partner_id.property_product_pricelist:
                title = ("Pricelist Warning")
                message = "You cannot change the pricelist of customer, Which is already mapped in customer master"
                warning = {
                    'title': title,
                    'message': message,
                    }
                self.update({
                    'pricelist_id': self.partner_id.property_product_pricelist and self.partner_id.property_product_pricelist.id or False,
                    })
                return {'warning': warning}
                
    @api.onchange('exp_delivery_date', 'date_order')
    def onchange_exp_delivery_date(self):
        if self.exp_delivery_date and self.date_order:
            print(">>>>>>>>>>>>>>>>>>>>>self.date_order>>>>>>>>>>>>>"
                  ">>>>>>>>>>>",self.date_order, self.exp_delivery_date, type(self.date_order), type(self.exp_delivery_date))
            date = self.date_order
            exp_delivery_date = self.exp_delivery_date
            # date_order = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
            date_order = datetime.strftime(date, '%Y-%m-%d')
            date_exp_delivery_date = datetime.strftime(exp_delivery_date, '%Y-%m-%d')
            if date_order > date_exp_delivery_date:
                title = ("Expected Date Warning")
                message = "Expected delivery date must be greater than or equal to the order date"
                warning = {
                    'title': title,
                    'message': message,
                    }
                self.update({
                    'exp_delivery_date': False,
                    })
                return {'warning': warning}
                
                
    #@api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        residual = 0.00
        amount_total = 0.00
        avail_credit_limit = 0.00
        payment_term_check = 'achieved'
        if not self.partner_id:
            self.update({
                'partner_invoice_id': False,
                'partner_shipping_id': False,
                'payment_term_id': False,
                'fiscal_position_id': False,
                'currency_id': False,
                'pricelist_id': False,
                'credit_limit': 0.00,
                'avail_credit_limit': 0.00,
                'approved_so_value': 0.00,
                'invoice_due': 0.00,
                'credit_limit_invisible': 0.00,
                'avail_credit_limit_invisible': 0.00,
                'approved_so_value_invisible': 0.00,
                'invoice_due_invisible': 0.00,
                'credit_limit_check': '',
                'payment_term_check': '',
                'warehouse_id': False,
                'cash_sale': False,
                'billing_info': '',
                'shipping_info': ''
                })
            return

        addr = self.partner_id.address_get(['delivery', 'invoice'])
        all_partners_children = {}
        all_partner_ids = []
        all_partners_children[self.partner_id.id] = self.env['res.partner'].search([('id', 'child_of', self.partner_id.id)]).ids
        all_partner_ids += all_partners_children[self.partner_id.id]
        
        values = {
            'payment_term_id': self.partner_id.property_payment_term_id and self.partner_id.property_payment_term_id.id or False,
            'partner_invoice_id': addr['invoice'],
            'partner_shipping_id': addr['delivery'],
            'currency_id': self.partner_id.transaction_currency_id and self.partner_id.transaction_currency_id.id or False,
            'warehouse_id': self.partner_id.delivery_warehouse_id and self.partner_id.delivery_warehouse_id.id or False,
            'credit_limit_check': '',
            'payment_term_check': '',
            'cash_sale': self.partner_id.cash_sale and self.partner_id.cash_sale or False,
            }
        if self.partner_id.transaction_currency_id:
            if self.partner_id.transaction_currency_id != self.env.user.company_id.currency_id:
                residual = self.partner_id.credit_transaction
            else:
                residual = self.partner_id.credit 
        else:
            residual = self.partner_id.credit
            # account.invoice replaced with account.move, type replaced with move_type ,
            # residual_signed replaced with amount_residual_signed, sale_note replaced with invoice_terms
        for each_inv in self.env['account.move'].sudo().search_read([
            ('state', '=', 'open'),('partner_id', 'in', all_partner_ids),
            ('move_type', 'in', ('out_invoice', 'out_refund'))],['move_type', 'amount_residual_signed', 'id']):
            for line in self.env['account.move'].sudo().browse(each_inv['id']).move_id.line_ids:
                if line.account_id.internal_type == 'receivable':
                    if fields.Date.context_today(self) > line.date_maturity:
                        payment_term_check = 'not_achieved'
        for each_sale in self.env['sale.order'].sudo().search([('invoice_status', '!=', 'invoiced'),('state', 'in', ('sale', 'done')),('partner_id', 'in', all_partner_ids)]):
            sale_line = False
            for each_sale_line in each_sale.order_line:
                if each_sale_line.invoice_status != 'invoiced':
                    qty_consider, amount_total_per_unit, do_cancel_qty, product_uom_qty = 0.00, 0.00, 0.00, 0.00
                    #for move in each_sale_line.sudo().procurement_ids.mapped('move_ids').filtered(lambda r: r.state == 'cancel'):
                    # for move in each_sale_line.sudo().procurement_ids.mapped('move_ids'):
                    for move in each_sale_line.sudo().mapped('move_ids'):
                        if move.location_dest_id.usage == "customer":
                            if move.state == 'cancel':
                                do_cancel_qty += move.product_uom._compute_quantity(move.product_uom_qty, each_sale_line.product_uom)
                            else:
                                product_uom_qty += move.product_uom._compute_quantity(move.product_uom_qty, each_sale_line.product_uom)
                    qty_consider = product_uom_qty - each_sale_line.qty_invoiced - do_cancel_qty
                    amount_total_per_unit = product_uom_qty and (each_sale_line.price_total / product_uom_qty) or 0
                    if qty_consider:
                        amount_total += (amount_total_per_unit * qty_consider)
                        sale_line = True
            if sale_line and each_sale.amount_roundoff:
                amount_total += each_sale.amount_roundoff
        avail_credit_limit = ((self.partner_id.credit_limit and self.partner_id.credit_limit or 0.00) - residual - amount_total)
        
        values['credit_limit'] = self.partner_id.credit_limit and self.partner_id.credit_limit or 0.00
        values['avail_credit_limit'] = avail_credit_limit
        values['approved_so_value'] = amount_total
        values['invoice_due'] = residual
        values['credit_limit_invisible'] = self.partner_id.credit_limit and self.partner_id.credit_limit or 0.00
        values['avail_credit_limit_invisible'] = avail_credit_limit
        values['approved_so_value_invisible'] = amount_total
        values['invoice_due_invisible'] = residual
        values['payment_term_check'] = payment_term_check
                            
        if self.partner_id.property_product_pricelist:
            if self.partner_id.transaction_currency_id == self.partner_id.property_product_pricelist.currency_id:
                values['pricelist_id'] = self.partner_id.property_product_pricelist.id
            else:
                values['pricelist_id'] = False
        if self.env.user.company_id.invoice_terms:
            values['note'] = self.with_context(lang=self.partner_id.lang).env.user.company_id.invoice_terms
        if self.partner_id.team_id:
            values['team_id'] = self.partner_id.team_id.id
        if self.partner_id.sales_manager_id:
            values['sales_manager_id'] = self.partner_id.sales_manager_id.id
        self.update(values)
        
    
    #@api.multi
    def action_confirm(self):
        residual = 0.00
        amount_total = 0.00
        avail_credit_limit = 0.00
        payment_term_check = 'achieved'
        sale_history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            if each.sale_history:
                sale_history = '\n' + each.sale_history
            each.action_check_credit_limit()
            all_partners_children = {}
            all_partner_ids = []
            all_partners_children[self.partner_id.id] = self.env['res.partner'].search([('id', 'child_of', self.partner_id.id)]).ids
            all_partner_ids += all_partners_children[self.partner_id.id]
            if each.partner_id.transaction_currency_id:
                if each.partner_id.transaction_currency_id != self.env.user.company_id.currency_id:
                    residual = each.partner_id.credit_transaction
                else:
                    residual = each.partner_id.credit
            else:
                residual = each.partner_id.credit
            for each_inv in self.env['account.move'].sudo().search_read([('state', '=', 'open'),('partner_id', 'in', all_partner_ids),('move_type', 'in', ('out_invoice', 'out_refund'))],['move_type' ,'amount_residual_signed', 'id']):
                for line in self.env['account.move'].sudo().browse(each_inv['id']).move_id.line_ids:
                    if line.account_id.internal_type == 'receivable':
                        if fields.Date.context_today(self) > line.date_maturity:
                            payment_term_check = 'not_achieved'
            for each_sale in self.env['sale.order'].sudo().search([('invoice_status', '!=', 'invoiced'),('state', 'in', ('sale', 'done')),('partner_id', 'in', all_partner_ids)]):
                sale_line = False
                for each_sale_line in each_sale.order_line:
                    if each_sale_line.invoice_status != 'invoiced':
                        qty_consider, amount_total_per_unit, do_cancel_qty, product_uom_qty = 0.00, 0.00, 0.00, 0.00
                        #for move in each_sale_line.sudo().procurement_ids.mapped('move_ids').filtered(lambda r: r.state == 'cancel'):
                        # for move in each_sale_line.sudo().procurement_ids.mapped('move_ids'):
                        for move in each_sale_line.sudo().mapped('move_ids'):
                            if move.location_dest_id.usage == "customer":
                                if move.state == 'cancel':
                                    do_cancel_qty += move.product_uom._compute_quantity(move.product_uom_qty, each_sale_line.product_uom)
                                else:
                                    product_uom_qty += move.product_uom._compute_quantity(move.product_uom_qty, each_sale_line.product_uom)
                        qty_consider = product_uom_qty - each_sale_line.qty_invoiced - do_cancel_qty
                        amount_total_per_unit = product_uom_qty and (each_sale_line.price_total / product_uom_qty) or 0
                        if qty_consider:
                            amount_total += (amount_total_per_unit * qty_consider)
                            sale_line = True
                if sale_line and each_sale.amount_roundoff:
                    amount_total += each_sale.amount_roundoff
            avail_credit_limit = ((each.partner_id.credit_limit and each.partner_id.credit_limit or 0.00) - residual - amount_total)
            if each.partner_id.credit_applicable == 'yes':
                if avail_credit_limit < each.amount_total:
                    if not self.user_has_groups('ebits_custom_sale.group_sale_higher_approval'):
                        raise_amount_total = raise_avail_credit_limit = 0.00
                        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
                        raise_amount_total = locale.format_string("%.2f", each.amount_total, grouping=True)
                        raise_avail_credit_limit = locale.format_string("%.2f", avail_credit_limit, grouping=True)
                        raise UserError(_('Sale total (%s) is greater than the customer available credit limit (%s) \n Kindly send to higher authority or split the order or contact administrator') % (raise_amount_total, raise_avail_credit_limit))
            each.write({'approved_user_id': self.env.user.id,
                        'approved_date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                        'sale_history': "Order has been approved by " + self.env.user.name + " on " + date + sale_history})

        res = super(SaleOrder, self).action_confirm()
        self.state ="done" #STATE DONE (APPROVED) WHEN ORDER CONFIRM -HARDIK
        for m_id in self.picking_ids.move_ids:
            for line in self.order_line:
                if m_id.product_id == line.product_id:
                    m_id.price_unit = line.price_unit
        return res


    #report in rml
    #@api.multi
    # def print_quotation(self):
    #     if self.cash_sale:
    #         return self.env['report'].get_action(self, 'sale.order.cash.rml.report')
    #     return self.env['report'].get_action(self, 'sale.order.rml.report')

    def print_quotation(self):
        self.ensure_one()

        if self.cash_sale:
            report_name = 'ebits_custom_sale.sale_order_report_cash'
        else:
            report_name = 'ebits_custom_sale.sale_order_report'

        report = self.env.ref(report_name, raise_if_not_found=False)

        if report:
            return report.report_action(self)
        else:
            return False
        
    #@api.multi
    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        if not self.warehouse_id.sale_journal_id:
            raise UserError(_('Kindly define sales journal in following warehouse/branch %s or contact administrator') % (self.warehouse_id.name))
        invoice_vals.update({
            'warehouse_id': self.warehouse_id and self.warehouse_id.id or False,
            'currency_id': self.currency_id and self.currency_id.id or False,
            'sale_order_id': self.id,
            'from_sale_order': True,
            'despatch_through': self.despatch_through and self.despatch_through or '',
            'destination': self.destination and self.destination or '',
            'sales_manager_id': self.sales_manager_id and self.sales_manager_id.id or False,
            'journal_id': self.warehouse_id.sale_journal_id.id,
            'cash_sale': self.cash_sale and self.cash_sale or False,
            'billing_info': self.billing_info and self.billing_info or '',
            'shipping_info': self.shipping_info and self.shipping_info or '',
            })
        return invoice_vals
        
    #@api.multi
    def action_open_partner_invoice(self):
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        for each in self:
            if each.partner_id:
                action['domain'] = [('partner_id', '=', each.partner_id.id),('state','=', 'open')]
            else:
                action = {'type': 'ir.actions.act_window_close'}
        return action
        
    #@api.multi
    def action_open_partner_approved_sale(self):
        action = self.env.ref('sale.action_orders_to_invoice').read()[0]
        for each in self:
            if each.partner_id:
                action['domain'] = [('partner_id', '=', each.partner_id.id),('state','in', ['sale', 'done']),('invoice_status', '!=', 'invoiced')]
            else:
                action = {'type': 'ir.actions.act_window_close'}
        return action
        
    #@api.multi
    def get_picking_ids_date(self):
        date = False
        dates = []
        for each in self.picking_ids:
            dates.append(each.date)
        if dates:
            date = max(dates)
            date = datetime.strptime(date,"%Y-%m-%d %H:%M:%S")
            date = date.strftime("%d-%m-%Y %H:%M:%S")
        return date
        
    #@api.multi
    def get_picking_ids_name(self):
        name = ""
        for each in self.picking_ids:
            if name:
                name += ", "
            name += each.name
        return name
        
    @api.model
    def _prepare_procurement_group(self):
        res = super(SaleOrder, self)._prepare_procurement_group()
        res.update({
            'approved_date': self.approved_date and self.approved_date or False,
            'cash_sale': self.cash_sale and self.cash_sale or False,
            'billing_info': self.billing_info and self.billing_info or '',
            'shipping_info': self.shipping_info and self.shipping_info or '',
            })
        return res
        
class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    
    state = fields.Selection(related='order_id.state', string='Order Status', readonly=True, copy=False, store=True)
    salesman_id = fields.Many2one(related='order_id.user_id', store=True, string='Created User', readonly=True)
    # removed required=True
    sales_user_id = fields.Many2one('res.users', string='Salesperson', index=True, copy=False)
    warehouse_id = fields.Many2one(related='order_id.warehouse_id', store=True, string='Warehouse', readonly=True)
    sales_manager_id = fields.Many2one(related='order_id.sales_manager_id', store=True, string='Sales Manager', readonly=True)
    team_id = fields.Many2one(related='order_id.team_id', store=True, string='Sales Team', readonly=True)
    customer_lead = fields.Float(
        'Delivery Lead Time', required=False, default=0.0,
        help="Number of days between the order confirmation and the shipping of the products to the customer")

    #commented as sale order line dont have this method
    #@api.multi
    # @api.onchange('product_id')
    # def product_id_change(self):
    #     result = {}
    #     if not self.product_id:
    #         return {'domain': {'product_uom': []}}
    #     vals = {}
    #
    #     domain = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
    #
    #     if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
    #         vals['product_uom'] = self.product_id.uom_id
    #         vals['product_uom_qty'] = 1.0
    #
    #     product = self.product_id.with_context(
    #         lang=self.order_id.partner_id.lang,
    #         partner=self.order_id.partner_id.id,
    #         quantity=vals.get('product_uom_qty') or self.product_uom_qty,
    #         date=self.order_id.date_order,
    #         pricelist=self.order_id.pricelist_id.id,
    #         uom=self.product_uom.id
    #     )
    #     # removed parameters as not in v17 or self.product_uom_qty, self.order_id.partner_id
    #     # price = self.order_id.pricelist_id._price_get(self.product_id.id, vals.get('product_uom_qty'))
    #
    #     # price = self.order_id.pricelist_id._price_get(self.product_id,self.product_uom_qty)
    #     # # price = self.order_id.pricelist_id._price_get(product, quantity)
    #     # print(">>>>>>>>>>>price>>>>>>>>>>>>>>>>>>>>>>",price)
    #     #
    #     # if price:
    #     #     if (self.order_id.pricelist_id.id in price) and price[self.order_id.pricelist_id.id] is False:
    #     #         warning = {
    #     #                 'title': _('Warning'),
    #     #                 'message': _("""Selected product "%s" not configured in customer pricelist "%s".\nKindly contact your administrator!!!.""") % (product.name_get()[0][1], self.order_id.pricelist_id.name)}
    #     #         self.product_id = False
    #     #         return {'warning': warning}
    #
    #     result = super(SaleOrderLine, self).product_id_change()
    #     return result
    
    @api.onchange('product_id')
    def onchange_product_id_to_sales_users_id(self):
        if self.order_id.partner_id:
            self.sales_user_id = self.order_id.partner_id.user_id and self.order_id.partner_id.user_id.id or False
            
    @api.onchange('product_uom', 'product_uom_qty')
    def _onchange_uom_id(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id and self.product_uom:
            product_uom = self.product_id.uom_id
            if self.product_uom.id != product_uom.id:
                self.product_uom = product_uom.id
                warning = {
                        'title': _('Warning'),
                        'message': _('Unit of Measure cannot be changed.')}
                return {'warning': warning}
        if self.product_uom_qty and (not self.product_uom.allow_decimal_digits):
            integer, decimal = divmod(self.product_uom_qty, 1)
            if decimal:
                self.product_uom_qty = 0.00
                warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the quantity should not contains decimal value') % (self.product_uom.name)}
                return {'warning': warning}
        return {'warning': warning}
        
    @api.onchange('product_uom_qty', 'product_uom', 'route_id')
    def _onchange_product_id_check_availability(self):
        if not self.product_id or not self.product_uom_qty or not self.product_uom:
            # replaced due to product_packaging converted to product_packaging_id
            # self.product_packaging = False
            self.product_packaging_id = False
            return {}
#        if self.product_id.type == 'product':
#            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
#            product_qty = self.product_uom._compute_quantity(self.product_uom_qty, self.product_id.uom_id)
#            if float_compare(self.product_id.virtual_available, product_qty, precision_digits=precision) == -1:
#                is_available = self._check_routing()
#                if not is_available:
#                    warning_mess = {
#                        'title': _('Not enough inventory!'),
#                        'message' : _('You plan to sell %s %s but you only have %s %s available!\nThe stock on hand is %s %s.') % \
#                            (self.product_uom_qty, self.product_uom.name, self.product_id.virtual_available, self.product_id.uom_id.name, self.product_id.qty_available, self.product_id.uom_id.name)
#                    }
#                    return {'warning': warning_mess}
        return {}
        
    #@api.multi
    def _prepare_order_line_procurement(self, group_id=False):
        self.ensure_one()
        exp_delivery_date = False
        res = super(SaleOrderLine, self)._prepare_order_line_procurement(group_id)
        if self.order_id.exp_delivery_date:
            exp_delivery_date = datetime.strptime(self.order_id.exp_delivery_date, "%Y-%m-%d")
            exp_delivery_date = datetime.strftime(exp_delivery_date, "%Y-%m-%d")
        else:
            exp_delivery_date = datetime.strptime(self.order_id.date_order, "%Y-%m-%d %H:%M:%S")
            exp_delivery_date = datetime.strftime(exp_delivery_date, "%Y-%m-%d") 
        exp_delivery_date = datetime.strptime(exp_delivery_date +" 18:29:00","%Y-%m-%d %H:%M:%S")
        exp_delivery_date = datetime.strftime(exp_delivery_date,"%Y-%m-%d %H:%M:%S")
        res.update({
            'approved_date': self.order_id.approved_date and self.order_id.approved_date or False,
            'date_planned': exp_delivery_date and exp_delivery_date or False
            })
        return res
            
    #@api.multi
    def _prepare_order_line_pack_product_procurement(self, pack=False, group_id=False):
#        date_planned = datetime.strptime(self.order_id.date_order, DEFAULT_SERVER_DATETIME_FORMAT)\
#            + timedelta(days=self.customer_lead or 0.0) - timedelta(days=self.order_id.company_id.security_lead)
        exp_delivery_date = False
        if self.order_id.exp_delivery_date:
            exp_delivery_date = datetime.strptime(self.order_id.exp_delivery_date, "%Y-%m-%d")
            exp_delivery_date = datetime.strftime(exp_delivery_date,"%Y-%m-%d")
        else:
            exp_delivery_date = datetime.strptime(self.order_id.date_order, "%Y-%m-%d %H:%M:%S")
            exp_delivery_date = datetime.strftime(exp_delivery_date, "%Y-%m-%d") 
        exp_delivery_date = datetime.strptime(exp_delivery_date +" 18:29:00", "%Y-%m-%d %H:%M:%S")
        exp_delivery_date = datetime.strftime(exp_delivery_date, "%Y-%m-%d %H:%M:%S")
        return {
            'name': pack.product_pack_id.name,
            'origin': self.order_id.name,
            'date_planned': exp_delivery_date and exp_delivery_date or False,
            'product_id': pack.product_pack_id.id,
            'product_qty': (pack.product_qty * self.product_uom_qty),
            'product_uom': pack.uom_id.id,
            'company_id': self.order_id.company_id.id,
            'group_id': group_id,
            'location_id': self.order_id.partner_shipping_id.property_stock_customer.id,
            'route_ids': self.route_id and [(4, self.route_id.id)] or [],
            'warehouse_id': self.order_id.warehouse_id and self.order_id.warehouse_id.id or False,
            'partner_dest_id': self.order_id.partner_shipping_id.id,
            'approved_date': self.order_id.approved_date and self.order_id.approved_date or False,
        }
        
    #@api.multi
    def _action_procurement_create(self):
        """
        Create procurements based on quantity ordered. If the quantity is increased, new
        procurements are created. If the quantity is decreased, no automated action is taken.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        new_procs = self.env['procurement.order']  # Empty recordset
        for line in self:
            if line.state != 'sale' or not line.product_id._need_procurement():
                continue
            qty = 0.0
            for proc in line.procurement_ids:
                qty += proc.product_qty
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) >= 0:
                continue

            if not line.order_id.procurement_group_id:
                vals = line.order_id._prepare_procurement_group()
                line.order_id.procurement_group_id = self.env["procurement.group"].create(vals)

            vals = line._prepare_order_line_procurement(group_id=line.order_id.procurement_group_id.id)
            vals['product_qty'] = line.product_uom_qty - qty
            new_proc = self.env["procurement.order"].create(vals)
            new_proc.message_post_with_view('mail.message_origin_link',
                values={'self': new_proc, 'origin': line.order_id},
                subtype_id=self.env.ref('mail.mt_note').id)
            new_procs += new_proc
            if line.product_id.package_available:
                for each_pack in line.product_id.package_product_lines:
                    pack_vals = line._prepare_order_line_pack_product_procurement(each_pack, group_id=line.order_id.procurement_group_id.id)
                    pack_new_proc = self.env["procurement.order"].create(pack_vals)
                    pack_new_proc.message_post_with_view('mail.message_origin_link',
                        values={'self': new_proc, 'origin': line.order_id},
                        subtype_id=self.env.ref('mail.mt_note').id)
                    new_procs += pack_new_proc
        new_procs.run()
#        orders = list(set(x.order_id for x in self))
#        for order in orders:
#            reassign = order.picking_ids.filtered(lambda x: x.state=='confirmed' or ((x.state in ['partially_available', 'waiting']) and not x.printed))
#            if reassign:
#                reassign.do_unreserve()
#                reassign.action_assign()
        return new_procs
        
    #@api.multi
    def _prepare_invoice_line(self,**optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
        res.update({
            'sales_user_id': self.sales_user_id and self.sales_user_id.id or False,
            'sale_order_line_id': self.id,
            'from_sale_order': True,
            })
        return res
        
#    @api.model
#    def _prepare_procurement_group(self):
#        res = super(SaleOrderLine, self)._prepare_procurement_group()
#        res.update({
#            'approved_date': self.order_id.approved_date and self.order_id.approved_date or False,
#            })
#        return res
        
    @api.onchange('product_id', 'price_unit', 'product_uom', 'product_uom_qty', 'tax_id')
    def _onchange_discount(self):
        PricelistItem = self.env['product.pricelist.item']
        self.discount = 0.0
        context_partner = dict(self.env.context, partner_id=self.order_id.partner_id.id)
        pricelist_context = dict(context_partner, uom=self.product_uom.id, date=self.order_id.date_order)

        if not (self.product_id and self.product_uom and
                self.order_id.partner_id and self.order_id.pricelist_id and
                self.order_id.pricelist_id.discount_policy == 'without_discount' and
                self.env.user.has_group('sale.group_discount_per_so_line')):
            if self.order_id.pricelist_id and self.product_id:
                # price, rule_id = (self.order_id.pricelist_id.with_context(pricelist_context)._get_product_price_rule
                #                   (self.product_id, self.product_uom_qty or 1.0, self.order_id.partner_id))

                price, rule_id = (self.order_id.pricelist_id.with_context(pricelist_context)._get_product_price_rule
                                  (self.product_id,self.product_uom_qty or 1.0))

                if rule_id:
                    pricelist_item = PricelistItem.browse(rule_id)
                    if pricelist_item.compute_price == 'percentage':
                        self.discount = pricelist_item.percent_price
                    if pricelist_item.compute_price == 'formula':
                        self.discount = pricelist_item.price_discount
            return
        price, rule_id = (self.order_id.pricelist_id.with_context(pricelist_context)._get_product_price_rule
                          (self.product_id, self.product_uom_qty or 1.0, self.order_id.partner_id))
        new_list_price, currency_id = self.with_context(context_partner)._get_real_price_currency(self.product_id, rule_id, self.product_uom_qty, self.product_uom, self.order_id.pricelist_id.id)
        new_list_price = self.env['account.tax']._fix_tax_included_price(new_list_price, self.product_id.taxes_id, self.tax_id)

        if price != 0 and new_list_price != 0:
            if self.product_id.company_id and self.order_id.pricelist_id.currency_id != self.product_id.company_id.currency_id:
                # new_list_price is in company's currency while price in pricelist currency
                ctx = dict(context_partner, date=self.order_id.date_order)
                new_list_price = self.env['res.currency'].browse(currency_id).with_context(ctx).compute(new_list_price, self.order_id.pricelist_id.currency_id)
            discount = (new_list_price - price) / new_list_price * 100
            if discount > 0:
                self.discount = discount
        
    #@api.multi
    def _compute_discount_line(self):
        for line in self:
            line.write({'discount': 0.00})
            
class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'
    
    approved_date = fields.Datetime(string='Sale Order Approved Date')
    cash_sale = fields.Boolean(string='Cash Sales', default=False,
                           help="Check this box if this customer is a cash sale customer.", copy=False)
    billing_info = fields.Text(string="Billing Info", copy=False)
    shipping_info = fields.Text(string="Shipping Info", copy=False)

# #########################################removed when account model is integrated
# class AcoountMove(models.Model):
#     _inherit = "account.move"

#     warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True, copy=False)
#     despatch_through = fields.Char('Despatch Through')
#     sale_order_id = fields.Many2one('sale.order', string='Sale', readonly=True, copy=False)
#     from_sale_order = fields.Boolean('From Sale Order', readonly=True, default=False, copy=False)
#     destination = fields.Char('Destination', readonly=True, copy=False)
#     sales_manager_id = fields.Many2one('res.users', string='Sales Manager', readonly=True, copy=False)
#     cash_sale = fields.Boolean(string='Cash Sales', default=False,
#                                help="Check this box if this customer is a cash sale customer.", copy=False)
#     billing_info = fields.Text(string="Billing Info", copy=False, readonly=True,
#                                )
#     shipping_info = fields.Text(string="Shipping Info", copy=False, readonly=True,
#                                 )
#     number = fields.Char(store=True, readonly=True, copy=False)
#     origin = fields.Char(string='Source Document',
#                          help="Reference of the document that produced this invoice.")

# #########################################removed when account model is integrated

# class AccountMoveLine(models.Model):
#     _inherit = "account.move.line"

#     sales_user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange',
#                                     copy=False)

#     sale_order_line_id = fields.Many2one('sale.order.line', string='Sale Line', readonly=True, copy=False)

#     from_sale_order = fields.Boolean('From Sale Order', readonly=True, default=False, copy=False)



#     # warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True, copy=False)

# #########################################removed when stock model is integrated
# class Warehouse(models.Model):
#     _inherit = "stock.warehouse"

#     sale_sequence_id = fields.Many2one('ir.sequence', 'Sales Order Sequence')
#     sale_journal_id = fields.Many2one('account.journal', 'Sale Invoice Journal')

# #########################################removed when pos model is integrated
# class PosOrder(models.Model):
#     _inherit = "pos.order"

#     amount_untaxed_company_currency = fields.Monetary(string='Untaxed Amount in Company Currency',
#                                                       store=True, readonly=True)

    
