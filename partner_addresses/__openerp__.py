# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2013 Agile Business Group sagl (<http://www.agilebg.com>)
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
##############################################################################

{
    'name': 'Addresses',
    'version': '1.0',
    'category': 'Tools',
    'description': """
This module shows the address type field 
(otherwise shown by sale_stock) and improve default addresses management.
""",
    'author': 'Agile Business Group',
    'website': 'http://www.agilebg.com',
    'summary': 'Partner addresses',
    'depends': [],
    'data': [
        'partner_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}