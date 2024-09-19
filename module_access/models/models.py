# -*- coding: utf-8 -*-

from odoo import models, fields, api

MENU_ITEM_SEPARATOR = "/"

class ModuleAccess(models.Model):
    _inherit = 'res.users'

    module_id = fields.Many2many('ir.module.module',string="Select Modules",domain=[('state', '=', 'installed')])
    menu_ids = fields.Many2many('ir.ui.menu', string="Select Menus",)

    @api.onchange('module_id','menu_ids')
    def _onchange_model_id(self):
        ls = []
        ls1 = []
        ls2 = []
        final_menu_ids = []
        for rec in self.module_id:
            ls.append(rec.shortdesc)
        ls = [element + "/" for element in ls]

        if ls:
            menu_idss111 = self.env['ir.ui.menu'].sudo().search([])
            for recs in menu_idss111:
                ls1.append(recs.complete_name)
            for path in ls1:
                if any(path.startswith(prefix) for prefix in ls):
                    ls2.append(path)
            menu_ids = self.env['ir.ui.menu'].sudo().search([('complete_name','in',ls2)])
            for menu_id in menu_ids:
                final_menu_ids.append(menu_id.id)

            return {
                'domain': {
                    'menu_ids': [('id', 'in', final_menu_ids)]
                }
            }
        else:
            return {
                'domain': {
                    'menu_ids': []
                }
            }

    @api.model
    def hide_buttons(self):
        """Fetch access rights based on the current user."""
        access_right_rec = self.sudo().search_read([],
                                                   ['module_id', 'menu_ids'])
        for dic in access_right_rec:
            menu_ids = dic.get('menu_ids', [])
            menu_names = self.env['ir.ui.menu'].sudo().browse(menu_ids).mapped('name')
            dic['menu_names'] = menu_names


        return access_right_rec

class IrMenu(models.Model):
    _inherit = 'ir.ui.menu'

    complete_name = fields.Char(string='Full Path', compute='_compute_complete_name', recursive=True,store=True)
    parent_id = fields.Many2one('ir.ui.menu', string='Parent Menu', index=True, ondelete="restrict")

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for menu in self:
            menu.complete_name = menu._get_full_name()

    def _get_full_name(self, level=6):
        """ Return the full name of ``self`` (up to a certain level). """
        if level <= 0:
            return '...'
        if self.parent_id:
            return self.parent_id._get_full_name(level - 1) + MENU_ITEM_SEPARATOR + (self.name or "")
        else:
            return self.name
