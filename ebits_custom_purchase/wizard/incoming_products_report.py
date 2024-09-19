# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo.addons.ebits_custom_purchase.wizard.excel_styles import ExcelStyles

from odoo import api, fields, models, _
from odoo.tools.translate import _
# from excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
import xlwt
from xlwt import * 
from io import StringIO
import base64
import xlrd
# import parser
import json
from lxml import etree

class IncomingProductReportWizard(models.TransientModel):
    _name = 'incoming.product.report.wizard'
    _description = 'Incoming Product Report Wizard'
    
    warehouse_ids = fields.Many2many('stock.warehouse', 'incoming_product_report_warehouse_rel', 'incoming_report_wizard_id', 'warehouse_id', string='Warehouse', required=True)
    category_ids = fields.Many2many('product.category', 'incoming_product_report_categ_rel', 'incoming_report_wizard_id', 'categ_id', string='Product Category')
    product_ids = fields.Many2many('product.product', 'incoming_product_report_product_rel', 'incoming_report_wizard_id', 'product_id', string='Product')
    partner_ids = fields.Many2many('res.partner', 'incoming_product_report_partner_rel', 'incoming_report_wizard_id', 'partner_id', string='Supplier')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(IncomingProductReportWizard, self).fields_view_get(
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
    def action_report(self):
        current_date = fields.Date.context_today(self)
        report_name = "Incoming Products Ageing Analysis"
        filters = "Filtered Based on : "
              
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        warehouse_sql = """ """
        
        category_ids = []
        category_list = []
        category_str = ""
        category_sql = """ """
        
        product_ids = []
        product_list = []
        product_str = ""
        product_sql = """ """
        
        partner_ids = []
        partner_list = []
        partner_str = ""
        partner_sql = """ """
        
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += " and wh.id in " + str(tuple(warehouse_ids)) 
            else:
                warehouse_sql += " and wh.id in (" + str(warehouse_ids[0]) + ")"
            filters += " | Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += " and wh.id in " + str(tuple(warehouse_ids)) 
                else:
                    warehouse_sql += " and wh.id in (" + str(warehouse_ids[0]) + ")"
                filters += " | Warehouse : "+ warehouse_str
        if self.category_ids:
            for each_id in self.category_ids:
                category_ids.append(each_id.id)
                category_list.append(each_id.name)
            category_list = list(set(category_list))
            category_str = str(category_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(category_ids) > 1:
                category_sql += " and categ.id in " + str(tuple(category_ids))
            else:
                 category_sql += " and categ.id in (" + str(category_ids[0]) + ")"
            filters += " | Product Category: " + category_str
            
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(product_ids) > 1:
                product_sql += " and product.id in "+ str(tuple(product_ids))
            else:
                product_sql += " and product.id in ("+ str(product_ids[0]) + ")"
            filters += " | Product: " + product_str
            
        if self.partner_ids:
            for each_id in self.partner_ids:
                partner_ids.append(each_id.id)

                partner_list.append(each_id.name)
            partner_list = list(set(partner_list))
            partner_str = str(partner_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(partner_ids) > 1:
                partner_sql += " and partner.id in "+ str(tuple(partner_ids))
            else:
                partner_sql += " and partner.id in ("+ str(partner_ids[0]) + ")"
            filters += " | Supplier: " + partner_str  
        
        sql = """
                    select 
                        x.warehouse,
                        x.category,
                        x.product, 
                        x.uom,
                        x.supplier,
                        string_agg(x.source, ', ') as source,
                        sum(x.nd_qty) as no_due,
                        sum(x.zt_qty) as zt_qty,
                        sum(x.ts_qty) as ts_qty,
                        sum(x.sn_qty) as sn_qty,
                        sum(x.nto_qty) as nto_qty,
                        sum(x.ao_qty) as ao_qty
                    from  
                    (select
                        wh.name as warehouse,
                        categ.name as category,
                        product.name as product,
                        uom.name as uom,
                        partner.name as supplier,
                        move.origin as source,    
                        sum(move.product_uom_qty) all_qty,
                        ((move.date_expected at time zone %s)::timestamp::date) as date,
                        (select sum(move.product_uom_qty) 
	                     where (%s - (move.date_expected at time zone %s)::timestamp::date) < 0) as nd_qty,
                        (select sum(move.product_uom_qty) 
                             where (%s - (move.date_expected at time zone %s)::timestamp::date) between 0 and 30) as zt_qty,
                        (select sum(move.product_uom_qty) 
                             where (%s - (move.date_expected at time zone %s)::timestamp::date)  between 31 and 60) as ts_qty,
                        (select sum(move.product_uom_qty) 
                             where (%s - (move.date_expected at time zone %s)::timestamp::date)  between 61 and 90) as sn_qty,
                        (select sum(move.product_uom_qty) 
                             where (%s - (move.date_expected at time zone %s)::timestamp::date)  between 91 and 120) as nto_qty,
                        (select sum(move.product_uom_qty) 
	                     where (%s - (move.date_expected at time zone %s)::timestamp::date) > 120) as ao_qty
                    from stock_move move
                        left join product_product pro on (pro.id = move.product_id)
                        left join product_template product on (product.id = pro.product_tmpl_id)
                        left join uom_uom uom on (uom.id = product.uom_id)
                        left join product_category categ on (categ.id = product.categ_id)
                        left join stock_picking_type spt on (spt.id = move.picking_type_id)
                        left join stock_warehouse wh on (wh.id = spt.warehouse_id)
                        left join stock_picking picking on (picking.id = move.picking_id)
                        left join res_partner partner on (partner.id = picking.partner_id)
                    where move.state in ('draft','confirmed','assigned') and spt.code = 'incoming' """ + category_sql + warehouse_sql + product_sql + partner_sql +"""
                    group by
                        wh.name,
                        categ.name,
                        product.name,
                        uom.name,
                        move.date_expected,
                        partner.name,
                        move.origin
                    order by
                        wh.name,
                        categ.name,
                        product,
                        date) x
                    group by
                        x.warehouse,
                        x.category,
                        x.product,
                        x.uom,
                        x.supplier
                    order by
                        x.warehouse,
                        x.category,
                        x.product """
        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(sql, (tz,current_date,tz,current_date,tz,current_date,tz,current_date,tz,current_date,tz,current_date,tz,))                
        data = self.env.cr.dictfetchall()
        if len(data) == 0:
            raise UserError(_("No records available.Try using different Inputs"))        
        # Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 7000
        sheet1.col(2).width = 6000
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 6000
        sheet1.col(5).width = 8500
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 3000
    
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 500
        sheet1.row(r1).height = 400
        sheet1.row(r2).height = 200 * 2
        sheet1.row(r3).height = 256 * 3
        title = report_name
        title1 = self.company_id.name
        title2 = filters 
        sheet1.write_merge(rc, rc, 0, 13, title1, Style.main_title())
        sheet1.write_merge(r1, r1, 0, 13, title, Style.sub_main_title())
        sheet1.write_merge(r2, r2, 0, 13, title2, Style.subTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Supplier", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Source", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "No Due", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "0-30", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "31-60", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "61-90", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "91-120", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "+120", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 13, "Total", Style.contentTextBold(r2,'black','white'))
        
        row = r3
        s_no = 0
        for each in data:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 600
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['warehouse'], Style.normal_left())
            sheet1.write(row, 2, each['supplier'], Style.normal_left())
            sheet1.write(row, 3, each['source'], Style.normal_left())
            sheet1.write(row, 4, each['category'], Style.normal_left())
            sheet1.write(row, 5, each['product'], Style.normal_left())
            sheet1.write(row, 6, each['uom'], Style.normal_left())
            sheet1.write(row, 7, each['no_due'], Style.normal_num_right_3digits())
            sheet1.write(row, 8, each['zt_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 9, each['ts_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 10, each['sn_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 11, each['nto_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 12, each['ao_qty'], Style.normal_num_right_3digits())
            
            start = xlwt.Utils.rowcol_to_cell(row, 6)
            end = xlwt.Utils.rowcol_to_cell(row, 12)
            
            sheet1.write(row, 13, Formula(('sum(' + str(start) + ':' + str(end) + ')')), Style.normal_num_right_3digits())
            
        if data and self.category_ids:
            sheet1.write_merge(row+1, row+1, 0, 6, 'Total', Style.normal_right_ice_blue())
            for i in range(7,13):
                start_v = xlwt.Utils.rowcol_to_cell(7, i)
                end_v = xlwt.Utils.rowcol_to_cell(row, i)
                sheet1.write(row+1, i, Formula(('sum(' + str(start_v) + ':' + str(end_v) + ')')), Style.normal_num_right_3digits())

        stream = StringIO()
        wbk.save(stream)

        self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'incoming.product.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
