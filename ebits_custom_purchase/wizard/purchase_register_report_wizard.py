# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.addons.ebits_custom_purchase.wizard.excel_styles import ExcelStyles

import xlwt
# import cStringIO
from io import StringIO
import base64
from lxml import etree
import io

class PurchaseRegisterReportWizard(models.TransientModel):
    _name = 'purchase.register.report.wizard'
    _description = 'Purchase Register Report Wizard'
    
    date_from = fields.Date(string='From Date(Order Date)', required=True)
    date_to = fields.Date(string='To Date(Order Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_purchase_register_partner', 'purchase_register_wizard_id', 'partner_id', string='Vendor')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_purchase_register_warehouse', 'purchase_register_wizard_id', 'warehouse_id', string='Warehouse')
    category_ids = fields.Many2many('product.category', 'etc_purchase_register_category', 'purchase_register_wizard_id', 'category_id', string='Product Category')
    product_ids = fields.Many2many('product.product', 'etc_purchase_register_product', 'purchase_register_wizard_id', 'product_id', string='Product')
    currency_ids = fields.Many2many('res.currency', 'etc_purchase_register_currency', 'purchase_register_wizard_id', 'currency_id', string='Currency')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to approve', 'Pending for Approval'),
        ('to_2nd_approve', 'Pending for 2nd Approval'),
        ('purchase', 'Purchase Order'),
        ('cancel', 'Cancelled')
        ], string='PO Status')
    invoice_status = fields.Selection([
        ('no', 'Nothing to Bill'),
        ('to invoice', 'Waiting Bills'),
        ('invoiced', 'Bills Received'),
        ], string='Billing Status')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PurchaseRegisterReportWizard, self).fields_view_get(
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
        po_obj = self.env['purchase.order.line']
        # date_from = self.date_from
        # date_to = self.date_to
        report_name = "Purchase Orders List Detailed"

        date_from_string = self.date_from.strftime("%Y-%m-%d")  # Convert datetime.date to string in "%Y-%m-%d" format
        from_date_struct_time = time.strptime(date_from_string, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date_struct_time)
        # from_date = time.strptime(self.date_from,"%Y-%m-%d")
        # from_date = time.strftime('%d-%m-%Y',from_date)
        date_to_string = self.date_to.strftime("%Y-%m-%d")
        from_date_to_struct_time = time.strptime(date_to_string, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', from_date_to_struct_time)


        # from_date = time.strptime(self.date_from, "%Y-%m-%d")
        # from_date = time.strftime('%d-%m-%Y', from_date)
        # to_date = time.strptime(self.date_to, "%Y-%m-%d")
        # to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date)
        
        all_partners_children = {}
        all_partner_ids = []
        partner_ids = []
        customer_list = []
        customer_str = ""
        
        warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        currency_ids = []
        currency_list = []
        currency_str = ""
        
        product_ids = []
        product_list = []
        product_str = ""
        
        category_ids = []
        category_list = []
        category_str = ""
        
        domain_default = []
        domain_default = [('order_id.date_order', '>=',  self.date_from), ('order_id.date_order', '<=', self.date_to)]
        
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
                domain_default = domain_default + [('order_id.partner_id', 'in', tuple(all_partner_ids))]
            else:
                domain_default = domain_default + [('order_id.partner_id', '=', all_partner_ids[0])]
            filters += ", Vendor: " + customer_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                domain_default = domain_default + [('order_id.warehouse_id', 'in', tuple(warehouse_ids))]
            else:
                domain_default = domain_default + [('order_id.warehouse_id', '=', warehouse_ids[0])]
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    domain_default = domain_default + [('order_id.warehouse_id', 'in', tuple(warehouse_ids))]
                else:
                    domain_default = domain_default + [('order_id.warehouse_id', '=', warehouse_ids[0])]
                filters += ", Warehouse: " + warehouse_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(currency_ids) > 1:
                domain_default = domain_default + [('order_id.currency_id', 'in', tuple(currency_ids))]
            else:
                domain_default = domain_default + [('order_id.currency_id', '=', currency_ids[0])]
            filters += ", Currency: " + currency_str  
        if self.product_ids:
            for each_id in self.product_ids:
                product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(product_ids) > 1:
                domain_default = domain_default + [('product_id', 'in', tuple(product_ids))]
            else:
                domain_default = domain_default + [('product_id', '=', product_ids[0])]
            filters += ", Product: " + product_str 
        if self.category_ids:
            for each_id in self.category_ids:
                category_ids.append(each_id.id)
                category_list.append(each_id.name)
            category_list = list(set(category_list))
            category_str = str(category_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(category_ids) > 1:
                domain_default = domain_default + [('product_id.categ_id', 'in', tuple(category_ids))]
            else:
                domain_default = domain_default + [('product_id.categ_id', '=', category_ids[0])]
            filters += ", Product Category: " + category_str  
        if self.state:
            if self.state == 'purchase':
                domain_default = domain_default + [('order_id.state', 'in', ['purchase', 'done'])]
            elif self.state == 'draft':
                domain_default = domain_default + [('order_id.state', 'in', ['draft', 'sent'])]
            else:
                domain_default = domain_default + [('state', '=', self.state)]
            if self.state == 'draft':
                filters += ", State : Draft"
            if self.state == 'to approve':
                filters += ", State : Pending for Approval"
            if self.state == 'to_2nd_approve':
                filters += ", State : Pending for 2nd Approval"
            if self.state == 'purchase':
                filters += ", State : Purchase Order"
            if self.state == 'cancel':
                filters += ", State : Cancelled"
        else:
            domain_default = domain_default + [('state', '!=', 'cancel')] 
        if self.invoice_status:
            domain_default = domain_default + [('order_id.invoice_status', '=', self.invoice_status)]
            if self.invoice_status == 'no':
                filters += ", Billing Status : Nothing to Bill"
            if self.invoice_status == 'to invoice':
                filters += ", Billing Status : Waiting Bills"
            if self.invoice_status == 'invoiced':
                filters += ", Billing Status : Bills Received"
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 5000
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 6000
        sheet1.col(4).width = 6500
        sheet1.col(5).width = 5000
        sheet1.col(6).width = 7000
        sheet1.col(7).width = 8500
        sheet1.col(8).width = 3000
        sheet1.col(9).width = 3000
        sheet1.col(10).width = 3000
        sheet1.col(11).width = 3000
        sheet1.col(12).width = 3000
        sheet1.col(13).width = 3000
        sheet1.col(14).width = 3000
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 4000
        sheet1.col(18).width = 4000
        sheet1.col(19).width = 4000
        sheet1.col(20).width = 4000
        sheet1.col(21).width = 5000
        sheet1.col(22).width = 4000
        sheet1.col(23).width = 4000
        sheet1.col(24).width = 4000
        sheet1.col(25).width = 4000
        sheet1.col(26).width = 4000
        sheet1.col(27).width = 4000
    
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
        sheet1.write_merge(rc, rc, 0, 27, title1, Style.main_title())
        sheet1.write_merge(r1, r1, 0, 27, title, Style.sub_main_title())
        sheet1.write_merge(r2, r2, 0, 27, title2, Style.subTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "PO No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "PO Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Vendor", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Category Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Required Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "Approved PR Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "PO Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "Received Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 13, "Returned Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 14, "Quantity to Bill", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 15, "Quantity to Refund", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 16, "Billed Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 17, "Refunded Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 18, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 19, "Unit Price", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 20, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 21, "PO Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 22, "Billing Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 23, "PO Creator", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 24, "1st Approver", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 25, "Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 26, "2nd Approver", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 27, "Approved Date", Style.contentTextBold(r2,'black','white'))
        
        row = r3
        s_no = 0
        po_records = po_obj.sudo().search(domain_default) 
        for each in po_records:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 400
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each.order_id.name, Style.normal_left())
            update_order_date = ""
            if each.order_id.date_order:
                order_date = each.date_order.date()  # Extract the date part from datetime
                update_order_date = order_date.strftime('%d-%m-%Y')

                # order_date = time.strftime(each.order_id.date_order)
                # order_date = datetime.strptime(order_date, '%Y-%m-%d %H:%M:%S').date()
                # update_order_date = datetime.strftime(order_date, '%d-%m-%Y')
            sheet1.write(row, 2, update_order_date, Style.normal_left())
            sheet1.write(row, 3, (each.order_id.partner_id and each.order_id.partner_id.name_get()[0][1] or ""), Style.normal_left())
            sheet1.write(row, 4, (each.order_id.warehouse_id and each.order_id.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(row, 5, (each.order_id.category_id and each.order_id.category_id.name or ""), Style.normal_left()) 
            sheet1.write(row, 6, (each.product_id.categ_id and each.product_id.categ_id.name or ""), Style.normal_left())
            sheet1.write(row, 7, (each.product_id and each.product_id.name_get()[0][1] or ""), Style.normal_left())
            sheet1.write(row, 8, (each.product_id.uom_id and each.product_id.uom_id.name or ""), Style.normal_left())
            update_required_date = ""
            if each.date_planned:
                required_date = each.date_planned.date()  # Extract the date part from datetime
                update_required_date = required_date.strftime('%d-%m-%Y')

                # required_date = time.strftime(each.date_planned)
                # required_date = datetime.strptime(required_date, '%Y-%m-%d %H:%M:%S').date()
                # update_required_date = datetime.strftime(required_date, '%d-%m-%Y')
            sheet1.write(row, 9, update_required_date, Style.normal_left())
            sheet1.write(row, 10, (each.pr_qty and each.pr_qty or 0.00), Style.normal_num_right_3digits())
            sheet1.write(row, 11, (each.product_qty and each.product_qty or 0.00), Style.normal_num_right_3digits()) 
            sheet1.write(row, 12, (each.qty_received and each.qty_received or 0.00), Style.normal_num_right_3digits()) 
            sheet1.write(row, 13, (each.qty_returned and each.qty_returned or 0.00), Style.normal_num_right_3digits()) 
            sheet1.write(row, 14, (each.qty_to_invoice and each.qty_to_invoice or 0.00), Style.normal_num_right_3digits()) 
            sheet1.write(row, 15, (each.qty_to_refund and each.qty_to_refund or 0.00), Style.normal_num_right_3digits()) 
            sheet1.write(row, 16, (each.qty_invoiced and each.qty_invoiced or 0.00), Style.normal_num_right_3digits()) 
            sheet1.write(row, 17, (each.qty_refunded and each.qty_refunded or 0.00), Style.normal_num_right_3digits()) 
            sheet1.write(row, 18, (each.order_id.currency_id and each.order_id.currency_id.name or ""), Style.normal_left())
            sheet1.write(row, 19, (each.price_unit and each.price_unit or 0.00), Style.normal_num_right_4digits()) 
            sheet1.write(row, 20, (each.price_subtotal and each.price_subtotal or 0.00), Style.normal_num_right_3separator()) 
            state = ""
            if each.state in ['draft', 'sent']:
                state = "Draft"
            if each.state == 'to approve':
                state = "Pending for Approval"
            if each.state == 'to_2nd_approve':
                state = "Pending for 2nd Approval"
            if each.state in ['purchase', 'done']:
                state = "Purchase Order"
            if each.state == 'cancel':
                state = "Cancelled"
            sheet1.write(row, 21, state, Style.normal_left())
            invoice_status = ""
            if each.order_id.invoice_status == 'no':
                invoice_status = "Nothing to Bill"
            if each.order_id.invoice_status == 'to invoice':
                invoice_status = "Waiting Bills"
            if each.order_id.invoice_status == 'invoiced':
                invoice_status = "Bills Received"
            sheet1.write(row, 22, invoice_status, Style.normal_left()) 
            sheet1.write(row, 23, (each.order_id.create_uid and each.order_id.create_uid.name or ""), Style.normal_left()) 
            sheet1.write(row, 24, (each.order_id.one_approved_id and each.order_id.one_approved_id.name or ""), Style.normal_left()) 
            update_first_approved_date = ""
            if each.order_id.one_approved_date:
                first_approved_date = each.order_id.one_approved_date.date()  # Extract the date part from datetime
                update_first_approved_date = first_approved_date.strftime('%d-%m-%Y')
                # first_approved_date = time.strftime(each.order_id.one_approved_date)
                # first_approved_date = datetime.strptime(first_approved_date, '%Y-%m-%d %H:%M:%S').date()
                # update_first_approved_date = datetime.strftime(first_approved_date, '%d-%m-%Y')
            sheet1.write(row, 25, update_first_approved_date, Style.normal_left())
            sheet1.write(row, 26, (each.order_id.two_approved_id and each.order_id.two_approved_id.name or ""), Style.normal_left()) 
            update_second_approved_date = ""
            if each.order_id.two_approved_date:
                second_approved_date = each.order_id.two_approved_date.date()  # Extract the date part from datetime
                update_second_approved_date = second_approved_date.strftime('%d-%m-%Y')
                # second_approved_date = time.strftime(each.order_id.two_approved_date)
                # second_approved_date = datetime.strptime(second_approved_date, '%Y-%m-%d %H:%M:%S').date()
                # update_second_approved_date = datetime.strftime(second_approved_date, '%d-%m-%Y')
            sheet1.write(row, 27, update_second_approved_date, Style.normal_left())

        # stream = StringIO()
        # stream = StringIO()
        # wbk.save(stream)

        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()

        self.write({ 'name': report_name +'.xls', 'output': base64.encodebytes(binary_data)})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'purchase.register.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
