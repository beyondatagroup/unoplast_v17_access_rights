# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
import pytz
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp

class PurchaseCancelReasonWizard(models.TransientModel):
    _name = "purchase.cancel.reason.wizard"
    _description = "Purchase Requisition Cancel Reason"
    
    name = fields.Text(string='Cancel Reason', required=True)
    purchase_req_id = fields.Many2one('purchase.requisition.extend', string="PR", required=True)
    
    # @api.multi
    def action_cancel(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            purchase_req_id = each.purchase_req_id
            if purchase_req_id.history:
                history = purchase_req_id.history + "\n"  
            purchase_req_id.state = 'cancel'
            purchase_req_id.history = history + 'This document is cancelled by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name 

class PurchaseResendReasonWizard(models.TransientModel):
    _name = "purchase.resend.reason.wizard"
    _description = "Purchase Requisition Resend Reason"
    
    name = fields.Text(string='Reason for Resend', required=True)
    purchase_req_id = fields.Many2one('purchase.requisition.extend', string="PR", required=True)
    
    # @api.multi
    def action_resend(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        history = ""
        for each in self:
            purchase_req_id = each.purchase_req_id
            if purchase_req_id.history:
                history = purchase_req_id.history + "\n" 
            purchase_req_id.write({
                'state': 'draft',
                'history': history + 'This document is resent to draft by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name,
                'one_approved_id': False, 
                'one_approved_date': False, 
                'two_approved_id': False,
                'two_approved_date': False,
                'one_approver_ids': [],
                'two_approver_ids': [],
            })
            
class PurchaseRequisitionWizard(models.TransientModel):
    _name = "purchase.requisition.wizard"
    _description = "Purchase Requisition Wizard"
    
    order_id = fields.Many2one('purchase.order', string='Purchase Order No', readonly=True)
    requisition_line = fields.One2many('purchase.requisition.line.wizard', 'pr_wizard_id', string='PR Line Wizard')
    
    @api.model
    def default_get(self, fields):
        res = super(PurchaseRequisitionWizard, self).default_get(fields)
        purchase_order_id = self.env['purchase.order'].browse(self.env.context.get('active_id')) 
        res['order_id'] = purchase_order_id and purchase_order_id.id or False 
        pr_line_search = self.env['po.requisition.item.lines'].search([('state', '=', 'approved'), ('to_ordered_qty', "!=", 0.00), ('requisition_id.category_id', '=', purchase_order_id.category_id.id), ('force_close', '=', False)])
        requisition_line = []
        for line in pr_line_search:
            purchase_line = {}
            purchase_line['requisition_id'] = line.requisition_id and line.requisition_id.id or False
            purchase_line['product_id'] = line.product_id and line.product_id.id or False
            purchase_line['uom_id'] = line.uom_id and line.uom_id.id or False
            purchase_line['date_required'] = line.date_required and line.date_required or False
            purchase_line['date_requisition'] = line.date_requisition and line.date_requisition or False
            purchase_line['approved_qty'] = line.approved_qty and line.approved_qty or 0.00
            purchase_line['po_ordered_qty'] = line.ordered_qty and line.ordered_qty or 0.00
            purchase_line['pending_qty'] = line.to_ordered_qty
            purchase_line['pr_line_id'] = line.id
            requisition_line.append((0, 0, purchase_line)) 
        res.update({"requisition_line": requisition_line}) 
        return res

    @api.model
    def _get_date_planned(self, seller, po=False):
        date_order = po.date_order if po else self.order_id.date_order
        if date_order:
            return datetime.strptime(date_order, DEFAULT_SERVER_DATETIME_FORMAT) + relativedelta(days=seller.delay if seller else 0)
        else:
            return datetime.today() + relativedelta(days=seller.delay if seller else 0)
        
    # @api.multi
    def action_get_product_list(self):
        po_line_obj = self.env['purchase.order.line']
        pr_line_obj = self.env['po.requisition.item.lines']
        po_pr_link_obj = self.env['po.pr.link.line']
        dict_req_line = {}
        po_approved = False
        for each in self:
            for line in each.requisition_line:
                if line.po_approved == True:
                    po_approved = True
                    if line.product_id.id in dict_req_line:
                        dict_req_line[line.product_id.id]['product_qty'] += line.pending_qty
                        dict_req_line[line.product_id.id]['requisition_line_id'].append((line.pr_line_id.id, line.pending_qty))
                    else:
                        # dict_req_line[line.product_id.id] = {}
                        dict_req_line[line.product_id.id] = {
                            'product_id' : line.product_id and line.product_id.id or False ,
                            'product_uom' : line.uom_id and line.uom_id.id or False,
                            # 'name' : line.product_id.name_get()[0][1],
                            'description' : line.product_id.name,
                            'date_planned' : line.date_required and line.date_required or False,
                            'product_qty' : line.pending_qty,
                            'price_unit' : 0.00,
                            'order_id' : each.order_id.id,
                            'requisition_line_id' : [],
                            }
                        dict_req_line[line.product_id.id]['requisition_line_id'].append((line.pr_line_id.id, line.pending_qty))
        if not po_approved:
            raise UserError(_("Unable to process.Select atleast one item!!!."))
        if each.order_id.order_line:
            for each_line in dict_req_line:
                updated = False
                for order_line in each.order_id.order_line:
                    if order_line.product_id.id == each_line:
                        order_line.product_qty += dict_req_line[each_line]['product_qty']
                        updated = True
                        for each_pr_line_id in dict_req_line[each_line]['requisition_line_id']:
                            po_pr_link_obj.create({'pr_line_id': each_pr_line_id[0],
                                'order_line_id': order_line.id,
                                'pr_qty': each_pr_line_id[1]})
                if not updated:
                    price_unit = 0.00
                    pol_id = po_line_obj.create({
                        'product_id': dict_req_line[each_line]['product_id'],
                        'product_uom': dict_req_line[each_line]['product_uom'],
                        'name': dict_req_line[each_line]['name'],
                        'date_planned': dict_req_line[each_line]['date_planned'],
                        'pr_qty': dict_req_line[each_line]['product_qty'],
                        'product_qty': dict_req_line[each_line]['product_qty'],
                        'price_unit': dict_req_line[each_line]['price_unit'],
                        'order_id': dict_req_line[each_line]['order_id'],
                        })
                    seller = pol_id.product_id._select_seller(
                        partner_id=each.order_id.partner_id,
                        quantity=pol_id.product_qty,
                        date=each.order_id.date_order and each.order_id.date_order[:10],
                        uom_id=pol_id.product_uom)

                    if seller or not pol_id.date_planned:
                        date_planned = pol_id._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

                    if not seller:
                        price_unit = 0.00
                    else:
                        price_unit = self.env['account.tax']._fix_tax_included_price(seller.price, pol_id.product_id.supplier_taxes_id, pol_id.taxes_id) if seller else 0.0
                        if price_unit and seller and each.order_id.currency_id and seller.currency_id != each.order_id.currency_id:
                            price_unit = seller.currency_id.compute(price_unit, each.order_id.currency_id)

                        if seller and pol_id.product_uom and seller.product_uom != pol_id.product_uom:
                            price_unit = seller.product_uom._compute_price(price_unit, pol_id.product_uom)
                    pol_id.price_unit = price_unit
                    for each_pr_line_id in dict_req_line[each_line]['requisition_line_id']:
                        po_pr_link_obj.create({'pr_line_id': each_pr_line_id[0],

                            'order_line_id': pol_id.id,
                            'pr_qty': each_pr_line_id[1]})
        else:
            for each_line in dict_req_line:
                price_unit = 0.00
                pol_id = po_line_obj.create({
                        'product_id': dict_req_line[each_line]['product_id'],
                        'product_uom': dict_req_line[each_line]['product_uom'],
                        'name': dict_req_line[each_line]['description'],
                        'date_planned': dict_req_line[each_line]['date_planned'],
                        'pr_qty': dict_req_line[each_line]['product_qty'],
                        'product_qty': dict_req_line[each_line]['product_qty'],
                        'price_unit': dict_req_line[each_line]['price_unit'],
                        'order_id': dict_req_line[each_line]['order_id'],
                        })
                seller = pol_id.product_id._select_seller(
                        partner_id=each.order_id.partner_id,
                        quantity=pol_id.product_qty,
                        date=each.order_id.date_order ,
                        uom_id=pol_id.product_uom)

                if seller or not pol_id.date_planned:
                    date_planned = pol_id._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

                if not seller:
                    price_unit = 0.00
                else:
                    price_unit = self.env['account.tax']._fix_tax_included_price(seller.price, pol_id.product_id.supplier_taxes_id, pol_id.taxes_id) if seller else 0.0
                    if price_unit and seller and each.order_id.currency_id and seller.currency_id != each.order_id.currency_id:
                        price_unit = seller.currency_id.compute(price_unit, each.order_id.currency_id)

                    if seller and pol_id.product_uom and seller.product_uom != pol_id.product_uom:
                        price_unit = seller.product_uom._compute_price(price_unit, pol_id.product_uom)
                pol_id.price_unit = price_unit
                print("\n\n\n...dict_req_line[each_line]['requisition_line_id']...........",dict_req_line[each_line]['requisition_line_id'])
                for each_pr_line_id in dict_req_line[each_line]['requisition_line_id']:
                    po_pr_link_obj.create({'pr_line_id': each_pr_line_id[0],
                        'order_line_id': pol_id.id,
                        'pr_qty': each_pr_line_id[1]})
        return True
        
    def action_select_all(self):
        self.write({})
        for each in self:
            if each.requisition_line:
                for line in each.requisition_line:
                    line.po_approved = True
                    line.pending_qty = line.approved_qty - line.po_ordered_qty
            else:
                raise UserError(_("Unable to process.No line to select."))
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'purchase.requisition.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    def action_deselect_all(self):
        self.write({})
        for each in self:
            if each.requisition_line:
                for line in each.requisition_line:
                    line.po_approved = False
                    line.pending_qty = 0.00
            else:
                raise UserError(_("Unable to process.No line to deselect."))
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'purchase.requisition.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
        
class PurchaseRequisitionLineWizard(models.TransientModel):
    _name = "purchase.requisition.line.wizard"
    _description = "Purchase Requisition Line Wizard" 
    
    pr_wizard_id = fields.Many2one('purchase.requisition.wizard',store=True, string="Purchase Requisition Wizard")
    requisition_id = fields.Many2one('purchase.requisition.extend', string='PR Number', readonly=True,store=True, )
    product_id = fields.Many2one('product.product', string='Product', readonly=True,store=True,)
    uom_id = fields.Many2one('uom.uom', string='UOM', readonly=True,store=True, )
    date_required = fields.Date(string='Required Date', readonly=True,store=True, )
    date_requisition = fields.Date(string='Requisition Date', readonly=True,store=True, )
    approved_qty = fields.Float(string='Approved Qty', digits='Product Unit of Measure', readonly=True,store=True, )
    po_approved = fields.Boolean(string='Approved for PO',store=True, )
    po_ordered_qty = fields.Float(string='Ordered Qty', digits='Product Unit of Measure', readonly=True,store=True, )
    pending_qty = fields.Float(string='Qty to Order', digits='Product Unit of Measure',store=True, )
    pr_line_id = fields.Many2one('po.requisition.item.lines', string='PR Line',store=True, )
    
    
    @api.onchange('pending_qty', 'approved_qty', 'po_ordered_qty')
    def onchange_pending_qty(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.pending_qty:
            if (self.approved_qty - self.po_ordered_qty) < self.pending_qty:
                warning = {
                    'title': _('Warning'),
                    'message': _('You cannnot give more than the qty to order')}
                self.pending_qty = self.approved_qty - self.po_ordered_qty
                return {'warning': warning}
            if not self.uom_id.allow_decimal_digits:
                integer, decimal = divmod(self.pending_qty, 1)
                if decimal:
                    self.pending_qty = self.approved_qty - self.po_ordered_qty
                    warning = {
                            'title': _('Warning'),
                            'message': _('You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the qty to order should not contains decimal value') % (self.uom_id.name)}
                    return {'warning': warning}

        return {'warning': warning}
        
class PurchaseForceClosedReasonWizard(models.TransientModel):
    _name = "purchase.force.closed.reason.wizard"
    _description = "Purchase Requisition Force Close Reason"
    
    name = fields.Text(string='Force Close Reason', required=True)
    
    # @api.multi
    def action_force_closed(self):
        purchase_req_line_id = self.env['po.requisition.item.lines'].browse(self.env.context.get('active_id'))
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        reason = ""
        for each in self:
            if purchase_req_line_id.requisition_id.force_closed_reason:
                reason = purchase_req_line_id.requisition_id.force_closed_reason + "\n"  
            purchase_req_line_id.force_close = True
            purchase_req_line_id.requisition_id.force_closed_reason = reason + 'This ' + purchase_req_line_id.product_id.name + ' product is force closed by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name 
        return True
