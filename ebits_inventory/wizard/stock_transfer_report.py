# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_inventory.wizard.excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
import xlwt
import base64
import io
from lxml import etree

class InternalStockTransferReportWizard(models.TransientModel):
    _name = 'internal.stock.transfer.report.wizard'
    _description = 'Internal Stock Transfer Report Wizard'
    
    date_from = fields.Date(string='From Date(Request Date)', required=True)
    date_to = fields.Date(string='To Date(Request Date)', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'internal_stock_transfer_report_warehouse', 'internal_stock_transfer_report_wizard_id', 'warehouse_id', string='Issuing Warehouse')
    requesting_warehouse_ids = fields.Many2many('stock.warehouse', 'internal_stock_transfer_report_requesting_warehouse', 'internal_stock_transfer_report_wizard_id', 'warehouse_id', string='Requesting Warehouse')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('internal.stock.transfer.report.wizard'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting For Approval'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
        ], string='Request Status')
    issue_state = fields.Selection([
        ('draft', 'Draft'),
        ('partial', 'Partially Issued'),
        ('done', 'Done'),
        ], string='Product Issue Status')
    receipt_state = fields.Selection([
        ('draft', 'Draft'),
        ('partial', 'Partially Received'),
        ('done', 'Done'),
        ], string='Product Receipt Status')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(InternalStockTransferReportWizard, self).fields_view_get(
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
        
    # @api.multi
    def action_report(self):
        if self.date_from > self.date_to:
            raise UserError(_('Invalid date range.Try  Using Different Values'))
        transfer_master_obj = self.env['internal.stock.transfer.master']
        transfer_request_obj = self.env['internal.stock.transfer.request']
        res = {}
        date_from = self.date_from
        date_to = self.date_to
        warehouse_sql = """ """
        requesting_warehouse_sql = """ """
        department_sql = """ """
        state_sql = """ """
        location_sql = """ """
        issue_state_sql = """ """
        receipt_state_sql = """ """
        department_ids = []
        department_list = []
        department_str = ""
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        requesting_warehouse_ids = []
        requesting_warehouse_list = []
        requesting_warehouse_str = ""
        location_ids = []
        location_list = []
        location_str = ""
        filters = "Filtered Based On : Requested Date"
        
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
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += " and rmaster.issuing_warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += " and rmaster.issuing_warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += " | Issuing Warehouse : " + warehouse_str
            
        if self.requesting_warehouse_ids:
            transfer_master_list = []
            for each_id in self.requesting_warehouse_ids:
                requesting_warehouse_ids.append(each_id.id)
                print('>>>>>>>>requesting_warehouse_ids>>>>>>>>>>>>>>>>>',requesting_warehouse_ids)
                requesting_warehouse_list.append(each_id.name)
                requesting_warehouse_list = list(set(requesting_warehouse_list))
                requesting_warehouse_str = str(requesting_warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            transfer_search = transfer_master_obj.search([('requesting_warehouse_id', 'in', requesting_warehouse_ids)])
            print('\n\n\ntransfer_search---------------',transfer_search)
            if not transfer_search:
                 raise UserError(_('This warehouse has not yet made any request.'))
            else:
                for each_transfer in transfer_search:
                     transfer_master_list.append(each_transfer.issuing_warehouse_id.id)
                     transfer_master_list = list(set(transfer_master_list))
                if len(requesting_warehouse_ids) > 1:
                    requesting_warehouse_sql += " and rmaster.requesting_warehouse_id in "+ str(tuple(requesting_warehouse_ids))
                else:
                    requesting_warehouse_sql += " and rmaster.requesting_warehouse_id = "+ str(requesting_warehouse_ids[0])
                if len(transfer_master_list) > 1:
                    requesting_warehouse_sql += " and rmaster.issuing_warehouse_id in "+ str(tuple(transfer_master_list))
                else:
                    requesting_warehouse_sql += " and rmaster.issuing_warehouse_id = "+ str(transfer_master_list[0])
                filters += " | Requesting Warehouse : " + requesting_warehouse_str
        
        if self.state:
            state_sql += " and line.state = '" + self.state + "'" 
            if self.state == 'draft':
                filters += "| Product Request Status : Draft"
            if self.state == 'waiting':
                filters += "| Product Request Status : Waiting for approval"
            if self.state == 'done':
                filters += "| Product Request Status : Done"
            if self.state == 'cancelled':
                filters += "| Product Request Status : Cancelled"
        if self.issue_state:
            issue_state_sql += " and issue_line.state = '" + self.issue_state + "'" 
            if self.issue_state == 'draft':
                filters += " | Product Issue Status : Draft"
            if self.issue_state == 'partial':
                filters += " | Product Issue Status : Partially Issued"
            if self.issue_state == 'done':
                filters += " | Product Issue Status : Done"
        if self.receipt_state:
            if self.receipt_state == 'draft':
                receipt_state_sql += " and ((line.received_qty = 0.00 or line.received_qty is null) and issue_line.state in('partial', 'done'))"
                filters += " | Product Receipt Status : Draft"
            if self.receipt_state == 'partial':
                receipt_state_sql += " and (line.received_qty > 0.00 and (line.received_qty < line.qty))"
                filters += " | Product Receipt Status : Partially Received"
            if self.receipt_state == 'done':
                receipt_state_sql += " and (line.received_qty = line.qty)"
                filters += " | Product Receipt Status : Done"
        report_name = ""
        report_name = "Stock Transfer Register"
        sql = """select
                    req.name as request_no,
                    to_char(req.date_requested, 'dd-mm-yyyy') as requested_date,
                    creator.name as creator,
                    req.requester,
                    rwh.name as requesting_warehouse,
                    iwh.name as issuing_warehouse,
                    rloc.name as requesting_location,
                    iloc.name as issuing_location,
                    appr.name as approver,
                    to_char(req.date_approved, 'dd-mm-yyyy') as approved_date,
                    pro.id as requested_product,
                    line.required_qty as requested_qty,
                    line.qty as approved_qty,
                    uom.name as uom,
                    to_char(req.date_required, 'dd-mm-yyyy') as required_date,
                    line.issued_qty as issued_qty,
                    line.pending_issue_qty as pending_issue_qty,
                    line.received_qty as received_qty,
                    line.pending_receipt_qty as pending_receipt_qty,
                    (case
                        when line.state = 'draft' then 'Draft'
                        when line.state = 'waiting' then 'Waiting for approval'
                        when line.state = 'done' then 'Done'
                        when line.state = 'cancelled' then 'Cancelled'
                    else
                        line.state
                    end) as request_state,
                    (case
                        when issue_line.state = 'draft' then 'Draft'
                        when issue_line.state = 'partial' then 'Partially Issued'
                        when issue_line.state = 'done' then 'Done'
                    else
                        issue_line.state
                    end) as issue_state,
                    (case
                        when ((line.received_qty = 0.00 or line.received_qty is null) and issue_line.state in('partial', 'done')) then 'Draft'
                        when (line.received_qty = line.qty) then 'Done'
                        when (line.received_qty > 0.00 and (line.received_qty < line.qty)) then 'Partially Received'
                    else
                        ' '
                    end) as receipt_state
                from internal_stock_transfer_request_lines line
                    left join internal_stock_transfer_request req on (req.id = line.request_id)
                    left join res_users users on (users.id = req.user_id)
                    left join res_partner creator on (creator.id = users.partner_id)
                    left join internal_stock_transfer_master rmaster on (rmaster.id = req.warehouse_master_id)
                    left join stock_warehouse rwh on (rwh.id = rmaster.requesting_warehouse_id)
                    left join stock_warehouse iwh on (iwh.id = rmaster.issuing_warehouse_id)
                    left join stock_location rloc on (rloc.id = req.required_location_id)
                    left join stock_picking_type type on (type.id = iwh.int_type_id)
                    left join stock_location iloc on (iloc.id = type.default_location_dest_id)
                    left join res_users appruser on (appruser.id = req.approver_user_id)
                    left join res_partner appr on (appr.id = appruser.partner_id)
                    left join product_product pro on (pro.id = line.product_id)
                    left join product_template product on(product.id = pro.id)
                    left join uom_uom uom on (uom.id = line.uom_id)
                    left join internal_stock_transfer_issue issue on (issue.request_id = req.id)
                    left join internal_stock_transfer_issue_line issue_line on (issue_line.issue_id = issue.id)
                where
                    req.date_requested >= %s and req.date_requested <= %s
    """ + warehouse_sql + requesting_warehouse_sql + department_sql + issue_state_sql + state_sql + location_sql + receipt_state_sql + """
                group by
                    req.name,
                    to_char(req.date_requested, 'dd-mm-yyyy'),
                    creator.name,
                    req.requester,
                    rwh.name,
                    iwh.name,
                    rloc.name,
                    iloc.name,
                    appr.name,
                    to_char(req.date_approved, 'dd-mm-yyyy'),
                    pro.id,
                    line.required_qty,
                    line.qty,
                    uom.name,
                    to_char(req.date_required, 'dd-mm-yyyy'),
                    line.issued_qty,
                    line.pending_issue_qty,
                    line.received_qty,
                    line.pending_receipt_qty,
                    request_state,
                    issue_state,
                    receipt_state
                order by
                    to_char(req.date_requested, 'dd-mm-yyyy') desc,
                    req.name desc
                     """
        self.env.cr.execute(sql , (date_from, date_to,))
        t = self.env.cr.dictfetchall()
        product_ids = [line['requested_product'] for line in t]
        product_names = {product.id: product.name for product in
                         self.env['product.product'].sudo().browse(product_ids)}
        print('>>>>>>>>>product_names>>>>>>>>>>>>.',product_names)
        if len(t) == 0:
            raise UserError(_('No data available.Try using different values'))

        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 5500
        sheet1.col(4).width = 3500
        sheet1.col(5).width = 6500
        sheet1.col(6).width = 6500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 5500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 7500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500
        sheet1.col(18).width = 3500
        sheet1.col(19).width = 3500
        sheet1.col(20).width = 4500
        sheet1.col(21).width = 4500
        sheet1.col(22).width = 4500

        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        date_from_title_str = date_from.strftime('%Y-%m-%d')
        date_from_title = time.strptime(date_from_title_str, "%Y-%m-%d")
        date_from_title = time.strftime('%d-%m-%Y', date_from_title)

        date_to_title_str = date_to.strftime('%Y-%m-%d')
        date_to_title = time.strptime(date_to_title_str, "%Y-%m-%d")
        date_to_title = time.strftime('%d-%m-%Y', date_to_title)
        title = report_name +' ( From ' + date_from_title + ' To ' + date_to_title + ' )'
        sheet1.write_merge(rc, rc, 0, 22, (self.company_id.name), Style.title())
        sheet1.write_merge(r1, r1, 0, 22, title, Style.title())
        sheet1.write_merge(r2, r2, 0, 22, filters, Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Requested Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Request No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Creator", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Requestor", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Requesting Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Issuing Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Source Location", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 8, "Destination Location", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 9, "Approved by ", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 10, "Approved Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 11, "Requested Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 12, "Requested Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 13, "Approved Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 14, "UOM", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 15, "Required Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 16, "Issued Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 17, "Pending Issue Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 18, "Received Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 19, "Pending Receipt Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 20, "Product Request Status", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 21, "Product Issue Status", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 22, "Product Receipt Status", Style.contentTextBold(r3, 'black', 'white'))
        row = 3
        s_no = 0
        for each in t:
            product_id = each['requested_product']
            if product_id in product_names:
                each['requested_product'] = product_names[product_id]
            s_no += 1
            row += 1
            sheet1.row(row).height = 450
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['requested_date'], Style.normal_left())
            sheet1.write(row, 2, each['request_no'], Style.normal_left())
            sheet1.write(row, 3, each['creator'], Style.normal_left())
            sheet1.write(row, 4, each['requester'], Style.normal_left())
            sheet1.write(row, 5, each['requesting_warehouse'], Style.normal_left())
            sheet1.write(row, 6, each['issuing_warehouse'], Style.normal_left())
            sheet1.write(row, 7, each['issuing_location'], Style.normal_left())
            sheet1.write(row, 8, each['requesting_location'], Style.normal_left())
            sheet1.write(row, 9, each['approver'], Style.normal_left())
            sheet1.write(row, 10, each['approved_date'], Style.normal_left())
            sheet1.write(row, 11, each['requested_product'], Style.normal_left())
            sheet1.write(row, 12, each['requested_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 13, each['approved_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 14, each['uom']['en_US'], Style.normal_left())
            sheet1.write(row, 15, each['required_date'], Style.normal_left())
            sheet1.write(row, 16, each['issued_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 17, each['pending_issue_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 18, each['received_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 19, each['pending_receipt_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 20, each['request_state'], Style.normal_left())
            sheet1.write(row, 21, each['issue_state'], Style.normal_left())
            sheet1.write(row, 22, each['receipt_state'], Style.normal_left())
        stream = io.BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.encodebytes(stream.getvalue())})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'internal.stock.transfer.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }

