# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_mrp.wizard.excel_styles import ExcelStyles
import xlwt
from io import BytesIO
import base64
import json
# import parser
from lxml import etree

class RawMaterialRequirementReportWizard(models.TransientModel):
    _name = 'raw.material.requirement.report.wizard'
    _description = 'Raw Material Requirement Report Wizard'
    
    date_from= fields.Date(string='From Date', required=True)
    date_to= fields.Date(string='To Date', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_raw_material_warehouse', 'raw_material_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_raw_material_product', 'raw_material_wizard_id', 'product_id', string='Product')
    raw_material_ids = fields.Many2many('product.product', 'etc_raw_material_prod_product', 'raw_material_wizard_id', 'material_id', string='Raw Materials')
    categ_ids = fields.Many2many('product.category', 'etc_raw_material_category', 'raw_material_wizard_id', 'categ_id', string='Category')
    show_value = fields.Boolean(string="Show Value")
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    state = fields.Selection([
        ('done', 'Done')], string='State')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(RawMaterialRequirementReportWizard, self).fields_view_get(
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
        product_obj = self.env['product.product']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Raw Material Requirement Report"
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
        categ_sql = """ """
        state_sql = """ """
        raw_material_sql = """ """
        
        product_ids = []
        product_list = []
        product_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        categ_ids = []
        categ_list = []
        categ_str = ""
        
        raw_material_ids = []
        raw_material_list = []
        raw_material_str = ""
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += " and mrp.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += " and mrp.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += " and mrp.warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += " and mrp.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                filters += ", Warehouse: " + warehouse_str
            
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(product_ids) > 1:
                product_sql += " and mrp.product_id in "+ str(tuple(product_ids))
            else:
                product_sql += " and mrp.product_id in ("+ str(product_ids[0]) + ")"
            filters += ", Product: " + product_str
            
        if self.raw_material_ids:
            for each_id in self.raw_material_ids:
                raw_material_ids.append(each_id.id)
                product_list.append(each_id.name)
            raw_material_list = list(set(raw_material_list))
            raw_material_str = str(raw_material_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(raw_material_ids) > 1:
                raw_material_sql += " and sm.product_id in "+ str(tuple(raw_material_ids))
            else:
                raw_material_sql += " and sm.product_id in ("+ str(raw_material_ids[0]) + ")"
            filters += ", Raw Material: " + raw_material_str
        
        if self.categ_ids:
            for each_id in self.categ_ids:
                categ_ids.append(each_id.id)
                categ_list.append(each_id.name)
            categ_list = list(set(categ_list))
            categ_str = str(categ_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(categ_ids) > 1:
                categ_sql += " and mrp_pt.categ_id in "+ str(tuple(categ_ids))
            else:
                categ_sql += " and mrp_pt.categ_id in ("+ str(categ_ids[0]) + ")"
            filters += ", Category: " + categ_str
        if self.state:
            if self.state == 'done':
                state_sql = " and mrp.state = " + "'" + str(self.state) + "'" + "and sm.state = 'done' and smv.state = 'done'"
                filters += ", State : Done"
        else:
            state_sql = " and mrp.state not in ('cancel', 'done') and sm.state not in ('done', 'cancel') and smv.state not in ('done', 'cancel')" 
            
        mo_requirement_sql = """select
	                                pp.id as product_id,
	                                (case when pp.default_code is not null then concat( '[' , pp.default_code::text, '] ', pt.name::text) else pt.name::text end ) as raw_materials,
	                                pu.name as uom,
	                                mrp_pc.name as category,
	                                (case when mrp_pp.default_code is not null then concat( '[' , mrp_pp.default_code::text, '] ', mrp_pt.name::text) else mrp_pt.name::text end ) as product,
	                                sum(sm.product_uom_qty) as qty,
	                                mrp.name as mo_no,
	                                sum(smv.product_uom_qty) as product_qty,
	                                (case when mrp.state in ('confirmed', 'planned') then 'Confirmed'
	                                 when mrp.state = 'progress' then 'In Progress'
	                                 when mrp.state = 'done' then 'Done' else mrp.state end) as state,
	                                 sw.name as warehouse
                                from stock_move sm
	                                left join mrp_production mrp on (mrp.id = sm.raw_material_production_id)
	                                left join product_product pp on (pp.id = sm.product_id)
	                                left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                left join uom_uom pu on (pu.id = pt.uom_id)
	                                left join product_product mrp_pp on (mrp_pp.id = mrp.product_id)
	                                left join product_template mrp_pt on (mrp_pt.id = mrp_pp.product_tmpl_id)
	                                left join product_category mrp_pc on (mrp_pc.id = mrp_pt.categ_id) 
	                                left join stock_warehouse sw on (sw.id = mrp.warehouse_id)
	                                left join stock_move smv on (mrp.id = smv.production_id)
                                where  
                                    sm.raw_material_production_id is not null
                                    and (((mrp.date_start at time zone %s)::timestamp::date) between %s and %s)""" + product_sql + warehouse_sql + categ_sql + state_sql + raw_material_sql +"""group by 
                                    pt.name, 
                                    pp.id,
                                    pu.name, 
                                    pt.default_code,
                                    pp.default_code,
                                    mrp.name,
                                    mrp_pc.name,
                                    mrp_pp.default_code,
                                    mrp_pt.name,
                                    mrp.state,
                                    sw.name
                                order by
                                    pt.default_code asc"""
                                    
	                                
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam' 
        
        self.env.cr.execute(mo_requirement_sql , (tz, date_from, date_to,))
        mo_requirement_data = self.env.cr.dictfetchall()
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 11000
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 8500
        sheet1.col(5).width = 8000
        sheet1.col(6).width = 5000
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 5500
        sheet1.col(9).width = 3500
        if self.show_value:
            sheet1.col(10).width = 3500

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
        if self.show_value:
            sheet1.write_merge(r1, r1, 0, 10, title1, Style.main_title())
            sheet1.write_merge(r2, r2, 0, 10, title, Style.sub_main_title())
            sheet1.write_merge(r3, r3, 0, 10, title2, Style.subTitle())
        else:
            sheet1.write_merge(r1, r1, 0, 9, title1, Style.main_title())
            sheet1.write_merge(r2, r2, 0, 9, title, Style.sub_main_title())
            sheet1.write_merge(r3, r3, 0, 9, title2, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Raw Material", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Raw Material Required Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "MO.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Product Qty", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Status", Style.contentTextBold(r2,'black','white'))
        if  self.show_value:
            sheet1.write(r4, 10, "Value", Style.contentTextBold(r2,'black','white'))
        row = r4
        s_no = 0
        
        product_id = False
        total = qty_value = qty_total = 0.00 
        for each in mo_requirement_data:
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>',each)
            raw_materials = json.loads(each['raw_materials'])
            product = json.loads(each['product'])
            value = 0.00
            row += 1
            s_no += 1
            if not product_id:
                product_id = each['product_id']
            if product_id != each['product_id']:  
                sheet1.write_merge(row, row, 0, 1, "Total", Style.groupByTitle())
                sheet1.write(row, 2, total, Style.groupByTotal3digits())
                if self.show_value:
                    sheet1.write_merge(row, row, 3, 7, qty_total, Style.groupByTotal3digits())
                    sheet1.write_merge(row, row, 8, 9, "", Style.groupByTotal3digits())
                    sheet1.write(row, 10, qty_value, Style.groupByTotal3Separator())
                else:
                    sheet1.write_merge(row, row, 3, 7, qty_total, Style.groupByTotal3digits())
                product_id = False
                total = 0.00
                qty_value = 0.00
                qty_total = 0.00
                row += 1
            total += each['qty']
            qty_total += each['product_qty']
            product_id = each['product_id']
            sheet1.row(row).height = 350
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, raw_materials['en_US'], Style.normal_left())
            sheet1.write(row, 2, each['qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 3, each['uom']['en_US'], Style.normal_left())
            sheet1.write(row, 4, each['category'], Style.normal_left())
            sheet1.write(row, 5, product['en_US'], Style.normal_left())
            sheet1.write(row, 6, each['mo_no'], Style.normal_left())
            sheet1.write(row, 7, each['product_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 8, each['warehouse'], Style.normal_left())
            sheet1.write(row, 9, each['state'], Style.normal_left())
            if self.show_value:
                product_brow = product_obj.browse(each['product_id'])
                value = product_brow.standard_price * each['qty']  
                sheet1.write(row, 10, value, Style.normal_num_right_3separator())
                qty_value += value 
        row += 1
        sheet1.write_merge(row, row, 0, 1, "Total", Style.groupByTitle())
        sheet1.write(row, 2, total, Style.groupByTotal3digits())
        if self.show_value:
            sheet1.write_merge(row, row, 3, 7, qty_total, Style.groupByTotal3digits())
            sheet1.write_merge(row, row, 8, 9, "", Style.groupByTotal3digits())
            sheet1.write(row, 10, qty_value, Style.groupByTotal3Separator())
        else:
            sheet1.write_merge(row, row, 3, 7, qty_total, Style.groupByTotal3digits())
            
        stream = BytesIO()
        wbk.save(stream)
        self.write({ 'name': report_name +'.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'raw.material.requirement.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }    
    
