# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from collections import OrderedDict
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_mrp.wizard.excel_styles import ExcelStyles
from odoo.exceptions import UserError, ValidationError
import xlwt
from xlwt import *
from io import StringIO
import base64
import xlrd
# import parser

class IpProcessReportWizard(models.TransientModel):
    _name = 'ip.process.report.wizard'
    _description = 'Ip Process Report Wizard'
    
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'ip_wiz_manuf_order_warehouse', 'manuf_order_wizard_id', 'warehouse_id', string='Warehouse')
    group_ids = fields.Many2many('labour.group', 'ip_process_report_group', 'ip_process_report_wizard_id', 'group_id', string='Group')
    labour_ids = fields.Many2many('labour.labour', 'ip_process_report_labour', 'ip_process_report_wizard_id', 'labour_id', string='Labour')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('ip.process.report.wizard'))
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(IpProcessReportWizard, self).fields_view_get(
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

    def action_report(self):
        if self.date_from > self.date_to:
            raise UserError(_('Invalid date range.Try using different values'))
        res = {}
        date_from = self.date_from
        date_to = self.date_to
        warehouse_sql = """ """
        group_sql = """ """
        categ_sql = """ """
        labour_sql = """ """
        state_sql = """ """
        labour_ids = []
        labour_list = []
        labour_str = ""
        group_ids = []
        group_list = []
        group_str = ""
        categ_ids = []
        categ_list = []
        categ_str = ""
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        filters = "Filtered Based On: Date"
        
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += " and production.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += " and production.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += " and production.warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += " and production.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                filters += ", Warehouse: " + warehouse_str
        
        if self.group_ids:
            for each_id in self.group_ids:
                group_ids.append(each_id.id)
                group_list.append(each_id.name)
                group_list = list(set(group_list))
                group_str = str(group_list).replace('[','').replace(']','').replace('u','').replace("'","")
            if len(group_ids) > 1:
                group_sql += " and lg.id in "+ str(tuple(group_ids))
            else:
                group_sql += " and lg.id in ("+ str(group_ids[0]) + ")"
            filters += " | Group: " + group_str
        
       
        if self.labour_ids:
            for each_id in self.labour_ids:
                labour_ids.append(each_id.id)
                labour_list.append(each_id.name)
                labour_list = list(set(labour_list))
                labour_str = str(labour_list).replace('[','').replace(']','').replace('u','').replace("'","")
            if len(labour_ids) > 1:
                labour_sql += " and line.labour_id in "+ str(tuple(labour_ids))
            else:
                labour_sql += " and line.labour_id in ("+ str(labour_ids[0]) + ")"
            filters += " | Labour: " + labour_str
        
        report_name = ""
        report_name = "Inter Process Production Register"
        sql = """select 
                     x.group, x.date, x.contractor, x.process, x.qty, x.rate, (x.rate * x.qty) as gross,
                     x.nssf, (((x.rate * x.qty)/100) * x.nssf) as deduct, 
                     ((x.rate * x.qty) - (((x.rate * x.qty)/100) * x.nssf)) as payable from  
                        (select
                             lg.name as Group,
                             lg.id,
                             to_char(production.date, 'dd-mm-yyyy') as date,
                             labour.name as Contractor,
                             resource.name as process,
                             sum(line.product_qty) as Qty,
                             (select rl.rate 
                              from labour_rate_line rl
                              where rl.group_id = lg.id and rl.date <= production.date
                              order by
                                  rl.date desc
                              LIMIT 1 ) as rate,
                             (select rl.nssf 
                              from labour_rate_line rl
                              where rl.group_id = lg.id and rl.date <= production.date
                              order by
                                  rl.date desc
                              LIMIT 1 ) as nssf
                         from production_line_detail line
                             left join inter_process_production production on (production.id = line.production_id)
                             left join labour_labour labour on (labour.id = line.labour_id)
                             left join labour_group lg on (lg.id = labour.group_id)
                             left join mrp_workcenter workcenter on (workcenter.id = line.process_id)
                             left join resource_resource resource on (resource.id = workcenter.resource_id)
                         where production.date >= %s and production.date <= %s  and production.state = 'done' """ + group_sql + labour_sql + warehouse_sql + """
                             group by
                                 lg.name,
                                 lg.id,
                                 labour.name,
                                 resource.name,
                                 production.date
                             order by
                                 lg.name) x 
                     """
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        self.env.cr.execute(sql , (date_from, date_to,))
        t = self.env.cr.dictfetchall()
        if len(t) == 0:
            raise UserError(_('No data available.Try using different values'))

        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 3500
        sheet1.col(5).width = 3500
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 3500
        sheet1.col(10).width = 3500
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 3500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500

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
        sheet1.write_merge(rc, rc, 0, 10, (self.company_id.name), Style.main_title())
        sheet1.write_merge(r1, r1, 0, 10, title, Style.sub_main_title())
        sheet1.write_merge(r2, r2, 0, 10, filters, Style.subTitle())
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 1, "Group", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 2, "Date", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 3, "Name of Contractor", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 4, "Process", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 5, "Qty", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 6, "Rate/Pc", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 7, "Gross Amount", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 8, "NSSF (%)", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 9, "Deduction Amount", Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write(r3, 10, "Net Payable", Style.contentTextBold(r3, 'black', 'white'))
        row = 3
        s_no = 0
        group = t[0]['group']
        start  = 4
        for each in t:
            row += 1
            sheet1.row(row).height = 450
            if group != each['group']:
                s_no += 1
                sheet1.write_merge(start, row-1, 0, 0, s_no, Style.normal_left())
                sheet1.write_merge(start, row-1, 1, 1, group, Style.normal_left())
                sheet1.write_merge(row, row, 0, 4, "TOTAL (TSH)", Style.groupByTitle())
                sheet1.write(row, 5, Formula(('sum(F%s:F%s)') %(start+1,row)), Style.groupByTotal())
                sheet1.write(row, 7, Formula(('sum(H%s:H%s)') %(start+1,row)), Style.groupByTotal3Separator())
                sheet1.write(row, 9, Formula(('sum(J%s:J%s)') %(start+1,row)), Style.groupByTotal3Separator())
                sheet1.write(row, 10, Formula(('sum(K%s:K%s)') %(start+1,row)), Style.groupByTotal3Separator())
                group = each['group']
                row += 1
                start = row
            sheet1.write(row, 2, each['date'], Style.normal_left())
            sheet1.write(row, 3, each['contractor'], Style.normal_left())
            sheet1.write(row, 4, each['process'], Style.normal_left())
            sheet1.write(row, 5, each['qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 6, each['rate'], Style.normal_num_right_3separator())
            sheet1.write(row, 7, each['gross'], Style.normal_num_right_3separator())
            sheet1.write(row, 8, each['nssf'], Style.normal_num_right_3separator())
            sheet1.write(row, 9, each['deduct'], Style.normal_num_right_3separator())
            sheet1.write(row, 10, each['payable'], Style.normal_num_right_3separator())
        sheet1.write_merge(start, row, 0, 0, s_no + 1, Style.normal_left())
        sheet1.write_merge(start, row, 1, 1, group, Style.normal_left())
        sheet1.write_merge(row+1, row+1, 0, 4, "TOTAL (TSH)", Style.groupByTitle())
        sheet1.write(row+1, 5, Formula(('sum(F%s:F%s)') %(start+1,row+1)), Style.groupByTotal3digits())
        sheet1.write(row+1, 7, Formula(('sum(H%s:H%s)') %(start+1,row+1)), Style.groupByTotal3Separator())
        sheet1.write(row+1, 9, Formula(('sum(J%s:J%s)') %(start+1,row+1)), Style.groupByTotal3Separator())
        sheet1.write(row+1, 10, Formula(('sum(K%s:K%s)') %(start+1,row+1)), Style.groupByTotal3Separator())
        sheet1.write_merge(row+5, row+5, 2, 3, 'APPROVED BY (Dir/F.C)', Style.contentTextBold(r3, 'black', 'white'))
        sheet1.write_merge(row+5, row+5, 9, 10, "SANCTIONED BY (Dept Head)", Style.contentTextBold(r3, 'black', 'white'))

        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.write({ 'name': report_name+'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'ip.process.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }

