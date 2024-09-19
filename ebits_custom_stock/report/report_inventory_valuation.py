# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

from datetime import datetime
import time
from odoo import api, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

class ReportInventoryValuation(models.AbstractModel):
    _name = 'report.ebits_custom_stock.report_inventory_valuation'
    
    def _lines(self, data):
        product_sql = """ """
        location_sql = """ """
        if data['form']['product_id']:
            product_sql += " and sq.product_id  = " + str(data['form']['product_id'][0])
        if data['form']['location_id']:
            location_sql += " and sq.location_id  = " + str(data['form']['location_id'][0])
        inventory_valuation_sql = """select 
	                                    concat('[', pt.default_code, ']', pt.name) as product,
	                                    sq.qty as quantity,
	                                    sl.name as location,
	                                    to_char(sq.in_date, 'dd-mm-yyyy hh24-mi-ss') as date,
	                                    (sq.cost * sq.qty) as inventory_value
                                    from stock_quant sq
	                                    left join product_product pp on (pp.id = sq.product_id)
	                                    left join product_template pt on (pt.id = pp.product_tmpl_id)
	                                    left join stock_location sl on (sl.id = sq.location_id)
                                    where
	                                    sq.create_date <= %s and sl.usage = 'internal' """ + location_sql + product_sql + """ order by sq.in_date desc, sl.name asc, pt.name """ 
        
        self.env.cr.execute(inventory_valuation_sql , (data['form']['request_date'],))
        inventory_valuation_data = self.env.cr.dictfetchall()
        return inventory_valuation_data
    
    
    @api.model
    def render_html(self, docids, data=None):
        docargs = {
            'data': data,
            'time': time,
            'lines': self._lines,
        }  
        return self.env['report'].render('ebits_custom_stock.report_inventory_valuation', docargs)       
        
