# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.report import report_sxw

class InternalTransferRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(InternalTransferRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.internal.transfer.rml.report', 'account.payment',
      'addons_ebits/ebits_custom_account/report/internal_transfer_report_rml.rml', parser=InternalTransferRmlReport, header=False)
      
class PaymentVoucherRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(PaymentVoucherRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.payment.voucher.rml.report', 'account.payment',
      'addons_ebits/ebits_custom_account/report/payment_voucher_report_rml.rml', parser=PaymentVoucherRmlReport, header=False)
      
class SupplierPaymentVoucherRmlReport(report_sxw.rml_parse):
    def set_context(self, objects, data, ids, report_type = None):
        super(SupplierPaymentVoucherRmlReport,self).set_context(objects, data, ids, report_type)
        
report_sxw.report_sxw('report.supplier.payment.voucher.rml.report', 'account.payment',
      'addons_ebits/ebits_custom_account/report/supplier_payment_voucher_report_rml.rml', parser=SupplierPaymentVoucherRmlReport, header=False)
