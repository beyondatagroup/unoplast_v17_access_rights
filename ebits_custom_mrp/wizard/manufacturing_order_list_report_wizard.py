# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_mrp.wizard.excel_styles import ExcelStyles
import xlwt
from io import BytesIO
import base64
from lxml import etree
import json



class ManufacturingOrderListReportWizard(models.TransientModel):
    _name = 'manufacturing.order.list.report.wizard'
    _description = 'Manufacturing Order List Report Wizard'
    
    date_from= fields.Date(string='From Date', required=True)
    date_to= fields.Date(string='To Date', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_manuf_order_list_warehouse', 'manuf_order_list_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_manuf_order_list_product', 'manuf_order_list_wizard_id', 'product_id', string='Product')
    categ_ids = fields.Many2many('product.category', 'etc_manuf_order_list_category', 'manuf_order_list_wizard_id', 'categ_id', string='Product Category')
    summary = fields.Boolean(string='Product Category Summary')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    state = fields.Selection([
        ('progress', 'In Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')], string='State')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(ManufacturingOrderListReportWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='warehouse_ids']"):
                warehouse_id = []
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                if warehouse_id:
                    node.set('domain', "[('id', 'in', " + str(warehouse_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res
    
    # @api.multi
    def action_report(self):
        production_obj = self.env['mrp.production']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Manufacturing Orders List"
        summary_report_name = "Manufacturing Orders List Summary Report"
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date) 
        
        product_sql = """ """
        warehouse_sql = """ """
        state_sql = """ """
        category_sql = """ """
        
        all_warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        all_categ_ids = []
        categ_list = []
        categ_str = ""
        
        all_product_ids = []
        product_list = []
        product_str = ""
        
        domain_default = []
        domain_default = [('date_start', '>=',  self.date_from), ('date_start', '<=',  self.date_to)]
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                all_warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_warehouse_ids) > 1:
                domain_default = domain_default + [('warehouse_id', 'in', tuple(all_warehouse_ids))]
                warehouse_sql += " and mp.warehouse_id in "+ str(tuple(all_warehouse_ids))
                filters += ", Warehouse : "+ warehouse_str
            else:
                domain_default = domain_default + [('warehouse_id', '=', all_warehouse_ids[0])]
                warehouse_sql += " and mp.warehouse_id in ("+ str(all_warehouse_ids[0]) + ")"
                filters += ", Warehouse : "+ warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    all_warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(all_warehouse_ids) > 1:
                    domain_default = domain_default + [('warehouse_id', 'in', tuple(all_warehouse_ids))]
                    warehouse_sql += " and mp.warehouse_id in "+ str(tuple(all_warehouse_ids))
                    filters += ", Warehouse : "+ warehouse_str
                else:
                    domain_default = domain_default + [('warehouse_id', '=', all_warehouse_ids[0])]
                    warehouse_sql += " and mp.warehouse_id in ("+ str(all_warehouse_ids[0]) + ")"
                    filters += ", Warehouse : "+ warehouse_str
        if self.product_ids:
            for each_id in self.product_ids:
                all_product_ids.append(each_id.id)
                product_list.append(each_id.name)
                product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_product_ids) > 1:
                domain_default = domain_default + [('product_id', 'in', tuple(all_product_ids))]
                product_sql += " and mp.product_id in "+ str(tuple(all_product_ids))
                filters += ", product : "+ product_str
            else:
                domain_default = domain_default + [('product_id', '=', all_product_ids[0])]
                product_sql += " and mp.product_id in ("+ str(all_product_ids[0]) + ")"
                filters += ", product : "+ product_str
        if self.categ_ids:
            for each_id in self.categ_ids:
                all_categ_ids.append(each_id.id)
                categ_list.append(each_id.name)
                categ_str = str(categ_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_categ_ids) > 1:
                domain_default = domain_default + [('product_id.categ_id', 'in', tuple(all_categ_ids))]
                category_sql += " and pt.categ_id in "+ str(tuple(all_categ_ids))
                filters += ", product Category : "+ categ_str
            else:
                domain_default = domain_default + [('product_id.categ_id', '=', all_categ_ids[0])]
                category_sql += " and pt.categ_id in ("+ str(all_categ_ids[0]) + ")"
                filters += ", product Category : "+ categ_str
        if self.state:
            if self.state == 'progress':
                domain_default = domain_default + [('state', 'in', ('confirmed', 'planned', 'progress'))]
            else:
                domain_default = domain_default + [('state', '=', self.state)]
            state_sql = " and mp.state = " + "'" + str(self.state) + "'"
            if self.state == 'progress':
                filters += ", State : In Progress"
            if self.state == 'done':
                filters += ", State : Done"
            if self.state == 'cancel':
                filters += ", State : Cancelled"
        else:
            domain_default = domain_default + [('state', '!=', 'cancel')]
            state_sql = " and mp.state != 'cancel' "
        production_records = production_obj.sudo().search(domain_default, order="name, date_start asc")

        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4000
        sheet1.col(2).width = 4000
        sheet1.col(3).width = 7000
        sheet1.col(4).width = 9000
        sheet1.col(5).width = 7500
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 5000
        sheet1.col(8).width = 7000
        sheet1.col(9).width = 5500
        sheet1.col(10).width = 3500
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 380
        sheet1.row(r4).height = 256 * 3
        title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
        title1 = self.company_id.name
        title2 = filters 
        sheet1.write_merge(r1, r1, 0, 10, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 10, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 10, title2, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Reference", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Planned Start Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Warehouse/Branch", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Quantity to Produce", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Raw Material Availability", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Source", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Status", Style.contentTextBold(r2,'black','white'))

        row = r4
        s_no = 0

        for each in production_records:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 300
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, (each.name and each.name or ""), Style.normal_left())
            update_date = ""
            if each.date_start:
                date_start_str = each.date_start.strftime('%Y-%m-%d')
                date_start = time.strptime(date_start_str, '%Y-%m-%d')
                update_date = time.strftime('%d-%m-%Y', date_start)

            sheet1.write(row, 2, update_date, Style.normal_left())
            sheet1.write(row, 3, (each.product_id.categ_id and each.product_id.categ_id.name or ""), Style.normal_left())
            sheet1.write(row, 4, (each.product_id and each.product_id.display_name or ""), Style.normal_left())
            sheet1.write(row, 5, (each.warehouse_id and each.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(row, 6, (each.product_qty and each.product_qty or 0.00), Style.normal_num_left())
            sheet1.write(row, 7, (each.product_id.uom_id and each.product_id.uom_id.name or ""), Style.normal_left())
            availability = ""
            if each.availability == 'assigned':
                availability = "Available"
            if each.availability == 'partially_available':
                availability = "Partially Available"
            if each.availability == 'waiting':
                availability = "Waiting"
            if each.availability == 'none':
                availability = "None"
            sheet1.write(row, 8, availability, Style.normal_left())
            sheet1.write(row, 9, (each.origin and each.origin or ""), Style.normal_left())
            state = ""
            if each.state in ['confirmed', 'planned', 'progress']:
                state = "In Progress"
            if each.state == 'done':
                state = "Done"
            if each.state == 'cancel':
                state = "Cancelled"
            sheet1.write(row, 10, state, Style.normal_left())

        if self.date_from and self.date_to and self.summary:   
            manuf_order_list_sql = """ select 
	                                    pc.name as category,
	                                    mp.name as reference,
	                                    to_char(((mp.date_start at time zone %s)::timestamp::date), 'dd-mm-yyyy') as start_date,
	                                    concat( '[' , pt.default_code, '] ', pt.name) as product,
	                                    sw.name as warehouse,
	                                    mp.product_qty as quantity,
	                                    pu.name as uom,
	                                    mp.origin as source,
	                                    (case when mp.availability = 'assigned' then 'Available'
		                                    when mp.availability = 'partially_available' then 'Partially Available'
		                                    when mp.availability = 'waiting' then 'Waiting'
		                                    when mp.availability = 'none' then 'None' else mp.availability end) as availability,
	                                    
	                                    (case when mp.state in ('confirmed','planned','progress') then 'In Progress'
		                                    when mp.state = 'done' then 'Done'
		                                    when mp.state = 'cancel' then 'Cancelled' else mp.state end) as status 
                                    from mrp_production mp
	                                    left join product_product pp on (pp.id = mp.product_id)
	                                    left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                    left join product_category pc on (pc.id = pt.categ_id)
	                                    left join uom_uom pu on (pu.id = pt.uom_id)
	                                    left join stock_warehouse sw on (sw.id = mp.warehouse_id)
	                               where 
                                        (((mp.date_start at time zone %s)::timestamp::date) between %s and %s) """ + product_sql + warehouse_sql + category_sql + state_sql + """ 
                                    order by 
                                        pc.name, 
                                        pt.default_code, pt.name, 
                                        mp.name, 
                                        mp.date_start"""
            
            tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
            self.env.cr.execute(manuf_order_list_sql , (tz, tz, date_from, date_to,))
            manuf_order_list_data = self.env.cr.dictfetchall()

            sheet2 = wbk.add_sheet(summary_report_name)
            sheet1.set_panes_frozen(True)
            sheet1.set_horz_split_pos(4)
            sheet2.show_grid = False 
            sheet2.col(0).width = 2000
            sheet2.col(1).width = 7000
            sheet2.col(2).width = 9000
            sheet2.col(3).width = 4000
            sheet2.col(4).width = 4000
            sheet2.col(5).width = 7500
            sheet2.col(6).width = 3500
            sheet2.col(7).width = 5000
            sheet2.col(8).width = 7000
            sheet2.col(9).width = 5500
            sheet2.col(10).width = 3500
        
            r1 = 0
            r2 = 1
            r3 = 2
            r4 = 3
            
            sheet2.row(r1).height = 500
            sheet2.row(r2).height = 400
            sheet2.row(r3).height = 380
            sheet2.row(r4).height = 256 * 3
            title = summary_report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
            title1 = self.company_id.name
            title2 = filters 
            sheet2.write_merge(r1, r1, 0, 10, title1, Style.main_title())
            sheet2.write_merge(r2, r2, 0, 10, title, Style.sub_main_title())
            sheet2.write_merge(r3, r3, 0, 10, 'Summary Based on Product Category', Style.subTitle())
            
            sheet2.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 1, "Product Category", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 2, "Product", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 3, "Reference", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 4, "Planned Start Date", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 5, "Warehouse/Branch", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 6, "Quantity to Produce", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 7, "UOM", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 8, "Raw Material Availability", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 9, "Source", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 10, "Status", Style.contentTextBold(r2,'black','white'))
            row = r4
            s_no = 0
            for each in manuf_order_list_data:
                product_str = each['product']
                product_data = json.loads(product_str.split('[] ')[-1])
                row = row + 1
                s_no = s_no + 1
                sheet2.row(row).height = 300
                sheet2.write(row, 0, s_no, Style.normal_left())
                sheet2.write(row, 1, each['category'], Style.normal_left())
                sheet2.write(row, 2, product_data['en_US'], Style.normal_left())
                sheet2.write(row, 3, each['reference'], Style.normal_left())
                sheet2.write(row, 4, each['start_date'], Style.normal_left())
                sheet2.write(row, 5, each['warehouse'], Style.normal_left())
                sheet2.write(row, 6, each['quantity'], Style.normal_num_left_3digits())
                sheet2.write(row, 7, each['uom']['en_US'], Style.normal_left())
                sheet2.write(row, 8, each['availability'], Style.normal_left())
                sheet2.write(row, 9, each['source'], Style.normal_left())
                sheet2.write(row, 10, each['status'], Style.normal_left())
            
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name +'.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'manufacturing.order.list.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
