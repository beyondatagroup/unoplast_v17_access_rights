# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
import xlwt
import cStringIO
import base64
import xlrd
import parser
from lxml import etree

class MaterialIssueDetailedReportWizard(models.TransientModel):
    _name = 'material.issue.detailed.report.wizard'
    _description = 'Material Issue Detailed Report'
    
    date_from = fields.Date(string='From Date(Requested Date)', required=True)
    date_to = fields.Date(string='To Date(Requested Date)', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_material_issue_warehouse', 'material_issue_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_material_issue_product', 'material_issue_wizard_id', 'product_id', string='Product')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('inprogress', 'Issue in Progress'),
        ('done', 'Done')
        ], string='Status')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(MaterialIssueDetailedReportWizard, self).fields_view_get(
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
        
    @api.multi
    def action_print_report(self):
        material_issue_obj = self.env['material.issue']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Material Issue Register Report"
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date) 
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        product_ids = []
        product_list = []
        product_str = ""
        
        domain_default = []
        domain_default = [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        
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
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                domain_default = domain_default + [('warehouse_id', 'in', tuple(warehouse_ids))]
            else:
                domain_default = domain_default + [('warehouse_id', '=', warehouse_ids[0])]
            filters += ", Warehouse: " + warehouse_str
        
        if self.state:
            domain_default = domain_default + [('state', '=', self.state)]
            if self.state == 'draft':
                filters += ", State: Draft" 
            if self.state == 'inprogress':
                filters += ", State: Issue in Progress"
            if self.state == 'done':
                filters += ", State: Done"
        
        material_issue_records = material_issue_obj.sudo().search(domain_default, order="date, name")
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4500
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 5500
        sheet1.col(5).width = 5500
        sheet1.col(6).width = 4500
        sheet1.col(7).width = 4500
        sheet1.col(8).width = 4500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 4500
        sheet1.col(11).width = 9500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 4000
        sheet1.col(15).width = 5000
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500
        sheet1.col(18).width = 3500
        
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        title = report_name +' ( From ' + from_date + ' To ' + to_date + ' )'
        sheet1.write_merge(rc, rc, 0, 18, (self.company_id and self.company_id.name or ' '), Style.title())
        sheet1.write_merge(r1, r1, 0, 18, title, Style.title())
        sheet1.write_merge(r2, r2, 0, 18, filters, Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Issue No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Last Issued Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Requested Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Creator", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Issuer", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Material Requestor", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 8, " Required Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 9, "Approved by", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 10, "Approved Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 11, "Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 12, "UOM", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 13, "Approved Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 14, "Source Location", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 15, "Destination Location", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 16, "Issued Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 17, "Pending Issue Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 18, "Status", Style.contentTextBold(r3, 'black', 'white'))
        row = 3
        s_no = 0
        
        for each in material_issue_records:
            for line in each.issue_lines:
                if self.product_ids and line.product_id.id not in product_ids:
                    continue
                s_no += 1
                row += 1
                sheet1.row(row).height = 450
                sheet1.write(row, 0, s_no, Style.normal_left())
                sheet1.write(row, 1, each.name and each.name or '', Style.normal_left())
                date_issue_last = ''
                if each.date_last_issue: 
                    date_issue_last = time.strptime(each.date_last_issue, "%Y-%m-%d")
                    date_issue_last = time.strftime('%d-%m-%Y', date_issue_last)
                sheet1.write(row, 2, date_issue_last, Style.normal_left())
                date_issue = ''
                if each.date: 
                    date_issue = time.strptime(each.date, "%Y-%m-%d")
                    date_issue = time.strftime('%d-%m-%Y', date_issue)
                sheet1.write(row, 3, date_issue, Style.normal_left())
                sheet1.write(row, 4, each.user_id and each.user_id.name or '', Style.normal_left())
                sheet1.write(row, 5, each.issuer_user_id and each.issuer_user_id.name or '', Style.normal_left())
                sheet1.write(row, 6, each.material_requester and each.material_requester or '', Style.normal_left())
                sheet1.write(row, 7, each.warehouse_id and each.warehouse_id.name  or '', Style.normal_left())
                req_date = ''
                if each.date_required: 
                    req_date = time.strptime(each.date_required, "%Y-%m-%d")
                    req_date = time.strftime('%d-%m-%Y', req_date)
                sheet1.write(row, 8, req_date, Style.normal_left())
                sheet1.write(row, 9, each.approver_user_id and each.approver_user_id.name or '', Style.normal_left())
                approved_date = ""
                if each.date_approved:
                    approved_date = time.strftime(each.date_approved) 
                    approved_date = datetime.strptime(approved_date, '%Y-%m-%d %H:%M:%S').date() 
                    approved_date = datetime.strftime(approved_date, '%d-%m-%Y')
                sheet1.write(row, 10, approved_date, Style.normal_left())
                sheet1.write(row, 11, line.product_id and line.product_id.name or '', Style.normal_left())
                sheet1.write(row, 12, line.uom_id and line.uom_id.name or '', Style.normal_left())
                sheet1.write(row, 13, line.qty and line.qty or 0.00, Style.normal_num_right_3digits())
                sheet1.write(row, 14, line.location_id and line.location_id.name or '', Style.normal_left())
                sheet1.write(row, 15, line.location_dest_id and line.location_dest_id.name or '', Style.normal_left())
                sheet1.write(row, 16, line.issued_qty and line .issued_qty or 0.00, Style.normal_num_right_3digits())
                sheet1.write(row, 17, line.pending_qty and line .pending_qty or 0.00, Style.normal_num_right_3digits())
                state = ''
                if line.state == 'draft':
                    state = 'Draft'
                if line.state == 'partial':
                    state = 'Partially Issued'
                if line.state == 'done':
                    state = 'Done'
                sheet1.write(row, 18, state, Style.normal_left())
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'material.issue.detailed.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
