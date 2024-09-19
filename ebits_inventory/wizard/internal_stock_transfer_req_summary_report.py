# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
# from excel_styles import ExcelStyles
import xlwt
import io
from io import StringIO
import base64
import xlrd
from lxml import etree
from odoo.addons.ebits_inventory.wizard.excel_styles import ExcelStyles


class InternalStockTransferRequestSummaryReportWizard(models.TransientModel):
    _name = 'internal.stock.transfer.request.summary.report.wizard'
    _description = 'Internal Stock Transfer Request Summary Report'
    
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
    
    date_from = fields.Date(string='From Date(Request Date)', required=True)
    date_to = fields.Date(string='To Date(Request Date)', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_internal_stock_transfer_req_warehouse', 'internal_stock_transfer_req_wizard_id', 'warehouse_id', string='Requesting Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_internal_stock_transfer_req_product', 'internal_stock_transfer_req_wizard_id', 'product_id', string='Product')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting for approval'),
        ('done', 'Approved')
        ], string='Status')
    warehouse_type = fields.Boolean('Warehouse', default=False)
    issuing_warehouse = fields.Selection(_get_issuing_warehouse, string='Issuing Warehouse') 
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(InternalStockTransferRequestSummaryReportWizard, self).fields_view_get(
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
                    'message': _('No request created for the selected warehouses.')}
            return {'warning': warning}
        
    # @api.multi
    def action_print_report(self):
        stock_transfer_req_obj = self.env['internal.stock.transfer.request']
        transfer_master_obj = self.env['internal.stock.transfer.master']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Internal Stock Transfer Request Report"
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
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        product_ids = []
        product_list = []
        product_str = ""
        
        domain_default = []
        domain_default = [('date_requested', '>=', self.date_from), ('date_requested', '<=', self.date_to)]
        
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            filters += ", Product : "+ product_str
            
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
                domain_default = domain_default + [('requesting_warehouse_id', 'in', tuple(warehouse_ids))]
            else:
                domain_default = domain_default + [('requesting_warehouse_id', '=', warehouse_ids[0])]
            if transfer_master_list:
                if len(transfer_master_list) > 1:
                    domain_default = domain_default + [('warehouse_master_id.issuing_warehouse_id', 'in', tuple(transfer_master_list))]
                else:
                    domain_default = domain_default + [('warehouse_master_id.issuing_warehouse_id', '=', transfer_master_list[0])]
            filters += ", Requesting Warehouse: " + warehouse_str
        
        if self.state:
            domain_default = domain_default + [('state', '=', self.state)]
            if self.state == 'draft':
                filters += ", State: Draft" 
            if self.state == 'waiting':
                filters += ", State: Waiting for approval"
            if self.state == 'done':
                filters += ", State: Approved"
        else:
            domain_default = domain_default + [('state', '!=', 'cancelled')]
            
        if self.issuing_warehouse:
            warehouse_search = self.env['stock.warehouse'].sudo().search([('id', '=', int(self.issuing_warehouse))])
            domain_default = domain_default + [('warehouse_master_id.issuing_warehouse_id', '=', int(self.issuing_warehouse))]
            filters += ", Issuing Warehouse :" + (warehouse_search.name and warehouse_search.name or '')
        
        stock_transfer_req_records = stock_transfer_req_obj.sudo().search(domain_default, order="date_requested")
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 4000
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 5000
        sheet1.col(5).width = 5000
        sheet1.col(6).width = 5500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 5500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 9500
        sheet1.col(11).width = 3000
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 4000
        
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        title = report_name +' ( From ' + from_date + ' To ' + to_date + ' )'
        sheet1.write_merge(rc, rc, 0, 14, (self.company_id and self.company_id.name or ' '), Style.title())
        sheet1.write_merge(r1, r1, 0, 14, title, Style.title())
        sheet1.write_merge(r2, r2, 0, 14, filters, Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Request Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Request No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Required Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Creator", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Requestor", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Approved By", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Approved Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 8, "Requesting Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 9, "Issuing Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 10, "Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 11, "UOM", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 12, "Required Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 13, "Approved Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 14, "Status", Style.contentTextBold(r3, 'black', 'white'))
        row = 3
        s_no = 0
        
        for each in stock_transfer_req_records:
            for line in each.request_lines:
                if self.product_ids and line.product_id.id not in product_ids:
                    continue
                s_no += 1
                row += 1
                sheet1.row(row).height = 450
                sheet1.write(row, 0, s_no, Style.normal_left())
                requested_date = ''
                if each.date_requested:
                    requested_date = each.date_requested
                    requested_date = requested_date.strftime('%d-%m-%Y')
                    # requested_date = time.strptime(each.date_requested, "%Y-%m-%d")
                    # requested_date = time.strftime('%d-%m-%Y', requested_date)
                sheet1.write(row, 1, requested_date, Style.normal_left())
                sheet1.write(row, 2, each.name and each.name or '', Style.normal_left())
                required_date = ''
                if each.date_required:
                    required_date = each.date_required
                    required_date = required_date.strftime('%d-%m-%Y')
                    # required_date = time.strptime(each.date_required, "%Y-%m-%d")
                    # required_date = time.strftime('%d-%m-%Y', required_date)
                sheet1.write(row, 3, required_date, Style.normal_left())
                sheet1.write(row, 4, each.user_id and each.user_id.name or '', Style.normal_left())
                sheet1.write(row, 5, each.requester and each.requester or '', Style.normal_left())
                sheet1.write(row, 6, each.approver_user_id and each.approver_user_id.name or '', Style.normal_left())
                approved_date = ''
                if each.date_approved:
                    approved_date = each.date_approved
                    approved_date = approved_date.strftime('%d-%m-%Y')

                    # approved_date = time.strptime(each.date_approved, "%Y-%m-%d")
                    # approved_date = time.strftime('%d-%m-%Y', approved_date)
                sheet1.write(row, 7, approved_date, Style.normal_left())
                sheet1.write(row, 8, each.requesting_warehouse_id and each.requesting_warehouse_id.name or '', Style.normal_left())
                sheet1.write(row, 9, each.warehouse_master_id and each.warehouse_master_id.name or '', Style.normal_left())
                sheet1.write(row, 10, line.product_id and line.product_id.name_get()[0][1] or '', Style.normal_left())
                sheet1.write(row, 11, line.uom_id and line.uom_id.name or '', Style.normal_left())
                sheet1.write(row, 12, line.required_qty and line.required_qty or 0.00, Style.normal_num_right_3digits())
                sheet1.write(row, 13, line.qty and line.qty or 0.00, Style.normal_num_right_3digits())
                form_state = ''
                if each.state == 'draft':
                    form_state = 'Draft'
                if each.state == 'waiting':
                    form_state = 'Waiting for approval'
                if each.state == 'done':
                    form_state = 'Approved'
                sheet1.write(row, 14, form_state, Style.normal_left())
        # stream = StringIO.StringIO()
        # wbk.save(stream)
        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()
        self.write({'name': report_name + '.xls', 'output': base64.encodebytes(binary_data)})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'internal.stock.transfer.request.summary.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
