# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import pytz
import datetime
import time
from . import excel_styles
import xlwt
from io import BytesIO
import base64
from lxml import etree

class StockRegisterProductWarehouseWizard(models.TransientModel):
    _name = 'stock.register.product.warehouse.wizard'
    _description = 'Stock Register Product, Warehouse & Location Wise'
    
    report_type = fields.Selection([
        ('product', 'Product Wise - Stock in Location - as on selected date'), 
        ('product_details', 'Product Wise - Stock in Location - Detailed'),
        ('product_summary', 'Product Wise - Stock in Location - Summary'),
        ('location_summary', 'Location Wise - Product Stock - Summary')], string='Report Type', required=True, default='product')
    company_id = fields.Many2one('res.company', string='Company', readonly=True, default=lambda self: self.env.user.company_id)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True)
    date_from = fields.Date(string='Start Date')
    date_to = fields.Date(string='Date End', default=time.strftime('%Y-%m-%d'))
    product_ids = fields.Many2many('product.product', 'stock_register_product_wizard_rel', 'wizard_id', 'product_id', string='Product')
    location_ids = fields.Many2many('stock.location', 'stock_register_location_wizard_rel', 'wizard_id', 'location_id', string='Location')
    categ_ids = fields.Many2many('product.category', 'stock_register_categ_wizard_rel', 'wizard_id', 'categ_id', string='Location')
    view_location_id = fields.Many2one('stock.location', string='View Location')
    show_value = fields.Boolean(string='Show Inventory Value')
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(StockRegisterProductWarehouseWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='warehouse_id']"):
                warehouse_id = []
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                node.set('domain', "[('id', 'in', " + str(warehouse_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res
        
    @api.onchange('report_type')
    def onchange_report_type(self):
        if self.report_type:
            if self.report_type == 'product':
                self.date_from = False
        else:
           self.date_from = False 
    
    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        warning = {}
        domain = {
            'location_ids': [('usage', '=', 'internal')],
            'product_ids': [('type', '=', 'product')]
            }
        if self.warehouse_id:
            self.view_location_id = self.warehouse_id.view_location_id.id
            self.categ_ids = []
            domain = {
                'location_ids': ['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')],
                'product_id': ['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')]
            }
        else:
            self.view_location_id = False
        return {'domain': domain}
            
    @api.onchange('categ_ids')
    def onchange_categ_ids(self):
        domain = {}
        if self.warehouse_id and self.categ_ids:
            domain = {
                'location_ids': ['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')],
                'product_id': ['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')]
                }
        return {'domain': domain}
    
    
    def get_categ_str(self):
        categ_ids = []
        categ_list = []
        categ_str = ""
        if self.categ_ids:
            for each_id in self.categ_ids:
                categ_ids.append(each_id.id)
                categ_list.append(each_id.name)
            categ_list = list(set(categ_list))
            categ_str = str(categ_list).replace('[','').replace(']','').replace("u'","").replace("'","")
            categ_str = "Includes Product Category(s) : " + categ_str 
        return categ_str
    
    
    def inventory_query(self, product_ids, location_ids, date_from, date_to):
        date_domain = ""
        product_domain = ""
        location_domain_in = ""
        location_domain_out = ""
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        if date_from:
            date_domain += " AND ((stock_move.date at time zone '" + str(tz) + "')::timestamp)::date >= '"+ str(date_from) + "'"
        if date_to:
            date_domain += " AND ((stock_move.date at time zone '" + str(tz) + "')::timestamp)::date <= '"+ str(date_to) + "'"
        if location_ids:
            if len(location_ids) > 1:
                location_domain_out += " AND source_location.id in " + str(tuple(location_ids))
                location_domain_in += " AND dest_location.id in " + str(tuple(location_ids))
            else:
                location_domain_out += " AND source_location.id = " + str(location_ids[0])
                location_domain_in += " AND dest_location.id = " + str(location_ids[0])
        if product_ids: 
            if len(product_ids) > 1:
                product_domain += " AND product_product.id in " + str(tuple(product_ids))
            else:
                product_domain += " AND product_product.id = " + str(product_ids[0])
        # stock_quant_obj = self.env['stock.quant'].search_read([('location_id','=',self.warehouse_id.id)],fields=['location_id','product_id','inventory_quantity_auto_apply','value'])
        # print('>>>>>>>>>>>>>>>stock_quant_obj>>>>>>>>>>>>>>>>',stock_quant_obj)

        sql = """
              SELECT 
                location_id,
                product_id,
                SUM(inventory_quantity_auto_apply) as quantity,
                SUM(value) as inventory_value
                FROM
                ((SELECT
                    stock_move.id AS id,
                    dest_location.id AS location_id,
                    stock_move.product_id AS product_id,
                    quant.qty AS quantity,
                    quant.cost AS cost,
                    (quant.qty * quant.cost) AS inventory_value
                FROM
                    stock_quant as quant
                JOIN
                    stock_quant_move_rel ON stock_quant_move_rel.quant_id = quant.id
                JOIN
                    stock_move ON stock_move.id = stock_quant_move_rel.move_id
                JOIN
                    stock_location dest_location ON stock_move.location_dest_id = dest_location.id
                JOIN
                    stock_location source_location ON stock_move.location_id = source_location.id
                JOIN
                    product_product ON product_product.id = stock_move.product_id
                JOIN
                    product_template ON product_template.id = product_product.product_tmpl_id
                WHERE quant.qty > 0 AND stock_move.state = 'done' 
                AND source_location.id != dest_location.id """ + date_domain + location_domain_in + product_domain + """
                ) UNION ALL
                (SELECT
                    (-1) * stock_move.id AS id,
                    source_location.id AS location_id,
                    stock_move.product_id AS product_id,
                    - quant.qty AS quantity,
                    quant.cost AS cost,
                    (-quant.qty * quant.cost) AS inventory_value
                FROM
                    stock_quant as quant
                JOIN
                    stock_quant_move_rel ON stock_quant_move_rel.quant_id = quant.id
                JOIN
                    stock_move ON stock_move.id = stock_quant_move_rel.move_id
                JOIN
                    stock_location source_location ON stock_move.location_id = source_location.id
                JOIN
                    stock_location dest_location ON stock_move.location_dest_id = dest_location.id
                JOIN
                    product_product ON product_product.id = stock_move.product_id
                JOIN
                    product_template ON product_template.id = product_product.product_tmpl_id
                WHERE quant.qty > 0 AND stock_move.state = 'done' 
                AND dest_location.id != source_location.id """ + date_domain + location_domain_out + product_domain + """
                ))
                AS foo
                GROUP BY location_id, product_id """

        self.env.cr.execute(sql, (tz, tz))
        inventory_valuation_data = self.env.cr.dictfetchall()
        print('>>>>>>>>>>>>>>inventory_valuation_data>>>>>>>>>>>>>>>>>>>>>>>>>>',inventory_valuation_data)
        return inventory_valuation_data
    
    
    def action_print_report_pdf(self):
        self.ensure_one()
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['report_type', 'warehouse_id', 'company_id', 'date_from', 'date_to', 'product_ids', 'location_ids'])[0]
        if self.report_type == 'product':
            if self.show_value:
                return self.env['report'].get_action(self, 'stockregister.product.summary.value.rml', data=data)
            else:
                return self.env['report'].get_action(self, 'stockregister.product.summary.rml', data=data)
        elif self.report_type == 'product_summary':
            return self.env['report'].get_action(self, 'product.stock.summary.value.rml', data=data)
        
        elif self.report_type == 'location_summary':
            return self.env['report'].get_action(self, 'location.stock.summary.value.rml', data=data)
        else:
            raise UserError(_("This report cannot be printed pdf format"))
#            if self.show_value:
#                return self.env['report'].get_action(self, 'stockregister.product.detailed.value.rml', data=data)
#            else:
#                return self.env['report'].get_action(self, 'stockregister.product.detailed.rml', data=data)
            
    
    def action_report_excel(self):
        self.ensure_one()
        if self.report_type == 'product':
            return self.action_report_product_excel()
        if self.report_type == 'product_details':
            return self.action_report_product_detailed_excel()
        if self.report_type == "product_summary":
            return self.action_report_product_summary_excel()
        if self.report_type == "location_summary":
            return self.action_report_location_summary_excel()
            
    
    def action_report_pdf_get_products(self):
        self.ensure_one()
        obj_product = self.env['product.product']
        final_products = []
        if self.product_ids:
            products = self.product_ids
        else:
            if self.categ_ids:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product'), ('categ_id', 'in', [ c.id for c in self.categ_ids ])])
            else:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')])
        for product in products:
            result = self.action_report_pdf_get_location(product)
            if len(result) != 0:
                final_products.append(product)
        return final_products
        
    
    def action_report_pdf_get_location(self, product=None, location_search=None):
        self.ensure_one()
        obj_product = self.env['product.product']
        obj_location = self.env['stock.location']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from = date_to = x_from_date = x_to_date = False
        from_des = to_des = ""
        qty, price = 0.00, 0.00
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            if self.report_type != 'product':
                from_des = " Date From - " + str(date_from)
                x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y")
            to_des = " Date Till - "+ str(date_to)
            x_to_date = self.date_to
        if self.location_ids:
            location_search = self.location_ids
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
        result = []
        s_no = 0
        if not product:
            if location_search:
                if self.product_ids:
                    products = self.product_ids
                else:
                    if self.categ_ids:
                        products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product'), ('categ_id', 'in', [ c.id for c in self.categ_ids ])])
                    else:
                        products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')])
                product_location_data = self.inventory_query(products.ids, location_search.ids, x_from_date, x_to_date)
                for each_loc in location_search:
                    for prod in products:
                        qty_available, price_available = 0.00, 0.00
                        qty_available_list = [ x['quantity'] for x in product_location_data if (x['product_id'] == prod.id) and (x['location_id'] == each_loc.id)]
                        qty_available = sum(qty_available_list)
                        #qty_available = prod.with_context({'location': each_loc.id, 'from_date': x_from_date or False, 'to_date': x_to_date or False}).qty_available
                        if self.show_value:
#                            quant_search = obj_quant.search([('product_id', '=', prod.id), ('location_id', '=', each_loc.id), ('in_date', '<=', x_to_date)])
#                            for each_quant in quant_search:
#                                price_available += each_quant.inventory_value
                            qty_available_value = [ x['inventory_value'] for x in product_location_data if (x['product_id'] == prod.id) and (x['location_id'] == each_loc.id)]
                            price_available += sum(qty_available_value)
                            
                        if qty_available:
                            s_no = s_no + 1
                            result.append({
                                's_no': s_no,
                                'product': prod.name,
                                'location': each_loc.name_get()[0][1],
                                'qty_available': qty_available,
                                'price_available': price_available
                                })
                            qty += qty_available
                            price += price_available                
        else:
            if self.location_ids:
                location_search = self.location_ids
            else:
                location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
            product_location_data = self.inventory_query([product.id], location_search.ids, x_from_date, x_to_date)
            for each_loc in location_search:
                qty_available, price_available = 0.00, 0.00
                qty_available_list = [ x['quantity'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id)]
                qty_available = sum(qty_available_list)
                #qty_available = product.with_context({'location': each_loc.id, 'from_date': x_from_date or False, 'to_date': x_to_date or False}).qty_available
                if self.show_value:
#                    quant_search = obj_quant.search([('product_id', '=', product.id), ('location_id', '=', each_loc.id), ('in_date', '<=', x_to_date)])
#                    for each_quant in quant_search:
#                        price_available += each_quant.inventory_value
                    qty_available_value = [ x['inventory_value'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id)]
                    price_available += sum(qty_available_value)
                    
                if qty_available:
                    s_no = s_no + 1
                    result.append({
                        's_no': s_no,
                        'location': each_loc.name_get()[0][1],
                        'qty_available': qty_available,
                        'price_available': price_available
                        })
                    qty += qty_available
                    price += price_available
        return result
        
    
    def action_report_pdf_get_location_total(self, product):
        self.ensure_one()
        obj_location = self.env['stock.location']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from = date_to = x_from_date = x_to_date = False
        from_des = to_des = ""
        qty, price = 0.00, 0.00
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            if self.report_type != 'product':
                from_des = " Date From - " + str(date_from)
                x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y")
            to_des = " Date Till - "+ str(date_to)
            x_to_date = self.date_to
        if self.location_ids:
            location_search = self.location_ids
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
        result = {'qty': 0.00, 'price': 0.00}
        s_no = 0
        product_location_data = self.inventory_query([product.id], location_search.ids, x_from_date, x_to_date)
        for each_loc in location_search:
            qty_available, price_available = 0.00, 0.00
            qty_available_list = [ x['quantity'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id)]
            qty_available = sum(qty_available_list)
            #qty_available = product.with_context({'location': each_loc.id, 'from_date': x_from_date or False, 'to_date': x_to_date or False}).qty_available
            if self.show_value:
#                quant_search = obj_quant.search([('product_id', '=', product.id), ('location_id', '=', each_loc.id), ('in_date', '<=', x_to_date)])
#                for each_quant in quant_search:
#                    price_available += each_quant.inventory_value
                qty_available_value = [ x['inventory_query'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id)]
                price_available += sum(qty_available_value)
                
            if qty_available:
                qty += qty_available
                price += price_available
        result['qty'] = qty
        result['price'] = price
        return result

    
    def action_report_product_excel(self):
        self.ensure_one()
        obj_location = self.env['stock.location']
        obj_product = self.env['product.product']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from = date_to = x_from_date = x_to_date = False
        from_des = to_des = ""
        categ_str = self.get_categ_str()    
        if self.location_ids:
            location_search = self.location_ids
            print('>>>>>>>>>>>>>>>>location_search>>>>>>>>>>>>>>>>>>', location_search)
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
            print ("\n\n\nlocation_search", location_search)
        if self.product_ids:
            products = self.product_ids
        else:
            if self.categ_ids:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product'), ('categ_id', 'in', [ c.id for c in self.categ_ids ])])
                print('>>>>>>>>>>>>products>>>>>>>>>>>>>>>>', products)
            else:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')])
                print ("\n\n\nproducts", products)
        report_name = "Product Wise Stock Register"
        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 8000
        sheet1.col(2).width = 3000
        sheet1.col(3).width = 4000
        sheet1.col(4).width = 5000
        sheet1.col(5).width = 3000
    
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 200 * 2
        sheet1.row(r3).height = 256 * 2
        sheet1.row(r4).height = 256 * 2
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            if self.report_type != 'product':
                from_des = " Date From - " + str(date_from)
                x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y")
            to_des = " Date Till - " + str(date_to)
            x_to_date = self.date_to
        if self.show_value:
            sheet1.write_merge(r1, r1, 0, 4, self.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 4, self.warehouse_id.name + report_name, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 0, 4, " ( " + from_des + to_des + " )", Style.sub_title_color())
            sheet1.write_merge(r4, r4, 0, 4, (categ_str and categ_str or "Includes all product categories"), Style.subTitle_left())
        else:
            sheet1.write_merge(r1, r1, 0, 3, self.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 3, self.warehouse_id.name + report_name, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 0, 3, " ( " + from_des + to_des + " )", Style.sub_title_color())
            sheet1.write_merge(r4, r4, 0, 3, (categ_str and categ_str or "Includes all product categories"), Style.subTitle_left())

        row = r4
        s_no = 0
        qty, price = 0.00, 0.00
        # product_location_data = self.inventory_query(products.ids, location_search.ids, x_from_date, x_to_date)
        stock_quant_obj = self.env['stock.quant'].search_read([('location_id', '=', self.warehouse_id.lot_stock_id.id),('product_id', 'in', products.ids)],
                                                              fields=['location_id', 'product_id',
                                                                      'inventory_quantity_auto_apply', 'value'])
        product_location_data = [
            {
                'inventory_value': item['value'],
                'location_id': item['location_id'][0],
                'product_id': item['product_id'][0],
                'quantity': item['inventory_quantity_auto_apply']
            }
            for item in stock_quant_obj
        ]
        # print('>>>>>>>>>>>>>>>output_data>>>>>>>>>>>>>>>>', output_data)

        for product in products:
            product_print = False
            s_no = 0
            qty, price = 0.00, 0.00
            for each_loc in location_search:
                qty_available, price_available = 0.00, 0.00
                qty_available_list = [ x['quantity'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id) ]
                qty_available = sum(qty_available_list)
                #qty_available = product.with_context({'location': each_loc.id, 'from_date': x_from_date or False, 'to_date': x_to_date or False}).qty_available
                if self.show_value:
#                    quant_search = obj_quant.search([('product_id', '=', product.id), ('location_id', '=', each_loc.id), ('in_date', '<=', x_to_date)])
#                    for each_quant in quant_search:
#                        price_available += each_quant.inventory_value
                    qty_available_value = [ x['inventory_value'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id) ]
                    price_available += sum(qty_available_value)
                if qty_available:
                    if not product_print:
                        #############Product Head
                        row = row + 1
                        sheet1.row(row).height = 500
                        if self.show_value:
                            sheet1.write_merge(row, row, 0, 4, (product.name_get()[0][1] + " - " + product.uom_id.name), Style.subTitle_color())
                        else:
                            sheet1.write_merge(row, row, 0, 3, (product.name_get()[0][1] + " - " + product.uom_id.name), Style.subTitle_color())
                        product_print = True
                        ###############Location Head
                        row = row + 1
                        sheet1.row(row).height = 300
                        sheet1.write(row, 0, "S.No", Style.contentTextBold(r2,'black','white'))
                        sheet1.write_merge(row, row, 1, 2, "Location", Style.contentTextBold(r2,'black','white'))
                        sheet1.write(row, 3, "Quantity", Style.contentTextBold(r2,'black','white'))
                        if self.show_value:
                            sheet1.write(row, 4, "Value", Style.contentTextBold(r2,'black','white'))

                    row = row + 1
                    s_no = s_no + 1
                    sheet1.row(row).height = 300
                    sheet1.write(row, 0, s_no, Style.normal_left())
                    sheet1.write_merge(row, row, 1, 2, each_loc.name_get()[0][1], Style.normal_left())
                    sheet1.write(row, 3, qty_available, Style.normal_num_right_3digits())
                    if self.show_value:
                        sheet1.write(row, 4, price_available, Style.normal_num_right_3separator())
                    qty += qty_available
                    price += price_available
            if product_print:
                row = row + 1
                sheet1.write_merge(row, row, 0, 2, 'All Location Total', Style.groupByTotal())
                sheet1.write(row, 3, qty, Style.groupByTotal())
                if self.show_value:
                    sheet1.write(row, 4, price, Style.groupByTotal())
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.register.product.warehouse.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
    
    
    def action_report_product_detailed_excel(self):
        self.ensure_one()
        obj_location = self.env['stock.location']
        obj_product = self.env['product.product']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from, date_to, x_from_date, x_to_date = False, False, False, False
        from_des, to_des = "", ""
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        
        categ_str = self.get_categ_str()
        
        if self.location_ids:
            location_search = self.location_ids
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
        if self.product_ids:
            products = self.product_ids
        else:
            if self.categ_ids:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product'), ('categ_id', 'in', [ c.id for c in self.categ_ids ])])
            else:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')])
                
        opening_in_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_dest_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        opening_out_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        sql = """select x.id as id, x.move_date as move_date, x.date as date, x.name as name, x.type as type, sum(x.qty) as qty, sum(x.price) as price from
                    ((select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', (case when sm.issue_id is not null then rmi.source_doc else '' end), (case when sm.issue_id is not null then '/' else '' end), sm.origin) else (case when sp.origin is not null then concat(sp.name, '/', sp.origin) else sm.name end) end) else '' end) end) as name,
                    'in' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id = sp.id)
                    left join raw_material_issue rmi on (rmi.id = sm.issue_id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_dest_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor,
                    rmi.source_doc,
                    sp.origin
                order by sm.date)
                Union
                (select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', (case when sm.issue_id is not null then rmi.source_doc else '' end), (case when sm.issue_id is not null then '/' else '' end), sm.origin) else (case when sp.origin is not null then concat(sp.name, '/', sp.origin) else sm.name end)  end) else '' end) end) as name,
                    'out' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                    left join raw_material_issue rmi on (rmi.id = sm.issue_id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor,
                    rmi.source_doc,
                    sp.origin
                order by sm.date)) x 
                group by
                    x.id,
                    x.move_date,
                    x.date,
                    x.name,
                    x.type
                order by x.move_date"""
        
        report_name = "Stock Register Product Wise Detailed"
        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 4000
        sheet1.col(1).width = 8000
        sheet1.col(2).width = 3000
        sheet1.col(3).width = 4000
        sheet1.col(4).width = 4000
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 4000
        sheet1.col(7).width = 4000
        sheet1.col(8).width = 4000
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 256 * 2
        sheet1.row(r3).height = 256 * 2
        sheet1.row(r4).height = 256 * 2
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            from_des = " Date From - " + str(date_from)
            x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y")
            to_des = " Date Till - "+ str(date_to)
            x_to_date = self.date_to
        
        if self.show_value:
            sheet1.write_merge(r1, r1, 0, 7, self.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 7, self.warehouse_id.name + report_name, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 0, 7, " ( " + from_des + to_des + " )", Style.title_color())
            sheet1.write_merge(r4, r4, 0, 7, (categ_str and categ_str or "Includes all product categories"), Style.subTitle_left())
        else:
            sheet1.write_merge(r1, r1, 0, 5, self.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 5, self.warehouse_id.name + report_name, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 0, 5, " ( " + from_des + to_des + " )", Style.title_color())
            sheet1.write_merge(r4, r4, 0, 5, (categ_str and categ_str or "Includes all product categories"), Style.subTitle_left())
        row = r4
        closing_qty, closing_value, price_available = 0.00, 0.00, 0.00
        #product_location_data = self.inventory_query(products.ids, location_search.ids, x_from_date, x_to_date)
        for product in products:
            closing_qty, closing_value, price_available = 0.00, 0.00, 0.00 
            tot_in_qty, tot_out_qty, tot_in_value, tot_out_value = 0.00, 0.00, 0.00, 0.00 
            product_print = False
            for each_loc in location_search:
                opening_print, transaction_print = [], []
                qty_available, in_qty, out_qty, balance, price_available,  = 0.00, 0.00, 0.00, 0.00, 0.00 
                opening_in_qty, opening_out_qty, opening_in_value, opening_out_value = 0.00, 0.00, 0.00, 0.00 
                in_value, out_value = 0.00, 0.00
                ###############location Opening Stock Check
                self.env.cr.execute(opening_in_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
                opening_in_data = self.env.cr.dictfetchall()
                self.env.cr.execute(opening_out_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
                opening_out_data = self.env.cr.dictfetchall()
                
                for each_in in opening_in_data:
                    opening_in_qty += each_in['qty']
                    #if self.show_value:
                    #    opening_in_value += (each_in['qty'] * (each_in['price'] and each_in['price'] or 0.00))
                for each_out in opening_out_data:
                    opening_out_qty += each_out['qty']
                    #if self.show_value:
                    #    opening_out_value += (each_out['qty'] * (each_out['price'] and each_out['price'] or 0.00))
                balance = opening_in_qty - opening_out_qty
                if balance:
                    opening_print.append('True')
                #price_available = opening_in_value - opening_out_value
                if balance != abs(balance):
                    out_qty = abs(balance)
                    #out_value = abs(price_available)
                else:
                    in_qty = balance
                    #in_value = abs(price_available)
                ############### location transaction check
                self.env.cr.execute(sql, (tuple([tz, self.date_from, tz, self.date_to, product.id, each_loc.id,  tz, self.date_from, tz, self.date_to, product.id, each_loc.id])))
                data = self.env.cr.dictfetchall()
                for transaction in data:
                    if transaction['type'] == 'in':
                        transaction_print.append('True')
                    if transaction['type'] == 'out':
                        transaction_print.append('True')
                        
                if 'True' in opening_print or 'True' in transaction_print:
                    ############### print product name
                    if not product_print:
                        row = row + 1
                        sheet1.row(row).height = 700
                        if self.show_value:
                            sheet1.write_merge(row, row, 0, 7, (product.name_get()[0][1] + " - " + product.uom_id.name), Style.sub_title_color())
                        else:
                            sheet1.write_merge(row, row, 0, 5, (product.name_get()[0][1] + " - " + product.uom_id.name), Style.sub_title_color())
                        product_print = True
                    ############### print location name
                    row = row + 1
                    sheet1.row(row).height = 300
                    if self.show_value:
                        sheet1.write_merge(row, row, 0, 7, each_loc.name_get()[0][1], Style.subTitle_sub_color_left())
                    else:
                        sheet1.write_merge(row, row, 0, 5, each_loc.name_get()[0][1], Style.subTitle_sub_color_left())
                        
                    row = row + 1
                    sheet1.row(row).height = 300
                    sheet1.write(row, 0, "Date", Style.contentTextBold(r2,'black','white'))
                    sheet1.write_merge(row, row, 1, 2, "Description", Style.contentTextBold(r2,'black','white'))
                    sheet1.write(row, 3, "In Qty", Style.contentTextBold(r2,'black','white'))
                    if self.show_value:
                        sheet1.write(row, 4, "In Value", Style.contentTextBold(r2,'black','white'))
                        sheet1.write(row, 5, "Out Qty", Style.contentTextBold(r2,'black','white'))
                        sheet1.write(row, 6, "Out Value", Style.contentTextBold(r2,'black','white'))
                        sheet1.write(row, 7, "Balance Qty", Style.contentTextBold(r2,'black','white'))
                        #sheet1.write(row, 8, "Inventory Value", Style.contentTextBold(r2,'black','white'))
                    else:
                        sheet1.write(row, 4, "Out Qty", Style.contentTextBold(r2,'black','white'))
                        sheet1.write(row, 5, "Balance Qty", Style.contentTextBold(r2,'black','white'))

                    row = row + 1
                    sheet1.row(row).height = 300
                    sheet1.write_merge(row, row, 0, 2, "Opening", Style.subTitle_left_color())
                    sheet1.write(row, 3, in_qty, Style.normal_num_right_color())
                    if self.show_value:
                        sheet1.write(row, 4, in_value, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 5, out_qty, Style.normal_num_right_color())
                        sheet1.write(row, 6, out_value, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 7, balance, Style.normal_num_right_color())
                        #sheet1.write(row, 8, price_available, Style.normal_num_right_color_3separator())
                    else:
                        sheet1.write(row, 4, out_qty, Style.normal_num_right_color())
                        sheet1.write(row, 5, balance, Style.normal_num_right_color())
                    for each in data:
                        row = row + 1
                        sheet1.row(row).height = 300
                        sheet1.write(row, 0, each['date'], Style.normal_left())
                        sheet1.write_merge(row, row, 1, 2, each['name'], Style.normal_left())
                        if each['type'] == 'in':
                            in_qty += each['qty']
                            in_value +=  (each['qty'] * (each['price'] and each['price'] or 0.00))
                            balance += each['qty']
                            if self.show_value:
                                sheet1.write(row, 3, each['qty'], Style.normal_num_right_3digits())
                                sheet1.write(row, 4, (each['qty'] * (each['price'] and each['price'] or 0.00)), Style.normal_num_right_3separator())
                                sheet1.write(row, 5, 0.00, Style.normal_num_right_3digits())
                                sheet1.write(row, 6, 0.00, Style.normal_num_right_3separator())
                                sheet1.write(row, 7, balance, Style.normal_num_right_3digits())
                                #price_available += (each['qty'] * (each['price'] and each['price'] or 0.00))
                                #sheet1.write(row, 8, price_available, Style.normal_num_right_3separator())
                            else:
                                sheet1.write(row, 3, each['qty'], Style.normal_num_right_3digits())
                                sheet1.write(row, 4, 0.00, Style.normal_num_right_3digits())
                                sheet1.write(row, 5, balance, Style.normal_num_right_3digits())
                        if each['type'] == 'out':
                            out_qty += each['qty']
                            out_value += (each['qty'] * (each['price'] and each['price'] or 0.00))
                            balance -= each['qty']
                            if self.show_value:
                                sheet1.write(row, 3, 0.00, Style.normal_num_right_3digits())
                                sheet1.write(row, 4, 0.00, Style.normal_num_right_3separator())
                                sheet1.write(row, 5, each['qty'], Style.normal_num_right_3digits())
                                sheet1.write(row, 6, (each['qty'] * (each['price'] and each['price'] or 0.00)), Style.normal_num_right_3separator())
                                sheet1.write(row, 7, balance, Style.normal_num_right_3digits())
                                #price_available -= (each['qty'] * (each['price'] and each['price'] or 0.00))
                                #sheet1.write(row, 8, price_available, Style.normal_num_right_3separator())
                            else:
                                sheet1.write(row, 3, 0.00, Style.normal_num_right_3digits())
                                sheet1.write(row, 4, each['qty'], Style.normal_num_right_3digits())
                                sheet1.write(row, 5, balance, Style.normal_num_right_3digits())
                    ############### location wise closing_qty
                    row = row + 1
                    sheet1.row(row).height = 300
                    sheet1.write_merge(row, row, 0, 2, "Closing", Style.subTitle_left_color())
                    sheet1.write(row, 3, in_qty, Style.normal_num_right_color())
                    if self.show_value:
                        sheet1.write(row, 4, in_value, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 5, out_qty, Style.normal_num_right_color())
                        sheet1.write(row, 6, out_value, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 7, balance, Style.normal_num_right_color())
                        #sheet1.write(row, 8, price_available, Style.normal_num_right_color_3separator())
                    else:
                        sheet1.write(row, 4, out_qty, Style.normal_num_right_color())
                        sheet1.write(row, 5, balance, Style.normal_num_right_color())
                    closing_qty += balance
                    #closing_qty_list = [ x['quantity'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id)]
                    #closing_qty = sum(closing_qty_list)
                    #closing_qty = product.with_context({'location': each_loc.id, 'from_date': x_from_date or False, 'to_date': x_to_date or False}).qty_available
                    if self.show_value:
                        closing_quant_search = obj_quant.search([('product_id', '=', product.id), ('location_id', '=', each_loc.id), ('in_date', '>=', x_from_date), ('in_date', '<=', x_to_date)])
                        for close_quant in closing_quant_search:
                            closing_value += close_quant.value
                    tot_in_qty += in_qty
                    tot_out_qty += out_qty
                    tot_in_value += in_value
                    tot_out_value += out_value
                
            ############### All location closing qty
            if product_print:
                row = row + 2
                sheet1.write_merge(row, row, 0, 2, 'All Location Total Closing', Style.groupByTotal())
                if closing_qty != abs(closing_qty):
                    closing_qty = closing_qty
                if self.show_value:
                    sheet1.write(row, 3, tot_in_qty, Style.groupByTotal3digits())
                    sheet1.write(row, 4, tot_in_value, Style.groupByTotal3separator())
                    sheet1.write(row, 5, tot_out_qty, Style.groupByTotal3digits())
                    sheet1.write(row, 6, tot_out_value, Style.groupByTotal3separator())
                    sheet1.write(row, 7, closing_qty, Style.groupByTotal3digits())
                    #sheet1.write(row, 8, closing_value, Style.groupByTotal3separator())
                else:
                    sheet1.write(row, 3, tot_in_qty, Style.groupByTotal3digits())
                    sheet1.write(row, 4, tot_out_qty, Style.groupByTotal3digits())
                    sheet1.write(row, 5, closing_qty, Style.groupByTotal3digits())
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls','output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.register.product.warehouse.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
                
    
    def action_report_pdf_get_location_detailed(self, product):
        self.ensure_one()
        obj_location = self.env['stock.location']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from, date_to, x_from_date, x_to_date = False, False, False, False
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        if self.location_ids:
            location_search = self.location_ids
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
            
        opening_in_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_dest_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        opening_out_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        sql = """select x.id as id, x.move_date as move_date, x.date as date, x.name as name, x.type as type, sum(x.qty) as qty, sum(x.price) as price from
                    ((select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', (case when sm.issue_id is not null then rmi.source_doc else '' end), (case when sm.issue_id is not null then '/' else '' end), sm.origin) else (case when sp.origin is not null then concat(sp.name, '/', sp.origin) else sm.name end)  end) else '' end) end) as name,
                    'in' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                    left join raw_material_issue rmi on (rmi.id = sm.issue_id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_dest_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor,
                    sm.issue_id,
                    rmi.source_doc,
                    sp.origin
                order by sm.date)
                Union
                (select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', (case when sm.issue_id is not null then rmi.source_doc else '' end), (case when sm.issue_id is not null then '/' else '' end), sm.origin) else (case when sp.origin is not null then concat(sp.name, '/', sp.origin) else sm.name end) end) else '' end) end) as name,
                    'out' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                    left join raw_material_issue rmi on (rmi.id = sm.issue_id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor,
                    sm.issue_id,
                    rmi.source_doc,
                    sp.origin
                order by sm.date)) x 
                group by
                    x.id,
                    x.move_date,
                    x.date,
                    x.name,
                    x.type
                order by x.move_date"""
        
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y")
            x_to_date = self.date_to
        
        closing_qty, closing_value, price_available = 0.00, 0.00, 0.00 
        tot_in_qty, tot_out_qty, tot_in_value, tot_out_value = 0.00, 0.00, 0.00, 0.00
        result = []
        for each_loc in location_search:
            opening_print, transaction_print = [], []
            qty_available, in_qty, out_qty, balance, price_available,  = 0.00, 0.00, 0.00, 0.00, 0.00 
            opening_in_qty, opening_out_qty, opening_in_value, opening_out_value = 0.00, 0.00, 0.00, 0.00 
            in_value, out_value = 0.00, 0.00
            ###############location Opening Stock Check
            self.env.cr.execute(opening_in_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
            opening_in_data = self.env.cr.dictfetchall()
            self.env.cr.execute(opening_out_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
            opening_out_data = self.env.cr.dictfetchall()
            
            for each_in in opening_in_data:
                opening_in_qty += each_in['qty']
                #if self.show_value:
                #    opening_in_value += (each_in['qty'] * (each_in['price'] and each_in['price'] or 0.00))
            for each_out in opening_out_data:
                opening_out_qty += each_out['qty']
                #if self.show_value:
                #    opening_out_value += (each_out['qty'] * (each_out['price'] and each_out['price'] or 0.00))
            balance = opening_in_qty - opening_out_qty
            if balance:
                opening_print.append('True')
            #price_available = opening_in_value - opening_out_value
            if balance != abs(balance):
                out_qty = abs(balance)
                #out_value = abs(price_available)
            else:
                in_qty = balance
                #in_value = abs(price_available)
            ############### location transaction check
            self.env.cr.execute(sql, (tuple([tz, self.date_from, tz, self.date_to, product.id, each_loc.id,  tz, self.date_from, tz, self.date_to, product.id, each_loc.id])))
            data = self.env.cr.dictfetchall()
            for transaction in data:
                if transaction['type'] == 'in':
                    transaction_print.append('True')
                if transaction['type'] == 'out':
                    transaction_print.append('True')
            if 'True' in opening_print or 'True' in transaction_print:
                result.append({
                    'location': each_loc.name_get()[0][1],
                    'date': '',
                    'description': "Opening",
                    'in_qty': in_qty,
                    'in_value': in_value,
                    'out_qty': out_qty,
                    'out_value': out_value,
                    'balance_qty': balance,
                    #'inventory_value': price_available,
                    })
                for each in data:
                    if each['type'] == 'in':
                        in_qty += each['qty']
                        in_value +=  (each['qty'] * (each['price'] and each['price'] or 0.00))
                        balance += each['qty']
                        #price_available += (each['qty'] * (each['price'] and each['price'] or 0.00))
                        result.append({
                            'location': '',
                            'date': each['date'],
                            'description': each['name'],
                            'in_qty': each['qty'],
                            'in_value': (each['qty'] * (each['price'] and each['price'] or 0.00)),
                            'out_qty': 0.00,
                            'out_value': 0.00,
                            'balance_qty': balance,
                            #'inventory_value': price_available,
                            })
                    if each['type'] == 'out':
                        out_qty += each['qty']
                        out_value += (each['qty'] * (each['price'] and each['price'] or 0.00))
                        balance -= each['qty']
                        #price_available -= (each['qty'] * (each['price'] and each['price'] or 0.00))
                        result.append({
                            'location': '',
                            'date': each['date'],
                            'description': each['name'],
                            'in_qty': 0.00,
                            'in_value': 0.00,
                            'out_qty': each['qty'],
                            'out_value': (each['qty'] * (each['price'] and each['price'] or 0.00)),
                            'balance_qty': balance,
                            #'inventory_value': price_available,
                            })
                ############### location wise closing_qty
                result.append({
                    'location': '',
                    'date': False,
                    'description': "Closing",
                    'in_qty': in_qty,
                    'in_value': in_value,
                    'out_qty': out_qty,
                    'out_value': out_value,
                    'balance_qty': balance,
                    #'inventory_value': price_available,
                    })
        return result

    
    def action_report_pdf_get_product_summary(self, product, total_req=None):
        self.ensure_one()
        obj_location = self.env['stock.location']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from, date_to, x_from_date, x_to_date = False, False, False, False
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        if self.location_ids:
            location_search = self.location_ids
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
            
        opening_in_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_dest_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        opening_out_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        sql = """select x.id as id, x.move_date as move_date, x.date as date, x.name as name, x.type as type, sum(x.qty) as qty, sum(x.price) as price from
                    ((select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'in' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uomt_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_dest_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)
                Union
                (select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'out' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)) x 
                group by
                    x.id,
                    x.move_date,
                    x.date,
                    x.name,
                    x.type
                order by x.move_date"""
        
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y")
            x_to_date = self.date_to
        
        closing_qty, closing_value, price_available = 0.00, 0.00, 0.00 
        tot_open_qty, tot_open_val, tot_bal, tot_val, tot_in_qty, tot_out_qty, tot_in_value, tot_out_value = 0.00, 0.00, 0.00,  0.00,0.00, 0.00, 0.00, 0.00
        result = []
        for each_loc in location_search:
            res = {}
            opening_print, transaction_print = [], []
            qty_available, in_qty, out_qty, balance, price_available,  = 0.00, 0.00, 0.00, 0.00, 0.00 
            opening_in_qty, opening_out_qty, opening_in_value, opening_out_value = 0.00, 0.00, 0.00, 0.00 
            in_value, out_value = 0.00, 0.00
            ###############location Opening Stock Check
            self.env.cr.execute(opening_in_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
            opening_in_data = self.env.cr.dictfetchall()
            self.env.cr.execute(opening_out_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
            opening_out_data = self.env.cr.dictfetchall()
            
            for each_in in opening_in_data:
                opening_in_qty += each_in['qty']
                #if self.show_value:
                #    opening_in_value += (each_in['qty'] * (each_in['price'] and each_in['price'] or 0.00))
            for each_out in opening_out_data:
                opening_out_qty += each_out['qty']
                #if self.show_value:
                #    opening_out_value += (each_out['qty'] * (each_out['price'] and each_out['price'] or 0.00))
            balance = opening_in_qty - opening_out_qty
            if balance:
                opening_print.append('True')
            #price_available = opening_in_value - opening_out_value
            if balance != abs(balance):
                out_qty = abs(balance)
                #out_value = abs(price_available)
            else:
                in_qty = balance
                #in_value = abs(price_available)
            ############### location transaction check
            self.env.cr.execute(sql, (tuple([tz, self.date_from, tz, self.date_to, product.id, each_loc.id,  tz, self.date_from, tz, self.date_to, product.id, each_loc.id])))
            data = self.env.cr.dictfetchall()
            for transaction in data:
                if transaction['type'] == 'in':
                    transaction_print.append('True')
                if transaction['type'] == 'out':
                    transaction_print.append('True')
            if 'True' in opening_print or 'True' in transaction_print:
                tot_open_qty += in_qty
                tot_open_val += in_value
                res = {
                    'location': each_loc.name_get()[0][1],
                    'date': '',
                    'description': "Opening",
                    'open_qty': in_qty,
                    #'open_val': in_value,
                    'in_qty': 0.00,
                    'in_value': 0.00,
                    'out_qty': 0.00,
                    'out_value': 0.00,
                    'balance_qty': balance,
                    #'inventory_value': price_available,
                    }
                in_qty, in_value, out_qty, out_value = 0.00, 0.00, 0.00, 0.00
                for each in data:
                    if each['type'] == 'in':
                        in_qty += each['qty']
                        in_value +=  (each['qty'] * (each['price'] and each['price'] or 0.00))
                        balance += each['qty']
                        #price_available += (each['qty'] * (each['price'] and each['price'] or 0.00))

                    if each['type'] == 'out':
                        out_qty += each['qty']
                        out_value += (each['qty'] * (each['price'] and each['price'] or 0.00))
                        balance -= each['qty']
                        #price_available -= (each['qty'] * (each['price'] and each['price'] or 0.00))
                res['in_qty'] += in_qty
                res['in_value'] += in_value
                res['out_qty'] += out_qty
                res['out_value'] += out_value
                res['balance_qty'] = balance
                #res['inventory_value'] = price_available
                result.append(res)
                tot_in_qty += in_qty
                tot_in_value += in_value
                tot_out_qty += out_qty
                tot_out_value += out_value
                tot_bal += balance
                #tot_val += price_available

        if total_req == 'yes':
            return {
                'tot_open_qty': tot_open_qty,
                #'tot_open_val': tot_open_val,
                'tot_in_qty': tot_in_qty,
                'tot_in_value': tot_in_value,
                'tot_out_qty': tot_out_qty,
                'tot_out_value': tot_out_value,
                'tot_bal': tot_bal,
                #'tot_val': tot_val,
                }
        return result

    
    def action_report_pdf_get_location_detailed_total(self, product):
        self.ensure_one()
        obj_location = self.env['stock.location']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from, date_to, x_from_date, x_to_date = False, False, False, False
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        if self.location_ids:
            location_search = self.location_ids
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
            
        opening_in_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_dest_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        opening_out_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        sql = """select x.id as id, x.move_date as move_date, x.date as date, x.name as name, x.type as type, sum(x.qty) as qty, sum(x.price) as price from
                    ((select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                     (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'in' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_dest_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)
                Union
                (select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                     (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'out' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)) x 
                group by
                    x.id,
                    x.move_date,
                    x.date,
                    x.name,
                    x.type
                order by x.move_date"""
        
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y")
            x_to_date = self.date_to
        
        closing_qty, closing_value, price_available = 0.00, 0.00, 0.00 
        tot_in_qty, tot_out_qty, tot_in_value, tot_out_value = 0.00, 0.00, 0.00, 0.00
        #product_location_data = self.inventory_query([product.id], location_search.ids, x_from_date, x_to_date)
        for each_loc in location_search:
            opening_print, transaction_print = [], []
            qty_available, in_qty, out_qty, balance, price_available,  = 0.00, 0.00, 0.00, 0.00, 0.00 
            opening_in_qty, opening_out_qty, opening_in_value, opening_out_value = 0.00, 0.00, 0.00, 0.00 
            in_value, out_value = 0.00, 0.00
            ###############location Opening Stock Check
            self.env.cr.execute(opening_in_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
            opening_in_data = self.env.cr.dictfetchall()
            self.env.cr.execute(opening_out_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
            opening_out_data = self.env.cr.dictfetchall()
            
            for each_in in opening_in_data:
                opening_in_qty += each_in['qty']
                #if self.show_value:
                #    opening_in_value += (each_in['qty'] * (each_in['price'] and each_in['price'] or 0.00))
            for each_out in opening_out_data:
                opening_out_qty += each_out['qty']
                #if self.show_value:
                #    opening_out_value += (each_out['qty'] * (each_out['price'] and each_out['price'] or 0.00))
            balance = opening_in_qty - opening_out_qty
            if balance:
                opening_print.append('True')
            #price_available = opening_in_value - opening_out_value
            if balance != abs(balance):
                out_qty = abs(balance)
                #out_value = abs(price_available)
            else:
                in_qty = balance
                #in_value = abs(price_available)
            ############### location transaction check
            self.env.cr.execute(sql, (tuple([tz, self.date_from, tz, self.date_to, product.id, each_loc.id,  tz, self.date_from, tz, self.date_to, product.id, each_loc.id])))
            data = self.env.cr.dictfetchall()
            for transaction in data:
                if transaction['type'] == 'in':
                    transaction_print.append('True')
                if transaction['type'] == 'out':
                    transaction_print.append('True')
            if 'True' in opening_print or 'True' in transaction_print:
                for each in data:
                    if each['type'] == 'in':
                        in_qty += each['qty']
                        in_value +=  (each['qty'] * (each['price'] and each['price'] or 0.00))
                        balance += each['qty']
                        #price_available += (each['qty'] * (each['price'] and each['price'] or 0.00))
                    if each['type'] == 'out':
                        out_qty += each['qty']
                        out_value += (each['qty'] * (each['price'] and each['price'] or 0.00))
                        balance -= each['qty']
                        #price_available -= (each['qty'] * (each['price'] and each['price'] or 0.00))
                ############### location wise closing_qty
                closing_qty += balance
                #closing_qty_list = [ x['quantity'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id)]
                #closing_qty = sum(closing_qty_list)
                #closing_qty = product.with_context({'location': each_loc.id, 'from_date': x_from_date or False, 'to_date': x_to_date or False}).qty_available
                #if self.show_value:
                #    closing_quant_search = obj_quant.search([('product_id', '=', product.id), ('location_id', '=', each_loc.id), ('in_date', '>=', x_from_date), ('in_date', '<=', x_to_date)])
                #    for close_quant in closing_quant_search:
                #        closing_value += close_quant.inventory_value
                tot_in_qty += in_qty
                tot_out_qty += out_qty
                tot_in_value += in_value
                tot_out_value += out_value
            ############### All location closing qty
            result = {}
            if closing_qty != abs(closing_qty):
                closing_qty = closing_qty
            result = {
                'description': "All Location Total Closing",
                'in_qty': tot_in_qty,
                'in_value': tot_in_value,
                'out_qty': tot_out_qty,
                'out_value': tot_out_value,
                'balance_qty': closing_qty,
                #'inventory_value': closing_value,
                }
        return result
        
    
    def action_report_product_summary_excel(self):
        self.ensure_one()
        obj_location = self.env['stock.location']
        obj_product = self.env['product.product']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from, date_to, x_from_date, x_to_date = False, False, False, False
        from_des, to_des = "", ""
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        
        categ_str = self.get_categ_str()
        
        if self.location_ids:
            location_search = self.location_ids
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
        if self.product_ids:
            products = self.product_ids
        else:
            if self.categ_ids:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product'), ('categ_id', 'in', [ c.id for c in self.categ_ids ])])
            else:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')])
                
        opening_in_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                        from stock_move sm
                            left join uom_uom um on (sm.product_uom = um.id)
                            left join product_product pp on (sm.product_id = pp.id)
                            left join product_template pt on (pp.product_tmpl_id = pt.id)
                            left join uom_uom uom on (uom.id = pt.uom_id)
                        where sm.state = 'done'
                            and ((sm.date at time zone %s)::timestamp::date) < %s
                            and sm.product_id = %s
                            and sm.location_dest_id = %s
                            and sm.location_id != sm.location_dest_id    
                        group by sm.product_id,
                            sm.id,
                            sm.date,
                            pt.name,
                            sm.product_uom,
                            um.factor,
                            uom.factor
                        """
        opening_out_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        sql = """select x.id as id, x.move_date as move_date, x.date as date, x.name as name, x.type as type, sum(x.qty) as qty, sum(x.price) as price from
                    ((select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'in' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_dest_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)
                Union
                (select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'out' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)) x 
                group by
                    x.id,
                    x.move_date,
                    x.date,
                    x.name,
                    x.type
                order by x.move_date"""
        
        report_name = "Product Wise Stock Summary"
        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 7000
        sheet1.col(1).width = 6000
        sheet1.col(2).width = 4000
        sheet1.col(3).width = 4000
        sheet1.col(4).width = 4000
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 4000
        sheet1.col(7).width = 4000
        sheet1.col(8).width = 4000
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 256 * 2
        sheet1.row(r3).height = 256 * 2
        sheet1.row(r4).height = 256 * 2
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            from_des = " Date From - " + str(date_from)
            x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y")
            to_des = " Date Till - "+ str(date_to)
            x_to_date = self.date_to
        
        if self.show_value:
            sheet1.write_merge(r1, r1, 0, 6, self.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 6, self.warehouse_id.name + report_name, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 0, 6, " ( " + from_des + to_des + " )", Style.title_color())
            sheet1.write_merge(r4, r4, 0, 6, (categ_str and categ_str or "Includes all product categories"), Style.subTitle_left())
        else:
            sheet1.write_merge(r1, r1, 0, 5, self.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 5, self.warehouse_id.name + report_name, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 0, 5, " ( " + from_des + to_des + " )", Style.title_color())
            sheet1.write_merge(r4, r4, 0, 5, (categ_str and categ_str or "Includes all product categories"), Style.subTitle_left())
        row = r4
        closing_qty, closing_value, price_available = 0.00, 0.00, 0.00 
        #product_location_data = self.inventory_query(products.ids, location_search.ids, x_from_date, x_to_date)
        for product in products:
            closing_qty, closing_value, price_available = 0.00, 0.00, 0.00 
            tot_open_qty, tot_open_val, tot_in_qty, tot_out_qty, tot_in_value, tot_out_value = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00 
            product_print = False
            for each_loc in location_search:
                opening_print, transaction_print = [], []
                qty_available, in_qty, out_qty, balance, price_available,  = 0.00, 0.00, 0.00, 0.00, 0.00 
                opening_in_qty, opening_out_qty, opening_in_value, opening_out_value = 0.00, 0.00, 0.00, 0.00 
                in_value, out_value = 0.00, 0.00
                ###############location Opening Stock Check
                self.env.cr.execute(opening_in_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
                opening_in_data = self.env.cr.dictfetchall()
                self.env.cr.execute(opening_out_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
                opening_out_data = self.env.cr.dictfetchall()

                for each_in in opening_in_data:
                    opening_in_qty += each_in['qty']
                    #if self.show_value:
                    #    opening_in_value += (each_in['qty'] * (each_in['price'] and each_in['price'] or 0.00))
                for each_out in opening_out_data:
                    opening_out_qty += each_out['qty']
                    #if self.show_value:
                    #    opening_out_value += (each_out['qty'] * (each_out['price'] and each_out['price'] or 0.00))
                balance = opening_in_qty - opening_out_qty
                if balance:
                    opening_print.append('True')
                #price_available = opening_in_value - opening_out_value
                if balance != abs(balance):
                    out_qty = abs(balance)
                    #out_value = abs(price_available)
                else:
                    in_qty = balance
                    #in_value = abs(price_available)
                ############### location transaction check
                self.env.cr.execute(sql, (tuple([tz, self.date_from, tz, self.date_to, product.id, each_loc.id,  tz, self.date_from, tz, self.date_to, product.id, each_loc.id])))
                data = self.env.cr.dictfetchall()
                for transaction in data:
                    if transaction['type'] == 'in':
                        transaction_print.append('True')
                    if transaction['type'] == 'out':
                        transaction_print.append('True')
                        
                if 'True' in opening_print or 'True' in transaction_print:
                    ############### print product name
                    if not product_print:
                        row = row + 1
                        sheet1.row(row).height = 700
                        if self.show_value:
                            sheet1.write_merge(row, row, 0, 6, (product.name_get()[0][1] + " - " + product.uom_id.name), Style.sub_title_color())
                        else:
                            sheet1.write_merge(row, row, 0, 5, (product.name_get()[0][1] + " - " + product.uom_id.name), Style.sub_title_color())
                        product_print = True
                        row = row + 1
                        sheet1.row(row).height = 300
                        
                        if self.show_value:
                            sheet1.write(row, 0, "Location", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 1, "Opening Qty", Style.contentTextBold(r2,'black','white'))
                            #sheet1.write(row, 2, "Opening Value", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 2, "In Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 3, "In Value", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 4, "Out Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 5, "Out Value", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 6, "Balance Qty", Style.contentTextBold(r2,'black','white'))
                            #sheet1.write(row, 8, "Inventory Value", Style.contentTextBold(r2,'black','white'))
                        else:
                            sheet1.write_merge(row, row, 0, 1, "Location", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 2, "Opening Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 3, "In Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 4, "Out Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 5, "Balance Qty", Style.contentTextBold(r2,'black','white'))

                    qty_in, val_in, qty_out, val_out, qty_bal, val_bal = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
                    row = row + 1
                    for each in data:
                        if each['type'] == 'in':
                            qty_in += each['qty']
                            val_in += (each['qty'] * (each['price'] and each['price'] or 0.00))
                            #price_available += (each['qty'] * (each['price'] and each['price'] or 0.00))
                            balance += each['qty']

                        if each['type'] == 'out':
                            qty_out += each['qty']
                            val_out += (each['qty'] * (each['price'] and each['price'] or 0.00))
                            #price_available -= (each['qty'] * (each['price'] and each['price'] or 0.00))
                            balance -= each['qty']

                    sheet1.row(row).height = 300
                    
                    if self.show_value:
                        sheet1.write(row, 0, each_loc.name_get()[0][1], Style.normal_left())
                        sheet1.write(row, 1, in_qty, Style.normal_num_right_color())
                        #sheet1.write(row, 2, in_value, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 2, qty_in, Style.normal_num_right_color())
                        sheet1.write(row, 3, val_in, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 4, qty_out, Style.normal_num_right_color())
                        sheet1.write(row, 5, val_out, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 6, balance, Style.normal_num_right_color())
                        #sheet1.write(row, 8, price_available, Style.normal_num_right_color_3separator())
                    else:
                        sheet1.write_merge(row, row, 0, 1, each_loc.name_get()[0][1], Style.normal_left())
                        sheet1.write(row, 2, in_qty, Style.normal_num_right_color())
                        sheet1.write(row, 3, qty_in, Style.normal_num_right_color())
                        sheet1.write(row, 4, qty_out, Style.normal_num_right_color())
                        sheet1.write(row, 5, balance, Style.normal_num_right_color())
                    
                    closing_qty += balance
                    #closing_qty_list = [ x['quantity'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id)]
                    #closing_qty = sum(closing_qty_list)
                    #closing_qty += product.with_context({'location': each_loc.id, 'from_date': x_from_date or False, 'to_date': x_to_date or False}).qty_available

                    #closing_value += price_available
                    tot_open_qty += in_qty
                    #tot_open_val+= in_value
                    tot_in_qty += qty_in
                    tot_out_qty += qty_out
                    tot_in_value += val_in
                    tot_out_value += val_out
                
            ############### All location closing qty
            if product_print:
                row = row + 1
                if closing_qty != abs(closing_qty):
                    closing_qty = closing_qty
                if self.show_value:
                    sheet1.write(row, 0, 'All Location Total Closing', Style.groupByTotal())
                    sheet1.write(row, 1, tot_open_qty, Style.groupByTotal3digits())
                    #sheet1.write(row, 2, tot_open_val, Style.groupByTotal3separator())
                    sheet1.write(row, 2, tot_in_qty, Style.groupByTotal3digits())
                    sheet1.write(row, 3, tot_in_value, Style.groupByTotal3separator())
                    sheet1.write(row, 4, tot_out_qty, Style.groupByTotal3digits())
                    sheet1.write(row, 5, tot_out_value, Style.groupByTotal3separator())
                    sheet1.write(row, 6, closing_qty, Style.groupByTotal3digits())
                    #sheet1.write(row, 8, closing_value, Style.groupByTotal3separator())
                else:
                    sheet1.write_merge(row, row, 0, 1, 'All Location Total Closing', Style.groupByTotal())
                    sheet1.write(row, 2, tot_open_qty, Style.groupByTotal3digits())
                    sheet1.write(row, 3, tot_in_qty, Style.groupByTotal3digits())
                    sheet1.write(row, 4, tot_out_qty, Style.groupByTotal3digits())
                    sheet1.write(row, 5, closing_qty, Style.groupByTotal3digits())
        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.register.product.warehouse.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
    
    
    def action_summary_pdf_get_location_search(self):
        final_location = []
        obj_location = self.env['stock.location']
        if self.location_ids:
            location_search = self.location_ids
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
        for each in location_search:
            result = self.action_report_pdf_get_location(None, each)
            if len(result) != 0:
                final_location.append(each)
        location_search = final_location
        return location_search
        
    
    def action_report_pdf_get_location_summary(self, location_search, total_req=None):
        self.ensure_one()
        obj_product = self.env['product.product']
        obj_location = self.env['stock.location']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from, date_to, x_from_date, x_to_date = False, False, False, False
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        if self.product_ids:
            products = self.product_ids
        else:
            if self.categ_ids:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product'), ('categ_id', 'in', [ c.id for c in self.categ_ids ])])
            else:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')])
                
        opening_in_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_dest_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        opening_out_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        sql = """select x.id as id, x.move_date as move_date, x.date as date, x.name as name, x.type as type, sum(x.qty) as qty, sum(x.price) as price from
                    ((select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'in' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_dest_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)
                Union
                (select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'out' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)) x 
                group by
                    x.id,
                    x.move_date,
                    x.date,
                    x.name,
                    x.type
                order by x.move_date"""
        
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y" )
            x_to_date = self.date_to
        for each_loc in location_search:
            closing_qty, closing_value, price_available = 0.00, 0.00, 0.00 
            tot_open_qty, tot_open_val, tot_bal, tot_val, tot_in_qty, tot_out_qty, tot_in_value, tot_out_value = 0.00, 0.00, 0.00,  0.00,0.00, 0.00, 0.00, 0.00
            result = []
            for prod in products:
                res = {}
                opening_print, transaction_print = [], []
                qty_available, in_qty, out_qty, balance, price_available,  = 0.00, 0.00, 0.00, 0.00, 0.00 
                opening_in_qty, opening_out_qty, opening_in_value, opening_out_value = 0.00, 0.00, 0.00, 0.00 
                in_value, out_value = 0.00, 0.00
                ###############location Opening Stock Check
                self.env.cr.execute(opening_in_sql, (tuple([tz, self.date_from, prod.id, each_loc.id])))
                opening_in_data = self.env.cr.dictfetchall()
                self.env.cr.execute(opening_out_sql, (tuple([tz, self.date_from, prod.id, each_loc.id])))
                opening_out_data = self.env.cr.dictfetchall()
                
                for each_in in opening_in_data:
                    opening_in_qty += each_in['qty']
                    #if self.show_value:
                    #    opening_in_value += (each_in['qty'] * (each_in['price'] and each_in['price'] or 0.00))
                for each_out in opening_out_data:
                    opening_out_qty += each_out['qty']
                    #if self.show_value:
                    #    opening_out_value += (each_out['qty'] * (each_out['price'] and each_out['price'] or 0.00))
                balance = opening_in_qty - opening_out_qty
                if balance:
                    opening_print.append('True')
                #price_available = opening_in_value - opening_out_value
                if balance != abs(balance):
                    out_qty = abs(balance)
                    #out_value = abs(price_available)
                else:
                    in_qty = balance
                    #in_value = abs(price_available)
                ############### location transaction check
                self.env.cr.execute(sql, (tuple([tz, self.date_from, tz, self.date_to, prod.id, each_loc.id,  tz, self.date_from, tz, self.date_to, prod.id, each_loc.id])))
                data = self.env.cr.dictfetchall()
                for transaction in data:
                    if transaction['type'] == 'in':
                        transaction_print.append('True')
                    if transaction['type'] == 'out':
                        transaction_print.append('True')
                if 'True' in opening_print or 'True' in transaction_print:
                    tot_open_qty += in_qty
                    tot_open_val += in_value
                    res = {
                        'product': prod.name_get()[0][1],
                        'date': '',
                        'description': "Opening",
                        'open_qty': in_qty,
                        #'open_val': in_value,
                        'in_qty': 0.00,
                        'in_value': 0.00,
                        'out_qty': 0.00,
                        'out_value': 0.00,
                        'balance_qty': balance,
                        #'inventory_value': price_available,
                        }
                    in_qty, in_value, out_qty, out_value = 0.00, 0.00, 0.00, 0.00
                    for each in data:
                        if each['type'] == 'in':
                            in_qty += each['qty']
                            in_value +=  (each['qty'] * (each['price'] and each['price'] or 0.00))
                            balance += each['qty']
                            #price_available += (each['qty'] * (each['price'] and each['price'] or 0.00))

                        if each['type'] == 'out':
                            out_qty += each['qty']
                            out_value += (each['qty'] * (each['price'] and each['price'] or 0.00))
                            balance -= each['qty']
                            #price_available -= (each['qty'] * (each['price'] and each['price'] or 0.00))
                    res['in_qty'] += in_qty
                    res['in_value'] += in_value
                    res['out_qty'] += out_qty
                    res['out_value'] += out_value
                    res['balance_qty'] = balance
                    #res['inventory_value'] = price_available
                    result.append(res)
                    tot_in_qty += in_qty
                    tot_in_value += in_value
                    tot_out_qty += out_qty
                    tot_out_value += out_value
                    tot_bal += balance
                    #tot_val += price_available
        if total_req == 'yes':
            return {
                'tot_open_qty': tot_open_qty,
                #'tot_open_val': tot_open_val,
                'tot_in_qty': tot_in_qty,
                'tot_in_value': tot_in_value,
                'tot_out_qty': tot_out_qty,
                'tot_out_value': tot_out_value,
                'tot_bal': tot_bal,
                #'tot_val': tot_val,
                }
        return result                


    
    def action_report_location_summary_excel(self):
        self.ensure_one()
        obj_location = self.env['stock.location']
        obj_product = self.env['product.product']
        obj_quant = self.env['stock.quant']
        qty_available = 0.00
        date_from, date_to, x_from_date, x_to_date = False, False, False, False
        from_des, to_des = "", ""
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        
        categ_str = self.get_categ_str()
        
        if self.location_ids:
            location_search = self.location_ids
        else:
            location_search = obj_location.search(['|', ('id', 'child_of', self.warehouse_id.view_location_id.id), ('location_id', '=', self.warehouse_id.view_location_id.id), ('usage', '=', 'internal')])
        if self.product_ids:
            products = self.product_ids
        else:
            if self.categ_ids:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product'), ('categ_id', 'in', [ c.id for c in self.categ_ids ])])
            else:
                products = obj_product.search(['|', ('stock_warehouse_ids', 'in', self.warehouse_id.id), ('stock_warehouse_ids', '=', False), ('type', '=', 'product')])
                
        opening_in_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                        from stock_move sm
                            left join uom_uom um on (sm.product_uom = um.id)
                            left join product_product pp on (sm.product_id = pp.id)
                            left join product_template pt on (pp.product_tmpl_id = pt.id)
                            left join uom_uom uom on (uom.id = pt.uom_id)
                        where sm.state = 'done'
                            and ((sm.date at time zone %s)::timestamp::date) < %s
                            and sm.product_id = %s
                            and sm.location_dest_id = %s
                            and sm.location_id != sm.location_dest_id    
                        group by sm.product_id,
                            sm.id,
                            sm.date,
                            pt.name,
                            sm.product_uom,
                            um.factor,
                            uom.factor
                        """
        opening_out_sql = """ select sm.id as id, (uom.factor * (sum(sm.product_qty) / um.factor)) as qty, sum(sm.price_unit) as price
                            from stock_move sm
                                left join uom_uom um on (sm.product_uom = um.id)
	                            left join product_product pp on (sm.product_id = pp.id)
                                left join product_template pt on (pp.product_tmpl_id = pt.id)
                                left join uom_uom uom on (uom.id = pt.uom_id)
                            where sm.state = 'done'
                                and ((sm.date at time zone %s)::timestamp::date) < %s
                                and sm.product_id = %s
                                and sm.location_id = %s
                                and sm.location_id != sm.location_dest_id    
                            group by sm.product_id,
                                sm.id,
                                sm.date,
                                pt.name,
                                sm.product_uom,
                                um.factor,
                                uom.factor
                            """
        sql = """select x.id as id, x.move_date as move_date, x.date as date, x.name as name, x.type as type, sum(x.qty) as qty, sum(x.price) as price from
                    ((select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'in' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_dest_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)
                Union
                (select 
                    sm.id,
                    sm.date as move_date,
                    to_char(sm.date,'dd/mm/YYYY') as date,
                    (case when sm.picking_id is null then sm.name else 
                     (case when sp.name is not null then (case when sm.origin is not null then concat(sp.name, '/', sm.origin) else sp.name end) else '' end) end) as name,
                    'out' as type,
                    (uom.factor * (sum(sm.product_qty) / um.factor)) as qty,
                    sum(sm.price_unit) as price
                from stock_move sm
                    left join uom_uom um on (sm.product_uom = um.id)
	                left join product_product pp on (sm.product_id = pp.id)
                    left join product_template pt on (pp.product_tmpl_id = pt.id)
                    left join uom_uom uom on (uom.id = pt.uom_id)
                    left join stock_picking sp on (sm.picking_id= sp.id)
                where sm.state = 'done'
                    and ((sm.date at time zone %s)::timestamp::date) >= %s
                    and ((sm.date at time zone %s)::timestamp::date)  <= %s
                    and sm.product_id = %s
                    and sm.location_id = %s
                    and sm.location_id != sm.location_dest_id
                group by sm.product_id,
                    sm.id,
                    sm.date,
                    pt.name,
                    sp.name,
                    sm.product_uom,
                    um.factor,
                    uom.factor
                order by sm.date)) x 
                group by
                    x.id,
                    x.move_date,
                    x.date,
                    x.name,
                    x.type
                order by x.move_date"""
        
        report_name = "Location Wise Stock Summary"
        Style = excel_styles.ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(3)
        sheet1.show_grid = False 
        sheet1.col(0).width = 10000
        sheet1.col(1).width = 6000
        sheet1.col(2).width = 4000
        sheet1.col(3).width = 4000
        sheet1.col(4).width = 4000
        sheet1.col(5).width = 4000
        sheet1.col(6).width = 4000
        sheet1.col(7).width = 4000
        sheet1.col(8).width = 4000
        r1 = 0
        r2 = 1
        r3 = 2
        r4 = 3
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 256 * 2
        sheet1.row(r3).height = 256 * 2
        sheet1.row(r4).height = 256 * 2
        if self.date_from:
            # date_from = time.strptime(self.date_from, "%Y-%m-%d")
            date_from = self.date_from.strftime("%d-%m-%Y")
            from_des = " Date From - " + str(date_from)
            x_from_date = self.date_from
        if self.date_to:
            # date_to = time.strptime(self.date_to, "%Y-%m-%d")
            date_to = self.date_to.strftime("%d-%m-%Y")
            to_des = " Date Till - "+ str(date_to)
            x_to_date = self.date_to
        
        if self.show_value:
            sheet1.write_merge(r1, r1, 0, 6, self.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 6, self.warehouse_id.name + report_name, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 0, 6,  " ( " + from_des + to_des + " )", Style.title_color())
            sheet1.write_merge(r4, r4, 0, 6, (categ_str and categ_str or "Includes all product categories"), Style.subTitle_left())
            
            
        else:
            sheet1.write_merge(r1, r1, 0, 5, self.company_id.name, Style.title_color())
            sheet1.write_merge(r2, r2, 0, 5, self.warehouse_id.name + report_name, Style.sub_title_color())
            sheet1.write_merge(r3, r3, 0, 5, " ( " + from_des + to_des + " )", Style.title_color())
            sheet1.write_merge(r4, r4, 0, 5, (categ_str and categ_str or "Includes all product categories"), Style.subTitle_left())
        row = r4
        closing_qty, closing_value, price_available = 0.00, 0.00, 0.00
        #product_location_data = self.inventory_query(products.ids, location_search.ids, x_from_date, x_to_date)
        for each_loc in location_search:
            closing_qty, closing_value, price_available = 0.00, 0.00, 0.00 
            tot_open_qty, tot_open_val, tot_in_qty, tot_out_qty, tot_in_value, tot_out_value = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00 
            location_print = False
            for product in products:
                opening_print, transaction_print = [], []
                qty_available, in_qty, out_qty, balance, price_available,  = 0.00, 0.00, 0.00, 0.00, 0.00 
                opening_in_qty, opening_out_qty, opening_in_value, opening_out_value = 0.00, 0.00, 0.00, 0.00 
                in_value, out_value = 0.00, 0.00
                ###############location Opening Stock Check
                self.env.cr.execute(opening_in_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
                opening_in_data = self.env.cr.dictfetchall()
                self.env.cr.execute(opening_out_sql, (tuple([tz, self.date_from, product.id, each_loc.id])))
                opening_out_data = self.env.cr.dictfetchall()
                
                for each_in in opening_in_data:
                    opening_in_qty += each_in['qty']
                    #if self.show_value:
                    #    opening_in_value += (each_in['qty'] * (each_in['price'] and each_in['price'] or 0.00))
                for each_out in opening_out_data:
                    opening_out_qty += each_out['qty']
                    #if self.show_value:
                    #    opening_out_value += (each_out['qty'] * (each_out['price'] and each_out['price'] or 0.00))
                balance = opening_in_qty - opening_out_qty
                if balance:
                    opening_print.append('True')
                #price_available = opening_in_value - opening_out_value
                if balance != abs(balance):
                    out_qty = abs(balance)
                    #out_value = abs(price_available)
                else:
                    in_qty = balance
                    #in_value = abs(price_available)
                ############### location transaction check
                self.env.cr.execute(sql, (tuple([tz, self.date_from, tz, self.date_to, product.id, each_loc.id,  tz, self.date_from, tz, self.date_to, product.id, each_loc.id])))
                data = self.env.cr.dictfetchall()
                for transaction in data:
                    if transaction['type'] == 'in':
                        transaction_print.append('True')
                    if transaction['type'] == 'out':
                        transaction_print.append('True')
                        
                if 'True' in opening_print or 'True' in transaction_print:
                    ############### print product name
                    if not location_print:
                        row = row + 1
                        sheet1.row(row).height = 700
                        if self.show_value:
                            sheet1.write_merge(row, row, 0, 6, (each_loc.name_get()[0][1]), Style.sub_title_color())
                        else:
                            sheet1.write_merge(row, row, 0, 5, (each_loc.name_get()[0][1]), Style.sub_title_color())
                        location_print = True
                        row = row + 1
                        sheet1.row(row).height = 300
                        
                        if self.show_value:
                            sheet1.write(row, 0, "Product", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 1, "Opening Qty", Style.contentTextBold(r2,'black','white'))
                            #sheet1.write(row, 2, "Opening Value", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 2, "In Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 3, "In Value", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 4, "Out Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 5, "Out Value", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 6, "Balance Qty", Style.contentTextBold(r2,'black','white'))
                            #sheet1.write(row, 8, "Inventory Value", Style.contentTextBold(r2,'black','white'))
                        else:
                            sheet1.write_merge(row, row, 0, 1, "Product", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 2, "Opening Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 3, "In Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 4, "Out Qty", Style.contentTextBold(r2,'black','white'))
                            sheet1.write(row, 5, "Balance Qty", Style.contentTextBold(r2,'black','white'))

                    qty_in, val_in, qty_out, val_out, qty_bal, val_bal = 0.00, 0.00, 0.00, 0.00, 0.00, 0.00
                    row = row + 1
                    for each in data:
                        if each['type'] == 'in':
                            qty_in += each['qty']
                            val_in += (each['qty'] * (each['price'] and each['price'] or 0.00))
                            #price_available += (each['qty'] * (each['price'] and each['price'] or 0.00))
                            balance += each['qty']

                        if each['type'] == 'out':
                            qty_out += each['qty']
                            val_out += (each['qty'] * (each['price'] and each['price'] or 0.00))
                            #price_available -= (each['qty'] * (each['price'] and each['price'] or 0.00))
                            balance -= each['qty']

                    sheet1.row(row).height = 300
                    
                    if self.show_value:
                        sheet1.write(row, 0, product.name_get()[0][1], Style.normal_left())
                        sheet1.write(row, 1, in_qty, Style.normal_num_right_color())
                        #sheet1.write(row, 2, in_value, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 2, qty_in, Style.normal_num_right_color())
                        sheet1.write(row, 3, val_in, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 4, qty_out, Style.normal_num_right_color())
                        sheet1.write(row, 5, val_out, Style.normal_num_right_color_3separator())
                        sheet1.write(row, 6, balance, Style.normal_num_right_color())
                        #sheet1.write(row, 8, price_available, Style.normal_num_right_color_3separator())
                    else:
                        sheet1.write_merge(row, row, 0, 1, product.name_get()[0][1], Style.normal_left())
                        sheet1.write(row, 2, in_qty, Style.normal_num_right_color())
                        sheet1.write(row, 3, qty_in, Style.normal_num_right_color())
                        sheet1.write(row, 4, qty_out, Style.normal_num_right_color())
                        sheet1.write(row, 5, balance, Style.normal_num_right_color())

                    closing_qty += balance
                    #closing_qty_list = [ x['quantity'] for x in product_location_data if (x['product_id'] == product.id) and (x['location_id'] == each_loc.id)]
                    #closing_qty = sum(closing_qty_list)
                    #closing_qty += product.with_context({'location': each_loc.id, 'from_date': x_from_date or False, 'to_date': x_to_date or False}).qty_available

                    #closing_value += price_available
                    #tot_open_qty += in_qty
                    #tot_open_val+= in_value
                    #tot_in_qty += qty_in
                    #tot_out_qty += qty_out
                    tot_in_value += val_in
                    tot_out_value += val_out
                
            ############### All location closing qty
            if location_print:
                row = row + 1
                if closing_qty != abs(closing_qty):
                    closing_qty = closing_qty
                if self.show_value:
                    sheet1.write(row, 0, 'All Location Total Closing', Style.groupByTotal())
                    sheet1.write(row, 1, " ", Style.groupByTotal())
                    #sheet1.write(row, 2, " ", Style.groupByTotal())
                    sheet1.write(row, 2, " ", Style.groupByTotal())
                    sheet1.write(row, 3, tot_in_value, Style.groupByTotal3separator())
                    sheet1.write(row, 4, " ", Style.groupByTotal())
                    sheet1.write(row, 5, tot_out_value, Style.groupByTotal3separator())
                    sheet1.write(row, 6, " ", Style.groupByTotal())
                    #sheet1.write(row, 8, closing_value, Style.groupByTotal3separator())

        stream = BytesIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.b64encode(stream.getvalue()).decode('utf-8')})
        return {
                'name': _('Notification'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.register.product.warehouse.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
