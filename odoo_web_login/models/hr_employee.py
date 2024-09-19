# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import random
import werkzeug.urls

from collections import defaultdict
from datetime import datetime, timedelta

from odoo import api, fields, models, _


class Employee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def get_birthday(self):
        birthday_wishes = ""
        today = datetime.now()
        print("\n\n\n===today===",today)
        today_month_day = '%-' + today.strftime('%m') + '-' + today.strftime('%d')
        print("\n\n\n===today_month_day===",today_month_day)
        ids = self.search([('birthday', 'like', today_month_day)])
        if not ids:
            return birthday_wishes
        for each_id in ids:
            if birthday_wishes:
                birthday_wishes += ', \n'
            birthday_wishes += "Happy Birthday " + each_id.name + " !!!."
        if birthday_wishes:
            company = self.env.user.company_id.name
            birthday_wishes = company + ' Wishes You !!! ' + '\n' + birthday_wishes
            print("\n\n\n===birthday_wishes===",birthday_wishes)
        return birthday_wishes
    