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
# import parser
from lxml import etree
import io

class PoRegisterBillingDetailReportWizard(models.TransientModel):
    _name = 'po.register.billing.detail.register.report.wizard'
    _description = 'Purchase Register Billing Detail Report Wizard'
    
    date_from = fields.Date(string='From Date(Order Date)', required=True)
    date_to = fields.Date(string='To Date(Order Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_po_reg_billing_partner', 'po_reg_bill_wizard_id', 'partner_id', string='Vendor')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_po_reg_billing_warehouse', 'po_reg_bill_wizard_id', 'warehouse_id', string='Warehouse')
    category_ids = fields.Many2many('product.category', 'etc_po_reg_billing_category', 'po_reg_bill_wizard_id', 'category_id', string='Product Category')
    product_ids = fields.Many2many('product.product', 'etc_po_reg_billing_product', 'po_reg_bill_wizard_id', 'product_id', string='Product')
    currency_ids = fields.Many2many('res.currency', 'etc_po_reg_billing_currency', 'po_reg_bill_wizard_id', 'currency_id', string='Currency')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to approve', 'Pending for Approval'),
        ('to_2nd_approve', 'Pending for 2nd Approval'),
        ('done', 'Purchase Order'),
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
        res = super(PoRegisterBillingDetailReportWizard, self).fields_view_get(
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
        pol_obj = self.env['purchase.order.line']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Purchase Orders-Billing Detailed"
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filtered Based on Date From : " + str(from_date) + " , To : " + str(to_date)
        filters = "Filtered Based on Date From : "+ str(from_date) + " , To : "+ str(to_date)
        
        all_partners_children = {}
        all_partner_ids = []
        partner_list = []
        partner_str = ""
        
        all_warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        all_currency_ids = []
        currency_list = []
        currency_str = ""
        
        all_category_ids = []
        category_list = []
        category_str = ""
        
        all_product_ids = []
        product_list = []
        product_str = ""
        
        domain_default = []
        domain_default = [('order_id.date_order', '>=', self.date_from), ('order_id.date_order', '<=', self.date_to),('order_id.invoice_status', '=', 'invoiced')]
        if self.partner_ids:
            for each_id in self.partner_ids:
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id] 
                partner_list.append(each_id.name)
            partner_list = list(set(partner_list))
            partner_str = str(partner_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                domain_default = domain_default + [('order_id.partner_id', 'in', tuple(all_partner_ids))]
                filters += ", Vendor : "+ partner_str
            else:
                domain_default = domain_default + [('order_id.partner_id', '=', all_partner_ids[0])]
                filters += ", Vendor : "+ partner_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                all_warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_warehouse_ids) > 1:
                domain_default = domain_default + [('order_id.warehouse_id', 'in', tuple(all_warehouse_ids))]
                filters += ", Warehouse : "+ warehouse_str
            else:
                domain_default = domain_default + [('order_id.warehouse_id', '=', all_warehouse_ids[0])]
                filters += ", Warehouse : "+ warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    all_warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(all_warehouse_ids) > 1:
                    domain_default = domain_default + [('order_id.warehouse_id', 'in', tuple(all_warehouse_ids))]
                    filters += ", Warehouse : "+ warehouse_str
                else:
                    domain_default = domain_default + [('order_id.warehouse_id', '=', all_warehouse_ids[0])]
                    filters += ", Warehouse : "+ warehouse_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                all_currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_currency_ids) > 1:
                domain_default = domain_default + [('order_id.currency_id', 'in', tuple(all_currency_ids))]
                filters += ", Currency : "+ currency_str
            else:
                domain_default = domain_default + [('order_id.currency_id', '=', all_currency_ids[0])]
                filters += ", Currency : "+ currency_str
        if self.category_ids:
            for each_id in self.category_ids:
                all_category_ids.append(each_id.id)
                category_list.append(each_id.name)
            category_list = list(set(category_list))
            category_str = str(category_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_category_ids) > 1:
                domain_default = domain_default + [('product_id.categ_id', 'in', tuple(all_category_ids))]
                filters += ", Product Category : "+ category_str
            else:
                domain_default = domain_default + [('product_id.categ_id', '=', all_category_ids[0])]
                filters += ", Product Category : "+ category_str
        if self.product_ids:
            for each_id in self.product_ids:
                all_product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_product_ids) > 1:
                domain_default = domain_default + [('product_id', 'in', tuple(all_product_ids))]
                filters += ", Product : "+ product_str
            else:
                domain_default = domain_default + [('product_id', '=', all_product_ids[0])]
                filters += ", Product : "+ product_str
        if self.state:
            if self.state == 'purchase':
                domain_default = domain_default + [('state', 'in', ['purchase', 'done'])]
            elif self.state == 'draft':
                domain_default = domain_default + [('state', 'in', ['draft', 'sent'])]
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
            domain_default = domain_default + [('order_id.state', '!=', 'cancel')]
#        if self.invoice_status:
#            domain_default = domain_default + [('order_id.invoice_status', '=', self.invoice_status)]
#            if self.invoice_status == 'no':
#                filters += ", Billing Status : Nothing to Bill"
#            if self.invoice_status == 'to invoice':
#                filters += ", Billing Status : Waiting Bills"
#            if self.invoice_status == 'invoiced':
#                filters += ", Billing Status : Bills Received"
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(5)
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 5000
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 8000
        sheet1.col(4).width = 7000
        sheet1.col(5).width = 5000
        sheet1.col(6).width = 7500
        sheet1.col(7).width = 8000
        sheet1.col(8).width = 4500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 4500
        sheet1.col(11).width = 4500
        sheet1.col(12).width = 4500
        sheet1.col(13).width = 3000
        sheet1.col(14).width = 3000
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 4000
        sheet1.col(18).width = 4000
        sheet1.col(19).width = 4000
        sheet1.col(20).width = 4000
        sheet1.col(21).width = 8000
        sheet1.col(22).width = 4000
        sheet1.col(23).width = 4000
        sheet1.col(24).width = 5000
        sheet1.col(25).width = 4000
        sheet1.col(26).width = 4000
        sheet1.col(27).width = 4000
        sheet1.col(28).width = 4000
        sheet1.col(29).width = 4000
        sheet1.col(30).width = 4000
        sheet1.col(31).width = 4000
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        r5 = 4
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 200 * 2
        sheet1.row(r5).height = 256 * 3
        title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
        title1 = self.company_id.name
        title2 = filters 
        title3 = 'PO Currency'
        title4 = 'Local Currency' + ' ( ' + str(self.company_id.currency_id.name) + ' )'
        title5 = 'Billing Currency'
        sheet1.write_merge(r1, r1, 0, 31, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 31, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 6, 20, 'Purchase Orders Detailed', Style.groupByTitle())
        sheet1.write_merge(r3, r3, 21, 24, 'Billing Details', Style.groupByTitle())
        sheet1.write_merge(r4, r4, 0, 5, title2, Style.subTitle())
        sheet1.write_merge(r4, r4, 6, 20, title3, Style.subTitle())
        sheet1.write_merge(r4, r4, 21, 23, title5, Style.subTitle())
        sheet1.write_merge(r4, r4, 24, 24, title4, Style.subTitle())
        
        sheet1.write(r5, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 1, "PO No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 2, "PO Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 3, "Vendor", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 4, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 5, "Category Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 6, "Product Category", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 7, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 8, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 9, "Required Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 10, "Approved PR Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 11, "PO Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 12, "Received Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 13, "Returned Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 14, "Quantity to Bill", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 15, "Quantity to Refund", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 16, "Billed Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 17, "Refunded Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 18, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 19, "Unit Price", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 20, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 21, "Bill No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 22, "Unit Price", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 23, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 24, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 25, "PO Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 26, "Billing Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 27, "PO Creator", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 28, "1st Approver", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 29, "Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 30, "2nd Approver", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 31, "Approved Date", Style.contentTextBold(r2,'black','white'))
        
        row = 5
        s_no = 0
        pol_records = pol_obj.sudo().search(domain_default, order="product_id")
        print("\n\n.........domain_default",domain_default)
        print("\n\n.........pol_records",pol_records)
        billing_untaxed_total = 0.00
        for each in pol_records:
            s_row = row
            sheet1.row(row).height = 350
            local_billing_untaxted = 0.00 
            invoice_line_records = each.invoice_lines.filtered(lambda r: r.move_id.state in ['open', 'paid'])
            if invoice_line_records:
                for line in invoice_line_records:
                    if line.invoice_id.type == 'in_invoice':
                        sheet1.write(row, 21, line.invoice_id.number + ' - Regular', Style.normal_left()) 
                        sheet1.write(row, 22, line.price_unit, Style.normal_num_right_4digits())  
                        sheet1.write(row, 23, line.price_subtotal, Style.normal_num_right_3separator())
                        sheet1.write(row, 24, abs(line.price_subtotal_signed and line.price_subtotal_signed or 0.00), Style.normal_num_right_3separator())
                        local_billing_untaxted += abs(line.price_subtotal_signed) 
                    else:
                        sheet1.write(row, 21, line.invoice_id.number + ' - Refund', Style.normal_left()) 
                        sheet1.write(row, 22, line.price_unit, Style.normal_num_right_4digits())  
                        sheet1.write(row, 23, line.price_subtotal, Style.normal_num_right_3separator())
                        sheet1.write(row, 24, -1 * abs(line.price_subtotal_signed and line.price_subtotal_signed or 0.00), Style.normal_num_right_3separator())
                        local_billing_untaxted += -1 * abs(line.price_subtotal_signed) 
                    row = row + 1
            if not invoice_line_records:
                sheet1.write(row, 21, '', Style.normal_left()) 
                sheet1.write(row, 22, '', Style.normal_num_right_4digits())  
                sheet1.write(row, 23, '', Style.normal_num_right_3separator())
                sheet1.write(row, 24, '', Style.normal_num_right_3separator())
                row = row + 1
            row = row - 1  
            s_no = s_no + 1  
            sheet1.write_merge(s_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(s_row, row, 1, 1, each.order_id.name, Style.normal_left())
            update_order_date = ""
            if each.order_id.date_order:
                order_date = each.order_id.date_order.date()  # Extract the date part
                update_order_date = order_date.strftime('%d-%m-%Y')
                # order_date = time.strftime(each.order_id.date_order)
                # order_date = datetime.strptime(order_date, '%Y-%m-%d %H:%M:%S').date()
                # update_order_date = datetime.strftime(order_date, '%d-%m-%Y')
            sheet1.write_merge(s_row, row, 2, 2, update_order_date, Style.normal_left())
            sheet1.write_merge(s_row, row, 3, 3, (each.order_id.partner_id and each.order_id.partner_id.name_get()[0][1] or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 4, 4, (each.order_id.warehouse_id and each.order_id.warehouse_id.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 5, 5, (each.order_id.category_id and each.order_id.category_id.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 6, 6, (each.product_id.categ_id and each.product_id.categ_id.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 7, 7, (each.product_id and each.product_id.name_get()[0][1] or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 8, 8, (each.product_id.uom_id and each.product_id.uom_id.name or ""), Style.normal_left())
            update_required_date = ""
            if each.order_id.date_planned:
                required_date = each.order_id.date_planned.date()  # Extract the date part
                update_required_date = required_date.strftime('%d-%m-%Y')
                # required_date = time.strftime(each.order_id.date_planned)
                # required_date = datetime.strptime(required_date, '%Y-%m-%d %H:%M:%S').date()
                # update_required_date = datetime.strftime(required_date, '%d-%m-%Y')
            sheet1.write_merge(s_row, row, 9, 9, update_required_date, Style.normal_left())
            sheet1.write_merge(s_row, row, 10, 10, each.pr_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(s_row, row, 11, 11, each.product_qty, Style.normal_num_right_3digits())
            sheet1.write_merge(s_row, row, 12, 12, each.qty_received, Style.normal_num_right_3digits())
            sheet1.write_merge(s_row, row, 13, 13, (each.qty_returned and each.qty_returned or 0.00), Style.normal_num_right_3digits())
            sheet1.write_merge(s_row, row, 14, 14, (each.qty_to_invoice and each.qty_to_invoice or 0.00), Style.normal_num_right_3digits())
            sheet1.write_merge(s_row, row, 15, 15, (each.qty_to_refund and each.qty_to_refund or 0.00), Style.normal_num_right_3digits())
            sheet1.write_merge(s_row, row, 16, 16, each.qty_invoiced, Style.normal_num_right_3digits())
            sheet1.write_merge(s_row, row, 17, 17, (each.qty_refunded and each.qty_refunded or 0.00), Style.normal_num_right_3digits())
            sheet1.write_merge(s_row, row, 18, 18, (each.order_id.currency_id and each.order_id.currency_id.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 19, 19, each.price_unit, Style.normal_num_right_4digits())
            sheet1.write_merge(s_row, row, 20, 20, each.price_subtotal, Style.normal_num_right_3separator())
            state = ""
            if each.order_id.state in ['draft', 'sent']:
                state = "Draft"
            if each.order_id.state == 'to approve':
                state = "Pending for Approval"
            if each.order_id.state == 'to_2nd_approve':
                state = "Pending for 2nd Approval"
            if each.order_id.state in ['purchase', 'done']:
                state = "Purchase Order"
            if each.order_id.state == 'cancel':
                state = "Cancelled"
            sheet1.write_merge(s_row, row, 25, 25, state, Style.normal_left())
            invoice_status = ""
            if each.order_id.invoice_status == 'no':
                invoice_status = "Nothing to Bill"
            if each.order_id.invoice_status == 'to invoice':
                invoice_status = "Waiting Bills"
            if each.order_id.invoice_status == 'invoiced':
                invoice_status = "Bills Received"
            sheet1.write_merge(s_row, row, 26, 26, invoice_status, Style.normal_left())
            sheet1.write_merge(s_row, row, 27, 27, (each.order_id.create_uid and each.order_id.create_uid.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 28, 28, (each.order_id.one_approved_id and each.order_id.one_approved_id.name or ""), Style.normal_left())
            update_first_approved_date = ""
            if each.order_id.one_approved_date:
                first_approved_date = each.order_id.one_approved_date.date()  # Extract the date part
                update_first_approved_date = first_approved_date.strftime('%d-%m-%Y')
                # first_approved_date = time.strftime(each.order_id.one_approved_date)
                # first_approved_date = datetime.strptime(first_approved_date, '%Y-%m-%d %H:%M:%S').date()
                # update_first_approved_date = datetime.strftime(first_approved_date, '%d-%m-%Y')
            sheet1.write_merge(s_row, row, 29, 29, update_first_approved_date, Style.normal_left())
            sheet1.write_merge(s_row, row, 30, 30, (each.order_id.two_approved_id and each.order_id.two_approved_id.name or ""), Style.normal_left())
            update_second_approved_date = ""
            if each.order_id.two_approved_date:
                second_approved_date = each.order_id.second_approved_date.date()  # Extract the date part
                update_second_approved_date = second_approved_date.strftime('%d-%m-%Y')
                # second_approved_date = time.strftime(each.order_id.two_approved_date)
                # second_approved_date = datetime.strptime(second_approved_date, '%Y-%m-%d %H:%M:%S').date()
                # update_second_approved_date = datetime.strftime(second_approved_date, '%d-%m-%Y')
            sheet1.write_merge(s_row, row, 31, 31, update_second_approved_date, Style.normal_left())
            row = row + 1
            sheet1.write(row, 24, local_billing_untaxted, Style.groupByTotal3Separator()) 
            row = row + 1
            billing_untaxed_total += local_billing_untaxted
        sheet1.write_merge(row, row, 0, 23, 'Grand Total', Style.groupByTitle())
        sheet1.write(row, 24, billing_untaxed_total, Style.groupByTotal3Separator())

        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()

        self.write({'name': report_name + '.xls', 'output': base64.encodebytes(binary_data)})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'po.register.billing.detail.register.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
