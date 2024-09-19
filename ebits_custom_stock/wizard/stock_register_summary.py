# -*- coding: utf-8 -*-
# Part of EBITS TechCon.

from odoo import api, fields, models, _
from . import excel_styles
import xlwt
from io import BytesIO
import base64
from lxml import etree

class StockRegisterSummary(models.TransientModel):
    _name = "stock.register.summary"
    _description = "Warehouse Stock Summary"
    
    master_ids = fields.Many2many('stock.report.master', string='Report for', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='Format', readonly=True)

    def print_report(self):
        report_name = "Warehouse Stock Summary Report"
        filters = "Filtered based on "
        product_obj = self.env['product.product']
        purchase_line_obj = self.env['purchase.order.line']
        pr_line_obj = self.env['po.requisition.item.lines']
        
        master_ids = []
        master_list = []
        master_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        location_ids = []
        location_list = []
        location_str = ""
        
        categ_ids = []
        categ_list = []
        
        for each_id in self.master_ids:
            master_ids.append(each_id.id)
            master_list.append(each_id.name)
            for categ in each_id.categ_ids:
                categ_ids.append(categ)
                categ_list.append(categ.name)
                for wh in categ.warehouse_ids:
                    warehouse_ids.append(wh)
                    warehouse_list.append(wh.name)
        if master_list:
            master_list = list(set(master_list))
            master_str = str(master_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            filters += "Report for: " + master_str
        
        if warehouse_ids:
            warehouse_list = list(set(warehouse_list))
            warehouse_ids = list(set(warehouse_ids))
            warehouse_str = str(warehouse_list).replace("[","").replace("]","").replace("u'","").replace("'","")
            filters += "  Warehouse: " + warehouse_str
        if categ_ids:
            categ_ids = list(set(categ_ids))
        if categ_list:
            categ_list = list(set(categ_list))
        
        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(5)
        sheet1.show_grid = False 
        
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 4
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 310 * 3
        title = report_name 
        title1 = self.company_id.name
        title2 = filters 
        #***************** Headings *****************#
        headings = ["S.No", "Product Category", "Product", "UOM"]
        heading_sizes = [2000, 9000, 7500, 2500 ]
        for h in range(len(heading_sizes)):
            sheet1.col(h).width = heading_sizes[h]
        qty_heads = ["Intransit Stock", "Pending PO Qty", "PR Qty To Be Approved", "PR Qty Approved To Be Ordered"]
        
        hl = len(headings)
        for i in range(hl):
            sheet1.write(r4, i, headings[i], Style.contentTextBold(r2, 'black', 'white'))
        for x in range(hl, (hl + len(warehouse_ids))):
            sheet1.col(x).width = 6500
            sheet1.write(r4-1, x, warehouse_ids[x - hl].name, Style.contentTextBold(r2, 'black', 'white'))
            sheet1.write(r4, x, "Stock On Hand", Style.contentTextBold(r2, 'black', 'white'))
        for y in range((hl + len(warehouse_ids)), (hl + len(warehouse_ids)) + 4):
            sheet1.col(y).width = 4500
            sheet1.write(r4, y, qty_heads[0], Style.contentTextBold(r2, 'black', 'white'))
            del qty_heads[0]
        #***************** Headings *****************#            
        row = r4
        s_no = 0
        col = 3
        for each in categ_ids:
            for item in product_obj.search([('categ_id', '=', each.id)]):
                row += 1
                s_no = s_no + 1
                sheet1.write(row, 0, s_no, Style.normal_left())
                sheet1.write(row, 1, each.name, Style.normal_left())
                sheet1.write(row, 2, item.name_get()[0][1], Style.normal_left())
                sheet1.write(row, 3, item.uom_id.name, Style.normal_left())
                col = 3
                transit_qty = {}
                po_qty = 0.00
                waiting_qty = 0.00
                to_be_ordered = 0.00
                for warehouse in warehouse_ids:
                    col += 1
                    sheet1.write(row, col, item.with_context({'warehouse': warehouse.id}).qty_available, Style.normal_right())
                    transit_qty [str(warehouse.transit_location_id.id)] = item.with_context({'location': warehouse.transit_location_id.id}).qty_available
                    pending_po = purchase_line_obj.search([('warehouse_id', '=', warehouse.id), ('product_id', '=', item.id), ('state', 'in', ['purchase', 'done'])])
                    pending_pr = pr_line_obj.search([('warehouse_id', '=', warehouse.id), ('product_id', '=', item.id), ('state', 'in', ('waiting', 'waiting_2nd'))])
                    to_be_ordered_pr = pr_line_obj.search([('warehouse_id', '=', warehouse.id), ('product_id', '=', item.id), ('state', '=', 'done')])
                    po_qty = sum((x.product_qty - x.qty_received) for x in pending_po)
                    waiting_qty += sum(x.approved_qty for x in pending_pr)
                    to_be_ordered += sum(x.to_ordered_qty for x in to_be_ordered_pr)
                col += 1    
                sheet1.write(row, col, sum(transit_qty[x] for x in transit_qty), Style.normal_right())
                col += 1    
                sheet1.write(row, col, po_qty, Style.normal_right())
                col += 1    
                sheet1.write(row, col, waiting_qty, Style.normal_right())
                col += 1    
                sheet1.write(row, col, to_be_ordered, Style.normal_right())
        sheet1.write_merge(r1, r1, 0, col, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, col, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, col, title2, Style.subTitle_left())
            
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.register.summary',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
