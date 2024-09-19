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
import xlrd
import json
from lxml import etree

class ManufacturingOrderReportWizard(models.TransientModel):
    _name = 'manufacturing.order.report.wizard'
    _description = 'Manufacturing Order Report Wizard'
    
    date_from= fields.Date(string='From Date', required=True)
    date_to= fields.Date(string='To Date', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_manuf_order_warehouse', 'manuf_order_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_manuf_order_product', 'manuf_order_wizard_id', 'product_id', string='Product')
    categ_ids = fields.Many2many('product.category', 'etc_manuf_order_category', 'manuf_order_wizard_id', 'categ_id', string='Category')
    show_value = fields.Boolean(string="Show Value")
    shift_type = fields.Selection([('shift_1', 'Shift 1'), ('shift_2', 'Shift 2'), ('shift_3', 'Shift 3')], string="Shift")
    summary = fields.Boolean(string='Summary')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    state = fields.Selection([
        ('progress', 'In Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')], string='State')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(ManufacturingOrderReportWizard, self).fields_view_get(
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
        unbuild_obj = self.env['mrp.unbuild']
        move_obj = self.env['stock.move']
        report_name = "Manufacturing Order Report"
#        summary_report_name = "Product Wise Summary Report" 
#        summary_product_report_name = "Raw Material Wise Summary Report" 
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
        shift_type_sql = """ """
        
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
        if self.state:
            if self.state == 'progress':
                state_sql = " and mrp.state in ('confirmed', 'planned', 'progress')" 
            else:
                state_sql = " and mrp.state = " + "'" + str(self.state) + "'"
            if self.state == 'progress':
                filters += ", State : In Progress"
            if self.state == 'done':
                filters += ", State : Done"
            if self.state == 'cancel':
                filters += ", State : Cancelled"
        else:
            state_sql = " and mrp.state != 'cancel'" 
        if self.shift_type:
            shift_type_sql = " and sm.shift_type = " + "'" + str(self.shift_type) + "'"
            if self.shift_type == 'shift_1':
                filters += ", Shift : Shift 1"
            if self.shift_type == 'shift_2':
                filters += ", Shift : Shift 2"
            if self.shift_type == 'shift_3':
                filters += ", Shift : Shift 3"
        manuf_order_sql = """select
	                            mrp.id as mrp_id,
	                            mrp.name as mo_no,
	                            to_char(((mrp.date_start at time zone %s)::timestamp::date), 'dd-mm-yyyy') as planned_date,
	                            pp.id as product_id,
	                            (case when pp.default_code is not null then concat( '[' , pt.default_code::text, '] ', pt.name::text) else pt.name::text end) as product,
	                            pu.name as uom,
	                            pc.name as category,
	                            sum(sm.product_uom_qty) as planned_qty,
	                            sum(sm.quantity) as produced_qty,
                                (sum(sm.product_uom_qty) - sum(sm.quantity)) as pending_qty, 
	                            (case when bom_pp.default_code is not null then concat( '[' , bom_pt.default_code::text, '] ', bom_pt.name::text) else bom_pt.name::text end ) as bom,
	                            rp.name as responsible,
	                            mrp.origin as source,
	                            sw.name as warehouse,
	                            (case when mrp.force_closed = True then 'Yes' else 'No' end)as force_closed,
	                            (case when mrp.state in ('confirmed', 'planned','progress') then 'In Progress'
                                 when mrp.state = 'done' then 'Done'
                                 when mrp.state = 'cancel' then 'Cancelled' else mrp.state end) as state
                                from mrp_production mrp
                                    left join stock_move sm on (sm.production_id = mrp.id)
	                                left join product_product pp on (pp.id = sm.product_id)
	                                left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                left join uom_uom pu on (pu.id = pt.uom_id)
	                                left join product_category pc on (pc.id = pt.categ_id)
	                                left join mrp_bom bom on (bom.id = mrp.bom_id)
	                                left join product_template bom_pt on (bom_pt.id = bom.product_tmpl_id)
	                                left join product_product bom_pp on (bom_pp.id = bom.product_id)
	                                left join res_users res on (res.id  = mrp.user_id)
	                                left join res_partner rp on (rp.id = res.partner_id)
	                                left join stock_warehouse sw on (sw.id = mrp.warehouse_id)
                                where (((mrp.date_start at time zone %s)::timestamp::date) between %s and %s)""" + product_sql + warehouse_sql + categ_sql + state_sql + shift_type_sql +""" group by mrp.id,
	                                    mrp.name,
	                                    pp.id,
	                                    mrp.date_start,
	                                    pp.default_code,
	                                    pt.default_code,
	                                    pt.name,
	                                    pu.name,
	                                    pc.name,
	                                    bom_pt.default_code,
	                                    bom_pp.default_code,
	                                    bom_pt.name,
	                                    rp.name,
	                                    mrp.origin,
	                                    sw.name,
	                                    mrp.force_closed,
	                                    mrp.state  
	                               order by mrp.date_start asc """
                                
        raw_material_sql = """select
	                            (case when pp.default_code is not null then concat( '[' , pt.default_code::text, '] ', pt.name::text) else pt.name::text end) as product,
	                            mrp.product_id as product_id,
	                            pu.name as uom,
	                            (case when sum(sm.product_uom_qty) is not null then sum(sm.product_uom_qty) else 0.00 end) as planned_consumption_qty,
	                            (case when sum(sm.quantity) is not null then sum(sm.quantity) else 0.00 end) as actual_consumed_qty,
                                (case when sum(sm.product_uom_qty * sm.price_unit) is not null then sum(sm.product_uom_qty * sm.price_unit) else 0.00 end) as raw_material,
                                (case when sm.state in ('draft', 'waiting', 'confirmed', 'assigned') then 'Inprogress'
                                 when sm.state = 'done' then 'Done' else sm.state end) as state
                            from stock_move sm
	                            left join mrp_production mrp on (mrp.id = sm.raw_material_production_id)
	                            left join product_product pp on (pp.id = sm.product_id)
	                            left join product_template pt on (pt.id = pp.product_tmpl_id)
	                            left join uom_uom pu on (pu.id = pt.uom_id)
                            where 
                                mrp.id = %s and 
                                sm.scrapped = False and sm.state != 'cancel'
                                and sm.raw_material_production_id is not null """ + warehouse_sql + """
                            group by 
                                pt.name, 
                                pu.name,
                                sm.id, 
                                mrp.product_id,
                                pt.default_code,
                                pp.default_code,
                                sm.state 
                            order by
                                sm.state, pt.default_code asc"""
                            
        finished_products_sql = """select
                                    sm.id as sm_id, 
                                    to_char(((sm.date at time zone %s)::timestamp::date), 'dd-mm-yyyy') as production_date,
                                    (case when sm.shift_type = 'shift_1' then 'Shift 1'
                                     when sm.shift_type = 'shift_2' then 'Shift 2'
                                     when sm.shift_type = 'shift_3' then 'Shift 3' else sm.shift_type end) as shift,
                                    (case when sum(sm.quantity) is not null then sum(sm.quantity) else 0.00 end) as quantity_done,
                                    (case when sum(sm.product_uom_qty) is not null then sum(sm.product_uom_qty) else 0.00 end) as to_produce,
                                    (case when sm.state in ('draft', 'waiting', 'confirmed', 'assigned') then 'Pending'
                                     when sm.state = 'done' then 'Done' else sm.state end) as state
                                    from stock_move sm 
                                     left join mrp_production mrp on (mrp.id = sm.production_id)
                                     left join product_product pp on (pp.id = sm.product_id)
                                where 
                                    mrp.id = %s and 
                                    pp.id = %s and
                                    sm.scrapped = False and sm.state != 'cancel'
                                    and sm.production_id is not null """+ warehouse_sql + """
                                group by
                                    sm.id, 
                                    production_date,
                                    shift, sm.state"""
                                    

                                    
        built_summary_sql = """ select x.p_type,
                                       x.product, 
                                       sum(x.built_qty) as bt_qty,
                                       sum(x.built_cost) as bt_cost,
                                       (sum(x.built_cost) / sum(x.built_qty)) as u_cost,
                                       sum(x.unbuilt_qty) as ub_qty,
                                       sum(x.unbuilt_cost) as unb_cost,
                                       (sum(x.built_qty) - sum(x.unbuilt_qty)) as total_qty,
                                       ((sum(x.built_qty) - sum(x.unbuilt_qty)) * (sum(x.built_cost) / sum(x.built_qty))) as tl_cost
                                from
                                ((select 
	                                'FG' as p_type,
	                                mrp.id as mpid,
	                                pp.id as p_id,
	                                pt.name as product,
	                                sum(sm.product_qty) as built_qty,
                                        (select coalesce(sum(stm.product_qty), 0.00) as unbuilt_qty 
	                                    from stock_move stm
	                                    left join mrp_unbuild ub on (ub.id = stm.consume_unbuild_id) 
	                                    where ub.mo_id = mrp.id and stm.product_id = pp.id),
	                                sum((sm.price_unit * sm.product_qty)) as built_cost,
	                                coalesce((select sum((sq.qty * sq.cost)) 
	                                 from stock_quant_move_rel sqm
	                                 left join stock_quant sq on (sq.id = sqm.quant_id)
	                                 left join stock_move stm on (stm.id = sqm.move_id)
	                                 left join mrp_unbuild mpu on (mpu.id = stm.consume_unbuild_id)
	                                 where mpu.mo_id = mrp.id and stm.product_id = pp.id), 0.00) as unbuilt_cost,
	                                
	                                sum((sm.price_unit * sm.product_qty))/ sum(mrp.product_qty) as unit_cost
	                                
                                from stock_move sm
                                    left join mrp_production mrp on (mrp.id = sm.production_id)
                                    left join product_product pp on (pp.id = sm.product_id)
                                    left join product_template pt on (pt.id = pp.product_tmpl_id)
                                where (((mrp.date_start at time zone %s)::timestamp::date) between %s and %s) and sm.production_id is not null and mrp.state = 'done' """ + product_sql + warehouse_sql + categ_sql + shift_type_sql +"""
                                group by
                                    mrp.id,
                                    pp.id,
                                    pt.name
                                order by p_type, product)
                                UNION
                                (select 
	                                'Raw' as p_type,
	                                mrp.id as mpid,
	                                pp.id as p_id,
	                                pt.name as product,
	                                sum(sm.product_qty) as built_qty,
	                                (select coalesce(sum(stm.product_qty), 0.00) as unbuilt_qty 
	                                    from stock_move stm
	                                    left join mrp_unbuild ub on (ub.id = stm.unbuild_id) 
	                                    where ub.mo_id = mrp.id and stm.product_id = pp.id),
	                                sum((sm.price_unit * sm.product_qty)) as built_cost,
	                                coalesce((select sum((sq.qty * sq.cost)) 
	                                 from stock_quant_move_rel sqm
	                                 left join stock_quant sq on (sq.id = sqm.quant_id)
	                                 left join stock_move stm on (stm.id = sqm.move_id)
	                                 left join mrp_unbuild mpu on (mpu.id = stm.unbuild_id)
	                                 where mpu.mo_id = mrp.id and stm.product_id = pp.id), 0.00) as unbuilt_cost,	                                
	                                sum((sm.price_unit * sm.product_qty))/ sum(mrp.product_qty) as unit_cost
                                from stock_move sm 
                                left join mrp_production mrp on (sm.raw_material_production_id = mrp.id)
                                left join product_product pp on (pp.id = sm.product_id)
                                left join product_template pt on (pt.id = pp.product_tmpl_id)
                                where (((mrp.date_start at time zone %s)::timestamp::date) between %s and %s) and sm.raw_material_production_id is not null and mrp.state = 'done' """ + product_sql + warehouse_sql + categ_sql + shift_type_sql +"""
                                group by
                                    mrp.id,
                                    pp.id,
                                    pt.name
                                order by p_type, pt.name))
                                 x 
                                group by
                                    x.p_type,
                                    x.product
                                order by
                                    x.p_type,
                                    x.product """
        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam' 
        self.env.cr.execute(manuf_order_sql , (tz, tz, date_from, date_to,))
        manuf_order_data = self.env.cr.dictfetchall()

        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
#        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4500
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 4500
        sheet1.col(5).width = 4500
        sheet1.col(6).width = 6500
        sheet1.col(7).width = 9000
        sheet1.col(8).width = 3000
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 4500
        sheet1.col(11).width = 4500
        sheet1.col(12).width = 4500
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 3000
        sheet1.col(16).width = 3000
        sheet1.col(17).width = 3000
        sheet1.col(18).width = 3000
        sheet1.col(19).width = 3000
        sheet1.col(20).width = 3000
        sheet1.col(21).width = 3000
        sheet1.col(22).width = 4500
        sheet1.col(23).width = 4500
        sheet1.col(24).width = 4500
    
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
        title3 = 'Finished Products'
        title4 = 'Raw Materials Consumed'
        sheet1.write_merge(r1, r1, 0, 24, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 24, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 16, title2, Style.subTitle())
        sheet1.write_merge(r3, r3, 17, 21, title3, Style.subTitle())
        sheet1.write_merge(r3, r3, 22, 24, "Unbuild", Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "MO No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Planned Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Source", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Responsible", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Planned Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Produced Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 11, "Pending Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 12, "Unbuild Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 13, "Total Produced Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 14, "Production Value", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 15, "Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 16, "Force Closed", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 17, "Production Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 18, "Shift", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 19, "Planned Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 20, "Produced Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 21, "Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 22, "Unbuild No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 23, "Unbuilt Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 24, "Unbuilt Quantity", Style.contentTextBold(r2,'black','white'))
        
        row = r4
        s_no = 0
        material_row = finished_row = 0.00
        inner_dict = {'built_qty': 0.00, 'built_cost': 0.00, 'unbuilt_qty': 0.00, 'unbuilt_cost': 0.00, 'total_qty': 0.00}
        summary_dict = {}
        for each in manuf_order_data:

            start_row = row + 1
            row = row + 1
            s_row = row
            s_no = s_no + 1
            product_str = each['product']
            product_data = json.loads(product_str.split('[] ')[-1])
            if each['product'] not in summary_dict:
                summary_dict[each['product']] = inner_dict
            summary_dict[each['product']]['built_qty'] += each['produced_qty'] or 0.00
            sheet1.row(row).height = 350
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['mo_no'], Style.normal_left())
            sheet1.write(row, 2, each['planned_date'], Style.normal_left())
            sheet1.write(row, 3, each['warehouse'], Style.normal_left())
            sheet1.write(row, 4, each['source'], Style.normal_left())
            sheet1.write(row, 5, each['responsible'], Style.normal_left())
            sheet1.write(row, 6, each['category'], Style.normal_left())
            sheet1.write(row, 7, product_data['en_US'], Style.normal_left())
            sheet1.write(row, 8, each['uom']['en_US'], Style.normal_left())
            sheet1.write(row, 9, each['planned_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 10, each['produced_qty'], Style.normal_num_right_3digits())
            produced_qty = each['produced_qty'] and each['produced_qty'] or 0.00
            sheet1.write(row, 11, each['pending_qty'], Style.normal_num_right_3digits())
            # sheet1.write(row, 12, each['bom'], Style.normal_left())
            sheet1.write(row, 15, each['state'], Style.normal_left())
            sheet1.write(row, 16, each['force_closed'], Style.normal_left())
            
            self.env.cr.execute(raw_material_sql , (each['mrp_id'],))
            raw_material_data = self.env.cr.dictfetchall()
#            total_production = 0.00
#            for raw_line in raw_material_data:
#                total_production += raw_line['raw_material']
                
            self.env.cr.execute(finished_products_sql , (tz, each['mrp_id'], each['product_id'],))
            finished_products_data = self.env.cr.dictfetchall()
            ub_data = unbuild_obj.search([('mo_id', '=', each['mrp_id']), ('state', '!=', 'draft')])
            print('>>>>>>>>>>>ub_data>>>>>>>>>>', ub_data)
            ub_row = row
            inventory_value = 0.00
            if finished_products_data:
                for line in finished_products_data:
                    inventory_value += sum(x.inventory_value for x in move_obj.search([('id', '=', line['sm_id'])]).move_line_ids.quant_id)
                    print('>>>>>>>>>inventory_value>>>>>>>>>>>>>>',inventory_value)
                    sheet1.row(row).height = 350
                    sheet1.write(row, 17, line['production_date'], Style.normal_left())
                    sheet1.write(row, 18, line['shift'], Style.normal_left())
                    sheet1.write(row, 19, line['to_produce'], Style.normal_num_right_3digits())
                    sheet1.write(row, 20, line['quantity_done'], Style.normal_num_right_3digits())
                    sheet1.write(row, 21, line['state'], Style.normal_left())
                    row = row + 1
                row = row - 1
            summary_dict[each['product']]['built_cost'] += inventory_value
            ub_total, ub_value = 0.00, 0.00
            if ub_data:
                if len(ub_data) > 1:
                    fg_data = move_obj.search([('consume_unbuild_id', 'in', list(x.id for x in ub_data)), ('product_id', '=', each['product_id'])])
                    scrap_data = move_obj.search([('unbuild_id', 'in', list(x.id for x in ub_data)), ('product_id', '=', each['product_id'])])
                    print('>>>>>>>>>fg_data>>>>>>>>>>>iffff>>>',fg_data, scrap_data)
                else:
                    fg_data = move_obj.search([('consume_unbuild_id', '=', ub_data.id), ('product_id', '=', each['product_id'])])
                    scrap_data = move_obj.search([('unbuild_id', '=', ub_data.id), ('product_id', '=', each['product_id'])])
                    print('>>>>>>>>>fg_data>>>>>>>>>>>else>>>',fg_data, scrap_data)

                for ub in (fg_data and fg_data or scrap_data):
                    ub_value += sum(x.location_id.usage == 'production' and x.inventory_value or 0.00 for x in ub.quant_ids)
                    inventory_value -= ub_value
                    # sheet1.write(ub_row, 22, (ub.consume_unbuild_id and ub.consume_unbuild_id.name or (ub.unbuild_id and ub.unbuild_id.name or False)), Style.normal_left())
                    date = ub.consume_unbuild_id and ub.consume_unbuild_id.write_date or (ub.unbuild_id and ub.unbuild_id.write_date or False)
                    date_str = date.strftime('%Y-%m-%d %H:%M:%S')
                    date = time.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    date = time.strftime('%d-%m-%Y', date)
                    sheet1.write(ub_row, 23, date, Style.normal_left())
                    sheet1.write(ub_row, 24, ub.product_qty, Style.normal_right())
                    ub_total += ub.product_qty
                    ub_row += 1
                if ub_row > row:
                    row = ub_row - 1
                
            summary_dict[each['product']]['unbuilt_qty'] += ub_total
            summary_dict[each['product']]['unbuilt_cost'] += ub_value
            sheet1.write(start_row, 12, ub_total, Style.normal_right())
            sheet1.write(start_row, 13, (produced_qty - ub_total), Style.normal_right())
            sheet1.write(s_row, 14, ((produced_qty - ub_total) and inventory_value or 0.00), Style.normal_num_right())
            summary_dict[each['product']]['total_qty'] = summary_dict[each['product']]['built_qty'] - summary_dict[each['product']]['unbuilt_qty']
        if self.date_from and self.date_to and self.summary:
#            sheet2 = wbk.add_sheet(summary_report_name)
#            sheet2.set_panes_frozen(True)
#            sheet2.set_horz_split_pos(4)
##            sheet2.show_grid = False 
#            sheet2.col(0).width = 2000
#            sheet2.col(1).width = 9000
#            sheet2.col(2).width = 3500
#            sheet2.col(3).width = 6000
#            sheet2.col(4).width = 3500
#            sheet2.col(5).width = 9000
#            sheet2.col(6).width = 3500
#            sheet2.col(7).width = 4500
#            sheet2.col(8).width = 9000
#            sheet2.col(9).width = 3000
#            sheet2.col(10).width = 4500
#            sheet2.col(11).width = 4500
#        
#            r1 = 0
#            r2 = 1
#            r3 = 2
#            r4 = 3
#            
#            sheet2.row(r1).height = 500
#            sheet2.row(r2).height = 400
#            sheet2.row(r3).height = 200 * 2
#            sheet2.row(r4).height = 256 * 3
#            title = summary_report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
#            title1 = self.company_id.name
#            title2 = 'Manufacturing Order Summary Report'  
#            title3 = 'Finished Products'
#            title4 = 'Raw Materials Consumed'
#            sheet2.write_merge(r1, r1, 0, 11, title1, Style.main_title())
#            sheet2.write_merge(r2, r2, 0, 11, title, Style.sub_main_title())
#            sheet2.write_merge(r3, r3, 0, 6, title2, Style.subTitle())
#            sheet2.write_merge(r3, r3, 7, 7, title3, Style.subTitle())
#            sheet2.write_merge(r3, r3, 8, 11, title4, Style.subTitle())
#            
#            sheet2.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 1, "Product", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 2, "UOM", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 4, "Planned Quantity", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 5, "BOM", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 6, "Responsible", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 7, "Produced Quantity", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 8, "Product", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 9, "UOM", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 10, "Planned Consumption Qty", Style.contentTextBold(r2,'black','white'))
#            sheet2.write(r4, 11, "Actual Consumed Qty", Style.contentTextBold(r2,'black','white'))
#            row = r4
#            s_no = 0
#            material_row = finished_row = 0.00
#            self.env.cr.execute(manuf_order_summary_sql , (tz, date_from, date_to,))
#            manuf_order_summary_data = self.env.cr.dictfetchall()
#            for each in manuf_order_summary_data:
#                start_row = row + 1
#                row = row + 1
#                s_no = s_no + 1
#                sheet2.row(row).height = 350
#                sheet2.write(row, 0, s_no, Style.normal_left())
#                sheet2.write(row, 1, each['product'], Style.normal_left())
#                sheet2.write(row, 2, each['uom'], Style.normal_left())
#                sheet2.write(row, 3, each['warehouse'], Style.normal_left())
#                sheet2.write(row, 4, each['planned_qty'], Style.normal_num_right_3digits())
#                sheet2.write(row, 5, each['bom'], Style.normal_left())
#                sheet2.write(row, 6, each['responsible'], Style.normal_left())
#                self.env.cr.execute(finished_products_summary_sql , (each['user_id'], each['product_id'], tz,date_from, date_to,))
#                finished_products_summary_data = self.env.cr.dictfetchall()
#                if finished_products_summary_data:
#                    for line in finished_products_summary_data:
#                        sheet2.row(row).height = 350
#                        sheet2.write(row, 7, line['quantity_done'], Style.normal_num_right_3digits())
#                        row = row + 1
#                        finished_row = row
#                self.env.cr.execute(raw_material_product_summary_sql , (each['user_id'], each['product_id'],  tz, date_from, date_to,))
#                raw_material_summary_data = self.env.cr.dictfetchall()
#                if raw_material_summary_data:
#                    for raw_line in raw_material_summary_data:
#                        sheet2.row(start_row).height = 350
#                        sheet2.write(start_row, 8, raw_line['product'], Style.normal_left())
#                        sheet2.write(start_row, 9, raw_line['uom'], Style.normal_left())
#                        sheet2.write(start_row, 10, raw_line['planned_consumption_qty'], Style.normal_num_right_3digits())
#                        sheet2.write(start_row, 11, raw_line['actual_consumed_qty'], Style.normal_num_right_3digits())
#                        start_row = start_row + 1
#                    row = start_row 
#                    material_row = row
#                if finished_row <= material_row:
#                    row = material_row - 1
#                else:
#                    row  = finished_row - 1
#                    
#            sheet3 = wbk.add_sheet(summary_product_report_name)
#            sheet1.set_panes_frozen(True)
#            sheet1.set_horz_split_pos(4)
##            sheet3.show_grid = False 
#            sheet3.col(0).width = 2000
#            sheet3.col(1).width = 9000
#            sheet3.col(2).width = 3000
#            sheet3.col(3).width = 3000
#            sheet3.col(4).width = 7500
#            sheet3.col(5).width = 9500
#            sheet3.col(6).width = 3000
#            sheet3.col(7).width = 3000
#            sheet3.col(8).width = 3000
#        
#            r1 = 0
#            r2 = 1
#            r3 = 2
#            r4 = 3
#            
#            sheet3.row(r1).height = 500
#            sheet3.row(r2).height = 400
#            sheet3.row(r3).height = 200 * 2
#            sheet3.row(r4).height = 256 * 3
#            title = summary_product_report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
#            title1 = self.company_id.name
#            title2 = 'Raw Material Summary Report'  
#            sheet3.write_merge(r1, r1, 0, 8, title1, Style.main_title())
#            sheet3.write_merge(r2, r2, 0, 8, title, Style.sub_main_title())
#            sheet3.write_merge(r3, r3, 0, 8, title2, Style.subTitle())
#            
#            sheet3.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 1, "Raw Material", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 2, "UOM", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 3, "Total Required Quantity", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 4, "Product Category", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 5, "Product", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 6, "Required Quantity", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 7, "MO.No", Style.contentTextBold(r2,'black','white'))
#            sheet3.write(r4, 8, "Status", Style.contentTextBold(r2,'black','white'))
#            row = r4
#            s_no = 0
#            material_row = finished_row = 0.00
#            self.env.cr.execute(raw_material_summary_report_sql , (tz, date_from, date_to,))
#            raw_material_summary_report_data = self.env.cr.dictfetchall()
#            for each in raw_material_summary_report_data:
#                row = row + 1
#                s_no = s_no + 1
#                sheet3.row(row).height = 350
#                sheet3.write(row, 0, s_no, Style.normal_left())
#                sheet3.write(row, 1, each['product'], Style.normal_left())
#                sheet3.write(row, 2, each['uom'], Style.normal_left())
#                sheet3.write(row, 3, each['planned_consumption_qty'], Style.normal_num_right_3digits())
#               
#                self.env.cr.execute(mo_product_sql , (each['id'], tz, date_from, date_to,))
#                mo_product_data = self.env.cr.dictfetchall()
#                if mo_product_data:
#                    for line in mo_product_data:
#                        sheet3.row(row).height = 350
#                        sheet3.write(row, 4, line['category'], Style.normal_left())
#                        sheet3.write(row, 5, line['product'], Style.normal_left())
#                        sheet3.write(row, 6, line['qty'], Style.normal_num_right_3digits())
#                        sheet3.write(row, 7, line['mo_no'], Style.normal_left())
#                        sheet3.write(row, 8, line['state'], Style.normal_left())
#                        row = row + 1
#                row = row - 1
            sheet4 = wbk.add_sheet("Summary")
            sheet4.set_panes_frozen(True)
            sheet4.set_horz_split_pos(4)
#            sheet4.show_grid = False 
            sheet4.col(0).width = 2000
            sheet4.col(1).width = 3000
            sheet4.col(2).width = 9000
            sheet4.col(3).width = 4500
            sheet4.col(4).width = 4500
            sheet4.col(5).width = 4500
            sheet4.col(6).width = 4500
            sheet4.col(7).width = 7500
        
            r1 = 0
            r2 = 1
            r3 = 2
            r4 = 3
            
            sheet4.row(r1).height = 500
            sheet4.row(r2).height = 400
            sheet4.row(r3).height = 200 * 2
            sheet4.row(r4).height = 256 * 3
            title = "Summary" +' ( Date From ' + from_date + ' To ' + to_date + ' )'
            title1 = self.company_id.name
            title2 = filters  
            sheet4.write_merge(r1, r1, 0, 7, title1, Style.main_title())
            sheet4.write_merge(r2, r2, 0, 7, title, Style.sub_main_title())
            sheet4.write_merge(r3, r3, 0, 7, title2, Style.subTitle())
            
            sheet4.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
            sheet4.write(r4, 1, "Type", Style.contentTextBold(r2,'black','white'))
            sheet4.write(r4, 2, "Product", Style.contentTextBold(r2,'black','white'))
            sheet4.write(r4, 3, "Built Qty", Style.contentTextBold(r2,'black','white'))
            sheet4.write(r4, 4, "Built Cost", Style.contentTextBold(r2,'black','white'))
            sheet4.write(r4, 5, "Unbuilt Qty", Style.contentTextBold(r2,'black','white'))
            sheet4.write(r4, 6, "Unbuilt Cost", Style.contentTextBold(r2,'black','white'))
            sheet4.write(r4, 7, "Total Built Qty", Style.contentTextBold(r2,'black','white'))
            row = r4
            s_no = 0
            self.env.cr.execute(built_summary_sql , (tz, date_from, date_to, tz, date_from, date_to,))
            summary_data = self.env.cr.dictfetchall()
            print('>>>>>>>>>>>>>>>>>>>summary_data>>>>>>>>>>>>>>',summary_data)
            for each in summary_data:
                row += 1
                s_no += 1
                sheet4.write(row, 0, s_no, Style.normal_left())
                sheet4.write(row, 1, each['p_type'], Style.normal_left())
                sheet4.write(row, 2, each['product']['en_US'], Style.normal_left())
                sheet4.write(row, 3, (each['bt_qty'] and round(each['bt_qty'], 2) or 0.00), Style.normal_right())
                sheet4.write(row, 4, (each['bt_cost'] and round(each['bt_cost'], 2) or 0.00), Style.normal_right())
                sheet4.write(row, 5, (each['ub_qty'] and round(each['ub_qty'], 2) or 0.00), Style.normal_right())
                sheet4.write(row, 6, (each['unb_cost'] and round(each['unb_cost'], 2) or 0.00), Style.normal_right())
                sheet4.write(row, 7, round(each['total_qty'], 2), Style.normal_right())
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'manufacturing.order.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
