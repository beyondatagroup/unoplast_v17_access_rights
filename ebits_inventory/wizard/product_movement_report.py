# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from . import excel_styles
from odoo.exceptions import UserError, ValidationError
import xlwt
from xlwt import * 
from io import BytesIO
import base64
import xlrd
import json
from lxml import etree

class ProductMovementReportWizard(models.TransientModel):
    _name = 'product.movement.report.wizard'
    _description = 'Product Movement Report Wizard'
    
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True)
    product_ids = fields.Many2many('product.product', 'product_movement_report_product', 'product_movement_report_wizard_id', 'product_id', string='Product')
    state = fields.Selection([
        ('draft', 'New'), 
        ('confirmed', 'Waiting Availability'),
        ('assigned', 'Available'), ('done', 'Done'), ('cancel', 'Cancelled')], string='Status')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('product.movement.report.wizard'))

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(ProductMovementReportWizard, self).fields_view_get(
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
        
    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        warning = {}
        domain = {}
        if self.warehouse_id:
            domain = {
                'product_id': [('stock_warehouse_ids', 'in', self.warehouse_id.id),('type', '!=', 'service')]
                }
        return {'domain': domain}
        
    def action_report(self):
        warehouse_obj = self.env['stock.warehouse']
        if self.date_from > self.date_to:
            raise UserError(_('Invalid date range.Try  Using Different Values'))
        res = {}
        date_from = self.date_from
        date_to = self.date_to
        sql = """ """
        warehouse_sql = """ """
        product_sql = """ """
        categ_sql = """ """
        default_location_sql = """ """
        source_location_sql = """ """
        destination_location_sql = """ """
        state_sql = """ """
        categ_ids = []
        categ_list = []
        categ_str = ""
        product_ids = []
        product_list = []
        product_str = ""
        source_location_ids = []
        source_location_list = []
        source_location_str = ""
        destination_location_ids = []
        destination_location_list = []
        destination_location_str = ""
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        filters = "Filtered Based On: Date"
        
        if self.warehouse_id:
            warehouse_sql += "and warehouse.id in "+ str(tuple(self.warehouse_id))
            filters += " | Warehouse: " + str(self.warehouse_id.name)
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                warehouse_id = []
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                    warehouse_list.append(each.name)
                if warehouse_id:
                    warehouse_list = list(set(warehouse_list))
                    warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                    if len(warehouse_id) > 1:
                        warehouse_id = tuple(warehouse_id)
                        warehouse_sql += " and warehouse.id in " + str(tuple(warehouse_id))
                    else:
                        warehouse_sql += " and warehouse.id = " + str(warehouse_id[0])
                    filters += " | Warehouse: " + warehouse_str
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
            filters += " | Product: " + product_str
        if self.state:
            state_sql = " and move.state = " + "'" + str(self.state) + "'"
            if self.state == 'draft':
                filters += ", Status : New"
            if self.state == 'confirmed':
                filters += ", Status : Waiting Availability"
            if self.state == 'assigned':
                filters += ", Status : Available"
            if self.state == 'done':
                filters += ", Status : Done"
            if self.state == 'cancel':
                filters += ", Status : Cancelled"
        location_search = self.env['stock.location'].search([('id', 'child_of', self.warehouse_id.view_location_id.id)])
        location_search = tuple(x.id for x in location_search)
        report_name = ""
        report_name = "Product Movement Report"
        
        sql = """select
                     move.id,
                     to_char((move.date at time zone %s)::timestamp::date, 'dd-mm-yyyy') as date,
                     warehouse.name as warehouse,
                     template.name->>'en_US' product,
                     categ.name category,
                     move.product_uom_qty as qty,
                     uom.name->>'en_US' as uom,
                     (case 
                         when move.price_unit is not null then (move.product_uom_qty * move.price_unit) else 0.00
                     end) as value,
                     loc.name as source_location,
                     loc_dest.name destination_location,
                     (case when move.state = 'draft' then 'New'
                      when move.state = 'waiting' then 'Waiting Another Move'
                      when move.state = 'confirmed' then 'Waiting Availability'
                      when move.state = 'assigned' then 'Available'
                      when move.state = 'done' then 'Done'
                      when move.state = 'cancel' then 'Cancelled' else move.state end) as status
                 from stock_move move 
                     left join stock_location loc on (loc.id = move.location_id)
                     left join stock_picking_type type on (type.id = move.picking_type_id)
                     left join stock_warehouse warehouse on (warehouse.id = %s)
                     left join stock_location loc_dest on (loc_dest.id = move.location_dest_id)
                     left join product_product product on (product.id = move.product_id)
                     left join product_template template on (template.id = product.product_tmpl_id)
                     left join uom_uom uom on (uom.id = template.uom_id)
                     left join product_category categ on (categ.id = template.categ_id)
                 where
                     (move.date at time zone %s)::timestamp::date >= %s 
                     and (move.date at time zone %s)::timestamp::date <= %s 
                     and (loc.id in %s or loc_dest.id in %s)""" + product_sql + state_sql + """
                 group by
                     move.id,
                     move.date,
                     warehouse.name,
                     template.name->>'en_US',
                     categ.name,
                     move.product_uom_qty,
                     uom.name->>'en_US',
                     loc.name,
                     loc_dest.name,
                     move.state,
                     move.price_unit
                 order by
                     move.date,
                     warehouse.name,
                     categ.name,
                     template.name->>'en_US'
                """
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(sql , ( tz, self.warehouse_id.id, tz, date_from, tz, date_to, location_search, location_search))
        t = self.env.cr.dictfetchall()
        print("\n\n\n\n\n==========t============",t)
        if len(t) == 0:
            raise UserError(_('No data available.Try using different values'))

        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3000
        sheet1.col(2).width = 6500
        sheet1.col(3).width = 6500
        sheet1.col(4).width = 7000
        sheet1.col(5).width = 3500
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 7000
        sheet1.col(9).width = 7000
        sheet1.col(10).width = 7000

        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        # date_from_title = time.strptime(date_from, "%Y-%m-%d")
        date_from_title = date_from.strftime('%d-%m-%Y')
        # date_to_title = time.strptime(date_to, "%Y-%m-%d")
        date_to_title = date_to.strftime('%d-%m-%Y')
        title = report_name +' ( From ' + date_from_title + ' To ' + date_to_title + ' )'
        sheet1.write_merge(rc, rc, 0, 10, (self.company_id.name), Style.title_ice_blue())
        sheet1.write_merge(r1, r1, 0, 10, title, Style.title_ice_blue())
        sheet1.write_merge(r2, r2, 0, 10, filters, Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 1, "Date", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 2, "Warehouse", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 3, "Product Category", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 4, "Product", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 5, "Quantity", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 6, "UOM", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 7, "Product Value", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 8, "Source Location", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 9, "Destination Location", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 10, "Status", Style.contentTextBold(2, 'black', 'white'))
        row = 3
        s_no = 0
        for each in t:
            s_no += 1
            row += 1
            sheet1.row(row).height = 450
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['date'], Style.normal_left())
            sheet1.write(row, 2, each['warehouse'], Style.normal_left())
            sheet1.write(row, 3, each['category'], Style.normal_left())
            sheet1.write(row, 4, each['product'], Style.normal_left())
            sheet1.write(row, 5, each['qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 6, each['uom'], Style.normal_left())
            sheet1.write(row, 7, each['value'], Style.normal_num_right_3separator())
            sheet1.write(row, 8, each['source_location'], Style.normal_left())
            sheet1.write(row, 9, each['destination_location'], Style.normal_left())
            sheet1.write(row, 10, each['status'], Style.normal_left())
        sheet1.write(row+1, 7, Formula(('sum(H5:H' + str(row+1) + ')')), Style.normal_right_ice_blue_num())
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'product.movement.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }


