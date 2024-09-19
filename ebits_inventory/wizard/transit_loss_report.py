# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
import xlwt
import cStringIO
import base64
import xlrd
import parser
import json
from lxml import etree

class TransitLossReportWizard(models.TransientModel):
    _name = 'transit.loss.report.wizard'
    _description = 'Transit Loss Report Wizard'
    
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'transit_loss_report_warehouse', 'transit_loss_report_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'transit_loss_report_product', 'transit_loss_report_wizard_id', 'product_id', string='Product')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('transit.loss.report.wizard'))

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(TransitLossReportWizard, self).fields_view_get(
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
        
    @api.multi
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
        product_ids = []
        product_list = []
        product_str = ""
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        filters = "Filtered Based On: Issue Date"
        
        if self.warehouse_ids:
            warehouse_search = self.env['stock.warehouse'].search([('id', 'in', tuple(x.id for x in self.warehouse_ids))])
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            filters += " | Warehouse: " + warehouse_str
        else:
            warehouse_search = self.env['stock.warehouse'].search([])
       
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
        report_name = ""
        report_name = "Transit Loss Report"
        sql = """select
                     %s as warehouse,
                     sw.name as receive_warehouse,
                     sp.name as picking,
                     istr.id as id,
                     istr.force_closed_reason as reason,
                     to_char(((move.date at time zone %s)::timestamp::date), 'dd-mm-yyyy') as date,
                     isti.name as issue_no,
                     istrq.name as request_no,
                     template.name as product,
                     categ.name as category,
                     uom.name as uom,
                     sum(move.product_uom_qty) as qty,
                     sum(case when move.price_unit is not null then (move.product_uom_qty * move.price_unit) else 0.00
                     end) as sale_value,
                     loc.name as source_location,
                     loc_dest.name as destination_location
                 from
                     stock_move move
                     left join stock_location loc on (loc.id = move.location_id)
                     left join stock_location loc_dest on (loc_dest.id = move.location_dest_id)
                     left join product_product product on (product.id = move.product_id)
                     left join product_template template on (template.id = product.product_tmpl_id)
                     left join product_category categ on (categ.id = template.categ_id)
                     left join product_uom uom on (uom.id = template.uom_id)
                     left join internal_stock_transfer_receipt istr on (istr.id = move.internal_stock_transfer_receipt_id)
                     left join stock_warehouse sw on (sw.id = istr.receiving_warehouse_id)
                     left join internal_stock_transfer_issue isti on (isti.id = istr.issue_id)
                     left join internal_stock_transfer_request istrq on (istrq.id = istr.request_id)
                     left join stock_picking sp on (sp.id = move.picking_id)
                 where
                     (move.date at time zone %s)::timestamp::date >= %s and (move.date at time zone %s)::timestamp::date <= %s and move.location_dest_id = %s and move.location_id = %s and move.picking_type_id = %s""" + warehouse_sql + product_sql + """
                 group by
                     warehouse,
                     template.name,
                     categ.name,
                     uom.name,
                     loc.name,
                     loc_dest.name,
                     isti.name,
                     istrq.name,
                     move.date,
                     sw.name,
                     sp.name,
                     istr.id,
                     istr.force_closed_reason 
                order by
                    istr.id desc,
                    warehouse,
                    template.name,
                    categ.name
                """
        records = []
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        for each in warehouse_search:
            self.env.cr.execute(sql , (str(each.name), tz, tz, date_from, tz, date_to, each.transit_loss_location_id.id, each.transit_location_id.id, each.int_type_id.id))
            temp = self.env.cr.dictfetchall()
            records = records + temp
        if len(records) == 0:
            raise UserError(_('No data available.Try using different values'))

        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 5500
        sheet1.col(3).width = 5500
        sheet1.col(4).width = 6500
        sheet1.col(5).width = 8500
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 7000
        sheet1.col(10).width = 7000
        sheet1.col(11).width = 4000
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 3500
        sheet1.col(14).width = 4000

        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        
        sheet1.row(rc).height = 700
        sheet1.row(r1).height = 700
        sheet1.row(r2).height = 700
        sheet1.row(r3).height = 256 * 3

        date_from_title = time.strptime(date_from, "%Y-%m-%d")
        date_from_title = time.strftime('%d-%m-%Y', date_from_title)
        date_to_title = time.strptime(date_to, "%Y-%m-%d")
        date_to_title = time.strftime('%d-%m-%Y', date_to_title)
        title = report_name +' ( From ' + date_from_title + ' To ' + date_to_title + ' )'
        sheet1.write_merge(rc, rc, 0, 14, (self.company_id.name), Style.title_ice_blue())
        sheet1.write_merge(r1, r1, 0, 14, title, Style.title_ice_blue())
        sheet1.write_merge(r2, r2, 0, 14, filters, Style.groupByTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 1, "Date", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 2, "Request/Receiving Warehouse", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 3, "Issuing Warehouse", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 4, "Product", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 5, "Product Category", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 6, "Quantity", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 7, "UOM", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 8, "Value", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 9, "Source Location", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 10, "Destination Location", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 11, "Reference", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 12, "Issue No", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 13, "Request No", Style.contentTextBold(2, 'black', 'white'))
        sheet1.write(r3, 14, "Reason", Style.contentTextBold(2, 'black', 'white'))
        row = 3
        s_no = 0
        sale_value_total = 0.00
        record = False
        for each in records:
            s_no += 1
            row += 1
            sheet1.row(row).height = 450

            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['date'], Style.normal_left())
            sheet1.write(row, 2, each['receive_warehouse'], Style.normal_left())
            sheet1.write(row, 3, each['warehouse'], Style.normal_left())
            sheet1.write(row, 4, each['product'], Style.normal_left())
            sheet1.write(row, 5, each['category'], Style.normal_left())
            sheet1.write(row, 6, each['qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 7, each['uom'], Style.normal_left())
            sheet1.write(row, 8, each['sale_value'], Style.normal_num_right_3separator())
            
            sale_value_total += each['sale_value']
            
            sheet1.write(row, 9, each['source_location'], Style.normal_left())
            sheet1.write(row, 10, each['destination_location'], Style.normal_left())
            sheet1.write(row, 11, each['picking'], Style.normal_left())
            sheet1.write(row, 12, each['issue_no'], Style.normal_left())
            sheet1.write(row, 13, each['request_no'], Style.normal_left())
            sheet1.write(row, 14, each['reason'], Style.normal_left())

        sheet1.write(row+1, 8, sale_value_total, Style.normal_right_ice_blue_num())
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.write({'name': report_name+ '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'transit.loss.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }

