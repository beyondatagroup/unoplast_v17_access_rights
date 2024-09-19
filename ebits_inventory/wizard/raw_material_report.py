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
from xlwt import *
import base64
from lxml import etree
from odoo.addons.ebits_custom_purchase.wizard.excel_styles import ExcelStyles
import io

class RawMaterialReportWizard(models.TransientModel):
    _name = 'raw.material.report.wizard'
    _description = 'Raw Material Report Wizard'
    
    date_from = fields.Date(string='From Date(Issue Date)', required=True)
    date_to = fields.Date(string='To Date(Issue Date)', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'raw_material_report_warehouse', 'raw_material_report_wizard_id', 'warehouse_id', string='Warehouse')
    location_ids = fields.Many2many('stock.location', 'raw_material_report_location', 'raw_material_report_wizard_id', 'location_id', string='Issued from Location')
    location_dest_ids = fields.Many2many('stock.location', 'raw_material_report_dest_location', 'raw_material_report_wizard_id', 'location_dest_id', string='Issued to Location')
    product_ids = fields.Many2many('product.product', 'raw_material_report_product', 'raw_material_report_wizard_id', 'product_id', string='Product')
    return_product_ids = fields.Many2many('product.product', 'raw_material_report_return_product', 'raw_material_report_wizard_id', 'return_product_id', string='Return Product')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('raw.material.report.wizard'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting'),
        ('partial', 'Partially Returned'),
        ('done', 'Done')
        ], string='Return Product Status')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(RawMaterialReportWizard, self).fields_view_get(
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
        res = {}
        date_from = self.date_from
        date_to = self.date_to
        warehouse_sql = """ """
        product_sql = """ """
        return_product_sql = """ """
        issued_from_loc_sql = """ """
        issued_to_loc_sql = """ """
        state_sql = """ """
        return_product_ids = []
        return_product_list = []
        return_product_str = ""
        product_ids = []
        product_list = []
        product_str = ""
        issued_from_loc_ids = []
        issued_from_loc_list = []
        issued_from_loc_str = ""
        issued_to_loc_ids = []
        issued_to_loc_list = []
        issued_to_loc_str = ""
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        filters = "Filtered Based On: Issue Date"
        rev_filters = "Filtered Based On: Reverse Date"
        
        state_dict = {
            'draft': 'Draft',
            'waiting': 'Waiting',
            'partial': 'Partially Returned',
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
                warehouse_sql += "and wh.id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and wh.id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
            rev_filters += ", Warehouse: " + warehouse_str
       
        if self.location_ids:
            for each_id in self.location_ids:
                issued_from_loc_ids.append(each_id.id)
                issued_from_loc_list.append(each_id.name)
                issued_from_loc_list = list(set(issued_from_loc_list))
                issued_from_loc_str = str(issued_from_loc_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(issued_from_loc_ids) > 1:
                issued_from_loc_sql += " and rmi.location_id in "+ str(tuple(issued_from_loc_ids))
            else:
                issued_from_loc_sql += " and rmi.location_id in ("+ str(issued_from_loc_ids[0]) + ")"
            filters += ", Issued from Location: " + issued_from_loc_str
            rev_filters += ", Reverse from Location: " + issued_from_loc_str

        if self.location_dest_ids:
            for each_id in self.location_dest_ids:
                issued_to_loc_ids.append(each_id.id)
                issued_to_loc_list.append(each_id.name)
                issued_to_loc_list = list(set(issued_to_loc_list))
                issued_to_loc_str = str(issued_to_loc_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(issued_to_loc_ids) > 1:
                issued_to_loc_sql += " and rmi.location_dest_id in "+ str(tuple(issued_to_loc_ids))
            else:
                issued_to_loc_sql += " and rmi.location_dest_id in ("+ str(issued_to_loc_ids[0]) + ")"
            filters += ", Issued to Location: " + issued_to_loc_str
            rev_filters += ", Reverse to Location: " + issued_to_loc_str
        
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.product_tmpl_id.name)
                product_list = list(set(product_list))
                product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(product_ids) > 1:
                product_sql += "and product.id in "+ str(tuple(product_ids))
            else:
                product_sql += "and product.id in ("+ str(product_ids[0]) + ")"
            filters += ", Product: " + product_str
            rev_filters += ", Product: " + product_str
        if self.return_product_ids:
            for each_id in self.return_product_ids:
                return_product_ids.append(each_id.id)
                return_product_list.append(each_id.name)
                return_product_list = list(set(return_product_list))
                return_product_str = str(return_product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(return_product_ids) > 1:
                return_product_sql += " and rmil.product_id in "+ str(tuple(return_product_ids))
            else:
                return_product_sql += " and rmil.product_id in ("+ str(return_product_ids[0]) + ")"
            filters += ", Return Products: " + return_product_str
            rev_filters += ", Reverse Products: " + return_product_str
        if self.state:
            state_sql += " and rmil.state = '" + self.state + "'"
            filters += ", Status: " + state_dict[self.state] 
        report_name = ""
        report_name = "Cloth Orders Register"
        report_name_reverse = "Reverse Cloth Orders Register"
        cloth_issue_sql = """select
                     rmi.date_issue as issue_date,
                     rmi.name as issue_no,
                     rp.name as issued_by,
                     rmi.issued_to,
                     wh.name as issued_warehouse,
                     location.name as issued_from_location,
                     loc.name as issued_to_location,
                     template.name as issue_product,
                     rmi.issued_qty as issue_qty,
                     uom.name as issue_uom,
                     rmi.issued_mtrs as issued_mtrs,
                     rmi.returned_mtrs as returned_mtrs,
                     (case when rmi.issue_type = 'reverse' then rmi.source_doc else '' end) as source_doc,
                     (case 
                         when rmi.state = 'issued' then 'Issued' 
                         when rmi.state = 'done' then 'Done' 
                         when rmi.state = 'inprogress' then 'Return in Progress'
                         when rmi.state = 'draft' then 'Draft' 
                         else rmi.state end) as issue_state,
                     tmpl.name as product,
                     (case
                         when rmil.expected_qty is not null then rmil.expected_qty else 0.00 end) as expected_qty,
                     (case
                         when rmil.expected_mtrs is not null then rmil.expected_mtrs else 0.00 end) as expected_mtrs,
                     line_uom.name as uom,
                     (case
                         when rmil.total_returned_qty is not null then rmil.total_returned_qty else 0.00 end) as actual_received_qty,
                     (case
                         when rmil.total_returned_mtrs is not null then rmil.total_returned_mtrs else 0.00 end) as actual_received_mtrs,
                     
                     ((case
                           when rmil.expected_qty is not null then rmil.expected_qty else 0.00 end)
                      - 
                      (case
                           when rmil.total_returned_qty is not null then rmil.total_returned_qty else 0.00 end)) as pending_qty,
                     ((case
                           when rmil.expected_mtrs is not null then rmil.expected_mtrs else 0.00 end)
                      - 
                      (case
                           when rmil.total_returned_mtrs is not null then rmil.total_returned_mtrs else 0.00 end)) as pending_mtrs,
                     case 
                         when rmil.state = 'waiting' then 'Waiting' 
                         when rmil.state = 'done' then 'Done' 
                         when rmil.state = 'partial' then 'Partially Issued'
                         when rmil.state = 'draft' then 'Draft' 
                         else rmil.state end,
                     case
                         when rmil.closed ='True' then 'Yes'
                         else '' 
                     end as force_closed
                 from
                     raw_material_return_line rmil
                     left join raw_material_issue rmi on (rmi.id = rmil.issue_id)
                     left join res_users users on(users.id = rmi.user_id)
                     left join res_partner rp on (rp.id = users.partner_id)
                     left join stock_warehouse wh on (wh.id = rmi.warehouse_id)
                     left join stock_location location on (location.id = rmi.location_id)
                     left join stock_location loc on (loc.id = rmi.location_dest_id)
                     left join product_product product on (product.id = rmi.product_id)
                     left join product_template template on (template.id = product.product_tmpl_id)
                     left join uom_uom uom on (uom.id = rmi.uom_id)
                     left join product_product line_product on (line_product.id = rmil.product_id)
                     left join product_template tmpl on (tmpl.id = line_product.product_tmpl_id)
                     left join uom_uom line_uom on (line_uom.id = rmil.uom_id)"""
                     
        cloth_issue_cond_sql = """where rmi.date_issue >= %s and rmi.date_issue  <= %s and rmi.issue_type = 'normal' and rmi.state!='draft'""" + issued_from_loc_sql + issued_to_loc_sql + warehouse_sql + product_sql + return_product_sql + state_sql  
        
        cloth_issue_reverse_cond_sql = """where rmi.date_issue >= %s and rmi.date_issue  <= %s and rmi.issue_type = 'reverse' and rmi.state!='draft'""" + issued_from_loc_sql + issued_to_loc_sql + warehouse_sql + product_sql + return_product_sql + state_sql  
        
        cloth_group_sql = """ group by rmi.name, 
                        rmi.date_issue, 
                        rp.name, 
                        rmi.issued_to, 
                        wh.name, 
                        location.name, 
                        loc.name, 
                        template.name, 
                        rmi.issued_qty, 
                        uom.name, 
                        rmi.issued_mtrs, 
                        rmi.returned_mtrs, 
                        rmi.state, 
                        tmpl.name, 
                        rmil.expected_qty, 
                        rmil.expected_mtrs, 
                        line_uom.name, 
                        rmil.total_returned_qty, 
                        rmil.total_returned_mtrs, 
                        rmil.state, 
                        rmil.closed,
                        rmi.source_doc,
                        rmi.issue_type 
                        order by rmi.date_issue desc, rmi.name"""
                     
        sql = cloth_issue_sql + cloth_issue_cond_sql + cloth_group_sql
        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(sql , (date_from, date_to,))
        t = self.env.cr.dictfetchall()
        if len(t) == 0:
            raise UserError(_('No data available.Try using different values'))

        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 4500
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 3500
        sheet1.col(5).width = 3500
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 6500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 6500
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500
        sheet1.col(18).width = 3500
        sheet1.col(19).width = 3500
        sheet1.col(20).width = 3500
        sheet1.col(21).width = 3500
        sheet1.col(22).width = 3500
        sheet1.col(23).width = 3500
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
        sheet1.write_merge(rc, rc, 0, 23, (self.company_id.name), Style.title())
        sheet1.write_merge(r1, r1, 0, 23, title, Style.title())
        sheet1.write_merge(r2, r2, 0, 13, filters, Style.groupByTitle())
        sheet1.write_merge(r2, r2, 14, 23, 'Return Product Details', Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Issue Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Issue No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Issued by", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Issued To", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Issued Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Issued from Location", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Issued to Location", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 8, "Issue Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 9, "Issue Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 10, "Issue UOM", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 11, "Issued Mtrs", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 12, "Returned Mtrs", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 13, "Issue Status", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 14, "Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 15, "Expected Return Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 16, "Expected Return Mtrs", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 17, "UOM", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 18, "Actual Received Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 19, "Actual Received Mtrs", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 20, "Pending Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 21, "Pending Mtrs", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 22, "Status", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 23, "Force Closed", Style.contentTextBold(r3, 'black', 'white'))
        row = 3
        s_no = 0
        issue_name = ""
        summary = OrderedDict()
        for each in t:
            print("\n\n.............each",each)
            row += 1
            sheet1.row(row).height = 450
            if issue_name != each['issue_no']:
                s_no += 1
                sheet1.write(row, 0, s_no, Style.normal_left())
                issue_date = each['issue_date']
                issue_date = issue_date.strftime('%d-%m-%Y')

                # issue_date = time.strptime(each['issue_date'], "%Y-%m-%d")
                # issue_date = time.strftime('%d-%m-%Y', issue_date)
                sheet1.write(row, 1, issue_date, Style.normal_left())
                sheet1.write(row, 2, each['issue_no'], Style.normal_left())
                sheet1.write(row, 3, each['issued_by'], Style.normal_left())
                sheet1.write(row, 4, each['issued_to'], Style.normal_left())
                sheet1.write(row, 5, each['issued_warehouse'], Style.normal_left())
                sheet1.write(row, 6, each['issued_from_location'], Style.normal_left())
                sheet1.write(row, 7, each['issued_to_location'], Style.normal_left())
                sheet1.write(row, 8, each['issue_product']['en_US'], Style.normal_left())
                if each['issue_product']['en_US'] not in summary:
                    summary[each['issue_product']['en_US']] = [0.00, 0.00, 0.00, 0.00]
                sheet1.write(row, 9, each['issue_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 10, each['issue_uom']['en_US'], Style.normal_left())
                sheet1.write(row, 11, each['issued_mtrs'], Style.normal_num_right_3digits())
                summary[each['issue_product']['en_US']][0] += each['issue_qty']
                summary[each['issue_product']['en_US']][1] += each['issued_mtrs']
                
                sheet1.write(row, 12, each['returned_mtrs'], Style.normal_num_right_3digits())
                sheet1.write(row, 13, each['issue_state'], Style.normal_left())
                issue_name = each['issue_no']
            sheet1.write(row, 14, each['product']['en_US'], Style.normal_left())
            if each['product']['en_US'] not in summary:
                    summary[each['product']['en_US']] = [0.00, 0.00, 0.00, 0.00]
            sheet1.write(row, 15, each['expected_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 16, each['expected_mtrs'], Style.normal_num_right_3digits())
            sheet1.write(row, 17, each['uom']['en_US'], Style.normal_left())
            sheet1.write(row, 18, each['actual_received_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 19, each['actual_received_mtrs'], Style.normal_num_right_3digits())
            summary[each['product']['en_US']][0] += each['actual_received_qty']
            summary[each['product']['en_US']][1] += each['actual_received_mtrs']
            sheet1.write(row, 20, each['pending_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 21, each['pending_mtrs'], Style.normal_num_right_3digits())
            sheet1.write(row, 22, each['state'], Style.normal_left())
            sheet1.write(row, 23, each['force_closed'], Style.normal_left())
            
#=====================================Reverse Cloth Issue=================================================

        reverse_sql = cloth_issue_sql + cloth_issue_reverse_cond_sql + cloth_group_sql
        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(reverse_sql , (date_from, date_to,))
        reverse_data = self.env.cr.dictfetchall()
        if len(reverse_data) != 0:
            #raise UserError(_('No data available.Try using different values'))
        
            sheet2 = wbk.add_sheet(report_name_reverse)
            sheet2.set_panes_frozen(True)
            sheet2.set_horz_split_pos(4)
            sheet2.show_grid = False 
            sheet2.col(0).width = 2000
            sheet2.col(1).width = 3500
            sheet2.col(2).width = 3500
            sheet2.col(3).width = 3500
            sheet2.col(4).width = 3500
            sheet2.col(5).width = 3500
            sheet2.col(6).width = 3500
            sheet2.col(7).width = 3500
            sheet2.col(8).width = 6500
            sheet2.col(9).width = 3500
            sheet2.col(10).width = 3500
            sheet2.col(11).width = 3500
            sheet2.col(12).width = 3500
            sheet2.col(13).width = 4500
            sheet2.col(14).width = 4500
            sheet2.col(15).width = 6500
            sheet2.col(16).width = 3500
            sheet2.col(17).width = 3500
            sheet2.col(18).width = 3500
            sheet2.col(19).width = 3500
            sheet2.col(20).width = 3500
            sheet2.col(21).width = 3500
            sheet2.col(22).width = 3500
            sheet2.col(23).width = 3500
            rc = 0
            r1 = 1
            r2 = 2
            r3 = 3
            sheet2.row(rc).height = 700
            sheet2.row(r1).height = 700
            sheet2.row(r2).height = 700
            sheet2.row(r3).height = 256 * 3

            title = report_name_reverse +' ( From ' + date_from_title + ' To ' + date_to_title + ' )'
            sheet2.write_merge(rc, rc, 0, 23, (self.company_id.name), Style.title())
            sheet2.write_merge(r1, r1, 0, 23, title, Style.title())
            sheet2.write_merge(r2, r2, 0, 14, rev_filters, Style.groupByTitle())
            sheet2.write_merge(r2, r2, 15, 23, 'Reverse Product Details', Style.groupByTitle())
            sheet2.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 1, "Reverse Date", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 2, "Reverse No", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 3, "Reverse Created by", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 4, "Reverse From", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 5, "Reverse Warehouse", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 6, "Reverse from Location", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 7, "Reverse to Location", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 8, "Reverse Product", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 9, "Reverse Qty", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 10, "UOM", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 11, "Reverse Mtrs", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 12, "Reverse Mtrs", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 13, "Status", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 14, "Source Document", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 15, "Product", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 16, "Expected Return Qty", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 17, "Expected Return Mtrs", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 18, "UOM", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 19, "Actual Received Qty", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 20, "Actual Received Mtrs", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 21, "Pending Qty", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 22, "Pending Mtrs", Style.contentTextBold(r3, 'black', 'white'))
            sheet2.write(r3, 23, "Status", Style.contentTextBold(r3, 'black', 'white'))
            row = 3
            s_no = 0
            issue_name = ""
            for each_rev in reverse_data:
                row += 1
                sheet2.row(row).height = 450
                if issue_name != each_rev['issue_no']:
                    s_no += 1
                    sheet2.write(row, 0, s_no, Style.normal_left())
                    # rev_issue_date = time.strptime(each_rev['issue_date'], "%Y-%m-%d")
                    # rev_issue_date = time.strftime('%d-%m-%Y', rev_issue_date)
                    rev_issue_date = each_rev['issue_date']
                    rev_issue_date = rev_issue_date.strftime('%d-%m-%Y')

                    sheet2.write(row, 1, rev_issue_date, Style.normal_left())
                    sheet2.write(row, 2, each_rev['issue_no'], Style.normal_left())
                    sheet2.write(row, 3, each_rev['issued_by'], Style.normal_left())
                    sheet2.write(row, 4, each_rev['issued_to'], Style.normal_left())
                    sheet2.write(row, 5, each_rev['issued_warehouse'], Style.normal_left())
                    sheet2.write(row, 6, each_rev['issued_from_location'], Style.normal_left())
                    sheet2.write(row, 7, each_rev['issued_to_location'], Style.normal_left())
                    sheet2.write(row, 8, each_rev['issue_product']['en_US'] , Style.normal_left())
                    sheet2.write(row, 9, each_rev['issue_qty'], Style.normal_num_right_3digits())
                    sheet2.write(row, 10, each_rev['issue_uom']['en_US'] , Style.normal_left())
                    sheet2.write(row, 11, each_rev['issued_mtrs'], Style.normal_num_right_3digits())
                    if each_rev['issue_product']['en_US'] not in summary:
                        summary[each_rev['issue_product']['en_US'] ] = [0.00, 0.00, 0.00, 0.00]
                    summary[each_rev['issue_product']['en_US'] ][2] += each_rev['issue_qty']
                    summary[each_rev['issue_product']['en_US'] ][3] += each_rev['issued_mtrs']
                    sheet2.write(row, 12, each_rev['returned_mtrs'], Style.normal_num_right_3digits())
                    sheet2.write(row, 13, each_rev['issue_state'], Style.normal_left())
                    sheet2.write(row, 14, each_rev['source_doc'], Style.normal_left())
                    issue_name = each_rev['issue_no']
                if each_rev['product']['en_US']  not in summary:
                    summary[each_rev['product']['en_US'] ] = [0.00, 0.00, 0.00, 0.00]
                sheet2.write(row, 15, each_rev['product']['en_US'] , Style.normal_left())
                sheet2.write(row, 16, each_rev['expected_qty'], Style.normal_num_right_3digits())
                sheet2.write(row, 17, each_rev['expected_mtrs'], Style.normal_num_right_3digits())
                sheet2.write(row, 18, each_rev['uom']['en_US'] , Style.normal_left())
                sheet2.write(row, 19, each_rev['actual_received_qty'], Style.normal_num_right_3digits())
                sheet2.write(row, 20, each_rev['actual_received_mtrs'], Style.normal_num_right_3digits())
                summary[each_rev['product']['en_US'] ][2] += each_rev['actual_received_qty']
                summary[each_rev['product']['en_US']][3] += each_rev['actual_received_mtrs']
                sheet2.write(row, 21, each_rev['pending_qty'], Style.normal_num_right_3digits())
                sheet2.write(row, 22, each_rev['pending_mtrs'], Style.normal_num_right_3digits())
                sheet2.write(row, 23, each_rev['state'], Style.normal_left())

#******************************************************Summary***************************************************************************
        sheet3 = wbk.add_sheet('Summary')
        sheet3.set_panes_frozen(True)
        sheet3.set_horz_split_pos(4)
        sheet3.show_grid = False 
        sheet3.col(0).width = 2000
        sheet3.col(1).width = 13500
        sheet3.col(2).width = 4500
        sheet3.col(3).width = 4500
        sheet3.col(4).width = 4500
        sheet3.col(5).width = 4500
        sheet3.col(6).width = 4500
        sheet3.col(7).width = 4500
        
        rc = 0
        r1 = 1
        rh = 2
        r3 = 3
        sheet3.row(rc).height = 700
        sheet3.row(r1).height = 700
        sheet3.row(r3).height = 256 * 3

        title = report_name_reverse +' ( From ' + date_from_title + ' To ' + date_to_title + ' )'
        sheet3.write_merge(rc, rc, 0, 7, (self.company_id.name), Style.title())
        sheet3.write_merge(r1, r1, 0, 7, title, Style.title())
        sheet3.write_merge(rh, rh, 0, 1, '', Style.groupByTitle())
        sheet3.write_merge(rh, rh, 2, 3, 'Built', Style.groupByTitle())
        sheet3.write_merge(rh, rh, 4, 5, 'Unbuilt', Style.groupByTitle())
        sheet3.write_merge(rh, rh, 6, 7, 'Total Built', Style.groupByTitle())
        sheet3.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet3.write(r3, 1, "Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet3.write(r3, 2, "Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet3.write(r3, 3, "Mts", Style.contentTextBold(r3, 'black', 'white'))
        sheet3.write(r3, 4, "Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet3.write(r3, 5, "Mts", Style.contentTextBold(r3, 'black', 'white'))
        sheet3.write(r3, 6, "Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet3.write(r3, 7, "Mts", Style.contentTextBold(r3, 'black', 'white'))
        
        s_no = 0
        row = 3
        for each in summary:
            s_no += 1
            row += 1
            sheet3.write(row, 0, s_no, Style.normal_left())
            sheet3.write(row, 1, each, Style.normal_left())
            sheet3.write(row, 2, summary[each][0], Style.normal_right())
            sheet3.write(row, 3, summary[each][1], Style.normal_right())
            sheet3.write(row, 4, summary[each][2], Style.normal_right())
            sheet3.write(row, 5, summary[each][3], Style.normal_right())
            built_qty = xlwt.Utils.rowcol_to_cell(row, 2)
            built_metres = xlwt.Utils.rowcol_to_cell(row, 3)
            unbuilt_qty = xlwt.Utils.rowcol_to_cell(row, 4)
            unbuilt_metres = xlwt.Utils.rowcol_to_cell(row, 5)
            sheet3.write(row, 6, Formula((str(built_qty) + '-' + str(unbuilt_qty))), Style.normal_right())
            sheet3.write(row, 7, Formula((str(built_metres) + '-' + str(unbuilt_metres))), Style.normal_right())

        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()
        self.write({'name': report_name + '.xls', 'output':base64.encodebytes(binary_data)})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'raw.material.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }

