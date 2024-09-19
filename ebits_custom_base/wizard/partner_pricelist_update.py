# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import pytz
import datetime
import time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError


class PartnerPricelistUpdate(models.TransientModel):
    _name = "partner.pricelist.update"
    _description = "Partner Pricelist Update"

    partner_id = fields.Many2one("res.partner", string="Customer", required=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    old_pricelist_id = fields.Many2one(
        "product.pricelist", string="Old Pricelist", readonly=True
    )
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        required=True,
    )

    # @api.multi
    def update(self):
        
        id = self.env.context.get('active_id')

        partner = self.env['res.partner'].browse(id)
        
        old_history = ""
        fmt = "%d-%m-%Y %H:%M:%S"
        date = ""
        for each in self:
            
            if not self.env.registry.in_test_mode():
                if each.old_pricelist_id == each.pricelist_id:
                    raise ValidationError(_('Error! You cannot assign the same pricelist as assigned earlier'))
            
            if partner.changes_history:
                old_history = "\n" + partner.changes_history
            date = datetime.datetime.now(
                pytz.timezone(self.env.user.tz or "GMT")
            ).strftime(fmt)
            history = (
                "Pricelist has been updated from "
                + (
                    each.old_pricelist_id
                    and each.old_pricelist_id.name
                    + " ("
                    + each.old_pricelist_id.currency_id.name
                    + ")"
                    or ""
                )
                + " to "
                + (
                    each.pricelist_id.name
                    + " ("
                    + each.pricelist_id.currency_id.name
                    + ")"
                )
                + " By "
                + self.env.user.name
                + " on "
                + date
            )
            partner.write(
                {
                    "property_product_pricelist": each.pricelist_id,
                    "changes_history": history + old_history,
                }
            )

            partner_value_id = self.env.context.get("active_id")
            obj = self.env["res.partner"].browse(partner_value_id)

            # obj.write({"property_product_pricelist": each.pricelist_id.id})

            if obj:
                obj.property_product_pricelist = each.pricelist_id
            print(">>>>>>>>>>>each.pricelist_id>>>>>>>>>>>>>>>",each.pricelist_id.name,self.env.context.get("active_id"),obj.property_product_pricelist)
        return {"type": "ir.actions.act_window_close"}


# class PartnerSalesManagerUpdate(models.TransientModel):
#    _name = 'partner.salesmanager.update'
#    _description = 'Partner Sales Manager Update'

#    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
#    old_sales_manager_id = fields.Many2one("res.users", string="Old Sales Manager", readonly=True)
#    sales_manager_id = fields.Many2one("res.users", string="New Sales Manager", required=True)
#

#    @api.multi
#    def update(self):
#        partner = self.env['res.partner'].browse(self.env.context.get('active_id', False))
#        old_history = ""
#        fmt = "%d-%m-%Y %H:%M:%S"
#        date = ''
#        for each in self:
#            if each.old_sales_manager_id == each.sales_manager_id:
#                raise ValidationError(_('Error! You cannot assign the same sales manager as assigned earlier'))
#            if partner.changes_history:
#                old_history = "\n" + partner.changes_history
#            date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
#            history = "Sales manager has been updated from "+ (each.old_sales_manager_id and each.old_sales_manager_id.name or "")+ " to "+ (each.sales_manager_id and each.sales_manager_id.name or "") + " By " + self.env.user.name + " on " + date
#            partner.write({'sales_manager_id': each.sales_manager_id.id, 'changes_history': history + old_history})
#        return {'type': 'ir.actions.act_window_close'}
#
#
# class PartnerSalesUserUpdate(models.TransientModel):
#    _name = 'partner.salesperson.update'
#    _description = 'Partner Sales User Update'

#    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
#    old_user_id = fields.Many2one("res.users", string="Old Sales Person", readonly=True)
#    user_id = fields.Many2one("res.users", string="New Sales Person", required=True)
#

#    @api.multi
#    def update(self):
#        partner = self.env['res.partner'].browse(self.env.context.get('active_id', False))
#        old_history = ""
#        fmt = "%d-%m-%Y %H:%M:%S"
#        date = ''
#        for each in self:
#            if each.old_user_id == each.user_id:
#                raise ValidationError(_('Error! You cannot assign the same sales person as assigned earlier'))
#            if partner.changes_history:
#                old_history = "\n" + partner.changes_history
#            date = datetime.datetime.now(pytz.timezone(self.env.user.tz or 'GMT')).strftime(fmt)
#            history = "Sales person has been updated from "+ (each.old_user_id and each.old_user_id.name or "")+ " to "+ (each.user_id and each.user_id.name or "") + " By " + self.env.user.name + " on " + date
#            partner.write({'user_id': each.user_id.id, 'changes_history': history + old_history})
#        return {'type': 'ir.actions.act_window_close'}
