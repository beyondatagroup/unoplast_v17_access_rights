# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import itertools
import psycopg2

from itertools import groupby
from datetime import datetime, timedelta

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang
import odoo.addons.decimal_precision as dp
#from odoo.exceptions import ValidationError, except_orm


class ResCurrency(models.Model):
    _inherit = 'res.currency'
    
    subcurrency = fields.Char(string="Sub Currency", size=5)
#     rate = fields.Float(compute='_compute_current_rate', string='Current Rate', digits=(12, 20),
#                         help='The rate of the currency to the currency of rate 1.')
#
#     #@api.multi
#     def _compute_current_rate(self):
#         date = self._context.get('date') or fields.Datetime.now()
#         # company_id = self._context.get('company_id') or self.env['res.users']._get_company().id
#         company_id = self._context.get('company_id')
#         # the subquery selects the last rate before 'date' for the given currency/company
#         query = """SELECT c.id, (SELECT r.rate FROM res_currency_rate r
#                                   WHERE r.currency_id = c.id AND r.name <= %s
#                                     AND (r.company_id IS NULL OR r.company_id = %s)
#                                ORDER BY r.company_id, r.name DESC
#                                   LIMIT 1) AS rate
#                    FROM res_currency c
#                    WHERE c.id IN %s"""
#         self._cr.execute(query, (date, company_id, tuple(self.ids)))
#         currency_rates = dict(self._cr.fetchall())
#         for currency in self:
#             currency.rate = currency_rates.get(currency.id) or 1.0
# #ResCurrency()
#
# class CurrencyRate(models.Model):
#     _inherit = "res.currency.rate"
#
#     #name = fields.Datetime(string='Date', required=True, index=True, default=fields.Datetime.now)
#     currency_value = fields.Float('Currency Value', digits=(12, 3))
#     rate = fields.Float(digits=(12, 20), help='The rate of the currency to the currency of rate 1')
#
#     @api.onchange('currency_value')
#     def _onchange_currency_value(self):
#         if self.currency_value:
#             self.rate = 1 / self.currency_value
#         else:
#             self.rate = 0.000000
#         return {}
#CurrencyRate()
