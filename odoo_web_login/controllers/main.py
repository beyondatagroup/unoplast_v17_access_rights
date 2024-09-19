# -*- encoding: utf-8 -*-
##############################################################################
#
#    Samples module for Odoo Web Login Screen
#    Copyright (C) 2017- XUBI.ME (http://www.xubi.me)
#    @author binhnguyenxuan (https://www.linkedin.com/in/binhnguyenxuan)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
##############################################################################

import ast

# from odoo.addons.portal.controllers.web import Home
from odoo.addons.web.controllers.home import (
    ensure_db,
    Home,
    SIGN_UP_REQUEST_PARAMS,
)

import pytz
import datetime
import logging

import odoo
import odoo.modules.registry
from odoo import http
from odoo.http import request
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


# ----------------------------------------------------------
# Odoo Web web Controllers
# ----------------------------------------------------------
class LoginHome(Home):

    # @http.route('/web/login', type='http', auth="none")
    # def web_login(self, *args, **kw):
    #     # res =super(LoginHome, self).web_login(redirect, **kw)
    #     ensure_db()
    #     response = super().web_login(*args, **kw)
    #     print("\n\n\nheloooooooooooooooooooooooo")
    #     param_obj = request.env['ir.config_parameter'].sudo()
    #     request.params['disable_footer'] = ast.literal_eval(param_obj.get_param('login_form_disable_footer')) or False
    #     request.params['disable_database_manager'] = ast.literal_eval(
    #         param_obj.get_param('login_form_disable_database_manager')) or False

    #     change_background = ast.literal_eval(param_obj.get_param('login_form_change_background_by_hour')) or False
    #     values = {k: v for k, v in request.params.items() if k in SIGN_UP_REQUEST_PARAMS}
    #     if change_background:
    #         config_login_timezone = param_obj.get_param('login_form_change_background_timezone')
    #         tz = config_login_timezone and pytz.timezone(config_login_timezone) or pytz.utc
    #         current_hour = datetime.datetime.now(tz=tz).hour or 10

    #         if (current_hour >= 0 and current_hour < 3) or (current_hour >= 18 and current_hour < 24):  # Night
    #             values['background_src'] = param_obj.get_param('login_form_background_night') or ''
    #             print("0==3",values['background_src'])
    #         elif current_hour >= 3 and current_hour < 7:  # Dawn
    #             values['background_src'] = param_obj.get_param('login_form_background_dawn') or ''
    #             print("3==7",values['background_src'])
    #         elif current_hour >= 7 and current_hour < 16:  # Day
    #             values['background_src'] = param_obj.get_param('login_form_background_day') or ''
    #             print("7==16",values['background_src'])
    #         else:  # Dusk
    #             values['background_src'] = param_obj.get_param('login_form_background_dusk') or ''
    #             print("else",values['background_src'])
    #     else:
    #         values['background_src'] = param_obj.get_param('login_form_background_default') or ''
    #     return response
    

    @http.route("/web/login", type="http", auth="none")
    def web_login(self, redirect=None, **kw):
        ensure_db()
        request.params["login_success"] = False
        if request.httprequest.method == "GET" and redirect and request.session.uid:
            return request.redirect(redirect)

        # simulate hybrid auth=user/auth=public, despite using auth=none to be able
        # to redirect users when no db is selected - cfr ensure_db()
        if request.env.uid is None:
            if request.session.uid is None:
                request.env["ir.http"]._auth_method_public()
            else:
                request.update_env(user=request.session.uid)

        values = {
            k: v for k, v in request.params.items() if k in SIGN_UP_REQUEST_PARAMS
        }
        param_obj = request.env["ir.config_parameter"].sudo()
        emp_obj = request.env['hr.employee'].sudo()
        # request.params["disable_footer"] = (
        #     ast.literal_eval(param_obj.get_param("login_form_disable_footer")) or False
        # )
        # request.params["disable_database_manager"] = (
        #     ast.literal_eval(param_obj.get_param("login_form_disable_database_manager"))
        #     or False
        # )

        change_background = (
            ast.literal_eval(
                param_obj.get_param("login_form_change_background_by_hour")
            )
            or False
        )
        
        birthday_wishes = emp_obj.get_birthday()
        values['birthday_message'] = _(birthday_wishes)
        if birthday_wishes:
            values["background_src"] = param_obj.get_param('login_form_background_birthday') or ''
        else:
            if change_background:
                config_login_timezone = param_obj.get_param(
                    "login_form_change_background_timezone"
                )
                tz = (
                    config_login_timezone
                    and pytz.timezone(config_login_timezone)
                    or pytz.utc
                )
                current_hour = datetime.datetime.now(tz=tz).hour or 10

                if (current_hour >= 0 and current_hour < 3) or (
                    current_hour >= 18 and current_hour < 24
                ):  # Night
                    values["background_src"] = (
                        param_obj.get_param("login_form_background_night") or ""
                    )
                    print("0==3", values["background_src"])
                elif current_hour >= 3 and current_hour < 7:  # Dawn
                    values["background_src"] = (
                        param_obj.get_param("login_form_background_dawn") or ""
                    )
                    print("3==7", values["background_src"])
                elif current_hour >= 7 and current_hour < 16:  # Day
                    values["background_src"] = (
                        param_obj.get_param("login_form_background_day") or ""
                    )
                    print("7==16", values["background_src"])
                else:  # Dusk
                    values["background_src"] = (
                        param_obj.get_param("login_form_background_dusk") or ""
                    )
                    print("else", values["background_src"])
            else:
                values["background_src"] = (
                    param_obj.get_param("login_form_background_default") or ""
                )
        try:
            values["databases"] = http.db_list()
        except odoo.exceptions.AccessDenied:
            values["databases"] = None

        if request.httprequest.method == "POST":
            try:
                uid = request.session.authenticate(
                    request.db, request.params["login"], request.params["password"]
                )
                request.params["login_success"] = True
                return request.redirect(self._login_redirect(uid, redirect=redirect))
            except odoo.exceptions.AccessDenied as e:
                if e.args == odoo.exceptions.AccessDenied().args:
                    values["error"] = _("Wrong login/password")
                else:
                    values["error"] = e.args[0]
        else:
            if "error" in request.params and request.params.get("error") == "access":
                values["error"] = _(
                    "Only employees can access this database. Please contact the administrator."
                )

        if "login" not in values and request.session.get("auth_login"):
            values["login"] = request.session.get("auth_login")

        if not odoo.tools.config["list_db"]:
            values["disable_database_manager"] = True

        response = request.render("web.login", values)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
        return response
