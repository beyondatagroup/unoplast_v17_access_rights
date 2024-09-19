# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
import io
# from excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
import xlwt
# import cStringIO
import base64
import xlrd
# import parser
from lxml import etree
from odoo.addons.ebits_inventory.wizard.excel_styles import ExcelStyles



class InternalStockTransferIssueRegistedReportWizard(models.TransientModel):
    _name = 'internal.stock.transfer.issue.register.report.wizard'
    _description = 'Internal Stock Transfer Issue Register Report'
    
    # @api.multi
    def _get_requesting_warehouse(self):
        transfer_master_obj = self.env['internal.stock.transfer.master']
        transfer_master_list = []
        requesting_warehouse_id = []
        warehouse_ids = []
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            if self.env.user.sudo().default_warehouse_ids:
                for each in self.env.user.sudo().default_warehouse_ids:
                     warehouse_ids.append(each.id)
                transfer_search = transfer_master_obj.sudo().search([('issuing_warehouse_id', 'in', warehouse_ids)])
                for each_transfer in transfer_search:
                    if each_transfer.requesting_warehouse_id.id not in requesting_warehouse_id:
                        transfer_master_list.append((str(each_transfer.requesting_warehouse_id.id), str(each_transfer.requesting_warehouse_id.name)))
                        requesting_warehouse_id.append(each_transfer.requesting_warehouse_id.id)
        else:
            transfer_search = transfer_master_obj.sudo().search([])
            for each_transfer in transfer_search:
                if each_transfer.requesting_warehouse_id.id not in requesting_warehouse_id:
                    transfer_master_list.append((str(each_transfer.requesting_warehouse_id.id), str(each_transfer.requesting_warehouse_id.name)))
                    requesting_warehouse_id.append(each_transfer.requesting_warehouse_id.id)
        return transfer_master_list
    
    
    date_from = fields.Date(string='From Date(Issued Date)')
    date_to = fields.Date(string='To Date(Issued Date)')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_internal_transfer_issue_register_warehouse', 'internal_transfer_issue_register_wizard_id', 'warehouse_id', string='Issuing Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_internal_transfer_issue_register_product', 'internal_transfer_issue_register_wizard_id', 'product_id', string='Product')
    req_warehouse = fields.Selection(_get_requesting_warehouse, string="Requesting  Warehouse", store=True)
    warehouse_type = fields.Boolean('Warehouse', default=False)
    issue_type = fields.Selection([
        ('completed_issue', 'Completely Issued'),
        ('pending_issue', 'Pending Issue')], string='Issue Type', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(InternalStockTransferIssueRegistedReportWizard, self).fields_view_get(
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
        
    @api.onchange('warehouse_ids', 'req_warehouse')
    def _onchange_warehouse_ids(self):
        transfer_master_obj = self.env['internal.stock.transfer.master']
        warning = {}
        if self.warehouse_ids:
            self.warehouse_type = True
        else:
            self.warehouse_type = False
        if self.warehouse_ids and self.req_warehouse:
            for each in self.warehouse_ids:
                transfer_search = transfer_master_obj.search([('issuing_warehouse_id', '=', each.ids), ('requesting_warehouse_id', '=', int(self.req_warehouse))])
            if not transfer_search:
                 self.req_warehouse = ''
                 warning = {
                    'title': _('Warning'),
                    'message': _('No issues available for the selected warehouses.')}
            return {'warning': warning}
            
    # @api.multi
    def action_print_report(self):
        transfer_issue_obj = self.env['internal.stock.transfer.issue']
        transfer_master_obj = self.env['internal.stock.transfer.master']
        report_name = "Internal Stock Transfer Issue Report"
        curr_date = fields.date.today()
        curr_date = curr_date.strftime("%d-%m-%Y")
        if self.issue_type == 'completed_issue':
            date_from = self.date_from
            date_to = self.date_to
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
            filters = "Filter Based on Issue Date From : "+ str(from_date) + " , To : "+ str(to_date) 
        else:
            filters = "Filter Based as on date : " + curr_date
        product_sql = """ """
        req_warehouse_sql = """ """
        warehouse_sql = """ """
        
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
            transfer_search = transfer_master_obj.search([('issuing_warehouse_id', 'in', warehouse_ids)])
            for each_transfer in transfer_search:
                 transfer_master_list.append(each_transfer.requesting_warehouse_id.id)
                 transfer_master_list = list(set(transfer_master_list))
            if len(warehouse_ids) > 1:
                warehouse_sql += "and rmaster.issuing_warehouse_id in "+ str(tuple(warehouse_ids))
                domain_default = domain_default + [('issuing_warehouse_id', 'in', tuple(warehouse_ids))]
            else:
                warehouse_sql += "and rmaster.issuing_warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                domain_default = domain_default + [('issuing_warehouse_id', '=', warehouse_ids[0])]
            if len(transfer_master_list) > 1:
                warehouse_sql += " and rmaster.requesting_warehouse_id in "+ str(tuple(transfer_master_list))
                domain_default = domain_default + [('warehouse_master_id.requesting_warehouse_id', 'in', tuple(transfer_master_list))]
            else:
                warehouse_sql += " and rmaster.requesting_warehouse_id = "+ str(transfer_master_list[0])
                domain_default = domain_default + [('warehouse_master_id.requesting_warehouse_id', '=', transfer_master_list[0])]
            filters += ", Issuing Warehouse: " + warehouse_str
        
        if self.req_warehouse:
            warehouse_search = self.env['stock.warehouse'].sudo().search([('id', '=', int(self.req_warehouse))])
            req_warehouse_sql += "and rmaster.requesting_warehouse_id = "+ self.req_warehouse
            domain_default = domain_default + [('warehouse_master_id.requesting_warehouse_id', '=', int(self.req_warehouse))]
            filters += ", Requesting Warehouse :" + (warehouse_search.name and warehouse_search.name or '')
                
        internal_stock_issue_sql = """select 
	                                    ist_iss.name as issue_no,
	                                    ist_iss.request_no as request_no, 
	                                    sw_iss.name as issuing_warehouse,
	                                    ist_iss.request_warehouse as req_warehouse,
	                                    to_char(((sm.date at time zone %s)::timestamp::date), 'dd-mm-yyyy') as issue_date,
	                                    concat( '[' , pp.default_code, '] ', pt.name) as product,
	                                    pu.name as uom,
	                                    sm.product_uom_qty as quantity,
	                                    (select ist_issli.approved_qty from internal_stock_transfer_issue_line ist_issli 
	                                         where ist_issli.product_id = sm.product_id and ist_issli.issue_id = ist_iss.id) as approved_qty,
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
	                                    (case when ist_iss.closed = True then 'Yes' else 'No' end) as force_closed,
	                                    (case when sm.state = 'assigned' then 'Available' 
	                                         when sm.state = 'confirmed' then 'Waiting Availability' 
	                                         when sm.state = 'waiting' then 'waiting Another Move' 
	                                         when sm.state = 'done' then 'Done' else sm.state end) as status,
	                                    (case when ist_iss.state = 'draft' then 'Draft' 
	                                         when ist_iss.state = 'partial' then 'Partially Issued' 
	                                         when ist_iss.state = 'done' then 'Done' else ist_iss.state end) as form_status
                                    from stock_move sm
	                                    left join internal_stock_transfer_issue ist_iss on (ist_iss.id = sm.internal_stock_transfer_issue_id)
	                                    left join product_product pp on (pp.id = sm.product_id)
	                                    left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                    left join uom_uom pu on (pu.id = pt.uom_id)
	                                    left join stock_warehouse sw_iss on (sw_iss.id = ist_iss.issuing_warehouse_id)
	                                    left join stock_picking sp on (sp.id = sm.picking_id)
	                                    left join truck_driver_employee te on (te.id = sp.driver_id)
	                                    left join internal_stock_transfer_master rmaster on (rmaster.id = ist_iss.warehouse_master_id)
                                    where (((sm.date at time zone %s)::timestamp::date) between %s and %s) and sm.internal_stock_transfer_issue_id is not null and sm.internal_stock_transfer_receipt_id is null and sm.state = 'done'"""+ warehouse_sql + product_sql + req_warehouse_sql + """ order by sm.date""" 
                        
        if self.issue_type == 'completed_issue':
            tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
            self.env.cr.execute(internal_stock_issue_sql, (tz, tz, date_from, date_to))
            internal_stock_issue_data = self.env.cr.dictfetchall()
        else:
            internal_stock_issue_data = transfer_issue_obj.sudo().search(domain_default, order="name")
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        if self.issue_type == 'completed_issue':
            sheet1.col(0).width = 2000
            sheet1.col(1).width = 4000
            sheet1.col(2).width = 4500
            sheet1.col(3).width = 3500
            sheet1.col(4).width = 5500
            sheet1.col(5).width = 5500
            sheet1.col(6).width = 10500
            sheet1.col(7).width = 3500
            sheet1.col(8).width = 4500
            sheet1.col(9).width = 4500
            sheet1.col(10).width = 9500
            sheet1.col(11).width = 9500
            sheet1.col(12).width = 4500
            sheet1.col(13).width = 9500
            sheet1.col(14).width = 4500
            sheet1.col(15).width = 5000
            sheet1.col(16).width = 7500
            sheet1.col(17).width = 7500
            sheet1.col(18).width = 7500
            sheet1.col(19).width = 3500
            sheet1.col(20).width = 3500
            sheet1.col(21).width = 3500
        else:
            sheet1.col(0).width = 2000
            sheet1.col(1).width = 4000
            sheet1.col(2).width = 4000
            sheet1.col(3).width = 4500
            sheet1.col(4).width = 5500
            sheet1.col(5).width = 5500
            sheet1.col(6).width = 10500
            sheet1.col(7).width = 3500
            sheet1.col(8).width = 3500
            sheet1.col(9).width = 3500
            sheet1.col(10).width = 3500
            sheet1.col(11).width = 4000
        
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        if self.issue_type == 'completed_issue':
            title = report_name +' ( From ' + from_date + ' To ' + to_date + ' )'
            sheet1.write_merge(rc, rc, 0, 21, (self.company_id and self.company_id.name or ' '), Style.title())
            sheet1.write_merge(r1, r1, 0, 21, title, Style.title())
            sheet1.write_merge(r2, r2, 0, 21, filters, Style.groupByTitle())
        else:
            title = report_name + ' as on date: ' + curr_date  
            sheet1.write_merge(rc, rc, 0, 11, (self.company_id and self.company_id.name or ' '), Style.title())
            sheet1.write_merge(r1, r1, 0, 11, title, Style.title())
            sheet1.write_merge(r2, r2, 0, 11, filters, Style.groupByTitle())
        
        if self.issue_type == 'completed_issue':
            sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 1, "Issue Date", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 2, "Issue No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 3, "Request No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 4, "Requesting Warehouse", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 5, "Issuing Warehouse", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 6, "Product", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 7, "UOM", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 8, "Approved Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 9, "Issued Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 10, "Driver", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 11, "Driver Name", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 12, "Driver Licence No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 13, "Driver Licence Type", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 14, "Driver Licence Place", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 15, "Driver Phone", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 16, "Vehicle No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 17, "Vehicle Owner", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 18, "Vehicle Owner Address", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 19, "Agent Name", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 20, "Status", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 21, "Force Closed", Style.contentTextBold(r3, 'black', 'white'))
        else:
            sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 1, "Issue No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 2, "Request No", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 3, "Required Date", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 4, "Requesting Warehouse", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 5, "Issuing Warehouse", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 6, "Product", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 7, "UOM", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 8, "Approved Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 9, "Issued Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 10, "Pending Issue Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet1.write(r3, 11, "Status", Style.contentTextBold(r3, 'black', 'white'))
        
        row = 3
        s_no = 0
        for each in internal_stock_issue_data:
            if self.issue_type == 'completed_issue':
                s_no += 1
                row += 1
                sheet1.row(row).height = 450
                sheet1.write(row, 0, s_no, Style.normal_left())
                sheet1.write(row, 1, each['issue_date'], Style.normal_left())
                sheet1.write(row, 2, each['issue_no'], Style.normal_left())
                sheet1.write(row, 3, each['request_no'], Style.normal_left())
                sheet1.write(row, 4, each['req_warehouse'], Style.normal_left())
                sheet1.write(row, 5, each['issuing_warehouse'], Style.normal_left())
                sheet1.write(row, 6, each['product'], Style.normal_left())
                sheet1.write(row, 7, each['uom']['en_US'], Style.normal_left())
                sheet1.write(row, 8, each['approved_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 9, each['quantity'], Style.normal_num_right_3digits())
                sheet1.write(row, 10, each['driver']['en_US'], Style.normal_left())
                sheet1.write(row, 11, each['driver_name'], Style.normal_left())
                sheet1.write(row, 12, each['driver_licence'], Style.normal_left())
                sheet1.write(row, 13, each['licence_type'], Style.normal_left())
                sheet1.write(row, 14, each['licence_place'], Style.normal_left())
                sheet1.write(row, 15, each['driver_phone'], Style.normal_left())
                sheet1.write(row, 16, each['vehicle_no'], Style.normal_left())
                sheet1.write(row, 17, each['vehicle_owner'], Style.normal_left())
                sheet1.write(row, 18, each['owner_address'], Style.normal_left())
                sheet1.write(row, 19, each['agent_name'], Style.normal_left())
                sheet1.write(row, 20, each['status'], Style.normal_left())
                sheet1.write(row, 21, each['force_closed'], Style.normal_left())
            else:
                for line in each.issue_lines:
                    if self.product_ids and line.product_id.id not in product_ids:
                        continue
                    if line.state in ('done', 'cancel'):
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
                    sheet1.write(row, 4, each.request_warehouse and each.request_warehouse or '', Style.normal_left())
                    sheet1.write(row, 5, each.issuing_warehouse_id and each.issuing_warehouse_id.name or '', Style.normal_left())
                    sheet1.write(row, 6, line.product_id and line.product_id.name_get()[0][1] or '', Style.normal_left())
                    sheet1.write(row, 7, line.uom_id and line.uom_id.name or '', Style.normal_left())
                    sheet1.write(row, 8, line.approved_qty and line.approved_qty or 0.00, Style.normal_num_right_3digits())
                    sheet1.write(row, 9, line.issued_qty and line.issued_qty or 0.00, Style.normal_num_right_3digits())
                    sheet1.write(row, 10, line.pending_issue_qty and line.pending_issue_qty or 0.00, Style.normal_num_right_3digits())
                    state = ''
                    if line.state == 'draft':
                        state = 'Draft'
                    if line.state == 'partial':
                        state = 'Partially Issued'
                    sheet1.write(row, 11, state, Style.normal_left())

        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()
        self.write({'name': report_name + '.xls', 'output':  base64.encodebytes(binary_data)})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'internal.stock.transfer.issue.register.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new',
                }
