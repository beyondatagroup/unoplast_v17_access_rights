# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import datetime
import hashlib
import pytz
import threading
#import urllib2
#import urlparse
from operator import itemgetter
from email.utils import formataddr
from lxml import etree

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.modules import get_module_resource
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import UserError, ValidationError
#from odoo.osv.orm import browse_record
from itertools import groupby
from odoo.tools.misc import formatLang
import odoo.addons.decimal_precision as dp
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

class ResStateRegion(models.Model):
    _name = "res.state.region"
    _description = "Country Region"
    
    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True, translate=True, size=5)
    state_id = fields.Many2one("res.country.state", string="State")
    country_id = fields.Many2one("res.country", string="Country", required=True)
    
    @api.onchange('state_id')
    def _onchange_state_id(self):
        if self.state_id:
            return {'value': {'country_id': self.state_id.country_id and self.state_id.country_id.id or False}}
        else:
            return {'value': {'country_id': False}}

    
class ResStateArea(models.Model):
    _name = "res.state.area"
    _description = "District's Area/Village"
    
    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True, translate=True, size=5)
    region_id = fields.Many2one("res.state.region", string="Region", required=True)
    state_id = fields.Many2one("res.country.state", string="State")
    country_id = fields.Many2one("res.country", string="Country", required=True)
    
    @api.onchange('region_id')
    def _onchange_region_id(self):
        if self.region_id:
            return {'value': {  'state_id': self.region_id.state_id and self.region_id.state_id.id or False, 
                                'country_id': self.region_id.country_id and self.region_id.country_id.id or False
                            }
                    }
        else:
            return {'value': {'state_id': False, 'country_id': False}}


class Company(models.Model):
    _inherit = "res.company"  
    
    region_id = fields.Many2one("res.state.region", string='Region')
    area_id = fields.Many2one("res.state.area", string='Area')
    discount_account_id = fields.Many2one("account.account", string="Discount Account")  
    
class Pricelist(models.Model):
    _inherit = "product.pricelist"

    def _get_partner_sale_pricelist(self, partner_id, company_id=None):
        """ Retrieve the applicable pricelist for a given partner in a given company.

            :param company_id: if passed, used for looking up properties,
             instead of current user's company
        """
        Partner = self.env['res.partner']
        # Property = self.env['ir.property'].with_context(force_company=company_id or self.env.user.company_id.id)
        Property = self.env['ir.property'].with_company(company_id or self.env.user.company_id.id)

        p = Partner.browse(partner_id)
        pl = Property.get('property_product_pricelist', Partner._name, '%s,%s' % (Partner._name, p.id))
        if pl:
            pl = pl[0].id
            
        if not pl:
            if p.transaction_currency_id:
#                if p.country_id:
#                    pls = self.env['product.pricelist'].search([('country_group_ids.country_ids.code', '=', p.country_id and p.country_id.code or False),('currency_id', '=', p.transaction_currency_id.id)], limit=1)
#                else:
                pls = self.env['product.pricelist'].search([('currency_id', '=', p.transaction_currency_id.id)], limit=1)
                pl = pls and pls[0].id

        if not pl:
            if p.country_id.code:
                pls = self.env['product.pricelist'].search([('country_group_ids.country_ids.code', '=', p.country_id.code)], limit=1)
                pl = pls and pls[0].id

        if not pl:
            # search pl where no country
            pls = self.env['product.pricelist'].search([('country_group_ids', '=', False)], limit=1)
            pl = pls and pls[0].id

        if not pl:
            prop = Property.get('property_product_pricelist', 'res.partner')
            pl = prop and prop[0].id

        if not pl:
            pls = self.env['product.pricelist'].search([], limit=1)
            pl = pls and pls[0].id

        return pl


class Partner(models.Model):
    _inherit = "res.partner"
    
    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()
        
    @api.model
    def _get_credit_applicable(self):
        return 'yes'
        
    ##@api.multi
    def _asset_difference_search_transaction(self, account_type, operator, operand):
        if operator not in ('<', '=', '>', '>=', '<='):
            return []
        if type(operand) not in (float, int):
            return []
        sign = 1
        if account_type == 'payable':
            sign = -1
        res = self._cr.execute('''
            SELECT partner.id
            FROM res_partner partner
            LEFT JOIN account_move_line aml ON aml.partner_id = partner.id
            RIGHT JOIN account_account acc ON aml.account_id = acc.id
            WHERE acc.internal_type = %s
              AND NOT acc.deprecated
            GROUP BY partner.id
            HAVING %s * COALESCE(SUM(aml.amount_residual_currency), 0) ''' + operator + ''' %s''', (account_type, sign, operand))
        res = self._cr.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', map(itemgetter(0), res))]

    @api.model
    def _credit_search_transaction(self, operator, operand):
        return self._asset_difference_search_transaction('receivable', operator, operand)

    @api.model
    def _debit_search_transaction(self, operator, operand):
        return self._asset_difference_search_transaction('payable', operator, operand)
        
    ##@api.multi
    # def _credit_debit_get_transaction(self):
    #     tables, where_clause, where_params = self.env['account.move.line']._query_get()
    #     where_params = [tuple(self.ids)] + where_params
    #     if where_clause:
    #         where_clause = 'AND ' + where_clause
    #     self._cr.execute("""SELECT account_move_line.partner_id, act.type, SUM(account_move_line.amount_residual_currency)
    #                   FROM account_move_line
    #                   LEFT JOIN account_account a ON (account_move_line.account_id=a.id)
    #                   LEFT JOIN account_account_type act ON (a.user_type_id=act.id)
    #                   WHERE act.type IN ('receivable','payable')
    #                   AND account_move_line.partner_id IN %s
    #                   AND account_move_line.reconciled IS FALSE
    #                   """ + where_clause + """
    #                   GROUP BY account_move_line.partner_id, act.type
    #                   """, where_params)
    #     for pid, type, val in self._cr.fetchall():
    #         partner = self.browse(pid)
    #         if type == 'receivable':
    #             partner.credit_transaction = val
    #         elif type == 'payable':
    #             partner.debit_transaction = -val

    def _get_defaultsupplier(self):
        if self._context.get('default_supplier_rank') == 1:
            return True
        else:
            return False

    ##@api.multi
    def _invoice_total_transaction(self):
        account_invoice_report = self.env['account.invoice.report']
        account_invoice_report_obj = self.env['account.invoice.report']
        if not self.ids:
            self.total_invoiced = 0.0
            return True

        user_currency_id = self.env.user.company_id.currency_id.id
        all_partners_and_children = {}
        all_partner_ids = []
        for partner in self:
            # price_total is in the company currency
            all_partners_and_children[partner] = self.search([('id', 'child_of', partner.id)]).ids
            all_partner_ids += all_partners_and_children[partner]

        # searching account.invoice.report via the orm is comparatively expensive
        # (generates queries "id in []" forcing to build the full table).
        # In simple cases where all invoices are in the same currency than the user's company
        # access directly these elements

        # generate where clause to include multicompany rules
        # where_query = account_invoice_report._where_calc([
        #     ('partner_id', 'in', all_partner_ids), ('state', 'not in', ['draft', 'cancel']), ('company_id', '=', self.env.user.company_id.id),
        #     ('type', 'in', ('out_invoice', 'out_refund'))
        # ])

        where_query = account_invoice_report._where_calc([
            ('partner_id', 'in', all_partner_ids), 
            ('state', 'not in', ['draft', 'cancel']), 
            ('company_id', '=', self.env.user.company_id.id),
            ('move_type', 'in', ('out_invoice', 'out_refund'))  # Replaced 'type' with 'move_type'
        ])

        account_invoice_report._apply_ir_rules(where_query, 'read')
        from_clause, where_clause, where_clause_params = where_query.get_sql()

        # price_total is in the company currency
        query = """
                  SELECT id as id, partner_id as partner_id
                    FROM account_invoice_report account_invoice_report
                   WHERE %s
                   GROUP BY id, partner_id
                """ % where_clause
        self.env.cr.execute(query, where_clause_params)
        price_totals = self.env.cr.dictfetchall()
        for partner, child_ids in all_partners_and_children.items():
            total_invoiced_transaction = 0.00
            for price in price_totals:
                if price['partner_id'] in child_ids:
                    account_invoice_report_bro = account_invoice_report_obj.browse(price['id'])
                    total_invoiced_transaction += account_invoice_report_bro.user_currency_price_total * account_invoice_report_bro.currency_rate
            partner.total_invoiced_transaction = total_invoiced_transaction
            #partner.total_invoiced_transaction = sum(account_invoice_report_obj.browse(price['id']).user_currency_price_total for price in price_totals if price['partner_id'] in child_ids)
    
    customer = fields.Boolean(string='Is a Customer', default=False,
                           help="Check this box if this contact is a customer.")

    supplier = fields.Boolean(string='Is a Vendor', default=lambda self: self._get_defaultsupplier(),
                              help="Check this box if this contact is a Vendor.")

    contractor = fields.Boolean(string='Is a Contractor', default=False,
                           help="Check this box if this contact is a contractor.")
    cash_sale = fields.Boolean(string='Cash Sales', default=False,
                           help="Check this box if this customer is a cash sale customer.")
    ppf_no = fields.Char('PPF No')
    nssf_no = fields.Char('NSSF No')
    partner_code = fields.Char("Code", copy=False)
    transaction_currency_id = fields.Many2one("res.currency", string="Transaction Currency", )
    delivery_warehouse_id = fields.Many2one("stock.warehouse", string="Branch/Delivery Warehouse")
    region_id = fields.Many2one("res.state.region", string='Region')
    area_id = fields.Many2one("res.state.area", string='Area')
    vat = fields.Char(string='TIN', help="Tax Identification Number.\n Fill it if the company is subjected to taxes.\nUsed by the some of the legal statements.")
    vrn_no = fields.Char("VAT")
    business_no = fields.Char("Business Licence")
    sales_manager_id = fields.Many2one("res.users", string="Sales Manager")
    team_id = fields.Many2one('crm.team', 'Sales Team')
    credit_applicable = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Credit Limit Applicable?", default=lambda self: self._get_credit_applicable())
    changes_history = fields.Text(string="History", readonly=True)

    # removed compute='_compute_product_pricelist',inverse="_inverse_product_pricelist",
    property_product_pricelist = fields.Many2one(
        'product.pricelist', 'Sale Pricelist',
         company_dependent=False,  # NOT A REAL PROPERTY
        help="This pricelist will be used, instead of the default one, for sales to the current partner")
    # credit_transaction = fields.Monetary(compute='_credit_debit_get_transaction', search=_credit_search_transaction,
    #     string='Total Receivable in Transaction Currency', help="Total amount this customer owes you.", currency_field='transaction_currency_id')
    # debit_transaction = fields.Monetary(compute='_credit_debit_get_transaction', search=_debit_search_transaction, string='Total Payable in Transaction Currency',
    #     help="Total amount you have to pay to this vendor.", currency_field='transaction_currency_id')
    ####################added new
    credit_transaction = fields.Monetary(search=_credit_search_transaction,
        string='Total Receivable in Transaction Currency', help="Total amount this customer owes you.", currency_field='transaction_currency_id')
    debit_transaction = fields.Monetary(search=_debit_search_transaction, string='Total Payable in Transaction Currency',
        help="Total amount you have to pay to this vendor.", currency_field='transaction_currency_id')

    total_invoiced_transaction = fields.Monetary(compute='_invoice_total_transaction', string="Total Invoiced in Transaction Currency",
        groups='account.group_account_invoice', currency_field='transaction_currency_id')
    is_customer = fields.Boolean(default=False)
    is_vendor = fields.Boolean(default=False)



    @api.model
    def default_get(self, fields):
        if self.env.context.get('res_partner_search_mode') == 'supplier':
            self.is_vendor = True
        else:
            self.is_customer = True
        res = super(Partner, self).default_get(fields)
        return res


    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.registry.in_test_mode():
            if not self.env.user.has_group('ebits_custom_base.group_res_partner_create_edit_user'):
                raise UserError(_("You don't have access to create this document. \nContact your administrator"))
        
        partner = super(Partner, self).create(vals_list)
        for p in partner:
            if p.supplier_rank:
                p.supplier = p.supplier_rank
                if not p.partner_code:
                    p.partner_code = self.env['ir.sequence'].next_by_code('res.partner.supplier.code') or ''
            elif p.customer_rank:
                p.customer = p.customer_rank
            
        return partner
        
    ##@api.multi
    def write(self, values):
        all_partners_children = {}
        all_partner_ids = []
        for each in self:
            all_partners_children[each.id] = self.env['res.partner'].search([('id', 'child_of', each.id)]).ids
            all_partner_ids += all_partners_children[each.id]
        if 'delivery_warehouse_id' in values:
            if self.customer:
                for each_inv in self.env['account.move'].sudo().search_read([('partner_id', 'in', all_partner_ids)]):
                    
                    if not self.env.registry.in_test_mode():
                        if each_inv:
                            raise UserError(_('Warehouse/Branch cannot be changed!. \n Already some transaction has been done in invoice side'))
                for each_sale in self.env['sale.order'].sudo().search_read([('partner_id', 'in', all_partner_ids)]):
                    
                    if not self.env.registry.in_test_mode():
                        if each_sale:
                            raise UserError(_('Warehouse/Branch cannot be changed!. \n Already some transaction has been done in sale side'))
                for each_po in self.env['purchase.order'].sudo().search_read([('partner_id', 'in', all_partner_ids)]):
                    
                    if not self.env.registry.in_test_mode():
                        if each_po:
                            raise UserError(_('Warehouse/Branch cannot be changed!. \n Already some transaction has been done in purchase side'))
                for each_pos in self.env['pos.order'].sudo().search_read([('partner_id', 'in', all_partner_ids)]):
                    
                    if not self.env.registry.in_test_mode():
                        if each_pos:
                            raise UserError(_('Warehouse/Branch cannot be changed!. \n Already some transaction has been done in pos side'))
                for each_pay in self.env['account.payment'].sudo().search_read([('partner_id', 'in', all_partner_ids)]):
                    
                    if not self.env.registry.in_test_mode():
                        if each_pay:
                            raise UserError(_('Warehouse/Branch cannot be changed!. \n Already some transaction has been done in payment side'))
        if 'transaction_currency_id' in values:
            if values['transaction_currency_id'] != self.currency_id.id:
                for each_inv in self.env['account.move'].sudo().search_read([('partner_id', 'in', all_partner_ids),('currency_id', '=', self.currency_id.id)]):
                    
                    if not self.env.registry.in_test_mode():
                        if each_inv:
                            raise UserError(_('Transaction Currency cannot be changed!. \n Already some transaction has been done in invoice side'))
                for each_sale in self.env['sale.order'].sudo().search_read([('partner_id', 'in', all_partner_ids),('currency_id', '=', self.currency_id.id)]):
                    
                    if not self.env.registry.in_test_mode():
                        if each_sale:
                            raise UserError(_('Transaction Currency cannot be changed!. \n Already some transaction has been done in sale side'))
                for each_po in self.env['purchase.order'].sudo().search_read([('partner_id', 'in', all_partner_ids),('currency_id', '=', self.currency_id.id)]):
                    
                    if not self.env.registry.in_test_mode():
                        if each_po:
                            raise UserError(_('Transaction Currency cannot be changed!. \n Already some transaction has been done in purchase side'))
                for each_pos in self.env['pos.order'].sudo().search_read([('partner_id', 'in', all_partner_ids),('pricelist_id.currency_id', '=', self.currency_id.id)]):
                    if not self.env.registry.in_test_mode():
                        if each_pos:
                            raise UserError(_('Transaction Currency cannot be changed!. \n Already some transaction has been done in pos side'))
                for each_pay in self.env['account.payment'].sudo().search_read([('partner_id', 'in', all_partner_ids),('currency_id', '=', self.currency_id.id)]):
                    
                    if not self.env.registry.in_test_mode():
                        if each_pay:
                            raise UserError(_('Transaction Currency cannot be changed!. \n Already some transaction has been done in payment side'))
        partner = super(Partner, self).write(values)
        return partner

    @api.onchange('name')
    def onchange_name_rights(self):
        warning = {}
        if self.name:
            if not self.env.user.has_group('ebits_custom_base.group_res_partner_create_edit_user'):
                self.name = ""
                title = ("Warning")
                message = "You don't have access to create this document. \nContact your administrator"
                warning = {
                        'title': title,
                        'message': message,
                        }
        return {'warning': warning}
                
    ##@api.multi
    # @api.depends('country_id')
    # def _compute_product_pricelist(self):
    #     for p in self:
    #         if not isinstance(p.id, models.NewId):  # if not onchange
    #             if p.transaction_currency_id:
    #                 p.property_product_pricelist = self.env['product.pricelist']._get_partner_sale_pricelist(p.id)
    #             else:
    #                 # as _get_partner_pricelist is not there
    #                 # p.property_product_pricelist = self.env['product.pricelist']._get_partner_pricelist(p.id)
    #                 p.property_product_pricelist = self.env['product.pricelist']._get_partner_sale_pricelist(p.id)

    #@api.one
    # def _inverse_product_pricelist(self):
    #     if self.transaction_currency_id:
    #         pls = self.env['product.pricelist'].search(
    #             [('currency_id', '=', self.transaction_currency_id and self.transaction_currency_id.id or self.company_id.currency_id.id)],
    #             limit=1
    #         )
    #     else:
    #         pls = self.env['product.pricelist'].search(
    #             [('country_group_ids.country_ids.code', '=', self.country_id and self.country_id.code or False),('currency_id', '=', self.transaction_currency_id and self.transaction_currency_id.id or self.company_id.currency_id.id)],
    #             limit=1
    #         )
    #     default_for_country = pls and pls[0]
    #     # actual = self.env['ir.property'].get('property_product_pricelist', 'res.partner', 'res.partner,%s' % self.id)
    #     actual = self.env['ir.property']._get('property_product_pricelist', 'res.partner', 'res.partner,%s' % self.id)
    #
    #     # update at each change country, and so erase old pricelist
    #     if self.property_product_pricelist or (actual and default_for_country and default_for_country.id != actual.id):
    #         # keep the company of the current user before sudo
    #         self.env['ir.property'].with_context(force_company=self.env.user.company_id.id).sudo()._set_multi(
    #             'property_product_pricelist',
    #             self._name,
    #             {self.id: self.property_product_pricelist or default_for_country.id},
    #             default_value=default_for_country.id
    #         )


    #@api.one
    # def _inverse_product_pricelist(self):
    #     if self.transaction_currency_id:
    #         pls = self.env['product.pricelist'].search(
    #             [('currency_id', '=', self.transaction_currency_id and self.transaction_currency_id.id or self.company_id.currency_id.id)],
    #             limit=1
    #         )
    #     else:
    #         pls = self.env['product.pricelist'].search(
    #             [('country_group_ids.country_ids.code', '=', self.country_id and self.country_id.code or False),('currency_id', '=', self.transaction_currency_id and self.transaction_currency_id.id or self.company_id.currency_id.id)],
    #             limit=1
    #         )
    #     default_for_country = pls and pls[0]
    #     # actual = self.env['ir.property'].get('property_product_pricelist', 'res.partner', 'res.partner,%s' % self.id)
    #     actual = self.env['ir.property']._get('property_product_pricelist', 'res.partner', 'res.partner,%s' % self.id)

    #     # update at each change country, and so erase old pricelist
    #     if self.property_product_pricelist or (actual and default_for_country and default_for_country.id != actual.id):
    #         # keep the company of the current user before sudo
            
    #         self.env['ir.property'].with_company(self.env.user.company_id.id).sudo()._set_multi(
    #             'property_product_pricelist',
    #             self._name,
    #             {self.id: self.property_product_pricelist or default_for_country.id},
    #             default_value=default_for_country.id
    #         )

    #         # self.env['ir.property'].with_context(force_company=self.env.user.company_id.id).sudo()._set_multi(
    #         #     'property_product_pricelist',
    #         #     self._name,
    #         #     {self.id: self.property_product_pricelist or default_for_country.id},
    #         #     default_value=default_for_country.id
    #         # )

    def _commercial_fields(self):
        return super(Partner, self)._commercial_fields() + ['property_product_pricelist']
    
    @api.onchange('team_id')
    def _onchange_team_id(self):
        domain = {}
        member_ids = []
        if self.team_id:
            domain['sales_manager_id'] = [('id', '=', self.team_id.user_id.id)]
            return {'value': {'sales_manager_id': self.team_id.user_id and self.team_id.user_id.id or False, 'user_id': False},
                    'domain': domain
                        }
        else:
            return {'value': { 'sales_manager_id': False ,'user_id': False},
                    }
    
    @api.onchange('area_id')
    def _onchange_area_id(self):
        if self.area_id:
            return {'value': {  
                    'region_id': self.area_id.region_id and self.area_id.region_id.id or False, 
                    'state_id': self.area_id.state_id and self.area_id.state_id.id or False, 
                    'country_id': self.area_id.country_id and self.area_id.country_id.id or False
                    }}
        else:
            return {'value': { 'region_id': False ,'state_id': False, 'country_id': False}}
            
    ##@api.multi
#     def _compute_display_name(self):
#         res = []
#         for partner in self:
#             name = partner.name or ''
#             partner_code = ''
#             if partner.partner_code:
#                 partner_code = partner.partner_code
#                 name = "[%s] %s" % (partner_code, name)
# #            if partner.transaction_currency_id:
# #                name = "%s (%s)" % (name, partner.transaction_currency_id.symbol)
#             if partner.company_name or partner.parent_id:
#                 if not name and partner.type in ['invoice', 'delivery', 'other']:
#                     name = partner.name and partner or (partner.street and partner.street or partner.street2)
#                     #name = partner._display_address(without_company=True)
#                     #name = dict(self.fields_get(['type'])['type']['selection'])[partner.type]
#                 if not partner.is_company:
#                     name = "%s, %s" % (partner.commercial_company_name or partner.parent_id.name, name)
#             if self._context.get('show_address_only'):
#                 name = partner._display_address(without_company=True)
#             if self._context.get('show_address'):
#                 name = name + "\n" + partner._display_address(without_company=True)
#             #name = name.replace('\n\n', '\n')
#             #name = name.replace('\n\n', '\n')
#             if self._context.get('show_email') and partner.email:
#                 name = "%s <%s>" % (name, partner.email)
#             #if self._context.get('html_format'):
#                 #name = name.replace('\n', '<br/>')
#             res.append((partner.id, name))
#         return res

    # @api.depends('name', 'partner_code', 'company_name', 'parent_id', 'type', 'street', 'street2', 'email', 'transaction_currency_id')
    # def _compute_display_name(self):
    #    res = []
    #    for partner in self:
    #     name = partner.name or ''
    #     if partner.partner_code:
    #         name = "[%s] %s" % (partner.partner_code, name)
            
    #         if partner.company_name or partner.parent_id:
    #             if not name and partner.type in ['invoice', 'delivery', 'other']:
    #                 name = partner.name or partner.street or partner.street2
    #             if not partner.is_company:
    #                 name = "%s, %s" % (partner.commercial_company_name or partner.parent_id.name, name)

    #         if self.env.context.get('show_address_only'):
    #             name = partner._display_address(without_company=True)
    #         if self.env.context.get('show_address'):
    #             name = name + "\n" + partner._display_address(without_company=True)
    #         if self.env.context.get('show_email') and partner.email:
    #             name = "%s <%s>" % (name, partner.email)

    #         partner.display_name = name
    #         res.append((partner.id, name))
        
    #     return res 


    # Remove deprecated method 'name_get' and used _compute_display_name according to current odoo version
    @api.depends('partner_code', 'company_name', 'parent_id', 'type', 'street', 'street2')
    def _compute_display_name(self):
        super()._compute_display_name()
        for partner in self:
            name = partner.name or ''
            if partner.partner_code:
                partner_code = partner.partner_code
                name = "[%s] %s" % (partner_code, name)
            if partner.company_name or partner.parent_id:
                if not name and partner.type in ['invoice', 'delivery', 'other']:
                    name = partner.name or partner.street or partner.street2
                if not partner.is_company:
                    name = "%s, %s" % (partner.commercial_company_name or partner.parent_id.name, name)
            if partner._context.get('show_address_only'):
                name = partner._display_address(without_company=True)
            if partner._context.get('show_address'):
                name += "\n" + partner._display_address(without_company=True)
            if partner._context.get('show_email'):
                name = "%s <%s>" % (name, partner.email)
            partner.display_name = name


    
#     ##@api.multi
#     def name_get(self):
#         res = []
#         for partner in self:
#             name = partner.name or ''
#             partner_code = ''
#             if partner.partner_code:
#                 partner_code = partner.partner_code
#                 name = "[%s] %s" % (partner_code, name)
# #            if partner.transaction_currency_id:
# #                name = "%s (%s)" % (name, partner.transaction_currency_id.symbol)
#             if partner.company_name or partner.parent_id:
#                 if not name and partner.type in ['invoice', 'delivery', 'other']:
#                     name = partner.name and partner or (partner.street and partner.street or partner.street2)
#                     #name = partner._display_address(without_company=True)
#                     #name = dict(self.fields_get(['type'])['type']['selection'])[partner.type]
#                 if not partner.is_company:
#                     name = "%s, %s" % (partner.commercial_company_name or partner.parent_id.name, name)
#             if self._context.get('show_address_only'):
#                 name = partner._display_address(without_company=True)
#             if self._context.get('show_address'):
#                 name = name + "\n" + partner._display_address(without_company=True)
#             #name = name.replace('\n\n', '\n')
#             #name = name.replace('\n\n', '\n')
#             if self._context.get('show_email') and partner.email:
#                 name = "%s <%s>" % (name, partner.email)
#             #if self._context.get('html_format'):
#                 #name = name.replace('\n', '<br/>')
#             res.append((partner.id, name))
#         return res
        
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            self.check_access_rights('read')
            where_query = self._where_calc(args)
            self._apply_ir_rules(where_query, 'read')
            from_clause, where_clause, where_clause_params = where_query.get_sql()
            where_str = where_clause and (" WHERE %s AND " % where_clause) or ' WHERE '

            # search on the name of the contacts and of its company
            search_name = name
            if operator in ('ilike', 'like'):
                search_name = '%%%s%%' % name
            if operator in ('=ilike', '=like'):
                operator = operator[1:]

            unaccent = get_unaccent_wrapper(self.env.cr)

            # commented as contact was not created
            # query = """SELECT id
            #              FROM res_partner
            #           {where} ({partner_code} {operator} {percent}
            #                OR {email} {operator} {percent}
            #                OR {display_name} {operator} {percent}
            #                OR {reference} {operator} {percent})
            #                -- don't panic, trust postgres bitmap
            #          ORDER BY {display_name} {operator} {percent} desc,
            #                   {display_name}
            #         """.format(where=where_str,
            #                    operator=operator,
            #                    partner_code=unaccent('partner_code'),
            #                    email=unaccent('email'),
            #                    display_name=unaccent('display_name'),
            #                    reference=unaccent('ref'),
            #                    percent=unaccent('%s'))
            #
            # where_clause_params += [search_name]*5
            # if limit:
            #     query += ' limit %s'
            #     where_clause_params.append(limit)
            # self.env.cr.execute(query, where_clause_params)
            # partner_ids = map(lambda x: x[0], self.env.cr.fetchall())
            #
            # if partner_ids:
            #     return self.browse(partner_ids).name_get()
            # else:
            #     return []

        return super(Partner, self).name_search(name, args, operator=operator, limit=limit)

    ##@api.multi
    def _display_address(self, without_company=False):

        '''
        The purpose of this function is to build and return an address formatted accordingly to the
        standards of the country where it belongs.

        :param address: browse record of the res.partner to format
        :returns: the address formatted in a display that fit its country habits (or the default ones
            if not country is specified)
        :rtype: string
        '''
        # get the information that will be injected into the display format
        # get the address format
        address_format = self.country_id.address_format or \
              "%(street)s\n%(street2)s\n%(city)s %(region_code)s %(area_code)s %(state_code)s %(zip)s\n%(country_name)s"
        args = {
            'state_code': self.state_id.code or '',
            'state_name': self.state_id.name or '',
            'region_code': self.region_id.code or '',
            'region_name': self.region_id.name or '',
            'area_code': self.area_id.code or '',
            'area_name': self.area_id.name or '',
            'country_code': self.country_id.code or '',
            'country_name': self.country_id.name or '',
            'company_name': self.commercial_company_name or '',
            'nothing':"",
        }
        for field in self._address_fields():
            args[field] = getattr(self, field) or ''
        if without_company:
            args['company_name'] = ''
        elif self.commercial_company_name:
            address_format = '%(company_name)s\n' + address_format
            
        return address_format % args

    def _display_address_depends(self):
        # field dependencies of method _display_address()
        return self._address_fields() + [
            'country_id.address_format', 'country_id.code', 'country_id.name',
            'company_name', 'state_id.code', 'state_id.name', 
            'area_id.code', 'area_id.name', 'region_id.code', 'region_id.name' 
        ]
    
