# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_mrp.wizard.excel_styles import ExcelStyles
import xlwt
from io import StringIO
import base64
import xlrd
# import parser
from lxml import etree

class InterProcessProductionReportWizard(models.TransientModel):
    _name = 'inter.process.production.report.wizard'
    _description = 'Inter Process Production Report Wizard'
    
    date_from= fields.Date(string='From Date', required=True)
    date_to= fields.Date(string='To Date', required=True)
    product_ids = fields.Many2many('product.product', 'etc_ip_production_product', 'ip_production_wizard_id', 'product_id', string='Product')
    process_ids = fields.Many2many('mrp.workcenter', 'etc_ip_production_workcenter', 'ip_production_wizard_id', 'workcenter_id', string='Process')
    labour_ids = fields.Many2many('labour.labour', 'etc_ip_production_labour', 'ip_production_wizard_id', 'labour_id', string='Labour')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_ip_production_warehouse', 'ip_production_wizard_id', 'warehouse_id', string='Warehouse')
    categ_ids = fields.Many2many('product.category', 'etc_ip_production_category', 'ip_production_wizard_id', 'categ_id', string='Category')
    shift_type = fields.Selection([('shift_1', 'Shift 1'), ('shift_2', 'Shift 2'), ('shift_3', 'Shift 3')], string="Shift")
    summary = fields.Boolean(string='Summary')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(InterProcessProductionReportWizard, self).fields_view_get(
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
        report_name = "Inter Process Production Report"
        report_based_product = "Summary Based On Product"
        report_based_process = "Summary Based On Process"
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date)
        product_sql = """ """
        process_sql = """ """
        labour_sql = """ """
        warehouse_sql = """ """
        categ_sql = """ """
        shift_type_sql = """ """
        
        product_ids = []
        product_list = []
        product_str = ""
        
        process_ids = []
        process_list = []
        process_str = ""
        
        labour_ids = []
        labour_list = []
        labour_str = ""
        
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
                warehouse_sql += " and ipp.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += " and ipp.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += " and ipp.warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += " and ipp.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                filters += ", Warehouse: " + warehouse_str
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(product_ids) > 1:
                product_sql += " and pld.product_id in "+ str(tuple(product_ids))
            else:
                product_sql += " and pld.product_id in ("+ str(product_ids[0]) + ")"
            filters += ", Product: " + product_str
        if self.process_ids:
            for each_id in self.process_ids:
                process_ids.append(each_id.id)
                process_list.append(each_id.name)
            process_list = list(set(process_list))
            process_str = str(process_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(process_ids) > 1:
                process_sql += " and pld.process_id in "+ str(tuple(process_ids))
            else:
                process_sql += " and pld.process_id in ("+ str(process_ids[0]) + ")"
            filters += ", Process: " + process_str
        if self.labour_ids:
            for each_id in self.labour_ids:
                labour_ids.append(each_id.id)
                labour_list.append(each_id.name)
            labour_list = list(set(labour_list))
            labour_str = str(labour_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(labour_ids) > 1:
                labour_sql += " and pld.labour_id in "+ str(tuple(labour_ids))
            else:
                labour_sql += " and pld.labour_id in ("+ str(labour_ids[0]) + ")"
            filters += ", Process: " + labour_str
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
            shift_type_sql = " and ipp.shift_type = " + "'" + str(self.shift_type) + "'"
            if self.shift_type == 'shift_1':
                filters += ", Shift : Shift 1"
            if self.shift_type == 'shift_2':
                filters += ", Shift : Shift 2"
            if self.shift_type == 'shift_3':
                filters += ", Shift : Shift 3"
        ip_production_sql = """ select 
                                to_char(pld.date, 'dd-mm-yyy') as date,
                                sw.name as warehouse,
                                concat( '[' , pt.default_code, '] ', pt.name) as product,
                                pu.name as uom,
                                pc.name as category,
                                rr.name as process,
                                ll.name as labour,
                                pld.product_qty as quantity,
                                (case when ipp.shift_type = 'shift_1' then 'Shift 1'
                                 when ipp.shift_type = 'shift_2' then 'Shift 2'
                                 when ipp.shift_type = 'shift_3' then 'Shift 3' else ipp.shift_type end) as shift
                            from production_line_detail pld
                                left join inter_process_production ipp on (ipp.id = pld.production_id)
                                left join product_product pp on (pp.id = pld.product_id)
                                left join product_template pt on (pt.id = pp.product_tmpl_id)
                                left join product_uom pu on (pu.id = pt.uom_id)
                                left join product_category pc on (pc.id = pt.categ_id)
                                left join mrp_workcenter mrp on (mrp.id = pld.process_id)
                                left join resource_resource rr on (rr.id = mrp.resource_id)
                                left join labour_labour ll on (ll.id = pld.labour_id)
                                left join stock_warehouse sw on (sw.id = ipp.warehouse_id)
                            where (pld.date between %s and %s) and pld.state = 'done'""" + product_sql + process_sql + labour_sql + warehouse_sql + categ_sql + shift_type_sql + """ order by 
                                                    pld.date,
                                                    ipp.shift_type, 
                                                    pt.name, 
                                                    rr.name"""
        
        ip_produc_product_based_sql = """select 
	                                        concat( '[' , pt.default_code, '] ', pt.name) as product,
	                                        pu.name as uom,
	                                        to_char(pld.date, 'dd-mm-yyy') as production_date,
	                                        sw.name as warehouse,
	                                        rr.name as process,
	                                        ll.name as labour,
	                                        pld.product_qty as quantity
                                        from production_line_detail pld
	                                        left join inter_process_production ipp on (ipp.id = pld.production_id)
	                                        left join product_product pp on (pp.id = pld.product_id)
	                                        left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                        left join product_uom pu on (pu.id = pt.uom_id)
	                                        left join mrp_workcenter mrp on (mrp.id = pld.process_id)
	                                        left join resource_resource rr on (rr.id = mrp.resource_id)
	                                        left join labour_labour ll on (ll.id = pld.labour_id)
	                                        left join stock_warehouse sw on (sw.id = ipp.warehouse_id)
                                        where (pld.date between %s and %s) and pld.state = 'done'
                                            and pld.product_id = %s """ + warehouse_sql + """ order by pld.product_id asc"""
                                        
        product_based_sql = """ select 
	                                pld.product_id as product_id
                                from production_line_detail pld
	                                left join inter_process_production ipp on (ipp.id = pld.production_id)
	                                left join product_product pp on (pp.id = pld.product_id)
                                where (pld.date between %s and %s) and pld.state = 'done' """+ warehouse_sql + product_sql +""" group by pld.product_id 
                                order by pld.product_id asc"""
                                
        ip_produc_process_based_sql = """select 
	                                        rr.name as process,
	                                        sw.name as warehouse,
	                                        ll.name as labour,
	                                        pld.production_id as product,
	                                        to_char(pld.date, 'dd-mm-yyy') as production_date,
	                                        concat( '[' , pt.default_code, '] ', pt.name) as product,
	                                        pu.name as uom,
	                                        pld.product_qty as quantity
                                        from production_line_detail pld
	                                        left join inter_process_production ipp on (ipp.id = pld.production_id)
	                                        left join product_product pp on (pp.id = pld.product_id)
	                                        left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                        left join product_uom pu on (pu.id = pt.uom_id)
	                                        left join mrp_workcenter mrp on (mrp.id = pld.process_id)
	                                        left join resource_resource rr on (rr.id = mrp.resource_id)
	                                        left join labour_labour ll on (ll.id = pld.labour_id)
	                                        left join stock_warehouse sw on (sw.id = ipp.warehouse_id)
                                        where pld.state = 'done' and (pld.date between %s and %s)
                                        and pld.process_id = %s """ + warehouse_sql + """ order by pld.process_id asc, ll.name, pld.date""" 
                                        
        process_based_sql = """ select 
	                                pld.process_id as process_id
                                from production_line_detail pld
	                                left join inter_process_production ipp on (ipp.id = pld.production_id)
	                                left join mrp_workcenter mrp on (mrp.id = pld.process_id)
                                where (pld.date between %s and %s) and pld.state = 'done' """+ warehouse_sql + process_sql +""" group by pld.process_id 
                                order by pld.process_id asc"""
        
        self.env.cr.execute(ip_production_sql , (date_from, date_to,))
        ip_production_data = self.env.cr.dictfetchall()
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 4000
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 5500
        sheet1.col(5).width = 4500
        sheet1.col(6).width = 3500
    
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
        sheet1.write_merge(r1, r1, 0, 9, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 9, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 9, title2, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Shift", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Process", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Labour", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Quantity", Style.contentTextBold(r2,'black','white'))
        
        row = r4
        s_no = 0
        total_qty = 0.00
        for each in ip_production_data:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 350
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['date'], Style.normal_left())
            sheet1.write(row, 2, each['shift'], Style.normal_left())
            sheet1.write(row, 3, each['warehouse'], Style.normal_left())
            sheet1.write(row, 4, each['process'], Style.normal_left())
            sheet1.write(row, 5, each['labour'], Style.normal_left())
            sheet1.write(row, 6, each['quantity'], Style.normal_num_right_3digits())
            total_qty += each['quantity']
                    
        if self.product_ids:
            row = row + 1    
            sheet1.write_merge(row, row, 0, 8, 'Total', Style.groupByTitle()) 
            sheet1.write_merge(row, row, 9, 9, total_qty, Style.groupByTotal3digits()) 

        if self.date_from and self.date_to and self.summary:
            sheet2 = wbk.add_sheet(report_based_product)
            sheet2.show_grid = False 
            sheet2.col(0).width = 2000
            sheet2.col(1).width = 6500
            sheet2.col(2).width = 4000
            sheet2.col(3).width = 4000
            sheet2.col(4).width = 5000
            sheet2.col(5).width = 5000
            sheet2.col(6).width = 4000
            sheet2.col(7).width = 4000
            
            r1 = 0
            r2 = 1
            r3 = 2
            r4 = 3
            
            sheet2.row(r1).height = 500
            sheet2.row(r2).height = 400
            sheet2.row(r3).height = 200 * 2
            sheet2.row(r4).height = 256 * 3
            title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
            title1 = self.company_id.name
            sheet2.write_merge(r1, r1, 0, 7, title1, Style.main_title())
            sheet2.write_merge(r2, r2, 0, 7, title, Style.sub_main_title())
            sheet2.write_merge(r3, r3, 0, 7, report_based_product, Style.subTitle())
            
            sheet2.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 1, "Product", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 2, "UOM", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 3, "Date", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 4, "Warehouse", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 5, "Process", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 6, "Labour", Style.contentTextBold(r2,'black','white'))
            sheet2.write(r4, 7, "Qty", Style.contentTextBold(r2,'black','white'))
            
            row = r4
            s_no = 0
            
            self.env.cr.execute(product_based_sql, (date_from, date_to,))
            product_based_data = self.env.cr.dictfetchall()
            
            for line in product_based_data:
                self.env.cr.execute(ip_produc_product_based_sql , (date_from, date_to, line['product_id'],))
                ip_produc_product_based_data = self.env.cr.dictfetchall()
                for each_line in ip_produc_product_based_data:
                    row = row + 1
                    s_no = s_no + 1
                    sheet2.row(row).height = 300
                    sheet2.write(row, 0, s_no, Style.normal_left())
                    sheet2.write(row, 1, each_line['product'], Style.normal_left())
                    sheet2.write(row, 2, each_line['uom'], Style.normal_left())
                    sheet2.write(row, 3, each_line['production_date'], Style.normal_left())
                    sheet2.write(row, 4, each_line['warehouse'], Style.normal_left())
                    sheet2.write(row, 5, each_line['process'], Style.normal_left())
                    sheet2.write(row, 6, each_line['labour'], Style.normal_left())
                    sheet2.write(row, 7, each_line['quantity'], Style.normal_num_right_3digits())
                
            sheet3 = wbk.add_sheet(report_based_process)
            sheet3.show_grid = False 
            sheet3.col(0).width = 2000
            sheet3.col(1).width = 6500
            sheet3.col(2).width = 5000
            sheet3.col(3).width = 4000
            sheet3.col(4).width = 5000
            sheet3.col(5).width = 6500
            sheet3.col(6).width = 4000
            sheet3.col(7).width = 4000
            
            r1 = 0
            r2 = 1
            r3 = 2
            r4 = 3
            sheet3.row(r1).height = 500
            sheet3.row(r2).height = 400
            sheet3.row(r3).height = 200 * 2
            sheet3.row(r4).height = 256 * 3
            title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
            title1 = self.company_id.name
            sheet3.write_merge(r1, r1, 0, 7, title1, Style.main_title())
            sheet3.write_merge(r2, r2, 0, 7, title, Style.sub_main_title())
            sheet3.write_merge(r3, r3, 0, 7, report_based_process, Style.subTitle())
            
            sheet3.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
            sheet3.write(r4, 1, "Process", Style.contentTextBold(r2,'black','white'))
            sheet3.write(r4, 2, "Warehouse", Style.contentTextBold(r2,'black','white'))
            sheet3.write(r4, 3, "Labour", Style.contentTextBold(r2,'black','white'))
            sheet3.write(r4, 4, "Date", Style.contentTextBold(r2,'black','white'))
            sheet3.write(r4, 5, "Product", Style.contentTextBold(r2,'black','white'))
            sheet3.write(r4, 6, "UOM", Style.contentTextBold(r2,'black','white'))
            sheet3.write(r4, 7, "Qty", Style.contentTextBold(r2,'black','white'))
            
            row = r4
            s_no = 0
            self.env.cr.execute(process_based_sql, (date_from, date_to,))
            process_based_data = self.env.cr.dictfetchall()
            for line in process_based_data:
                self.env.cr.execute(ip_produc_process_based_sql , (date_from, date_to,line['process_id'],))
                ip_produc_process_based_data = self.env.cr.dictfetchall()
                for each_line in ip_produc_process_based_data:
                    row = row + 1
                    s_no = s_no + 1
                    sheet3.row(row).height = 300
                    sheet3.write(row, 0, s_no, Style.normal_left())
                    sheet3.write(row, 1, each_line['process'], Style.normal_left())
                    sheet3.write(row, 2, each_line['warehouse'], Style.normal_left())
                    sheet3.write(row, 3, each_line['labour'], Style.normal_left())
                    sheet3.write(row, 4, each_line['production_date'], Style.normal_left())
                    sheet3.write(row, 5, each_line['product'], Style.normal_left())
                    sheet3.write(row, 6, each_line['uom'], Style.normal_left())
                    sheet3.write(row, 7, each_line['quantity'], Style.normal_num_right_3digits())
            
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.write({'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'inter.process.production.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
