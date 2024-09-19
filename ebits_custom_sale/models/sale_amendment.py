# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import groupby
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang

import odoo.addons.decimal_precision as dp


class SaleOrderAmendment(models.Model):
    _name = "sale.order.amendment"
    # _inherit = ['mail.thread', 'ir.needaction_mixin']
    _inherit = ['mail.thread']
    _description = "Sales Order Amendment"
    # _order = 'date_order desc, id desc'

    sale_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade', index=True, copy=False)
    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True)
    origin = fields.Char(string='Source Document', help="Reference of the document that generated this sales order request.")
    client_order_ref = fields.Char(string='Customer Reference', copy=False)
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('waiting', 'Waiting For Approval'),
        ('waiting_higher', 'Waiting For Higher Authority Approval'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, tracking=True)
    date_order = fields.Datetime(string='Order Date', required=True, readonly=True, index=True, copy=False)
    validity_date = fields.Date(string='Expiration Date', readonly=True,
        help="Manually set the expiration date of your quotation (offer), or it will set the date automatically based on the template if online quotation is installed.")
    create_date = fields.Datetime(string='Creation Date', readonly=True, index=True, help="Date on which sales order is created.")
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=True, index=True, help="Date on which the sale order is confirmed.")
    user_id = fields.Many2one('res.users', string='Created User', readonly=True)
    sales_manager_id = fields.Many2one('res.users', string='Sales Manager', readonly=True)
    exp_delivery_date = fields.Datetime(string='Expected Delivery Date', copy=False, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True, required=True, change_default=True, index=True, tracking=True)
    partner_invoice_id = fields.Many2one('res.partner', string='Invoice Address', readonly=True, required=True, help="Invoice address for current sales order.")
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', readonly=True, required=True, help="Delivery address for current sales order.")
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, readonly=True, help="Pricelist for current sales order.")
    currency_id = fields.Many2one("res.currency", related='pricelist_id.currency_id', string="Currency", readonly=True, required=True)
    project_id = fields.Many2one('account.analytic.account', 'Analytic Account', readonly=True, help="The analytic account related to a sales order.", copy=False)
    order_line = fields.One2many('sale.order.amendment.line', 'order_id', string='Order Lines', copy=True)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status', store=True, readonly=True)
    note = fields.Text('Terms and conditions')
    amount_untaxed = fields.Float(string='Untaxed Amount', readonly=True)
    amount_discounted = fields.Float(string='Discount Amount', readonly=True)
    amount_roundoff = fields.Float(string='Roundoff Amount', readonly=True)
    amount_tax = fields.Float(string='Taxes', readonly=True)
    amount_total = fields.Float(string='Total', readonly=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms')
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position')
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    team_id = fields.Many2one('crm.team', 'Sales Team', readonly=True)
    product_id = fields.Many2one('product.product', related='order_line.product_id', string='Product')
    incoterm = fields.Many2one('account.incoterms', 'Incoterms',
        help="International Commercial Terms are a series of predefined commercial terms used in international transactions.")
    picking_policy = fields.Selection([
        ('direct', 'Deliver each product when available'),
        ('one', 'Deliver all products at once')],
        string='Shipping Policy', required=True, readonly=True, default='direct')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True, readonly=True)
    credit_limit = fields.Float(string='Initial Credit Limit', readonly=True, copy=False, help="Initial Credit Limit in Customer Master")
    avail_credit_limit = fields.Float(string='Availabile Credit Limit', readonly=True, copy=False, help="Availabile Credit Limit = Initial Credit Limit - (Total Invoiced Due amount) - (Total Confirmed Sales Amount Yet To Be Invoiced)")
    invoice_due = fields.Float(string='Balance Due', readonly=True, copy=False, help="Invoice Balance Due")
    approved_so_value = fields.Float(string='Approved SO Value', readonly=True, copy=False, help="Approved So Value")
    credit_limit_check = fields.Selection([
        ('achieved', 'Achieved'),
        ('not_achieved', 'Not Achieved'),
        ('none', 'Not Required'),
        ], string='Credit Limit Check', readonly=True, copy=False)
    sale_revision_no = fields.Integer(string='Revision', copy=False, readonly=True)
    sale_amendment_no = fields.Integer(string='Amendment', copy=False, readonly=True)
    payment_term_check = fields.Selection([
        ('achieved', 'Achieved'),
        ('not_achieved', 'Not Achieved'),
        ('none', 'Not Required'),
        ], string='Payment Terms Check', readonly=True, copy=False)
    revision_reason = fields.Text('Revision Reason', copy=False, readonly=True)
    revision_user_id = fields.Many2one('res.users', string='Revision User', copy=False, readonly=True)
    amendment_reason = fields.Text('Amendment Reason', copy=False, readonly=True)
    amendment_user_id = fields.Many2one('res.users', string='Amendment User', copy=False, readonly=True)
    cancel_reason = fields.Text('Cancel Reason', copy=False, readonly=True)
    higher_reason = fields.Text('Higher Approval Requested Reason', copy=False, readonly=True)
    cancel_user_id = fields.Many2one('res.users', string='Cancelled User', copy=False, readonly=True)
    sale_history = fields.Text('History', copy=False, readonly=True)
    approved_user_id = fields.Many2one('res.users', string='Approved User', copy=False, readonly=True)
    approved_date = fields.Datetime(string='Approved Date', copy=False, readonly=True)
    sale_remarks = fields.Text(string="Remarks", copy=False, readonly=True)

    # @api.multi
    def unlink(self):
        for order in self:
            raise UserError(_('You can not delete amendment history.'))
        return super(SaleOrderAmendment, self).unlink()


class SaleOrderAmendmentLine(models.Model):
    _name = 'sale.order.amendment.line'
    _description = 'Sales Order Amendment Line'

    # _order = 'order_id, layout_category_id, sequence, id'
    # _order = 'order_id, sequence'


    order_id = fields.Many2one('sale.order.amendment', string='Order Reference', required=True, ondelete='cascade', index=True, copy=False)
    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status', readonly=True, default='no')
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price', default=0.0)
    tax_id = fields.Many2many('account.tax', string='Taxes', domain=['|', ('active', '=', False), ('active', '=', True)])
    price_subtotal = fields.Float(string='Subtotal', readonly=True)
    discount = fields.Float(string='Discount (%)', digits='Discount', default=0.0)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True, default=1.0)
    # product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    salesman_id = fields.Many2one(related='order_id.user_id', store=True, string='Created User', readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='Currency', readonly=True)
    company_id = fields.Many2one(related='order_id.company_id', string='Company', store=True, readonly=True)
    order_partner_id = fields.Many2one(related='order_id.partner_id', store=True, string='Customer')
    # model 'account.analytic.tag' is removed from odoo 16.
    # analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')

    state = fields.Selection(related='order_id.state', string='Order Status', readonly=True, copy=False, store=True)
    customer_lead = fields.Float(
        'Delivery Lead Time', required=True, default=0.0,
        help="Number of days between the order confirmation and the shipping of the products to the customer")
    product_packaging = fields.Many2one('product.packaging', string='Packaging', default=False)
    # route_id = fields.Many2one('stock.location.route', string='Route', domain=[('sale_selectable', '=', True)])
    route_id = fields.Many2one('stock.route', string='Route', domain=[('sale_selectable', '=', True)])
    product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id', string='Product Template', readonly=True)
    # layout_category_id = fields.Many2one('sale.layout_category', string='Section')
    # layout_category_sequence = fields.Integer(related='layout_category_id.sequence', string='Layout Sequence', store=True)
    sales_user_id = fields.Many2one('res.users', string='Salesperson', copy=False)
