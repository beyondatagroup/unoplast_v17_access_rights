# -*- encoding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2004-2014 OpenERP S.A. (<http://odoo.com>).
#
##############################################################################
import time

from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError
from datetime import datetime
import pytz

class ForceCloseRawIssueWizard(models.TransientModel):
    _name = 'force.close.raw.issue.wizard'
    _description = 'Force Close Raw Issue Wizard'
    
    reason = fields.Text(string='Reason', required=True)
    
    # @api.multi
    def action_close(self):
        active_id = self._context.get('active_id')
        raw_obj = self.env['raw.material.issue']
        raw_browse = raw_obj.browse(active_id)
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in raw_browse:
            each.closed = True
            each.reason += "\nIssue has been force closed by " + str(self.env.user.name) + " for the reason - '" + str(self.reason) + "'" + " on " + str(date)
            for lines in each.return_lines:
                if lines.balance_qty:
                    lines.closed = True
            each.action_closed()
            if each.returned_mtrs and each.balance_mtrs_total_value != 0.00:
                each.action_create_account_entry()
        return True
        
# ************** Material Issues ***************************  

class CancelMaterialIssue(models.TransientModel):
    _name = 'cancel.material.request'
    _description = 'Cancel Material Request Wizard'
    
    reason = fields.Text(string='Reason', required=True)
    
    # @api.multi
    def action_cancel(self):
        active_id = self._context.get('active_id')
        request_obj = self.env['material.request']
        request_browse = request_obj.browse(active_id)
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in request_browse:
            each.history += "\nThis request has been rejected by " + str(self.env.user.name) + " for the reason - '" + str(self.reason) + "'" + " on " + str(date)
            each.state = 'cancelled'
            for lines in each.request_lines:
                lines.state = 'cancelled'
        return True
        
class ForceCloseMaterialIssue(models.TransientModel):
    _name = 'force.close.material.issue'
    _description = 'Force Close Material issue Wizard'
    
    reason = fields.Text(string='Reason', required=True)
    
    # @api.multi
    def action_close(self):
        active_id = self._context.get('active_id')
        issue_obj = self.env['material.issue']
        issue_browse = issue_obj.browse(active_id)
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in issue_browse:
            each.closed = True
            each.history += "\nIssue has been force closed by " + str(self.env.user.name) + " for the reason - '" + str(self.reason) + "'" + " on " + str(date)
            each.state = 'done'
            for lines in each.issue_lines:
                if lines.pending_qty:
                    lines.closed = True
                lines.state = 'done'
        return True
        
class ForceCloseMaterialReturn(models.TransientModel):
    _name = 'force.close.material.return'
    _description = 'Force Close Material Return Wizard'
    
    reason = fields.Text(string='Reason', required=True)
    
    # @api.multi
    def action_close(self):
        active_id = self._context.get('active_id')
        return_obj = self.env['material.return']
        return_browse = return_obj.browse(active_id)
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in return_browse:
            each.closed = True
            each.history += "\nReturn has been force closed by " + str(self.env.user.name) + " for the reason - '" + str(self.reason) + "'" + " on " + str(date)
            each.state = 'done'
            for lines in each.return_lines:
                if lines.pending_qty:
                    lines.closed = True
                lines.state = 'done'
        return True
        
#******************** Internal transfers *************************

class RejectInternalStockTransferRequest(models.TransientModel):
    _name = 'reject.internal.stock.transfer.request'
    _description = 'Reject Internal Stock Transfer Request Wizard'
    
    reason = fields.Text(string='Reason', required=True)
    
    # @api.multi
    def action_close(self):
        active_id = self._context.get('active_id')
        request_obj = self.env['internal.stock.transfer.request']
        request_browse = request_obj.browse(active_id)
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in request_browse:
            each.history += "\nThis request has been rejected by " + str(self.env.user.name) + " for the reason - '" + str(self.reason) + "'" + " on " + str(date)
            each.state = 'cancelled'
            for lines in each.request_lines:
                lines.state = 'cancelled'
        return True
        
class ForceCloseInternalStockTransferIssue(models.TransientModel):
    _name = 'force.close.internal.stock.transfer.issue'
    _description = 'Force Close Internal Stock Transfer Issue Wizard'
    
    reason = fields.Text(string='Reason', required=True)
    
    # @api.multi
    def action_close(self):
        active_id = self._context.get('active_id')
        issue_obj = self.env['internal.stock.transfer.issue']
        issue_browse = issue_obj.browse(active_id)
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in issue_browse:
            each.closed = True
            each.history += "\nThis issue has been force closed by " + str(self.env.user.name) + " for the reason - '" + str(self.reason) + "'" + " on " + str(date)
            each.state = 'done'
            for lines in each.issue_lines:
                if lines.pending_issue_qty:
                    lines.closed = True
                lines.state = 'done'
        return True
        
class ForceCloseInternalStockTransferReceipt(models.TransientModel):
    _name = 'force.close.internal.stock.transfer.receipt'
    _description = 'Force Close Internal Stock Transfer Receipt Wizard'
    
    reason = fields.Text(string='Reason', required=True)
    
    # @api.multi
    def action_close(self):
        active_id = self._context.get('active_id')
        receipt_obj = self.env['internal.stock.transfer.receipt']
        picking_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        receipt_browse = receipt_obj.browse(active_id)
        picking_id = False
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in receipt_browse:
            each.closed = True
            each.force_closed_reason = self.reason
            each.history = "\nThis receipt has been force closed by " + str(self.env.user.name) + " for the reason - '" + str(self.reason) + "'" + " on " + str(date)
            each.state = 'done'
            for line in each.receipt_lines:
                if not picking_id and line.state != 'done':
                    picking_id = picking_obj.create({
                        'location_dest_id': each.sudo().warehouse_master_id.issuing_warehouse_id.transit_loss_location_id and each.sudo().warehouse_master_id.issuing_warehouse_id.transit_loss_location_id.id or False,
                        'location_id': each.sudo().warehouse_master_id.issuing_warehouse_id.transit_location_id and each.sudo().warehouse_master_id.issuing_warehouse_id.transit_location_id.id or False,
                        'origin': str(each.sudo().issue_id.name) + '/' + str(each.name),
                        'picking_type_id': each.sudo().warehouse_master_id.issuing_warehouse_id.int_type_id and each.sudo().warehouse_master_id.issuing_warehouse_id.int_type_id.id or False,
                        'internal_stock_transfer_issue_id': each.sudo().issue_id.id,
                        })
                if line.state != 'done':
                    move_obj.create({
                        'product_id': line.product_id and line.product_id.id or False,
                        'product_uom': line.uom_id and line.uom_id.id or False,
                        'product_uom_qty': line.pending_receipt_qty and line.pending_receipt_qty or False,
                        'name': line.product_id.name_get()[0][1] + '/' + str(each.name),
                        'origin': str(each.sudo().issue_id.name) + '/' + str(each.name),
                        'location_dest_id': each.sudo().warehouse_master_id.issuing_warehouse_id.transit_loss_location_id and each.sudo().warehouse_master_id.issuing_warehouse_id.transit_loss_location_id.id or False,
                        'location_id': each.sudo().warehouse_master_id.issuing_warehouse_id.transit_location_id and each.sudo().warehouse_master_id.issuing_warehouse_id.transit_location_id.id or False,
                        'picking_id': picking_id.id ,
                        'internal_stock_transfer_receipt_id': each.id,
                        'internal_stock_transfer_receipt_line_id': line.id,
                        'internal_stock_transfer_request_id': each.request_id and each.request_id.id or False,
                        #'internal_stock_transfer_issue_id': each.sudo().issue_id and each.sudo().issue_id.id or False,
                        'picking_type_id': each.sudo().warehouse_master_id.issuing_warehouse_id.int_type_id and each.sudo().warehouse_master_id.issuing_warehouse_id.int_type_id.id or False
                                })
                    if line.pending_receipt_qty:
                        line.closed = True
                    line.state = 'done'
        if picking_id:
            picking_id.action_confirm()
            picking_id.action_assign()
            picking_id.force_assign()
            for pack_line in picking_id.move_ids_without_package:
                pack_line.write({'product_packaging_quantity': pack_line.product_qty})
            # picking_id.do_transfer()
            picking_id.button_validate()
        return True
        
