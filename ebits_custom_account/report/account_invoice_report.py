# -*- coding: utf-8 -*-

from odoo import tools
from odoo import models, fields, api


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"
    
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', readonly=True)
    sales_manager_id = fields.Many2one("res.users", string="Sales Manager", readonly=True)
    team_id = fields.Many2one('crm.team', string='Sales Team')
    region_id = fields.Many2one("res.state.region", string='Region', readonly=True)
    area_id = fields.Many2one("res.state.area", string='Area', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('proforma', 'Pro-forma'),
        ('proforma2', 'Pending For Approval'),
        ('open', 'Open'),
        ('paid', 'Done'),
        ('cancel', 'Cancelled')
        ], string='Invoice Status', readonly=True)
    weight = fields.Float(string='Gross Weight', readonly=True, groups="ebits_custom_base.group_show_weight_report")
    volume = fields.Float(string='Volume', readonly=True, groups="ebits_custom_base.group_show_weight_report")

    _order = 'date desc'

    def _select(self):
        select_str = """
            SELECT sub.id, sub.date, sub.product_id, sub.partner_id, sub.country_id,  sub.region_id, sub.area_id, sub.sales_manager_id, sub.account_analytic_id,
                sub.payment_term_id, sub.uom_name, sub.currency_id, sub.journal_id,
                sub.fiscal_position_id, sub.sales_user_id as user_id, sub.company_id, sub.nbr, sub.type, sub.state,
                sub.weight, sub.volume,
                sub.categ_id, sub.date_due, sub.account_id, sub.account_line_id, sub.partner_bank_id,
                sub.product_qty, sub.price_total as price_total, sub.price_average as price_average,
                COALESCE(cr.rate, 1) as currency_rate, sub.residual as residual, sub.commercial_partner_id as commercial_partner_id, sub.team_id as team_id, sub.warehouse_id 
        """
        return select_str

    def _sub_select(self):
        select_str = """
                SELECT ail.id AS id,
                    ai.date_invoice AS date,
                    ail.product_id, ai.partner_id, ai.payment_term_id, ail.account_analytic_id,
                    u2.name AS uom_name,
                    ai.currency_id, ai.journal_id, ai.fiscal_position_id, ail.sales_user_id as sales_user_id, ai.company_id,
                    1 AS nbr,
                    ai.type, ai.state, pt.categ_id, ai.date_due, ai.account_id, ail.account_id AS account_line_id,
                    ai.partner_bank_id,
                    SUM ((invoice_type.sign * ail.quantity) / (u.factor * u2.factor)) AS product_qty,
                    SUM(ail.price_subtotal_signed) AS price_total,
                    SUM(ABS(ail.price_subtotal_signed)) / CASE
                            WHEN SUM(ail.quantity / u.factor * u2.factor) <> 0::numeric
                               THEN SUM(ail.quantity / u.factor * u2.factor)
                               ELSE 1::numeric
                            END AS price_average,
                    ai.residual_company_signed / (SELECT count(*) FROM account_invoice_line l where invoice_id = ai.id) *
                    count(*) * invoice_type.sign AS residual,
                    ai.commercial_partner_id as commercial_partner_id,
                    partner.country_id, partner.region_id, partner.area_id, partner.sales_manager_id, 
                    SUM(pr.weight * (invoice_type.sign*ail.quantity) / u.factor * u2.factor) AS weight,
                    SUM(pr.volume * (invoice_type.sign*ail.quantity) / u.factor * u2.factor) AS volume, ai.team_id as team_id, ai.warehouse_id 
        """
        return select_str

    def _group_by(self):
        where_sql = ""
#        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
#            warehouse_ids = []
#            for each in self.env.user.sudo().default_warehouse_ids:
#                warehouse_ids.append(each.id)
#            if len(warehouse_ids) > 1:
#                where_sql += " Where ai.warehouse_id in "+ str(tuple(warehouse_ids))
#            else:
#                where_sql += " Where ai.warehouse_id  in ("+ str(warehouse_ids[0]) + ") "
        if where_sql:
            group_by_str = ""
            group_by_str += where_sql
            group_by_str = """ 
                    GROUP BY ail.id, ail.product_id, ail.account_analytic_id, ai.date_invoice, ai.id,
                        ai.partner_id, ai.payment_term_id, u2.name, u2.id, ai.currency_id, ai.journal_id,
                        ai.fiscal_position_id, ail.sales_user_id, ai.company_id, ai.type, invoice_type.sign, ai.state, pt.categ_id,
                        ai.date_due, ai.account_id, ail.account_id, ai.partner_bank_id, ai.residual_company_signed,
                        ai.amount_total_company_signed, ai.commercial_partner_id, partner.country_id, partner.region_id, partner.area_id, partner.sales_manager_id, ai.team_id, ai.warehouse_id """
        else:
            group_by_str = """
                    GROUP BY ail.id, ail.product_id, ail.account_analytic_id, ai.date_invoice, ai.id,
                        ai.partner_id, ai.payment_term_id, u2.name, u2.id, ai.currency_id, ai.journal_id,
                        ai.fiscal_position_id, ail.sales_user_id, ai.company_id, ai.type, invoice_type.sign, ai.state, pt.categ_id,
                        ai.date_due, ai.account_id, ail.account_id, ai.partner_bank_id, ai.residual_company_signed,
                        ai.amount_total_company_signed, ai.commercial_partner_id, partner.country_id, partner.region_id, partner.area_id, partner.sales_manager_id, ai.team_id, ai.warehouse_id """
        return group_by_str
