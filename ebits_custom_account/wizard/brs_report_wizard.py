# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import time
from odoo import api, fields, models, _
from odoo.tools.translate import _
from excel_styles import ExcelStyles
import xlwt
import cStringIO
import base64
import xlrd
import parser
from odoo.exceptions import UserError, AccessError, ValidationError
from lxml import etree

class BankReconciliationReportWizard(models.TransientModel):
    _name = 'bank.reconciliation.report.wizard'
    _description = 'Bank Reconciliation Report Wizard'
    
    name = fields.Char(string='File Name', readonly=True)
    output = fields.Binary(string='format', readonly=True)
