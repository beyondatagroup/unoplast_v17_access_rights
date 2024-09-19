# -*- encoding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2004-2014 OpenERP S.A. (<http://odoo.com>).
#
##############################################################################
import time

from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError
from datetime import datetime
import pytz

class AutoSchedulerRequestWizard(models.TransientModel):
    _name = 'auto.scheduler.request.wizard'
    _description = 'Inter transfer Request scheduler Wizard'
    
    # @api.multi
    def action_run(self):
        scheduler_obj = self.env['auto.intertransfer.request']
        scheduler_obj.run_itr_material_request_scheduler()
        return True
        
# AutoSchedulerRequestWizard()
        
