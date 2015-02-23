# -*- coding: utf-8 -*-
###############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class product_product(orm.Model):
    ''' Extend product.product
    '''    
    _name = 'product.product'
    _inherit = 'product.product'
    
    _columns = {
        'sql_import': fields.boolean('SQL import', required=False),
        'accounting_structured': fields.char('Accounting structured', size=2),
        'statistic_category': fields.char(
            'Statistic category', size=10, 
            required=False, readonly=False),
    }
    
    _defaults = {
        'sql_import': lambda *a: False,
        'statistic_category': lambda *x: False,
    }

    def get_product_from_sql_code(self, cr, uid, code, context = None):
        ''' Return product_id read from the import code passed
            (all product also pre-deleted
        '''
        product_ids = self.search(cr, uid, [('default_code', '=', code), ])

        if product_ids:
            return product_ids[0]
        return False

    def get_is_to_import_product(self, cr, uid, item_id, context = None):
        ''' Return if the product is to import (MM) from ID
        '''
        product_id = self.search(cr, uid, [('id', '=', item_id),])
        if product_id:
            product_browse = self.search(cr, uid, product_id, context=context)
            return not product_browse[0].not_analysis

        return True #False # Jump line with product not found

    # -------------------------------------------------------------------------
    #                                  Scheduled action
    # -------------------------------------------------------------------------
    def schedule_sql_product_import(self, cr, uid, verbose_log_count=100, 
            write_date_from=False, write_date_to=False, create_date_from=False,
            create_date_to=False, context=None):
        ''' Import product from external SQL DB
        '''
        product_proxy = self.pool.get('product.product')
        accounting_pool = self.pool.get('micronaet.accounting')
        # Get route for manufacture:
        route_pool = self.pool.get('stock.location.route')
        route_ids = route_pool.search(cr, uid, [('name', '=', 'Manufacture')], context=context)
        to_manufacture = (1, ) # TODO parametrize
        if route_ids:
            manufacture = [(6, 0, [route_ids[0]])]
        else:
            manufacture = False    
        
        try:
            cursor = accounting_pool.get_product( 
                cr, uid, active = False, write_date_from=write_date_from,
                write_date_to=write_date_to, create_date_from=create_date_from,
                create_date_to=create_date_to, context=context) 
            if not cursor:
                _logger.error(
                    "Unable to connect no importation of package list for product!")
                return False

            i = 0
            for record in cursor:
                try:
                    i += 1
                    if verbose_log_count and i % verbose_log_count == 0:
                        _logger.info('Import %s: record import/update!' % i)                             

                    data = {
                        # TODO IFL_ART_DBP o DBV for supply_method='produce'
                        'name': record['CDS_ART'] + (
                            record['CDS_AGGIUN_ART'] or ''),
                        'default_code': record['CKY_ART'],
                        'sql_import': True,
                        'active': True,
                        'accounting_structured': record['NKY_STRUTT_ART'],
                        'statistic_category': "%s%s" % (
                            record['CKY_CAT_STAT_ART'] or '', 
                            "%02d" % int(
                                record['NKY_CAT_STAT_ART'] or '0') if record[
                                    'CKY_CAT_STAT_ART'] else '',
                        ),
                    }
                    # Test if is to manufacture
                    if manufacture and record['NKY_STRUTT_ART'] in to_manufacture:
                        data['route_ids'] = manufacture
                        
                    if accounting_pool.is_active(record):
                        data['state'] = 'sellable'
                    else:
                        data['state'] = 'obsolete'
                        
                    product_ids = product_proxy.search(cr, uid, [
                        ('default_code', '=', record['CKY_ART'])])
                    if product_ids:
                        product_id = product_ids[0]
                        product_proxy.write(cr, uid, product_id, data, 
                            context=context)
                    else:
                        product_id = product_proxy.create(cr, uid, data, 
                            context=context)
                except:
                    _logger.error('Error import product [%s], jumped: %s' % (
                        record['CDS_ART'], sys.exc_info(), ))
                        
            _logger.info('All product is updated!')
        except:
            _logger.error('Error generic import product: %s' % (
                sys.exc_info(), ))
            return False
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
