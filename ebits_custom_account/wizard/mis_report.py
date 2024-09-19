# -*- coding: utf-8 -*-
# Part of EBITS TechCon

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date
import calendar
import time
from collections import OrderedDict
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
import xlwt
from odoo.exceptions import UserError, ValidationError
import cStringIO
import base64
from xlwt import *

class MisReportWizard(models.TransientModel):
    _name = "mis.report.wizard"
    _description = "MIS Report Wizard"
    
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    comparison = fields.Boolean(string='Compare To Year')
    warehouse_ids = fields.Many2many('stock.warehouse', 'etc_mis_warehouse_rel', 'mis_wizard_id', 'warehouse_id', string='Warehouse', required=True)
    year = fields.Selection(list(reversed([(str(x), str(x)) for x in range((datetime.now().year)-10, datetime.now().year)])), string='Year')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='Format', readonly=True)
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(MisReportWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.user_has_groups('warehouse_stock_restrictions.group_stock_picking_type_allowed'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='warehouse_ids']"):
                warehouse_id = []
                for each in self.env.user.sudo().default_warehouse_ids:
                    warehouse_id.append(each.id)
                node.set('domain', "[('id', 'in', " + str(warehouse_id) + ")]")
            res['arch'] = etree.tostring(doc)
        return res
    
    @api.onchange('date_from', 'date_to')
    def onchange_dates(self):
        warning = {}
        if self.date_from:
            if (datetime.strptime(self.date_from, "%Y-%m-%d")) > datetime.now():
                self.date_from = False
                warning = {
                    'title': _("Warning"),
                    'message': _("You cannot set dates greater than the current date")}
                return {'warning': warning}
        if self.date_to:
            if (datetime.strptime(self.date_to, "%Y-%m-%d")) > datetime.now():
                self.date_to = False
                warning = {
                    'title': _("Warning"),
                    'message': _("You cannot set dates greater than the current date")}
                return {'warning': warning}
                 
    @api.multi
    def get_comparison_date(self):
        dates = []
        from_d = datetime.strptime(self.date_from, "%Y-%m-%d")
        to = datetime.strptime(self.date_to, "%Y-%m-%d")
        if ((int(from_d.month) == 2) and (int(from_d.day) == 29)):
            if not calendar.isleap(int(self.year)):
                dates += [date(int(self.year), int(from_d.month), 28)]
            else:
                dates += [date(int(self.year), int(from_d.month), int(from_d.day))]
        else:
            dates += [date(int(self.year), int(from_d.month), int(from_d.day))]
        if ((int(to.month) == 2) and (int(to.day) == 29)):
            if not calendar.isleap(int(self.year)):
                dates += [date(int(self.year), int(to.month), 28)]
            else:
                dates += [date(int(self.year), int(to.month), int(to.day))]
            
        else:
            dates += [date(int(self.year),int(to.month), int(to.day))]
        return dates
        
    @api.multi
    def _sum_partner_excel(self, data, partner):
        field = "debit - credit"
        result, result_init = 0.00, 0.00
        if data['form']['initial_balance']:
            query_get_data_init = self.env['account.move.line'].with_context(date_from=data['form']['date_from'], date_to=data['form']['date_to'], initial_bal=True, strict_range=True)._query_get()
            reconcile_clause_init = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '
            if len(partner) > 1:
                params_init = [tuple(partner), tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data_init[2]
                query_init = """SELECT sum(""" + field + """)
                        FROM """ + query_get_data_init[0] + """, account_move AS m
                        WHERE "account_move_line".partner_id in %s
                            AND m.id = "account_move_line".move_id
                            AND m.state IN %s
                            AND account_id IN %s
                            AND """ + query_get_data_init[1] + reconcile_clause_init
                self.env.cr.execute(query_init, tuple(params_init))
            else:
                params_init = [partner[0], tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data_init[2]
                query_init = """SELECT sum(""" + field + """)
                        FROM """ + query_get_data_init[0] + """, account_move AS m
                        WHERE "account_move_line".partner_id = %s
                            AND m.id = "account_move_line".move_id
                            AND m.state IN %s
                            AND account_id IN %s
                            AND """ + query_get_data_init[1] + reconcile_clause_init
                self.env.cr.execute(query_init, tuple(params_init))

            contemp_init = self.env.cr.fetchone()
            if contemp_init is not None:
                result_init = contemp_init[0] or 0.0
        
        query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()
        reconcile_clause = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '
        if len(partner) > 1:
            params = [tuple(partner), tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
            query = """SELECT sum(""" + field + """)
                    FROM """ + query_get_data[0] + """, account_move AS m
                    WHERE "account_move_line".partner_id in %s
                        AND m.id = "account_move_line".move_id
                        AND m.state IN %s
                        AND account_id IN %s
                        AND """ + query_get_data[1] + reconcile_clause
            self.env.cr.execute(query, tuple(params))
        else:
            params = [partner[0], tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
            query = """SELECT sum(""" + field + """)
                    FROM """ + query_get_data[0] + """, account_move AS m
                    WHERE "account_move_line".partner_id = %s
                        AND m.id = "account_move_line".move_id
                        AND m.state IN %s
                        AND account_id IN %s
                        AND """ + query_get_data[1] + reconcile_clause
            self.env.cr.execute(query, tuple(params))

        contemp = self.env.cr.fetchone()
        if contemp is not None:
            result = contemp[0] or 0.0
        return result + result_init
        
    def _build_contexts(self, data, all_warehouse_ids):
        result = {}
        journal_obj = self.env['account.journal']
        if len(all_warehouse_ids) > 1:
            journal = journal_obj.search([('stock_warehouse_ids', 'in', all_warehouse_ids)])
            result['journal_ids'] = journal and journal.ids or False
        else:
            journal = journal_obj.search([('stock_warehouse_ids', '=', all_warehouse_ids[0])])
            result['journal_ids'] = journal and journal.ids or False
        #result['journal_ids'] = self.env['account.journal'].search([]).ids
        result['state'] = 'posted'
        result['date_from'] = data['form']['date_from'] or False
        result['date_to'] = data['form']['date_to'] or False
        result['strict_range'] = True if result['date_from'] else False
        return result
        
    @api.multi
    def print_report(self):
        if (self.date_from) and (self.date_to):
            if (datetime.strptime(self.date_from, "%Y-%m-%d").year) != (datetime.strptime(self.date_to, "%Y-%m-%d").year):
                raise UserError(('The dates must be of the same year.'))
            elif ((datetime.strptime(self.date_to, "%Y-%m-%d").month) - (datetime.strptime(self.date_from, "%Y-%m-%d").month) > 2):
                raise UserError(('You cannot set a period of more than three months.'))
        
        invoice_obj = self.env['account.invoice']
        sf_obj = self.env['sf.manufacturing.order']
        partner_obj = self.env['res.partner']
        categ_obj = self.env['product.category']
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']
        ac_type_obj = self.env['account.account.type']
        
        account_type_search = ac_type_obj.search([('name', '=', 'Income'), ('type', '=', 'other')])
        account_type_id =  account_type_search and account_type_search.id or False 
        
        account_type_sql = account_type_id and (" and atp.id = %s" % (account_type_id)) or ""
        
        data = {}
        date_from = self.date_from
        date_to = self.date_to
        
        from_date = time.strptime(self.date_from, "%Y-%m-%d")
        from_date = time.strftime("%d-%m-%Y", from_date)
    
        to_date = time.strptime(self.date_to, "%Y-%m-%d")
        to_date = time.strftime("%d-%m-%Y", to_date)
        filters = "Filter Based on Date From : "+ str(from_date) + " , To : "+ str(to_date) 
        
        all_warehouse_ids = []
        warehouse_list = []
        warehouse_str = ""
        warehouse_sql = """ """
        
        regions = []
        for each_id in self.warehouse_ids:
            all_warehouse_ids.append(each_id.id)
            warehouse_list.append(each_id.name)
        warehouse_list = list(set(warehouse_list))
        warehouse_str = str(warehouse_list).replace("[", "").replace("]", "").replace("u'","").replace("'","")
        if len(all_warehouse_ids) > 1:
            warehouse_sql += " in " + str(tuple(all_warehouse_ids))
            category = categ_obj.search([('warehouse_ids', 'in', all_warehouse_ids), ('type', '!=', 'view')])
            sf_rec = sf_obj.search([('warehouse_id', 'in', tuple(all_warehouse_ids)), ('order_type', '=', 'normal')])
            filters += ", Warehouse : " + warehouse_str
        else:
            warehouse_sql += " = " + str(all_warehouse_ids[0])
            category = categ_obj.search([('warehouse_ids', '=', all_warehouse_ids[0]), ('type', '!=', 'view')])
            sf_rec = sf_obj.search([('warehouse_id', '=', all_warehouse_ids[0]), ('order_type', '=', 'normal')])
            filters += ", Warehouse : "+ warehouse_str
        if self.comparison:
            filters += ", Compared to the year : " + self.year + ", Amount in millions"
        else:
            filters += ", Amount in millions"
        
        data['form'] = self.read(['date_from', 'date_to', 'warehouse_ids'])[0]
        data['form']['date_from'] = date(int(self.year), 1, 1)
        data['computed'] = {}
        data['computed']['move_state'] = ['posted']
        data['form']['initial_balance'] = True
        data['computed']['ACCOUNT_TYPE'] = ['payable', 'receivable', 'liquidity']
        data['form']['reconciled'] = True
        used_context = self._build_contexts(data, all_warehouse_ids)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()
        self.env.cr.execute("""
            SELECT a.id
            FROM account_account a
            WHERE a.internal_type IN %s
                AND NOT a.deprecated""", (tuple(data['computed']['ACCOUNT_TYPE']),))
        data['computed']['account_ids'] = [a for (a,) in self.env.cr.fetchall()]
        params = [tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        reconcile_clause = "" if data['form']['reconciled'] else ' AND "account_move_line".reconciled = false '
        
        warehouse_clause = ""
        warehouse_ids = []
        if data['form']['warehouse_ids']:
            warehouse_clause = ""
            warehouse_ids = data['form']['warehouse_ids']
            if len(warehouse_ids) > 1:
                warehouse_clause += " AND res.delivery_warehouse_id in "+ str(tuple(warehouse_ids))
            else:
                warehouse_clause += " AND res.delivery_warehouse_id = "+ str(warehouse_ids[0])

        partner_clause = ""
        partner_ids = []
        partner_ids = partner_obj.sudo().search(['|', ('customer', '=', True), ('parent_id', '=', False)])
        partner_ids = partner_ids.ids
        if len(partner_ids) > 1:
            partner_clause += """ AND res.id in """ + str(tuple(partner_ids))
        else:
            partner_clause += """ AND res.id in (""" + str(partner_ids[0]) + """)"""
        query = """
            SELECT DISTINCT "account_move_line".partner_id
            FROM """ + query_get_data[0] + """, account_account AS account, account_move AS am, res_partner res
            WHERE "account_move_line".partner_id IS NOT NULL
                AND res.id = "account_move_line".partner_id
                AND "account_move_line".account_id = account.id
                AND am.id = "account_move_line".move_id
                AND am.state IN %s
                AND "account_move_line".account_id IN %s
                AND NOT account.deprecated
                AND """ + query_get_data[1] + reconcile_clause + warehouse_clause + partner_clause
        self.env.cr.execute(query, tuple(params))
        partner_ids = [res['partner_id'] for res in self.env.cr.dictfetchall()]
        partners = partner_obj.sudo().browse(partner_ids)
        partners = sorted(partners, key=lambda x: (x.delivery_warehouse_id, x.region_id))

        report_name = "MIS Report"
        c_period_dates = []
        if self.comparison:
            comp_from, comp_to = self.get_comparison_date()[0], self.get_comparison_date()[1]
            dates = []
            dates.append(comp_from)
            dates.append(comp_to)
            cstart, cend = comp_from, comp_to
            if comp_from != comp_to:
                c_months = OrderedDict(((cstart + timedelta(_)).strftime(r"%b-%y"), None) for _ in xrange((cend - cstart).days)).keys()
            else:
                cend = cend + relativedelta(days = +1)
                c_months = OrderedDict(((cstart + timedelta(_)).strftime(r"%b-%y"), None) for _ in xrange((cend - cstart).days)).keys()
                if len(c_months) > 1:
                    del c_months[-1]
            for c_month in range(len(c_months)):
                month_start = datetime.strptime(c_months[c_month], '%b-%y')
                month_start = month_start.strftime("%Y-%m-%d")
                c_period_dates.append(month_start)
            period_end = comp_to.strftime("%Y-%m-%d")
            c_period_dates.append(period_end)
        dates = []
        dates.append(date_from)
        dates.append(date_to)
        period_dates = []
        start, end = [datetime.strptime(_, "%Y-%m-%d") for _ in dates]
        if date_from != date_to:
            months = OrderedDict(((start + timedelta(_)).strftime(r"%b-%y"), None) for _ in xrange((end - start).days)).keys()
        else:
            end = end + relativedelta(days = +1)
            months = OrderedDict(((start + timedelta(_)).strftime(r"%b-%y"), None) for _ in xrange((end - start).days)).keys()
            if len(months) > 1:
                del months[-1]
        for month in range(len(months)):
            month_start = datetime.strptime(months[month], '%b-%y')
            month_start = month_start.strftime("%Y-%m-%d")
            period_dates.append(month_start)
        period_end = end.strftime("%Y-%m-%d")
        period_dates.append(period_end)
        region_dict = {}
#        for each in partners:
#            if each.region_id and (each.region_id not in regions):
#                if each.region_id in region_dict:
#                    region_dict[each.region_id.id].append(each.id)
#                else:
#                    region_dict[each.region_id.id] = []
#                    region_dict[each.region_id.id].append(each.id)
#                regions.append(each.region_id) 
        region_dict = {}
        for each in partners:
            region_key = ""
            if each.delivery_warehouse_id:
                region_key = each.delivery_warehouse_id.name
            else:
                region_key = "Unknown"
            region_key += "_/_"
            if each.region_id:
                region_key += each.region_id.name
                if region_key in region_dict:
                    region_dict[region_key].append(each.id)
                else:
                    region_dict[region_key] = []
                    region_dict[region_key].append(each.id)
            else:
                region_key += "Unknown"
                if region_key in region_dict:
                    region_dict[region_key].append(each.id)
                else:
                    region_dict[region_key] = []
                    region_dict[region_key].append(each.id)
              
        sf_products = list(set(x.product_id for x in sf_rec))
        summary = OrderedDict(sorted(region_dict.items()))
        categ_from_sql = """ select y.month_year, y.year, y.mm, y.w_c, y.categ, sum(y.amount) as amount from """
        categ_group_sql = """ y
                            group by y.w_c, y.categ, y.year, y.mm, y.month_year
                            order by 
                            y.categ, y.year, y.mm """
                            
        sql = """ (select x.month_year, x.year, x.mm, x.w_c, x.categ, sum(x.sale_value_company_currency) as amount from ((select
                   concat(to_char(inv.date_invoice, 'Mon'), '-', to_char(inv.date_invoice, 'YY')) as month_year,
                   to_char(inv.date_invoice, 'YYYY') as year,
                   to_char(inv.date_invoice, 'MM') as mm,
                   to_char(inv.date_invoice, 'Mon') as month,
                   sum(round(invline.price_subtotal_signed, 2)) as sale_value_company_currency,
                   inv.warehouse_id as warehouse_id,
                   wh.name as warehouse,
                   concat(wh.name, '_/_', pc.name) as w_c,
                   reg.name as region,
                   pc.name as categ
                from
                   account_invoice_line invline
                   left join product_product pp on (pp.id = invline.product_id)
                   left join product_template pt on (pt.id = pp.product_tmpl_id)
                   left join product_category pc on (pc.id = pt.categ_id)
                   left join account_invoice inv on (inv.id = invline.invoice_id)
                   left join stock_warehouse wh on (wh.id = inv.warehouse_id)
                   left join res_partner res on (res.id = inv.partner_id)
                   left join res_state_region reg on (reg.id = res.region_id)
                where
                   inv.date_invoice >= %s and inv.date_invoice <= %s
                   and inv.warehouse_id """ + warehouse_sql + """ 
                   and inv.state in ('open', 'paid')
                   and inv.type in ('out_invoice', 'out_refund')
                group by
                   to_char(inv.date_invoice, 'YYYY'),
                   to_char(inv.date_invoice, 'MM'),
                   to_char(inv.date_invoice, 'Mon'),
                   concat(to_char(inv.date_invoice, 'Mon'), '-', to_char(inv.date_invoice, 'YY')),
                   inv.warehouse_id,
                   wh.name,
                   concat(wh.name, '_/_', reg.name),
                   reg.name,
                   pc.name
                order by 
                   to_char(inv.date_invoice, 'YYYY'),
                   to_char(inv.date_invoice, 'MM'))
                UNION
                (select
                   concat(to_char((pos.date_order at time zone %s)::timestamp::date, 'Mon'), '-', to_char((pos.date_order at time zone %s)::timestamp::date, 'YY')) as month_year,
                   to_char(((pos.date_order at time zone %s)::timestamp::date), 'YYYY') as year,
                   to_char(((pos.date_order at time zone %s)::timestamp::date), 'MM') as mm,
                   to_char(((pos.date_order at time zone %s)::timestamp::date), 'Mon') as month,
                   sum(round(pol.price_subtotal_company_currency, 2)) as sale_value_company_currency,
                   config.warehouse_id as warehouse_id,
                   wh.name as warehouse,
                   concat(wh.name, '_/_', pc.name) as w_c,
                   reg.name as region,
                   pc.name as categ
                from
                   pos_order_line pol
                   left join pos_order pos on (pos.id = pol.order_id)
                   left join product_product pp on (pp.id = pol.product_id)
                   left join product_template pt on (pt.id = pp.product_tmpl_id)
                   left join product_category pc on (pc.id = pt.categ_id)
                   left join res_partner rp on(rp.id = pos.partner_id)
                   left join pos_session session on (session.id = pos.session_id)
                   left join pos_config config on (config.id = session.config_id)
                   left join stock_warehouse wh on (wh.id = config.warehouse_id)
                   left join res_state_region reg on(reg.id = rp.region_id)
                where
                   ((pos.date_order at time zone %s)::timestamp::date) >= %s
                   and ((pos.date_order at time zone %s)::timestamp::date) <= %s
                   and config.warehouse_id """ + warehouse_sql + """ 
                   and pos.state in ('invoiced', 'paid', 'done')
                group by
                   to_char(((pos.date_order at time zone %s)::timestamp::date), 'YYYY'),
                   to_char(((pos.date_order at time zone %s)::timestamp::date), 'MM'),
                   to_char(((pos.date_order at time zone %s)::timestamp::date), 'Mon'),
                   concat(to_char(((pos.date_order at time zone %s)::timestamp::date), 'Mon'), '-', to_char(((pos.date_order at time zone %s)::timestamp::date), 'YY')),
                   config.warehouse_id,
                   wh.name,
                   concat(wh.name, '_/_', reg.name),
                   reg.name,
                   pc.name
                order by 
                   to_char(((pos.date_order at time zone %s)::timestamp::date), 'YYYY'),
                   to_char(((pos.date_order at time zone %s)::timestamp::date), 'MM'))) x  
                   group by x.w_c, x.categ, x.year, x.mm, x.month_year
                order by 
                    x.w_c, x.year, x.mm)
                   """
        
        tz = self.env.user.partner_id.tz and self.env.user.partner_id.tz or 'Africa/Dar_es_Salaam'
        
        sc_sql = """select coalesce(o.s_month_year, o.c_month_year) as month_year,
                        coalesce(o.s_year, o.c_year) as year,
	                    coalesce(o.s_warehouse, o.c_warehouse) as warehouse,
	                    coalesce(o.s_region, o.c_region) as region,
	                    coalesce(o.w_r, o.c_w_r) as w_r,
	                    coalesce(o.sales, 0.00) as sales,
	                    coalesce(o.collection, 0.00) as collection
                    from 
                      (select * from (select concat(to_char(aml.date, 'Mon'), '-', to_char(aml.date, 'YY')) as s_month_year,
                       to_char(aml.	date, 'YYYY') as s_year,
                       to_char(aml.date, 'MM') as s_mm,
                       to_char(aml.date, 'Mon') as s_month,
                       wh.id as s_warehouse_id,
                       wh.name as s_warehouse,
                       ac.name,
                       reg.name as s_region,
                       concat((case when wh.name is not null then wh.name else 'Unknown' end), '_/_', (case when reg.name is not null then reg.name else 'Unknown' end)) as w_r,
                       sum(aml.credit - aml.debit) as sales
                    from
                       account_move_line aml
                       left join account_move am on (am.id = aml.move_id)
                       left join account_account ac on (ac.id = aml.account_id)
                       left join account_account_type atp on (atp.id = ac.user_type_id)
                       left join res_partner rp on(rp.id = aml.partner_id)
                       left join stock_warehouse wh on (wh.id = rp.delivery_warehouse_id)
                       left join res_state_region reg on (reg.id = aml.region_id)
                       left join account_journal aj on (aj.id = am.journal_id)
                    where
                       aml.date >= %s and aml.date <= %s
                       and wh.id """ + warehouse_sql + account_type_sql + """
                       and am.state = 'posted'
                       and atp.type = 'other'
                       and aj.type = 'sale'
                    group by
                       to_char(aml.date, 'YYYY'),
                       to_char(aml.date, 'MM'),
                       to_char(aml.date, 'Mon'),
                       concat(to_char(aml.date, 'Mon'), '-', to_char(aml.date, 'YY')),
                       wh.id,
                       ac.name,
                       reg.name,
                       concat((case when wh.name is not null then wh.name else 'Unknown' end), '_/_', (case when reg.name is not null then reg.name else 'Unknown' end))
                    order by 
                       to_char(aml.date, 'YYYY'),
                       to_char(aml.date, 'MM')) x
                    full join
                    (select concat(to_char(aml.date, 'Mon'), '-', to_char(aml.date, 'YY')) as c_month_year,
                       to_char(aml.date, 'YYYY') as c_year,
                       to_char(aml.date, 'MM') as c_mm,
                       to_char(aml.date, 'Mon') as c_month,
                       wh.id as c_warehouse_id,
                       wh.name as c_warehouse,
                       reg.name as c_region,
                       concat((case when wh.name is not null then wh.name else 'Unknown' end), '_/_', (case when reg.name is not null then reg.name else 'Unknown' end)) as c_w_r,
                       sum(aml.debit - aml.credit) as collection
                    from
                       account_move_line aml
                       left join account_move am on (am.id = aml.move_id)
                       left join account_account ac on (ac.id = aml.account_id)
                       left join account_account_type atp on (atp.id = ac.user_type_id)
                       left join res_partner rp on(rp.id = aml.partner_id)
                       left join stock_warehouse wh on (wh.id = rp.delivery_warehouse_id)
                       left join res_state_region reg on (reg.id = aml.region_id)
                       left join account_journal aj on (aj.id = am.journal_id)
                    where
                       aml.date >= %s and aml.date <= %s
                       and wh.id """ + warehouse_sql + """
                       and am.state = 'posted'
                       and atp.type = 'liquidity'
                       and aj.type in ('cash', 'bank')
                    group by
                       to_char(aml.date, 'YYYY'),
                       to_char(aml.date, 'MM'),
                       to_char(aml.date, 'Mon'),
                       concat(to_char(aml.date, 'Mon'), '-', to_char(aml.date, 'YY')),
                       wh.id,
                       reg.name,
                       concat((case when wh.name is not null then wh.name else 'Unknown' end), '_/_', (case when reg.name is not null then reg.name else 'Unknown' end))
                    order by 
                       to_char(aml.date, 'YYYY'),
                       to_char(aml.date, 'MM')) y on ((y.c_month_year = x.s_month_year) and (x.s_warehouse_id = y.c_warehouse_id) and (x.s_region = y.c_region))) o """
                       


        self.env.cr.execute(sc_sql, (self.date_from, self.date_to, self.date_from, self.date_to,))
        reg_data = self.env.cr.dictfetchall()
        
        self.env.cr.execute(sc_sql, (date(datetime.strptime(self.date_from, "%Y-%m-%d").year, 1, 1), self.date_to, date(datetime.strptime(self.date_from, "%Y-%m-%d").year, 1, 1), self.date_to,))
        cum_data = self.env.cr.dictfetchall()
        sc_regions = []
        if self.comparison:
            self.env.cr.execute(sc_sql, (comp_from, comp_to,comp_from, comp_to,))
            comp_data = self.env.cr.dictfetchall()
            
            self.env.cr.execute(sc_sql, (date(int(self.year), 1, 1), comp_to, date(int(self.year), 1, 1), comp_to,))
            comp_cum_data = self.env.cr.dictfetchall()
            for each in comp_cum_data:
                sc_regions.append(each['w_r'])
        for each in cum_data:
            sc_regions.append(each['w_r'])

        sc_regions = list(set(sc_regions))
        sc_regions = sorted(sc_regions, key=unicode.lower)

        
        Style = ExcelStyles()
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet(report_name)
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(4)
        sheet1.col(0).width = 2000
        sheet1.col(1).width = 6000
        sheet1.col(2).width = 6000
        r1 = 0
        r2 = 1
        r3 = 2
        rt = 3
        r4 = 4
        sheet1.row(r1).height = 500
        sheet1.row(r2).height = 400
        sheet1.row(r3).height = 200 * 2
        sheet1.row(rt).height = 200 * 2
        sheet1.row(r4).height = 200 * 3
        title = report_name + " ( Date From " + from_date + " To " + to_date + " )"
        title1 = self.company_id.name
        title2 = filters
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 1, "Warehouse", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 2, "Region", Style.contentTextBold(r2, 'black', 'white'))
        months_col = 2
        month_index, c_month_index = {}, {}
        for month in range(len(months)):
            months_col += 1
            sheet1.write(r4, months_col, (months[month] + ' Sales'), Style.groupByTitleIb())
            month_index[months[month]] = months_col
            months_col += 1
            sheet1.write(r4, months_col, (months[month] + ' Collection'), Style.groupByTitleIb())
            if self.comparison:
                months_col += 1
                sheet1.write(r4, months_col, (c_months[month] + ' Sales'), Style.groupByTitleTan())
                c_month_index[c_months[month]] = months_col
                months_col += 1
                sheet1.write(r4, months_col, (c_months[month] + ' Collection'), Style.groupByTitleTan())
        sheet1.col(months_col + 2).width = 3700
        sheet1.write(r4, (months_col + 2), ("CUM Sales "+ str(datetime.strptime(self.date_from, "%Y-%m-%d").year)), Style.groupByTitleIb())
        sheet1.col(months_col + 3).width = 3700
        sheet1.write(r4, (months_col + 3), ("CUM Collection "+ str(datetime.strptime(self.date_from, "%Y-%m-%d").year)), Style.groupByTitleIb())
        title_end = (months_col + 3)
        if self.comparison:
            sheet1.col(months_col + 4).width = 3700
            sheet1.col(months_col + 5).width = 3700
            sheet1.write(r4, (months_col + 4), ("CUM Sales " + self.year ), Style.groupByTitleTan())
            sheet1.write(r4, (months_col + 5), ("CUM Collection " + self.year ), Style.groupByTitleTan())
            title_end = (months_col + 5)
        
        
        sheet1.write_merge(r1, r1, 0, title_end, title1, Style.main_title())
        sheet1.write_merge(r2, r2, 0, title_end, title, Style.sub_main_title())
        sheet1.write_merge(r3, r3, 0, title_end, title2, Style.subTitle())
        sheet1.write_merge(rt, rt, 0, title_end, "Regional Sales Report", Style.subTitle())
        
        row = 4
        start_row = 4 + 1
        s_no = 0
        region = ''
        warehouse = ''
        reg_amount, cum_amount, com_amount, comp_cum_amount = 0.00, 0.00, 0.00, 0.00
        col_amount, cum_col_amount, com_col_amount, comp_cum_col_amount = 0.00, 0.00, 0.00, 0.00
        for each in sc_regions:
            s_no += 1
            row += 1
            warehouse = each.split('_/_')[0]
            region = each.split('_/_')[1]
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, warehouse, Style.normal_left())
            sheet1.write(row, 2, region, Style.normal_left())
            for m in month_index:
                reg_amount = sum([x['sales'] if (x['w_r'] and x['w_r'] == each and x['month_year'] == m) else 0.00 for x in reg_data])
                sheet1.write(row, month_index[m], round((reg_amount/1000000.00), 2), Style.normal_right())
                col_amount = sum([x['collection'] if (x['w_r'] and x['w_r'] == each and x['month_year'] == m) else 0.00 for x in reg_data])
                sheet1.write(row, (month_index[m] + 1), round((col_amount/1000000.00), 2), Style.normal_right())
            cum_amount = sum([x['sales'] if (x['w_r'] and x['w_r'] == each and x['year'] == str(datetime.strptime(self.date_from, "%Y-%m-%d").year)) else 0.00 for x in cum_data])
            cum_col_amount = sum([x['collection'] if (x['w_r'] and x['w_r'] == each and x['year'] == str(datetime.strptime(self.date_from, "%Y-%m-%d").year)) else 0.00 for x in cum_data])
            sheet1.write(row, (months_col + 2), round((cum_amount/1000000.00), 2), Style.normal_right())
            sheet1.write(row, (months_col + 3), round((cum_col_amount/1000000.00), 2), Style.normal_right())
            if self.comparison:
                for c in c_month_index:
                    com_amount = sum([x['sales'] if (x['w_r'] and x['w_r'] == each and x['month_year'] == c) else 0.00 for x in comp_data])
                    sheet1.write(row, c_month_index[c], round((com_amount/1000000.00), 2), Style.normal_right())
                    com_col_amount = sum([x['collection'] if (x['w_r'] and x['w_r'] == each and x['month_year'] == c) else 0.00 for x in comp_data])
                    sheet1.write(row, (c_month_index[c] + 1), round((com_col_amount/1000000.00), 2), Style.normal_right())
    
                comp_cum_amount = sum([x['sales'] if (x['w_r'] and x['w_r'] == each and x['year'] == self.year) else 0.00 for x in comp_cum_data])
                sheet1.write(row, (months_col + 4), round((comp_cum_amount/1000000.00), 2), Style.normal_right())
                comp_cum_col_amount = sum([x['collection'] if (x['w_r'] and x['w_r'] == each and x['year'] == self.year) else 0.00 for x in comp_cum_data])
                sheet1.write(row, (months_col + 5), round((comp_cum_col_amount/1000000.00), 2), Style.normal_right())
        sheet1.write_merge(row+1, row + 1, 0, 2, "Total", Style.groupByTitle())
        mr = self.comparison and (months_col + 6) or (months_col + 4)
        for i in range(3, mr):
            if i == months_col + 1:
                continue
            start = xlwt.Utils.rowcol_to_cell(4, i)
            end = xlwt.Utils.rowcol_to_cell(row, i)
            sheet1.write(row+1, i, Formula(('sum(' + str(start) + ':' + str(end) + ')')), Style.normal_num_right_2digits_color())
        
        #*************Category Based Report*****************
        w_categ = []
        self.env.cr.execute((categ_from_sql + sql + categ_group_sql), (self.date_from, self.date_to, tz, tz, tz, tz, tz, tz, self.date_from, tz, self.date_to, tz, tz, tz, tz, tz, tz, tz,))
        categ_data = self.env.cr.dictfetchall()
        
        self.env.cr.execute((categ_from_sql + sql + categ_group_sql), (date(datetime.strptime(self.date_from, "%Y-%m-%d").year, 1, 1), self.date_to, tz, tz, tz, tz, tz, tz, date(datetime.strptime(self.date_from, "%Y-%m-%d").year, 1, 1), tz, self.date_to, tz, tz, tz, tz, tz, tz, tz,))
        categ_cum_data = self.env.cr.dictfetchall()
        for each in categ_cum_data:
            w_categ.append(each['w_c'])
        if self.comparison:
            self.env.cr.execute((categ_from_sql + sql + categ_group_sql), (comp_from, comp_to, tz, tz, tz, tz, tz, tz, comp_from, tz, comp_to, tz, tz, tz, tz, tz, tz, tz,))
            categ_comp_data = self.env.cr.dictfetchall()
            
            self.env.cr.execute((categ_from_sql + sql + categ_group_sql), (date(int(self.year), 1, 1), comp_to, tz, tz, tz, tz, tz, tz, date(int(self.year), 1, 1), tz, comp_to, tz, tz, tz, tz, tz, tz, tz,))
            categ_comp_cum = self.env.cr.dictfetchall()
            for each in categ_comp_cum:
                w_categ.append(each['w_c'])

        w_categ = list(set(w_categ))
        w_categ = sorted(w_categ, key=unicode.lower)                
        
        rt = row + 3
        r4 = rt + 1
        sheet1.row(rt).height = 200 * 2
        sheet1.row(r4).height = 200 * 3
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 1, "Warehouse", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 2, "Product Category", Style.contentTextBold(r2, 'black', 'white'))
        months_col = 2
        month_index, c_month_index = {}, {}
        for month in range(len(months)):
            months_col += 1
            sheet1.write(r4, months_col, months[month], Style.groupByTitleIb())
            month_index[months[month]] = months_col
            if self.comparison:
                months_col += 1
                sheet1.write(r4, months_col, c_months[month], Style.groupByTitleTan())
                c_month_index[c_months[month]] = months_col
        sheet1.write(r4, (months_col + 2), ("CUM "+ str(datetime.strptime(self.date_from, "%Y-%m-%d").year)), Style.groupByTitleIb())
        title_end = (months_col + 2)
        if self.comparison:
            sheet1.write(r4, (months_col + 3), ("CUM " + self.year ), Style.groupByTitleTan())
            title_end = (months_col + 3)
            
        sheet1.write_merge(rt, rt, 0, title_end, "Category Wise Sales Report", Style.subTitle())
        
        row = r4
        start_row = r4 + 1
        s_no = 0
        cat_amount, cat_cum_amount, cat_com_amount, comp_cum_amount = 0.00, 0.00, 0.00, 0.00
        for each in w_categ:
            warehouse  = each.split('_/_')[0]
            category = each.split('_/_')[1]
            s_no += 1
            row += 1
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, warehouse, Style.normal_left())
            sheet1.write(row, 2, category, Style.normal_left())
            for m in month_index:
                cat_amount = sum([x['amount'] if (x['w_c'] and x['w_c'] == each and x['month_year'] == m) else 0.00 for x in categ_data])
                sheet1.write(row, month_index[m], round((cat_amount/1000000.00), 2), Style.normal_right())
            cat_cum_amount = sum([x['amount'] if (x['w_c'] and x['w_c'] == each and x['year'] == str(datetime.strptime(self.date_from, "%Y-%m-%d").year)) else 0.00 for x in categ_cum_data])
            sheet1.write(row, (months_col + 2), round((cat_cum_amount/1000000.00), 2), Style.normal_right())
            if self.comparison:
                for c in c_month_index:
                    cat_com_amount = sum([x['amount'] if (x['w_c'] and x['w_c'] == each and x['month_year'] == c) else 0.00 for x in categ_comp_data])
                    sheet1.write(row, c_month_index[c], round((cat_com_amount/1000000.00), 2), Style.normal_right())
    
                comp_cum_amount = sum([x['amount'] if (x['w_c'] and x['w_c'] == each and x['year'] == self.year) else 0.00 for x in categ_comp_cum])
                sheet1.write(row, (months_col + 3), round((comp_cum_amount/1000000.00), 2), Style.normal_right())
        sheet1.write_merge(row + 1, row + 1, 0, 2, "Total", Style.groupByTitle())
        mr = self.comparison and (months_col + 4) or (months_col + 3)
        for i in range(3, (mr)):
            if i == months_col + 1:
                continue
            start = xlwt.Utils.rowcol_to_cell(start_row, i)
            end = xlwt.Utils.rowcol_to_cell(row, i)
            sheet1.write(row + 1, i, Formula(('sum(' + str(start) + ':' + str(end) + ')')), Style.normal_num_right_2digits_color())
        
        #******************Monthly outstanding Debtors Report**************
        rt = row + 3
        r4 = rt + 1
        sheet1.row(r4).height = 200 * 3
        
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 1, "Warehouse", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 2, "Region", Style.contentTextBold(r2, 'black', 'white'))
        months_col = 2
        month_index, c_month_index = {}, {}
        for month in range(len(months)):
            months_col += 1
            sheet1.write(r4, months_col, months[month], Style.groupByTitleIb())
            month_index[months[month]] = months_col
            if self.comparison:
                months_col += 1
                sheet1.write(r4, months_col, c_months[month], Style.groupByTitleTan())
                c_month_index[c_months[month]] = months_col
        sheet1.write(r4, (months_col + 2), ("CUM "+ str(datetime.strptime(self.date_from, "%Y-%m-%d").year)), Style.groupByTitleIb())
        title_end = (months_col + 2)
        if self.comparison:
            sheet1.write(r4, (months_col + 3), ("CUM " + self.year ), Style.groupByTitleTan())
            title_end = (months_col + 3)
        sheet1.write_merge(rt, rt, 0, title_end, "Outstanding Debtors Report", Style.subTitle())
        row = r4
        start_row = r4 + 1
        s_no = 0
        reg_amount, cum_amount, com_amount, comp_cum_amount = 0.00, 0.00, 0.00, 0.00
        data['form']['initial_balance'] = False
        for each in summary:
            s_no += 1
            row += 1
            warehouse = each.split('_/_')[0]
            region = each.split('_/_')[1]
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, warehouse, Style.normal_left())
            sheet1.write(row, 2, region, Style.normal_left())
            i = 0
            for m in month_index:
                month_data = data
                month_data['form']['date_from'] = period_dates[i]
                month_data['form']['used_context']['date_from'] = period_dates[i]
                if i == len(month_index) - 1:
                    period_dates_end = datetime.strptime(period_dates[i + 1], "%Y-%m-%d")
                    month_data['form']['date_to'] = period_dates[i + 1]
                    month_data['form']['used_context']['date_to'] = period_dates[i + 1]
                else:
                    period_dates_end = datetime.strptime(period_dates[i + 1], "%Y-%m-%d")
                    period_dates_end = period_dates_end - timedelta(days=1)
                    period_dates_end = period_dates_end.strftime("%Y-%m-%d")
                    month_data['form']['date_to'] = period_dates_end
                    month_data['form']['used_context']['date_to'] = period_dates_end
                tot_balance = self._sum_partner_excel(month_data, region_dict[each])
                sheet1.write(row, month_index[m], round((tot_balance/1000000.00), 2), Style.normal_right())
                i =+ 1
            month_data = data
            month_data['form']['date_from'] = date(datetime.strptime(self.date_from, "%Y-%m-%d").year, 1, 1).strftime("%Y-%m-%d")
            month_data['form']['date_to'] = self.date_to
            month_data['form']['used_context']['date_from'] = date(datetime.strptime(self.date_from, "%Y-%m-%d").year, 1, 1).strftime("%Y-%m-%d")
            month_data['form']['used_context']['date_to'] = self.date_to
            tot_balance = self._sum_partner_excel(month_data, region_dict[each])
            sheet1.write(row, (months_col + 2), round((tot_balance/1000000.00), 2), Style.normal_right())
            if self.comparison:
                j = 0
                for m in c_month_index:
                    month_data = data
                    month_data['form']['date_from'] = c_period_dates[j]
                    month_data['form']['used_context']['date_from'] = c_period_dates[j]
                    if j == len(c_month_index) - 1:
                        period_dates_end =  datetime.strptime(c_period_dates[j + 1], "%Y-%m-%d")
                        month_data['form']['date_to'] =  c_period_dates[j + 1]
                        month_data['form']['used_context']['date_to'] = c_period_dates[j + 1]
                    else:
                        period_dates_end =  datetime.strptime(c_period_dates[j + 1], "%Y-%m-%d")
                        period_dates_end = period_dates_end - timedelta(days=1)
                        period_dates_end = period_dates_end.strftime("%Y-%m-%d")
                        month_data['form']['date_to'] = period_dates_end
                        month_data['form']['used_context']['date_to'] = period_dates_end

                    tot_balance = self._sum_partner_excel(month_data, region_dict[each])
                    sheet1.write(row, c_month_index[m], round((tot_balance/1000000.00), 2), Style.normal_right())
                    j =+ 1
                
                month_data = data
                month_data['form']['date_from'] = date(int(self.year), 1, 1).strftime("%Y-%m-%d")
                month_data['form']['used_context']['date_from'] = date(int(self.year), 1, 1).strftime("%Y-%m-%d")
                month_data['form']['date_to'] = comp_to.strftime("%Y-%m-%d")
                month_data['form']['used_context']['date_to'] = comp_to.strftime("%Y-%m-%d")
                tot_balance = self._sum_partner_excel(month_data, region_dict[each])
                sheet1.write(row, (months_col + 3), round((tot_balance/1000000.00), 2), Style.normal_right())
        sheet1.write_merge(row + 1, row + 1, 0, 2, "Total", Style.groupByTitle())
        for i in range(3, (title_end + 1)):
            if i == months_col + 1:
                continue
            start = xlwt.Utils.rowcol_to_cell(start_row, i)
            end = xlwt.Utils.rowcol_to_cell(row, i)
            sheet1.write(row + 1, i, Formula(('sum(' + str(start) + ':' + str(end) + ')')), Style.normal_num_right_2digits_color())
            
        rt = row + 3
        r4 = rt + 1
        #***************Production Report*************
        sf_sql = """
                select x.month_year, x.year, x.mm, x.month, x.w_p, x.product, (sum(x.qty) - sum(x.ub_qty)) as qty from
                ((select
                    concat(to_char(sf.date_done, 'Mon'), '-', to_char(sf.date_done, 'YY')) as month_year,
                    to_char(sf.date_done, 'YYYY') as year,
                    to_char(sf.date_done, 'MM') as mm,
                    to_char(sf.date_done, 'Mon') as month,
                    sf.order_type,
                    pt.name as product,
                    wh.name as warehouse,
                    uom.name as uom,
                    concat(wh.name, '_/_', pt.name, '_/_', uom.name) as w_p,
                    (sum(sf.product_qty)) as qty,
                    0.00 as ub_qty
                from sf_manufacturing_order sf
                    left join product_product pp on (pp.id = sf.product_id)
                    left join product_template pt on (pt.id = pp.product_tmpl_id)
                    left join product_uom uom on (uom.id = sf.uom_id)
                    left join stock_warehouse wh on (wh.id = sf.warehouse_id)
                where wh.id """ + warehouse_sql + """ and sf.date_done >= %s and sf.date_done <= %s and sf.order_type = 'normal'
                group by 
                   to_char(sf.date_done, 'YYYY'),
                   to_char(sf.date_done, 'MM'),
                   to_char(sf.date_done, 'Mon'),
                   concat(to_char(sf.date_done, 'Mon'), '-', to_char(sf.date_done, 'YY')),
                   sf.order_type,
                   pt.name,
                   wh.name,
                   concat(wh.name, '_/_', pt.name),
                   uom.name
                order by
                    sf.order_type,
                    pt.name,
                    to_char(sf.date_done, 'YYYY'),
                    to_char(sf.date_done, 'MM'))
                UNION
                (select
                    concat(to_char(sf.date_done, 'Mon'), '-', to_char(sf.date_done, 'YY')) as month_year,
                    to_char(sf.date_done, 'YYYY') as year,
                    to_char(sf.date_done, 'MM') as mm,
                    to_char(sf.date_done, 'Mon') as month,
                    sf.order_type,
                    pt.name as product,
                    wh.name as warehouse,
                    uom.name as uom,
                    concat(wh.name, '_/_', pt.name, '_/_', uom.name) as w_p,
                    0.00 as qty,
                    (sum(sf.product_qty)) as ub_qty
                from sf_manufacturing_order sf
                left join product_product pp on (pp.id = sf.product_id)
                left join product_template pt on (pt.id = pp.product_tmpl_id)
                left join product_uom uom on (uom.id = sf.uom_id)
                left join stock_warehouse wh on (wh.id = sf.warehouse_id)
                where wh.id """ + warehouse_sql + """ and sf.date_done >= %s and sf.date_done <= %s and sf.order_type = 'unbuild_order'
                group by 
                   to_char(sf.date_done, 'YYYY'),
                   to_char(sf.date_done, 'MM'),
                   to_char(sf.date_done, 'Mon'),
                   concat(to_char(sf.date_done, 'Mon'), '-', to_char(sf.date_done, 'YY')),
                   sf.order_type,
                   pt.name,
                   wh.name,
                   concat(wh.name, '_/_', pt.name),
                   uom.name
                order by
                    sf.order_type,
                    pt.name,
                    to_char(sf.date_done, 'YYYY'),
                    to_char(sf.date_done, 'MM'))) x
                group by
                    x.year,
                    x.mm,
                    x.month,
                    x.month_year,
                    x.w_p,
                    x.product,
                    x.uom
                order by
                    x.product,
                    x.year,
                    x.month
                    """
        
        self.env.cr.execute(sf_sql, (self.date_from, self.date_to, self.date_from, self.date_to,))
        sf_data = self.env.cr.dictfetchall()
        self.env.cr.execute(sf_sql, (date(datetime.strptime(self.date_from, "%Y-%m-%d").year, 1, 1), self.date_to, date(datetime.strptime(self.date_from, "%Y-%m-%d").year, 1, 1), self.date_to,))
        sf_cum_data = self.env.cr.dictfetchall()
        w_product = []
        if self.comparison:
            self.env.cr.execute(sf_sql, (comp_from, comp_to, comp_from, comp_to,))
            comp_sf_data = self.env.cr.dictfetchall()
            self.env.cr.execute(sf_sql, (date(int(self.year), 1, 1), comp_to, date(int(self.year), 1, 1), comp_to,))
            comp_sf_cum = self.env.cr.dictfetchall()
            for each in comp_sf_cum:
                w_product.append(each['w_p'])
        for each in sf_cum_data:
            w_product.append(each['w_p'])
        w_product = list(set(w_product))
        w_product = sorted(w_product, key=unicode.lower)    
        
        r3 = row + 3
        r4 = r3 + 1
        sheet1.row(r3).height = 200 * 2
        sheet1.row(r4).height = 200 * 3
       
        sheet1.write(r4, 0, "S.No", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 1, "Warehouse", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 2, "Product", Style.contentTextBold(r2, 'black', 'white'))
        sheet1.write(r4, 3, "UOM", Style.contentTextBold(r2, 'black', 'white'))
        months_col = 3
        month_index, c_month_index = {}, {}
        for month in range(len(months)):
            months_col += 1
            sheet1.write(r4, months_col, months[month], Style.groupByTitleIb())
            month_index[months[month]] = months_col
            if self.comparison:
                months_col += 1
                sheet1.write(r4, months_col, c_months[month], Style.groupByTitleTan())
                c_month_index[c_months[month]] = months_col
        sheet1.write(r4, (months_col + 2), ("CUM "+ str(datetime.strptime(self.date_from, "%Y-%m-%d").year)), Style.groupByTitleIb())
        title_end = (months_col + 2)
        if self.comparison:
            sheet1.write(r4, (months_col + 3), ("CUM " + self.year ), Style.groupByTitleTan())
            title_end = (months_col + 3)
        sheet1.write_merge(r3, r3, 0, title_end, "Production Report in MT", Style.subTitle()) 
        row = r4
        start_row = r4 + 1
        s_no = 0
        cat_amount, cat_cum_amount, cat_com_amount, comp_cum_amount = 0.00, 0.00, 0.00, 0.00
        for each in w_product:
            s_no += 1
            row += 1
            warehouse = each.split('_/_')[0]
            product = each.split('_/_')[1]
            uom = each.split('_/_')[2]
            sheet1.write(row, 0, s_no, Style.normal_left())
            sheet1.write(row, 1, warehouse, Style.normal_left())
            sheet1.write(row, 2, product, Style.normal_left())
            sheet1.write(row, 3, uom, Style.normal_left())
            for m in month_index:
                cat_amount = sum([x['qty'] if (x['w_p'] and x['w_p'] == each and x['month_year'] == m) else 0.00 for x in sf_data])
                sheet1.write(row, month_index[m], round((cat_amount/1000.00), 3), Style.normal_right())
            cat_cum_amount = sum([x['qty'] if (x['w_p'] and x['w_p'] == each and x['year'] == str(datetime.strptime(self.date_from, "%Y-%m-%d").year)) else 0.00 for x in sf_cum_data])
            sheet1.write(row, (months_col + 2), round((cat_cum_amount/1000.00), 3), Style.normal_right())
            if self.comparison:
                for c in c_month_index:
                    cat_com_amount = sum([x['qty'] if (x['w_p'] and x['w_p'] == each and x['month_year'] == c) else 0.00 for x in comp_sf_data])
                    sheet1.write(row, c_month_index[c], round((cat_com_amount/1000.00), 3), Style.normal_right())
    
                comp_cum_amount = sum([x['qty'] if (x['w_p'] and x['w_p'] == each and x['year'] == self.year) else 0.00 for x in comp_sf_cum])
                sheet1.write(row, (months_col + 3), round((comp_cum_amount/1000.00), 3), Style.normal_right())
        sheet1.write_merge(row + 1, row + 1, 0, 3, "Total", Style.groupByTitle())
        for i in range(4, (title_end + 1)):
            if i == months_col + 1:
                continue
            start = xlwt.Utils.rowcol_to_cell(start_row, i)
            end = xlwt.Utils.rowcol_to_cell(row, i)
            sheet1.write(row + 1, i, Formula(('sum(' + str(start) + ':' + str(end) + ')')), Style.normal_num_right_3digits_color())
        
        
        stream = cStringIO.StringIO()
        wbk.save(stream)
        self.write({'name': report_name + '.xls', 'output': base64.encodestring(stream.getvalue())})
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mis.report.wizard',
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target':'new'
                }
