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

class ProductDeliveryReportWizard(models.TransientModel):
    _name = 'product.delivery.report.wizard'
    _description = 'Product Delivery Report Wizard'
    
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_product_delivery_partner', 'product_delivery_wizard_id', 'partner_id', string='Customer')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_product_delivery_warehouse', 'product_delivery_wizard_id', 'warehouse_id', string='Warehouse')
    manager_ids = fields.Many2many('res.users', 'etc_product_delivery_users', 'product_delivery_wizard_id', 'user_id', string='Sales Manager')
    product_ids = fields.Many2many('product.product', 'etc_product_delivery_product', 'product_delivery_wizard_id', 'product_id', string='Product')
    date_type = fields.Selection(
        [('expected_date', 'Expected Delivery Date'), 
        ('actual_date', 'Actual Date')
        ], string='Date Type', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(ProductDeliveryReportWizard, self).fields_view_get(
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
        date_from = self.date_from.strftime('%d-%m-%Y')
        # date_to = time.strptime(to_date,"%Y-%m-%d")
        date_to = self.date_to.strftime('%d-%m-%Y')
        report_name = "Product Delivery Status"
        filters = ""
        customer_sql = """ """
        warehouse_sql = """ """
        manager_sql = """ """
        product_sql = """ """
        status_sql = """ """
        date_sql = """ """
        actual_date_sql = """ """
        
        all_partners_children = {}
        all_partner_ids = []
        partner_ids = []
        customer_list = []
        customer_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        manager_ids = []
        manager_list = []
        manager_str = ""
        
        product_ids = []
        product_list = []
        product_str = ""
        
        if self.date_type:
            if self.date_type == 'expected_date':
                date_sql += "and ((sm.date_expected at time zone %s)::timestamp::date) >= " + "'" + str(self.date_from) + "'" + "and ((sm.date_expected at time zone %s)::timestamp::date) <= " + "'" + str(self.date_to) + "'"
                status_sql = " and sm.state in ('waiting', 'confirmed', 'assigned')" 
                filters += " Expected Delivery Date From : "+ str(date_from) + ' To ' +  str(date_to)
            else:
                date_sql += "and ((sp.date_done at time zone %s)::timestamp::date) >= " + "'" + str(self.date_from) + "'" + "and ((sp.date_done at time zone %s)::timestamp::date) <= " + "'" + str(self.date_to) + "'" 
                status_sql = " and sm.state = 'done' "
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
                customer_sql += " and sp.partner_id in "+ str(all_partner_ids)
            else:
                customer_sql += " and sp.partner_id in ("+ str(all_partner_ids[0]) + ")"
            filters += ", Customer: " + customer_str
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
        if self.manager_ids:
            for each_id in self.manager_ids:
                manager_ids.append(each_id.id)
                manager_list.append(each_id.name)
            manager_list = list(set(manager_list))
            manager_str = str(manager_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(manager_ids) > 1:
                manager_sql += "and rp.sales_manager_id in "+ str(tuple(manager_ids))
            else:
                manager_sql += "and rp.sales_manager_id in ("+ str(manager_ids[0]) + ")"
            filters += ", Sales Manager: " + manager_str  
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
        print("\n\n\n\n\n===============+ customer_sql + warehouse_sql + manager_sql + product_sql + status_sql + date_sql +", customer_sql + warehouse_sql + manager_sql + product_sql + status_sql + date_sql )
        delivery_sql = """ select sp.name as reference,
                                ((sm.date_expected at time zone %s)::timestamp::date) as expected_date,
                                rp.name as customer,
                                concat((case when rp.street is not null then concat(rp.street, ', ') else '' end), 
	                                (case when rp.street2 is not null then concat(rp.street2, ', ') else '' end),
	                                (case when rp.city is not null then concat(rp.city, ', ') else '' end),
	                                (case when rsa.name->>'en_US' is not null then concat(rsa.name->>'en_US', ', ') else '' end),
	                                (case when rsr.name->>'en_US' is not null then concat(rsr.name->>'en_US', ', ') else '' end),
	                                (case when rp.zip is not null then concat(rp.zip, ', ') else '' end),
	                                (case when rc.name->>'en_US' is not null then concat(rc.name->>'en_US', '.') else '' end)) as address,
	                            sw.name as warehouse,
                                res.name as sales_manager,
                                so.name as sales_order_no,
                                ((so.date_order at time zone %s)::timestamp::date) as sales_order_date,
                                ((sp.date_done at time zone %s)::timestamp::date) as actual_date,
                                ((sp.approved_date at time zone %s)::timestamp::date) as approved_date,
                                concat( '[' , pp.default_code, '] ', pt.name->>'en_US') as product,
                                pu.name->>'en_US' as uom,
                                sum(sm.product_uom_qty) as quantity,
                                (case when sm.state = 'assigned' then 'Available' 
                                 when sm.state = 'confirmed' then 'Waiting Availability' 
                                 when sm.state = 'waiting' then 'waiting Another Move' 
                                 when sm.state = 'done' then 'Done' else sm.state end) as status,
                                 sp.driver_name as driver_name,
                                 sp.driver_phone as driver_phone,
                                 sp.driver_licence as licence_no,
                                 sp.driver_licence_type as licence_type,
                                 sp.driver_licence_place as licence_place,
                                 sp.vehicle_no as vehicle_no,
                                 sp.vehicle_owner as vehicle_owner,
                                 sp.vehicle_owner_address as owner_address,
                                 sp.agent_name as agent_name 	 
                            from stock_picking sp
                                left join stock_picking_type spt on (spt.id = sp.picking_type_id)
                                left join stock_warehouse sw on (sw.id = spt.warehouse_id)
                                left join stock_move sm on (sm.picking_id = sp.id)
                                left join product_product pp on (pp.id = sm.product_id)
                                left join product_template pt on (pt.id = pp.product_tmpl_id)
	                            left join sale_order so on (so.id = sp.sale_id)
	                            left join res_partner rp on (rp.id = so.partner_shipping_id)
	                            left join res_state_area rsa on (rsa.id = rp.area_id)
	                            left join res_state_region rsr on (rsr.id = rp.region_id)
	                            left join res_country rc on (rc.id = rp.country_id)
	                            left join res_users ru on (ru.id = rp.sales_manager_id)
	                            left join res_partner res on (res.id = ru.partner_id)
	                            left join uom_uom pu on (pu.id = pt.uom_id)
                            where
                                spt.code = 'outgoing' and sp.to_refund_po is not True """ + customer_sql + warehouse_sql + manager_sql + product_sql + status_sql + date_sql + """ group by
                                rp.name,          
                                sm.date_expected,            
                                sp.date_done,
                                sp.name,
                                pu.name->>'en_US',
                                address,
                                rp.street,
                                rp.street2,
                                rp.city,
                                rsa.name->>'en_US',
                                res.name,
                                rsr.name->>'en_US',
                                rp.zip,
                                sp.driver_name,
                                sp.driver_phone,
                                sp.driver_licence,
                                sp.driver_licence_type,
                                sp.driver_licence_place,
                                sp.vehicle_no,
                                sp.vehicle_owner,
                                sp.vehicle_owner_address,
                                sp.agent_name,
                                rc.name,
                                sw.name,
                                so.name,
                                sales_order_date,
                                sp.approved_date,
                                pp.default_code,
                                pt.name->>'en_US',
                                status,
                                so.approved_date
                        order by 
                                expected_date asc, sp.date_done, sp.name"""
                                
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        print("\n\n\n\n\n==============tz========",tz)
        self.env.cr.execute(delivery_sql, (tz, tz, tz, tz, tz, tz))
        print("\n\n\n\n\n\n==============self.env.cr.execute(delivery_sql, (tz, tz, tz, tz, tz, tz))==============",delivery_sql)
        print("\n\n\n\n\n\n==============delivery_sql==============",delivery_sql)
        product_data = self.env.cr.dictfetchall()
        print("\n\n\n\n\n\n==============product_data==============",product_data)
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
        sheet1.col(5).width = 12000
        sheet1.col(6).width = 8000
        sheet1.col(7).width = 4500
        sheet1.col(8).width = 4500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 4500
        sheet1.col(11).width = 9500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 4500
        sheet1.col(14).width = 4500
        sheet1.col(15).width = 4500
        sheet1.col(16).width = 4500
        sheet1.col(17).width = 4500
        sheet1.col(18).width = 4500
        sheet1.col(19).width = 4500
        sheet1.col(20).width = 4500
        sheet1.col(21).width = 4500
        sheet1.col(22).width = 4500
        sheet1.col(23).width = 4500
    
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
                sheet1.write_merge(rc, rc, 0, 14, title1, Style.main_title())
                sheet1.write_merge(r1, r1, 0, 14, title, Style.sub_main_title())
                sheet1.write_merge(r2, r2, 0, 14, title2, Style.subTitle_left())
            else:
                title = report_name +' ( Actual Delivery Date From ' + date_from + ' To ' +  date_to + ' )'
                sheet1.write_merge(rc, rc, 0, 23, title1, Style.main_title())
                sheet1.write_merge(r1, r1, 0, 23, title, Style.sub_main_title())
                sheet1.write_merge(r2, r2, 0, 23, title2, Style.subTitle_left())
        else:
            sheet1.write_merge(rc, rc, 0, 14, title1, Style.main_title())
            sheet1.write_merge(r1, r1, 0, 14, report_name, Style.sub_main_title())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Reference No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Expected Delivery Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Actual Delivery Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Customer", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Customer Address", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Sales Manager", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Sales order No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Sales Order Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 13, "Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 14, "Status", Style.contentTextBold(r2,'black','white'))
        if self.date_type == 'actual_date':
            sheet1.write(r3, 15, "Driver Name", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r3, 16, "Driver Contact No", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r3, 17, "Driver Licence No", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r3, 18, "Driver Licence Type", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r3, 19, "Issued Licence Place", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r3, 20, "Vehicle No", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r3, 21, "Vehicle Owner", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r3, 22, "Vehicle Owner Address", Style.contentTextBold(r2,'black','white'))
            sheet1.write(r3, 23, "Agent Name", Style.contentTextBold(r2,'black','white'))
        
        row = r3
        s_no = 0
        for each in product_data:
            row += 1
            s_no = s_no + 1
            sheet1.row(row).height = 600
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['reference'], Style.normal_left())
            expected_date = ""
            if each['expected_date']:
                # expected_date = time.strptime(each['expected_date'], "%Y-%m-%d")
                # expected_date = time.strftime('%d-%m-%Y', expected_date)
                # expected_date = self.expected_date.strftime('%d-%m-%Y')
                expected_date = each['expected_date'].strftime('%d-%m-%Y')
            sheet1.write(row, 2, expected_date, Style.normal_left())
            actual_date = ""
            if each['actual_date']:
                # actual_date = time.strptime(each['actual_date'], "%Y-%m-%d")
                # actual_date = time.strftime('%d-%m-%Y', actual_date)
                # actual_date = self.actual_date.strftime('%d-%m-%Y')
                actual_date = each['actual_date'].strftime('%d-%m-%Y')
            sheet1.write(row, 3, actual_date, Style.normal_left())
            sheet1.write(row, 4, each['customer'], Style.normal_left())
            sheet1.write(row, 5, each['address'], Style.normal_left())
            sheet1.write(row, 6, each['warehouse'], Style.normal_left())
            sheet1.write(row, 7, each['sales_manager'], Style.normal_left())
            sheet1.write(row, 8, each['sales_order_no'], Style.normal_left())
            sales_order_date = ""
            if each['sales_order_date']:
                # sales_order_date = time.strptime(each['sales_order_date'], "%Y-%m-%d")
                # sales_order_date = self.sales_order_date.strftime('%d-%m-%Y')
                sales_order_date = each['sales_order_date'].strftime('%d-%m-%Y')
            sheet1.write(row, 9, sales_order_date, Style.normal_left())
            approved_date = ""
            if each['approved_date']:
                # approved_date = time.strptime(each['approved_date'], "%Y-%m-%d")
                # approved_date = self.approved_date.strftime('%d-%m-%Y', )
                approved_date = each['approved_date'].strftime('%d-%m-%Y')
            sheet1.write(row, 10, approved_date, Style.normal_left())
            sheet1.write(row, 11, each['product'], Style.normal_left())
            sheet1.write(row, 12, each['uom'], Style.normal_left())
            sheet1.write(row, 13, each['quantity'], Style.normal_num_right_3digits())
            sheet1.write(row, 14, each['status'], Style.normal_left())    
            if self.date_type == 'actual_date':              
                sheet1.write(row, 15, each['driver_name'], Style.normal_left())
                sheet1.write(row, 16, each['driver_phone'], Style.normal_left())
                sheet1.write(row, 17, each['licence_no'], Style.normal_left())
                sheet1.write(row, 18, each['licence_type'], Style.normal_left())
                sheet1.write(row, 19, each['licence_place'], Style.normal_left())
                sheet1.write(row, 20, each['vehicle_no'], Style.normal_left())
                sheet1.write(row, 21, each['vehicle_owner'], Style.normal_left())
                sheet1.write(row, 22, each['owner_address'], Style.normal_left())
                sheet1.write(row, 23, each['agent_name'], Style.normal_left())

        stream = BytesIO()
        wbk.save(stream)                            
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'product.delivery.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
