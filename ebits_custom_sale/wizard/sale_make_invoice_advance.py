# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    @api.model
    def _count(self):
        return len(self._context.get('active_ids', []))

    @api.model
    def _get_advance_payment_method(self):
        result = []
        if self._count() == 1:
            sale_obj = self.env['sale.order']
            order = sale_obj.browse(self._context.get('active_ids'))[0]
            for line in order.order_line:
                if line.qty_delivered > line.qty_invoiced:
                    result.append('delivered')
                if line.qty_delivered < line.qty_invoiced:    
                    result.append('all')
            if 'delivered' in result:
                return 'delivered'
            if 'all' in result:
                return 'all'
        return 'delivered'

    advance_payment_method = fields.Selection([
        ('delivered', 'Customer Invoice'),
        ('all', 'Customer Credit Note'),
        ('percentage', 'Down payment (percentage)'),
        ('fixed', 'Down payment (fixed amount)')
        ], string='Create', default=_get_advance_payment_method, required=True)
    count = fields.Integer(default=_count, string='# of Orders')
    refund_reason = fields.Text("Refund Reason")
    
    #@api.multi

    # def create_invoices(self):
    #     # sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
    #     # print(">>>>>>>>>sale_orders>>>>>>>>>>>>>>>>.",sale_orders)
    #     # inv_obj = self.env['account.move']
    #     # invoice_item_sequence = 1
    #     #
    #     # if self.advance_payment_method == 'delivered':
    #     #     sale_orders._create_invoices()
    #     # elif self.advance_payment_method == 'all':
    #     #     inv = sale_orders._create_invoices(final=True)
    #     #     for inv_brow in inv_obj.browse(inv):
    #     #         inv_brow.refund_reason = self.refund_reason
    #     #
    #     # else:
    #     #     # Create deposit product if necessary
    #     #     if not self.product_id:
    #     #         vals = self._prepare_deposit_product()
    #     #         self.product_id = self.env['product.product'].create(vals)
    #     #         self.env['ir.values'].sudo().set_default('sale.config.settings',
    #     #                                                  'deposit_product_id_setting', self.product_id.id)
    #     #
    #     #     sale_line_obj = self.env['sale.order.line']
    #     #     for order in sale_orders:
    #     #         if self.advance_payment_method == 'percentage':
    #     #             amount = order.amount_untaxed * self.amount / 100
    #     #         else:
    #     #             amount = self.amount
    #     #         if self.product_id.invoice_policy != 'order':
    #     #             raise UserError(_('The product used to invoice a down payment '
    #     #                               'should have an invoice policy set to "Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'))
    #     #         if self.product_id.type != 'service':
    #     #             raise UserError(_("The product used to invoice a down payment should "
    #     #                               "be of type 'Service'. Please use another product or update this product."))
    #     #         if order.fiscal_position_id and self.product_id.taxes_id:
    #     #             tax_ids = order.fiscal_position_id.map_tax(self.product_id.taxes_id).ids
    #     #         else:
    #     #             tax_ids = self.product_id.taxes_id.ids
    #     #         so_line = sale_line_obj.create({
    #     #             'name': _('Advance: %s') % (time.strftime('%m %Y'),),
    #     #             'price_unit': amount,
    #     #             'product_uom_qty': 0.0,
    #     #             'order_id': order.id,
    #     #             'discount': 0.0,
    #     #             'product_uom': self.product_id.uom_id.id,
    #     #             'product_id': self.product_id.id,
    #     #             'tax_id': [(6, 0, tax_ids)],
    #     #         })
    #     #         self._create_invoice(order, so_line, amount)
    #     #
    #     # if self._context.get('open_invoices', False):
    #     #     return sale_orders.action_view_invoice()
    #     # return {'type': 'ir.actions.act_window_close'}
    #     return True

#SaleAdvancePaymentInv()
