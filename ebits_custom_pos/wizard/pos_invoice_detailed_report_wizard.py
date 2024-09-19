# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
import xlwt
import cStringIO
import base64
import xlrd
import parser
from lxml import etree

class PosDetailedReportWizard(models.TransientModel):
    _name = 'pos.detailed.report.wizard'
    _description = 'POS Detailed Report Wizard'
    
    date_from= fields.Date(string='From Date(Invoice Date)', required=True)
    date_to= fields.Date(string='To Date(Invoice Date)', required=True)
    partner_ids = fields.Many2many('res.partner', 'etc_pos_detailed_partner', 'pos_wizard_id', 'partner_id', string='Customer')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_pos_detailed_warehouse', 'pos_wizard_id', 'warehouse_id',  string='Warehouse')
    user_ids = fields.Many2many('res.users', 'etc_pos_detailed_users', 'pos_wizard_id', 'user_id', string='Sales Manager')
    currency_ids = fields.Many2many('res.currency', 'etc_pos_detailed_currency', 'pos_wizard_id', 'currency_id', string='Currency')
    journal_ids = fields.Many2many('account.journal', 'etc_pos_detailed_journal', 'pos_wizard_id', 'journal_id', string='Journal')
    product_ids = fields.Many2many('product.product', 'etc_pos_detailed_product', 'pos_wizard_id', 'product_id', string='Product')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    # @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PosDetailedReportWizard, self).fields_view_get(
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
        pos_obj = self.env['pos.order']
        date_from = self.date_from
        date_to = self.date_to
        report_name = "POS Invoice Detailed Report"
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime('%d-%m-%Y', from_date)
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime('%d-%m-%Y', to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date) 
        
        all_partners_children = {}
        all_partner_ids = []
        partner_list = []
        partner_str = ""
        
        all_warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        
        all_user_ids = []
        user_list = []
        user_str = ""
        
        all_currency_ids = []
        currency_list = []
        currency_str = ""
        
        all_journal_ids = []
        journal_list = []
        journal_str = ""
        
        all_product_ids = []
        product_list = []
        product_str = ""
        
        domain_pos = []
        domain_pos = [('date_order', '>=',  self.date_from), ('date_order', '<=',  self.date_to), ('state', 'in', ('paid', 'done'))]
        
        if self.partner_ids:
            for each_id in self.partner_ids:
                all_partners_children[each_id.id] = self.env['res.partner'].sudo().search([('id', 'child_of', each_id.id)]).ids
                all_partner_ids += all_partners_children[each_id.id] 
                partner_list.append(each_id.name)
            partner_list = list(set(partner_list))
            partner_str = str(partner_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_partner_ids) > 1:
                domain_pos = domain_pos + [('partner_id', 'in', tuple(all_partner_ids))]
                filters += ", Customer : "+ partner_str
            else:
                domain_pos = domain_pos + [('partner_id', '=', all_partner_ids[0])]
                filters += ", Customer : "+ partner_str
        if self.warehouse_ids:
            for each_id in self.warehouse_ids:
                all_warehouse_ids.append(each_id.id)
                warehouse_list.append(each_id.name)
            warehouse_list = list(set(warehouse_list))
            warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_warehouse_ids) > 1:
                domain_pos = domain_pos + [('session_id.config_id.warehouse_id', 'in', tuple(all_warehouse_ids))]
                filters += ", Warehouse : "+ warehouse_str
            else:
                domain_pos = domain_pos + [('session_id.config_id.warehouse_id', '=', all_warehouse_ids[0])]
                filters += ", Warehouse : "+ warehouse_str
        else:
            if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
                for each in self.env.user.sudo().default_warehouse_ids:
                    all_warehouse_ids.append(each.id)
                    warehouse_list.append(each.name)
                warehouse_list = list(set(warehouse_list))
                warehouse_str = str(warehouse_list).replace('[','').replace(']','').replace("u'","").replace("'","")
                if len(all_warehouse_ids) > 1:
                    domain_pos = domain_pos + [('session_id.config_id.warehouse_id', 'in', tuple(all_warehouse_ids))]
                    filters += ", Warehouse : "+ warehouse_str
                else:
                    domain_pos = domain_pos + [('session_id.config_id.warehouse_id', '=', all_warehouse_ids[0])]
                    filters += ", Warehouse : "+ warehouse_str
        if self.user_ids:
            for each_id in self.user_ids:
                all_user_ids.append(each_id.id)
                user_list.append(each_id.name)
            user_list = list(set(user_list))
            user_str = str(user_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_user_ids) > 1:
                domain_pos = domain_pos + [('user_id', 'in', tuple(all_user_ids))]
                filters += ", Sales Manager : "+ user_str
            else:
                domain_pos = domain_pos + [('user_id', '=', all_user_ids[0])]
                filters += ", Sales Manager : "+ user_str
        if self.currency_ids:
            for each_id in self.currency_ids:
                all_currency_ids.append(each_id.id)
                currency_list.append(each_id.name)
            currency_list = list(set(currency_list))
            currency_str = str(currency_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_currency_ids) > 1:
                domain_pos = domain_pos + [('pricelist_id.currency_id', 'in', tuple(all_currency_ids))]
                filters += ", currency : "+ currency_str
            else:
                domain_pos = domain_pos + [('pricelist_id.currency_id', '=', all_currency_ids[0])]
                filters += ", currency : "+ currency_str
        if self.product_ids:
            for each_id in self.product_ids:
                all_product_ids.append(each_id.id)
                product_list.append(each_id.name)
            product_list = list(set(product_list))
            product_str = str(product_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_product_ids) > 1:
                domain_pos = domain_pos + [('lines.product_id', 'in', tuple(all_product_ids))]
                filters += ", product : "+ product_str
            else:
                domain_pos = domain_pos + [('lines.product_id', '=', all_product_ids[0])]
                filters += ", product : "+ product_str
        if self.journal_ids:
            for each_id in self.journal_ids:
                all_journal_ids.append(each_id.id)
                journal_list.append(each_id.name)
            journal_list = list(set(journal_list))
            journal_str = str(journal_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            if len(all_journal_ids) > 1:
                domain_pos = domain_pos + [('sale_journal', 'in', tuple(all_journal_ids))]
                filters += ", Journal : "+ journal_str
            else:
                domain_pos = domain_pos + [('sale_journal', '=', all_journal_ids[0])]
                filters += ", Journal : "+ journal_str
            
        pos_record = pos_obj.sudo().search(domain_pos, order="date_order, name")
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 3500
        sheet1.col(2).width = 6500
        sheet1.col(3).width = 3000
        sheet1.col(4).width = 4000
        sheet1.col(5).width = 3500
        sheet1.col(6).width = 10000
        sheet1.col(7).width = 5000
        sheet1.col(8).width = 4500
        sheet1.col(9).width = 4500
        sheet1.col(10).width = 4000
        sheet1.col(11).width = 5500
        sheet1.col(12).width = 5000
        sheet1.col(13).width = 8000
        sheet1.col(14).width = 4000
        sheet1.col(15).width = 4000
        sheet1.col(16).width = 3000
        sheet1.col(17).width = 3000
        sheet1.col(18).width = 3000
        sheet1.col(19).width = 4500
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 256 * 3
        title = report_name +' ( Date From ' + from_date + ' To ' + to_date + ' )'
        title1 = self.company_id.name
        title2 = filters 
        sheet1.write_merge(r1, r1, 0, 19, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, 19, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, 19, title2, Style.subTitle())
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 1, "Type", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 2, "Warehouse", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 3, "Invoice No", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 4, "Invoice Date", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 5, "Customer", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 6, "Delivery Address", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 7, "Created By", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 8, "Sales Manager", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 9, "Sales Person", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 10, "Journal", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 11, "Reference", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 12, "Currency", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 13, "Product", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 14, "Quantity", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 15, "UOM", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 16, "Unit Price", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 17, "Discount (%)", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 18, "Subtotal W/O TAX Amount", Style.contentTextBold(r2,'black','white'))
        sheet1.write(r4, 19, "Subtotal With TAX Amount", Style.contentTextBold(r2,'black','white'))
            
        row = r4
        s_no = 0
        pos_local_inv_amt_without_tax = 0.00
        pos_local_inv_amt_with_tax = 0.00
        for each_pos in pos_record:
            row = row + 1
            s_no = s_no + 1
            sheet1.row(row).height = 500
            sheet1.write(row, 0, s_no, Style.normal_left())
            if each_pos.amount_untaxed >= 0.00:
                sheet1.write(row, 1, 'POS Regular', Style.normal_left())
            else:
                sheet1.write(row, 1, 'POS Refund', Style.normal_left())
            sheet1.write(row, 2, (each_pos.session_id.config_id.warehouse_id and each_pos.session_id.config_id.warehouse_id.name or ""), Style.normal_left())
            sheet1.write(row, 3, (each_pos.name and each_pos.name or ""), Style.normal_left())
            update_order_date = ""
            if each_pos.date_order:
                order_date = time.strftime(each_pos.date_order) 
                order_date = datetime.strptime(order_date, '%Y-%m-%d %H:%M:%S').date() 
                update_order_date = datetime.strftime(order_date, '%d-%m-%Y')
            sheet1.write(row, 4, update_order_date, Style.normal_left())
            partner_name = ""
            partner_name = (each_pos.partner_id and each_pos.partner_id.name or "") + " - " + (each_pos.partner_name and each_pos.partner_name or "")
            sheet1.write(row, 5, partner_name, Style.normal_left())
            sheet1.write(row, 6, (each_pos.partner_address and each_pos.partner_address or ""), Style.normal_left())
            sheet1.write(row, 7, (each_pos.user_id and each_pos.user_id.name or ""), Style.normal_left())
            sheet1.write(row, 8, "", Style.normal_left())
            sheet1.write(row, 9, (each_pos.user_id and each_pos.user_id.name or ""), Style.normal_left())
            sheet1.write(row, 10, (each_pos.sale_journal and each_pos.sale_journal.name or ""), Style.normal_left())
            sheet1.write(row, 11, (each_pos.session_id and each_pos.session_id.name or ""), Style.normal_left())
            sheet1.write(row, 12, (each_pos.pricelist_id.currency_id and each_pos.pricelist_id.currency_id.name or ""), Style.normal_left())
            if each_pos.lines:
                if self.product_ids:
                    for each in self.product_ids: 
                        for line_pos in each_pos.lines:
                            if each.id == line_pos.product_id.id:
                                sheet1.row(row).height = 500
                                sheet1.write(row, 13, (line_pos.product_id and line_pos.product_id.name_get()[0][1] or ""), Style.normal_left())
                                sheet1.write(row, 14, line_pos.qty, Style.normal_num_right_3digits())
                                sheet1.write(row, 15, (line_pos.product_id.uom_id and line_pos.product_id.uom_id.name or ""), Style.normal_left())
                                sheet1.write(row, 16, line_pos.price_unit, Style.normal_num_right_3separator())
                                sheet1.write(row, 17, line_pos.discount, Style.normal_num_right())
                                sheet1.write(row, 18, line_pos.price_subtotal, Style.normal_num_right_3separator())
                                sheet1.write(row, 19, line_pos.price_subtotal_incl, Style.normal_num_right_3separator())
                                pos_local_inv_amt_without_tax += line_pos.price_subtotal
                                pos_local_inv_amt_with_tax += line_pos.price_subtotal_incl
#                                pos_local_inv_discount += line_pos.discount
                                row = row + 1
                else:
                    for line_pos in each_pos.lines:
                        sheet1.row(row).height = 500
                        sheet1.write(row, 13, (line_pos.product_id and line_pos.product_id.name_get()[0][1] or ""), Style.normal_left())
                        sheet1.write(row, 14, line_pos.qty, Style.normal_num_right_3digits())
                        sheet1.write(row, 15, (line_pos.product_id.uom_id and line_pos.product_id.uom_id.name or ""), Style.normal_left())
                        sheet1.write(row, 16, line_pos.price_unit, Style.normal_num_right_3separator())
                        sheet1.write(row, 17, line_pos.discount, Style.normal_num_right())
                        sheet1.write(row, 18, line_pos.price_subtotal, Style.normal_num_right_3separator())
                        sheet1.write(row, 19, line_pos.price_subtotal_incl, Style.normal_num_right_3separator())
                        pos_local_inv_amt_without_tax += line_pos.price_subtotal
                        pos_local_inv_amt_with_tax += line_pos.price_subtotal_incl
#                        pos_local_inv_discount += line_pos.discount  
                        row = row + 1
                row = row - 1
        row = row + 1
        sheet1.write_merge(row, row, 0, 16, 'Total', Style.groupByTitle())
        sheet1.write(row, 17, "", Style.groupByTotal())
        sheet1.write(row, 18, (pos_local_inv_amt_without_tax), Style.groupByTotal3Separator())
        sheet1.write(row, 19, (pos_local_inv_amt_with_tax), Style.groupByTotal3Separator())
        stream = cStringIO.StringIO()
        wbk.save(stream)

        self.write({ 'name': report_name +'.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'pos.detailed.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
