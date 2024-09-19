# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
import xlwt
from odoo.addons.ebits_custom_purchase.wizard.excel_styles import ExcelStyles
import io
import base64

from lxml import etree

class MaterialIssueReportWizard(models.TransientModel):
    _name = 'material.issue.report.wizard'
    _description = 'Material Issue Report Wizard'
    
    date_from = fields.Date(string='From Date(Requested Date)', required=True)
    date_to = fields.Date(string='To Date(Requested Date)', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'material_issue_report_warehouse', 'material_issue_report_wizard_id', 'warehouse_id', string='Warehouse')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('material.issue.report.wizard'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('inprogress', 'Issue in Progress'),
        ('done', 'Done')
        ], string='Status')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(MaterialIssueReportWizard, self).fields_view_get(
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
            raise UserError(_('Invalid date range.Try using different values'))
        res = {}
        date_from = self.date_from
        date_to = self.date_to
        warehouse_sql = """ """
        state_sql = """ """
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        filters = "Filtered Based On: Requested Date"
        
        state_dict = {
            'draft': 'Draft',
            'inprogress': 'Issue in Progress',
            'done': 'Done'
            }
        
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
                warehouse_sql += "and mi.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and mi.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        
        if self.state:
            state_sql += " and mil.state = '" + self.state + "'" 
            filters += ", State: " + state_dict[self.state]
        report_name = ""
        report_name = "Material Request & Issue Summary"
        sql = """select
                     req.name as request_no,
                     (case
                        when req.returnable = 'yes' then 'Returnable'
                        else 'Non-Returnable'
                     end) as request_type,
                     mi.date as requested_date,
                     creator.name as creator,
                     mi.material_requester,
                     wh.name as requested_warehouse,
                     department.name as required_to_department,
                     approver.name as approved_by,
                     to_char(((mi.date_approved at time zone %s)::timestamp::date), 'dd-mm-yyyy') as approved_date,
                     template.name as product,
                     mil.qty,
                     uom.name as uom,
                     to_char(mil.date_expected,'dd-mm-yyyy') as required_date,
                     (case when mil.issued_qty is not null then mil.issued_qty else 0.00 end) as issued_qty,
                     ((case when mil.qty is not null then mil.qty else 0.00 end) - (case when mil.issued_qty is not null then mil.issued_qty else 0.00 end)) as pending_qty,
                     case 
                         when mil.state = 'done' then 'Done' 
                         when mil.state = 'partial' then 'Partially Issued'
                         when mil.state = 'draft' then 'Draft' 
                         else mil.state end as state,
                     case
                         when mil.closed = True then 'Yes'
                         else '' end as force_closed
                 from
                     material_issue_line mil
                     left join material_issue mi on (mi.id = mil.issue_id)
                     left join  material_request req on (req.id = mi.request_id)
                     left join res_users users on (users.id = mi.user_id)
                     left join res_partner creator on (creator.id = users.partner_id)
                     left join stock_warehouse wh on (wh.id = mi.warehouse_id)
                     left join hr_department department on (department.id = mi.department_id)
                     left join res_users appusers on (appusers.id = mi.approver_user_id)
                     left join res_partner approver on (approver.id = appusers.partner_id)
                     left join product_product product on (product.id = mil.product_id)
                     left join product_template template on (template.id = product.product_tmpl_id)
                     left join uom_uom uom on (uom.id = mil.uom_id)
                 where
                     mi.date >= %s and mi.date <= %s
    """ + warehouse_sql + state_sql + """
                 group by
                     req.name,
                     req.returnable,
                     mi.date,
                     creator.name,
                     mi.material_requester,
                     wh.name,
                     department.name,
                     approver.name,
                     to_char(((mi.date_approved at time zone %s)::timestamp::date), 'dd-mm-yyyy'),
                     template.name,
                     mil.qty,
                     uom.name,
                     to_char(mil.date_expected,'dd-mm-yyyy'),
                     mil.issued_qty,
                     (mil.qty - mil.issued_qty),
                     mil.state,
                     mil.closed
                 order by
                     mi.date desc,
                     req.name
                     """
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(sql , (tz,date_from, date_to,tz,))
        t = self.env.cr.dictfetchall()
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
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 3500
        sheet1.col(5).width = 3500
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 4500
        sheet1.col(13).width = 3500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        date_from_title = time.strptime(from_date_str, "%Y-%m-%d")
        date_from_title = time.strftime('%d-%m-%Y', date_from_title)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        date_to_title = time.strptime(to_date_str, "%Y-%m-%d")
        date_to_title = time.strftime('%d-%m-%Y', date_to_title)

        # date_from_title = time.strptime(date_from, "%Y-%m-%d")
        # date_from_title = time.strftime('%d-%m-%Y', date_from_title)
        # date_to_title = time.strptime(date_to, "%Y-%m-%d")
        # date_to_title = time.strftime('%d-%m-%Y', date_to_title)
        title = report_name +' ( From ' + date_from_title + ' To ' + date_to_title + ' )'
        sheet1.write_merge(rc, rc, 0, 16, (self.company_id and self.company_id.name or ' '), Style.title())
        sheet1.write_merge(r1, r1, 0, 16, title, Style.title())
        sheet1.write_merge(r2, r2, 0, 16, filters, Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Request No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Request Type", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Requested Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Creator", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Requestor", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Requested warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Approved by ", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 8, "Approved Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 9, "Requested Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 10, "Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 11, "UOM", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 12, "Required Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 13, "Issued Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 14, "Pending Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 15, "Status", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 16, "Force Closed", Style.contentTextBold(r3, 'black', 'white'))
        row = 3
        s_no = 0
        for each in t:
            s_no += 1
            row += 1
            sheet1.row(row).height = 450
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['request_no'], Style.normal_left())
            sheet1.write(row, 2, each['request_type'], Style.normal_left())
            requested_date = each['requested_date']
            requested_date = requested_date.strftime('%d-%m-%Y')
            # requested_date = time.strptime(each['requested_date'], "%Y-%m-%d")
            # requested_date = time.strftime('%d-%m-%Y', requested_date)
            sheet1.write(row, 3, requested_date, Style.normal_left())
            sheet1.write(row, 4, each['creator'], Style.normal_left())
            sheet1.write(row, 5, each['material_requester'], Style.normal_left())
            sheet1.write(row, 6, each['requested_warehouse'], Style.normal_left())
            sheet1.write(row, 7, each['approved_by'], Style.normal_left())
            sheet1.write(row, 8, each['approved_date'], Style.normal_left())
            sheet1.write(row, 9, each['product']['en_US'], Style.normal_left())
            sheet1.write(row, 10, each['qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 11, each['uom']['en_US'], Style.normal_left())
            sheet1.write(row, 12, each['required_date'], Style.normal_left())
            sheet1.write(row, 13, each['issued_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 14, each['pending_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 15, each['state'], Style.normal_left())
            sheet1.write(row, 16, each['force_closed'], Style.normal_left())
        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.encodebytes(binary_data)})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'material.issue.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }

