# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class BDPosOrder(models.Model):
    _inherit = ["pos.order"]

    