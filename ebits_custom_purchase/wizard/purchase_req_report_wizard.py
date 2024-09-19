# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
# from excel_styles import ExcelStyles
from odoo.addons.ebits_custom_purchase.wizard.excel_styles import ExcelStyles

import xlwt
# import cStringIO
from io import StringIO
import base64
import xlrd


class PurchaseRequisitionReportWizard(models.TransientModel):
    _name = 'purchase.requisition.report.wizard'
    _description = 'Purchase Requisition Report Wizard'
    
    date_from = fields.Date(string='From Date(Requisition Date)', required=True)
    date_to = fields.Date(string='To Date(Requisition Date)', required=True)
    pur_category_ids = fields.Many2many('purchase.category', 'etc_purcase_req_pur_category', 'purchase_req_wizard_id', 'pur_category_id', string='Requisition Type')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_purchase_req_warehous', 'purchase_req_wizard_id', 'warehouse_id', string='Warehouse')
    category_ids = fields.Many2many('product.category', 'etc_purchase_req_category', 'purchase_req_wizard_id', 'categ_id', string='Product Category')
    product_ids = fields.Many2many('product.product', 'etc_purchase_req_product', 'purchase_req_wizard_id', 'product_id', string='Product')
    location_ids = fields.Many2many('stock.location', 'etc_purchase_req_location', 'purchase_req_wizard_id', 'location_id', string='Required Location')
    state = fields.Selection([('draft', 'Draft'), ('waiting', 'Waiting For Approval'), ('waiting_2nd', 'Waiting For 2nd Approval'), ('approved', 'Approved'), ('cancel', 'Cancelled')], string='Status')
    force_close = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Force Closed')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PurchaseRequisitionReportWizard, self).fields_view_get(
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
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Purchase Requisition List"
        date_from_string = self.date_from.strftime("%Y-%m-%d")  # Convert datetime.date to string in "%Y-%m-%d" format
        from_date_struct_time = time.strptime(date_from_string, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date_struct_time)
        # from_date = time.strptime(self.date_from,"%Y-%m-%d")
        # from_date = time.strftime('%d-%m-%Y',from_date)
        date_to_string = self.date_to.strftime("%Y-%m-%d")
        from_date_to_struct_time = time.strptime(date_to_string, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', from_date_to_struct_time)
        # to_date = time.strptime(self.date_to,"%Y-%m-%d")
        # to_date = time.strftime('%d-%m-%Y',to_date)
        filters = "Filtered Based on Date From : "+str(from_date) + " , To : "+str(to_date)
        req_type_sql = """ """
        warehouse_sql = """ """
        category_sql = """ """
        product_sql = """ """
        location_sql = """ """
        status_sql = """ """
        force_close_sql = """ """
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        category_ids = []
        category_list = []
        category_str = ""
        
        product_ids = []
        product_list = []
        product_str = ""
        
        location_ids = []
        location_list = []
        location_str = ""
        
        pur_category_ids = []
        pur_category_list = []
        pur_category_str = ""
        
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and pr.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and pr.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += "and pr.warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += "and pr.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                filters += ", Warehouse: " + warehouse_str
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(product_ids) > 1:
                product_sql += "and prl.product_id in "+ str(tuple(product_ids))
            else:
                product_sql += "and prl.product_id in ("+ str(product_ids[0]) + ")"
            filters += ", Product: " + product_str 
        if self.category_ids:
            for each_id in self.category_ids:
                category_ids.append(each_id.id)
                category_list.append(each_id.name)
            category_list = list(set(category_list))
            category_str = str(category_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(category_ids) > 1:
                category_sql += "and pt.categ_id in "+ str(tuple(category_ids))
            else:
                category_sql += "and pt.categ_id in ("+ str(category_ids[0]) + ")"
            filters += ", Product Category: " + category_str 
        if self.location_ids:
            for each_id in self.location_ids:
                location_ids.append(each_id.id)
                location_list.append(each_id.name)
            location_list = list(set(location_list))
            location_str = str(location_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(location_ids) > 1:
                location_sql += "and prl.location_id in "+ str(tuple(location_ids))
            else:
                location_sql += "and prl.location_id in ("+ str(location_ids[0]) + ")"
            filters += ", Required Location: " + location_str 
        if self.pur_category_ids:
            for each_id in self.pur_category_ids:
                pur_category_ids.append(each_id.id)
                pur_category_list.append(each_id.name)
            pur_category_list = list(set(pur_category_list))
            pur_category_str = str(pur_category_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(pur_category_ids) > 1:
                req_type_sql += "and pr.category_id in "+ str(tuple(pur_category_ids))
            else:
                req_type_sql += "and pr.category_id in ("+ str(pur_category_ids[0]) + ")"
            filters += ", Requisition Type: " + pur_category_str 
        if self.force_close:
            if self.force_close == 'yes':
                force_close_sql = "and prl.force_close = True"
                filters += ", Force Closed : Yes"
            if self.force_close == 'no':
                force_close_sql = "and prl.force_close = False"
                filters += ", Force Closed : No"
        if self.state:
            status_sql = " and prl.state = " + "'" + str(self.state) + "'"
            if self.state == 'draft':
                filters += ", State : Draft"
            if self.state == 'waiting':
                filters += ", State : Waiting For Approval"
            if self.state == 'waiting_2nd':
                filters += ", State : Waiting For 2nd Approval"
            if self.state == 'approved':
                filters += ", State : Approved"
            if self.state == 'cancel':
                filters += ", State : Cancelled"
        else:
            status_sql = " and prl.state != 'cancel'" 
        pur_req_sql = """ select 	
	                            pr.name as req_no,
	                            pr.date_requisition as req_date,
	                            pc.name as req_type,
	                            rp.name as requestor,
	                            sw.name as warehouse,
	                            par_o.name as employee,
	                            par_t.name as employee2,
	                            to_char(pr.one_approved_date, 'dd-mm-yyyy') as approved_date,
	                            to_char(pr.two_approved_date, 'dd-mm-yyyy') as approved_date2,
	                            proc.name as product_categ,
	                            concat( '[' , pp.default_code, '] ', pt.name) as product,
	                            pu.name as uom,
	                            prl.required_qty as req_qty,
	                            prl.date_required as required_date,
	                            sl.name as req_location,
	                            pr.id as id,
	                            prl.approved_qty as approved_qty,
	                            prl.ordered_qty as po_qty,
	                            prl.to_ordered_qty as to_ordered_qty,
	                            (case when prl.force_close = 'True' then 'Yes' else 'No' end) as force_close,
	                            (case when prl.state = 'draft' then 'Draft' 
                                 when prl.state = 'waiting' then 'Waiting For Approval' 
                                 when prl.state = 'waiting_2nd' then 'Waiting For 2nd Approval' 
	                             when prl.state = 'approved' then 'Approved'
	                             when prl.state = 'cancel' then 'Cancelled' else prl.state end) as state
                            from purchase_requisition_extend pr
	                            left join purchase_category pc on (pc.id = pr.category_id)
	                            left join res_users ru on (ru.id = pr.user_id)
	                            left join res_partner rp on (rp.id = ru.partner_id)
	                            left join stock_warehouse sw on (sw.id = pr.warehouse_id)
	                            left join res_users app_o on (app_o.id = pr.one_approved_id)
	                            left join res_partner par_o on (par_o.id = app_o.partner_id)
	                            left join res_users app_t on (app_t.id = pr.two_approved_id)
	                            left join res_partner par_t on (par_t.id = app_t.partner_id)
	                            left join po_requisition_item_lines prl on (prl.requisition_id = pr.id)
	                            left join product_product pp on (pp.id = prl.product_id)
	                            left join product_template pt on (pt.id = pp.product_tmpl_id)
	                            left join product_category proc on (proc.id = pt.categ_id)	
	                            left join uom_uom pu on (pu.id = pt.uom_id)
	                            left join stock_location sl on (sl.id = prl.location_id)
                            where  (pr.date_requisition between %s and %s)""" + req_type_sql + warehouse_sql + category_sql + product_sql + location_sql + status_sql + force_close_sql +""" group by
                                pr.name,
	                            pr.date_requisition,
	                            pc.name,
	                            prl.state,
	                            prl.required_qty,
	                            prl.approved_qty,
	                            prl.ordered_qty,
	                            prl.to_ordered_qty,
	                            prl.force_close,
	                            rp.name,
	                            sw.name,
	                            par_o.name,
	                            pr.one_approved_date,
	                            par_t.name,
	                            pr.two_approved_date,
	                            proc.name,
	                            concat( '[' , pp.default_code, '] ', pt.name),
	                            pu.name,
	                            prl.date_required,
	                            sl.name,
	                            pr.id,
	                            (case when prl.state = 'draft' then 'Draft' 
                                 when prl.state = 'waiting' then 'Waiting Approval' 
	                             when prl.state = 'approved' then 'Approved'
	                             when prl.state = 'cancel' then 'Cancel' else prl.state end) 
                            order by
	                            pr.date_requisition desc, pr.name desc"""

        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'                        
        
        self.env.cr.execute(pur_req_sql , (date_from, date_to,))
        pur_req_data = self.env.cr.dictfetchall()
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 5000
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 3500
        sheet1.col(4).width = 5000
        sheet1.col(5).width = 6000
        sheet1.col(6).width = 4500
        sheet1.col(7).width = 4500
        sheet1.col(8).width = 4500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 6500
        sheet1.col(11).width = 6500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 3500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 4500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500
        sheet1.col(18).width = 3500
        sheet1.col(19).width = 3500
        sheet1.col(20).width = 3500
    
        rc = 0
        r1 = 1
        r2 = 2
        r3 = 3
        sheet1.row(rc).height = 500
        sheet1.row(r1).height = 400
        sheet1.row(r2).height = 200 * 2
        sheet1.row(r3).height = 256 * 3
        title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
        title1 = self.company_id.name
        title2 = filters 
        sheet1.write_merge(rc, rc, 0, 20, title1, Style.main_title())
        sheet1.write_merge(r1, r1, 0, 20, title, Style.sub_main_title())
        sheet1.write_merge(r2, r2, 0, 20, title2, Style.subTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "Requisition No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "Requisition Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Requisition Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Requestor", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "1st Approved By", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "1st Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "2nd Approved By", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "2nd Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 13, "Request Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 14, "Required Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 15, "Required Location", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 16, "PR Approved Quantity       ** (A) **", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 17, "PR Qty in PO (Draft/Pending Approval/Approved) ** (B) **", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 18, "Pending Qty to be Ordered ** (A-B) **", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 19, "Force Closed", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 20, "Status", Style.contentTextBold(r2,'black','white'))
        
        row = r3
        s_no = 0
        
        for each in pur_req_data:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 300
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['req_no'], Style.normal_left())
            req_date = ""
            if each['req_date']:
                req_date = time.strptime(each['req_date'], "%Y-%m-%d")
                req_date = time.strftime('%d-%m-%Y', req_date)
            sheet1.write(row, 2, req_date, Style.normal_left())
            sheet1.write(row, 3, each['req_type'], Style.normal_left())
            sheet1.write(row, 4, each['requestor'], Style.normal_left())
            sheet1.write(row, 5, each['warehouse'], Style.normal_left())
            sheet1.write(row, 6, each['employee'], Style.normal_left())
            sheet1.write(row, 7, each['approved_date'], Style.normal_left())
            sheet1.write(row, 8, each['employee2'], Style.normal_left())
            sheet1.write(row, 9, each['approved_date2'], Style.normal_left())
            sheet1.write(row, 10, each['product_categ'], Style.normal_left())
            sheet1.write(row, 11, each['product'], Style.normal_left())
            sheet1.write(row, 12, each['uom'], Style.normal_left())
            sheet1.write(row, 13, each['req_qty'], Style.normal_num_right_3digits())
            required_date = ""
            if each['required_date']:
                required_date = time.strptime(each['required_date'], "%Y-%m-%d")
                required_date = time.strftime('%d-%m-%Y', required_date)
            sheet1.write(row, 14, required_date, Style.normal_left())
            sheet1.write(row, 15, each['req_location'], Style.normal_left())
            sheet1.write(row, 16, each['approved_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 17, each['po_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 18, each['to_ordered_qty'], Style.normal_num_right_3digits())
            sheet1.write(row, 19, each['force_close'], Style.normal_left())
            sheet1.write(row, 20, each['state'], Style.normal_left())

        stream = StringIO()
        wbk.save(stream)

        self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'purchase.requisition.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
