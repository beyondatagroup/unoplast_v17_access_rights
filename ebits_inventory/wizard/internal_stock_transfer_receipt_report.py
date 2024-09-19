# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
import xlwt
import base64
from lxml import etree
import io
from odoo.addons.ebits_inventory.wizard.excel_styles import ExcelStyles
import json


class InternalStockTransferReceiptRegistedReportWizard(models.TransientModel):
    _name = 'internal.stock.transfer.receipt.register.report.wizard'
    _description = 'Internal Stock Transfer Receipt Register Report'
    
    # @api.multi
    def _get_issuing_warehouse(self):
        transfer_master_obj = self.env['internal.stock.transfer.master']
        transfer_master_list = []
        issuing_warehouse_id = []
        warehouse_ids = []
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            if self.env.user.sudo().default_warehouse_ids:
                for each in self.env.user.sudo().default_warehouse_ids:
                     warehouse_ids.append(each.id)
                transfer_search = transfer_master_obj.sudo().search([('requesting_warehouse_id', 'in', warehouse_ids)])
                for each_transfer in transfer_search:
                    if each_transfer.issuing_warehouse_id.id not in issuing_warehouse_id:
                        transfer_master_list.append((str(each_transfer.issuing_warehouse_id.id), str(each_transfer.issuing_warehouse_id.name)))
                        issuing_warehouse_id.append(each_transfer.issuing_warehouse_id.id)
        else:
            transfer_search = transfer_master_obj.sudo().search([])
            for each_transfer in transfer_search:
                if each_transfer.issuing_warehouse_id.id not in issuing_warehouse_id:
                    transfer_master_list.append((str(each_transfer.issuing_warehouse_id.id), str(each_transfer.issuing_warehouse_id.name)))
                    issuing_warehouse_id.append(each_transfer.issuing_warehouse_id.id)
        return transfer_master_list
    
    
    date_from = fields.Date(string='From Date(Receipt Date)')
    date_to = fields.Date(string='To Date(Receipt Date)')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_internal_transfer_receipt_register_warehouse', 'internal_transfer_receipt_register_wizard_id', 'warehouse_id', string='Receiving Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_internal_transfer_receipt_register_product', 'internal_transfer_receipt_register_wizard_id', 'product_id', string='Product')
    receive_type = fields.Selection([
        ('completed_received', 'Completely Received'),
        ('pending_received', 'Pending Receipt')], string='Receipt Type', required=True)
    warehouse_type = fields.Boolean('Warehouse', default=False)
    issuing_warehouse = fields.Selection(_get_issuing_warehouse, string='Issuing Warehouse') 
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(InternalStockTransferReceiptRegistedReportWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='warehouse_ids']"):
                warehouse_id = []
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                node.set('domain', "[('id', 'in', " + str(warehouse_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res
        
    @api.onchange('warehouse_ids', 'issuing_warehouse')
    def _onchange_warehouse_ids(self):
        transfer_master_obj = self.env['internal.stock.transfer.master']
        warning = {}
        if self.warehouse_ids:
            self.warehouse_type = True
        else:
            self.warehouse_type = False
        if self.warehouse_ids and self.issuing_warehouse:
            for each in self.warehouse_ids:
                transfer_search = transfer_master_obj.search([('requesting_warehouse_id', '=', each.ids), ('issuing_warehouse_id', '=', int(self.issuing_warehouse))])
            if not transfer_search:
                 self.issuing_warehouse = ''
                 warning = {
                    'title': _('Warning'),
                    'message': _('This warehouse has not yet made any issued.')}
            return {'warning': warning}
   
    # @api.multi
    def action_print_report(self):
        transfer_receive_obj = self.env['internal.stock.transfer.receipt']
        transfer_master_obj = self.env['internal.stock.transfer.master']
        date_from = self.date_from
        date_to = self.date_to
        curr_date = fields.date.today()
        curr_date = curr_date.strftime("%d-%m-%Y")
        report_name = "Internal Stock Transfer Receipt Report"
        if self.receive_type == 'completed_received':
            # from_date = time.strptime(self.date_from, "%Y-%m-%d")
            # from_date = time.strftime('%d-%m-%Y', from_date)
            # to_date = time.strptime(self.date_to, "%Y-%m-%d")
            # to_date = time.strftime('%d-%m-%Y', to_date)
            from_date_str = self.date_from.strftime('%Y-%m-%d')
            from_date = time.strptime(from_date_str, "%Y-%m-%d")
            from_date = time.strftime('%d-%m-%Y', from_date)

            # Similarly for date_to if needed
            to_date_str = self.date_to.strftime('%Y-%m-%d')
            to_date = time.strptime(to_date_str, "%Y-%m-%d")
            to_date = time.strftime('%d-%m-%Y', to_date)
            filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date) 
        else:
            filters = "Filter Based as on date :" + curr_date
        warehouse_sql = """ """
        product_sql = """ """
        issue_warehouse_sql = """ """
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        product_ids = []
        product_list = []
        product_str = ""
        
        domain_default = []
        domain_default = [('state', 'in', ('draft', 'partial'))]
       
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(product_ids) > 1:
                product_sql += "and sm.product_id in "+ str(tuple(product_ids))
            else:
                product_sql += "and sm.product_id in ("+ str(product_ids[0]) + ")"
            filters += ", Product: " + product_str 
            
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
        if warehouse_ids:
            transfer_master_list = []
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            transfer_search = transfer_master_obj.search([('requesting_warehouse_id', 'in', warehouse_ids)])
            for each_transfer in transfer_search:
                 transfer_master_list.append(each_transfer.issuing_warehouse_id.id)
                 transfer_master_list = list(set(transfer_master_list))
            if len(warehouse_ids) > 1:
                warehouse_sql += "and ist_rept.receiving_warehouse_id in "+ str(tuple(warehouse_ids))
                domain_default = domain_default + [('receiving_warehouse_id', 'in', tuple(warehouse_ids))]
            else:
                warehouse_sql += "and ist_rept.receiving_warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                domain_default = domain_default + [('receiving_warehouse_id', '=', warehouse_ids[0])]
            if len(transfer_master_list) > 1:
                warehouse_sql += " and rmaster.issuing_warehouse_id in "+ str(tuple(transfer_master_list))
                domain_default = domain_default + [('warehouse_master_id.issuing_warehouse_id', 'in', tuple(transfer_master_list))]
            else:
                warehouse_sql += " and rmaster.issuing_warehouse_id = "+ str(transfer_master_list[0])
                domain_default = domain_default + [('warehouse_master_id.issuing_warehouse_id', '=', transfer_master_list[0])]
            filters += ", Receiving Warehouse: " + warehouse_str
        
        if self.issuing_warehouse:
            warehouse_search = self.env['stock.warehouse'].sudo().search([('id', '=', int(self.issuing_warehouse))])
            issue_warehouse_sql += "and rmaster.issuing_warehouse_id = "+ (self.issuing_warehouse)
            domain_default = domain_default + [('warehouse_master_id.issuing_warehouse_id', '=', transfer_master_list[0])]
            filters += ", Issuing Warehouse :" + (warehouse_search.name and warehouse_search.name or '')
                
        internal_stock_receipt_sql = """select 
                                        ist_rept.name as receipt_no,
                                        ist_rept.request_no as request_no, 
                                        ist_iss.name as issue_no,
                                        rp.name as received_by,
                                        sw_rept.name as receiving_warehouse,
                                        ist_rept.issue_ref as reference,
                                        ist_rept.issue_warehouse as issuing_warehouse,
                                        to_char(((sm.date at time zone %s)::timestamp::date), 'dd-mm-yyyy') as receipt_date,
                                        concat( '[' , pp.default_code, '] ', pt.name) as product,
                                        pu.name as uom,
                                        sm.product_uom_qty as quantity,
                                        te.name as driver,
                                        sp.driver_name as driver_name,
                                        sp.driver_licence as driver_licence, 
                                        sp.driver_licence_type as licence_type,
                                        sp.driver_licence_place as licence_place,
                                        sp.driver_phone as driver_phone,
                                        sp.vehicle_no as vehicle_no,
                                        sp.vehicle_owner as vehicle_owner,
                                        sp.vehicle_owner_address as owner_address,
                                        sp.agent_name as agent_name,
                                        (case when ist_rept.closed = True then 'Yes' else 'No' end) as force_closed,
                                        (case when sm.state = 'assigned' then 'Available' 
	                                     when sm.state = 'confirmed' then 'Waiting Availability' 
	                                     when sm.state = 'waiting' then 'waiting Another Move' 
	                                     when sm.state = 'done' then 'Done' else sm.state end) as status,
                                        (case when ist_rept.state = 'draft' then 'Draft' 
	                                     when ist_rept.state = 'partial' then 'Partially Issued' 
	                                     when ist_rept.state = 'done' then 'Done' else ist_rept.state end) as form_status
                                    from stock_move sm
                                        left join internal_stock_transfer_receipt ist_rept on (ist_rept.id = sm.internal_stock_transfer_receipt_id)
                                        left join internal_stock_transfer_issue ist_iss on (ist_iss.id = ist_rept.issue_id)
                                        left join res_users ru on (ru.id = ist_rept.receiver_user_id)
                                        left join res_partner rp on (rp.id = ru.partner_id)
                                        left join product_product pp on (pp.id = sm.product_id)
                                        left join product_template pt on (pt.id = pp.product_tmpl_id)
                                        left join uom_uom pu on (pu.id = pt.uom_id)
                                        left join stock_warehouse sw_rept on (sw_rept.id = ist_rept.receiving_warehouse_id)
                                        left join stock_picking sp on (sp.id = sm.picking_id)
                                        left join truck_driver_employee te on (te.id = sp.driver_id)
                                        left join internal_stock_transfer_master rmaster on (rmaster.id = ist_rept.warehouse_master_id)
                                    where (((sm.date at time zone %s)::timestamp::date) between %s and %s) and  sm.internal_stock_transfer_receipt_id is not null and sm.state = 'done'"""+ warehouse_sql + product_sql + issue_warehouse_sql +""" order by sm.date""" 
                        
        if self.receive_type == 'completed_received':
            tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
            self.env.cr.execute(internal_stock_receipt_sql, (tz, tz, date_from, date_to))
            internal_stock_receipt_data = self.env.cr.dictfetchall()
        else:
            internal_stock_receipt_data = transfer_receive_obj.sudo().search(domain_default, order="name")
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4000
        sheet1.col(2).width = 4000
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 4000
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 5000
        sheet1.col(7).width = 4500
        sheet1.col(8).width = 4500
        sheet1.col(9).width = 9500
        sheet1.col(10).width = 3000
        sheet1.col(11).width = 4500
        sheet1.col(12).width = 5500
        sheet1.col(13).width = 6500
        sheet1.col(14).width = 4500
        sheet1.col(15).width = 4500
        sheet1.col(16).width = 4500
        sheet1.col(17).width = 4500
        sheet1.col(18).width = 4500
        sheet1.col(19).width = 4500
        sheet1.col(20).width = 4500
        sheet1.col(21).width = 3500
        sheet1.col(22).width = 3500
        sheet1.col(23).width = 3500
        sheet1.col(24).width = 3500
        sheet1.col(25).width = 3500
        
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        if self.receive_type == 'completed_received':
            title = report_name +' ( From ' + from_date + ' To ' + to_date + ' )'
            sheet1.write_merge(rc, rc, 0, 23, (self.company_id and self.company_id.name or ''), Style.title())
            sheet1.write_merge(r1, r1, 0, 23, title, Style.title())
            sheet1.write_merge(r2, r2, 0, 23, filters, Style.groupByTitle())
        else:
            title = report_name +' as on date :'+ curr_date
            sheet1.write_merge(rc, rc, 0, 24, (self.company_id and self.company_id.name or ''), Style.title())
            sheet1.write_merge(r1, r1, 0, 24, title, Style.title())
            sheet1.write_merge(r2, r2, 0, 24, filters, Style.groupByTitle())
        
        if self.receive_type == 'completed_received':
            sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 1, "Receipt Date", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 2, "Receipt No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 3, "Request No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 4, "Issue No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 5, "Issue Reference", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 6, "Received By", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 7, "Receiving Warehouse", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 8, "Issuing Warehouse", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 9, "Product", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 10, "UOM", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 11, "Received Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 12, "Driver", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 13, "Driver Name", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 14, "Driver Licence", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 15, "Driver Licence Type", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 16, "Driver Licence Place", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 17, "Driver Phone", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 18, "Vehicle No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 19, "Vehicle Owner", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 20, "Vehicle Owner Address", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 21, "Agent Name", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 22, "Status", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 23, "Force Closed", Style.contentTextBold(r3, 'black', 'white'))
        else:
            sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 1, "Receipt No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 2, "Request No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 3, "Required Date", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 4, "Issue No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 5, "Issue Reference", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 6, "Received By", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 7, "Receiving Warehouse", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 8, "Issuing Warehouse", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 9, "Product", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 10, "UOM", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 11, "Issued Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 12, "Received Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 13, "Pending Receipt Quatity Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 14, "Driver", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 15, "Driver Name", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 16, "Driver Licence", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 17, "Driver Licence Type", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 18, "Driver Licence Place", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 19, "Driver Phone", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 20, "Vehicle No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 21, "Vehicle Owner", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 22, "Vehicle Owner Address", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 23, "Agent Name", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 24, "Status", Style.contentTextBold(r3, 'black', 'white'))
        
        row = 3
        s_no = 0
        for each in internal_stock_receipt_data:
            if self.receive_type == 'completed_received':
                product_str = each['product']
                product_data = json.loads(product_str.split('[] ')[-1])
                s_no += 1
                row += 1
                sheet1.row(row).height = 450
                sheet1.write(row, 0, s_no, Style.normal_left())
                sheet1.write(row, 1, each['receipt_date'], Style.normal_left())
                sheet1.write(row, 2, each['receipt_no'], Style.normal_left())
                sheet1.write(row, 3, each['request_no'], Style.normal_left())
                sheet1.write(row, 4, each['issue_no'], Style.normal_left())
                sheet1.write(row, 5, each['reference'], Style.normal_left())
                sheet1.write(row, 6, each['received_by'], Style.normal_left())
                sheet1.write(row, 7, each['receiving_warehouse'], Style.normal_left())
                sheet1.write(row, 8, each['issuing_warehouse'], Style.normal_left())
                sheet1.write(row, 9, product_data['en_US'], Style.normal_left())
                sheet1.write(row, 10, each['uom']['en_US'], Style.normal_left())
                sheet1.write(row, 11, each['quantity'], Style.normal_num_right_3digits())
                sheet1.write(row, 12, each['driver']['en_US'], Style.normal_left())
                sheet1.write(row, 13, each['driver_name'], Style.normal_left())
                sheet1.write(row, 14, each['driver_licence'], Style.normal_left())
                sheet1.write(row, 15, each['licence_type'], Style.normal_left())
                sheet1.write(row, 16, each['licence_place'], Style.normal_left())
                sheet1.write(row, 17, each['driver_phone'], Style.normal_left())
                sheet1.write(row, 18, each['vehicle_no'], Style.normal_left())
                sheet1.write(row, 19, each['vehicle_owner'], Style.normal_left())
                sheet1.write(row, 20, each['owner_address'], Style.normal_left())
                sheet1.write(row, 21, each['agent_name'], Style.normal_left())
                sheet1.write(row, 22, each['status'], Style.normal_left())
                sheet1.write(row, 23, each['force_closed'], Style.normal_left())
            else:
                for line in each.receipt_lines:
                    if self.product_ids and line.product_id.id not in product_ids:
                        continue
                    if line.state == 'done':
                        continue
                    s_no += 1
                    row += 1
                    sheet1.row(row).height = 450
                    sheet1.write(row, 0, s_no, Style.normal_left())
                    sheet1.write(row, 1, each.name and each.name or '', Style.normal_left())
                    sheet1.write(row, 2, each.request_no and each.request_no or '', Style.normal_left())
                    req_date = ""
                    if line.date_required:
                        req_date = time.strptime(line.date_required, "%Y-%m-%d")
                        req_date = time.strftime('%d-%m-%Y', req_date)
                    sheet1.write(row, 3, req_date, Style.normal_left())
                    sheet1.write(row, 4, each.issue_id and each.issue_id.name or '', Style.normal_left())
                    sheet1.write(row, 5, each.issue_id and each.issue_ref or '', Style.normal_left())
                    sheet1.write(row, 6, each.receiver_user_id and each.receiver_user_id.name or '', Style.normal_left())
                    sheet1.write(row, 7, each.receiving_warehouse_id and each.receiving_warehouse_id.name or '', Style.normal_left())
                    sheet1.write(row, 8, each.issue_warehouse and each.issue_warehouse or '', Style.normal_left())
                    sheet1.write(row, 9, line.product_id and line.product_id.name_get()[0][1] or '', Style.normal_left())
                    sheet1.write(row, 10, line.uom_id and line.uom_id.name or '', Style.normal_left())
                    sheet1.write(row, 11, line.issued_qty and line.issued_qty or 0.00, Style.normal_num_right_3digits())
                    sheet1.write(row, 12, line.received_qty and line.received_qty or 0.00, Style.normal_num_right_3digits())
                    sheet1.write(row, 13, line.pending_receipt_qty and line.pending_receipt_qty or 0.00, Style.normal_num_right_3digits())
                    sheet1.write(row, 14, each.driver_id and each.driver_id.name or '', Style.normal_left())
                    sheet1.write(row, 15, each.driver_name and each.driver_name or '', Style.normal_left())
                    sheet1.write(row, 16, each.driver_licence and each.driver_licence or '', Style.normal_left())
                    sheet1.write(row, 17, each.driver_licence_type and each.driver_licence_type or '', Style.normal_left())
                    sheet1.write(row, 18, each.driver_licence_place and each.driver_licence_place or '', Style.normal_left())
                    sheet1.write(row, 19, each.driver_phone and each.driver_phone or '', Style.normal_left())
                    sheet1.write(row, 20, each.vehicle_no and each.vehicle_no or '', Style.normal_left())
                    sheet1.write(row, 21, each.vehicle_owner and each.vehicle_owner or '', Style.normal_left())
                    sheet1.write(row, 22, each.vehicle_owner_address and each.vehicle_owner_address or '', Style.normal_left())
                    sheet1.write(row, 23, each.agent_name and each.agent_name or '', Style.normal_left())
                    state = ''
                    if line.state == 'draft':
                        state = 'Draft'
                    if line.state == 'partial':
                        state = 'Partially Received'
                    sheet1.write(row, 24, state, Style.normal_left())

        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()
        self.write({'name': report_name + '.xls', 'output':base64.encodebytes(binary_data)})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'internal.stock.transfer.receipt.register.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
