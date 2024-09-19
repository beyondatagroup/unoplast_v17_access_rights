# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
import pytz
from odoo import api, fields, models, _
from odoo.tools.translate import _
from . import excel_styles
import xlwt
import io
import base64
import xlrd


class DriverDetailsWizard(models.TransientModel):
    _name = 'driver.details.wizard'
    _description = 'Driver Details Wizard'
    
    driver_id = fields.Many2one('truck.driver.employee', string="Driver", copy=False)
    vehicle_no = fields.Char(string="Vehicle No", size=64, copy=False)
    vehicle_owner = fields.Char(string="Vehicle Owner", size=64, copy=False)
    vehicle_owner_address = fields.Char(string="Vehicle Owner Address", size=128, copy=False)
    driver_licence = fields.Char(string="Driver Licence No", size=64, copy=False)
    driver_name = fields.Char(string="Driver Name", size=64, copy=False)
    driver_licence_type = fields.Char(string="Driver Licence Type", size=64, copy=False)
    driver_licence_place = fields.Char(string="Issued Licence Place", size=64, copy=False)
    driver_phone = fields.Char(string="Driver Contact No", size=64, copy=False)
    agent_name = fields.Char(string="Agent Name", size=64, copy=False)
    wizard_check = fields.Boolean(string="Check", copy=False)
    
    @api.model
    def default_get(self, fields):
        res = super(DriverDetailsWizard, self).default_get(fields)
        picking_obj = self.env['stock.picking']
        if self.env.context.get('active_id'):
            picking_bro = picking_obj.browse(self.env.context['active_id'])
        else:
            picking_bro = picking_obj
        res['driver_id'] = picking_bro.driver_id and picking_bro.driver_id.id or False
        res['vehicle_no'] = picking_bro.vehicle_no or ''
        res['vehicle_owner'] = picking_bro.vehicle_owner or ''
        res['vehicle_owner_address'] = picking_bro.vehicle_owner_address or ''
        res['driver_licence'] = picking_bro.driver_licence or ''
        res['driver_name'] = picking_bro.driver_name or ''
        res['driver_licence_type'] = picking_bro.driver_licence_type or ''
        res['driver_licence_place'] = picking_bro.driver_licence_place or ''
        res['driver_phone'] = picking_bro.driver_phone or ''
        res['agent_name'] = picking_bro.agent_name or ''
        res['wizard_check'] = True
        return res
    
    
    @api.onchange('driver_id')
    def onchange_driver_id(self):
        if self.wizard_check:
            self.wizard_check = False
            return {}
        if not self.wizard_check:
            if self.driver_id:
                self.driver_name = self.driver_id.name or ""
                self.driver_licence = self.driver_id.driver_licence or ""
                self.driver_licence_type = self.driver_id.driver_licence_type or ""
                self.driver_licence_place = self.driver_id.driver_licence_place or ""
                self.driver_phone =  self.driver_id.driver_phone or ""
            else:
                self.driver_name = ""
                self.driver_licence = ""
                self.driver_licence_type = ""
                self.driver_licence_place = ""
                self.driver_phone = ""
                
    def action_update(self):
        active_id = self._context.get('active_id')
        picking_obj = self.env['stock.picking']
        picking_browse = picking_obj.browse(active_id)
        for each in picking_browse:
            each.driver_id = self.driver_id and self.driver_id.id or False
            each.driver_name = self.driver_name and self.driver_name or ''
            each.driver_licence = self.driver_licence and self.driver_licence or ''
            each.driver_licence_type = self.driver_licence_type and self.driver_licence_type or ''
            each.driver_licence_place = self.driver_licence_place and self.driver_licence_place or ''
            each.agent_name =  self.agent_name and self.agent_name or ''
            each.vehicle_owner =  self.vehicle_owner and self.vehicle_owner or ''
            each.vehicle_no =  self.vehicle_no and self.vehicle_no or ''
            each.vehicle_owner_address =  self.vehicle_owner_address and self.vehicle_owner_address or ''
            each.driver_phone =  self.driver_phone and self.driver_phone or ''
        return True
        
class ReferenceDetailsWizard(models.TransientModel):
    _name = 'reference.details.wizard'
    _description = 'Reference Details Wizard'   
    
    
    reference_no = fields.Char(string='DC Reference No', size=64)
    reference_date = fields.Date(string='DC Reference Date')
    supplier_inv_no = fields.Char(string='Vendor Invoice No', size=64)
    supplier_inv_date = fields.Date(string='Vendor Invoice Date')
    gate_entry_ref = fields.Char(string='Gate Entry Ref', size=64)
    
    @api.model
    def default_get(self, fields):
        res = super(ReferenceDetailsWizard, self).default_get(fields)
        picking_obj = self.env['stock.picking']
        if self.env.context.get('active_id'):
            picking_bro = picking_obj.browse(self.env.context['active_id'])
        else:
            picking_bro = picking_obj
        res['reference_no'] = picking_bro.reference_no or ''
        res['reference_date'] = picking_bro.reference_date or False
        res['supplier_inv_no'] = picking_bro.supplier_inv_no or ''
        res['supplier_inv_date'] = picking_bro.supplier_inv_date or False
        res['gate_entry_ref'] = picking_bro.gate_entry_ref or ''
        return res
    
    def action_update(self):
        active_id = self._context.get('active_id')
        picking_obj = self.env['stock.picking']
        picking_browse = picking_obj.browse(active_id)
        for each in picking_browse:
            each.reference_no =  self.reference_no and self.reference_no or ''
            each.reference_date =  self.reference_date and self.reference_date or False
            each.supplier_inv_no =  self.supplier_inv_no and self.supplier_inv_no or ''
            each.supplier_inv_date =  self.supplier_inv_date and self.supplier_inv_date or False
            each.gate_entry_ref =  self.gate_entry_ref and self.gate_entry_ref or ''
        return True
        
class CancelReasonWizard(models.TransientModel):
    _name = 'picking.cancel.reason.wizard'
    _description = 'Stock Picking Cancel Reason Wizard'
    
    name = fields.Text(string='Cancel Reason', required=True)

    
    def action_cancel_reason(self):
        picking_id = self.env['stock.picking'].browse(self.env.context.get('active_id'))
        fmt = "%d-%m-%Y %H:%M:%S"
        date = fields.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        cancel_reason = ""
        for each in self:
            if picking_id.cancel_reason:
                cancel_reason = picking_id.cancel_reason + "\n"  
            # picking_id.mapped('move_lines').action_cancel()
            picking_id.mapped('move_lines')._action_cancel()
            picking_id.cancel_reason = cancel_reason + 'This document is cancelled by '+ self.env.user.name + ' on this date '+ date + '\nReason -- '+ each.name 
        return True
        
        
