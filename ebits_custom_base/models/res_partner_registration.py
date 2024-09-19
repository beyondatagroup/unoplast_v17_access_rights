# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import datetime
import pytz
from datetime import datetime
from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
import odoo.addons.decimal_precision as dp


class PartnerRegistrationDetails(models.Model):
    _name = "res.partner.registration.details"
    _description = 'Partner Registration Details'
    _order = "id desc"

    name = fields.Char(string='Name', copy=False, readonly=True)
    date = fields.Date(string='Date', copy=False, readonly=True)
    title = fields.Many2one('res.partner.title', string='Title', copy=False
                            )
    parent_id = fields.Many2one('res.partner', string='Related Company', copy=False, readonly=True,
                                )
    ref = fields.Char(string='Internal Reference', copy=False, readonly=True,
                      )
    ppf_no = fields.Char('PPF No', copy=False, readonly=True)
    nssf_no = fields.Char('NSSF No', copy=False, readonly=True)
    user_id = fields.Many2one('res.users', string='Created User', readonly=True, default=lambda self: self.env.user)
    sales_user_id = fields.Many2one('res.users', string='Salesperson',
                                    help='The internal user that is in charge of communicating with this contact if any.',
                                    copy=False, readonly=True)
    related_partner_id = fields.Many2one('res.partner', string='Related Partner', readonly=True)
    website = fields.Char(help="Website of Partner or Company", copy=False, readonly=True)
    comment = fields.Text(string='Notes', copy=False, readonly=True)
    category_id = fields.Many2many('res.partner.category', 'res_partner_registration_details_category',
                                   'registration_id', 'category_id', string='Tags', copy=False, readonly=True,
                                   )
    payment_term_id = fields.Many2one('account.payment.term', string='Customer Payment Terms', copy=False,
                                      readonly=True)
    supplier_payment_term_id = fields.Many2one('account.payment.term', string='Vendor Payment Terms', copy=False,
                                               readonly=True)
    # account_receivable_id = fields.Many2one('account.account', string='Account Receivable',
    #                                         domain="[('internal_type', '=', 'receivable'), ('deprecated', '=', False)]",
    #                                         copy=False, readonly=True)

    # account_payable_id = fields.Many2one('account.account', string='Account Payable',
    #                                      domain="[('internal_type', '=', 'payable'), ('deprecated', '=', False)]",
    #                                      copy=False, readonly=True)

    account_receivable_id = fields.Many2one('account.account', string='Account Receivable',
                                            domain="[('deprecated', '=', False)]",
                                            copy=False, readonly=True)

    account_payable_id = fields.Many2one('account.account', string='Account Payable',
                                         domain="[('deprecated', '=', False)]",
                                         copy=False, readonly=True)
    customer = fields.Boolean(string='Is a Customer', default=True,
                              help="Check this box if this contact is a customer.", copy=False, readonly=True,
                              )
    supplier = fields.Boolean(string='Is a Vendor',
                              help="Check this box if this contact is a vendor. If it's not checked, purchase people will not see it when encoding a purchase order.",
                              copy=False, readonly=True)
    employee = fields.Boolean(help="Check this box if this contact is an Employee.", copy=False, readonly=True,
                              )
    contractor = fields.Boolean(help="Check this box if this contact is an Contractor.", copy=False, readonly=True,
                                )
    function = fields.Char(string='Job Position', copy=False, readonly=True)
    type = fields.Selection(
        [('contact', 'Contact'),
         ('invoice', 'Invoice address'),
         ('delivery', 'Shipping address'),
         ('other', 'Other address')], string='Address Type',
        default='contact',
        help="Used to select automatically the right address according to the context in sales and purchases documents.")
    transaction_currency_id = fields.Many2one("res.currency", string="Transaction Currency", copy=False, readonly=True
                                              )
    delivery_warehouse_id = fields.Many2one("stock.warehouse", string="Branch/Delivery Warehouse", copy=False,
                                            readonly=True)
    street = fields.Char(string="street", copy=False, readonly=True)
    street2 = fields.Char(string="street2", copy=False, readonly=True)
    zip = fields.Char(string="ZIP", copy=False, readonly=True)
    city = fields.Char(string="City")
    state_id = fields.Many2one("res.country.state", string="State", copy=False, readonly=True
                               )
    area_id = fields.Many2one("res.state.area", string="Area", copy=False, readonly=True,
                              )
    region_id = fields.Many2one("res.state.region", string="Region", copy=False, readonly=True,
                                )
    country_id = fields.Many2one("res.country", string="Country", copy=False, readonly=True,
                                 )
    email = fields.Char(string="Email", copy=False, readonly=True)
    vat = fields.Char(string='TIN',
                      help="Tax Identification Number.\n Fill it if the company is subjected to taxes.\nUsed by the some of the legal statements.",
                      copy=False, readonly=True)
    vrn_no = fields.Char("VAT", copy=False, readonly=True)
    business_no = fields.Char("Business Licence", copy=False, readonly=True)
    sales_manager_id = fields.Many2one("res.users", string="Sales Manager", copy=False, readonly=True
                                       )
    team_id = fields.Many2one('crm.team', 'Sales Team', copy=False, readonly=True
                              )
    pricelist_id = fields.Many2one('product.pricelist', 'Sale Pricelist',
                                   help="This pricelist will be used, instead of the default one, for sales to the current partner",
                                   copy=False, readonly=True)
    credit_limit = fields.Float(string='Credit Limit', digits='Product Price', copy=False,
                                readonly=True)
    # credit_limit = fields.Float(string='Credit Limit', digits=dp.get_precision('Product Price'), copy=False,
    #                             readonly=True)
    phone = fields.Char("Phone", copy=False, readonly=True)
    # fax = fields.Char("Fax", copy=False, readonly=True)
    mobile = fields.Char("Mobile", copy=False, readonly=True)
    is_company = fields.Boolean(string='Is a Company', default=False,
                                help="Check if the contact is a company, otherwise it is a person", copy=False,
                                readonly=True)
    company_type = fields.Selection(string='Company Type',
                                    selection=[('person', 'Individual'), ('company', 'Company')],
                                    compute='_compute_company_type', readonly=False)
    company_id = fields.Many2one('res.company', 'Company', copy=False, readonly=True,
                                 )
    company_name = fields.Char('Company Name', copy=False, readonly=True)
    color = fields.Integer(string='Color Index', default=0)
    image = fields.Binary("Image", attachment=True,
                          help="This field holds the image used as avatar for this contact, limited to 1024x1024px", )
    image_medium = fields.Binary("Medium-sized image", attachment=True,
                                 help="Medium-sized image of this contact. It is automatically " \
                                      "resized as a 128x128px image, with aspect ratio preserved. " \
                                      "Use this field in form views or some kanban views.")
    image_small = fields.Binary("Small-sized image", attachment=True,
                                help="Small-sized image of this contact. It is automatically " \
                                     "resized as a 64x64px image, with aspect ratio preserved. " \
                                     "Use this field anywhere a small image is required.")
    history = fields.Text(string='History', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting for Approval'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft')

    @api.depends('is_company')
    def _compute_company_type(self):
        for partner in self:
            partner.company_type = 'company' if partner.is_company else 'person'

    @api.onchange('company_type')
    def onchange_company_type(self):
        if self.company_type:
            if self.company_type == 'company':
                self.is_company = True
            else:
                self.is_company = False

    #@api.multi
    def action_send_approval(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.state = 'waiting'
            each.history = each.history and "Sent for approval on " + str(date) + " by " + str(
                self.env.user.name) + "\n " + each.history or "Sent for approval on " + str(date) + " by " + str(
                self.env.user.name)
        return True

    #@api.multi
    def action_reedit(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.state = 'draft'
            each.history = each.history and "Returned for correction on " + str(date) + " by " + str(
                self.env.user.name) + "\n " + each.history or "Returned for correction on " + str(date) + " by " + str(
                self.env.user.name)
        return True

    #@api.multi
    def action_cancel(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        for each in self:
            each.state = 'cancelled'
            each.history = each.history and "Cancelled on " + str(date) + " by " + str(
                self.env.user.name) + "\n " + each.history or "Cancelled on " + str(date) + " by " + str(
                self.env.user.name)
        return True

    #@api.multi
    def action_approve(self):
        fmt = "%d-%m-%Y %H:%M:%S"
        date = datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
        partner_obj = self.env['res.partner']
        property_obj = self.env['ir.property']
        for each in self:
            property_account_payable_id = False
            property_account_receivable_id = False
            #            if each.contractor:
            #                payable_id = property_obj.get('property_account_payable_id', 'res.partner')
            #                property_account_payable_id = payable_id and payable_id.id or False
            #                receivable_id = property_obj.get('property_account_receivable_id', 'res.partner')
            #                property_account_receivable_id = receivable_id and receivable_id.id or False
            #            else:
            property_account_payable_id = each.account_payable_id and each.account_payable_id.id or False
            property_account_receivable_id = each.account_receivable_id and each.account_receivable_id.id or False
            parent_id = partner_obj.create({
                'name': each.name,
                'date': each.date and each.date or False,
                'title': each.title and each.title.id or False,
                'is_company': each.is_company,
                'parent_id': each.parent_id and each.parent_id.id or False,
                'type': each.type and each.type or 'contact',
                'street': each.street and each.street or '',
                'street2': each.street2 and each.street2 or '',
                'city': each.city and each.city or '',
                'area_id': each.area_id and each.area_id.id or False,
                'region_id': each.region_id and each.region_id.id or False,
                'zip': each.zip and each.zip or '',
                'transaction_currency_id': each.transaction_currency_id and each.transaction_currency_id.id or False,
                'delivery_warehouse_id': each.delivery_warehouse_id and each.delivery_warehouse_id.id or False,
                'team_id': each.team_id and each.team_id.id or False,
                'vat': each.vat and each.vat or '',
                'vrn_no': each.vrn_no and each.vrn_no or '',
                'business_no': each.business_no and each.business_no or '',
                'property_product_pricelist': each.pricelist_id and each.pricelist_id.id or False,
                'credit_limit': each.credit_limit and each.credit_limit or 0.00,
                'sales_manager_id': each.sales_manager_id and each.sales_manager_id.id or False,
                'state_id': each.state_id and each.state_id.id or False,
                'country_id': each.country_id and each.country_id.id or False,
                'email': each.email and each.email or '',
                'website': each.website and each.website or '',
                'category_id': [(6, 0, each.category_id)],
                'function': each.function and each.function or '',
                'phone': each.phone and each.phone or '',
                'mobile': each.mobile and each.mobile or '',
                # 'fax': each.fax and each.fax or '',
                'comment': each.comment and each.comment or '',
                'customer_rank': each.customer and each.customer or False,
                'supplier_rank': each.supplier and each.supplier or False,
                'contractor': each.contractor and each.contractor or False,
                'user_id': each.user_id and each.user_id.id or False,
                'property_payment_term_id': each.payment_term_id and each.payment_term_id.id or False,
                'property_supplier_payment_term_id': each.supplier_payment_term_id and each.supplier_payment_term_id.id or False,
                'property_account_payable_id': property_account_payable_id,
                'property_account_receivable_id': property_account_receivable_id,
                'credit_applicable': 'yes',
                'ppf_no': each.ppf_no,
                'nssf_no': each.nssf_no,
            })
            for line in each.child_ids:
                partner_obj.create({
                    'name': line.name,
                    'date': line.date and line.date or False,
                    'title': line.title and line.title.id or False,
                    'parent_id': parent_id and parent_id.id or False,
                    'type': line.type and line.type or '',
                    'street': line.street and line.street or '',
                    'street2': line.street2 and line.street2 or '',
                    'city': line.city and line.city or '',
                    'zip': line.zip and line.zip or '',
                    'state_id': line.state_id and line.state_id.id or False,
                    'country_id': line.country_id and line.country_id.id or False,
                    'email': line.email and line.email or '',
                    'website': line.website and line.website or '',
                    'category_id': [(6, 0, each.category_id)],
                    'function': line.function and line.function or '',
                    'phone': line.phone and line.phone or '',
                    'mobile': line.mobile and line.mobile or '',
                    # 'fax': line.fax and line.fax or '',
                    'comment': each.comment and each.comment or '',
                    'customer_rank': each.customer and each.customer or False,
                    'supplier_rank': each.supplier and each.supplier or False,
                    'contractor': each.contractor and each.contractor or False,
                    'user_id': each.sales_user_id and each.sales_user_id.id or False,
                })
                line.state = 'approved'
            each.state = 'approved'
            each.history = each.history and "Approved on " + str(date) + " by " + str(
                self.env.user.name) + "\n " + each.history or "Approved on " + str(date) + " by " + str(
                self.env.user.name)
            each.related_partner_id = parent_id.id and parent_id.id or False
        return True

    #@api.multi
    def open_parent(self):
        self.ensure_one()
        address_form_id = self.env.ref('base.view_partner_address_form').id
        return {'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'view_mode': 'form',
                'views': [(address_form_id, 'form')],
                'res_id': self.parent_id.id,
                'target': 'new',
                'flags': {'form': {'action_buttons': True}}}

    #@api.multi
    def unlink(self):
        for each in self:
            if not self.env.registry.in_test_mode():
                if each.state != 'draft':
                    raise UserError(_('You can delete a registration form which is only in the draft state.'))
        return super(PartnerRegistrationDetails, self).unlink()


#PartnerRegistrationDetails()


class PartnerRegistrationDetailsInherit(models.Model):
    _inherit = "res.partner.registration.details"

    child_ids = fields.One2many('res.partner.registration.details', 'registration_id', string='Contacts', copy=False)
    registration_id = fields.Many2one('res.partner.registration.details', string='Related Registration',
                                      ondelete='cascade')

