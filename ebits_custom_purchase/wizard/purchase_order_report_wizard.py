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
import io
import base64
import xlrd

from lxml import etree
import io

class PurchaseOrderReportWizard(models.TransientModel):
    _name = 'purchase.order.report.wizard'
    _description = 'Purchase Order Report Wizard'
    
    date_from= fields.Date(string='From Date(Order Date)', required=True)
    date_to= fields.Date(string='To Date(Order Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_purchase_order_partner', 'purchase_order_wizard_id', 'partner_id', string='Vendor')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_purchase_order_warehouse', 'purchase_order_wizard_id', 'warehouse_id', string='Warehouse')
    currency_ids = fields.Many2many('res.currency', 'etc_purchase_order_currency', 'purchase_order_wizard_id', 'currency_id', string='Currency')
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
    output= fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PurchaseOrderReportWizard, self).fields_view_get(
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
        report_name = "Purchase Orders List"
        print("\n\n......date_from......",date_from)
        print("\n\n......date_to......",date_to)
        from_date_str = self.date_from.strftime('%Y-%m-%d')
        from_date = time.strptime(from_date_str, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)

        # Similarly for date_to if needed
        to_date_str = self.date_to.strftime('%Y-%m-%d')
        to_date = time.strptime(to_date_str, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filtered Based on Date From : "+ str(from_date) + " , To : "+ str(to_date)
        partner_sql = """ """
        warehouse_sql = """ """
        currency_sql = """ """
        po_status_sql = """ """
        billing_status_sql = """ """
        
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
                partner_sql += " and po.partner_id in "+ str(all_partner_ids)
            else:
                partner_sql += " and po.partner_id in ("+ str(all_partner_ids[0]) + ")"
            filters += ", Vendor: " + customer_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(warehouse_ids) > 1:
                warehouse_sql += "and po.warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_sql += "and po.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
            filters += ", Warehouse: " + warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(warehouse_ids) > 1:
                    warehouse_sql += "and po.warehouse_id in "+ str(tuple(warehouse_ids))
                else:
                    warehouse_sql += "and po.warehouse_id in ("+ str(warehouse_ids[0]) + ")"
                filters += ", Warehouse: " + warehouse_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(currency_ids) > 1:
                currency_sql += "and po.currency_id in "+ str(tuple(currency_ids))
            else:
                currency_sql += "and po.currency_id in ("+ str(currency_ids[0]) + ")"
            filters += ", Currency: " + currency_str  
        if self.state:
            if self.state in ['done', 'purchase']:
                po_status_sql = " and po.state in ('purchase', 'done')" 
            elif self.state in ['draft', 'sent']:
                po_status_sql = " and po.state in ('draft', 'sent')" 
            else:
                po_status_sql = " and po.state = " + "'" + str(self.state) + "'"
            if self.state in ['draft', 'sent']:
                filters += ", State : Draft"
            if self.state == 'to approve':
                filters += ", State : Pending for Approval"
            if self.state == 'to_2nd_approve':
                filters += ", State : Pending for 2nd Approval"
            if self.state in ['purchase', 'done']:
                filters += ", State : Purchase Order"
            if self.state == 'cancel':
                filters += ", PO Status : Cancelled"
        else:
            po_status_sql = " and po.state != 'cancel'" 
        if self.invoice_status:
            billing_status_sql = " and po.invoice_status = " + "'" + str(self.invoice_status) + "'"
            if self.invoice_status == 'no':
                filters += ", Billing Status : Nothing to Bill"
            if self.invoice_status == 'to invoice':
                filters += ", Billing Status : Waiting Bills"
            if self.invoice_status == 'invoiced':
                filters += ", Billing Status : Bills Received"
        pur_order_sql = """ select 
	                            po.name as po_no,
	                            ((po.date_order at time zone %s)::timestamp::date) as po_date,
	                            po.id as id,
	                            rp.name as vendor,
	                            sw.name as warehouse,
	                            category.name as req_type,
	                            rc.name as po_currency,
	                            po.amount_untaxed as untaxed_amt,
	                            (case when po.amount_tax > 0 then po.amount_tax else 0.00 end) as tax_amount,
	                            ((case when po.amount_tax > 0 then po.amount_tax else 0.00 end)/
	                            (case when po.amount_untaxed > 0 then po.amount_untaxed else 1.00 end) * 100.00) as tax_percentage,
	                            po.amount_total as total_amount,
	                            po.arrival_time as arrival_time,
	                            po.depature_time as depature_time,
	                            (case when po.state = 'draft' then 'Draft' 
	                             when po.state = 'sent' then 'Draft'
	                             when po.state = 'to approve' then 'Pending for Approval'
	                             when po.state = 'to_2nd_approve' then 'Pending for 2nd Approval'
	                             when po.state = 'purchase' then 'Purchase Order'
	                             when po.state = 'done' then 'Purchase Order'
	                             when po.state = 'cancel' then 'Cancelled' else po.state end) as po_status,
	                            (case when po.invoice_status = 'no' then 'Nothing to Bill' 
	                             when po.invoice_status = 'to invoice' then 'Waiting Bills'
	                             when po.invoice_status = 'invoiced' then 'Bills Received' else po.invoice_status end) as billing_status,
	                             po_creator_rp.name as po_creator,
	                             apt.name as payment_term,
	                             psm.name as shipping_mode,
	                             po.delivery_location as delivery_location,
	                             one_rp.name as first_approver,
	                             ((po.one_approved_date at time zone %s)::timestamp::date) as first_approved_date,
                                 two_rp.name as second_approver,
	                             ((po.two_approved_date at time zone %s)::timestamp::date) as second_approved_date
                            from purchase_order po
	                            left join res_partner rp on (rp.id = po.partner_id)
	                            left join stock_warehouse sw on (sw.id = po.warehouse_id)
	                            left join purchase_category category on (category.id = po.category_id)
	                            left join res_currency rc on (rc.id = po.currency_id)
	                            left join res_users one_approver on (one_approver.id = po.one_approved_id)
	                            left join res_partner one_rp on (one_rp.id = one_approver.partner_id)
	                            left join res_users two_approver on (two_approver.id = po.two_approved_id)
	                            left join res_partner two_rp on (two_rp.id = two_approver.partner_id)
	                            left join res_users po_create on (po_create.id = po.create_uid)
	                            left join res_partner po_creator_rp on (po_creator_rp.id = po_create.partner_id)
	                            left join account_payment_term apt on (apt.id = po.payment_term_id)
	                            left join po_shipping_mode psm on (psm.id = po.shipping_mode_id)
                            where
	                            (((po.date_order at time zone %s)::timestamp::date) between %s and %s)""" + partner_sql + warehouse_sql + currency_sql + po_status_sql + billing_status_sql + """ group by
                                		rp.name,
	                                    po.name,
	                                    po.date_order,
	                                    psm.name,
	                                    po.delivery_location,
	                                    po.id,
	                                    sw.name,
	                                    apt.name,
	                                    rc.name,
	                                    category.name,
	                                    po.amount_tax,
	                                    po.amount_total,
	                                    po.arrival_time,
	                                    po.depature_time,
	                                    po_status,
	                                    billing_status,
	                                    one_rp.name,
	                                    po.one_approved_date,
	                                    two_rp.name,
	                                    po.two_approved_date,
	                                    po_creator_rp.name 
                                order by
	                                   po.date_order desc, po.name desc"""
        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'                        
        
        self.env.cr.execute(pur_order_sql , (tz, tz, tz, tz, date_from, date_to,))
        pur_order_data = self.env.cr.dictfetchall()
        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
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
        sheet1.col(10).width = 3000
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
        sheet1.write_merge(rc, rc, 0, 21, title1, Style.main_title())
        sheet1.write_merge(r1, r1, 0, 21, title, Style.sub_main_title())
        sheet1.write_merge(r2, r2, 0, 21, title2, Style.subTitle())
        
        sheet1.write(r3, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 1, "PO No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 2, "PO Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 3, "Vendor", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 4, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 5, "Category Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 6, "PO Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 7, "Untaxed Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 8, "Tax Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 9, "Total Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 10, "ETA", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 11, "ETD", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 12, "PO Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 13, "Billing Status", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 14, "PO Creator", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 15, "1st Approver", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 16, "Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 17, "2nd Approver", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 18, "Approved Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 19, "Payment Terms", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 20, "Mode of Shipment", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r3, 21, "Delivery Location", Style.contentTextBold(r2,'black','white'))
        
        row = r3
        s_no = 0
        for each in pur_order_data:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 600
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, each['po_no'], Style.normal_left())
            po_date = ""
            if each['po_date']:
                po_date_str = each['po_date'].strftime("%Y-%m-%d")  # Convert to string
                po_date = time.strptime(po_date_str, "%Y-%m-%d")
                # po_date = time.strptime(each['po_date'], "%Y-%m-%d")
                po_date = time.strftime('%d-%m-%Y', po_date)
            sheet1.write(row, 2, po_date, Style.normal_left())
            sheet1.write(row, 3, each['vendor'], Style.normal_left())
            sheet1.write(row, 4, each['warehouse'], Style.normal_left())
            sheet1.write(row, 5, each['req_type'], Style.normal_left())
            sheet1.write(row, 6, each['po_currency'], Style.normal_left())
            sheet1.write(row, 7, each['untaxed_amt'], Style.normal_num_right_3separator())
            sheet1.write(row, 8, each['tax_amount'], Style.normal_num_right_3separator())
            sheet1.write(row, 9, each['total_amount'], Style.normal_num_right_3separator())
            arrival_time = ""
            if each['arrival_time']:
                arrival_time_str = each['arrival_time'].strftime("%Y-%m-%d")
                arrival_time = time.strptime(arrival_time_str, "%Y-%m-%d")
                arrival_time = time.strftime('%d-%m-%Y', arrival_time) 
            sheet1.write(row, 10, arrival_time, Style.normal_left())
            depature_time = ""
            print("\n\n...........each",each)
            if each['depature_time']:
                depature_time_str = each['depature_time'].strftime("%Y-%m-%d")
                depature_time = time.strptime(depature_time_str, "%Y-%m-%d")
                depature_time = time.strftime('%d-%m-%Y', depature_time) 
            sheet1.write(row, 11, depature_time, Style.normal_left())
            sheet1.write(row, 12, each['po_status'], Style.normal_left())
            sheet1.write(row, 13, each['billing_status'], Style.normal_left())
            sheet1.write(row, 14, each['po_creator'], Style.normal_left())
            sheet1.write(row, 15, each['first_approver'], Style.normal_left())
            first_approved_date = ""
            if each['first_approved_date']:
                first_approved_date_str = each['first_approved_date'].strftime("%Y-%m-%d")
                first_approved_date = time.strptime(first_approved_date_str, "%Y-%m-%d")
                first_approved_date = time.strftime('%d-%m-%Y', first_approved_date)
            sheet1.write(row, 16, first_approved_date, Style.normal_left())
            sheet1.write(row, 17, each['second_approver'], Style.normal_left())
            second_approved_date = ""
            if each['second_approved_date']:
                second_approved_date_str = each['first_approved_date'].strftime("%Y-%m-%d")

                second_approved_date = time.strptime(second_approved_date_str, "%Y-%m-%d")
                second_approved_date = time.strftime('%d-%m-%Y', second_approved_date)
            sheet1.write(row, 18, each['second_approved_date'], Style.normal_left())
            print("\n\n........ each['payment_term']..", each['payment_term'])
            sheet1.write(row, 19, each['payment_term']['en_US'], Style.normal_left())
            sheet1.write(row, 20, each['shipping_mode'], Style.normal_left())
            sheet1.write(row, 21, each['delivery_location'], Style.normal_left())

        # stream = cStringIO.StringIO()
        # stream = io.BytesIO()
        # wbk.save(stream)
        # binary_data = stream.getvalue()
        #
        # # stream = io.StringIO()
        # # wbk.save(stream)
        # self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(binary_data)})
        stream = io.BytesIO()
        wbk.save(stream)
        binary_data = stream.getvalue()

        # Use encodebytes instead of encodestring
        self.write({'name': report_name + '.xls', 'output': base64.encodebytes(binary_data)})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'purchase.order.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
