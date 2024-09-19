# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from datetime import date


class IrSequenceSubSequenceWizard(models.TransientModel):
    _name = 'ir.sequence.sub.sequence.wizard'
    _description = 'Ir Sequence Sub Sequence Wizard'
    
    sequence_id = fields.Many2one('ir.sequence', string="Sequence", required=True)
    year = fields.Selection('Year',default=datetime.now().year)
    
    def action_create_sub_sequence(self):
        # active_id = self._context.get('active_id')
        # seq_obj = self.env['ir.sequence']
        # seq_line_obj = self.env['ir.sequence.date_range']
        # if self.year:
        #     seq_browse = self.sequence_id
        #     for month in range(1, 13):
        #         create_range = True
        #         start_date = date(self.year, month, 1)
        #         #end_date = date(self.year, month, 1).replace(day=28) + timedelta(days=4)
        #         end_date = date(self.year, month, 1)
        #         end_date = end_date - timedelta(days=end_date.day)
        #         for each in seq_browse.date_range_ids:
        #             seq_line_search = seq_line_obj.search([('date_from', '=', start_date),('date_to', '=', end_date),('sequence_id', '=', seq_browse.id)])
        #             if seq_line_search:
        #                 create_range = False
        #         if create_range:
        #             seq_line_obj.create({
        #                 'sequence_id': active_id,
        #                 'date_from': start_date,
        #                 'date_to': end_date,
        #                 'number_next_actual': 1
        #             })
        return True
