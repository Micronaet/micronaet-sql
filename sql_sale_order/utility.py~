# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import openerp.netsvc as netsvc
import logging
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
#                           Utility function
# -----------------------------------------------------------------------------
# View function:
def no_establishment_group(self, cr, uid, context=None):
    ''' Test if current user belongs to group_production_production group    
    '''
    group_pool = self.pool.get('res.groups')
    group_ids = group_pool.search(
        cr, uid, [
            ('name','=','Production visibility production')], 
        context=context)
    group_proxy = group_pool.read(
        cr, uid, group_ids, ('users',), context=context)[0]
    return uid in group_proxy['users']

# Conversion function:
def prepare(valore):
    valore=valore.decode('cp1252')
    valore=valore.encode('utf-8')
    return valore.strip()
 
def log_error(self, cr, uid, operation, error, context=None):
    """ Log error in OpenERP log and add in log.activity object the same value
    """
    self.pool.get('log.activity').log_error(cr, uid, operation, error)
    _logger.error(error) # global variable
    return False
 
def prepare_date(valore):
    valore=valore.strip()
    if len(valore)==8:
       if valore: # TODO test correct date format
          return valore[:4] + "-" + valore[4:6] + "-" + valore[6:8]
    return False
 
def prepare_float(valore):
    valore=valore.strip()
    if valore: # TODO test correct date format
       return float(valore.replace(",","."))
    else:
       return 0.0   # for empty values
 
# ID function:
def get_partner_id(self, cr, uid, ref, context=None):
    ''' Get OpenERP ID for res.partner with passed accounting reference
    '''
    partner_id=self.pool.get("res.partner").search(cr, uid, ["|","|",('mexal_c','=',ref),('mexal_d','=',ref),('mexal_s','=',ref)], context=context)
    return partner_id[0] if partner_id else False
 
def browse_partner_id(self, cr, uid, item_id, context=None):
    ''' Return browse obj for partner id
    '''
    browse_ids = self.pool.get('res.partner').browse(cr, uid, [item_id], context=context)
    return browse_ids[0] if browse_ids else False
 
def browse_partner_ref(self, cr, uid, ref, context=None):
    ''' Get OpenERP ID for res.partner with passed accounting reference
    '''
    partner_id = self.pool.get("res.partner").search(cr, uid, ["|","|",('mexal_c','=',ref),('mexal_d','=',ref),('mexal_s','=',ref)], context=context)
    return self.pool.get('res.partner').browse(cr, uid, partner_id[0], context=context) if partner_id else False
 
def get_product_id(self, cr, uid, ref, context=None):
    ''' Get OpenERP ID for product.product with passed accounting reference
    '''
    item_id = self.pool.get('product.product').search(cr, uid, [('default_code', '=', ref)], context=context)
    return item_id[0] if item_id else False
 
def browse_product_id(self, cr, uid, item_id, context=None):
    ''' Return browse obj for product id
    '''
    browse_ids = self.pool.get('product.product').browse(cr, uid, [item_id], context=context)
    return browse_ids[0] if browse_ids else False
 
def browse_product_ref(self, cr, uid, ref, context=None):
    ''' Return browse obj for product ref
        Create a minimal product with code ref for not jump oc line creation
        (after normal sync of product will update all the fields not present
    '''
    item_id = self.pool.get('product.product').search(cr, uid, [('default_code', '=', ref)], context=context)
    if not item_id:
       try:
           uom_id = self.pool.get('product.uom').search(cr, uid, [('name', '=', 'kg')],context=context)
           uom_id = uom_id[0] if uom_id else False
           item_id=self.pool.get('product.product').create(cr,uid,{
               'name': ref,
               'name_template': ref,
               'mexal_id': ref,
               'default_code': ref,
               'sale_ok': True,
               'type': 'consu',
               'standard_price': 0.0,
               'list_price': 0.0,
               'description_sale': ref, # preserve original name (not code + name)
               'description': ref,
               'uos_id': uom_id,
               'uom_id': uom_id,
               'uom_po_id': uom_id,
               'supply_method': 'produce',
           }, context=context)
       except:
           return False # error creating product
    else:
        item_id=item_id[0]  # first
    return self.pool.get('product.product').browse(cr, uid, item_id, context=context)
 
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
