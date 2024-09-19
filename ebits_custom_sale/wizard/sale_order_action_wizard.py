# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
import pytz
import datetime
import time

class SaleOrderCancelWizard(models.TransientModel):
    _name = 'sale.order.cancel.wizard'
    _description = 'Sales Order Cancel Wizard'
    
    order_id = fields.Many2one('sale.order', string='Order Reference', required=True, copy=False, readonly=True)
    cancel_reason = fields.Text('Cancel Reason', required=True, copy=False)
    
    @api.model
    def default_get(self, fields):
        if len(self.env.context.get('active_ids', list())) > 1:
            raise UserError("You may cancel only one quotation at a time!")
        res = super(SaleOrderCancelWizard, self).default_get(fields)

        sale_obj = self.env['sale.order']
        sale_order = sale_obj.browse(self.env.context.get('active_id'))
        if sale_order:
            res.update({'order_id': sale_order.id})
            if sale_order.state == 'done':
                raise UserError("You cannot cancel the order which is confirmed already!")
        return res
        
    #@api.multi
    def action_cancel(self):
        cancel_reason = ""
        sale_history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            print(">>>>>>>>each>>>>>>>>>>>",each)
            sale_order = each.order_id
            print(">>>>>>>>sale_order>>>>>>>>>>>", sale_order)
            if sale_order.cancel_reason:
                cancel_reason = '\n' + sale_order.cancel_reason
            if sale_order.sale_history:
                sale_history = '\n' + sale_order.sale_history
            sale_order.write({'cancel_reason': each.cancel_reason + "\nby " + self.env.user.name + " on " + date + cancel_reason, 
                'cancel_user_id': self.env.user.id,
                'sale_history': "Order cancelled by " + self.env.user.name + " on " + date + sale_history})
            sale_order._action_cancel()
        return {'type': 'ir.actions.act_window_close'}
        
#SaleOrderCancelWizard()

class SaleOrderRevisionWizard(models.TransientModel):
    _name = 'sale.order.revision.wizard'
    _description = 'Sales Order Revision Wizard'
    
    order_id = fields.Many2one('sale.order', string='Order Reference', required=True, copy=False, readonly=True)
    revision_reason = fields.Text('Revision Reason', required=True, copy=False)
    
    @api.model
    def default_get(self, fields):
        if len(self.env.context.get('active_ids', list())) > 1:
            raise UserError("You may revision one quotation at a time!")
        res = super(SaleOrderRevisionWizard, self).default_get(fields)

        sale_obj = self.env['sale.order']
        sale_order = sale_obj.browse(self.env.context.get('active_id'))
        if sale_order:
            res.update({'order_id': sale_order.id})
        return res
        
    #@api.multi
    def action_revision(self):
        revision_reason = ""
        sale_history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            sale_order = each.order_id
            if sale_order.revision_reason:
                revision_reason = '\n' + sale_order.revision_reason
            if sale_order.sale_history:
                sale_history = '\n' + sale_order.sale_history
            sale_order.write({'revision_reason': each.revision_reason + "\nby " + self.env.user.name + " on " + date + revision_reason, 
                'revision_user_id': self.env.user.id, 
                'sale_revision_no': sale_order.sale_revision_no + 1, 
                'state': 'draft',
                'sale_history': "Order revised by " + self.env.user.name + " on " + date + sale_history})
        return {'type': 'ir.actions.act_window_close'} 
        
#SaleOrderRevisionWizard()

class SaleOrderAmendmentWizard(models.TransientModel):
    _name = 'sale.order.amendment.wizard'
    _description = 'Sales Order Amendment Wizard'
    
    order_id = fields.Many2one('sale.order', string='Order Reference', required=True, copy=False, readonly=True)
    amendment_reason = fields.Text('Amendment Reason', required=True, copy=False)
    
    @api.model
    def default_get(self, fields):
        if len(self.env.context.get('active_ids', list())) > 1:
            raise UserError("You may amendment one quotation at a time!")
        res = super(SaleOrderAmendmentWizard, self).default_get(fields)

        sale_obj = self.env['sale.order']
        sale_order = sale_obj.browse(self.env.context.get('active_id'))
        if sale_order:
            res.update({'order_id': sale_order.id})
            for each_line in sale_order.order_line:
                if each_line.qty_delivered != 0:
                    raise UserError("You cannot Amend the order which is delivered partially/fully!")
        return res
        
    #@api.multi
    def action_amend(self):
        sale_amendment_obj = self.env['sale.order.amendment']
        print(">>>>111>>>>>>>sale_amendment_obj>>>>>>>>>>>>", sale_amendment_obj)
        sale_amendment_line_obj = self.env['sale.order.amendment.line']
        print(">>>>111>>>>>>>sale_amendment_line_obj>>>>>>>>>>>>", sale_amendment_line_obj)
        amendment_reason = ""
        sale_history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            sale_order = each.order_id
            if sale_order.amendment_reason:
                amendment_reason = '\n' + sale_order.amendment_reason
            if sale_order.sale_history:
                sale_history = '\n' + sale_order.sale_history
                
            sale_order.amendment_reason = each.amendment_reason + "\nby " + self.env.user.name + " on " + date + amendment_reason 
            sale_order.amendment_user_id = self.env.user.id
            sale_order.sale_amendment_no = sale_order.sale_amendment_no + 1
            sale_order.sale_history = "Order amended by " + self.env.user.name + " on " + date + sale_history

            sale_order._action_cancel()
            sale_order.action_unlock()
            sale_order.action_draft()

            sale_amendment_id = sale_amendment_obj.create({
                'sale_id': sale_order.id,
                'name': sale_order.name,
                'origin': sale_order.origin,
                'client_order_ref': sale_order.client_order_ref,
                'state': sale_order.state,
                'date_order': sale_order.date_order,
                'validity_date': sale_order.validity_date,
                'confirmation_date': sale_order.confirmation_date,
                'user_id': sale_order.user_id and sale_order.user_id.id or False,
                'partner_id': sale_order.partner_id and sale_order.partner_id.id or False,
                'partner_invoice_id': sale_order.partner_invoice_id and sale_order.partner_invoice_id.id or False,
                'partner_shipping_id': sale_order.partner_shipping_id and sale_order.partner_shipping_id.id or False,
                'pricelist_id': sale_order.pricelist_id and sale_order.pricelist_id.id or False,
                # 'project_id': sale_order.project_id and sale_order.project_id.id or False,
                'currency_id': sale_order.currency_id and sale_order.currency_id.id or False,
                'invoice_status': sale_order.invoice_status and sale_order.invoice_status or '',
                'note': sale_order.note and sale_order.note or '',
                'amount_untaxed': sale_order.amount_untaxed,
                'amount_discounted': sale_order.amount_discounted,
                'amount_tax': sale_order.amount_tax,
                'amount_roundoff': sale_order.amount_roundoff,
                'amount_total': sale_order.amount_total,
                'payment_term_id': sale_order.payment_term_id and sale_order.payment_term_id.id or False,
                'fiscal_position_id': sale_order.fiscal_position_id and sale_order.fiscal_position_id.id or False,
                'company_id': sale_order.company_id and sale_order.company_id.id or False,
                'team_id': sale_order.team_id and sale_order.team_id.id or False,
                'sales_manager_id': sale_order.sales_manager_id and sale_order.sales_manager_id.id or False,
                'incoterm': sale_order.incoterm and sale_order.incoterm or False,
                'picking_policy': sale_order.picking_policy and sale_order.picking_policy or '',
                'warehouse_id': sale_order.warehouse_id and sale_order.warehouse_id.id or False,
                'credit_limit': sale_order.credit_limit,
                'avail_credit_limit': sale_order.avail_credit_limit,
                'approved_so_value': sale_order.approved_so_value,
                'invoice_due': sale_order.invoice_due,
                'credit_limit_check': sale_order.credit_limit_check or '',
                'payment_term_check': sale_order.payment_term_check or '',
                'approved_user_id': sale_order.approved_user_id and sale_order.approved_user_id.id or False,
                'approved_date': sale_order.approved_date and sale_order.approved_date or False,
                'exp_delivery_date': sale_order.exp_delivery_date and sale_order.exp_delivery_date or False,
                'revision_user_id': sale_order.revision_user_id and sale_order.revision_user_id.id or False, 
                'cancel_user_id': sale_order.cancel_user_id and sale_order.cancel_user_id.id or False,
                'sale_revision_no': sale_order.sale_revision_no,
                'amendment_user_id': self.env.user.id, 
                'sale_amendment_no': sale_order.sale_amendment_no,
                'higher_reason': sale_order.higher_reason or '',
                'amendment_reason': sale_order.amendment_reason or '',
                'revision_reason': sale_order.revision_reason or '',
                'cancel_reason': sale_order.cancel_reason or '',
                'sale_remarks': sale_order.sale_remarks or '',
                'sale_history': sale_order.sale_history or '',
                })
            print(">>>>>>2>>>>>sale_amendment_obj>>>>>>>>>>>>",sale_amendment_obj)
            for line in sale_order.order_line:
                sale_amendment_line_obj.create({
                    'order_id': sale_amendment_id.id,
                    'name': line.name,
                    'sequence': line.sequence,
                    'invoice_status': line.invoice_status,
                    'price_unit': line.price_unit,
                    'tax_id':  [(6, 0, line.tax_id.ids)],
                    'price_subtotal': line.price_subtotal,
                    'discount': line.discount,
                    'product_id': line.product_id and line.product_id.id or False,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_uom and line.product_uom.id or False,
                    #error
                    # 'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                    'customer_lead': line.customer_lead,
                    #error
                    # 'product_packaging': line.product_packaging and line.product_packaging.id or False,
                    # 'route_id': line.route_id and line.route_id.id or False,
                    # error
                    # 'layout_category_id': line.layout_category_id and line.layout_category_id.id or False,
                    'sales_user_id': line.sales_user_id and line.sales_user_id.id or False,
                  })
            print(">>>>>>3>>>>>sale_amendment_obj>>>>>>>>>>>>",sale_amendment_obj)
        # return {'type': 'ir.actions.act_window_close'}
        
#SaleOrderAmendmentWizard()
    
class SaleOrderHigherApprovalWizard(models.TransientModel):
    _name = 'sale.order.higher.approval.wizard'
    _description = 'Sales Order Higher Approval Wizard'
    
    order_id = fields.Many2one('sale.order', string='Order Reference', required=True, copy=False, readonly=True)
    higher_reason = fields.Text('Reason', required=True, copy=False)
    
    @api.model
    def default_get(self, fields):
        if len(self.env.context.get('active_ids', list())) > 1:
            raise UserError("You may split one quotation at a time!")
        res = super(SaleOrderHigherApprovalWizard, self).default_get(fields)

        sale_obj = self.env['sale.order']
        sale_order = sale_obj.browse(self.env.context.get('active_id'))
        if sale_order:
            res.update({'order_id': sale_order.id})
            if sale_order.state == 'done':
                raise UserError("You cannot cancel the order which is confirmed already!")
        return res
        
    #@api.multi
    def action_request(self):
        higher_reason = ""
        sale_history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            sale_order = each.order_id
            if sale_order.higher_reason:
                higher_reason = '\n' + sale_order.higher_reason
            if sale_order.sale_history:
                sale_history = '\n' + sale_order.sale_history
            sale_order.write({'higher_reason': each.higher_reason + "\nby " + self.env.user.name + " on " + date + higher_reason, 
                'sale_history': "Requested for higher approval by " + self.env.user.name + " on " + date + sale_history})
            sale_order.action_send_for_higher_approval()
        return {'type': 'ir.actions.act_window_close'}   
        
#SaleOrderHigherApprovalWizard()
