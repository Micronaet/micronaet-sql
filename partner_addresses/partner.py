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

import re
from openerp.osv import orm, fields
from openerp.tools.translate import _

class res_partner(orm.Model):

	_inherit = 'res.partner'

	_columns = {
		'is_address': fields.boolean('Is an Address'),
		'child_ids': fields.one2many('res.partner', 'parent_id', 'Contacts', domain=[('is_address','=',False)]),
		'address_ids': fields.one2many('res.partner', 'parent_id', 'Addresses', domain=[('is_address','=',True)]),
	}

	def name_get(self, cr, uid, ids, context=None):
		if context is None:
		    context = {}
		if isinstance(ids, (int, long)):
		    ids = [ids]
		res = []
		for record in self.browse(cr, uid, ids, context=context):
		    name = record.name
		    if record.parent_id:
		        name =  "%s (%s)" % (name, record.parent_id.name)
		    if context.get('show_address'):
		        name = name + "\n" + self._display_address(cr, uid, record, without_company=True, context=context)
		        name = name.replace('\n\n','\n')
		        name = name.replace('\n\n','\n')
		    if context.get('show_email') and record.email:
		        name = "%s <%s>" % (name, record.email)
		    if record.is_address:
		    	address = self._display_address(cr, uid, record, without_company=True, context=context)
		    	address = address.replace('\n',' ')
		    	address = re.sub(r'\s+', ' ', address)
		    	name = "%s, %s (%s)" % (record.parent_id.name, address, record.type)
		    res.append((record.id, name))
		return res

	def address_get_obj(self, cr, uid, ids, adr_type=None, context=None):
		if adr_type is None:
			adr_type = 'default'
		result = {}
		# retrieve addresses from the partner itself and its children
		res = []
		# need to fix the ids ,It get False value in list like ids[False]
		if ids and ids[0]!=False:
			for p in self.browse(cr, uid, ids):
				res.append((p.type, p))
				res.extend((c.type, c) for c in p.address_ids)
		address_dict = dict(reversed(res))
		# get the id of the (first) default address if there is one,
		# otherwise get the id of the first address in the list
		default_address = False
		if res:
			default_address = address_dict.get('default', res[0][1])
		result = address_dict.get(adr_type, default_address)
		return result
