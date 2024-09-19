# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

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

class RolReportWizard(models.TransientModel):
    _name = 'rol.report.wizard'
    _description = 'ROL Report Wizard'
    
    product_ids = fields.Many2many('product.product', 'etc_rol_report_product', 'rol_report_wizard_id', 'product_id', string='Product')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_rol_report_warehouse', 'rol_report_wizard_id', 'warehouse_id', string='Warehouse')
    view_location_ids = fields.Many2many('stock.location', 'etc_rol_report_view_location', 'rol_report_wizard_id', 'view_location_id', string='View Location')
    location_ids = fields.Many2many('stock.location', 'etc_rol_report_location', 'rol_report_wizard_id', 'location_id', string='Location')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(RolReportWizard, self).fields_view_get(
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
    
#    @api.onchange('warehouse_ids')
#    def onchange_warehouse_ids(self):
#        if self.warehouse_ids:
#            self.view_location_ids = [(6, 0, [x.view_location_id.id for x in self.warehouse_ids])]
#        else:
#            self.view_location_ids = False
    
    
    def action_report(self):
        report_name = "Reordering Level Report"
        filters = ""
        product_sql = """ """
        location_sql = """ """
        warehouse_sql = """ """
        
        product_ids = []
        product_list = []
        product_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        location_ids = []
        location_list = []
        location_str = ""
        if self.product_ids or self.warehouse_ids or self.location_ids:
           filters += "Filter Base on :" 
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
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace('u','').replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and sw_op.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and sw_op.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += "  Warehouse: " + warehouse_str
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace('u','').replace("'","")
            if len(product_ids) > 1:
                product_sql += "and pp.id in "+ str(tuple(product_ids))
            else:
                product_sql += "and pp.id in ("+ str(product_ids[0]) + ")"
            filters += "  Product: " + product_str
        if self.location_ids:
            for each_id in self.location_ids:
                location_ids.append(each_id.id)
                location_list.append(each_id.name)
            location_list = list(set(location_list))
            location_str = str(location_list).replace('[','').replace(']','').replace('u','').replace("'","")
            if len(location_ids) > 1:
                location_sql += "and sw_op.location_id in "+ str(tuple(location_ids))
            else:
                location_sql += "and sw_op.location_id in ("+ str(location_ids[0]) + ")"
            filters += "  Location: " + location_str
        print("\n\n\n\nproduct_sql",product_sql)
        print("\n\n\n\nlocation_sql",location_sql)
        print("\n\n\n\nwarehouse_sql",warehouse_sql)
        rol_sql = """select * from (select 
	                            pp.default_code as product_code,
	                            pp.id as product_id,
	                            concat( '[' , pt.default_code, '] ', pt.name->>'en_US') as product,
	                            pc.name as category,
	                            pu.name->>'en_US' as uom,
	                            sw.name as warehouse,
	                            sl.name as location,
	                            sw.id as warehouse_id,
	                            sl.id as location_id,
	                            (case when sw_op.product_min_qty is not null then sw_op.product_min_qty else 0.00 end) as min_qty,
	                            (case when sw_op.product_max_qty  is not null then sw_op.product_max_qty else 0.00 end) as max_qty,

	                            (select (case when sum(sq.quantity) is not null then sum(sq.quantity) else 0.00 end) from stock_quant sq
		                            where sq.product_id = pp.id and sq.location_id = sl.id ) as stock_location_qty,

	                            (select (case when sum(pol.product_qty) is not null then sum(pol.product_qty) else 0.00 end) from purchase_order_line pol
			                            left join purchase_order po on(po.id = pol.order_id)
		                            where pol.product_id = pp.id and po.warehouse_id = sw.id and po.state not in  ('purchase', 'done', 'cancel')) as po_qty,

	                            (select (case when sum(sm.product_uom_qty) is not null then sum(sm.product_uom_qty) else 0.00 end) from stock_move sm
			                            left join stock_picking sp on (sp.id = sm.picking_id)
			                            left join stock_picking_type spt on (spt.id = sp.picking_type_id)
		                            where sm.product_id = pp.id and sm.warehouse_id = sw.id and sp.state not in ('cancel','done') and spt.code like 'incoming%') as grn_qty,

                                    (select (case when sum(istl.qty) is not null then sum(istl.qty) else 0.00 end) 
		                           from internal_stock_transfer_request_lines istl
		                           where istl.state = 'waiting'
			                        and istl.product_id = pp.id
			                        and istl.requesting_warehouse_id = sw.id)as st_request_qty,  
			                        
			                     (select (case when sum((case when st_iss.approved_qty is not null then st_iss.approved_qty else 0.00 end) - 
	                                    (case when st_iss.issued_qty is not null then st_iss.issued_qty else 0.00 end)) is not null then sum((case when st_iss.approved_qty is not null then st_iss.approved_qty else 0.00 end) - 
	                                    (case when st_iss.issued_qty is not null then st_iss.issued_qty else 0.00 end)) else 0.00 end) 
		                               from internal_stock_transfer_issue_line st_iss
		                                     left join internal_stock_transfer_issue ist on (ist.id = st_iss.issue_id)  
		                               where ist.state in ('draft', 'partial')
		                                     and st_iss.product_id = pp.id
		                                     and st_iss.issuing_warehouse_id = sw.id
		                               ) as st_issue_qty,  

                                 (select (case when sum((case when st_rec.issued_qty is not null then st_rec.issued_qty else 0.00 end) - 
	                                   (case when st_rec.received_qty is not null then st_rec.received_qty else 0.00 end)) is not null then sum((case when st_rec.issued_qty is not null then st_rec.issued_qty else 0.00 end) - 
	                                   (case when st_rec.received_qty is not null then st_rec.received_qty else 0.00 end)) else 0.00 end)
		                               from internal_stock_transfer_receipt_line st_rec
			                                left join internal_stock_transfer_receipt isr on (isr.id = st_rec.receipt_id)  
		                               where isr.state in ('draft', 'partial')
			                                and st_rec.product_id = pp.id
			                                and st_rec.receiving_warehouse_id = sw.id
		                               ) as st_receipt_qty, 
		                            
                                (select (case when sum(smo.product_uom_qty) is not null then sum(smo.product_uom_qty) else 0.00 end) from stock_move smo
	                                    left join mrp_production mrp on (mrp.id = smo.production_id)
                                    where mrp.product_id = pp.id and mrp.warehouse_id = sw.id and smo.state not in ('cancel','done')) as mo_qty,
                                    (select	(case when sum(sm.product_uom_qty) is not null then sum(sm.product_uom_qty) else 0.00 end) from stock_move sm
			                            left join stock_picking sp on (sp.id = sm.picking_id)
			                            left join stock_picking_type spt on (spt.id = sp.picking_type_id)
		                            where sm.product_id = pp.id and sm.warehouse_id = sw.id and sp.state not in ('cancel','done') and spt.code = 'outgoing') as do_qty, 
		                            (select (case when sum((case when st_iss.approved_qty is not null then st_iss.approved_qty else 0.00 end) - 
	                                    (case when st_iss.issued_qty is not null then st_iss.issued_qty else 0.00 end)) is not null then sum((case when st_iss.approved_qty is not null then st_iss.approved_qty else 0.00 end) - 
	                                    (case when st_iss.issued_qty is not null then st_iss.issued_qty else 0.00 end)) else 0.00 end)
		                               from internal_stock_transfer_issue_line st_iss
		                                     left join internal_stock_transfer_issue ist on (ist.id = st_iss.issue_id)  
		                               where ist.state in ('draft', 'partial')
		                                     and st_iss.product_id = pp.id
		                                     and st_iss.issuing_warehouse_id = sw.id
		                               ) as st_out_issue_qty    
                            from stock_warehouse_orderpoint sw_op 
	                            left join  product_product pp on (pp.id = sw_op.product_id) 
	                            left join product_template pt on (pt.id = pp.product_tmpl_id)
	                            left join uom_uom pu on (pu.id = pt.uom_id)
	                            left join product_category pc on (pc.id = pt.categ_id)
	                            left join stock_warehouse sw on (sw.id = sw_op.warehouse_id)
	                            left join stock_location sl on (sl.id = sw_op.location_id)
                            where pp.active = True and pt.type = 'product'""" + product_sql + location_sql + warehouse_sql + """group by  
                            pp.id,
                            sw.id,
                            sl.id,
                            pt.name->>'en_US',
                            pu.name->>'en_US',
                            pc.name,
                            pt.default_code,
                            sw.name,
                            sl.name, 
                            sw_op.product_min_qty,
                            sw_op.product_max_qty 
                            order by pp.id) x where (x.min_qty > (x.stock_location_qty + x.grn_qty ));""" 
        
             
        self.env.cr.execute(rol_sql)
        rol_data = self.env.cr.dictfetchall()
        print("\n\n\n\n\n=rol_data==rol_data===",rol_data)
        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 9000
        sheet1.col(2).width = 7500
        sheet1.col(3).width = 2500
        sheet1.col(4).width = 6500
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 3500
        sheet1.col(8).width = 3500
        sheet1.col(9).width = 4000
        sheet1.col(10).width = 4000
        sheet1.col(11).width = 4000
        sheet1.col(12).width = 3000
        sheet1.col(13).width = 3500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 4500
        sheet1.col(18).width = 7000
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 310 * 3
        title = report_name 
        title1 = self.company_id.name
        title2 = filters 
        sheet1.write_merge(r1, r1, 0, 18, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 18, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 18, title2, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Location", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Min Qty \n\n\n\t(A)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Max Qty \n\n\n\t(B)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Stock Location Qty \n\n\t(C)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Stock Transfer Request Qty \n\n\t(D)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Pending Issue Qty from other Warehouse \n\t(E)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 11, "Stock Transfer Pending Receipt Qty \n\t(F)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 12, "Unapproved PO Qty \n\n\t(G)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 13, "Pending GRN Qty \n\n\t(H)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 14, "Quality Location Qty \n\n\t(I)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 15, "Pending MO Qty \n\n\t(J)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 16, "Pending DO Qty \n\n\t(K)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 17, "Pending Issue Qty to other Warehouse \n\n\t(L)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 18, "Quantity to be Ordered \n\n\n(B-[sum(C to J) - sum(K to L)])", Style.contentTextBold(r2,'black','white'))
        
        row = r4
        s_no = 0
        total_qty = 0.00
        if rol_data:
            for line in rol_data:
                row += 1
                s_no = s_no + 1
                sheet1.row(row).height = 350
                sheet1.write(row, 0, s_no, Style.normal_left())
                sheet1.write(row, 1, line['product'], Style.normal_left())
                sheet1.write(row, 2, line['category'], Style.normal_left())
                sheet1.write(row, 3, line['uom'], Style.normal_left())
                sheet1.write(row, 4, line['warehouse'], Style.normal_left())
                sheet1.write(row, 5, line['location'], Style.normal_left())
                sheet1.write(row, 6, line['min_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 7, line['max_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 8, line['stock_location_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 9, line['st_request_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 10, line['st_issue_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 11, line['st_receipt_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 12, line['po_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 13, line['grn_qty'], Style.normal_num_right_3digits())
                # sheet1.write(row, 14, line['quality_location_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 15, line['mo_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 16, line['do_qty'], Style.normal_num_right_3digits())
                sheet1.write(row, 17, line['st_out_issue_qty'], Style.normal_num_right_3digits())
                total_qty = (line['max_qty'] - abs((line['stock_location_qty'] + line['st_request_qty'] + line['mo_qty']) - (line['do_qty'] + line['st_out_issue_qty'])))
                sheet1.write(row, 18, total_qty, Style.normal_num_right_3digits())
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'rol.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
