from odoo import api, models, _
import datetime


class ReportPurchaseOrderReport(models.AbstractModel):
    _name = 'report.ebits_custom_purchase.purchase_order_report'
    _description = "Custom Purchase Order Report"

    @api.model
    def _get_report_values(self, docids, data=None):

        return {
            'data': data
        }
