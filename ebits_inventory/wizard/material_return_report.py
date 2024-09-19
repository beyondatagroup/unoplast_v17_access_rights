# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
import xlwt
import cStringIO
import base64
import xlrd
import parser
from lxml import etree

class MaterialReturnReportWizard(models.TransientModel):
    _name = 'material.return.report.wizard'
    _description = 'Material Return Report Wizard'
    
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'material_return_report_warehouse', 'material_return_report_wizard_id', 'warehouse_id', string='Warehouse')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('inprogress', 'Issue in Progress'),
        ('done', 'Done')
        ], string='Product Status')
    return_state = fields.Selection([
        ('draft', 'Draft'),
        ('inprogress', 'Issue in Progress'),
        ('done', 'Done')
        ], string='Form Status')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(MaterialReturnReportWizard, self).fields_view_get(
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
    def action_report(self):
        if self.date_from > self.date_to:
            raise UserError(_('Invalid date range.Try using different values'))
        res = {}
        date_from = self.date_from
        date_to = self.date_to
        warehouse_sql = """ """
        state_sql = """ """
        return_state_sql = """ """
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        filters = "Filtered Based On: Date"
        
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
                warehouse_sql += "and mr.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and mr.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += " | Warehouse: " + warehouse_str
       
        if self.state:
            state_sql += " and line.state = '" + self.state + "'" 
            if self.state == 'draft':
                filters += ", State: Draft"
            elif self.state == 'inprogress':
                filters += ", State: Return in progress"
            elif self.state == 'done':
                filters += " | State: Done"
        if self.return_state:
            return_state_sql += " and mr.state = '" + self.return_state + "'" 
            if self.return_state == 'draft':
                filters += ", Return State: Draft"
            elif self.return_state == 'inprogress':
                filters += ", Return State: Return in progress"
            elif self.return_state == 'done':
                filters += " | Return State: Done"
        report_name = ""
        report_name = "Material Return Register"
        sql = """select
                     mr.name as return_no,
                     request.name as request_no,
                     issue.name as issue_no,
                     wh.name as warehouse,
                     location.name as source_location,
                     location_dest.name as destination_location,
                     acptd.name as accepted_by,
                     to_char(mr.date_accepted, 'dd-mm-yyyy') as date,
                     to_char(mr.date_return, 'dd-mm-yyyy') as returned_date,
                     template.name as product,
                     uom.name as uom,
                     (case
                          when line.qty is not null then line.qty else 0.00
                      end) as returnable_qty,
                     (case
                          when line.returned_qty is not null then line.returned_qty else 0.00
                      end) as returned_qty,
                     ((case
                          when line.qty is not null then line.qty else 0.00
                      end) -
                     (case
                          when line.returned_qty is not null then line.returned_qty else 0.00
                      end)) as pending_return_qty,
                     (case
                          when line.state = 'draft' then 'Draft'
                          when line.state = 'inprogress' then 'Return in progress'
                          when line.state = 'done' then 'Done'
                          else line.state
                      end) as state,
                     (case
                          when mr.state = 'draft' then 'Draft'
                          when mr.state = 'inprogress' then 'Return in progress'
                          when mr.state = 'done' then 'Done'
                          else mr.state
                      end) as return_state,
                     (case 
                          when mr.closed = True then 'Yes'
                          else ' '
                      end) as force_closed
                 from
                     material_return_line line
                     left join material_return mr on (mr.id = line.return_id)
                     left join material_issue issue on (issue.id = mr.issue_id)
                     left join material_request request on (request.id = issue.request_id)
                     left join stock_warehouse wh on (wh.id = mr.warehouse_id)
                     left join stock_location location on (location.id = line.location_id)
                     left join stock_location location_dest on (location_dest.id = line.location_dest_id)
                     left join res_users users on (users.id = mr.accepted_by)
                     left join res_partner acptd on (acptd.id = users.partner_id)
                     left join product_product product on (product.id = line.product_id)
                     left join product_template template on (template.id = product.product_tmpl_id)
                     left join product_uom uom on (uom.id = line.uom_id)
                 where
                     mr.date_accepted >= %s and mr.date_accepted <= %s
    """ + warehouse_sql + state_sql + return_state_sql + """
                 group by
                     mr.name,
                     request.name,
                     issue.name,
                     wh.name,
                     location.name,
                     location_dest.name,
                     acptd.name,
                     to_char(mr.date_accepted, 'dd-mm-yyyy'),
                     to_char(mr.date_return, 'dd-mm-yyyy'),
                     template.name,
                     uom.name,
                     returnable_qty,
                     returned_qty,
                     pending_return_qty,
                     line.state,
                     mr.state,
                     mr.closed
                 order by
                     to_char(mr.date_accepted, 'dd-mm-yyyy') desc,
                     mr.name desc
                     """
        self.env.cr.execute(sql , (date_from, date_to,))
        t = self.env.cr.dictfetchall()
        if len(t) == 0:
            raise UserError(_('No data available.Try using different values'))

        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
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
        sheet1.col(17).width = 2000

        r1 = 0
        r2 = 1
        r3 = 2
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        date_from_title = time.strptime(date_from, "%Y-%m-%d")
        date_from_title = time.strftime('%d-%m-%Y', date_from_title)
        date_to_title = time.strptime(date_to, "%Y-%m-%d")
        date_to_title = time.strftime('%d-%m-%Y', date_to_title)
        title = report_name +' ( From ' + date_from_title + ' To ' + date_to_title + ' )'
        sheet1.write_merge(r1, r1, 0, 17, title, Style.title())
        sheet1.write_merge(r2, r2, 0, 17, filters, Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Return No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Request No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Issue No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Source Location", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Destination Location", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Accepted by ", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 8, "Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 9, "Last Returned Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 10, "Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 11, "UOM", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 12, "Returnable Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 13, "Returned Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 14, "Pending Return Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 15, "Product Status", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 16, "Form Status", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 17, "Force Closed", Style.contentTextBold(r3, 'black', 'white'))
        row = 2
        s_no = 0
        for each in t:
            s_no += 1
            row += 1
            sheet1.row(row).height = 450
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['return_no'], Style.normal_left())
            sheet1.write(row, 2, each['request_no'], Style.normal_left())
            sheet1.write(row, 3, each['issue_no'], Style.normal_left())
            sheet1.write(row, 4, each['warehouse'], Style.normal_left())
            sheet1.write(row, 5, each['source_location'], Style.normal_left())
            sheet1.write(row, 6, each['destination_location'], Style.normal_left())
            sheet1.write(row, 7, each['accepted_by'], Style.normal_left())
            sheet1.write(row, 8, each['date'], Style.normal_left())
            sheet1.write(row, 9, each['returned_date'], Style.normal_left())
            sheet1.write(row, 10, each['product'], Style.normal_right())
            sheet1.write(row, 11, each['uom'], Style.normal_left())
            sheet1.write(row, 12, each['returnable_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 13, each['returned_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 14, each['pending_return_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 15, each['state'], Style.normal_left())
            sheet1.write(row, 16, each['return_state'], Style.normal_left())
            sheet1.write(row, 17, each['force_closed'], Style.normal_left())
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'material.return.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }

