from datetime import date
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def invoice_test(self):
        print(">>>>>>>>>>>>>>>>>>>>>>>invoice_test>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

        invoice_report_name = 'ebits_custom_sale.report_account_invoice_test'
        vendor_report_name = 'ebits_custom_sale.report_account_vendor_test'

        self.ensure_one()
        if self.move_type == 'out_invoice':  # Customer Invoice
            report_name = invoice_report_name
        elif self.move_type == 'in_invoice':  # Vendor Bill
            print('\nnnnnnnnnnnnn', self.move_type)
            report_name = vendor_report_name
        else:
            return False

        report = self.env.ref(report_name, raise_if_not_found=False)

        if report:

            return report.report_action(self)
        else:

            return False
