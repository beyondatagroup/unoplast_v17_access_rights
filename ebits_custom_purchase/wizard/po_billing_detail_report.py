# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
import io
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

class PoBillingDetailReportWizard(models.TransientModel):
    _name = 'po.billing.detail.report.wizard'
    _description = 'Purchase Order Billing Detail Report Wizard'
    
    date_from = fields.Date(string='From Date(Order Date)', required=True)
    date_to= fields.Date(string='To Date(Order Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_po_billing_partner', 'po_billing_wizard_id', 'partner_id', string='Vendor')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_po_billing_warehouse', 'po_billing_wizard_id', 'warehouse_id', string='Warehouse')
    currency_ids = fields.Many2many('res.currency', 'etc_po_billing_currency', 'po_billing_wizard_id', 'currency_id', string='Currency')
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
        res = super(PoBillingDetailReportWizard, self).fields_view_get(
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
        po_obj = self.env['purchase.order']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "Purchase Orders-Billing"
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
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
        
        domain_default = []
        domain_default = [('date_order', '>=',  self.date_from), ('date_order', '<=', self.date_to), ('invoice_status', '=', 'invoiced')]
        if self.partner_ids:
            for each_id in self.partner_ids:
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id] 
                partner_list.append(each_id.name)
            partner_list = list(set(partner_list))
            partner_str = str(partner_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                domain_default = domain_default + [('partner_id', 'in', tuple(all_partner_ids))]
                filters += ", Vendor : "+ partner_str
            else:
                domain_default = domain_default + [('partner_id', '=', all_partner_ids[0])]
                filters += ", Vendor : "+ partner_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                all_warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_warehouse_ids) > 1:
                domain_default = domain_default + [('warehouse_id', 'in', tuple(all_warehouse_ids))]
                filters += ", Warehouse : "+ warehouse_str
            else:
                domain_default = domain_default + [('warehouse_id', '=', all_warehouse_ids[0])]
                filters += ", Warehouse : "+ warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    all_warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(all_warehouse_ids) > 1:
                    domain_default = domain_default + [('warehouse_id', 'in', tuple(all_warehouse_ids))]
                    filters += ", Warehouse : "+ warehouse_str
                else:
                    domain_default = domain_default + [('warehouse_id', '=', all_warehouse_ids[0])]
                    filters += ", Warehouse : "+ warehouse_str
                    
        if self.currency_ids:
            for each_id in self.currency_ids:
                all_currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_currency_ids) > 1:
                domain_default = domain_default + [('currency_id', 'in', tuple(all_currency_ids))]
                filters += ", Currency : "+ currency_str
            else:
                domain_default = domain_default + [('currency_id', '=', all_currency_ids[0])]
                filters += ", Currency : "+ currency_str
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
            domain_default = domain_default + [('state', 'in', ['purchase', 'done'])]
                
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(5)
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3000
        sheet1.col(2).width = 3500
        sheet1.col(3).width = 5000
        sheet1.col(4).width = 5000
        sheet1.col(5).width = 5000
        sheet1.col(6).width = 3500
        sheet1.col(7).width = 4000
        sheet1.col(8).width = 4000
        sheet1.col(9).width = 4000
        sheet1.col(10).width = 6000
        sheet1.col(11).width = 3500
        sheet1.col(12).width = 3500
        sheet1.col(13).width = 3500
        sheet1.col(14).width = 3500
        sheet1.col(15).width = 3500
        sheet1.col(16).width = 3500
        sheet1.col(17).width = 3500
        sheet1.col(18).width = 3500
        sheet1.col(19).width = 3500
        sheet1.col(20).width = 3500
        sheet1.col(21).width = 3500
        sheet1.col(22).width = 3500
        sheet1.col(23).width = 3500
        sheet1.col(24).width = 3500
        sheet1.col(25).width = 3500
        sheet1.col(26).width = 4500
        sheet1.col(27).width = 4500
        sheet1.col(28).width = 4500
    
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
        sheet1.write_merge(r1, r1, 0, 28, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 28, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 6, 9, 'Purchase Orders Details', Style.groupByTitle())
        sheet1.write_merge(r3, r3, 10, 16, 'Billing Details', Style.groupByTitle())
        sheet1.write_merge(r4, r4, 0, 5, title2, Style.subTitle())
        sheet1.write_merge(r4, r4, 6, 9, title3, Style.subTitle())
        sheet1.write_merge(r4, r4, 10, 13, title5, Style.subTitle())
        sheet1.write_merge(r4, r4, 14, 16, title4, Style.subTitle())
        
        sheet1.write(r5, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 1, "PO No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 2, "PO Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 3, "Vendor", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 4, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 5, "Category Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 6, "PO Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 7, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 8, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 9, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 10, "Bill No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 11, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 12, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 13, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 14, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 15, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 16, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 17, "ETA", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 18, "ETD", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 19, "PO Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 20, "Billing Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 21, "PO Creator", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 22, "1st Approver", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 23, "Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 24, "2nd Approver", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 25, "Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 26, " Payment Terms ", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 27, " Mode of Shipment ", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r5, 28, " Delivery Location ", Style.contentTextBold(r2,'black','white'))
        
        row = 5
        s_no = 0
        billing_untaxed_total = billing_tax_total = billing_total = 0.00  
        po_records = po_obj.sudo().search(domain_default, order="date_order desc") 
        for each in po_records:
            s_row = row
            sheet1.row(row).height = 500
            invoice_records = each.invoice_ids.filtered(lambda r: r.state_1 in ['open', 'paid'])
            print("invoice_records>>>>>>>>",invoice_records)
            local_billing_untaxted = local_billing_tax = locl_billing_total = 0.00
            for line in invoice_records:
                if line.move_type == 'in_invoice':
                    print("line.----------------------------",line.name)
                    sheet1.write(row, 10, line.name + ' - Regular', Style.normal_left())
                    sheet1.write(row, 11, line.amount_untaxed, Style.normal_num_right_3separator()) 
                    sheet1.write(row, 12, line.amount_tax, Style.normal_num_right_3separator())
                    sheet1.write(row, 13, line.amount_total, Style.normal_num_right_3separator())
                    sheet1.write(row, 14, abs(line.amount_untaxed_signed), Style.normal_num_right_3separator()) 
                    sheet1.write(row, 15, abs(line.company_amount_tax), Style.normal_num_right_3separator())
                    sheet1.write(row, 16, abs(line.company_amount_total), Style.normal_num_right_3separator())
                    row = row + 1
                    local_billing_untaxted += abs(line.amount_untaxed_signed)
                    local_billing_tax += abs(line.company_amount_tax)
                    locl_billing_total += abs(line.company_amount_total)
                else:
                    sheet1.write(row, 10, line.name + ' - Refund', Style.normal_left())
                    sheet1.write(row, 11, -1 * line.amount_untaxed, Style.normal_num_right_3separator()) 
                    sheet1.write(row, 12, -1 * line.amount_tax, Style.normal_num_right_3separator())
                    sheet1.write(row, 13, -1 * line.amount_total, Style.normal_num_right_3separator())
                    sheet1.write(row, 14, -1 * abs(line.amount_untaxed_signed), Style.normal_num_right_3separator()) 
                    sheet1.write(row, 15, -1 * abs(line.company_amount_tax), Style.normal_num_right_3separator())
                    sheet1.write(row, 16, -1 * abs(line.company_amount_total), Style.normal_num_right_3separator())
                    row = row + 1
                    local_billing_untaxted += -1 * abs(line.amount_untaxed_signed)
                    local_billing_tax += -1 * abs(line.company_amount_tax)
                    locl_billing_total += -1 * abs(line.company_amount_total)
            if not invoice_records:
                sheet1.write(row, 10, '', Style.normal_left())
                sheet1.write(row, 11, '', Style.normal_num_right_3separator()) 
                sheet1.write(row, 12, '', Style.normal_num_right_3separator())
                sheet1.write(row, 13, '', Style.normal_num_right_3separator())
                sheet1.write(row, 14, '', Style.normal_num_right_3separator()) 
                sheet1.write(row, 15, '', Style.normal_num_right_3separator())
                sheet1.write(row, 16, '', Style.normal_num_right_3separator())
                row = row + 1
            s_no = s_no + 1
            row = row - 1
            sheet1.write_merge(s_row, row, 0, 0, s_no, Style.normal_left())
            sheet1.write_merge(s_row, row, 1, 1, each.name, Style.normal_left())
            update_order_date = ""
            print("\n\n ............each",each)
            if each.date_order:
                # Assuming each.date_order is a datetime object
                order_date = each.date_order.date()  # Extract the date part from datetime
                update_order_date = order_date.strftime('%d-%m-%Y')  # Convert date to desired string format
            sheet1.write_merge(s_row, row, 2, 2, update_order_date, Style.normal_left())
            sheet1.write_merge(s_row, row, 3, 3, (each.partner_id and each.partner_id.name_get()[0][1] or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 4, 4, (each.warehouse_id and each.warehouse_id.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 5, 5, (each.category_id and each.category_id.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 6, 6, (each.currency_id and each.currency_id.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 7, 7, each.amount_untaxed, Style.normal_num_right_3separator())
            sheet1.write_merge(s_row, row, 8, 8, each.amount_tax, Style.normal_num_right_3separator())
            sheet1.write_merge(s_row, row, 9, 9, each.amount_total, Style.normal_num_right_3separator())
            arrival_time = ""
            if each.arrival_time:
                arrival_time = each.arrival_time
                arrival_time = arrival_time.strftime('%d-%m-%Y')
                # arrival_time = time.strptime(each.arrival_time, "%Y-%m-%d")
                # arrival_time = time.strftime('%d-%m-%Y', arrival_time)
            sheet1.write_merge(s_row, row, 17, 17, arrival_time, Style.normal_left())
            depature_time = ""
            if each.depature_time:
                depature_time = each.depature_time
                depature_time = depature_time.strftime('%d-%m-%Y')

                # depature_time = time.strptime(each.depature_time, "%Y-%m-%d")
                # depature_time = time.strftime('%d-%m-%Y', depature_time)
            sheet1.write_merge(s_row, row, 18, 18, depature_time, Style.normal_left())
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
            sheet1.write_merge(s_row, row, 19, 19, state, Style.normal_left())
            invoice_status = ""
            if each.invoice_status == 'no':
                invoice_status = "Nothing to Bill"
            if each.invoice_status == 'to invoice':
                invoice_status = "Waiting Bills"
            if each.invoice_status == 'invoiced':
                invoice_status = "Bills Received"
            sheet1.write_merge(s_row, row, 20, 20, invoice_status, Style.normal_left())
            sheet1.write_merge(s_row, row, 21, 21, (each.create_uid and each.create_uid.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 22, 22, each.one_approved_id.name, Style.normal_left())
            update_first_approved_date = ""
            if each.one_approved_date:
                # Assuming each.one_approved_date is a datetime object
                first_approved_date = each.one_approved_date.date()  # Extract the date part
                update_first_approved_date = first_approved_date.strftime('%d-%m-%Y')
            sheet1.write_merge(s_row, row, 23, 23, update_first_approved_date, Style.normal_left())
            sheet1.write_merge(s_row, row, 24, 24, (each.two_approved_id and each.two_approved_id.name or ""), Style.normal_left())
            update_second_approved_date = ""
            if each.two_approved_date:
                second_approved_date = each.two_approved_date.date()
                # second_approved_date = time.strftime(each.two_approved_date)
                # second_approved_date = datetime.strptime(second_approved_date, '%Y-%m-%d %H:%M:%S').date()
                update_second_approved_date = datetime.strftime(second_approved_date, '%d-%m-%Y') 
            sheet1.write_merge(s_row, row, 25, 25, update_second_approved_date, Style.normal_left())
            sheet1.write_merge(s_row, row, 26, 26, (each.payment_term_id and each.payment_term_id.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 27, 27, (each.shipping_mode_id and each.shipping_mode_id.name or ""), Style.normal_left())
            sheet1.write_merge(s_row, row, 28, 28, (each.delivery_location and each.delivery_location or ""), Style.normal_left())
            row = row + 1
            sheet1.write(row, 14, local_billing_untaxted, Style.groupByTotal3Separator())
            sheet1.write(row, 15, local_billing_tax, Style.groupByTotal3Separator())
            sheet1.write(row, 16, locl_billing_total, Style.groupByTotal3Separator())
            billing_untaxed_total += local_billing_untaxted
            billing_tax_total += local_billing_tax 
            billing_total += locl_billing_total 
            row = row + 1
        
        sheet1.write_merge(row, row, 0, 13, 'Grand Total', Style.groupByTitle())
        sheet1.write(row, 14, billing_untaxed_total, Style.groupByTotal3Separator())
        sheet1.write(row, 15, billing_tax_total, Style.groupByTotal3Separator())
        sheet1.write(row, 16, billing_total, Style.groupByTotal3Separator())

        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()

        self.write({ 'name': report_name +'.xls', 'output':base64.encodebytes(binary_data)})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'po.billing.detail.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
