# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) 
#    
#    Italian OpenERP Community (<http://www.openerp-italia.com>)
#
#############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import sys
import os
from openerp.osv import osv, fields
from datetime import datetime, timedelta
import logging


_logger = logging.getLogger(__name__)


class micronaet_accounting(osv.osv):
    ''' Extend with method
    '''
    _inherit = 'micronaet.accounting'

    # ---------------------
    #  CODE PRODUCT PARTIC:
    # ---------------------
    def get_product_first_supplier(self, cr, uid, year=False, context=None):
        ''' Access to anagrafic table of partic productpartner
            Table: tz_prz_cli_art
        '''
        table = 'ar_anagrafiche'
        if self.pool.get('res.company').table_capital_name(cr, uid, 
                context=context):
           table = table.upper()

        cursor = self.connect(cr, uid, year=year, context=context)
        try:
            cursor.execute('''
                SELECT CKY_ART, CKY_CNT_FOR_AB FROM %s;''' % table)
            return cursor               
        except: 
            return False
    
class ProductProduct(osv.osv):
    ''' Add product supplier obj
    '''    
    _inherit = 'product.product'
    
    # -------------------------------------------------------------------------
    #                             Override scheduled action
    # -------------------------------------------------------------------------    
    def schedule_sql_product_import(self, cr, uid, verbose_log_count=100, 
            write_date_from=False, write_date_to=False, create_date_from=False,
            create_date_to=False, multi_lang=False, with_price=False,
            context=None):
        ''' Update product with first supplier
        '''    
        _logger.info('Start update first supplier')

        # Pool used:
        partner_pool = self.pool.get('res.partner')

        # Import product fist:    
        #super(ProductProduct, self).schedule_sql_product_import(
        #    cr, uid, verbose_log_count=verbose_log_count, 
        #    write_date_from=write_date_from, 
        #    write_date_to=write_date_to, 
        #    create_date_from=create_date_from,
        #    create_date_to=create_date_to, 
        #    multi_lang=multi_lang, 
        #    with_price=with_price,
        #    context=context)
        cursor = self.pool.get(
            'micronaet.accounting').get_product_first_supplier(
                cr, uid, context=context)
        
        # Database for product decoding:
        products = {}
        product_ids = self.search(cr, uid, [], context=context)
        for product in self.browse(cr, uid, product_ids, context=context):
            products[product.default_code] = product.id
        _logger.info('Product database created')
            
        # Update partner    
        for record in cursor:
            default_code = record['CKY_ART']
            partner_code = record['CKY_CNT_FOR_AB']
            if not partner_code:
                continue # no first supplier
            
            if default_code not in products:
                _logger.error('Product code non found: %s' % default_code)
                
            product_id = products[default_code]                
            partner_ids = partner_pool.search(cr, uid, [
                ('sql_supplier_code', '=', partner_code)], context=context)
            if not partner_ids:
                _logger.error('Partner code non found: %s' % partner_code)
                continue
            
            # Update
            self.write(cr, uid, product_id, {
                'first_supplier_id': partner_ids[0],
                }, context=context)
            _logger.info('Update %s > %s' % (default_code, partner_code))    
        _logger.info('End syncronization')

