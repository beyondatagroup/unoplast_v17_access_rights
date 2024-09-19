# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_mrp.wizard.excel_styles import ExcelStyles
import xlwt
from xlwt import *
from io import BytesIO
import base64
import xlrd
# import parser
from lxml import etree
import json

class SfManufacturingOrderReportWizard(models.TransientModel):
    _name = 'sf.manufacturing.order.report.wizard'
    _description = 'SF Manufacturing Order Report Wizard'
    
    date_from= fields.Date(string='From Date', required=True)
    date_to= fields.Date(string='To Date', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_sf_manuf_order_warehouse', 'sf_manuf_order_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_sf_manuf_order_product', 'sf_manuf_order_wizard_id', 'product_id', string='Product')
    categ_ids = fields.Many2many('product.category', 'etc_sf_manuf_order_category', 'sf_manuf_order_wizard_id', 'categ_id', string='Category')
    shift_type = fields.Selection([('shift_1', 'Shift-1'), ('shift_2', 'Shift-2'), ('shift_3', 'Shift-3')], string="Shift")
    summary = fields.Boolean(string='Summary')
    state = fields.Selection([('draft', 'Draft'), ('inprogress', 'Inprogress'), ('completed', 'Completed')], string='Status')
    show_value = fields.Boolean(string="Show Value")
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name= fields.Char(string='File Name', readonly=True)
    output= fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(SfManufacturingOrderReportWizard, self).fields_view_get(
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
        date_from = self.date_from
        date_to = self.date_to
        report_name = "SF Manufacturing Order Report"
        unbuild_order_report_name = "SF Manufacturing Unbuild Order Report"
        summary_report = "Summary Based on Product Report"
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date)
        warehouse_sql = """ """
        product_sql = """ """
        categ_sql = """ """
        shift_type_sql = """ """
        state_sql = """ """
        
        product_ids = []
        product_list = []
        product_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        categ_ids = []
        categ_list = []
        categ_str = ""
        
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and smo.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and smo.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += " and smo.warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += " and smo.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                filters += ", Warehouse: " + warehouse_str
            
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(product_ids) > 1:
                product_sql += " and smo.product_id in "+ str(tuple(product_ids))
            else:
                product_sql += " and smo.product_id in ("+ str(product_ids[0]) + ")"
            filters += ", Product: " + product_str
        if self.categ_ids:
            for each_id in self.categ_ids:
                categ_ids.append(each_id.id)
                categ_list.append(each_id.name)
            categ_list = list(set(categ_list))
            categ_str = str(categ_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(categ_ids) > 1:
                categ_sql += " and pt.categ_id in "+ str(tuple(categ_ids))
            else:
                categ_sql += " and pt.categ_id in ("+ str(categ_ids[0]) + ")"
            filters += ", Category: " + categ_str
        if self.shift_type:
            shift_type_sql = " and smo.shift_type = " + "'" + str(self.shift_type) + "'"
            if self.shift_type == 'shift_1':
                filters += ", Shift : Shift-1"
            if self.shift_type == 'shift_2':
                filters += ", Shift : Shift-2"
            if self.shift_type == 'shift_3':
                filters += ", Shift : Shift-3"
        if self.state:
            state_sql = " and smo.state = " + "'" + str(self.state) + "'"
            if self.state == 'draft':
                filters += ", State : Draft"
            if self.state == 'inprogress':
                filters += ", State : Inprogress"
            if self.state == 'completed':
                filters += ", State : In Completed"
        else:
            state_sql = " and smo.state = 'completed'"
            
        sf_manuf_order_base_sql = """select
	                                smo.id as manuf_order_id,
	                                smo.name as sequence,
	                                to_char(smo.date, 'dd-mm-yyyy') as manuf_order_date,
	                                concat( '[' , pt.default_code, '] ', pt.name) as product,
	                                pu.name as uom,
	                                pc.name as category,
	                                sw.name as warehouse,
	                                source.name as source_location,
	                                dest.name as dest_location,
	                                smo.product_qty as qty,
	                                (case when smo.order_type = 'unbuild_order' then smo.source_doc else '' end) as source_doc,
	                                (case when smo.shift_type = 'shift_1' then 'Shift-1'
	                                 when smo.shift_type = 'shift_2' then 'Shift-2'
	                                 when smo.shift_type = 'shift_3' then 'Shift-3' else smo.shift_type end) as shift,
                                    (case when smo.state = 'draft' then 'Draft'
                                     when smo.state = 'inprogress' then 'Inprogress'
                                     when smo.state = 'completed' then 'Completed' else smo.state end) as state
                                from sf_manufacturing_order smo
	                                left join product_product pp on (pp.id = smo.product_id)
	                                left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                left join uom_uom pu on (pu.id = pt.uom_id)
	                                left join product_category pc on (pc.id = pt.categ_id)  
	                                left join stock_warehouse sw on (sw.id = smo.warehouse_id)
	                                left join stock_location source on (source.id = smo.source_location_id)
	                                left join stock_location dest on (dest.id = smo.dest_location_id)"""
        sf_manuf_cond_sql = """where (smo.date between %s and %s) and smo.order_type = 'normal' """ + warehouse_sql + categ_sql + product_sql + shift_type_sql + state_sql +""" order by smo.date asc, smo.name"""  
        
        sf_manuf_unbuild_cond_sql = """where (smo.date between %s and %s) and smo.order_type = 'unbuild_order' """ + warehouse_sql + categ_sql + product_sql + shift_type_sql + state_sql +""" order by smo.date asc, smo.name""" 
                                
        sf_raw_material_sql = """select
                                    rml.id as rml_id,
                                    rml.quantity as quantity,
                                    concat( '[' , pt.default_code, '] ', pt.name) as product,
                                    pu.name as uom,
                                    (select (case when sum((sm.price_unit * sm.product_uom_qty)) is not null then sum((sm.price_unit * sm.product_uom_qty)) else 0.00 end)
	                                        from stock_move sm
	                                        where sm.sf_raw_material_id = rml.id) as raw_material_value
                                from raw_materials_line rml
                                    left join sf_manufacturing_order smo on (smo.id = rml.order_id)
                                    left join product_product pp on (pp.id = rml.product_id)
                                    left join product_template pt on (pt.id = pp.product_tmpl_id)
                                    left join uom_uom pu on (pu.id = pt.uom_id)
                                where smo.id = %s """
                                
        sf_manuf_order_summary_sql = """ select 
	                                        concat( '[' , pt.default_code, '] ', pt.name) as product,
	                                        smo.product_id as product_id,
	                                        pu.name as uom,
	                                        sw.name as warehouse,
	                                        sum(case when 
	                                                smo.order_type = 'normal' then coalesce(product_qty, 0.00)
	                                              when
	                                                smo.order_type = 'unbuild_order' then coalesce(-product_qty, 0.00)
	                                              else 0.00 
	                                         end) as qty
                                        from sf_manufacturing_order smo
	                                        left join product_product pp on (pp.id = smo.product_id)
	                                        left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                        left join uom_uom pu on (pu.id = pt.uom_id)
	                                        left join product_category pc on (pc.id = pt.categ_id)  
	                                        left join stock_warehouse sw on (sw.id = smo.warehouse_id)
                                        where (smo.date between %s and %s) and smo.order_type in ('normal', 'unbuild_order')""" + warehouse_sql + categ_sql + product_sql + shift_type_sql + state_sql + """ group by pt.name, 
	                                         sw.name,
	                                         pt.default_code,
	                                         pu.name,
	                                         sw.name,
	                                         smo.product_id 
	                                   order by pt.default_code, pt.name"""
	                                         
        sf_raw_material_summary_sql = """select
                                            concat( '[' , pt.default_code, '] ', pt.name) as product,
                                            pu.name as uom,
                                            (case when sum(rml.quantity) is not null then sum(rml.quantity) else 0.00 end) as quantity
                                        from raw_materials_line rml
                                            left join sf_manufacturing_order smo on (smo.id = rml.order_id)
                                            left join product_product pp on (pp.id = rml.product_id)
                                            left join product_template pt on (pt.id = pp.product_tmpl_id)
                                            left join uom_uom pu on (pu.id = pt.uom_id)
                                        where smo.product_id = %s and (smo.date between %s and %s) and smo.order_type = 'normal'
                                        group by 
                                            pt.default_code, 
                                            pt.name, 
                                            pu.name 
                                        order by pt.default_code, pt.name"""
        
        sf_manuf_order_sql = sf_manuf_order_base_sql + sf_manuf_cond_sql
        
        self.env.cr.execute(sf_manuf_order_sql , (date_from, date_to,))
        sf_manuf_order_data = self.env.cr.dictfetchall()
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
#        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4500
        sheet1.col(2).width = 3000
        sheet1.col(3).width = 4500
        sheet1.col(4).width = 7000
        sheet1.col(5).width = 4500
        sheet1.col(6).width = 3000
        sheet1.col(7).width = 8000
        sheet1.col(8).width = 9000
        sheet1.col(9).width = 3000
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        if self.show_value:
            sheet1.col(13).width = 4000
            sheet1.col(14).width = 9000
            sheet1.col(15).width = 3000
            sheet1.col(16).width = 3000
            sheet1.col(17).width = 4000
        else:
            sheet1.col(13).width = 9000
            sheet1.col(14).width = 3000
            sheet1.col(15).width = 3000
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 256 * 3
        title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
        title1 = self.company_id.name
        title2 = filters 
        title3 = 'Raw Materials Consumed'
        if self.show_value:
            sheet1.write_merge(r1, r1, 0, 17, title1, Style.main_title())
            sheet1.write_merge(r2, r2, 0, 17, title, Style.sub_main_title())
            sheet1.write_merge(r3, r3, 0, 13, title2, Style.subTitle())
            sheet1.write_merge(r3, r3, 14, 17, title3, Style.subTitle())
        else:
            sheet1.write_merge(r1, r1, 0, 15, title1, Style.main_title())
            sheet1.write_merge(r2, r2, 0, 15, title, Style.sub_main_title())
            sheet1.write_merge(r3, r3, 0, 12, title2, Style.subTitle())
            sheet1.write_merge(r3, r3, 13, 15, title3, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "MO No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Destination Location", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Shift", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 11, "Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 12, "Source Document", Style.contentTextBold(r2,'black','white'))
        if self.show_value:
            sheet1.write(r4, 13, "Production Value", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r4, 14, "Product", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r4, 15, "UOM", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r4, 16, "Quantity", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r4, 17, "Consumption Value", Style.contentTextBold(r2,'black','white'))
        else:
            sheet1.write(r4, 13, "Product", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r4, 14, "UOM", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r4, 15, "Quantity", Style.contentTextBold(r2,'black','white'))
        
        row = r4
        s_no = 0
        overall_summary = OrderedDict()
        un_row = 0
        for each in sf_manuf_order_data:
            product_str = each['product']
            product_data = json.loads(product_str.split('[] ')[-1])
            row = row + 1
            s_row = row
            s_no = s_no + 1
            total_prodution = 0.00
            sheet1.row(row).height = 350
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, "Regular", Style.normal_left())
            sheet1.write(row, 2, each['manuf_order_date'], Style.normal_left())
            sheet1.write(row, 3, each['sequence'], Style.normal_left())
            sheet1.write(row, 4, each['warehouse'], Style.normal_left())
            sheet1.write(row, 5, each['dest_location'], Style.normal_left())
            sheet1.write(row, 6, each['shift'], Style.normal_left())
            sheet1.write(row, 7, each['category'], Style.normal_left())
            sheet1.write(row, 8, product_data['en_US'], Style.normal_left())
            sheet1.write(row, 9, each['uom']['en_US'], Style.normal_left())
            sheet1.write(row, 10, each['qty'], Style.normal_num_right_3digits())
            if each['product'] not in overall_summary:
                overall_summary[each['product']] = [0.00, 0.00, 0.00, 0.00]
            overall_summary[each['product']][0] += each['qty']
            sheet1.write(row, 11, each['state'], Style.normal_left())
            sheet1.write(row, 12, " ", Style.normal_left())
            
            self.env.cr.execute(sf_raw_material_sql , (each['manuf_order_id'],))
            sf_raw_material_data = self.env.cr.dictfetchall()
            if sf_raw_material_data:
                if self.show_value:
                    for line in sf_raw_material_data:
                        product_str = line['product']
                        product_data = json.loads(product_str.split('[] ')[-1])
                        sheet1.row(row).height = 350
                        sheet1.write(row, 14, product_data['en_US'], Style.normal_left())
                        sheet1.write(row, 15, line['uom']['en_US'], Style.normal_left())
                        sheet1.write(row, 16, line['quantity'], Style.normal_num_right_3digits())
                        if line['product'] not in overall_summary:
                            overall_summary[line['product']] = [0.00, 0.00, 0.00, 0.00]
                        overall_summary[line['product']][0] += line['quantity']
                        sheet1.write(row, 17, line['raw_material_value'], Style.normal_num_right_3separator())
                        overall_summary[line['product']][2] += line['raw_material_value']
                        total_prodution += line['raw_material_value']
                        row = row + 1
                    row = row - 1
                    sheet1.write(s_row, 13, total_prodution, Style.normal_num_right_3separator())
                    overall_summary[each['product']][2] += total_prodution
                else:
                    for line in sf_raw_material_data:
                        product_str = line['product']
                        product_data = json.loads(product_str.split('[] ')[-1])
                        sheet1.row(row).height = 350
                        sheet1.write(row, 13, product_data['en_US'], Style.normal_left())
                        sheet1.write(row, 14, line['uom']['en_US'], Style.normal_left())
                        sheet1.write(row, 15, line['quantity'], Style.normal_num_right_3digits())
                        if line['product'] not in overall_summary:
                            overall_summary[line['product']] = [0.00, 0.00, 0.00, 0.00]
                        overall_summary[line['product']][0] += line['quantity']
                        row = row + 1
                    row = row - 1
            un_row = row
            
        if self.date_from and self.date_to and self.summary:    
            sheet2 = wbk.add_sheet(summary_report)
            sheet2.set_panes_frozen(True)
            sheet2.set_horz_split_pos(4)
#            sheet2.show_grid = False 
            sheet2.col(0).width = 2000
            sheet2.col(1).width = 9000
            sheet2.col(2).width = 3000
            sheet2.col(3).width = 6500
            sheet2.col(4).width = 3000
            sheet2.col(5).width = 9000
            sheet2.col(6).width = 3000
            sheet2.col(7).width = 3500
        
            r1 = 0
            r2 = 1
            r3 = 2
            r4 = 3
            
            sheet2.row(r1).height = 500
            sheet2.row(r2).height = 400
            sheet2.row(r3).height = 200 * 2
            sheet2.row(r4).height = 256 * 3
            title = summary_report +' ( Date From ' + from_date + ' To ' + to_date + ' )'
            title1 = self.company_id.name
            title3 = 'Raw Materials Consumed'
            sheet2.write_merge(r1, r1, 0, 7, title1, Style.main_title())
            sheet2.write_merge(r2, r2, 0, 7, title, Style.sub_main_title())
            sheet2.write_merge(r3, r3, 0, 4, 'Summary Based on Product', Style.subTitle())
            sheet2.write_merge(r3, r3, 5, 7, title3, Style.subTitle())
            
            sheet2.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 1, "Product", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 2, "UOM", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 4, "Quantity", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 5, "Product", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 6, "UOM", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 7, "Quantity", Style.contentTextBold(r2,'black','white'))
            row = r4
            s_no = 0
            
            self.env.cr.execute(sf_manuf_order_summary_sql, (date_from, date_to,))
            sf_manuf_order_summary_data = self.env.cr.dictfetchall()
            for each in sf_manuf_order_summary_data:
                product_str = each['product']
                product_data = json.loads(product_str.split('[] ')[-1])
                row = row + 1
                s_no = s_no + 1
                sheet2.row(row).height = 350
                sheet2.write(row, 0, s_no, Style.normal_left())
                sheet2.write(row, 1, product_data['en_US'], Style.normal_left())
                sheet2.write(row, 2, each['uom']['en_US'], Style.normal_left())
                sheet2.write(row, 3, each['warehouse'], Style.normal_left())
                sheet2.write(row, 4, each['qty'], Style.normal_num_right_3digits())
                self.env.cr.execute(sf_raw_material_summary_sql , (each['product_id'], date_from, date_to,))
                sf_raw_material_summary_data = self.env.cr.dictfetchall()
                for line in sf_raw_material_summary_data:
                    product_str = line['product']
                    product_data = json.loads(product_str.split('[] ')[-1])
                    sheet2.row(row).height = 350
                    sheet2.write(row, 5, product_data['en_US'], Style.normal_left())
                    sheet2.write(row, 6, line['uom']['en_US'], Style.normal_left())
                    sheet2.write(row, 7, line['quantity'], Style.normal_num_right_3digits())
                    row = row + 1
                row = row - 1
                
#====================================SF-Manufacturing Unbuild Order========================================
        
        sf_manuf_unbuild_order_sql = sf_manuf_order_base_sql + sf_manuf_unbuild_cond_sql
        
        self.env.cr.execute(sf_manuf_unbuild_order_sql , (date_from, date_to,))
        sf_manuf_unbuild_order_data = self.env.cr.dictfetchall()
        
#        sheet3 = wbk.add_sheet(unbuild_order_report_name)
#        sheet3.set_panes_frozen(True)
#        sheet3.set_horz_split_pos(4)
##        sheet3.show_grid = False 
#        sheet3.col(0).width = 2000
#        sheet3.col(1).width = 3000
#        sheet3.col(2).width = 3000
#        sheet3.col(3).width = 7000
#        sheet3.col(4).width = 4500
#        sheet3.col(5).width = 3000
#        sheet3.col(6).width = 8000
#        sheet3.col(7).width = 9000
#        sheet3.col(8).width = 3000
#        sheet3.col(9).width = 3500
#        sheet3.col(10).width = 3500
#        sheet3.col(11).width = 4500
#        if self.show_value:
#            sheet3.col(12).width = 4000
#            sheet3.col(13).width = 9000
#            sheet3.col(14).width = 3000
#            sheet3.col(15).width = 3000
#            sheet3.col(16).width = 4000
#        else:
#            sheet3.col(12).width = 9000
#            sheet3.col(13).width = 3000
#            sheet3.col(14).width = 3000
#    
#        r1 = 0
#        r2 = 1
#        r3 = 2
#        r4 = 3
#        sheet3.row(r1).height = 500
#        sheet3.row(r2).height = 400
#        sheet3.row(r3).height = 200 * 2
#        sheet3.row(r4).height = 256 * 3
#        title = unbuild_order_report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
#        title1 = self.company_id.name
#        title2 = filters 
#        title3 = 'Unbuild Raw Materials'
#        if self.show_value:
#            sheet3.write_merge(r1, r1, 0, 16, title1, Style.main_title())
#            sheet3.write_merge(r2, r2, 0, 16, title, Style.sub_main_title())
#            sheet3.write_merge(r3, r3, 0, 12, title2, Style.subTitle())
#            sheet3.write_merge(r3, r3, 13, 16, title3, Style.subTitle())
#        else:
#            sheet3.write_merge(r1, r1, 0, 14, title1, Style.main_title())
#            sheet3.write_merge(r2, r2, 0, 14, title, Style.sub_main_title())
#            sheet3.write_merge(r3, r3, 0, 11, title2, Style.subTitle())
#            sheet3.write_merge(r3, r3, 12, 14, title3, Style.subTitle())
#        
#        sheet3.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 1, "Date", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 2, "Unbuild Order No", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 4, "Destination Location", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 5, "Shift", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 6, "Product Category", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 7, "Product", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 8, "UOM", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 9, "Quantity", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 10, "Status", Style.contentTextBold(r2,'black','white'))
#        sheet3.write(r4, 11, "Source Document", Style.contentTextBold(r2,'black','white'))
#        if self.show_value:
#            sheet3.write(r4, 12, "Production Value", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 13, "Product", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 14, "UOM", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 15, "Quantity", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 16, "Consumption Value", Style.contentTextBold(r2,'black','white'))
#        else:
#            sheet3.write(r4, 12, "Product", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 13, "UOM", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 14, "Quantity", Style.contentTextBold(r2,'black','white'))
#        
#        row = r4
#        s_no = 0
        row = un_row
        for each in sf_manuf_unbuild_order_data:
            product_str = each['product']
            product_data = json.loads(product_str.split('[] ')[-1])
            row = row + 1
            s_row = row
            s_no = s_no + 1
            total_prodution = 0.00
            sheet1.row(row).height = 350
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, "Unbuild Order", Style.normal_left())
            sheet1.write(row, 2, each['manuf_order_date'], Style.normal_left())
            sheet1.write(row, 3, each['sequence'], Style.normal_left())
            sheet1.write(row, 4, each['warehouse'], Style.normal_left())
            sheet1.write(row, 5, each['dest_location'], Style.normal_left())
            sheet1.write(row, 6, each['shift'], Style.normal_left())
            sheet1.write(row, 7, each['category'], Style.normal_left())
            sheet1.write(row, 8, product_data['en_US'], Style.normal_left())
            sheet1.write(row, 9, each['uom']['en_US'], Style.normal_left())
            sheet1.write(row, 10, (-1 * each['qty']), Style.normal_num_right_3digits())
            if each['product'] not in overall_summary:
                overall_summary[each['product']] = [0.00, 0.00, 0.00, 0.00]
            overall_summary[each['product']][1] += each['qty']
            sheet1.write(row, 11, each['state'], Style.normal_left())
            sheet1.write(row, 12, each['source_doc'], Style.normal_left())
            
            self.env.cr.execute(sf_raw_material_sql , (each['manuf_order_id'],))
            sf_raw_material_data = self.env.cr.dictfetchall()
            if sf_raw_material_data:
                if self.show_value:
                    for line in sf_raw_material_data:
                        product_str = each['product']
                        product_data = json.loads(product_str.split('[] ')[-1])
                        sheet1.row(row).height = 350
                        sheet1.write(row, 14, product_data['en_US'], Style.normal_left())
                        sheet1.write(row, 15, line['uom']['en_US'], Style.normal_left())
                        sheet1.write(row, 16, (-1 * line['quantity']), Style.normal_num_right_3digits())
                        if line['product'] not in overall_summary:
                            overall_summary[line['product']] = [0.00, 0.00, 0.00, 0.00]
                        overall_summary[line['product']][1] += line['quantity']
                        sheet1.write(row, 17, -line['raw_material_value'], Style.normal_num_right_3separator())
                        overall_summary[line['product']][3] += line['raw_material_value']
                        total_prodution += line['raw_material_value'] 
                        row = row + 1
                    row = row - 1
                    sheet1.write(s_row, 13, -total_prodution, Style.normal_num_right_3separator())
                    overall_summary[each['product']][3] += total_prodution
                else:
                    for line in sf_raw_material_data:
                        product_str = each['product']
                        product_data = json.loads(product_str.split('[] ')[-1])
                        sheet1.row(row).height = 350
                        sheet1.write(row, 13, product_data['en_US'], Style.normal_left())
                        sheet1.write(row, 14, line['uom']['en_US'], Style.normal_left())
                        sheet1.write(row, 15, line['quantity'], Style.normal_num_right_3digits())
                        if line['product'] not in overall_summary:
                            overall_summary[line['product']] = [0.00, 0.00, 0.00, 0.00]
                        overall_summary[line['product']][1] += line['quantity']
                        row = row + 1
                    row = row - 1
#**************************************************Overall Summary**********************************************************************
        
        sheet4 = wbk.add_sheet('Overall Summary')
        sheet4.set_panes_frozen(True)
        sheet4.set_horz_split_pos(4)
        sheet4.show_grid = False 
        sheet4.col(0).width = 2000
        sheet4.col(1).width = 13500
        sheet4.col(2).width = 4500
        sheet4.col(3).width = 4500
        sheet4.col(4).width = 4500
        sheet4.col(5).width = 5500
        sheet4.col(6).width = 4500
        sheet4.col(7).width = 4500
        
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet4.row(r1).height = 500
        sheet4.row(r2).height = 400
        sheet4.row(r3).height = 200 * 2
        title = "Overall Summary" +' ( Date From ' + from_date + ' To ' + to_date + ' )'
        title1 = self.company_id.name
        title2 = filters 
        
        col_end = self.show_value and 6 or 4
        sheet4.write_merge(r1, r1, 0, col_end, title1, Style.main_title())
        sheet4.write_merge(r2, r2, 0, col_end, title, Style.sub_main_title())
        sheet4.write_merge(r3, r3, 0, col_end, title2, Style.subTitle())
    
        sheet4.write(r4, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet4.write(r4, 1, "Product", Style.contentTextBold(r3, 'black', 'white'))
        sheet4.write(r4, 2, "Built Quantity", Style.contentTextBold(r3, 'black', 'white'))
        if self.show_value:
            sheet4.write(r4, 3, "Built Cost", Style.contentTextBold(r3, 'black', 'white'))
            sheet4.write(r4, 4, "Unbuilt Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet4.write(r4, 5, "Unbuilt Cost", Style.contentTextBold(r3, 'black', 'white'))
            sheet4.write(r4, 6, "Total Built Quantity", Style.contentTextBold(r3, 'black', 'white'))
        else:    
            sheet4.write(r4, 3, "Unbuilt Quantity", Style.contentTextBold(r3, 'black', 'white'))
            sheet4.write(r4, 4, "Total Built Quantity", Style.contentTextBold(r3, 'black', 'white'))
        s_no = 0
        row = r4
        if self.show_value:
            for each in overall_summary:
                product_data = json.loads(each.split('[] ')[-1])
                s_no += 1
                row += 1
                sheet4.write(row, 0, s_no, Style.normal_left())
                sheet4.write(row, 1, product_data['en_US'], Style.normal_left())
                sheet4.write(row, 2, overall_summary[each][0], Style.normal_right())
                sheet4.write(row, 3, overall_summary[each][2], Style.normal_right())
                sheet4.write(row, 4, overall_summary[each][1], Style.normal_right())
                sheet4.write(row, 5, overall_summary[each][3], Style.normal_right())
                built_qty = xlwt.Utils.rowcol_to_cell(row, 2)
                unbuilt_qty = xlwt.Utils.rowcol_to_cell(row, 4)
                sheet4.write(row, 6, Formula((str(built_qty) + '-' + str(unbuilt_qty))), Style.normal_right())
        else:
             for each in overall_summary:
                product_data = json.loads(each.split('[] ')[-1])
                s_no += 1
                row += 1
                sheet4.write(row, 0, s_no, Style.normal_left())
                sheet4.write(row, 1, product_data['en_US'], Style.normal_left())
                sheet4.write(row, 2, overall_summary[each][0], Style.normal_right())
                sheet4.write(row, 3, overall_summary[each][1], Style.normal_right())
                built_qty = xlwt.Utils.rowcol_to_cell(row, 2)
                unbuilt_qty = xlwt.Utils.rowcol_to_cell(row, 3)
                sheet4.write(row, 4, Formula((str(built_qty) + '-' + str(unbuilt_qty))), Style.normal_right())       
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sf.manufacturing.order.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
