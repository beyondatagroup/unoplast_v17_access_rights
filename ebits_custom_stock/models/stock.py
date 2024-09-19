# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import time
from collections import namedtuple
from datetime import datetime
import pytz
from dateutil import relativedelta

from odoo import api, fields, models, _,SUPERUSER_ID
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import float_utils
import logging

_logger = logging.getLogger(__name__)

class Warehouse(models.Model):
    _inherit = "stock.warehouse"
    _sql_constraints = [
        ('warehouse_name_uniq', 'unique(name, company_id)', 'The name of the warehouse must be unique per company!'),
        ('warehouse_code_uniq', 'unique(code, company_id)', 'The short name of the warehouse must be unique per company!'),
    ]

    production_unit_id = fields.Many2one('res.production.unit', 'Unit')
    production_division_id = fields.Many2one('res.production.unit.division', 'Division')
    sale_sequence_id = fields.Many2one('ir.sequence', 'Sales Order Sequence')
    sale_journal_id = fields.Many2one('account.journal', 'Sale Invoice Journal')
    po_requisition_sequence_id = fields.Many2one('ir.sequence', 'Purchase Requisition Sequence')
    purchase_sequence_id = fields.Many2one('ir.sequence', 'Purchase Order Sequence')
    purchase_journal_id = fields.Many2one('account.journal', 'Purchase Invoice Journal')
    account_analytic_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    quality_sequence_id = fields.Many2one('ir.sequence', 'Quality Check Sequence')
    raw_material_issue_sequence_id = fields.Many2one('ir.sequence', 'Raw Material Issue Sequence')
    material_request_sequence_id = fields.Many2one('ir.sequence', 'Material Request Sequence')
    material_issue_sequence_id = fields.Many2one('ir.sequence', 'Material Issue Sequence')
    material_return_sequence_id = fields.Many2one('ir.sequence', 'Material Return Sequence')
    job_work_sequence_id = fields.Many2one('ir.sequence', 'Job Work Sequence')
    sf_mo_sequence_id = fields.Many2one('ir.sequence', 'SF MO Sequence')
    mo_sequence_id = fields.Many2one('ir.sequence', 'MO Sequence')
    material_return_sequence_id = fields.Many2one('ir.sequence', 'Material Return Sequence')
    transit_location_id = fields.Many2one('stock.location', string='Transit Location')
    transit_loss_location_id = fields.Many2one('stock.location', string='Transit Loss Location')
    quality_location_id = fields.Many2one('stock.location', string='Quality Location')
    accept_loc_id = fields.Many2one('stock.location', string='Quality Accept Location')
    reject_loc_id = fields.Many2one('stock.location', string='Quality Reject Location')
    rework_loc_id = fields.Many2one('stock.location', string='Quality Rework Location') 
    po_notes = fields.Text(string="PO Terms & Conditions")
    address = fields.Text(string="Address(for Report Print)")
    factory_address = fields.Text(string="Factory Address")
    po_contact_info = fields.Text(string="PO Contact Info")
    round_off_account_id = fields.Many2one('account.account', 'Round Off Account')
    cloth_order_picking_type_id = fields.Many2one('stock.picking.type', 'Cloth Orders Picking Type')
    material_request_picking_type_id = fields.Many2one('stock.picking.type', 'Material Request Picking Type')
    material_return_picking_type_id = fields.Many2one('stock.picking.type', 'Material Return Picking Type')
    sf_mo_picking_type_id = fields.Many2one('stock.picking.type', 'Semi Finished Order Picking Type')
    default_resupply_wh_id = fields.Many2one(
        'stock.warehouse', 'Default Resupply Warehouse',
        help="Goods will always be resupplied from this warehouse")
    
    # @api.model
    @api.model_create_multi
    def create(self, vals):
        warehouses = super(Warehouse, self).create(vals) 
        picking_types = self.env['stock.picking.type'].search([('warehouse_id', 'in', warehouses.ids)])
        for each_picking_type in picking_types:
            each_picking_type.write({
                'production_unit_id': warehouses.production_unit_id and warehouses.production_unit_id.id or False,
                'production_division_id': warehouses.production_division_id and warehouses.production_division_id.id or False,
                })
        return warehouses
        
    
    def write(self, vals):
        res = super(Warehouse, self).write(vals)
        warehouses = self.with_context(active_test=False)  # TDE FIXME: check this
        if vals.get('production_unit_id'):
            picking_types = self.env['stock.picking.type'].search([('warehouse_id', '=', warehouses.id)])
            for each_picking_type in picking_types:
                each_picking_type.write({
                    'production_unit_id': warehouses.production_unit_id and warehouses.production_unit_id.id or False,
                    })
        if vals.get('production_division_id'):
            picking_types = self.env['stock.picking.type'].search([('warehouse_id', '=', warehouses.id)])
            for each_picking_type in picking_types:
                each_picking_type.write({
                    'production_division_id': warehouses.production_division_id and warehouses.production_division_id.id or False,
                    })
        return res

# Warehouse()

class PickingType(models.Model):
    _inherit = "stock.picking.type"
    
    production_unit_id = fields.Many2one('res.production.unit', 'Unit')
    production_division_id = fields.Many2one('res.production.unit.division', 'Division')
    # Statistics for the kanban view
    count_picking_draft = fields.Integer(compute='_compute_picking_count')
    count_picking_ready = fields.Integer(compute='_compute_picking_count')
    count_picking = fields.Integer(compute='_compute_picking_count')
    count_picking_waiting = fields.Integer(compute='_compute_picking_count')
    count_picking_late = fields.Integer(compute='_compute_picking_count')
    count_picking_backorders = fields.Integer(compute='_compute_picking_count')
    rate_picking_late = fields.Integer(compute='_compute_picking_count')
    rate_picking_backorders = fields.Integer(compute='_compute_picking_count')
    
    
    def _compute_picking_count(self):
        # TDE TODO count picking can be done using previous two
        domains = {
            'count_picking_draft': [('state', '=', 'draft')],
            'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting'))],
            'count_picking_ready': [('state', 'in', ('confirmed', 'assigned', 'partially_available'))],
            'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed', 'partially_available'))],
            'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed', 'partially_available'))],
            'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting', 'partially_available'))],
        }
        for field in domains:
            data = self.env['stock.picking'].read_group(domains[field] +
                [('state', 'not in', ('done', 'cancel')), ('picking_type_id', 'in', self.ids), ('to_refund', '!=', True), ('to_refund_po', '!=', True)],
                ['picking_type_id'], ['picking_type_id'])
            count = dict(map(lambda x: (x['picking_type_id'] and x['picking_type_id'][0], x['picking_type_id_count']), data))
            for record in self:
                record[field] = count.get(record.id, 0)
        for record in self:
            record.rate_picking_late = record.count_picking and record.count_picking_late * 100 / record.count_picking or 0
            record.rate_picking_backorders = record.count_picking and record.count_picking_backorders * 100 / record.count_picking or 0
            
    
    def get_action_picking_tree_done(self):
        return self._get_action('stock.action_picking_tree_done')

  
# PickingType()

class PackOperation(models.Model):
    _inherit = "stock.move.line"
    
    qty_onhand = fields.Float('Qty Onhand', readonly=True, digits=('Product Unit of Measure'))
#    qty_done_entered = fields.Float('Entered Done', default=0.0, digits=('Product Unit of Measure'))
#    is_done = fields.Boolean(compute='_compute_is_done', string='Done', readonly=False, oldname='processed_boolean')
    
    @api.onchange('product_uom_id', 'quantity')
    def onchange_quantity(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.quantity and (not self.product_uom_id.allow_decimal_digits):
            integer, decimal = divmod(self.quantity, 1)
            if decimal:
                self.quantity = 0.00
                warning = {
                        'title': _('Warning'),
                        'message': _('You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the qty to done should not contains decimal value') % (self.product_uom_id.name)}
        return {'warning': warning}
    
    # @api.onchange('product_uom_id', 'qty_done')
    # def onchange_qty_done(self):
    #     warning = {}
    #     integer, decimal = 0.00, 0.00
    #     if self.qty_done and (not self.product_uom_id.allow_decimal_digits):
    #         integer, decimal = divmod(self.qty_done, 1)
    #         if decimal:
    #             self.qty_done = 0.00
    #             warning = {
    #                     'title': _('Warning'),
    #                     'message': _('You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the qty to done should not contains decimal value') % (self.product_uom_id.name)}
    #     return {'warning': warning}

# PackOperation()
class StockLocationInherit(models.Model):
    _inherit = "stock.location"

    partner_id = fields.Many2one('res.partner', 'Owner', help="Owner of the location if not internal")

class StockMove(models.Model):
    _inherit = "stock.move"
    
    qty_onhand = fields.Float('Qty Onhand', readonly=True, digits=('Product Unit of Measure'))
    approved_date = fields.Datetime(string='Sale Order Approved Date', readonly=True)
    internal_stock_transfer_id = fields.Many2one('internal.stock.transfer.issue', string='Internal Stock Transfer Issue')

    @api.onchange('product_uom_qty', 'product_uom')
    def onchange_qty_done(self):
        warning = {}
        integer, decimal = 0.00, 0.00
        if self.product_uom_qty and (not self.product_uom.allow_decimal_digits):
            integer, decimal = divmod(self.product_uom_qty, 1)
            if decimal:
                self.product_uom_qty = 0.00
                warning = {
                    'title': _('Warning'),
                    'message': _('You cannot enter the decimal value on the following uom %s. \n Kindly make sure that the quantity should not contains decimal value') % (self.product_uom.name)}
        return {'warning': warning}
        
    
    def assign_picking(self):
        res = super(StockMove, self).assign_picking()
        for move in self:
            if move.picking_id and move.picking_id.picking_type_code == 'outgoing':
                move.write({
                    'name': move.name + ' / ' + move.picking_id.name + (move.picking_id.group_id and ' / ' + move.picking_id.group_id.name or '') 
                    })
        return True
        
    def _get_new_picking_values(self):
        res = super(StockMove, self)._get_new_picking_values()
        res.update({
            'cash_sale': self.group_id and self.group_id.cash_sale or False,
            'billing_info': self.group_id and self.group_id.billing_info or '',
            'shipping_info': self.group_id and self.group_id.shipping_info or '',
            })
        return res
        
    
    def product_price_update_after_done(self):
        ''' Adapt standard price on outgoing moves if the product cost_method is 'real', so that a
        return or an inventory loss is made using the last value used for an outgoing valuation. '''
        #to_update_moves = self.filtered(lambda move: move.product_id.cost_method == 'real' and move.location_dest_id.usage != 'internal')
        to_update_moves = self.filtered(lambda move: move.product_id.cost_method == 'real')
        to_update_moves._store_average_cost_price()
        
#    @api.constrains('product_uom')
#    def _check_uom(self):
#        if any(move.product_id.uom_id.category_id.id != move.product_uom.category_id.id for move in self):
#            raise UserError(_('You try to move a product %s using a UoM that is not compatible with the UoM of the product moved. Please use an UoM in the same UoM category.') % (move.product_id.name_get()[0][1]))

# StockMove()

class Picking(models.Model):
    _inherit = "stock.picking"
    
    state = fields.Selection(selection_add=[('partially_available', 'Partially Available')])
    
     # Override the field to reorder the selection values
    # state = fields.Selection([
    #     ('draft', 'Draft'),
    #     ('waiting', 'Waiting Another Operation'),
    #     ('confirmed', 'Waiting'),
    #     ('partially_available', 'Partially Available'),
    #     ('assigned', 'Ready'),
    #     ('done', 'Done'),
    #     ('cancel', 'Cancelled'),
    # ], string='Status', compute='_compute_state',
    #     copy=False, index=True, readonly=True, store=True, tracking=True,
    #     help=" * Draft: The transfer is not confirmed yet. Reservation doesn't apply.\n"
    #          " * Partially Available: The transfer is partially available.\n"
    #          " * Waiting another operation: This transfer is waiting for another operation before being ready.\n"
    #          " * Waiting: The transfer is waiting for the availability of some products.\n(a) The shipping policy is \"As soon as possible\": no product could be reserved.\n(b) The shipping policy is \"When all products are ready\": not all the products could be reserved.\n"
    #          " * Ready: The transfer is ready to be processed.\n(a) The shipping policy is \"As soon as possible\": at least one product has been reserved.\n(b) The shipping policy is \"When all products are ready\": all product have been reserved.\n"
    #          " * Done: The transfer has been processed.\n"
    #          " * Cancelled: The transfer has been cancelled.")  
    
    # @api.depends('move_lines.date_expected')
    # def _compute_dates(self):
    #     for record in self:
    #         # Debugging prints
    #         print("Computing dates for record:", record)
    #         print("Move lines:", record.move_lines)
    #         print("Dates:", record.move_lines.mapped('date_expected'))

    #         dates = record.move_lines.mapped('date_expected')
    #         record.scheduled_date = min(dates) if dates else False
    #         record.date_deadline = max(dates) if dates else False
    
    def _set_scheduled_date(self):
        self.move_lines.write({'date_expected': self.scheduled_date})

    @api.model_create_multi
    def create(self, vals_list):
        scheduled_dates = []
        for vals in vals_list:
            defaults = self.default_get(['name', 'picking_type_id'])
            picking_type = self.env['stock.picking.type'].browse(
                vals.get('picking_type_id', defaults.get('picking_type_id')))
            if vals.get('name', '/') == '/' and defaults.get('name', '/') == '/' and vals.get('picking_type_id',
                                                                                              defaults.get(
                                                                                                      'picking_type_id')):
                if picking_type.sequence_id:
                    vals['name'] = picking_type.sequence_id.next_by_id()

            # make sure to write `schedule_date` *after* the `stock.move` creation in
            # order to get a determinist execution of `_set_scheduled_date`
            scheduled_dates.append(vals.pop('scheduled_date', False))

        pickings = super().create(vals_list)

        for line in pickings.move_ids_without_package:
            for move_id in pickings.move_ids:
                if line.product_id == move_id.product_id:
                    move_id.price_unit = line.product_id.standard_price

        for picking, scheduled_date in zip(pickings, scheduled_dates):
            if scheduled_date:
                picking.with_context(mail_notrack=True).write({'scheduled_date': scheduled_date})
        pickings._autoconfirm_picking()

        for picking, vals in zip(pickings, vals_list):
            # set partner as follower
            if vals.get('partner_id'):
                if picking.location_id.usage == 'supplier' or picking.location_dest_id.usage == 'customer':
                    picking.message_subscribe([vals.get('partner_id')])
            if vals.get('picking_type_id'):
                for move in picking.move_ids:
                    if not move.description_picking:
                        move.description_picking = move.product_id.with_context(lang=move._get_lang())._get_description(
                            move.picking_id.picking_type_id)

        return pickings

    def write(self, vals):
        if vals.get('picking_type_id') and any(picking.state != 'draft' for picking in self):
            raise UserError(_("Changing the operation type of this record is forbidden at this point."))
        # set partner as a follower and unfollow old partner
        if vals.get('partner_id'):
            for picking in self:
                if picking.location_id.usage == 'supplier' or picking.location_dest_id.usage == 'customer':
                    if picking.partner_id:
                        picking.message_unsubscribe(picking.partner_id.ids)
                    picking.message_subscribe([vals.get('partner_id')])
        if vals.get('picking_type_id'):
            picking_type = self.env['stock.picking.type'].browse(vals.get('picking_type_id'))
            for picking in self:
                if picking.picking_type_id != picking_type:
                    picking.name = picking_type.sequence_id.next_by_id()
        res = super(Picking, self).write(vals)
        #
        for line in self.move_ids_without_package:
            for move_id in self.move_ids:
                if line.product_id == move_id.product_id:
                    move_id.price_unit = line.product_id.standard_price
        if vals.get('signature'):
            for picking in self:
                picking._attach_sign()
        # Change locations of moves if those of the picking change
        after_vals = {}
        if vals.get('location_id'):
            after_vals['location_id'] = vals['location_id']
        if vals.get('location_dest_id'):
            after_vals['location_dest_id'] = vals['location_dest_id']
        if 'partner_id' in vals:
            after_vals['partner_id'] = vals['partner_id']
        if after_vals:
            self.move_ids.filtered(lambda move: not move.scrapped).write(after_vals)
        if vals.get('move_ids') or vals.get('move_ids_without_package'):
            self._autoconfirm_picking()

        return res
        
    
    # @api.depends('sale_id', 'approved_date')
    # def _compute_manager_id(self):
    #     if self.sale_id:
    #         self.manager_id = self.sale_id.sales_manager_id
            
    
    @api.depends('currency_id', 'company_id.currency_id', 'picking_type_code')
    def _compute_hide_currency(self):
        if self.picking_type_code == 'incoming':
            if self.currency_id == self.company_id.currency_id:
                self.hide_currency = True
            else:
                self.hide_currency = False
        else:
            self.hide_currency = True
            
    
    @api.depends('move_ids_without_package.product_uom', 'move_ids_without_package.product_uom_qty')
    def _get_uom_based_quantity(self):
        qty_dict = {}
        qty_string = ''
        for line in self.move_ids_without_package:
            print("\n\n\n====")
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
    
    driver_id = fields.Many2one('truck.driver.employee', string="Driver", copy=False, readonly=True)
    vehicle_no = fields.Char(string="Vehicle No", size=64, copy=False, readonly=True)
    vehicle_owner = fields.Char(string="Vehicle Owner", size=64, copy=False, readonly=True)
    vehicle_owner_address = fields.Char(string="Vehicle Owner Address", size=128, copy=False, readonly=True)
    driver_licence = fields.Char(string="Driver Licence No", size=64, copy=False, readonly=True)
    driver_name = fields.Char(string="Driver Name", size=64, copy=False, readonly=True)
    driver_licence_type = fields.Char(string="Driver Licence Type", size=64, copy=False, readonly=True)
    driver_licence_place = fields.Char(string="Issued Licence Place", size=64, copy=False, readonly=True)
    driver_phone = fields.Char(string="Driver Contact No", size=64, copy=False, readonly=True)
    agent_name = fields.Char(string="Agent Name", size=64, copy=False, readonly=True)
    delivery_return = fields.Boolean(string="Delivery Return", default=False, copy=False)
    to_refund = fields.Boolean(string="To Refund SO", default=False, copy=False)
    to_refund_po = fields.Boolean(string="To Refund PO", default=False, copy=False)
    refund_sent_approval = fields.Boolean(string="Sale Return Sent For Approval", default=False, copy=False, readonly=True)
    refund_approved = fields.Boolean(string="Sale Return Approved", default=False, copy=False, readonly=True)
    move_lines = fields.One2many('stock.move', 'internal_stock_transfer_id', string='Stock Move')
    approved_date = fields.Datetime(string='Sale Order Approved Date', related='move_ids.approved_date', readonly=True, store=True)
    # scheduled_date = fields.Datetime(
    #     'Expected Delivery Date',  inverse='_set_scheduled_date', store=True,
    #     index=True,
    #     states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
    #     help="Scheduled time for the first part of the shipment to be processed. Setting manually a value here would set it as expected date for all the stock moves.")
    scheduled_date = fields.Datetime(
        'Expected Delivery Date',  inverse='_set_scheduled_date', store=True,
        index=True,
        help="Scheduled time for the first part of the shipment to be processed. Setting manually a value here would set it as expected date for all the stock moves.")
    date_deadline = fields.Datetime(
        'Max. Expected Date', store=True,
        index=True,
        help="Scheduled time for the last part of the shipment to be processed")
#    date_grn = fields.Date(string='GRN Date', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, copy=False)
    reference_no = fields.Char(string='DC Reference No', size=64, readonly=True, copy=False)
    reference_date = fields.Date(string='DC Reference Date', readonly=True, copy=False)
    supplier_inv_no = fields.Char(string='Vendor Invoice No', size=64, readonly=True, copy=False,)
    supplier_inv_date = fields.Date(string='Vendor Invoice Date', readonly=True, copy=False,)
    gate_entry_ref = fields.Char(string='Gate Entry Ref', readonly=True, copy=False,)
    manager_id = fields.Many2one('res.users', string="Manager",  store=True)
    # manager_id = fields.Many2one('res.users', string="Manager", compute='_compute_manager_id', store=True)
    remarks = fields.Text(string="Remarks", store=True, copy=False, readonly=True)
    # remarks = fields.Text(string="Remarks", compute='_compute_remarks', store=True, copy=False, readonly=True)
    cancel_reason = fields.Text(string="Cancel Reason", readonly=True, copy=False)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True, copy=True)
    lc_booked = fields.Boolean('LC Booked', default=False)
    hide_currency = fields.Boolean(string='Hide Currency', compute='_compute_hide_currency', default=False)
    cash_sale = fields.Boolean(string='Cash Sales', default=False, help="Check this box if this customer is a cash sale customer.", copy=False)
    # billing_info = fields.Text(string="Billing Info", readonly=True, states={'draft': [('readonly', False)]}, copy=False)
    # shipping_info = fields.Text(string="Shipping Info", readonly=True, states={'draft': [('readonly', False)]}, copy=False)
    billing_info = fields.Text(string="Billing Info",  copy=False)
    shipping_info = fields.Text(string="Shipping Info",  copy=False)
    total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Quantity')

#    @api.onchange('driver_id')
#    def onchange_driver_id(self):
#        if self.driver_id:
#            self.driver_name = self.driver_id.name or ""
#            self.driver_licence = self.driver_id.driver_licence or ""
#            self.driver_licence_type = self.driver_id.driver_licence_type or ""
#            self.driver_licence_place = self.driver_id.driver_licence_place or ""
#            self.driver_phone =  self.driver_id.driver_phone or ""
#        else:
#            self.driver_name = ""
#            self.driver_licence = ""
#            self.driver_licence_type = ""
#            self.driver_licence_place = ""
#            self.driver_phone = ""
#        return {}
               
    
    # @api.depends('move_lines.procurement_id.sale_line_id.order_id', 'move_lines.procurement_id.purchase_line_id.order_id')
    # def _compute_remarks(self):
    #     for move in self.move_lines:
    #         if move.procurement_id.sale_line_id:
    #             self.remarks = move.procurement_id.sale_line_id.order_id.sale_remarks
    #         if move.procurement_id.purchase_line_id:
    #             self.remarks = move.procurement_id.purchase_line_id.order_id.purchase_remarks
    
    def button_validate(self):
        # Perform the original validation process
        res = super().button_validate()
        if self.partner_id and  self.picking_type_code not in ['internal', 'outgoing']:
            for record in self:
                if not record.reference_no:
                    raise UserError("Please provide the DC Reference No before validating.")
                if not record.reference_date:
                    raise UserError("Please provide the DC Reference Date before validating.")
                if not record.supplier_inv_no:
                    raise UserError("Please provide the Vendor Invoice No before validating.")
                if not record.supplier_inv_date:
                    raise UserError("Please provide the Vendor Invoice Date before validating.")
                if not record.gate_entry_ref:
                    raise UserError("Please provide the Gate Entry Reference before validating.")

            # If all validations pass, return the result
            return res

    def action_check_stock_qty(self):
        # print("\n\n\n\n\n\n======enter.....=====")
        quant_obj = self.env['stock.quant']
        # print("\n\n\n\n\n\n======quant_obj.....=====",quant_obj)
        move_qty_available = 0.00
        for each in self:  
            # print("\n\n\n\n===========each.move_lines=====",[each.name for each in each.move_ids_without_package])
            for each_move in each.move_ids_without_package:
                move_qty_available = 0.00
                # print("\n\n\n\n\n\n============move_qty_available",move_qty_available)
                # print("\n\n\n\n\n\n============each_move.location_id.id",each_move.location_id.id)
                # print("\printn\n\n\n\n\n============each_move.product_id.id",each_move.product_id.id)
                quant_search = quant_obj.search_read([('location_id','=', each_move.location_id.id),('product_id','=', each_move.product_id.id)],['inventory_quantity_auto_apply'])
                # print("\n\n\n\n\n\n============quant_search",quant_search.inventory_quantity_auto_apply)
                for each_quant_qty in quant_search:
                    move_qty_available += each_quant_qty['inventory_quantity_auto_apply']
                # print("\n\n\n\n\n\n============move_qty_available",move_qty_available)
                each_move.write({'qty_onhand': move_qty_available})
        return True

    # def action_check_stock(self):
    #     stock_quant_obj = self.env['stock.quant']
    #     print("\n\n\n\nstock_quant_obj",stock_quant_obj)
    #     source_loc_stock = 0.00
    #     for each in self:
    #         for line in each.transfer_lines:
    #             source_loc_stock = 0.00
    #             print("\n\n\n\line.location_id",line.location_id.name)
    #             source_quant_search = stock_quant_obj.search_read([('location_id', '=', line.location_id.id), ('product_id', '=' , line.product_id.id)],['inventory_quantity_auto_apply'])
    #             print("\n\n\n\nsource_quant_search",source_quant_search)
    #             for source_quant in source_quant_search:
    #                 source_loc_stock += source_quant['inventory_quantity_auto_apply']
    #             line.source_loc_stock = source_loc_stock
    #             print("\n\n\n\nline.source_loc_stock",line.source_loc_stock)
    #     return True
    
    def action_confirm(self):
        res = super(Picking, self).action_confirm()
        self.action_check_stock_qty()
        return res
        
    
    def action_assign(self):
        res = super(Picking, self).action_assign()
        self.action_check_stock_qty()
        return res
        
    # FUNCTION NOT AVAILABLE ###
    # def force_assign(self):
    #     res = super(Picking, self).force_assign()
    #     self.action_check_stock_qty()
    #     return res
        
    def do_transfer(self):
        quality_obj = self.env['quality.check.many']
        quality_line_obj = self.env['product.check.line']
#        self.ensure_one()
        res = super(Picking, self).do_transfer()
        quality = False
        for each in self:
            quality = False
            if each.picking_type_code == 'incoming':
                for line in each.pack_operation_product_ids:
                    if line.product_id.type == 'product' and line.product_id.quality_check_required == 'yes':
                        if not quality:
                            quality_id = quality_obj.create({
                                'name': 'New #',
                                'supplier_id': each.partner_id and each.partner_id.id or False,
                                'picking_id': each.id,
                                'grn_no': each.name,
                                'grn_date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                'supplier_inv_no': each.supplier_inv_no and each.supplier_inv_no or "",
                                'supplier_inv_date': each.supplier_inv_date and each.supplier_inv_date or False,
                                'supplier_dc_no': each.reference_no and each.reference_no or "",
                                'supplier_dc_date': each.reference_date and each.reference_date or False,
                                'gate_entry_ref': each.gate_entry_ref and each.gate_entry_ref or '',
                                'qc_type': 'incoming',
                                'warehouse_id': each.picking_type_id.warehouse_id.id
                                })
                            quality = True
                        purchase_line_id = False
                        for each_pack_line in line.linked_move_operation_ids:
                            if each_pack_line.move_id:
                                if each_pack_line.move_id.purchase_line_id:
                                    purchase_line_id = each_pack_line.move_id.purchase_line_id.id
                        quality_line_obj.create({
                            'check_id': quality_id.id,
                            'product_id': line.product_id.id,
                            'uom_id': line.product_uom_id.id,
                            'inward_qty': line.qty_done and line.qty_done or line.product_qty,
                            'warehouse_id': each.picking_type_id.warehouse_id.id,
                            'source_loc_id': line.location_dest_id.id,
                            'purchase_line_id': purchase_line_id,
                            'qc_balance_qty': line.qty_done and line.qty_done or line.product_qty,
                            })
        return res

        
    ###### do_new_transfer NOT IN ODOO 17#########
    # def do_new_transfer(self):
    #     quality_obj = self.env['quality.check.many']
    #     quality_line_obj = self.env['product.check.line']
    #     for pick in self:
    #         if pick.to_refund:
    #             if not pick.refund_sent_approval:
    #                 raise UserError(_('You cannot return the item which is yet to be approved, \nKindly send for approval!!!'))
    #             if not pick.refund_approved:
    #                 raise UserError(_('You cannot return the item which is yet to be approved, \nKindly contact your higher authority or administrator !!!'))
    #         if pick.picking_type_code == 'incoming' and pick.to_refund != True:
    #             if not pick.gate_entry_ref:
    #                 raise UserError(_('Kindly Fill the Gate Entry Reference !!!'))
    #         if pick.picking_type_code == 'outgoing' and pick.to_refund_po != True:
    #             if not pick.driver_name:
    #                 raise UserError(_('Kindly Fill the driver details !!!'))
    #             if not pick.driver_phone:
    #                 raise UserError(_('Kindly Fill the driver phone !!!'))
    #             if not pick.driver_licence:
    #                 raise UserError(_('Kindly Fill the driver licence !!!'))
    #             if not pick.driver_licence_type:
    #                 raise UserError(_('Kindly Fill the driver licence type !!!'))
    #             if not pick.driver_licence_place:
    #                 raise UserError(_('Kindly Fill the driver licence place !!!'))
    #             if not pick.vehicle_no:
    #                 raise UserError(_('Kindly Fill the vehicle no !!!'))
    #             if not pick.vehicle_owner:
    #                 raise UserError(_('Kindly Fill the vehicle owner !!!'))
    #             if not pick.vehicle_owner_address:
    #                 raise UserError(_('Kindly Fill the vehicle owner address !!!'))
    #             if not pick.agent_name:
    #                 raise UserError(_('Kindly Fill the agent name !!!'))
    #         for each_pack_product in pick.pack_operation_product_ids:
    #             if each_pack_product.product_qty < each_pack_product.qty_done:
    #                 raise UserError(_('Product "%s" Given Quantity (%s) must be lesser than or equal to "To Do Quantity" (%s).Kindly Change the "To Do Quantity" and proceed forward ') % (each_pack_product.product_id.name_get()[0][1], each_pack_product.qty_done, each_pack_product.product_qty))
    #     res = super(Picking, self).do_new_transfer()
    #     return res
        
    
    def action_send_refund_approval(self):
        for pick in self:
            pick.write({'refund_sent_approval': True})
            
    
    def action_refund_approve(self):
        for pick in self:
            pick.write({'refund_approved': True})
            
    def _prepare_pack_ops(self, quants, forced_qties):
        """ Prepare pack_operations, returns a list of dict to give at create """
        # TDE CLEANME: oh dear ...
        valid_quants = quants.filtered(lambda quant: quant.qty > 0)
        _Mapping = namedtuple('Mapping', ('product', 'package', 'owner', 'location', 'location_dst_id'))

        all_products = valid_quants.mapped('product_id') | self.env['product.product'].browse(p.id for p in forced_qties.keys()) | self.move_ids.mapped('product_id')
        computed_putaway_locations = dict(
            (product, self.location_dest_id.get_putaway_strategy(product) or self.location_dest_id.id) for product in all_products)
        product_to_uom = dict((product.id, product.uom_id) for product in all_products)
        picking_moves = self.move_ids.filtered(lambda move: move.state not in ('done', 'cancel'))
        for move in picking_moves:
            computed_putaway_locations[move.product_id] = move.location_dest_id.id
            # If we encounter an UoM that is smaller than the default UoM or the one already chosen, use the new one instead.
            if move.product_uom != product_to_uom[move.product_id.id] and move.product_uom.factor > product_to_uom[move.product_id.id].factor:
                product_to_uom[move.product_id.id] = move.product_uom
        if len(picking_moves.mapped('location_id')) > 1:
            raise UserError(_('The source location must be the same for all the moves of the picking.'))
#        if len(picking_moves.mapped('location_dest_id')) > 1:
#            raise UserError(_('The destination location must be the same for all the moves of the picking.'))

        pack_operation_values = []
        # find the packages we can move as a whole, create pack operations and mark related quants as done
        top_lvl_packages = valid_quants._get_top_level_packages(computed_putaway_locations)
        for pack in top_lvl_packages:
            pack_quants = pack.get_content()
            pack_operation_values.append({
                'picking_id': self.id,
                'package_id': pack.id,
                'product_qty': 1.0,
                'location_id': pack.location_id.id,
                'location_dest_id': computed_putaway_locations[pack_quants[0].product_id],
                'owner_id': pack.owner_id.id,
            })
            valid_quants -= pack_quants

        # Go through all remaining reserved quants and group by product, package, owner, source location and dest location
        # Lots will go into pack operation lot object
        qtys_grouped = {}
        lots_grouped = {}
        for quant in valid_quants:
            key = _Mapping(quant.product_id, quant.package_id, quant.owner_id, quant.location_id, computed_putaway_locations[quant.product_id])
            qtys_grouped.setdefault(key, 0.0)
            qtys_grouped[key] += quant.qty
            if quant.product_id.tracking != 'none' and quant.lot_id:
                lots_grouped.setdefault(key, dict()).setdefault(quant.lot_id.id, 0.0)
                lots_grouped[key][quant.lot_id.id] += quant.qty
        # Do the same for the forced quantities (in cases of force_assign or incomming shipment for example)
        for product, qty in forced_qties.items():
            if qty <= 0.0:
                continue
            key = _Mapping(product, self.env['stock.quant.package'], self.owner_id, self.location_id, computed_putaway_locations[product])
            qtys_grouped.setdefault(key, 0.0)
            qtys_grouped[key] += qty

        # Create the necessary operations for the grouped quants and remaining qtys
        Uom = self.env['uom.uom']
        product_id_to_vals = {}  # use it to create operations using the same order as the picking stock moves
        for mapping, qty in qtys_grouped.items():
            uom = product_to_uom[mapping.product.id]
            val_dict = {
                'picking_id': self.id,
                'product_qty': mapping.product.uom_id._compute_quantity(qty, uom),
                'product_id': mapping.product.id,
                'package_id': mapping.package.id,
                'owner_id': mapping.owner.id,
                'location_id': mapping.location.id,
                'location_dest_id': mapping.location_dst_id,
                'product_uom_id': uom.id,
                'pack_lot_ids': [
                    (0, 0, {'lot_id': lot, 'qty': 0.0, 'qty_todo': lots_grouped[mapping][lot]})
                    for lot in lots_grouped.get(mapping, {}).keys()],
            }
            product_id_to_vals.setdefault(mapping.product.id, list()).append(val_dict)

        for move in self.move_ids.filtered(lambda move: move.state not in ('done', 'cancel')):
            values = product_id_to_vals.pop(move.product_id.id, [])
            pack_operation_values += values
        return pack_operation_values
        
    # AFTER CHECK ###    
    # @api.model
    # def _create_backorder(self):
    #     res = super(Picking, self)._create_backorder()
    #     # if res.quant_reserved_exist:
    #     #   res.do_unreserve()
    #     return res
        
    
    def copy(self, default=None):
        if not default:
            default = {}
        if not default:
            raise UserError(_('Not possible to duplicate the record!!!'))
        new_picking = super(Picking, self).copy(default=default)
        return new_picking
        
    @api.model
    def _prepare_values_extra_move(self, op, product, remaining_qty):
        # Uom = self.env["product.uom"]
        Uom = self.env["uom.uom"]
        uom_id = product.uom_id.id
        qty = remaining_qty
        if op.product_id and op.product_uom_id and op.product_uom_id.id != product.uom_id.id:
            if op.product_uom_id.factor > product.uom_id.factor:  # If the pack operation's is a smaller unit
                uom_id = op.product_uom_id.id
                # HALF-UP rounding as only rounding errors will be because of propagation of error from default UoM
                qty = product.uom_id._compute_quantity(remaining_qty, op.product_uom_id, rounding_method='HALF-UP')
        if qty:
            raise UserError(_('System is trying to create extra moves for this entry!\nPlease try again later.'))
        res = super(Picking, self)._prepare_values_extra_move(op, product, remaining_qty)
        return res
    

# Picking()

# MODEL IS NOT AVILABLE ###

# class ProcurementOrder(models.Model):
#     _inherit = "procurement.order"
    
#     approved_date = fields.Datetime(string='Sale Order Approved Date')
    
#     def _get_stock_move_values(self):
#         res = super(ProcurementOrder, self)._get_stock_move_values()
#         if self.approved_date:
#             res.update({
#                 'approved_date': self.approved_date,
#                 })
        #group_name = ''
        #if self.rule_id.group_propagation_option == 'propagate':
        #    group_name = self.group_id.name
        #elif self.rule_id.group_propagation_option == 'fixed':
        #    group_name = self.rule_id.group_id.name
        #res.update({
        #    'name': self.name + (group_name and ' / ' + group_name or '')
        #    })
        # return res
        
class Orderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"
    
    @api.onchange('warehouse_id')
    def onchange_custom_warehouse_id(self):
        warning = {}
        if self.warehouse_id:
            if self.product_id and self.product_id.stock_warehouse_ids:
                if self.warehouse_id not in self.product_id.stock_warehouse_ids:
                    self.warehouse_id = False
                    warning = {
                        'title': _('Warning'),
                        'message': _('Selected warehouse not available in product stocking warehouse.')}
        return {'warning': warning}
        
    @api.onchange('product_id')
    def onchange_custom_product_id(self):
        warning = {}
        if self.product_id:
            if self.warehouse_id and self.product_id.stock_warehouse_ids:
                if self.warehouse_id not in self.product_id.stock_warehouse_ids:
                    self.warehouse_id = False
                    warning = {
                        'title': _('Warning'),
                        'message': _('Selected warehouse not available in product stocking warehouse.')}
        return {'warning': warning}
        
    @api.onchange('location_id')
    def onchange_location_id(self):
        warning = {}
        if self.location_id:
            if self.warehouse_id:
                if self.location_id != self.warehouse_id.lot_stock_id:
                    self.location_id = self.warehouse_id.lot_stock_id.id
                    warning = {
                        'title': _('Warning'),
                        'message': _('You cannot change the location which is configured in warehouse/branch.')}
        return {'warning': warning}
        
class Quant(models.Model):
    """ Quants are the smallest unit of stock physical instances """
    _inherit = "stock.quant"
        
    qty = fields.Float(
        'Quantity',
        digits=('Product Unit of Measure'),
        index=True, readonly=True,
        help="Quantity of products in this quant, in the default unit of measure of the product")  
    cost = fields.Float('Unit Cost', group_operator='avg')   
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse',  copy=False)
    accounting_date = fields.Date(
        'Force Accounting Date', copy=False,
        help="Choose the accounting date at which you want to value the stock "
             "moves created by the inventory instead of the default one (the "
             "inventory end date)")   
    inventory_value = fields.Float('Inventory Value', compute='_compute_inventory_value', readonly=True)
    history_ids = fields.Many2many(
        'stock.move', 'stock_quant_move_rel', 'quant_id', 'move_id',
        string='Moves', copy=False,
        help='Moves that operate(d) on this quant')

    
    def _compute_inventory_value(self):
        for quant in self:
            if quant.company_id != self.env.user.company_id:
                # if the company of the quant is different than the current user company, force the company in the context
                # then re-do a browse to read the property fields for the good company.
                quant = quant.with_context(force_company=quant.company_id.id)
            quant.inventory_value = quant.product_id.standard_price * quant.quantity

    def _get_inventory_move_values(self, qty, location_id, location_dest_id, package_id=False, package_dest_id=False):
        """ Called when user manually set a new quantity (via `inventory_quantity`)
        just before creating the corresponding stock move.

        :param location_id: `stock.location`
        :param location_dest_id: `stock.location`
        :param package_id: `stock.quant.package`
        :param package_dest_id: `stock.quant.package`
        :return: dict with all values needed to create a new `stock.move` with its move line.
        """
        self.ensure_one()
        if self.env.context.get('inventory_name'):
            name = self.env.context.get('inventory_name')
        elif fields.Float.is_zero(qty, 0, precision_rounding=self.product_uom_id.rounding):
            name = _('Product Quantity Confirmed')
        else:
            name = _('Product Quantity Updated')
        if self.user_id and self.user_id.id != SUPERUSER_ID:
            name += f' ({self.user_id.display_name})'

        return {
            'name': name,
            'product_id': self.product_id.id,
            'price_unit': self.product_id.standard_price,
            'product_uom': self.product_uom_id.id,
            'product_uom_qty': qty,
            'company_id': self.company_id.id or self.env.company.id,
            'state': 'confirmed',
            'location_id': location_id.id,
            'location_dest_id': location_dest_id.id,
            'restrict_partner_id':  self.owner_id.id,
            'is_inventory': True,
            'picked': True,
            'move_line_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'product_uom_id': self.product_uom_id.id,
                'quantity': qty,
                'location_id': location_id.id,
                'location_dest_id': location_dest_id.id,
                'company_id': self.company_id.id or self.env.company.id,
                'lot_id': self.lot_id.id,
                'package_id': package_id.id if package_id else False,
                'result_package_id': package_dest_id.id if package_dest_id else False,
                'owner_id': self.owner_id.id,
            })]
        }



# MODEL IS NOT AVILABLE ###

# class StockInventory(models.Model):
#     _inherit = 'stock.inventory'
#     _order = "date desc,id desc"
    
    
#     @api.depends('move_ids.product_uom', 'move_ids.product_uom_qty')
#     def _get_uom_based_quantity(self):
#         qty_dict = {}
#         qty_string = ''
#         for line in self.move_ids:
#             if line.product_uom.id in qty_dict:
#                 qty_dict[line.product_uom.id]['product_uom_qty'] += line.product_uom_qty
#             else:
#                 qty_dict[line.product_uom.id] = {
#                     'product_uom_qty': line.product_uom_qty,
#                     'product_uom': line.product_uom and line.product_uom.name or '' 
#                     }
#         for each in qty_dict:
#             if qty_dict[each]['product_uom_qty'] and qty_dict[each]['product_uom']:
#                 if qty_string:
#                     qty_string += " , "
#                 qty_string += "{0:.3f}".format(qty_dict[each]['product_uom_qty']) + " " + (qty_dict[each]['product_uom'])
#         self.total_quantity_based_uom = qty_string
   
#     warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True, states={'draft': [('readonly', False)]}, copy=False)
#     accounting_date = fields.Date(
#         'Force Accounting Date', readonly=True, states={'draft': [('readonly', False)]}, copy=False,
#         help="Choose the accounting date at which you want to value the stock "
#              "moves created by the inventory instead of the default one (the "
#              "inventory end date)")
#     view_location_id = fields.Many2one('stock.location', string='View Location', copy=False)    
#     history = fields.Text('History', readonly=True, copy=False)
#     total_quantity_based_uom = fields.Char(compute='_get_uom_based_quantity', string='Total Quantity')
    
#     @api.onchange('warehouse_id')
#     def onchange_warehouse_id(self):
#         warning = {}
#         domain = {}
#         if self.warehouse_id:
#             self.view_location_id = self.warehouse_id.view_location_id.id
#             self.location_id = self.warehouse_id.lot_stock_id.id
#             domain = {
#                 'location_id': ['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage','not in', ['view', 'supplier','production'])],
#                 }
#         else:
#             self.view_location_id = False
#             self.location_id = False
#         return {'domain': domain}

    
#     def prepare_inventory(self):
#         res = super(StockInventory, self).prepare_inventory()
#         fmt = "%d-%m-%Y %H:%M:%S"
#         date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
#         history = ''
#         if self.history:
#             history = self.history + '\n'
#         self.history = history + 'This Inventory is Started by ' + self.env.user.name + ' on this date '+ date
#         return res
        
    
#     def action_done(self):
#         res = super(StockInventory, self).action_done()
#         fmt = "%d-%m-%Y %H:%M:%S"
#         date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
#         history = ''
#         if self.history:
#             history = self.history + '\n'
#         self.history = history + 'This Inventory is Validated by ' + self.env.user.name + ' on this date '+ date
#         return res
        
    
#     def action_cancel_draft(self):
#         res = super(StockInventory, self).action_cancel_draft()
#         fmt = "%d-%m-%Y %H:%M:%S"
#         date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
#         history = ''
#         if self.history:
#             history = self.history + '\n'
#         self.history = history + 'This Inventory is Cancelled and Re-sent to Draft by ' + self.env.user.name + ' on this date '+ date
#         return res

# MODEL IS NOT AVILABLE ###
   
# class InventoryLine(models.Model):
#     _inherit = "stock.inventory.line"
    
#     def _generate_moves(self):
#         moves = self.env['stock.move']
#         Quant = self.env['stock.quant']
#         for line in self:
#             if float_utils.float_compare(line.theoretical_qty, line.product_qty, precision_rounding=line.product_id.uom_id.rounding) == 0:
#                 continue
#             diff = line.theoretical_qty - line.product_qty
#             vals = {
#                 'name': _('INV:') + (line.inventory_id.name or '') + (line.product_id and  " - " + line.product_id.name_get()[0][1] or ""),
#                 'product_id': line.product_id.id,
#                 'product_uom': line.product_uom_id.id,
#                 'price_unit': line.product_id.standard_price,#new line EBITS TechCon
#                 'date': line.inventory_id.date,
#                 'company_id': line.inventory_id.company_id.id,
#                 'inventory_id': line.inventory_id.id,
#                 'state': 'confirmed',
#                 'restrict_lot_id': line.prod_lot_id.id,
#                 'restrict_partner_id': line.partner_id.id}
#             if diff < 0:  # found more than expected
#                 vals['location_id'] = line.product_id.property_stock_inventory.id
#                 vals['location_dest_id'] = line.location_id.id
#                 vals['product_uom_qty'] = abs(diff)
#             else:
#                 vals['location_id'] = line.location_id.id
#                 vals['location_dest_id'] = line.product_id.property_stock_inventory.id
#                 vals['product_uom_qty'] = diff
#             move = moves.create(vals)

#             if diff > 0:
#                 domain = [('qty', '>', 0.0), ('package_id', '=', line.package_id.id), ('lot_id', '=', line.prod_lot_id.id), ('location_id', '=', line.location_id.id)]
#                 preferred_domain_list = [[('reservation_id', '=', False)], [('reservation_id.inventory_id', '!=', line.inventory_id.id)]]
#                 quants = Quant.quants_get_preferred_domain(move.product_qty, move, domain=domain, preferred_domain_list=preferred_domain_list)
#                 Quant.quants_reserve(quants, move)
#             elif line.package_id:
#                 move.action_done()
#                 move.quant_ids.write({'package_id': line.package_id.id})
#                 quants = Quant.search([('qty', '<', 0.0), ('product_id', '=', move.product_id.id),
#                                        ('location_id', '=', move.location_dest_id.id), ('package_id', '!=', False)], limit=1)
#                 if quants:
#                     for quant in move.quant_ids:
#                         if quant.location_id.id == move.location_dest_id.id:  #To avoid we take a quant that was reconcile already
#                             quant._quant_reconcile_negative(move)
#         return moves
                    
class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    date_expected = fields.Datetime('Expected Date', default=fields.Datetime.now)
    def _prepare_move_values(self):
        res = super(StockScrap, self)._prepare_move_values()
        res['name'] = self.name + (self.product_id and  " - " + self.product_id.name_get()[0][1] or ""),
        return res
        
            
    @api.onchange('product_uom_id')
    def _onchange_product_uom_id(self):
        warning = {}
        if self.product_id and self.product_uom_id:
            if self.product_uom_id.id != self.product_id.uom_id.id:
                self.product_uom_id = self.product_id.uom_id and self.product_id.uom_id.id or False
                warning = {
                    'title': _('Warning'),
                    'message': _('Unit of measure cannot be changed.')}
        return {'warning': warning}
        
    
    def unlink(self):
        for each in self:
            if each.state != 'draft':
                raise UserError(_("You can delete a form which is only in draft state"))
        return super(StockScrap, self).unlink()
