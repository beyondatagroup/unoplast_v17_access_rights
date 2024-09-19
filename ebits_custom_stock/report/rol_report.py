# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models
import odoo.addons.decimal_precision as dp

from odoo.tools import float_is_zero, float_compare
from odoo.tools.misc import formatLang

class RolReport(models.Model):
    _name = "rol.report"
    _description = "Reordering Rules Report"
    _auto = False

    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    categ_id = fields.Many2one('product.category', 'Product Category', readonly=True)
    uom_id = fields.Many2one('uom.uom', 'UOM', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', readonly=True)
    location_id = fields.Many2one('stock.location', 'Location', readonly=True)
    min_qty = fields.Float('Min Qty ***(A)***', readonly=True, digits=('Product Unit of Measure'))
    max_qty = fields.Float('Max Qty ***(B)***', readonly=True, digits=('Product Unit of Measure'))
    stock_location_qty = fields.Float('Stock Location Qty ***(C)***', readonly=True, digits=('Product Unit of Measure'))
    po_qty = fields.Float('Unapproved PO Qty ***(D)***', readonly=True, digits=('Product Unit of Measure'))
    grn_qty = fields.Float ('Pending GRN Qty ***(E)***', readonly=True, digits=('Product Unit of Measure'))
    quality_location_qty = fields.Float('Quality Location Qty ***(F)***', readonly=True, digits=('Product Unit of Measure'))
    mo_qty = fields.Float('Pending MO Qty ***(G)***', readonly=True, digits=('Product Unit of Measure'))
    st_request_qty = fields.Float('Stock Transfer Request Qty (Waiting for Approval) ***(H)***', readonly=True, digits=('Product Unit of Measure'))
    st_issue_qty = fields.Float('Pending Issue Qty from other Warehouse ***(I)***', readonly=True, digits=('Product Unit of Measure'))
    st_receipt_qty = fields.Float('Stock Transfer Pending Receipt Qty ***(J)***', readonly=True, digits=('Product Unit of Measure'))
    do_qty = fields.Float('Pending DO Qty ***(K)***', readonly=True, digits=('Product Unit of Measure'))
    st_out_issue_qty = fields.Float('Pending Issue Qty to other Warehouse ***(L)***', readonly=True, digits=('Product Unit of Measure'))
    total_qty = fields.Float('Quantity to be Ordered ***(B-[sum(C to J) - sum(K to L)])***', readonly=True, digits=('Product Unit of Measure'))

    
    def _select(self):
        select_str = """ select x.id,
	                         x.product_id,
	                         x.categ_id,
	                         x.uom_id,
	                         x.warehouse_id,
	                         x.location_id,
	                         x.min_qty,
	                         x.max_qty,
	                         x.stock_location_qty,
	                         x.po_qty,
	                         x.grn_qty,
	                         x.mo_qty,
	                         x.st_request_qty,
	                         x.st_issue_qty,
	                         x.st_receipt_qty,
	                         x.do_qty,
	                         x.st_out_issue_qty,
                             (x.max_qty - abs((x.stock_location_qty + x.po_qty + x.grn_qty + x.st_request_qty + st_issue_qty + st_receipt_qty + x.mo_qty) - (x.do_qty + x.st_out_issue_qty))) as total_qty
                        from (select 
	                            row_number() over (order by min(pp.id)) as id,
	                            pp.default_code as product_code,
	                            pp.id as product_id,
	                            pc.id as categ_id,
	                            pu.id as uom_id,
	                            sw.id as warehouse_id,
	                            sl.id as location_id,
	                            (case when sw_op.product_min_qty is not null then sw_op.product_min_qty else 0.00 end) as min_qty,
	                            (case when sw_op.product_max_qty  is not null then sw_op.product_max_qty else 0.00 end) as max_qty,
	                            (select (case when sum(sq.qty) is not null then sum(sq.qty) else 0.00 end) from stock_quant sq
		                            where sq.product_id = pp.id and sq.location_id = sl.id ) as stock_location_qty,
	                            (select (case when sum(pol.product_qty) is not null then sum(pol.product_qty) else 0.00 end) from purchase_order_line pol
			                            left join purchase_order po on(po.id = pol.order_id)
		                            where pol.product_id = pp.id and po.warehouse_id = sw.id and po.state not in  ('purchase', 'done', 'cancel')) as po_qty,
	                            (select	(case when sum(sm.product_uom_qty) is not null then sum(sm.product_uom_qty) else 0.00 end) from stock_move sm
			                            left join stock_picking sp on (sp.id = sm.picking_id)
			                            left join stock_picking_type spt on (spt.id = sp.picking_type_id)
		                            where sm.product_id = pp.id and sm.warehouse_id = sw.id and sp.state not in ('cancel','done') and spt.code = 'incoming') as grn_qty,
                                (select (case when sum(istl.qty) is not null then sum(istl.qty) else 0.00 end) 
                                        from internal_stock_transfer_request_lines istl
                                         where istl.state = 'waiting'
                                                and istl.product_id = pp.id
                                                and istl.requesting_warehouse_id = sw.id)as st_request_qty,   
                                
                                (select (case when sum((case when st_iss.approved_qty is not null then st_iss.approved_qty else 0.00 end) - 
	                                    (case when st_iss.issued_qty is not null then st_iss.issued_qty else 0.00 end)) is not null then sum((case when st_iss.approved_qty is not null then st_iss.approved_qty else 0.00 end) - 
	                                    (case when st_iss.issued_qty is not null then st_iss.issued_qty else 0.00 end)) else 0.00 end)
		                               from internal_stock_transfer_issue_line st_iss
		                                     left join internal_stock_transfer_issue ist on (ist.id = st_iss.issue_id)  
		                               where ist.state in ('draft', 'partial')
		                                     and st_iss.product_id = pp.id
		                                     and st_iss.issuing_warehouse_id = sw.id
		                               ) as st_issue_qty,  

                               (select (case when sum((case when st_rec.issued_qty is not null then st_rec.issued_qty else 0.00 end) - 
	                                   (case when st_rec.received_qty is not null then st_rec.received_qty else 0.00 end)) is not null then sum((case when st_rec.issued_qty is not null then st_rec.issued_qty else 0.00 end) - 
	                                   (case when st_rec.received_qty is not null then st_rec.received_qty else 0.00 end)) else 0.00 end)
		                               from internal_stock_transfer_receipt_line st_rec
			                                left join internal_stock_transfer_receipt isr on (isr.id = st_rec.receipt_id)  
		                               where isr.state in ('draft', 'partial')
			                                and st_rec.product_id = pp.id
			                                and st_rec.receiving_warehouse_id = sw.id
		                              ) as st_receipt_qty,
		                            
	                            
                                (select (case when sum(smo.product_uom_qty) is not null then sum(smo.product_uom_qty) else 0.00 end) from stock_move smo
	                                    left join mrp_production mrp on (mrp.id = smo.production_id)
                                    where mrp.product_id = pp.id and mrp.warehouse_id = sw.id and smo.state not in ('cancel','done')) as mo_qty,
                                    (select	(case when sum(sm.product_uom_qty) is not null then sum(sm.product_uom_qty) else 0.00 end) from stock_move sm
			                            left join stock_picking sp on (sp.id = sm.picking_id)
			                            left join stock_picking_type spt on (spt.id = sp.picking_type_id)
		                            where sm.product_id = pp.id and sm.warehouse_id = sw.id and sp.state not in ('cancel','done') and spt.code = 'outgoing') as do_qty, 
		                            (select (case when sum((case when st_iss.approved_qty is not null then st_iss.approved_qty else 0.00 end) - 
	                                    (case when st_iss.issued_qty is not null then st_iss.issued_qty else 0.00 end)) is not null then sum((case when st_iss.approved_qty is not null then st_iss.approved_qty else 0.00 end) - 
	                                    (case when st_iss.issued_qty is not null then st_iss.issued_qty else 0.00 end)) else 0.00 end)
		                               from internal_stock_transfer_issue_line st_iss
		                                     left join internal_stock_transfer_issue ist on (ist.id = st_iss.issue_id)  
		                               where ist.state in ('draft', 'partial')
		                                     and st_iss.product_id = pp.id
		                                     and st_iss.issuing_warehouse_id = sw.id
		                               ) as st_out_issue_qty  
                            from stock_warehouse_orderpoint sw_op 
	                            left join product_product pp on (pp.id =sw_op.product_id) 
	                            left join product_template pt on (pt.id = pp.product_tmpl_id)
	                            left join product_category pc on (pc.id = pt.categ_id)
	                            left join uom_uom pu on (pu.id = pt.uom_id)
	                            left join stock_warehouse sw on (sw.id = sw_op.warehouse_id)
	                            left join stock_location sl on (sl.id = sw_op.location_id)
                            where pp.active = True and pt.type = 'product' 
                            group by 
	                            pp.id,
	                            pc.id,
	                            pu.id,
	                            sw.id,
	                            sl.id,
	                            sw_op.product_min_qty,
	                            sw_op.product_max_qty) x 
                                where (x.min_qty > (x.stock_location_qty + x.grn_qty ))"""                        
        return select_str
        

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (
            %s
            )""" % (self._table, self._select()))
            
 
