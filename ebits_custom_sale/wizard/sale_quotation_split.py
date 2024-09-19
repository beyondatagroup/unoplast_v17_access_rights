# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
import pytz
import datetime
import time

class SaleOrderLineSplitWizard(models.TransientModel):
    _name = 'sale.order.line.split.wizard'
    _description = 'Sales Order Line Split Wizard'
    
    order_id = fields.Many2one('sale.order', string='Order Reference', required=True, copy=False, readonly=True)
    order_line = fields.One2many('sale.order.line.split', 'split_wizard_id', string='Split Wizard Lines',
                                 copy=True)
    backorder = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'Not Required'),
        ], string='Create Backorder', required=True, copy=False)
    
    @api.model
    def default_get(self, fields):
        if len(self.env.context.get('active_ids', list())) > 1:
            raise UserError("You may split one quotation at a time!")
        res = super(SaleOrderLineSplitWizard, self).default_get(fields)

        sale_obj = self.env['sale.order']
        sale_lines = []
        sale_order = sale_obj.browse(self.env.context.get('active_id'))
        if sale_order:
            res.update({'order_id': sale_order.id})
            if sale_order.state in ['sale', 'done']:
                raise UserError("You cannot split the order which is confirmed already!")
            for line in sale_order.order_line:
                sale_lines.append((0, 0, {
                    'order_line_id': line.id,
                    'name': line.name,
                    'product_id': line.product_id.id, 
                    'product_uom_qty': line.product_uom_qty, 
                    'product_uom': line.product_uom.id,
                    'sequence': line.sequence,
                    }))
                print(">>>>>>>>>>>sale_lines>>>>>>>>>>>>>>>>",sale_lines)
            if sale_lines:
                res.update({'order_line': sale_lines})
                print(">>>>>>>>>>>res>>>>>>>>>>>>>>>>", res)
        return res
        
    #@api.multi
    def create_split(self):
        # uom_obj = self.env['product.uom']
        uom_obj = self.env['uom.uom']
        sequence_obj = self.env['ir.sequence']
        partial_datas = {}
        new_sale = None
        complete, too_many, too_few = [], [], []

        line_product_uom_qty, product_avail, partial_qty, product_uoms = {}, {}, {}, {}
        sale_history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            print(">>>>>each>>>>>>>>>>>>",each)
            sale_order = each.order_id
            if sale_order.state in ['sale', 'done']:
                raise UserError("You cannot split the order which is confirmed already!")
            if sale_order.sale_history:
                sale_history = '\n' + sale_order.sale_history
            for wizard_line in each.order_line:
                print(">>>>>>>>>>>each.order_line>>>>>>>>>>>>>>>>>>", wizard_line)
                if wizard_line.current_qty <= 0:
                    raise UserError("Please provide proper Quantity to split or remove the line.!")
###############################################changed the logic
                active_model = self._context.get('active_model')
                print(">>>>>>>>>>>each.active_model>>>>>>>>>>>>>>>>>>", active_model)
                active_id = self._context.get('active_id')
                print(">>>>>>>>>>>each.active_id>>>>>>>>>>>>>>>>>>", active_id)
                ticket_obj = self.env[active_model].browse(active_id)
                print(">>>>>>>>>>>each.ticket_obj>>>>>>>>>>>>>>>>>>", ticket_obj, ticket_obj.order_line)

                for wizard_line_new in ticket_obj.order_line:

                    print(">>>>>>>>>>>>>>>>>>wizard_line_new>>>>>>>>>>>>>>>>>>>>>>>>",wizard_line_new)
                    print(">>>>>>>>>>>>>>>>>>wizard_line_new>>>>>>>>>>>prod>>>>>>>>>>>>>",wizard_line_new.product_id.id)
                    print(">>>>>>>>>>>>>>>>>>wizard_line_new>>>>>>>>>>>>>>name>>>>>>>>>>",wizard_line_new.name)

                    print(">>>>>>>>>>>>wizard_line>>>>>>>>>>>>>>>>>>>>>>",wizard_line)
                    print(">>>>>>>>>>>>wizard_line>>>>>>>product_id.id>>>>>>>>>>>>>>>",wizard_line.product_uom.id,
                          self.order_line.product_id.id)
                    print(">>>>>>>>>>>>wizard_line.product_uom.id>>>>>>>>>>>>>>>>>>>>>>",wizard_line.product_uom.id)
                    print(">>>>>>>>>>>>wizard_line.nam>>>>>>>>>>>>>>>>>>>>>>",wizard_line.name)
                    print(">>>>>>>>>>>>wizard_line>>>>>>>>>>>>>>>>>>>>>>",self.order_line)
                    # print(">>>>>>>>>>>>wizard_line>>>>>>>>>>>>>>>>>>>>>>",wizard_line)

                    partial_datas['line%s' % (wizard_line_new)] = {
                        'order_line_id': wizard_line_new.id,
                        'product_id': wizard_line_new.product_id.id,
                        'product_uom_qty': wizard_line.current_qty,
                        'product_uom': wizard_line_new.product_uom.id,
                        'name': wizard_line_new.name,
                        }
                    print(">>>>>>>>>>>partial_datas>>>>>>>>>>>>>>>>>>",partial_datas)

                    for line in sale_order.order_line:

                        #############################################################changed the logic

                        # partial_data = partial_datas.get('line%s' % (line.id), {})
                        # partial_data = partial_datas.get('line%s' % (line.id), {})
                        # product_uom_qty = partial_data.get('product_uom_qty', 0.0)
                        product_uom_qty = wizard_line.current_qty
                        print(">>>>>>>>>>>>>>>>>>product_uom_qty>>>>>>>>>>>>>>>>>>>>>>",product_uom_qty)
                        line_product_uom_qty[line.id] = product_uom_qty
                        # product_uom = partial_data.get('product_uom', False)
                        product_uom =  wizard_line_new.product_uom.id
                        print(">>>>>>>>>>>>>>>>>>product_uom>>>>>>>>>>>>>>>>>>>>>>",product_uom)
                        product_uoms[line.id] = product_uom
                        partial_uom_qty = 0.00

                        if product_uoms[line.id]:
                            partial_uom_qty = (uom_obj.browse(product_uoms[line.id]).
                                               _compute_quantity(product_uom_qty, line.product_uom))
                        else:
                            partial_uom_qty = 0.00
                        partial_qty[line.id] = partial_uom_qty

                        if line.product_uom_qty == partial_qty[line.id]:
                            complete.append(line)
                        elif line.product_uom_qty > partial_qty[line.id]:
                            too_few.append(line)
                        else:
                            too_many.append(line)

            for line in too_few:
                product_uom_qty = line_product_uom_qty[line.id]
                if not new_sale:
                    new_sale_name = sale_order.name
                    sale_order.write({'name': 'Order #'})
                    new_sale = sale_order.copy(
                            {
                                'name': new_sale_name,
                                'order_line': [],
                                'state': sale_order.state,
                                'warehouse_id': sale_order.warehouse_id.id,
                                'partner_id': sale_order.partner_id.id,
                                'partner_invoice_id': sale_order.partner_invoice_id and sale_order.partner_invoice_id.id or False,
                                'partner_shipping_id': sale_order.partner_shipping_id and sale_order.partner_shipping_id.id or False,
                                'currency_id': sale_order.currency_id and sale_order.currency_id.id or False,
                                'pricelist_id': sale_order.pricelist_id and sale_order.pricelist_id.id or False,
                                'user_id': sale_order.user_id and sale_order.user_id.id or False,
                                'team_id': sale_order.team_id and sale_order.team_id.id or False,
                                'payment_term_id': sale_order.payment_term_id and sale_order.payment_term_id.id or False,
                                'fiscal_position_id': sale_order.fiscal_position_id and sale_order.fiscal_position_id.id or False,
                                'credit_limit': sale_order.credit_limit and sale_order.credit_limit or 0.00,
                                'avail_credit_limit': sale_order.avail_credit_limit and sale_order.avail_credit_limit or 0.00,
                                'credit_limit_invisible': sale_order.credit_limit and sale_order.credit_limit or 0.00,
                                'avail_credit_limit_invisible': sale_order.avail_credit_limit and sale_order.avail_credit_limit or 0.00,
                                'approved_so_value': sale_order.approved_so_value and sale_order.approved_so_value or 0.00,
                                'approved_so_value_invisible': sale_order.approved_so_value and sale_order.approved_so_value or 0.00,
                                'invoice_due': sale_order.invoice_due and sale_order.invoice_due or 0.00,
                                'invoice_due_invisible': sale_order.invoice_due and sale_order.invoice_due or 0.00,
                                'sale_history': "Order Splited by " + self.env.user.name + " On " + date + sale_history,
                                'sales_manager_id': sale_order.sales_manager_id and sale_order.sales_manager_id.id or False,
                                'exp_delivery_date': sale_order.exp_delivery_date and sale_order.exp_delivery_date or False
                            })
                if product_uom_qty != 0:
                    defaults = {
                            'product_id': line.product_id.id,
                            'product_uom_qty' : product_uom_qty,
                            'product_uom': product_uoms[line.id],
                            'order_id' : new_sale.id,
                            'price_unit': line.price_unit,
                            'name': line.name,
                            'sequence': line.sequence,
                            'invoice_status': line.invoice_status,
                            'tax_id': [(6, 0, line.tax_id.ids)],
                            'discount': line.discount,
                            'sales_user_id': line.sales_user_id and line.sales_user_id.id or False,
                            'state': line.state,
                            }
                    line.copy(defaults)
                line.write({'product_uom_qty': line.product_uom_qty - partial_qty[line.id]})

            if new_sale:
                for c in complete: 
                    c.write({'order_id': new_sale.id})
            for line in complete:
                defaults = {'product_uom': product_uoms[line.id],
                            'product_uom_qty': line_product_uom_qty[line.id]}
                line.write(defaults)
            for line in too_many:
                product_uom_qty = line_product_uom_qty[line.id]
                defaults = {
                    'product_uom_qty' : product_uom_qty,
                    'product_uom': product_uoms[line.id]
                    }
                if new_sale:
                    defaults.update(order_id=new_sale.id)
                line.write(defaults)
            # sale_order.button_dummy()
            sale_order.action_check_credit_limit()
            if new_sale:
                if each.backorder == 'no':
                    sale_order.write({'state': 'cancel', 'cancel_user_id': self.env.user.id, 'origin': sale_order.name, 'split_sale_id': new_sale.id, 'sale_history': "Order Splited by " + self.env.user.name + " On " + date + sale_history})
                else:
                    sale_order.write({'state': 'draft', 'origin': sale_order.name, 'split_sale_id': new_sale.id, 'sale_history': "Order Splited by " + self.env.user.name + " On " + date + sale_history})
                # new_sale.button_dummy()
                new_sale.action_check_credit_limit()
                action = self.env.ref('sale.action_quotations').read()[0]
                action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
                action['res_id'] = new_sale.id
                return action
        return {'type': 'ir.actions.act_window_close'}    
        
        
class SaleOrderLineSplit(models.TransientModel):
    _name = 'sale.order.line.split'
    _description = 'Sales Order Line Split'
    _order = 'sequence, id'
    
    split_wizard_id = fields.Many2one('sale.order.line.split.wizard', string='Split Wizard Reference', ondelete="cascade", required=True, copy=False)
    # order_line_id = fields.Many2one('sale.order.line', string='Order Line Reference',required=True,store=True)
    order_line_id = fields.Many2one('sale.order.line', string='Order Line Reference',store=True)
    # name = fields.Text(string='Description', required=True, readonly=True)
    name = fields.Text(string='Description', readonly=True,store=True)
    sequence = fields.Integer(string='Sequence', default=10, readonly=True, store=True)
    # product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)], change_default=True, ondelete='restrict', required=True, readonly=True)
    product_id = fields.Many2one('product.product', string='Product',ondelete='restrict', readonly=True,store=True)
    product_uom_qty = fields.Float(string='Quantity', digits='Product Unit of Measure',
                                   required=True, default=1.0, store=True)
    current_qty = fields.Float(string='Approved Quantity', digits='Product Unit of Measure', required=True, default=0.0)
    # product_uom = fields.Many2one('uom.uom', string='Unit of Measure', required=True, readonly=True)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True,store=True)
