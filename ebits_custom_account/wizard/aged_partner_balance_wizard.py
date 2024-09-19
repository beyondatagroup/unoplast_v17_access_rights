# -*- coding: utf-8 -*-
# Author: Damien Crier, Andrea Stirpe, Kevin Graveman, Dennis Sluijk

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
from odoo.exceptions import UserError

class AgedPartnerBalance(models.TransientModel):
    """Aged partner balance report wizard."""

    _name = 'aged.partner.balance.wizard'
    _description = 'Aged Partner Balance Wizard'

    company_id = fields.Many2one(comodel_name='res.company', default=lambda self: self.env.user.company_id, string='Company')
    date_at = fields.Date(string="Date At", required=True, default=fields.Date.to_string(datetime.today()))
    target_move = fields.Selection([('posted', 'All Posted Entries'),('all', 'All Entries')], string='Target Moves', required=True, default='posted')
    account_ids = fields.Many2many(comodel_name='account.account', string='Filter accounts')
    receivable_accounts_only = fields.Boolean(string="Receivable Accounts Only", default=True)
    payable_accounts_only = fields.Boolean(string="Payable Accounts Only")
    partner_ids = fields.Many2many(comodel_name='res.partner', string='Filter partners')
    show_other_currency = fields.Boolean(string='Show Other Currency')
    show_move_line_details = fields.Boolean(string='Show Move Line Details')
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(AgedPartnerBalance, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(res['arch'])
        for node in doc.xpath("//field[@name='partner_ids']"):
            node.set('domain', "['|', ('customer', '=', True), ('supplier', '=', True), ('parent_id', '=', False)]")
        res['arch'] = etree.tostring(doc)
        return res
                   

    @api.onchange('receivable_accounts_only', 'payable_accounts_only')
    def onchange_type_accounts_only(self):
        """Handle receivable/payable accounts only change."""
        if self.receivable_accounts_only or self.payable_accounts_only:
            domain = []
            if self.receivable_accounts_only and self.payable_accounts_only:
                domain += [('internal_type', 'in', ('receivable', 'payable'))]
            elif self.receivable_accounts_only:
                domain += [('internal_type', '=', 'receivable')]
            elif self.payable_accounts_only:
                domain += [('internal_type', '=', 'payable')]
            self.account_ids = self.env['account.account'].search(domain)
        else:
            self.account_ids = None

    @api.multi
    def button_export_pdf(self):
        self.ensure_one()
        if self.show_other_currency:
            for each in self.partner_ids:
                if each.transaction_currency_id.id == self.company_id.currency_id.id:
                    raise UserError(_("""Selected customer/vendor %s transaction currency is same as company currency.\nIf you want to see the report of other than company's currency transaction, remove the partner which you selected.""") % (each.name_get()[0][1]))
            return self._export(other_currency=True, xlsx_report=False)
        return self._export()

    @api.multi
    def button_export_xlsx(self):
        self.ensure_one()
        if self.show_other_currency:
            for each in self.partner_ids:
                if each.transaction_currency_id.id == self.company_id.currency_id.id:
                    raise UserError(_("""Selected customer/vendor %s transaction currency is same as company currency.\nIf you want to see the report of other than company's currency transaction, remove the partner which you selected.""") % (each.name_get()[0][1]))
            return self._export(other_currency=True, xlsx_report=True)
        return self._export(xlsx_report=True)

    def _prepare_report_aged_partner_balance(self):
        self.ensure_one()
        return {
            'date_at': self.date_at,
            'only_posted_moves': self.target_move == 'posted',
            'company_id': self.company_id.id,
            'filter_account_ids': [(6, 0, self.account_ids.ids)],
            'filter_partner_ids': [(6, 0, self.partner_ids.ids)],
            'show_move_line_details': self.show_move_line_details,
            'show_other_currency': self.show_other_currency,
        }

    def _export(self, other_currency=False, xlsx_report=False):
        """Default export is PDF."""
        model = self.env['report_aged_partner_balance_qweb']
        report = model.create(self._prepare_report_aged_partner_balance())
        return report.print_report(other_currency, xlsx_report)
