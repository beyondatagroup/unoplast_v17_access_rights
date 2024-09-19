# -*- coding: utf-8 -*-
###############################################################################
#
#    BeyonData Solutions Private Limited
#
#    Copyright (C) 2024-TODAY BeyonData Solutions Private Limited
#    Author: Tejas Apani
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#
###############################################################################

{
    'name': "Menu Access",
    'summary': """
        Use For Menu Access to Hide or Show User Wise""",
    'author': "BeyonData Solutions Private Limited",
    'website': "https://erp.beyondatagroup.com/",
    'category': 'Access Rights',
    'license': 'LGPL-3',
    'version': '17.0',
    'depends': ['base'],
    'data': [
        'views/views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'module_access//static/src/**/*',
        ]
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
