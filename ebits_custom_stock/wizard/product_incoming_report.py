# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from . import excel_styles
import xlwt
from io import BytesIO
import base64
import xlrd

from lxml import etree

class ProductIncomingReportWizard(models.TransientModel):
    _name = 'product.incoming.report.wizard'
    _description = 'Product Incoming Report Wizard'
    
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_product_incoming_partner', 'product_incoming_wizard_id', 'partner_id', string='Supplier')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_product_incoming_warehouse', 'product_incoming_wizard_id', 'warehouse_id', string='Warehouse')
    product_ids = fields.Many2many('product.product', 'etc_product_incoming_product', 'product_incoming_wizard_id', 'product_id', string='Product')
    date_type = fields.Selection(
        [('expected_date', 'Expected Delivery Date'), 
        ('actual_date', 'Actual Date')
        ], string='Date Type', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(ProductIncomingReportWizard, self).fields_view_get(
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
        
    @api.onchange('date_type')
    def _onchange_date_type(self):
        if self.date_type:
            self.date_to = False
            self.date_from = False
        else:
            self.date_from = False
            self.date_to = False
        
    
    def action_report(self):
        from_date = self.date_from
        to_date = self.date_to
        # date_from = time.strptime(from_date,"%Y-%m-%d")
        date_from = from_date.strftime('%d-%m-%Y')
        # date_to = time.strptime(to_date,"%Y-%m-%d")
        date_to = to_date.strftime('%d-%m-%Y')
        report_name = "Product Incoming Status"
        filters = ""
        supplier_sql = """ """
        warehouse_sql = """ """
        product_sql = """ """
        status_sql = """ """
        date_sql = """ """
        
        all_partners_children = {}
        all_partner_ids = []
        partner_ids = []
        customer_list = []
        customer_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        product_ids = []
        product_list = []
        product_str = ""
        
        if self.date_type:
            if self.date_type == 'expected_date':
                date_sql += "and ((sm.date_expected at time zone 'Asia/Calcutta')::timestamp::date) >= " + "'" + str(self.date_from) + "'" + "and ((sm.date_expected at time zone 'Asia/Calcutta')::timestamp::date) <= " + "'" + str(self.date_to) + "'"
                status_sql = " and sm.state in ('waiting', 'confirmed', 'assigned')" 
                filters += " Expected Delivery Date From : "+ str(date_from) + ' To ' +  str(date_to)
            else:
                date_sql += "and ((sp.date_done at time zone 'Asia/Calcutta')::timestamp::date) >= " + "'" + str(self.date_from) + "'" + "and ((sp.date_done at time zone 'Asia/Calcutta')::timestamp::date) <= " + "'" + str(self.date_to) + "'" 
                status_sql = " and sm.state = 'done'" 
                filters += " Actual Delivery Date From : "+ str(date_from) + ' To ' +  str(date_to)
        else:
            status_sql = " and sm.state != 'cancel'" 
        if self.partner_ids:
            for each_id in self.partner_ids:
                partner_ids.append(each_id.id)
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id]
                customer_list.append(each_id.name)
            customer_list = list(set(customer_list))
            customer_str = str(customer_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                all_partner_ids = tuple(all_partner_ids)
                supplier_sql += " and sp.partner_id in "+ str(all_partner_ids)
            else:
                supplier_sql += " and sp.partner_id in ("+ str(all_partner_ids[0]) + ")"
            filters += ", Supplier: " + customer_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
        if warehouse_ids:
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and spt.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and spt.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(product_ids) > 1:
                product_sql += "and sm.product_id in "+ str(tuple(product_ids))
            else:
                product_sql += "and sm.product_id in ("+ str(product_ids[0]) + ")"
            filters += ", Product: " + product_str 
            
        incoming_sql = """select 
	                            sp.name as reference,
	                            rp.name as supplier,
	                            ((sm.date_expected at time zone 'Asia/Calcutta')::timestamp::date) as expected_date,
	                            ((sp.date_done at time zone 'Asia/Calcutta')::timestamp::date) as actual_date,
	                            sw.name as warehouse,
	                            sp.origin as po_order_no,
	                            sp.gate_entry_ref as gate_entry,
	                            sp.reference_no as reference_no,
	                            to_char(sp.reference_date, 'dd-mm-yyyy') as reference_date,
	                            sp.supplier_inv_no as sup_inv_no,
	                            to_char(sp.supplier_inv_date, 'dd-mm-yyyy') as sup_inv_date, 
	                            concat( '[' , pp.default_code, '] ', pt.name->>'en_US') as product,
	                            sm.product_id as product_id,
	                            pu.name->>'en_US' as uom,
	                            sm.product_uom_qty as quantity,
	                            (case when sm.state = 'assigned' then 'Available' 
	                             when sm.state = 'confirmed' then 'Waiting Availability' 
	                             when sm.state = 'waiting' then 'waiting Another Move' 
	                             when sm.state = 'done' then 'Done' else sm.state end) as status,
	                             sp.id as picking_id,
	                             (select sl.name from stock_move_line spo
		                            left join stock_location sl on (sl.id = spo.location_dest_id)
	                            where spo.picking_id = sp.id  and spo.product_id = sm.product_id) as location
                            from stock_move sm
	                            left join stock_picking sp on (sp.id = sm.picking_id)
	                            left join res_partner rp on (rp.id = sp.partner_id)
	                            left join stock_picking_type spt on (spt.id = sp.picking_type_id)
	                            left join stock_warehouse sw on (sw.id = spt.warehouse_id)
	                            left join product_product pp on (pp.id = sm.product_id)
	                            left join product_template pt on (pt.id = pp.product_tmpl_id)
	                            left join uom_uom pu on (pu.id = pt.uom_id)
                            where spt.code like 'incoming%' and sp.to_refund is not True """+ supplier_sql + warehouse_sql + product_sql + status_sql + date_sql + """group by sp.name,
                            	rp.name,
	                            sm.date_expected,
	                            sp.date_done,
	                            sw.name,
	                            sp.id,
	                            sm.product_id,
	                            sp.origin,
	                            pp.default_code,
	                            pt.name->>'en_US',
	                            pu.name->>'en_US',
	                            sm.state,
	                            sm.product_uom_qty,
	                            sp.gate_entry_ref,
	                            sp.reference_no,
	                            sp.reference_date,
	                            sp.supplier_inv_no,
	                            sp.supplier_inv_date 
                            order by sp.name, sm.date_expected"""
                                
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        # self.env.cr.execute(incoming_sql, (tz, tz, tz, tz))
        self.env.cr.execute(incoming_sql)
        product_data = self.env.cr.dictfetchall()
        print("\n\n\n\n=============supplier_sql + warehouse_sql + product_sql + status_sql + date_sql===============",supplier_sql + warehouse_sql + product_sql + status_sql + date_sql)
        print("\n\n\n\n==========product_data============",product_data)
        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 6000
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 7000
        sheet1.col(5).width = 7000
        sheet1.col(6).width = 6000
        sheet1.col(7).width = 4500
        sheet1.col(8).width = 4500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 4500
        sheet1.col(11).width = 4500
        sheet1.col(12).width = 12000
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 4500
        sheet1.col(15).width = 8500
        sheet1.col(16).width = 4500
    
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 500
        sheet1.row(r1).height = 400
        sheet1.row(r2).height = 200 * 2
        sheet1.row(r3).height = 256 * 3
        title = ""
        title1 = self.company_id.name
        title2 = filters
        if self.date_type:
            if self.date_type == 'expected_date':
                title = report_name +' ( Expected Delivery Date From ' + date_from + ' To ' +  date_to + ' )'
                sheet1.write_merge(rc, rc, 0, 16, title1, Style.main_title())
                sheet1.write_merge(r1, r1, 0, 16, title, Style.sub_main_title())
                sheet1.write_merge(r2, r2, 0, 16, title2, Style.subTitle_left())
            else:
                title = report_name +' ( Actual Delivery Date From ' + date_from + ' To ' +  date_to + ' )'
                sheet1.write_merge(rc, rc, 0, 16, title1, Style.main_title())
                sheet1.write_merge(r1, r1, 0, 16, title, Style.sub_main_title())
                sheet1.write_merge(r2, r2, 0, 16, title2, Style.subTitle_left())
        else:
            sheet1.write_merge(rc, rc, 0, 16, title1, Style.main_title())
            sheet1.write_merge(r1, r1, 0, 16, report_name, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Reference No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Expected Delivery Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Actual Delivery Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Supplier", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Gate Entry Reference", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "DC Reference No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "DC Reference Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Vendor Invoice No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Vendor Invoice Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Purchase order No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 13, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 14, "Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 15, "Destination Location", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 16 , "Status", Style.contentTextBold(r2,'black','white'))
        
        row = r3
        s_no = 0
        for each in product_data:
            row += 1
            s_no = s_no + 1
            sheet1.row(row).height = 300
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['reference'], Style.normal_left())
            expected_date = ""
            if each['expected_date']:
                # expected_date = time.strptime(each['expected_date'], "%Y-%m-%d")
                expected_date = each['expected_date'].strftime('%d-%m-%Y')
            sheet1.write(row, 2, expected_date, Style.normal_left())
            actual_date = ""
            if each['actual_date']:
                # actual_date = time.strptime(each['actual_date'], "%Y-%m-%d")
                actual_date = each['actual_date'].strftime('%d-%m-%Y')
            sheet1.write(row, 3, actual_date, Style.normal_left())
            sheet1.write(row, 4, each['supplier'], Style.normal_left())
            sheet1.write(row, 5, each['warehouse'], Style.normal_left())
            sheet1.write(row, 6, each['gate_entry'], Style.normal_left())
            sheet1.write(row, 7, each['reference_no'], Style.normal_left())
            sheet1.write(row, 8, each['reference_date'], Style.normal_left())
            sheet1.write(row, 9, each['sup_inv_no'], Style.normal_left())
            sheet1.write(row, 10, each['sup_inv_date'], Style.normal_left())
            sheet1.write(row, 11, each['po_order_no'], Style.normal_left())
            sheet1.write(row, 12, each['product'], Style.normal_left())
            sheet1.write(row, 13, each['uom'], Style.normal_left())
            sheet1.write(row, 14, each['quantity'], Style.normal_num_right_3digits())
            sheet1.write(row, 15, each['location'], Style.normal_left())
            sheet1.write(row, 16, each['status'], Style.normal_left())    

        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'product.incoming.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
# *********************************check tz error