# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
import json

import xlwt
from odoo.addons.ebits_custom_purchase.wizard.excel_styles import ExcelStyles
import io
import base64

from lxml import etree

class MaterialIssueRegistedReportWizard(models.TransientModel):
    _name = 'material.issue.register.report.wizard'
    _description = 'Material Issue Register Report'
    
    date_from = fields.Date(string='From Date(Issued Date)', required=True)
    date_to = fields.Date(string='To Date(Issued Date)', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_material_issue_register_warehouse', 'material_issue_register_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_material_issue_register_product', 'material_issue_register_wizard_id', 'product_id', string='Product')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(MaterialIssueRegistedReportWizard, self).fields_view_get(
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
    def action_print_report(self):
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Material Issue Report"
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        # from_date = time.strptime(self.date_from, "%Y-%m-%d")
        # from_date = time.strftime('%d-%m-%Y', from_date)
        # to_date = time.strptime(self.date_to, "%Y-%m-%d")
        # to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Issue Date From : "+ str(from_date) + " , To : "+ str(to_date) 
        warehouse_sql = """ """
        product_sql = """ """
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        product_ids = []
        product_list = []
        product_str = ""
        
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
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and mi.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and mi.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        
        issue_sql = """select 
	                        mi.name as issue_no,
	                        to_char(((sm.date at time zone %s)::timestamp::date), 'dd-mm-yyyy') as issue_date,
	                        to_char(mi.date_last_issue, 'dd-mm-yyyy') as last_issued_date,
	                        mr.name as request_no,
	                        to_char(mi.date, 'dd-mm-yyyy') as request_date,
	                        rp_cr.name as creator,
	                        rp_iss.name as issuer,
	                        mi.material_requester as material_requester,
	                        sw.name as warehouse,
	                        to_char(mi.date_required, 'dd-mm-yyyy') as required_date,
	                        rp_ap.name as approved_by,
	                        to_char(mi.date_approved, 'dd-mm-yyyy') as approved_date,
	                        concat( '[' , pp.default_code, '] ', pt.name) as product,
	                        pu.name as uom,
	                        sm.product_uom_qty as quantity,
	                        (case when mi.closed = True then 'Yes' else 'No' end) as force_closed,
	                        (select mil.qty from material_issue_line mil 
			                    where mil.product_id = sm.product_id and mil.issue_id = mi.id) as approved_qty,
	                        (case when sm.state = 'assigned' then 'Available' 
	                             when sm.state = 'confirmed' then 'Waiting Availability' 
	                             when sm.state = 'waiting' then 'waiting Another Move' 
	                             when sm.state = 'done' then 'Done' else sm.state end) as status,
                             (case when mi.state = 'draft' then 'Draft' 
	                             when mi.state = 'inprogress' then 'Issue in Progress' 
	                             when mi.state = 'done' then 'Done' else mi.state end) as issued_status
                        from stock_move sm
	                        left join material_issue mi on (sm.material_issue_id = mi.id)
	                        left join product_product pp on (pp.id = sm.product_id)
	                        left join product_template pt on (pt.id = pp.product_tmpl_id)
	                        left join uom_uom pu on (pu.id = pt.uom_id)
	                        left join stock_warehouse sw on (sw.id = mi.warehouse_id)
	                        left join stock_picking sp on (sp.id = sm.picking_id)
	                        left join res_users ru_cr on (ru_cr.id = mi.user_id)
	                        left join res_partner rp_cr on (rp_cr.id = ru_cr.partner_id)
	                        left join res_users ru_iss on (ru_iss.id = mi.issuer_user_id)
	                        left join res_partner rp_iss on (rp_iss.id = ru_iss.partner_id)
	                        left join res_users ru_ap on (ru_ap.id = mi.approver_user_id)
	                        left join res_partner rp_ap on (rp_ap.id = ru_ap.partner_id)
	                        left join material_request mr on (mr.id = mi.request_id)
                        where (((sm.date at time zone %s)::timestamp::date) between %s and %s) and sm.material_issue_id is not null and sm.state = 'done'"""+ warehouse_sql + product_sql + """ order by sm.date""" 
                        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(issue_sql, (tz, tz, date_from, date_to))
        issue_data = self.env.cr.dictfetchall()
        print("\n\n\n\n................issue_data",issue_data)
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 4500
        sheet1.col(3).width = 5500
        sheet1.col(4).width = 5500
        sheet1.col(5).width = 5500
        sheet1.col(6).width = 4500
        sheet1.col(7).width = 4500
        sheet1.col(8).width = 4500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 4500
        sheet1.col(11).width = 10500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 4000
        sheet1.col(14).width = 4000
        sheet1.col(15).width = 4500
        sheet1.col(16).width = 3500
        
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        title = report_name +' ( From ' + from_date + ' To ' + to_date + ' )'
        sheet1.write_merge(rc, rc, 0, 16, (self.company_id and self.company_id.name or ' '), Style.title())
        sheet1.write_merge(r1, r1, 0, 16, title, Style.title())
        sheet1.write_merge(r2, r2, 0, 16, filters, Style.groupByTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Issue Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Issue No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Request No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Requested Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Creator", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Material Requestor", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Issuer", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 8, "Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 9, "Approved by", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 10, "Approved Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 11, "Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 12, "UOM", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 13, "Approved Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 14, "Issue Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 15, "Status", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 16, "Force Closed", Style.contentTextBold(r3, 'black', 'white'))
        
        row = 3
        s_no = 0
        for each in issue_data:
            s_no += 1
            row += 1
            json_part =  each['product'].split(' ', 1)[1]
            product_data = json.loads(json_part)
            sheet1.row(row).height = 450
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['issue_date'], Style.normal_left())
            sheet1.write(row, 2, each['issue_no'], Style.normal_left())
            sheet1.write(row, 3, each['request_no'], Style.normal_left())
            sheet1.write(row, 4, each['request_date'], Style.normal_left())
            sheet1.write(row, 5, each['creator'], Style.normal_left())
            sheet1.write(row, 6, each['material_requester'], Style.normal_left())
            sheet1.write(row, 7, each['issuer'], Style.normal_left())
            sheet1.write(row, 8, each['warehouse'], Style.normal_left())
            sheet1.write(row, 9, each['approved_by'], Style.normal_left())
            sheet1.write(row, 10, each['approved_date'], Style.normal_left())
            sheet1.write(row, 11, product_data["en_US"], Style.normal_left())
            sheet1.write(row, 12, each['uom']['en_US'], Style.normal_left())
            sheet1.write(row, 13, each['approved_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 14, each['quantity'], Style.normal_num_right_3digits())
            sheet1.write(row, 15, each['status'], Style.normal_left())
            sheet1.write(row, 16, each['force_closed'], Style.normal_left())

        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.encodebytes(binary_data)})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'material.issue.register.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
