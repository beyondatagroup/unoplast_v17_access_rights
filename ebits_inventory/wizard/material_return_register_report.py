# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_inventory.wizard.excel_styles import ExcelStyles
import xlwt
import base64
import io
from lxml import etree

class MaterialReturnRegistedReportWizard(models.TransientModel):
    _name = 'material.return.register.report.wizard'
    _description = 'Material Returned Register Report'
    
    date_from = fields.Date(string='From Date(Returned Date)', required=True)
    date_to = fields.Date(string='To Date(Returned Date)', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_material_returned_register_warehouse', 'material_returned_register_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_material_returned_register_product', 'material_returned_register_wizard_id', 'product_id', string='Product')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(MaterialReturnRegistedReportWizard, self).fields_view_get(
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
        report_name = "Material Returned Report"
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Returned Date From : "+ str(from_date) + " , To : "+ str(to_date) 
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
                warehouse_sql += "and mr.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and mr.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        
        material_return_sql = """select 
	                        mr.name as return_no,
	                        to_char(((sm.date at time zone %s)::timestamp::date), 'dd-mm-yyyy') as returned_date,
	                        to_char(mr.date_return, 'dd-mm-yyyy') as last_returned_date,
	                        mre.name as request_no,
	                        mi.name as issue_no,
	                        sw.name as warehouse,
	                        rp_ap.name as accepted_by,
	                        rp_re.name as return_user,
	                        to_char(mr.date_accepted, 'dd-mm-yyyy') as date,
	                        concat( '[' , pp.default_code, '] ', pt.name) as product,
	                        pu.name as uom,
	                        sm.product_uom_qty as quantity,
	                        (case when mr.closed = True then 'Yes' else 'No' end) as force_closed,
	                        (case when sm.state = 'assigned' then 'Available' 
	                             when sm.state = 'confirmed' then 'Waiting Availability' 
	                             when sm.state = 'waiting' then 'waiting Another Move' 
	                             when sm.state = 'done' then 'Done' else sm.state end) as status,
	                        (case when mr.state = 'draft' then 'Draft' 
	                             when mr.state = 'inprogress' then 'Return in Progress' 
	                             when mr.state = 'done' then 'Done' else mr.state end) as return_status
	                        from stock_move sm
	                        left join material_return mr on (mr.id = sm.material_return_id)
	                        left join material_issue mi on (mi.id = mr.issue_id)
	                        left join material_request mre on (mre.id = mi.request_id)
	                        left join product_product pp on (pp.id = sm.product_id)
	                        left join product_template pt on (pt.id = pp.product_tmpl_id)
	                        left join uom_uom pu on (pu.id = pt.uom_id)
	                        left join stock_warehouse sw on (sw.id = mr.warehouse_id)
	                        left join stock_picking sp on (sp.id = sm.picking_id)
	                        left join res_users ru_re on (ru_re.id = mr.user_id)
	                        left join res_partner rp_re on (rp_re.id = ru_re.partner_id)
	                        left join res_users ru_ap on (ru_ap.id = mr.accepted_by)
	                        left join res_partner rp_ap on (rp_ap.id = ru_ap.partner_id)
                        where (((sm.date at time zone %s)::timestamp::date) between %s and %s) and sm.material_return_id is not null and sm.state = 'done'"""+ warehouse_sql + product_sql + """ order by sm.date""" 
                        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(material_return_sql, (tz, tz, date_from, date_to))
        returned_data = self.env.cr.dictfetchall()
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 5500
        sheet1.col(2).width = 4500
        sheet1.col(3).width = 4500
        sheet1.col(4).width = 3500
        sheet1.col(5).width = 5500
        sheet1.col(6).width = 5500
        sheet1.col(7).width = 5500
        sheet1.col(8).width = 10500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 4500
        sheet1.col(11).width = 4500
        sheet1.col(12).width = 3000
        
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        title = report_name +' ( From ' + from_date + ' To ' + to_date + ' )'
        sheet1.write_merge(rc, rc, 0, 12, (self.company_id and self.company_id.name or ' '), Style.title())
        sheet1.write_merge(r1, r1, 0, 12, title, Style.title())
        sheet1.write_merge(r2, r2, 0, 12, filters, Style.groupByTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Returned Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Return No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Request No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Issue No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Return User", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Warehouse", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Accepted by ", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 8, "Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 9, "UOM", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 10, "Returned Quantity", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 11, "Status", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 12, "Force Closed", Style.contentTextBold(r3, 'black', 'white'))
        
        row = 3
        s_no = 0
        for each in returned_data:
            s_no += 1
            row += 1
            sheet1.row(row).height = 450
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['returned_date'], Style.normal_left())
            sheet1.write(row, 2, each['return_no'], Style.normal_left())
            sheet1.write(row, 3, each['request_no'], Style.normal_left())
            sheet1.write(row, 4, each['issue_no'], Style.normal_left())
            sheet1.write(row, 5, each['return_user'], Style.normal_left())
            sheet1.write(row, 6, each['warehouse'], Style.normal_left())
            sheet1.write(row, 7, each['accepted_by'], Style.normal_left())
            sheet1.write(row, 8, each['product'], Style.normal_left())
            sheet1.write(row, 9, each['uom']['en_US'], Style.normal_left())
            sheet1.write(row, 10, each['quantity'], Style.normal_num_right_3digits())
            sheet1.write(row, 11, each['status'], Style.normal_left())
            sheet1.write(row, 12, each['force_closed'], Style.normal_left())
                
        stream = io.BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.encodebytes(stream.getvalue())})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'material.return.register.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
