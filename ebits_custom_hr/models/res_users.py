# -*- coding: utf-8 -*-
# EBITS TechCon Module. See LICENSE file for full copyright and licensing details.

import re
import time
import math
import pytz
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
from odoo.modules.module import get_module_resource
import odoo.addons.decimal_precision as dp

class BdUser(models.Model):
    _inherit = "res.users"

    def web_save(self, vals, specification):

        if "create_employee_id" in vals:
            emp_browse = self.env["hr.employee"].browse(vals["create_employee_id"])

            if not self.env.registry.in_test_mode():
                if not emp_browse.production_unit_id:
                    raise ValidationError(_('Employee unit or employee code is empty return and fill'))
                
                if not emp_browse.employee_code:
                    raise ValidationError(_('Employee unit or employee code is empty return and fill'))

        res = super(BdUser, self).web_save(vals, specification)

        return res
        

