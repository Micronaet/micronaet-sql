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

class micronaet_accounting(orm.Model):
    ''' Object for keep function with the query
        Record are only table with last date of access
    '''
    _inherit = "micronaet.accounting"
    
    # -------------------------------------------------------------------------
    # Add query to import BOM
    # -------------------------------------------------------------------------
    def get_bom_line(self, cr, uid, context=None):
        ''' Access to anagrafic table bom
            Table: TA_DIBA_AUT
        '''
        table = "ta_diba_aut"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)
        try:#                        ID       Description
            cursor.execute("""SELECT * FROM %s;""" % table)
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False 

class MrpBom(orm.Model):
    ''' Add extra field to bom for importation
    '''
    _inherit = 'mrp.bom'
    
    _columns = {
        'sql_import': fields.boolean('SQL import'),
        }

    _defaults = {
        'sql_import': lambda *a: False,
        }

    # -------------------------------------------------------------------------
    #                                 Utility
    # -------------------------------------------------------------------------
    def get_create_bom_from_product_id(self, cr, uid, default_code, 
            context=None):
        ''' Return bom_id read for product code passed
            create if not present
        '''        
        product_pool = self.pool.get('product.product')
        product_ids = product_pool.search(cr, uid, [
            ('default_code', '=', default_code)], context=context)
            
        if not product_ids:
            _logger.error(
                'BOM product not found: %s, reimport list' % default_code)
            return False
            
        if not product_ids: # warning
            _logger.warning(
                'BOM product found more than one: %s, reimport list' % \
                    default_code)
        
        bom_ids = self.search(cr, uid, [
            ('sql_import', '=', True),
            ('product_id', '=', product_ids[0]), # XXX no template!
            ], context=context)
            
        if bom_ids:
            return bom_ids[0]
            
        product_proxy = product_pool.browse(
            cr, uid, product_ids, context=context)[0]    
        return self.create(cr, uid, {        
            'product_tmpl_id': product_proxy.product_tmpl_id.id, 
            'product_id': product_ids[0], 
            'code': product_proxy.default_code, 
            'type': 'normal',
            'product_qty': 1.0,
            'product_uom': product_proxy.uom_id.uom_id,
            'note': _('My SQL import generation'),
            }, context=context)    

    # -------------------------------------------------------------------------
    #                             Scheduled action
    # -------------------------------------------------------------------------
    def schedule_bom_import(self, cr, uid, verbose=100, capital=True, 
            context=None):
        ''' Import partner from external MySQL DB        
            verbose_log_count: number of record for verbose log (0 = nothing)
            capital: if table has capital letters (usually with mysql in win)
            context: dict for extra parameter            
        '''        
        _logger.info('''
            Start import BOM from SQL, setup:
            Verbose: %s - Capital name: %s''' % (
                verbose_log_count, capital))
        sql_pool = self.pool.get('micronaet.accounting')
        bom_pool = self.pool.get('mrp.bom.line')

     
        cursor = sql_pool.get_bom_line(cr, uid, context=context) 
        if not cursor:
            _logger.error("Unable to connect, no BOM!")
            return False

        _logger.info('Start import BOM database')
        i = 0
        bom_parent = {} # Database for convert code in bom         
        bom_lines = {} # Database of lines
        
        # Load line database (for deletion)
        line_ids = line_pool.search(cr, uid, [ # TODO
            ('sql_import', '=', True)], context=context)            
            
        # Create list for search element    
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            bom_lines[(line.bom_id.id, line.product_id)] = line.id
        
        for record in cursor:
            i += 1
            if verbose and i % verbose == 0:
                _logger.info('%s record imported / updated!' % i)
                        
                try:
                    default_code = record['CKY_ART_DBA']
                    #_NGB_RIGA']
                    component_code = record['CKY_ART_COMP']                    
                    product_qty = record['CDS_FORMUL_QTA'] or 0.0 # TODO float
                    #CSG_UNIMIS
                    
                    if default_code not in bom_parent:
                        bom_id = self.get_create_bom_from_product_id(
                            cr, uid, default_code, context=context)                        
                        bom_parent[default_code] = self.browse(
                            cr, uid, bom_id, context=context)

                    bom_proxy = bom_parent[default_code]                    
                    product_id =                            
                    
                    product_proxy
                    line_data = {
                        'product_id': product_proxy.id,
                        'product_qty': record['CDS_FORMUL_QTA'] or 0.0,
                        'product_uom': product_proxy.uom_id.id,
                        
                        'name': record['CDS_CNT'],
                        }

                    # if not in convert dict try to search
                    if not data['parent_id']:
                        parent_ids = self.search(cr, uid, ['|',
                            ('sql_customer_code', 
                                '=', parent_code),
                            ('sql_supplier_code', 
                                '=', parent_code),
                            ], context=context)
                    if parent_ids:
                        data['parent_id'] = parent_ids[0]

                    # Extra domain for search also in cust. / suppl.
                    if dest_merged:                              
                        # Remove if import error in cust. / suppl.
                        data['sql_customer_code'] = False
                        data['sql_supplier_code'] = False
                        # Search all for correct  startup error of imp.
                        domain = [ 
                            '|', '|',
                            ('sql_customer_code', '=', ref),
                            ('sql_supplier_code', '=', ref),
                            ('sql_destination_code', '=', ref),
                            ]
                    else:
                        # TODO when are we here?
                        #_logger.error(
                        #    'Destination: %s without parent code' % ref)
                        continue


                    except:
                        _logger.error(
                            'Error importing partner [%s], jumped: %s' % (
                                ref, sys.exc_info()))
                                            
                _logger.info('All BOM is updated!')
        except:
            _logger.error('Error generic import BOM: %s' % (
                sys.exc_info(), ))
            return False
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
