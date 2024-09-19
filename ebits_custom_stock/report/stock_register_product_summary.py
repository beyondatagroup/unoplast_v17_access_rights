# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
import time
from odoo import api, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from odoo.report import report_sxw

class StockRegisterProductSummaryRml(report_sxw.rml_parse):

    def set_context(self, objects, data, ids, report_type = None):
        super(StockRegisterProductSummaryRml,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.stockregister.product.summary.rml', 'stock.register.product.warehouse.wizard',
      'addons_ebits/ebits_custom_stock/report/stockregister_product_summary_rml.rml', parser=StockRegisterProductSummaryRml, header=False)
      
class StockRegisterProductSummaryValueRml(report_sxw.rml_parse):

    def set_context(self, objects, data, ids, report_type = None):
        super(StockRegisterProductSummaryValueRml,self).set_context(objects, data, ids, report_type)

report_sxw.report_sxw('report.stockregister.product.summary.value.rml', 'stock.register.product.warehouse.wizard',
      'addons_ebits/ebits_custom_stock/report/stockregister_product_summary_value_rml.rml', parser=StockRegisterProductSummaryValueRml, header=False)
      
class StockRegisterProductDetailedRml(report_sxw.rml_parse):

    def set_context(self, objects, data, ids, report_type = None):
        super(StockRegisterProductDetailedRml,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.stockregister.product.detailed.rml', 'stock.register.product.warehouse.wizard',
      'addons_ebits/ebits_custom_stock/report/stockregister_product_detailed_rml.rml', parser=StockRegisterProductDetailedRml, header=False)
      
class StockRegisterProductDetailedValueRml(report_sxw.rml_parse):

    def set_context(self, objects, data, ids, report_type = None):
        super(StockRegisterProductDetailedValueRml,self).set_context(objects, data, ids, report_type)

report_sxw.report_sxw('report.stockregister.product.detailed.value.rml', 'stock.register.product.warehouse.wizard',
      'addons_ebits/ebits_custom_stock/report/stockregister_product_detailed_value_rml.rml', parser=StockRegisterProductDetailedValueRml, header=False)
      
class ProductStockSummaryValueRml(report_sxw.rml_parse):

    def set_context(self, objects, data, ids, report_type = None):
        super(ProductStockSummaryValueRml,self).set_context(objects, data, ids, report_type)

report_sxw.report_sxw('report.product.stock.summary.value.rml', 'stock.register.product.warehouse.wizard',
      'addons_ebits/ebits_custom_stock/report/product_stock_summary_value_rml.rml', parser=ProductStockSummaryValueRml, header=False)
      
class LocationStockSummaryValueRml(report_sxw.rml_parse):

    def set_context(self, objects, data, ids, report_type = None):
        super(LocationStockSummaryValueRml,self).set_context(objects, data, ids, report_type)

report_sxw.report_sxw('report.location.stock.summary.value.rml', 'stock.register.product.warehouse.wizard',
      'addons_ebits/ebits_custom_stock/report/location_stock_summary_value_rml.rml', parser=LocationStockSummaryValueRml, header=False)
      
      
      
      
      
      
