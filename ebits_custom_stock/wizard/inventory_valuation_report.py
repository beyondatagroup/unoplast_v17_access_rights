# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

from datetime import datetime
import time
from pytz import timezone
from odoo import api, fields, models, _, tools
from odoo.tools.translate import _
from . import excel_styles
import xlwt
from io import BytesIO
import base64
import xlrd
from xlwt import *
from lxml import etree
import json
from odoo.addons import decimal_precision as dp

class InventoryValuationReportWizard(models.TransientModel):
    _name = 'inventory.valuation.report.wizard'
    _description = 'Inventory Valuation Report Wizard'
    
    choose_date = fields.Boolean('Inventory at Date')
    date = fields.Date('Date', default=fields.Date.context_today, required=True)
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today)
    summary = fields.Boolean(string='Summary', help="select this button to get a summary of inventory.")
    report_type = fields.Selection([('location', 'Location wise summary'),('product', 'Product wise summary')])
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    product_id = fields.Many2one('product.product', string='Product')
    view_location_id = fields.Many2one('stock.location', string='View Location')
    location_id = fields.Many2one('stock.location', string='Location')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    total_qty = fields.Float(string='Qty', readonly=True, digits=('Product Unit of Measure'))
    total_value = fields.Float(string='Inventory Value', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(InventoryValuationReportWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='warehouse_id']"):
                warehouse_id = []
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                node.set('domain', "[('id', 'in', " + str(warehouse_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res

    @api.onchange('summary')
    def onchange_summary(self):
        if not self.summary:
            self.report_type = False

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        warning = {}
        domain = {
            'location_id': [('usage', '=', 'internal')],
            'product_id': [('type', '=', 'product')]
            }
        if self.warehouse_id:
            self.view_location_id = self.warehouse_id.view_location_id and self.warehouse_id.view_location_id.id or False 
            domain = {
                'location_id': ['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')],
                'product_id': ['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')]
                }
        else:
            self.view_location_id = False
        return {'domain': domain}
    
    def get_inventory_value(self, mode=None, inventory_valuation_data = []):
        if not mode:
            mode = 'summary'
        quant_obj = self.env['stock.quant']
        if mode == 'normal':
            for inv in inventory_valuation_data:
                inv['inventory_value'] = quant_obj.browse(inv['id']).inventory_value
        else:
            for inv in inventory_valuation_data:
                inv_value = quant_obj.search_read([('product_id', '=', inv['product_id']), ('location_id', '=', inv['loc_id'])], ['inventory_value'])
                inv['inventory_value'] = sum(x['inventory_value'] for x in inv_value)
        return inventory_valuation_data
        
    def action_report(self):
        if self.choose_date:
            return self.action_report_with_date()
        else:
            return self.action_report_without_date()
        
    def action_report_without_date(self):
        report_name = "Inventory Valuation Report"
        # date = time.strptime(self.request_date, "%Y-%m-%d")
        date = self.date.strftime('%d-%m-%Y')
        filters = "Filter Based as on " + str(date) + " "
        product_domain, location_domain = "", ""
        warehouse_id, warehouse_list = [], []
        warehouse_sql, warehouse_str = "", ""
        location_obj = self.env['stock.location']
        product_obj = self.env['product.product']
        warehouse_obj = self.env['stock.warehouse']
        location_ids = []
        if self.warehouse_id:
            warehouse_id.append(self.warehouse_id.id)
            filters += " Warehouse : "+ str(self.warehouse_id.name)
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                    warehouse_list.append(each.name)
        if warehouse_list:
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            filters += " Warehouse : "+ warehouse_str
        
        if self.product_id:
            product_domain += " AND sq.product_id = " + str(self.product_id.id)
            filters += " Product : "+ str(self.product_id.name)
        else:
            if warehouse_id:
                product_search = product_obj.search(['|', ('stock_warehouse_ids', 'in', [ p for p in warehouse_id ]),('stock_warehouse_ids','=', False), ('type', '=', 'product')])
                product_ids = product_search.ids
                if product_ids and len(product_ids) > 1:
                    product_domain += " AND sq.product_id in " + str(tuple(product_ids))
                else:
                    product_domain += " AND sq.product_id = " + str(product_ids[0])
            else:
                product_search = product_obj.search([('type', '=', 'product')])
                product_ids = product_search.ids
                if product_ids and len(product_ids) > 1:
                    product_domain += " AND sq.product_id in " + str(tuple(product_ids))
                else:
                    product_domain += " AND sq.product_id = " + str(product_ids[0])
                
        if self.location_id:
            location_domain += " AND sq.location_id = " + str(self.location_id.id)
            filters += " Location : "+ str(self.location_id.name)
        else:
            location_ids = []
            if self.warehouse_id:
                location_search = location_obj.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
                location_ids = location_search.ids
                if location_ids:
                    if len(location_ids) > 1:
                        location_domain += " AND sq.location_id in " + str(tuple(location_ids))
                    else:
                        location_domain += " AND sq.location_id = " + str(location_ids[0])
            else:
                location_ids = []
                if warehouse_id:
                    for each_warehouse_id in warehouse_id:
                        warehouse_bro = warehouse_obj.browse(each_warehouse_id)
                        location_search = location_obj.search(['|', ('id', 'child_of', warehouse_bro.view_location_id.id), ('location_id', '=', warehouse_bro.view_location_id.id), ('usage', '=', 'internal')])
                        location_ids += location_search.ids
                else:
                    location_search = location_obj.search([('usage', '=', 'internal')])
                    location_ids += location_search.ids
                if location_ids:
                    if len(location_ids) > 1:
                        location_domain += " AND sq.location_id in " + str(tuple(location_ids))
                    else:
                        location_domain += " AND sq.location_id = " + str(location_ids[0])
        inventory_valuation_sql = """select 
                                        sq.id as id,
                                        pc.name as category,
	                                    concat((case when pt.default_code is not null then concat('[', pt.default_code,'] ') else '' end), pt.name->>'en_US') as product,
	                                    pu.name->>'en_US' as uom,
	                                    sq.quantity as quantity,
	                                    sl.id as loc_id,
	                                    sl.name as location,
                                        to_char(((sq.in_date at time zone %s)::timestamp), 'dd-mm-yyyy hh24:mi:ss') as date,
	                                    (sq.cost * sq.quantity) as inventory_value
                                    from stock_quant sq
	                                    left join product_product pp on (pp.id = sq.product_id)
	                                    left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                    left join product_category pc on (pc.id = pt.categ_id)
	                                    left join uom_uom pu on (pu.id = pt.uom_id)
	                                    left join stock_location sl on (sl.id = sq.location_id)
                                    where
	                                    ((sq.in_date at time zone %s)::timestamp::date) <= %s and sl.usage = 'internal' """+ product_domain + location_domain +""" group by sq.id,
	                                    pc.name,
	                                    concat((case when pt.default_code is not null then concat('[', pt.default_code,'] ') else '' end), pt.name->>'en_US'), 
	                                    pu.name->>'en_US', 
	                                    sl.id, 
	                                    sl.name,
	                                    sq.in_date,
	                                    sq.cost,
	                                    sq.quantity
                                    order by sq.in_date desc, sl.name """ 
	                                    
        summary_sql = """select 
                            x.loc_id as loc_id,
                            x.location as location,
                            x.category as category,
                            x.product as product,
                            x.product_id as product_id,
                            x.uom as uom,
                            sum(x.quantity) as quantity,
                            sum(x.inventory_value) as inventory_value 
                        from 
                        (select 
	                        sq.id as id,
	                            pc.name as category,
	                            concat((case when pt.default_code is not null then concat('[', pt.default_code,'] ') else '' end), pt.name->>'en_US') as product,
	                            pp.id as product_id,
	                            pu.name->>'en_US' as uom,
	                            sq.quantity as quantity,
	                            sl.id as loc_id,
	                            sl.name as location,
                                to_char(((sq.in_date at time zone %s)::timestamp), 'dd-mm-yyyy hh24:mi:ss') as date,
	                            (sq.cost * sq.quantity) as inventory_value
                            from stock_quant sq
	                            left join product_product pp on (pp.id = sq.product_id)
	                            left join product_template pt on (pt.id = pp.product_tmpl_id)
	                            left join product_category pc on (pc.id = pt.categ_id)
	                            left join uom_uom pu on (pu.id = pt.uom_id)
	                            left join stock_location sl on (sl.id = sq.location_id)
                            where
	                            ((sq.in_date at time zone %s)::timestamp::date) <= %s and sl.usage = 'internal' """+ product_domain + location_domain +"""
                             group by 
                                sq.id,
                                pc.name,
                                concat((case when pt.default_code is not null then concat('[', pt.default_code, '] ') else '' end), pt.name->>'en_US'), 
                                pp.id,
                                pt.name->>'en_US',
                                pu.name->>'en_US', 
                                sl.name, 
                                sl.id, 
                                sq.in_date,
                                sq.cost,
                                sq.quantity
                            order by sq.in_date desc, sl.name, pt.name->>'en_US') x 
                            group by
                                x.loc_id, 
                                x.location,
                                x.category,
                                x.product,
                                x.product_id,
                                x.uom"""
        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        if self.summary:
            if self.report_type == 'location':
                self.env.cr.execute(summary_sql + " order by x.location" , (tz, tz, self.request_date,))
                inventory_valuation_data = self.env.cr.dictfetchall()
                inventory_valuation_data  = self.get_inventory_value('summary', inventory_valuation_data)
                
            else:
                self.env.cr.execute(summary_sql + " order by x.product" , (tz, tz, self.request_date,))
                inventory_valuation_data = self.env.cr.dictfetchall()
                inventory_valuation_data  = self.get_inventory_value('summary', inventory_valuation_data)
        else:
            self.env.cr.execute(inventory_valuation_sql , (tz, tz, self.request_date,))
            inventory_valuation_data = self.env.cr.dictfetchall()
            inventory_valuation_data  = self.get_inventory_value('normal', inventory_valuation_data)
        
        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        #sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 9500
        sheet1.col(2).width = 9500
        sheet1.col(3).width = 9500
        sheet1.col(4).width = 8000
        sheet1.col(5).width = 3000
        sheet1.col(6).width = 5000
        sheet1.col(7).width = 3000
    
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 500
        sheet1.row(r1).height = 400
        sheet1.row(r2).height = 200 * 2
        sheet1.row(r3).height = 256 * 3
        title = report_name +' (As on Date ' + str(date) + ' )'
        title1 = self.company_id.name
        title2 = filters
        if self.summary:
            sheet1.write_merge(rc, rc, 0, 6, title1, Style.main_title())
            sheet1.write_merge(r1, r1, 0, 6, title, Style.sub_main_title())
            sheet1.write_merge(r2, r2, 0, 6, title2, Style.subTitle()) 
        else:
            sheet1.write_merge(rc, rc, 0, 7, title1, Style.main_title())
            sheet1.write_merge(r1, r1, 0, 7, title, Style.sub_main_title())
            sheet1.write_merge(r2, r2, 0, 7, title2, Style.subTitle())
        
        temp = ['product', 'location']
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, ((self.report_type == 'product' and self.summary) and "Product Category" or "Location"), Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, ((self.report_type == 'product' and self.summary) and "Product" or "Product Category"), Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, ((self.report_type == 'product' and self.summary) and "UOM" or "Product"), Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, ((self.report_type == 'product' and self.summary) and "Location" or "UOM"), Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, ((self.report_type in temp and self.summary) and "Inventory Value" or "Incoming Date"), Style.contentTextBold(r2,'black','white'))
        if not self.summary:
            sheet1.write(r3, 7, "Inventory Value", Style.contentTextBold(r2,'black','white'))
        row = r3
        s_no = 0
        qty = inv_value = 0.00
        sub_qty = sub_value = 0.00
        product = inventory_valuation_data and inventory_valuation_data[0]['product'] or ''
        location = inventory_valuation_data and ('loc_id' in inventory_valuation_data[0] and  inventory_valuation_data[0]['loc_id'] or '') or ''
        start = xlwt.Utils.rowcol_to_cell(row +1, 5)
        startv = xlwt.Utils.rowcol_to_cell(row +1, 6)
        print("\n\n\n\n\n=============inventory_valuation_data================",inventory_valuation_data)
        for each in inventory_valuation_data:
            row += 1
            s_no = s_no + 1
            sheet1.row(row).height = 300
            if self.summary:
                if self.report_type == 'location':
                    if location != each['loc_id']:
                        endv = xlwt.Utils.rowcol_to_cell(row-1,6)
                        sheet1.write(row, 6, Formula(('sum(' + str(startv) + ':' + str(endv) + ')')), Style.groupByTotal3digits())
                        if self.product_id:
                            end = xlwt.Utils.rowcol_to_cell(row-1,5)
                            sheet1.write(row, 5, Formula(('sum(' + str(start) + ':' + str(end) + ')')), Style.groupByTotal3separator())
                            start = xlwt.Utils.rowcol_to_cell(row +1, 5)
                        startv = xlwt.Utils.rowcol_to_cell(row +1, 6)
                        location = each['loc_id']
                        row += 1
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, ((self.report_type == 'product' and self.summary) and each['category'] or each['location']), Style.normal_left())
            sheet1.write(row, 2, ((self.report_type == 'product' and self.summary) and each['product'] or each['category']), Style.normal_left())
            sheet1.write(row, 3, ((self.report_type == 'product' and self.summary) and each['uom'] or each['product']), Style.normal_left())
            sheet1.write(row, 4, ((self.report_type == 'product' and self.summary) and each['location'] or each['uom']), Style.normal_left())
            sheet1.write(row, 5, each['quantity'], Style.normal_num_right_3digits())
            if self.report_type in temp and self.summary:
                sheet1.write(row, 6, each['inventory_value'], Style.normal_num_right_3separator())
            else:
                sheet1.write(row, 6, each['date'], Style.normal_left())
            if not self.summary:
                sheet1.write(row, 7, each['inventory_value'], Style.normal_num_right_3separator())

            qty += each['quantity'] or 0 
            inv_value += each['inventory_value']
        if self.summary:
            if self.report_type == 'product':
                end = xlwt.Utils.rowcol_to_cell(row,5)
                endv = xlwt.Utils.rowcol_to_cell(row,6)
                sheet1.write(row +1, 5, Formula(('sum(' + str(start) + ':' + str(end) + ')')), Style.groupByTotal3digits())
                sheet1.write(row +1, 6, Formula(('sum(' + str(startv) + ':' + str(endv) + ')')), Style.groupByTotal3separator())
                start = xlwt.Utils.rowcol_to_cell(row +2, 5)
                startv = xlwt.Utils.rowcol_to_cell(row +2, 6)
            else:
                endv = xlwt.Utils.rowcol_to_cell(row,6)
                sheet1.write(row +1, 6, Formula(('sum(' + str(startv) + ':' + str(endv) + ')')), Style.groupByTotal3digits())
                if self.product_id:
                    end = xlwt.Utils.rowcol_to_cell(row,5)
                    sheet1.write(row +1, 5, Formula(('sum(' + str(start) + ':' + str(end) + ')')), Style.groupByTotal3separator())
                    start = xlwt.Utils.rowcol_to_cell(row +2, 5)
                startv = xlwt.Utils.rowcol_to_cell(row +2, 6)
        if not self.product_id:
            row = row + 1
            if self.summary:
                sheet1.write_merge(row + 1, row + 1, 0, 4, 'Total Inventory Value', Style.groupByTitle())
                sheet1.write_merge(row + 1, row + 1, 5, 5, qty, Style.groupByTotal3digits())  # Add total qty here
                sheet1.write_merge(row + 1, row + 1, 6, 6, inv_value, Style.groupByTotal3separator())
            else:
                sheet1.write_merge(row, row, 0, 4, 'Total Inventory Value', Style.groupByTitle())
                sheet1.write_merge(row, row, 5, 5, qty, Style.groupByTotal3digits())
                sheet1.write_merge(row, row, 6, 6, '', Style.groupByTitle())
                sheet1.write_merge(row, row, 7, 7, inv_value, Style.groupByTotal3separator())
        else:
            row = row + 1
            if self.summary:
                sheet1.write_merge(row + 1, row + 1, 0, 4, 'Total', Style.groupByTitle())
                sheet1.write_merge(row + 1, row + 1, 5, 5, qty, Style.groupByTotal3digits())  # Add total qty here
                sheet1.write_merge(row + 1, row + 1, 6, 6, inv_value, Style.groupByTotal3separator())
            else:
                sheet1.write_merge(row, row, 0, 4, 'Total Quantity', Style.groupByTitle())
                sheet1.write_merge(row, row, 5, 5, qty, Style.groupByTotal3digits())  # Add total qty here
                sheet1.write_merge(row, row, 6, 6, 'Total Inventory Value', Style.groupByTitle())
                sheet1.write_merge(row, row, 7, 7, inv_value, Style.groupByTotal3separator())

            
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'inventory.valuation.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    def action_print_report_rml(self):
        total_qty, total_value = 0.00, 0.00
        product_domain, location_domain = "", ""
        warehouse_id = []
        location_obj = self.env['stock.location']
        product_obj = self.env['product.product']
        warehouse_obj = self.env['stock.warehouse']
        location_ids = []
        if self.warehouse_id:
            warehouse_id.append(self.warehouse_id.id)
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
        
        if self.product_id:
            product_domain += " AND sq.product_id = " + str(self.product_id.id)
        else:
            if warehouse_id:
                product_search = product_obj.search([ '|', ('stock_warehouse_ids', 'in', [ p for p in warehouse_id ]),('stock_warehouse_ids','=', False), ('type', '=', 'product')])
                
                product_ids = product_search.ids
                if product_ids and len(product_ids) > 1:
                    product_domain += " AND sq.product_id in " + str(tuple(product_ids))
                else:
                    product_domain += " AND sq.product_id = " + str(product_ids[0])
            else:
                product_search = product_obj.search([('type', '=', 'product')])
                product_ids = product_search.ids
                if product_ids and len(product_ids) > 1:
                    product_domain += " AND sq.product_id in " + str(tuple(product_ids))
                else:
                    product_domain += " AND sq.product_id = " + str(product_ids[0])
                
        
        if self.location_id:
            location_domain += " AND sq.location_id = " + str(self.location_id.id)
        else:
            if self.warehouse_id:
                location_search = location_obj.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
                location_ids = location_search.ids
                if location_ids:
                    if len(location_ids) > 1:
                        location_domain += " AND sq.location_id in " + str(tuple(location_ids))
                    else:
                        location_domain += " AND sq.location_id = " + str(location_ids[0])
            else:
                location_ids = []
                if warehouse_id:
                    for each_warehouse_id in warehouse_id:
                        warehouse_bro = warehouse_obj.browse(each_warehouse_id)
                    
                        location_search = location_obj.search(['|', ('id', 'child_of', warehouse_bro.view_location_id.id), ('location_id', '=', warehouse_bro.view_location_id.id), ('usage', '=', 'internal')])
                        location_ids += location_search.ids
                else:
                    location_search = location_obj.search([('usage', '=', 'internal')])
                    location_ids += location_search.ids
                if location_ids:
                    if len(location_ids) > 1:
                        location_domain += " AND sq.location_id in " + str(tuple(location_ids))
                    else:
                        location_domain += " AND sq.location_id = " + str(location_ids[0])
            
            
        inventory_valuation_sql = """select 
                sq.id as id,
                pc.name as category,
                concat((case when pt.default_code is not null then concat('[', pt.default_code,'] ') else '' end), pt.name->>'en_US') as product,
                pu.name->>'en_US' as uom,
                min(sq.quantity) as quantity,
                sl.name as location,
                sl.id as loc_id,
                to_char(((sq.in_date at time zone %s)::timestamp), 'dd-mm-yyyy hh24:mi:ss') as date,
                min(sq.cost * sq.quantity) as inventory_value
            from stock_quant sq
                left join product_product pp on (pp.id = sq.product_id)
                left join product_template pt on (pt.id = pp.product_tmpl_id)
                left join product_category pc on (pc.id = pt.categ_id)
                left join uom_uom pu on (pu.id = pt.uom_id)
                left join stock_location sl on (sl.id = sq.location_id)
            where
                ((sq.in_date at time zone %s)::timestamp::date) <= %s and sl.usage = 'internal'"""+ location_domain + product_domain +""" group by sq.id,
                pc.name,
                concat((case when pt.default_code is not null then concat('[', pt.default_code,'] ') else '' end), pt.name->>'en_US'), 
                pu.name->>'en_US', 
                sl.id, 
                sl.name,
                sq.in_date 
            order by sq.in_date desc, sl.name""" 
        
        summary_sql = """select 
                x.loc_id as loc_id,
                x.location as location,
                x.category as category,
                x.product as product,
                x.product_id as product_id,
                x.uom as uom,
                sum(x.quantity) as quantity,
                sum(x.inventory_value) as inventory_value 
            from 
            (select 
                    sq.id as id,
                    pc.name as category,
                    concat((case when pt.default_code is not null then concat('[', pt.default_code,'] ') else '' end), pt.name->>'en_US') as product,
                    pp.id as product_id,
                    pu.name->>'en_US' as uom,
                    sq.quantity as quantity,
                    sl.id as loc_id,
                    sl.name as location,
                    to_char(((sq.in_date at time zone %s)::timestamp), 'dd-mm-yyyy hh24-mi-ss') as date,
                    (sq.cost * sq.quantity) as inventory_value
                from stock_quant sq
                    left join product_product pp on (pp.id = sq.product_id)
                    left join product_template pt on (pt.id = pp.product_tmpl_id)
                    left join product_category pc on (pc.id = pt.categ_id)
                    left join uom_uom pu on (pu.id = pt.uom_id)
                    left join stock_location sl on (sl.id = sq.location_id)
                where
                    ((sq.in_date at time zone %s)::timestamp::date) <= %s and sl.usage = 'internal' """+ location_domain + product_domain +"""
                group by 
                    sq.id,
                    pc.name,
                    concat((case when pt.default_code is not null then concat('[', pt.default_code,'] ') else '' end), pt.name), 
                    pp.id, 
                    pt.name->>'en_US',
                    pu.name->>'en_US', 
                    sl.name, 
                    sl.id, 
                    sq.in_date
                order by sq.in_date desc, sl.name, concat((case when pt.default_code is not null then concat('[', pt.default_code,'] ') else '' end), pt.name)) x 
                group by
                    x.loc_id, 
                    x.location,
                    x.category,
                    x.product,
                    x.product_id,
                    x.uom"""
        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        if self.summary:
            inventory_valuation_data = []
            if self.report_type == 'location':
                self.env.cr.execute(summary_sql + " order by x.location" , (tz, tz, self.request_date,))
                summary_data = self.env.cr.dictfetchall()
                summary_data  = self.get_inventory_value('summary', summary_data)
            else:
                self.env.cr.execute(summary_sql + " order by x.product" , (tz, tz, self.request_date,))
                summary_data = self.env.cr.dictfetchall()
                summary_data  = self.get_inventory_value('summary', summary_data)
        else:
            self.env.cr.execute(inventory_valuation_sql , (tz, tz, self.request_date,))
            inventory_valuation_data = self.env.cr.dictfetchall()
            inventory_valuation_data = self.get_inventory_value('normal', inventory_valuation_data)
        
        if self.summary:
            qty, value = 0.00, 0.00
            if self.report_type == 'product':
                for rec in summary_data:
                    total_qty += rec['quantity']
                    total_value += rec['inventory_value']
                    inventory_valuation_data.append({
                        'category': rec['category'] and rec['category'] or ' ',
                        'product': rec['product'] and rec['product'] or ' ',
                        'uom': rec['uom'] and rec['uom'] or ' ',
                        'location': rec['location'] and rec['location'] or ' ',
                        'quantity': rec['quantity'] and rec['quantity'] or 0.00,
                        'date': ' ',
                        'inventory_value': rec['inventory_value'] and rec['inventory_value'] or  0.00,
                        })
                    
            else:
                loc_id = summary_data and summary_data[0]['loc_id'] or ''
                for rec in summary_data:
                    if rec['loc_id'] != loc_id:
                        inventory_valuation_data.append({
                            'category': ' ',
                            'product': ' ',
                            'uom': 'Total',
                            'location': ' ',
                            'quantity': self.product_id and qty or 0.00,
                            'date': ' ',
                            'inventory_value': value,
                            })
                        loc_id = rec['loc_id']
                        qty = 0.00
                        value = 0.00
                    qty += rec['quantity']
                    value += rec['inventory_value']
                    total_qty += rec['quantity']
                    total_value += rec['inventory_value']
                    inventory_valuation_data.append({
                        'category': rec['category'] and rec['category'] or ' ',
                        'product': rec['product'] and rec['product'] or ' ',
                        'uom': rec['uom'] and rec['uom'] or ' ',
                        'location': rec['location'] and rec['location'] or ' ',
                        'quantity': rec['quantity'] and rec['quantity'] or 0.00,
                        'date': ' ',
                        'inventory_value': rec['inventory_value'] and rec['inventory_value'] or  0.00 ,
                        })
                inventory_valuation_data.append({
                    'category': ' ',
                    'product': ' ',
                    'uom': 'Total',
                    'location': ' ',
                    'quantity': self.product_id and qty or 0.00,
                    'date': ' ',
                    'inventory_value': value,
                    })
        else:
            for rec in inventory_valuation_data:
                total_qty += rec['quantity']
                total_value += rec['inventory_value']
        self.total_qty = total_qty
        self.total_value = total_value
        return inventory_valuation_data
        
        
    def action_execute_history(self):
        product_domain = ""
        location_domain_in = ""
        location_domain_out = ""
        date_domain = ""
        order_by = ""
        warehouse_id, location_ids = [], []
        location_obj = self.env['stock.location']
        product_obj = self.env['product.product']
        warehouse_obj = self.env['stock.warehouse']
        if self.summary:
            if self.report_type == 'product':
                order_by += "ORDER BY product_id"
            else:
                order_by += "ORDER BY location_id"
        else:
            order_by += "ORDER BY location_id"
                
        if self.warehouse_id:
            warehouse_id.append(self.warehouse_id.id)
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
        if self.product_id:
            product_domain += " AND product_product.id = " + str(self.product_id.id)
        else:
            if warehouse_id:
                product_search = product_obj.search([ '|', ('stock_warehouse_ids', 'in', [ p for p in warehouse_id ]),('stock_warehouse_ids','=', False), ('type', '=', 'product')])
                product_ids = product_search.ids
                if product_ids and len(product_ids) > 1:
                    product_domain += " AND product_product.id in " + str(tuple(product_ids))
                else:
                    product_domain += " AND product_product.id = " + str(product_ids[0])
            else:
                product_search = product_obj.search([('type', '!=', 'service')])
                product_ids = product_search.ids
                if product_ids and len(product_ids) > 1:
                    product_domain += " AND product_product.id in " + str(tuple(product_ids))
                else:
                    product_domain += " AND product_product.id = " + str(product_ids[0])
                
        
        if self.location_id:
            location_domain_out += " AND source_location.id = " + str(self.location_id.id)
            location_domain_in += " AND dest_location.id = " + str(self.location_id.id)
        else:
            if self.warehouse_id:
                location_search = location_obj.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
                location_ids = location_search.ids
                if location_ids:
                    if len(location_ids) > 1:
                        location_domain_out += " AND source_location.id in " + str(tuple(location_ids))
                        location_domain_in += " AND dest_location.id in " + str(tuple(location_ids))
                    else:
                        location_domain_out += " AND source_location.id = " + str(location_ids[0])
                        location_domain_in += " AND dest_location.id = " + str(location_ids[0])
            else:
                location_ids = []
                if warehouse_id:
                    for each_warehouse_id in warehouse_id:
                        warehouse_bro = warehouse_obj.browse(each_warehouse_id)
                        location_search = location_obj.search(['|', ('id', 'child_of', warehouse_bro.view_location_id.id), ('location_id', '=', warehouse_bro.view_location_id.id), ('usage', '=', 'internal')])
                        location_ids += location_search.ids
                else:
                    location_search = location_obj.search([('usage', '=', 'internal')])
                    location_ids += location_search.ids
                if location_ids:
                    if len(location_ids) > 1:
                        location_domain_out += " AND source_location.id in " + str(tuple(location_ids))
                        location_domain_in += " AND dest_location.id in " + str(tuple(location_ids))
                    else:
                        location_domain_out += " AND source_location.id = " + str(location_ids[0])
                        location_domain_in += " AND dest_location.id = " + str(location_ids[0])
                    
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        
        if self.date:
            date_domain += " AND ((stock_move.date at time zone '" + str(tz) + "')::timestamp)::date <= '"+ str(self.date) + "'"
            
        sql = """
        SELECT 
            location_id,
            company_id,
            product_id,
            product_categ_id,
            product_template_id,
            SUM(quantity) as quantity,
            (case when SUM(quantity) != 0 then SUM(price_unit_on_quant * quantity) / SUM(quantity) else 0.00 end) as price_unit_on_quant,
            uom,
            category,
            product,
            location
        FROM
            ((SELECT
                stock_move.id AS id,
                stock_move.id AS move_id,
                dest_location.id AS location_id,
                dest_location.company_id AS company_id,
                stock_move.product_id AS product_id,
                product_template.id AS product_template_id,
                product_template.categ_id AS product_categ_id,
                quant.quantity AS quantity,
                to_char(((stock_move.date at time zone %s)::timestamp), 'dd-mm-yyyy hh24-mi-ss') as date,
                quant.cost as price_unit_on_quant,
                stock_move.origin AS source,
                pu.name->>'en_US' AS uom,
                categ.name As category,
                concat((case when product_template.default_code is not null then concat('[', product_template.default_code,'] ') else '' end), product_template.name->>'en_US') as product,
                dest_location.name AS location
            FROM
                stock_quant as quant
            JOIN
                stock_move ON stock_move.location_id = quant.location_id
            JOIN
                stock_location dest_location ON stock_move.location_dest_id = dest_location.id
            JOIN
                stock_location source_location ON stock_move.location_id = source_location.id
            JOIN
                product_product ON product_product.id = stock_move.product_id
            JOIN
                product_template ON product_template.id = product_product.product_tmpl_id
            JOIN 
                uom_uom pu on (pu.id = product_template.uom_id)
            JOIN 
                product_category categ on (categ.id = product_template.categ_id)
            WHERE quant.quantity > 0 AND stock_move.state = 'done' 
            AND source_location.id != dest_location.id
            """ + date_domain + location_domain_in + product_domain + """
            ) UNION ALL
            (SELECT
                (-1) * stock_move.id AS id,
                stock_move.id AS move_id,
                source_location.id AS location_id,
                source_location.company_id AS company_id,
                stock_move.product_id AS product_id,
                product_template.id AS product_template_id,
                product_template.categ_id AS product_categ_id,
                - quant.quantity AS quantity,
                to_char(((stock_move.date at time zone %s)::timestamp), 'dd-mm-yyyy hh24-mi-ss') as date,
                quant.cost as price_unit_on_quant,
                stock_move.origin AS source,
                pu.name->>'en_US' AS uom,
                categ.name As category,
                concat((case when product_template.default_code is not null then concat('[', product_template.default_code,'] ') else '' end), product_template.name->>'en_US') as product,
                source_location.name AS location
            FROM
                stock_quant as quant
            JOIN
                stock_move ON stock_move.location_id = quant.location_id
            JOIN
                stock_location source_location ON stock_move.location_id = source_location.id
            JOIN
                stock_location dest_location ON stock_move.location_dest_id = dest_location.id
            JOIN
                product_product ON product_product.id = stock_move.product_id
            JOIN
                product_template ON product_template.id = product_product.product_tmpl_id
            JOIN 
                uom_uom pu on (pu.id = product_template.uom_id)
            JOIN 
                product_category categ on (categ.id = product_template.categ_id)
            WHERE quant.quantity > 0 AND stock_move.state = 'done' 
            AND dest_location.id != source_location.id
            """ + date_domain + location_domain_out + product_domain + """
            ))
            AS foo
        GROUP BY location_id, location, company_id, product_id, product, product_categ_id, category, product_template_id, uom
        """ + order_by

        self.env.cr.execute(sql, (tz, tz))
        inventory_valuation_data = self.env.cr.dictfetchall()
        print("\n\n\n=======inventory_valuation_data=======",inventory_valuation_data)
        return inventory_valuation_data

        
        
    def action_print_report_date_rml(self):
        product_obj = self.env['product.product']
        data = self.action_execute_history()
        final_data = []
        total_qty, total_value = 0.00, 0.00
        for each in data:
            inventory_value = 0.00
            product_bro = product_obj.browse(each['product_id'])
            print("product_bro",product_bro.name,product_bro.cost_method)
            if product_bro.cost_method == 'real':
                inventory_value = each['quantity'] * each['price_unit_on_quant']
            # else:
            #     inventory_value = each['quantity'] * product_bro.get_history_price(self.company_id.id, date=self.date)
            # ####==========after solve*************************
            final_data.append({
                'category': each['category'] or ' ',
                'product': each['product'] or ' ',
                'uom': each['uom'] or ' ',
                'location': each['location'] or ' ',
                'loc_id': each['location_id'] or False,
                'quantity': each['quantity']or 0.00,
                'date':  '',
                'inventory_value': inventory_value or 0.00,
                })
            total_qty += each['quantity']
            total_value += inventory_value
        self.total_qty = total_qty
        self.total_value = total_value
        print("\n\n\n\n======func====final_data===============",final_data)
        return final_data
        
    def action_print_report_pdf(self):
        # self.ensure_one()
        # data = {}
        # data['ids'] = self.env.context.get('active_ids', [])
        # data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        # data['form'] = self.read(['product_id', 'location_id', 'warehouse_id','request_date', 'date'])[0]
        if self.choose_date:
            # return self.env['report'].get_action(self, 'inventory.valuation.date.rml.report', data=data)
            return self.env.ref(
            "ebits_custom_stock.report_inventory_valuation_date_action"
        ).report_action(self)
        else:
            return self.env.ref(
            "ebits_custom_stock.report_inventory_valuation_action"
        ).report_action(self)
        #     return self.env['report'].get_action(self, 'inventory.valuation.rml.report', data=data)
            
            
    def action_report_with_date(self):
        report_name = "Inventory Valuation Report"
        # date = time.strptime(self.date, "%Y-%m-%d")
        date = self.date.strftime("%d-%m-%Y")
        filters = "Filter Based as on " + str(date) + " "
        
        final_data = self.action_print_report_date_rml()
        print("\n\n\n\n=========final_data=============",final_data)
        
        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        #sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 9500
        sheet1.col(2).width = 9500
        sheet1.col(3).width = 9500
        sheet1.col(4).width = 8000
        sheet1.col(5).width = 3000
        sheet1.col(6).width = 5000
        sheet1.col(7).width = 3000
    
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 500
        sheet1.row(r1).height = 400
        sheet1.row(r2).height = 200 * 2
        sheet1.row(r3).height = 256 * 3
        title = report_name +' (As on Date ' + str(date) + ' )'
        title1 = self.company_id.name
        title2 = filters
        sheet1.write_merge(rc, rc, 0, 6, title1, Style.main_title())
        sheet1.write_merge(r1, r1, 0, 6, title, Style.sub_main_title())
        sheet1.write_merge(r2, r2, 0, 6, title2, Style.subTitle()) 
        
        temp = ['product', 'location']
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, ((self.report_type == 'product' and self.summary) and "Product Category" or "Location"), Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, ((self.report_type == 'product' and self.summary) and "Product" or "Product Category"), Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, ((self.report_type == 'product' and self.summary) and "UOM" or "Product"), Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, ((self.report_type == 'product' and self.summary) and "Location" or "UOM"), Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Inventory Value", Style.contentTextBold(r2,'black','white'))
        row = r3
        s_no = 0
        qty = inv_value = 0.00
        sub_qty = sub_value = 0.00
        print("\n\n\n\n\n======final_data===========",final_data)
        for each in final_data:
            row += 1
            s_no = s_no + 1
            sheet1.row(row).height = 300
                        
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, ((self.report_type == 'product' and self.summary) and each['category'] or each['location']), Style.normal_left())
            sheet1.write(row, 2, ((self.report_type == 'product' and self.summary) and each['product'] or each['category']), Style.normal_left())
            sheet1.write(row, 3, ((self.report_type == 'product' and self.summary) and each['uom'] or each['product']), Style.normal_left())
            sheet1.write(row, 4, ((self.report_type == 'product' and self.summary) and each['location'] or each['uom']), Style.normal_left())
            sheet1.write(row, 5, each['quantity'], Style.normal_num_right_3digits())
            sheet1.write(row, 6, each['inventory_value'], Style.normal_num_right_3separator())
            
            qty += each['quantity'] 
            inv_value += each['inventory_value']
        row += 1
        sheet1.write(row, 0, "", Style.normal_left())
        sheet1.write(row, 1, "", Style.normal_left())
        sheet1.write(row, 2, "", Style.normal_left())
        sheet1.write(row, 3, "", Style.normal_left())
        sheet1.write(row, 4, "", Style.normal_left())
        sheet1.write(row, 5, qty, Style.normal_num_right_3digits())
        sheet1.write(row, 6, "", Style.normal_left())
            
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'inventory.valuation.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                