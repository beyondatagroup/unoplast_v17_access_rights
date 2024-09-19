# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import time
import math
import pytz
from datetime import datetime, timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo import api, fields, models, SUPERUSER_ID, _

from odoo.tools.float_utils import float_is_zero, float_compare
# from odoo.tools.misc import formatLang
# from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP
import odoo.addons.decimal_precision as dp


class PurchaseOrderApprovalHierarchy(models.Model):
    _name = "purchase.order.approval.hierarchy"
    _description = "Purchase Order Approval Hierarchy"

    name = fields.Char(string="Name", size=64, required=True)
    date = fields.Datetime(string="Created Date", default=fields.Datetime.now, readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Production Unit / Division / Branch', required=True)
    category_ids = fields.Many2many('purchase.category', 'hierarchy_purchase_category_rel', 'hierarchy_id',
                                    'category_id', string='Category Type', required=True)
    hierarchy_type = fields.Selection([('one', 'One Level Approval'), ('two', 'Two Level Approval')],
                                      string="Hierarchy Type", required=True)
    one_level_user_ids = fields.Many2many('res.users', 'hierarchy_one_res_users_rel', 'hierarchy_id', 'category_id',
                                          string="1st Approver")
    two_level_user_ids = fields.Many2many('res.users', 'hierarchy_two_res_users_rel', 'hierarchy_id', 'category_id',
                                          string="2nd Approver")


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # READONLY_STATES = {
    #     'to_2nd_approve': [('readonly', True)],
    #     'purchase': [('readonly', True)],
    #     'done': [('readonly', True)],
    #     'cancel': [('readonly', True)],
    # }

    @api.model
    def _default_warehouse_id(self):
        company = self.env.user.company_id.id
        warehouse_ids = self.env['stock.warehouse'].search([('company_id', '=', company)], limit=1)
        return warehouse_ids

    @api.model
    def _default_picking_type(self):
        type_obj = self.env['stock.picking.type']
        company_id = self.env.context.get('company_id') or self.env.user.company_id.id
        types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id.company_id', '=', company_id)])
        if not types:
            types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id', '=', False)])
        return types[:1]

    #    @api.one
    #    @api.depends('order_line.price_subtotal')
    #    def _compute_discount_amount(self):
    #        amount_discounted_value = sum(line.price_subtotal for line in self.order_line)
    #        amount_actual_value = sum((line.price_unit * line.product_qty) for line in self.order_line)
    #        self.amount_discounted = amount_actual_value - amount_discounted_value

    # @api.one
    @api.depends('order_line.price_subtotal', 'amount_total',  'company_id', 'date_order')
    def _compute_custom_amount(self):
        for rec in self:
            rec.amount_total_signed = rec.amount_total
            amount_total_company_signed = rec.amount_total
            print("\n\n.........._compute_custom_amount........")
            print("\n\n..........rec.currency_id........",rec.currency_id)
            print("\n\n..........rec.company_id........",rec.company_id)
            print("\n\n.........rec.company_id.currency_id....",rec.company_id.currency_id)
            if rec.currency_id and rec.company_id and rec.currency_id != rec.company_id.currency_id:
                print("\n............iffffffffffffffffffffffff")
                currency_id = rec.currency_id.with_context(date=rec.date_order)
                print("\n............currency_id",currency_id)
                amount_total_company_signed = currency_id._convert(rec.amount_total, rec.company_id.currency_id)
                print("\n\n............amount_total_company_signed.......",amount_total_company_signed)
            rec.amount_total_company_signed = amount_total_company_signed * 1
            rec.amount_total_signed = rec.amount_total * 1

    # @api.depends('amount_total', 'amount_total_company_signed', 'currency_id', 'company_id')
    @api.onchange('amount_total','currency_id','order_line','amount_total_company_signed','company_id')
    def _get_amount_words(self):
        print("\n\n.........._get_amount_words........")
        for po in self:
            amount_in_words = ""
            amount_in_words_local = ""
            if po.currency_id:
                if po.amount_total and po.currency_id:
                    print("\n..........11111111111111111")
                    amount_in_words = str(po.currency_id.amount_to_text(po.amount_total))
                    print("\n\n............amount_in_words",amount_in_words)
                po.amount_to_text = amount_in_words
                if po.company_id.currency_id != po.currency_id:
                    print("\n\n.......iffffffffffffffff.............",po.company_id.currency_id,po.currency_id)
                    if po.amount_total_company_signed and po.company_id.currency_id:
                        amount_in_words_local =  str(po.company_id.currency_id.amount_to_text(po.amount_total_company_signed))
                po.amount_to_text_local_currency = amount_in_words_local
            else:
                if po.currency_id:
                    raise UserError(
                        _('Purchase Order Currency not Selected'))




    # @api.one
    @api.depends('state', 'picking_ids','order_line.qty_received')
    def _get_grn_status(self):
        picking_state = []
        for order in self:
            for line in order.order_line:
                if line.product_qty <= line.qty_received:
                    picking_state.append('yes')
                else:
                    picking_state.append('no')
        if 'yes' in picking_state:
            if 'no' in picking_state:
                order.picking_state = "Partially Received"
            else:
                order.picking_state = "Fully Received"
        else:
            order.picking_state = "To be Received"

    @api.depends('order_line.date_planned')
    def _compute_date_planned(self):
        for order in self:
            min_date = False
            for line in order.order_line:
                if not min_date or line.date_planned < min_date:
                    min_date = line.date_planned
            print("\n\n........._compute_date_planned----------",min_date)
            if min_date:
                order.date_planned = min_date

    # @api.depends('order_line.qty_received', 'order_line.move_ids.state')
    def _get_invoiced(self):
        super(PurchaseOrder, self)._get_invoiced()
        for order in self:
            if order.state not in ('purchase', 'done'):
                order.invoice_status = 'no'
                continue
            if any(line.invoice_status == 'to invoice' for line in order.order_line):
                order.invoice_status = 'to invoice'
            elif all(line.invoice_status == 'invoiced' for line in order.order_line):
                order.invoice_status = 'invoiced'
            else:
                order.invoice_status = 'no'
    #
    @api.depends('order_line.invoice_lines.move_id.state')
    def _compute_invoice_refund(self):
        for order in self:
            # old invoices = self.env['account.invoice']
            invoices = self.env['account.move']

            for line in order.order_line:
                invoices |= line.invoice_lines.mapped('move_id').filtered(lambda x: x.move_type == 'in_refund')
            order.invoice_refund_count = len(invoices)
    #
    @api.depends('order_line.invoice_lines.move_id.state')
    def _compute_invoice(self):
        super(PurchaseOrder, self)._compute_invoice()
        for order in self:
            # old invoices = self.env['account.invoice']
            invoices = self.env['account.move']
            for line in order.order_line:
                invoices |= line.invoice_lines.mapped('move_id').filtered(lambda x: x.move_type == 'in_invoice')
            order.invoice_count = len(invoices)
    #
    # # @api.one
    @api.depends('order_line.product_uom', 'order_line.product_qty')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.order_line:
            if line.product_uom.id in qty_dict:
                qty_dict[line.product_uom.id]['product_uom_qty'] += line.product_qty
            else:
                qty_dict[line.product_uom.id] = {
                    'product_uom_qty': line.product_qty,
                    'product_uom': line.product_uom and line.product_uom.name or ''
                }
        for each in qty_dict:
            if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
                if qty_string:
                    qty_string += " , "
                qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (
                qty_dict[each]['product_uom'])
        self.total_quantity_based_uom = qty_string

    name = fields.Char('Order Reference', required=True, index=True, copy=False, default='New #')
    state = fields.Selection(selection_add=[
        ('to approve',),
        ('to_2nd_approve', 'Pending for 2nd Approval'),
    ])
    picking_state = fields.Char(string="GRN Status", compute="_get_grn_status", readonly=True, store=True)
    category_id = fields.Many2one('purchase.category', string='Category Type',
                                  copy=False)
    payment_term_id = fields.Many2one('account.payment.term', 'Payment Terms',  copy=False)
    # incoterm_id = fields.Many2one('stock.incoterms', 'Incoterm',  copy=False , help="International Commercial Terms are a series of predefined commercial terms used in international transactions.")
    depature_time = fields.Date(string='ETD', copy=False)
    arrival_time = fields.Date(string='ETA', copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse',
                                   copy=False)
    picking_type_id = fields.Many2one('stock.picking.type', 'Deliver To',  required=True,
                                      help="This will determine picking type of incoming shipment", copy=False)
    default_location_dest_id_usage = fields.Selection(related='picking_type_id.default_location_dest_id.usage',
                                                      string='Destination Location Type',
                                                      help="Technical field used to display the Drop Ship Address",
                                                      readonly=True)
    partner_ref = fields.Char('Vendor Reference', copy=False, \
                              help="Reference of the sales order or bid sent by the vendor. "
                                   "It's used to do the matching when you receive the "
                                   "products as this reference is usually written on the "
                                   "delivery order sent by your vendor.", )
    origin = fields.Char('Source Document', copy=False, \
                         help="Reference of the document that generated this purchase order "
                              "request (e.g. a sale order or an internal procurement request)", )
    date_order = fields.Datetime('Order Date', required=True,  index=True, copy=False,
                                 default=fields.Datetime.now, \
                                 help="Depicts the date where the Quotation should be validated and converted into a purchase order.")
    # date_approve = fields.Date('Approval Date', readonly=1, index=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Vendor', required=True, 
                                 change_default=True, tracking=True)
    dest_address_id = fields.Many2one('res.partner', string='Drop Ship Address',  \
                                      help="Put an address if you want to deliver directly from the vendor to the customer. " \
                                           "Otherwise, keep empty to deliver to your own company.")
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, )
    one_approver_ids = fields.Many2many('res.users', 'po_one_level_approver_rel', 'purchase_id', 'user_id',
                                        string='1st Approver', readonly=True, copy=False)
    two_approver_ids = fields.Many2many('res.users', 'po_two_level_approver_rel', 'purchase_id', 'user_id',
                                        string='2nd Approver', readonly=True, copy=False)
    one_approved_id = fields.Many2one('res.users', string='1st Approved User', readonly=True, copy=False)
    two_approved_id = fields.Many2one('res.users', string='2nd Approved User', readonly=True, copy=False)
    one_approved_date = fields.Datetime(string='1st Approved Date', readonly=True, copy=False)
    two_approved_date = fields.Datetime(string='2nd Approved Date', readonly=True, copy=False)
    history = fields.Text(string="History", readonly=True)
    amount_to_text = fields.Char( string="In Words", )
    amount_to_text_local_currency = fields.Char( string="In Words(Local)",)
    #    amount_discounted = fields.Monetary(string='Discounted Amount',
    #        store=True, readonly=True, compute='_compute_discount_amount', track_visibility='always')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency",
                                          readonly=True)
    amount_total_signed = fields.Monetary(string='Total in Purchase Currency', currency_field='currency_id',
                                          store=True, readonly=True, compute='_compute_custom_amount')
    amount_total_company_signed = fields.Monetary(string='Total in Company Currency',
                                                  currency_field='company_currency_id',
                                                  store=True, readonly=True, compute='_compute_custom_amount')
    notes = fields.Text('Terms and Conditions')
    purchase_remarks = fields.Text(string="Remarks")

    amendment_no = fields.Integer(string="Amendment No", readonly=True)
    lc_no_id = fields.Many2one('purchase.order.lc.master', string='LC No', copy=False)
    delivery_location = fields.Char('Delivery Location',  copy=False)
    shipping_mode_id = fields.Many2one('po.shipping.mode', 'Mode of Shipment',  copy=False)
    date_planned = fields.Datetime(string='Expected Delivery Date', compute='_compute_date_planned', store=True,
                                   index=True)
    lc_line = fields.One2many('purchase.order.landed.cost.line', 'order_id', string="LC Expense Lines", copy=False,)
    invoice_refund_count = fields.Integer(compute="_compute_invoice_refund", string='# of Invoice Refunds', copy=False, default=0)
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Order Qty')

    # amount_roundoff = fields.Monetary(string='Round Off', store=True, readonly=True, compute='_amount_all', track_visibility='always')

    # # @api.multi
    # old
    # def print_purchase_order(self):
    #     self.ensure_one()
    #     if self.category_id.type == 'normal':
    #         return self.env['report'].get_action(self, 'purchase.order.rml.report')
    #     else:
    #         return self.env['report'].get_action(self, 'purchase.order.service.rml.report') # # @api.multi


    def print_purchase_order(self):
        if self.category_id.type == 'normal':
            return self.env.ref('ebits_custom_purchase.action_purchase_order_report').report_action(self)


    # @api.model
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name', False):
                vals['name'] = "New #"

        # if not vals.get('name'):
        #     vals.update({'name': 'New #'})
        # result = super(PurchaseOrder, self).create(vals)
        # return result

        # vals dict --> list 
        # for v in vals:
        #     if not v.name:
        #         v.name = "New #"

        result = super(PurchaseOrder, self).create(vals_list)
        return result



    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        type_obj = self.env['stock.picking.type']
        if not self.warehouse_id:
            self.picking_type_id = False
        else:
            types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id', '=', self.warehouse_id.id)])
            self.picking_type_id = types[:1]
            self.notes = self.warehouse_id.po_notes and self.warehouse_id.po_notes or ""
        return {}

    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        warning = {}
        for rec in self:

            if not rec.partner_id:
                rec.fiscal_position_id = False
                rec.payment_term_id = False
                rec.currency_id = False
            else:
                if rec.partner_id.transaction_currency_id:
                    rec.currency_id = rec.partner_id.transaction_currency_id.id
                else:
                    warning = {
                        'title': _('Warning'),
                        'message': _('Currency has not been configured in vendor master.')}
                vv = rec.env['account.fiscal.position'].with_context(company_id=rec.company_id.id)
                print("\n\n............vv",vv)

                rec.fiscal_position_id = rec.env['account.fiscal.position'].with_context(
                    company_id=rec.company_id)._get_fiscal_position(rec.partner_id)
                rec.payment_term_id = rec.partner_id.property_supplier_payment_term_id.id
                # self.currency_id = self.partner_id.property_purchase_currency_id.id or self.env.user.company_id.currency_id.id

            return {'warning': warning}

    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        warning = {}
        if self.currency_id:
            if self.partner_id:
                if self.partner_id.transaction_currency_id != self.currency_id:
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot change the Vendor currency configured in Vendor master.')}
                    self.currency_id = self.partner_id.transaction_currency_id
            else:
                if self.partner_id:
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot change the customer currency without selecting vendor.')}
                    self.currency_id = False

        return {'warning': warning}

    @api.onchange('order_line')
    def _onchange_order_line(self):
        lc_grouped = self.get_lc_values()
        lc_lines = self.lc_line.browse([])
        for each in lc_grouped:
            lc_lines += lc_lines.new(each)
        self.lc_line = lc_lines
        return

    # # @api.multi
    def recompute_lc_values(self):
        lc_grouped = []
        for each in self:
            if each.state not in ['purchase', 'done', 'cancel']:
                lc_grouped = each.get_lc_values()
                lc_lines = self.lc_line.browse([])
                for each_lc in lc_grouped:
                    lc_lines += lc_lines.new(each_lc)
                self.lc_line = lc_lines
        return True

    # # @api.multi
    def get_lc_values(self):
        lc_grouped = []
        lc_data = {}
        for each in self:
            for line in each.order_line:
                c_grouped = []
                price_total = total = percentage_value = 0.00
                price_total = line.price_unit * line.product_qty
                total = price_total
                if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
                    currency_id = self.currency_id.with_context(date=self.date_order)
                    total = currency_id._convert(price_total, self.company_id.currency_id)
                for each_lc in line.lc_expenses_ids:
                    percentage = percentage_value = 0.00
                    if each_lc.landed_percentage:
                        sub_lc_total = sub_total = 0.00
                        for each_sub_lc in each_lc.include_lc_product_ids:
                            sub_total = 0.00
                            if each_sub_lc.landed_percentage:
                                sub_total = total * (each_sub_lc.landed_percentage / 100)
                            sub_lc_total += sub_total
                        percentage_value = (total + sub_lc_total) * (each_lc.landed_percentage / 100)
                        if line.product_id.id in lc_data:
                            if each_lc.id in lc_data[line.product_id.id]:
                                lc_data[line.product_id.id][each_lc.id]['amount'] += percentage_value
                                lc_data[line.product_id.id][each_lc.id]['product_qty'] += line.product_qty
                            else:
                                lc_data[line.product_id.id][each_lc.id] = {
                                    'name': each_lc.name,
                                    'lc_expense_id': each_lc.id,
                                    'po_product_id': line.product_id.id,
                                    'lc_account_id': each_lc.property_account_expense_id.id or each_lc.categ_id.property_account_expense_categ_id.id,
                                    'percentage': each_lc.landed_percentage,
                                    'amount': percentage_value,
                                    'order_id': self.id,
                                    'product_qty': line.product_qty,
                                    'po_amount': line.price_unit * line.product_qty,
                                }
                        else:
                            lc_data[line.product_id.id] = {}
                            lc_data[line.product_id.id][each_lc.id] = {
                                'name': each_lc.name,
                                'lc_expense_id': each_lc.id,
                                'po_product_id': line.product_id.id,
                                'lc_account_id': each_lc.property_account_expense_id.id,
                                'percentage': each_lc.landed_percentage,
                                'amount': percentage_value,
                                'order_id': self.id,
                                'product_qty': line.product_qty,
                                'po_amount': line.price_unit * line.product_qty,
                            }
        for each_lc_data in lc_data:
            for each_sub_lc in lc_data[each_lc_data]:
                lc_grouped.append(lc_data[each_lc_data][each_sub_lc])
        return lc_grouped

    # # @api.multi
    def _add_supplier_to_product(self):
        # Add the partner in the supplier list of the product if the supplier is not registered for
        # this product. We limit to 10 the number of suppliers for a product to avoid the mess that
        # could be caused for some generic products ("Miscellaneous").
        for line in self.order_line:
            partner = self.partner_id if not self.partner_id.parent_id else self.partner_id.parent_id
            currency = partner.property_purchase_currency_id or self.env.company.currency_id
            price = self.currency_id._convert(line.price_unit, currency, line.company_id,
                                              line.date_order or fields.Date.today(), round=False)


            # Do not add a contact as a supplier

            if partner not in line.product_id.seller_ids.mapped('partner_id') and len(line.product_id.seller_ids) <= 10:
                currency = partner.transaction_currency_id or self.env.user.company_id.currency_id
                default_uom = line.product_id.product_tmpl_id.uom_po_id
                price = line.product_uom._compute_price(price, default_uom)



                supplierinfo = {
                    'partner_id': partner.id,
                    'sequence': max(
                        line.product_id.seller_ids.mapped('sequence')) + 1 if line.product_id.seller_ids else 1,
                    'product_uom': line.product_uom.id,
                    'min_qty': 0.0,
                    'price':price,
                    'currency_id': currency.id,
                    'delay': 0,
                }
                vals = {
                    'seller_ids': [(0, 0, supplierinfo)],
                }
                print("\n\n............supplierinfo.......",supplierinfo)
                print("\n\n............vals.......",vals)
                try:
                    line.product_id.write(vals)
                except AccessError:  # no write access rights -> just ignore
                    break

    # # @api.multi
    def button_confirm(self):
        print("\n......button_confirm......")
        hierarchy_obj = self.env['purchase.order.approval.hierarchy']
        history = name = code = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for order in self:
            if order.name == 'New #':
                #  create field cutom stock  purchase_sequence_id in
                if order.warehouse_id.purchase_sequence_id:
                    name = order.warehouse_id.purchase_sequence_id.next_by_id()
                    code = order.category_id.code or ''
                    order.write({'name': code + "/" + name})
                else:
                    raise UserError(
                        _('Purchase Order Sequence not defined in warehouse (%s)') % (order.warehouse_id.name))
            if order.state not in ['draft', 'sent']:
                continue
            order._add_supplier_to_product()
            print("\n\n.........hierarchy_obj....",hierarchy_obj)
            print("\n\n.........order.warehouse_id.id)....",order.warehouse_id)
            print("\n\n...... order.category_id.id....", order.category_id)
            hierarchy_search = hierarchy_obj.search(
                [('warehouse_id', '=', order.warehouse_id.id), ('category_ids', 'in', order.category_id.id)])
            print("\n\n...111111......hierarchy_search....",hierarchy_search)
            if not hierarchy_search:
                raise UserError(_("Approval hierarchy not defined for selected warehouse [%s] and category [%s].") % (
                order.warehouse_id.name, order.category_id.name,))
            for hierarchy in hierarchy_search:
                order.write({'one_approver_ids': [(6, 0, hierarchy.one_level_user_ids.ids)]})
                if hierarchy.hierarchy_type == 'two':
                    order.write({'two_approver_ids': [(6, 0, hierarchy.two_level_user_ids.ids)]})
            if order.history:
                history = order.history + "\n"
            order.write({'state': 'to approve',
                         'history': history + 'This document is sent for approval by ' + self.env.user.name + ' on this date ' + date})
            # Deal with double validation process
            # if order.company_id.po_double_validation == 'one_step'\
            #        or (order.company_id.po_double_validation == 'two_step'\
            #            and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_double_validation_amount, order.currency_id))\
            #        or order.user_has_groups('purchase.group_purchase_manager'):
            #    order.button_approve()
            # else:
            #    order.write({'state': 'to approve'})
        return True

    # # @api.multi
    def action_one_approve(self):
        approve_check = False
        history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for order in self:
            if order.history:
                history = order.history + "\n"
            for each in order.one_approver_ids:

                if each.id == self.env.user.id:

                    approve_check = True
                    order.write({'one_approved_id': self.env.user.id,
                                 'one_approved_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                    if order.two_approver_ids:
                        order.write({'state': 'to_2nd_approve',
                                     'history': history + 'This document is approved and sent for 2nd Level Approval by ' + self.env.user.name + ' on this date ' + date})
                    else:
                        order.write({'history': history + 'This document is approved by ' + self.env.user.name + ' on this date ' + date})
                        order.button_approve()
            if not approve_check:
                raise UserError(_("You cannot approve this quotation."))
        return True

    # # @api.multi
    def action_two_approve(self):
        approve_check = False
        history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for order in self:
            if order.history:
                history = order.history + "\n"
            for each in order.two_approver_ids:
                if each.id == self.env.user.id:
                    approve_check = True
                    order.write({'two_approved_id': self.env.user.id,
                                 'two_approved_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                 'history': history + 'This document is approved by ' + self.env.user.name + ' on this date ' + date})
                    order.button_approve()
            if not approve_check:
                raise UserError(_("You cannot approve this quotation."))
        return True

    # # @api.multi
    def action_po_send(self):
        '''
        This function opens a window to compose an email, with the edi purchase template message loaded by default
        '''
        self.ensure_one()
        self.action_rfq_send()
        # ir_model_data = self.env['ir.model.data']
        # try:
        #     template_id = \
        #     ir_model_data._xmlid_lookup('ebits_custom_purchase', 'email_template_edi_purchase_order_done')[1]
        # except ValueError:
        #     template_id = False
        # try:
        #     compose_form_id = ir_model_data._xmlid_lookup('mail', 'email_compose_message_wizard_form')[1]
        # except ValueError:
        #     compose_form_id = False
        # ctx = dict(self.env.context or {})
        # ctx.update({
        #     'default_model': 'purchase.order',
        #     'default_res_id': self.ids[0],
        #     'default_use_template': bool(template_id),
        #     'default_template_id': template_id,
        #     'default_composition_mode': 'comment',
        # })
        # return {
        #     'name': _('Compose Email'),
        #     'type': 'ir.actions.act_window',
        #     'view_type': 'form',
        #     'view_mode': 'form',
        #     'res_model': 'mail.compose.message',
        #     'views': [(compose_form_id, 'form')],
        #     'view_id': compose_form_id,
        #     'target': 'new',
        #     'context': ctx,
        # }

    # # @api.multi
    def action_open_stock_landed_cost(self):
        ctx = dict(self.env.context or {})
        result = {}
        for each in self:
            if not each.lc_no_id:
                raise UserError(_("You cannot open landed cost form without entering lc no"))
            ctx.update({
                'default_purchase_id': each.id,
                'default_lc_no_id': each.lc_no_id and each.lc_no_id.id or False,
            })
            action = self.env.ref('stock_landed_costs.action_stock_landed_cost')
            result = action.read()[0]
            result['context'] = ctx
            landed_ids = self.env['stock.landed.cost'].sudo().search([('purchase_id', '=', each.id)])
            stock_landed_id = []
            for each_land in landed_ids:
                stock_landed_id.append(each_land.id)
            if len(stock_landed_id) > 1:
                result['domain'] = "[('id','in',[" + ','.join(map(str, stock_landed_id)) + "])]"
            else:
                res = self.env.ref('stock_landed_costs.view_stock_landed_cost_form', False)
                result['views'] = [(res and res.id or False, 'form')]
                result['res_id'] = stock_landed_id and stock_landed_id[0] or False
        return result

    ### SEND WAREHOUSE_ID  IN VENDER BILL WHEN IT CREATE
    def _prepare_invoice(self):
        result = super(PurchaseOrder, self)._prepare_invoice()
        
        result['warehouse_id'] = self.warehouse_id and self.warehouse_id.id
        if self.picking_ids:
            result['ref'] = self.picking_ids[0].supplier_inv_no or self.partner_ref or ''
            result['invoice_date'] = self.picking_ids[0].supplier_inv_date
        return result
#not used for 17
    # # @api.multi
    ### SEND purchase_id  IN VENDER BILL WHEN IT CREATE
    def action_view_invoice(self, invoices=False):
        # Call the original method from the parent class
        result = super(PurchaseOrder, self).action_view_invoice(invoices)

        # Ensure result['context'] is a dictionary, or initialize it if not
        if isinstance(result, dict):
            result_context = result.get('context', {})
            if not isinstance(result_context, dict):
                result_context = {}
        else:
            result = {'context': {}}
            result_context = result['context']
        # Update the context with custom values
        result_context.update({
            'default_purchase_id': self.id,  # The default purchase order ID
        })

        # Apply the updated context back to the result
        result['context'] = result_context
        return result

    # # @api.multi
    def action_view_invoice_refund(self):
        """
        This function returns an action that display existing vendor refund
        bills of given purchase order id.
        When only one found, show the vendor bill immediately.
        """
        action = self.env.ref('account.action_invoice_tree2')
        result = action.read()[0]
        refunds = self.invoice_ids.filtered(lambda x: x.type == 'in_refund')
        # override the context to get rid of the default filtering
        result['context'] = {'type': 'in_refund',
                             'default_purchase_id': self.id,
                             'default_warehouse_id': self.warehouse_id.id,
                             'default_currency_id': self.currency_id.id,
                             'warehouse_id': self.warehouse_id.id,
                             'currency_id': self.currency_id.id}

        if not refunds:
            # Choose a default account journal in the
            # same currency in case a new invoice is created
            journal_domain = [
                ('type', '=', 'purchase'),
                ('company_id', '=', self.company_id.id),
                ('currency_id', '=', self.currency_id.id),
            ]
            default_journal_id = self.env['account.journal'].search(
                journal_domain, limit=1)
            if default_journal_id:
                result['context']['default_journal_id'] = default_journal_id.id
        else:
            # Use the same account journal than a previous invoice
            result['context']['default_journal_id'] = refunds[0].journal_id.id

        # choose the view_mode accordingly
        if len(refunds) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(refunds.ids) + ")]"
        elif len(refunds) == 1:
            res = self.env.ref('account.invoice_supplier_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = refunds.id
        return result

    @api.depends('name', 'partner_ref')
    def _compute_display_name(self):
        super()._compute_display_name()

        for po in self:
            
            name = po.name
            
            if po.partner_ref:
            
                name += ' (' + po.partner_ref + ')'

            po.display_name = name


    # @api.multi
    # @api.depends('name', 'partner_ref')
    # def name_get(self):
    #     result = []
    #     for po in self:
    #         name = po.name
    #         if po.partner_ref:
    #             name += ' (' + po.partner_ref + ')'
    #         #            if po.amount_total:
    #         #                name += ': ' + formatLang(self.env, po.amount_total, currency_obj=po.currency_id)
    #         result.append((po.id, name))
    #     return result

    @api.model
    def _prepare_picking(self):
        res = super(PurchaseOrder, self)._prepare_picking()
        res['currency_id'] = self.currency_id and self.currency_id.id or False
        if self.partner_ref:
            res['origin'] = self.name + " / " + self.partner_ref
        return res


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity')
    def _compute_qty_invoiced(self):
        super(PurchaseOrderLine, self)._compute_qty_invoiced()
        for line in self:
            qty = 0.0
            for inv_line in line.invoice_lines:
                inv_type = inv_line.move_id.move_type
                invl_q = inv_line.quantity
                # This is a small 'hack' to allow the odoo tests to pass.
                # See https://github.com/OCA/OCB/pull/598
                if inv_type == 'out_invoice' and inv_line.move_id.account_id.user_type_id.type == 'payable':
                    inv_type = 'in_invoice'
                if inv_line.move_id.state not in ['draft', 'cancel']:
                    if ((inv_type == 'in_invoice' and invl_q > 0.0) or (inv_type == 'in_refund' and invl_q < 0.0)):
                        qty += inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
            line.qty_invoiced = qty

    # @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity')
    def _compute_qty_refunded(self):
        for line in self:
            qty = 0.0
            for inv_line in line.invoice_lines:
                inv_type = inv_line.move_id.type
                invl_q = inv_line.quantity
                if ((inv_type == 'in_invoice' and invl_q < 0.0) or (inv_type == 'in_refund' and invl_q > 0.0)):
                    qty += inv_line.uom_id._compute_quantity(inv_line.quantity, line.product_uom)
            line.qty_refunded = qty

    @api.depends('order_id.state', 'qty_received', 'qty_invoiced',
                 'product_qty', 'move_ids.state',
                 'invoice_lines.move_id.state', 'invoice_lines.quantity')
    def _compute_qty_to_invoice(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            line.qty_to_invoice = 0.0
            line.qty_to_refund = 0.0
            if line.order_id.state not in ('purchase', 'done'):
                line.invoice_status = 'no'
                continue
            else:
                if line.product_id.purchase_method == 'receive':
                    qty = (line.qty_received - line.qty_returned) - (line.qty_invoiced - line.qty_refunded)
                    if qty >= 0.0:
                        line.qty_to_invoice = qty
                    else:
                        line.qty_to_refund = abs(qty)
                else:
                    line.qty_to_invoice = line.product_qty - line.qty_invoiced
                    line.qty_to_refund = 0.0

            if line.product_id.purchase_method == 'receive' and not line.move_ids.filtered(lambda x: x.state == 'done'):
                line.invoice_status = 'to invoice'
                # We would like to put 'no', but that would break standard
                # odoo tests.
                continue

            if abs(float_compare(line.qty_to_invoice, 0.0, precision_digits=precision)) == 1:
                line.invoice_status = 'to invoice'
            elif abs(float_compare(line.qty_to_refund, 0.0, precision_digits=precision)) == 1:
                line.invoice_status = 'to invoice'
            elif float_compare(line.qty_to_invoice, 0.0, precision_digits=precision) == 0 \
                    and float_compare(line.qty_to_refund, 0.0, precision_digits=precision) == 0:
                line.invoice_status = 'invoiced'
            else:
                line.invoice_status = 'no'

    # @api.depends('order_id.state', 'move_ids.state')
    # @api.depends('order_id.state')
    # def _compute_qty_returned(self):
    #     for line in self:
    #         line.qty_returned = 0.0
    #         bom_delivered = line.sudo()._get_bom_delivered()
    #         qty = 0.0
    #         if not bom_delivered:
    #             for move in line.move_ids:
    #                 if move.state == 'done' and move.location_id.usage != 'supplier':
    #                     qty += move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom)
    #         line.qty_returned = qty

    # @api.depends('order_id.state', 'move_ids.state', 'move_ids')
    # def _compute_qty_received(self):
    #     super(PurchaseOrderLine, self)._compute_qty_received()
    #     for line in self:
    #         bom_delivered = line.sudo()._get_bom_delivered()
    #         if not bom_delivered:
    #             for move in line.move_ids:
    #                 if move.state == 'done' and move.location_id.usage != 'supplier':
    #                     qty = move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom)
    #                     line.qty_received -= qty
    #
    pr_lines = fields.One2many('po.pr.link.line', 'order_line_id', string="purchase Order")
    pr_qty = fields.Float(string='Requested Qty', digits='Product Unit of Measure', copy=False,
                          readonly=True)
    product_qty = fields.Float(string='Order Qty', digits='Product Unit of Measure', required=True)
    price_unit = fields.Float(string='Unit Price', required=True, digits='Purchase Product Price')
    date_planned = fields.Datetime(string='Expected Delivery Date', required=True, index=True)
    lc_expenses_ids = fields.Many2many('product.product', 'purchase_product_lc_expense_rel', 'line_id', 'product_id',
                                       string='LC Expense')
    qty_invoiced = fields.Float(compute='_compute_qty_invoiced', string="Billed Qty", store=True,
                                digits='Product Unit of Measure')
    qty_received = fields.Float(compute='_compute_qty_received', string="Received Qty", store=True,
                                digits='Product Unit of Measure')
    ##Third Party
    qty_to_invoice = fields.Float(compute="_compute_qty_to_invoice", string='Qty to Bill', copy=False, default=0.0,
                                  digits='Product Unit of Measure', compute_sudo=True, store=True)
    qty_to_refund = fields.Float(compute="_compute_qty_to_invoice", string='Qty to Refund', copy=False, default=0.0,
                                 digits='Product Unit of Measure', compute_sudo=True, store=True)
    # qty_refunded = fields.Float(compute="_compute_qty_refunded", string='Refunded Qty', copy=False, default=0.0, digits=dp.get_precision('Product Unit of Measure'))
    qty_refunded = fields.Float(string='Refunded Qty', copy=False, default=0.0,
                                digits='Product Unit of Measure')
    qty_returned = fields.Float(string='Returned Qty', copy=False, default=0.0,
                                digits='Product Unit of Measure')
    # qty_returned = fields.Float(compute="_compute_qty_returned", string='Returned Qty', copy=False, default=0.0, digits=dp.get_precision('Product Unit of Measure'))
    invoice_status = fields.Selection([
        ('no', 'Not purchased'),
        ('to invoice', 'Waiting Invoices'),
        ('invoiced', 'Invoice Received'),
    ], string='Invoice Status', compute='_compute_qty_to_invoice', readonly=True, copy=False, default='no', compute_sudo=True, store=True)
    
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', related='order_id.warehouse_id',
                                   readonly=True, store=True, copy=False)

    @api.onchange('product_uom', 'product_qty')
    def _onchange_uom_id(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_id and self.product_uom:
            product_uom = self.product_id.uom_po_id and self.product_id.uom_po_id or self.product_id.uom_id
            if self.product_uom.id != product_uom.id:
                self.product_uom = product_uom.id
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of Measure cannot be changed.')}
                return {'warning': warning}
        if self.product_qty and (not self.product_uom.allow_decimal_digits):
            integer, decimal = divmod(self.product_qty, 1)
            if decimal:
                if self.pr_qty:
                    self.product_qty = self.pr_qty
                else:
                    self.product_qty = 0.00
                warning = {
                    'title': _('Warning'),
                    'message': _(
                        'You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the quantity should not contains decimal value') % (
                                   self.product_uom.name)}
                return {'warning': warning}
        return {'warning': warning}

    # @api.multi
    def _create_stock_moves(self, picking):
        moves = self.env['stock.move']
        done = self.env['stock.move'].browse()
        location_dest_id = False
        for line in self:
            if line.product_id.type not in ['product', 'consu']:
                continue
            qty = 0.0
            price_unit = line._get_stock_move_price_unit()
            for move in line.move_ids.filtered(lambda x: x.state != 'cancel'):
                qty += move.product_qty
            location_dest_id = False
            if line.product_id.quality_check_required == 'yes':
                if not line.order_id.picking_type_id.warehouse_id.quality_location_id:
                    raise UserError(
                        _("Unable to find quality location in selected warehouse [%s]. \nKindly contact your administrator!!!") % (
                        line.order_id.picking_type_id.warehouse_id.name,))
                location_dest_id = line.order_id.picking_type_id.warehouse_id.quality_location_id.id
            else:
                location_dest_id = line.order_id._get_destination_location()
            template = {
                'name': line.name + ' / ' + picking.name + ' / ' + line.order_id.name or '',
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'date': line.order_id.date_order,
                # not in move 'date_expected': line.date_planned,
                'location_id': line.order_id.partner_id.property_stock_supplier.id,
                'location_dest_id': location_dest_id,
                'picking_id': picking.id,
                'partner_id': line.order_id.dest_address_id.id,
                'move_dest_ids': False,
                'state': 'draft',
                'purchase_line_id': line.id,
                'company_id': line.order_id.company_id.id,
                'price_unit': price_unit,
                'picking_type_id': line.order_id.picking_type_id.id,
                'group_id': line.order_id.group_id.id,
                # not in move 'procurement_id': False,
                'origin': line.order_id.name,
                'route_ids': line.order_id.picking_type_id.warehouse_id and [
                    (6, 0, [x.id for x in line.order_id.picking_type_id.warehouse_id.route_ids])] or [],
                'warehouse_id': line.order_id.picking_type_id.warehouse_id.id,
            }
            # Fullfill all related procurements with this po line
            diff_quantity = line.product_qty - qty
            # procurement_ids not in 17 and in 10 not get data
            # for procurement in line.procurement_ids:
            #     # If the procurement has some moves already, we should deduct their quantity
            #     sum_existing_moves = sum(x.product_qty for x in procurement.move_ids if x.state != 'cancel')
            #     existing_proc_qty = procurement.product_id.uom_id._compute_quantity(sum_existing_moves,
            #                                                                         procurement.product_uom)
            #     procurement_qty = procurement.product_uom._compute_quantity(procurement.product_qty,
            #                                                                 line.product_uom) - existing_proc_qty
            #     if float_compare(procurement_qty, 0.0,
            #                      precision_rounding=procurement.product_uom.rounding) > 0 and float_compare(
            #             diff_quantity, 0.0, precision_rounding=line.product_uom.rounding) > 0:
            #         tmp = template.copy()
            #         tmp.update({
            #             'product_uom_qty': min(procurement_qty, diff_quantity),
            #             'move_dest_id': procurement.move_dest_id.id,
            #             # move destination is same as procurement destination
            #             'procurement_id': procurement.id,
            #             'propagate': procurement.rule_id.propagate,
            #         })
            #         done += moves.create(tmp)
            #         diff_quantity -= min(procurement_qty, diff_quantity)
            if float_compare(diff_quantity, 0.0, precision_rounding=line.product_uom.rounding) > 0:
                template['product_uom_qty'] = diff_quantity
                done += moves.create(template)
        return done


class PoPrLinkLine(models.Model):
    _name = 'po.pr.link.line'
    _description = 'PO and PR Link'
    _rec_name = 'pr_line_id'

    pr_line_id = fields.Many2one('po.requisition.item.lines', string="PR Item Line", required=True, copy=False)
    order_line_id = fields.Many2one('purchase.order.line', string='Order Line', ondelete='cascade', required=True,
                                    copy=False)
    pr_qty = fields.Float(string='PR Qty', digits='Product Unit of Measure', required=True,
                          copy=False)


class PurchaseOrderLandedCostLine(models.Model):
    _name = 'purchase.order.landed.cost.line'
    _description = 'Purchase Order Landed Cost Lines'

    name = fields.Char(string="Name", required=True, copy=False)
    order_id = fields.Many2one('purchase.order', string='Order', ondelete='cascade', required=True)
    lc_expense_id = fields.Many2one('product.product', string='LC Expense', required=True, copy=False)
    lc_account_id = fields.Many2one('account.account', string='LC Expense Account', copy=False)
    po_product_id = fields.Many2one('product.product', string='Product', required=True, copy=False)
    percentage = fields.Float(string='Percentage', required=True, digits=(16, 4), copy=False)
    po_amount = fields.Float(string='Product Price', required=True, digits='Product Price',
                             copy=False)
    amount = fields.Float(string='Amount', required=True, digits='Product Price', copy=False)
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True,
                               copy=False)
    picking_ids = fields.Many2many('stock.picking', 'picking_po_landed_cost_line_rel', 'landed_cost_id', 'picking_id',
                                   string='Pickings', copy=False, readonly=True)

# class ProcurementOrder(models.Model):
#     _inherit = 'procurement.order'
#
#     # @api.multi
#     def _prepare_purchase_order(self, partner):
#         self.ensure_one()
#         result = super(ProcurementOrder, self)._prepare_purchase_order(partner)
#         result['currency_id'] = partner.transaction_currency_id and partner.transaction_currency_id.id or self.env.user.company_id.currency_id.id
#
