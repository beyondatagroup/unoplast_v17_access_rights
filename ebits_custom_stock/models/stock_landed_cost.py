# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import time
from collections import namedtuple
from datetime import datetime
from dateutil import relativedelta

from odoo import api, fields, models, tools, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

from collections import defaultdict
from odoo.addons.stock_landed_costs.models import product

import logging

_logger = logging.getLogger(__name__)

SPLIT_METHOD = [
    ('equal', 'Equal'),
    ('by_quantity', 'By Quantity'),
    ('by_current_cost_price', 'By Current Cost'),
    ('by_weight', 'By Weight'),
    ('by_volume', 'By Volume'),
]


class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    landed_percentage = fields.Float(string="Landed Calculation Percentage", help="Percentage must be 0.00% t0 100.00%", digits=(16, 4))

    include_lc_product_ids = fields.Many2many('product.product', 'lc_expenses_product_product_rel', 'product_id', 'lc_expenses_id', string="Inclusive of Lc Type", help="This will be included with the costing value")
    

class LandedCost(models.Model):
    _inherit = 'stock.landed.cost'
    
    #lc_no = fields.Char(string="LC No", readonly=True, states={'draft': [('readonly', False)]}, copy=False)
    lc_no_id = fields.Many2one('purchase.order.lc.master', string='LC No',  copy=False)
    purchase_id = fields.Many2one('purchase.order', string="Purchase Order",  copy=False)
    name = fields.Char(string='Name', default='New #', copy=False, readonly=True)
    lc_journal_lines = fields.One2many('landed.cost.journal.lines', 'cost_id' , string='Journal lines', readonly=True)


#    
#    def compute_landed_cost(self):
#        AdjustementLines = self.env['stock.valuation.adjustment.lines']
#        res = super(LandedCost, self).compute_landed_cost()
#        picking_product_qty = {}
#        for cost in self.filtered(lambda cost: cost.picking_ids):
#            total_qty = 0.0
#            all_val_line_values = cost.get_valuation_lines()
#            for val_line_values in all_val_line_values:
#                if val_line_values['product_id'] in picking_product_qty:
#                    picking_product_qty[val_line_values['product_id']] += val_line_values.get('quantity', 0.0)
#                else:
#                    picking_product_qty[val_line_values['product_id']] = val_line_values.get('quantity', 0.0)
#            for each_picking_product in picking_product_qty:
#                for each_line in cost.purchase_id.lc_line:
#                    cost_amount = total_cost = 0.00
#                    if each_line.po_product_id.id == each_picking_product:
#                        cost_per_qty = each_line.amount / each_line.product_qty
#                        total_cost = cost_per_qty * picking_product_qty[each_picking_product]
#                        AdjustementLines.create({
#                            'purchase_id': each_line.order_id.id,
#                            'cost_id': cost.id,
#                            'product_id': each_line.po_product_id.id,
#                            'cost_product_id': each_line.lc_expense_id.id,
#                            'quantity': picking_product_qty[each_picking_product],
#                            'weight': 0.00,
#                            'volume': 0.00,
#                            'former_cost': total_cost,
#                            'additional_landed_cost': 0.00,
#                        })
#        return res

    
    def button_validate(self):
        if any(cost.state != 'draft' for cost in self):
            raise UserError(_('Only draft landed costs can be validated'))
        if any(not cost.valuation_adjustment_lines for cost in self):
            raise UserError(_('No valuation adjustments lines. You should maybe recompute the landed costs.'))
#        if not self._check_sum():
#            raise UserError(_('Cost and adjustments lines do not match. You should maybe recompute the landed costs.'))

        for cost in self:
            if cost.name == 'New #':
                cost.name = self.env['ir.sequence'].next_by_code('stock.landed.cost') or 'New #'

            move = self.env['account.move']
            move_vals = {
                'journal_id': cost.account_journal_id.id,
                'date': cost.date,
                'ref': cost.name and (cost.name + (cost.lc_no_id and " / " + cost.lc_no_id.name or "")) or (cost.lc_no_id and cost.lc_no_id.name or ""),
                'lc_no_id': cost.lc_no_id and cost.lc_no_id.id or False,
                'line_ids': [],
            }
            for picking in cost.picking_ids:
                picking.lc_booked = True
            for line in cost.valuation_adjustment_lines.filtered(lambda line: line.move_id):
                per_unit = line.final_cost / line.quantity
                diff = per_unit - line.former_cost

                # If the precision required for the variable diff is larger than the accounting
                # precision, inconsistencies between the stock valuation and the accounting entries
                # may arise.
                # For example, a landed cost of 15 divided in 13 units. If the products leave the
                # stock one unit at a time, the amount related to the landed cost will correspond to
                # round(15/13, 2)*13 = 14.95. To avoid this case, we split the quant in 12 + 1, then
                # record the difference on the new quant.
                # We need to make sure to able to extract at least one unit of the product. There is
                # an arbitrary minimum quantity set to 2.0 from which we consider we can extract a
                # unit and adapt the cost.
                curr_rounding = line.move_id.company_id.currency_id.rounding
                diff_rounded = tools.float_round(diff, precision_rounding=curr_rounding)
                diff_correct = diff_rounded
                quants = line.move_id.quant_ids.sorted(key=lambda r: r.qty, reverse=True)
                quant_correct = False
                if quants\
                        and tools.float_compare(quants[0].product_id.uom_id.rounding, 1.0, precision_digits=1) == 0\
                        and tools.float_compare(line.quantity * diff, line.quantity * diff_rounded, precision_rounding=curr_rounding) != 0\
                        and tools.float_compare(quants[0].qty, 2.0, precision_rounding=quants[0].product_id.uom_id.rounding) >= 0:
                    # Search for existing quant of quantity = 1.0 to avoid creating a new one
                    quant_correct = quants.filtered(lambda r: tools.float_compare(r.qty, 1.0, precision_rounding=quants[0].product_id.uom_id.rounding) == 0)
                    if not quant_correct:
                        quant_correct = quants[0]._quant_split(quants[0].qty - 1.0)
                    else:
                        quant_correct = quant_correct[0]
                        quants = quants - quant_correct
                    diff_correct += (line.quantity * diff) - (line.quantity * diff_rounded)
                    diff = diff_rounded

                quant_dict = {}
                for quant in quants:
                    quant_dict[quant] = quant.cost + diff
                if quant_correct:
                    quant_dict[quant_correct] = quant_correct.cost + diff_correct
                for quant, value in quant_dict.items():
                    quant.sudo().write({'state': 'done','cost': value})
                qty_out = 0
                for quant in line.move_id.quant_ids:
                    if quant.location_id.usage != 'internal':
                        qty_out += quant.qty
                move_vals['line_ids'] += line._create_accounting_entries(move, qty_out)
            move = move.create(move_vals)
            cost.write({'account_move_id': move.id})
            move._post()
            # move.with_context().action_post()
            for adjustment_line in cost.valuation_adjustment_lines:
                if adjustment_line.sudo().po_landed_line_id and cost.picking_ids:
                    adjustment_line.sudo().po_landed_line_id.picking_ids = cost.picking_ids
        return True
        

    def compute_landed_cost(self):
        AdjustementLines = self.env['stock.valuation.adjustment.lines']
        AdjustementLines.search([('cost_id', 'in', self.ids)]).unlink()

        digits = self.env['decimal.precision'].precision_get('Product Price')
        towrite_dict = {}
        picking_product_qty = {}
        for cost in self.filtered(lambda cost: cost.picking_ids):
            total_qty = 0.0
            total_cost = 0.0
            total_weight = 0.0
            total_volume = 0.0
            total_line = 0.0
            all_val_line_values = cost.get_valuation_lines()
            for val_line_values in all_val_line_values:
                for cost_line in cost.cost_lines:
                    val_line_values.update({'cost_id': cost.id, 'cost_line_id': cost_line.id, 'cost_product_id': cost_line.product_id.id,})
                    cost_line_ids =  self.env['stock.valuation.adjustment.lines'].create(val_line_values)
                    cost_line_ids.cost_line_id.account_id = cost_line.product_id.property_account_expense_id.id
                total_qty += val_line_values.get('quantity', 0.0)
                total_cost += val_line_values.get('former_cost', 0.0)
                total_weight += val_line_values.get('weight', 0.0)
                total_volume += val_line_values.get('volume', 0.0)
                total_line += 1

            for line in cost.cost_lines:
                value_split = 0.0
                for valuation in cost.valuation_adjustment_lines:
                    value = 0.0
                    if valuation.cost_line_id and valuation.cost_line_id.id == line.id:
                        if line.split_method == 'by_quantity' and total_qty:
                            per_unit = (line.price_unit / total_qty)
                            value = valuation.quantity * per_unit
                        elif line.split_method == 'by_weight' and total_weight:
                            per_unit = (line.price_unit / total_weight)
                            value = valuation.weight * per_unit
                        elif line.split_method == 'by_volume' and total_volume:
                            per_unit = (line.price_unit / total_volume)
                            value = valuation.volume * per_unit
                        elif line.split_method == 'equal':
                            value = (line.price_unit / total_line)
                        elif line.split_method == 'by_current_cost_price' and total_cost:
                            per_unit = (line.price_unit / total_cost)
                            value = valuation.former_cost * per_unit
                        else:
                            value = (line.price_unit / total_line)

                        if digits:
                            value = tools.float_round(value, precision_digits=digits, rounding_method='UP')
                            fnc = min if line.price_unit > 0 else max
                            value = fnc(value, line.price_unit - value_split)
                            value_split += value

                        if valuation.id not in towrite_dict:
                            towrite_dict[valuation.id] = value
                        else:
                            towrite_dict[valuation.id] += value
            for val_line_values in all_val_line_values:
                move_bro = self.env['stock.move'].browse(val_line_values['move_id'])
                for each_line in cost.purchase_id.lc_line:
                    pick_ids = []
                    for each_pick in each_line.picking_ids:
                        pick_ids.append(each_pick.id)
                    if move_bro.picking_id.id not in pick_ids:
                        cost_amount = total_cost = 0.00
                        if each_line.po_product_id.id == val_line_values['product_id']:
                            cost_per_qty = each_line.amount / each_line.product_qty
                            total_cost = cost_per_qty * val_line_values['quantity']
                            AdjustementLines.create({
                                'purchase_id': each_line.order_id.id,
                                'po_landed_line_id': each_line.id,
                                'cost_id': cost.id,
                                'product_id': each_line.po_product_id.id,
                                'cost_product_id': each_line.lc_expense_id.id,
                                'quantity': val_line_values['quantity'],
                                'weight': 0.00,
                                'volume': 0.00,
                                'former_cost': val_line_values['former_cost'],
                                'additional_landed_cost': total_cost,
                                'move_id': val_line_values['move_id'],
                            })
        if towrite_dict:
            for key, value in towrite_dict.items():
                AdjustementLines.browse(key).write({'additional_landed_cost': value})

        return True
    
    def update_journal_item_data(self):
        move_line_obj = self.env['account.move.line']
        journal_line_obj = self.env['landed.cost.journal.lines']
        move_line_dict = {}
        move_line_list = []
        for each in self:
            models.Model.unlink(each.lc_journal_lines)
            move_line_search = move_line_obj.search([('lc_no_id', '=', each.lc_no_id.id), ('debit', '>', 0.00), ('account_id', 'in', self.env.user.company_id.lc_account_ids.ids)])
            for move_line in move_line_search:
                move_line_dict = {
                    'entry_id': move_line.move_id and move_line.move_id.id or False,
                    'account_id': move_line.account_id and move_line.account_id.id or  False,
                    'name': move_line.name and move_line.name or '',
                    'debit': move_line.debit, 
                    'cost_id': each.id 
                }
                move_line_list.append(move_line_dict)
        for line in move_line_list:
            journal_line_obj.create(line)



# FOR TESTING AFTER REMOVE #### 
# class AccountConfigSettings(models.TransientModel):
#     _inherit = 'account.config.settings'

#     group_proforma_invoices = fields.Boolean(string='Allow Approval in invoices',
#         implied_group='account.group_proforma_invoices',
#         help="Allows you to put invoices in pending for approval state.")
#     lc_account_ids = fields.Many2many('account.account', 'etc_account_config_res_company_rela', 'config_id', 'account_id', related='company_id.lc_account_ids', string="LC Account(s)", help="This is the default account which will be used in the LC form journal entries filter.")
                    
        
class LandedCostLine(models.Model):
    _inherit = 'stock.landed.cost.lines'
    
    split_method = fields.Selection(selection=SPLIT_METHOD, string='Split Method', required=True, default='by_current_cost_price')
    
    @api.onchange('product_id')
    def onchange_product_id_custom(self):
        # if not self.product_id:
        #     self.quantity = 0.0
        self.account_id = self.product_id.property_account_expense_id.id
        self.split_method = 'by_current_cost_price'
        
class AdjustmentLines(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'
    
    purchase_id = fields.Many2one('purchase.order', string="Purchase Order", readonly=True, copy=False)
    po_landed_line_id = fields.Many2one('purchase.order.landed.cost.line', string="Purchase LC Cost Line", readonly=True, copy=False)
    name = fields.Char('Description', compute='_compute_name', store=True)
    cost_product_id = fields.Many2one('product.product', 'Costing Product')
    product_id = fields.Many2one('product.product', 'Incoming Product', required=True)
        
    
    @api.depends('cost_line_id.name', 'product_id.code', 'product_id.name', 'purchase_id')
    def _compute_name(self):
        for record in self:
            if record.purchase_id:
                name = '%s - ' % (record.purchase_id.name if record.purchase_id else '')
            else:
                # If there are multiple cost_line_ids, decide how to handle them
                cost_line_name = ', '.join(record.cost_line_id.mapped('name')) if record.cost_line_id else ''
                name = '%s - ' % cost_line_name
            record.name = name + (record.product_id.code or record.product_id.name or '')
        
    def _create_accounting_entries(self, move, qty_out):
        # TDE CLEANME: product chosen for computation ?
        cost_product = self.cost_product_id
        if not cost_product:
            return False
        accounts = self.product_id.product_tmpl_id.get_product_accounts()
        
        debit_account_id = accounts.get('stock_valuation') and accounts['stock_valuation'].id or False
        already_out_account_id = accounts['stock_output'].id

        credit_account_id = self.cost_line_id.account_id.id or cost_product.property_account_expense_id.id or cost_product.categ_id.property_account_expense_categ_id.id# self.product_id.property_account_expense_id.id

        if not credit_account_id:
            raise UserError(_('Please configure Stock Expense Account for product: %s.') % (cost_product.name))

        return self._create_account_move_line(move, credit_account_id, debit_account_id, qty_out, already_out_account_id)
        
class LandedCosJounrnalLines(models.Model):
    _name = "landed.cost.journal.lines"
    _description = "Landed Cost Journal Lines"
    
    cost_id = fields.Many2one('stock.landed.cost', string='Stock Landed Cost')
    entry_id = fields.Many2one('account.move', string='Journal Entry')
    account_id = fields.Many2one('account.account', string='Account')
    name = fields.Char(string='Label')
    debit = fields.Float(string='Debit')
        
