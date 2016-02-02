# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
# See the GNU Affero General Public License for more details.
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
from openerp import SUPERUSER_ID #, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)


class MicronaetAccounting(orm.Model):
    ''' Extend for add quey used
    '''    
    _inherit = 'micronaet.accounting'

    def get_ledger_list(self, cr, uid, context=None):
        ''' List of all ledger used for counterpart
            Table: AR_ANAGRAFICHE
        '''
        table = 'ar_anagrafiche'
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)        
        try:
            cursor.execute('''
                SELECT DISTINCT 
                    CKY_CNT_CPAR_RIC as CKY_CNT
                FROM 
                    %s 
                WHERE CKY_CNT_CPAR_RIC != ''
                UNION 
                SELECT 
                    DISTINCT CKY_CNT_CPAR_COS as CKY_CNT                     
                FROM 
                    %s 
                WHERE CKY_CNT_CPAR_COS != '';
                ''' % (table, table))
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False

    def get_product_ledger(self, cr, uid, context=None):
        ''' Return product and 2 counter part ledger (revenue and cost)
            Table: AR_ANAGRAFICHE
        '''
        table = 'ar_anagrafiche'
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)        
        try:
            cursor.execute('''
                SELECT 
                    CKY_ART, 
                    CKY_CNT_CPAR_RIC, CKY_CNT_CPAR_COS
                FROM %s;
            ''' % table)
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False

class ProductProduct(orm.Model):
    ''' Extend product.product for variants
    '''    
    _inherit = 'product.product'
    
    # -------------------------------------------------------------------------
    #                              Scheduled action
    # -------------------------------------------------------------------------    
    # Override action:
    def schedule_sql_product_import(self, cr, uid, verbose_log_count=100, 
            write_date_from=False, write_date_to=False, create_date_from=False,
            create_date_to=False, multi_lang=False, with_price=False, 
            context=None):
        ''' Use same action for import product, before will import that after
            update ledger from account
        '''
        super(ProductProduct, self).schedule_sql_product_import(
            cr, uid, verbose_log_count=100, 
            write_date_from=write_date_from, write_date_to=write_date_to, 
            create_date_from=create_date_from, 
            create_date_to=create_date_to, multi_lang=multi_lang, 
            with_price=with_price, context=context)

        _logger.info('Start update ledger to product')
        
        # Pool used:
        account_proxy = self.pool.get('account.account')            

        # -----------------------------------------------------------------
        #                Check presence for ledger used:
        # -----------------------------------------------------------------
        # MySQL read agent list:
        cursor = self.pool.get(
            'micronaet.accounting').get_ledger_list(
                cr, uid, context=context)
        if not cursor:
            _logger.error(
                "Unable to connect, no importation ledger-product!")
            return False

        i = 0
        account_list = {} # for speed up operations
        account_error = []            
        for record in cursor:
            i += 1
            try:
                account_code = record['CKY_CNT']
                
                # Search code to update:
                account_ids = account_proxy.search(cr, uid, [
                  ('account_ref', '=', account_code)])

                if account_ids: # update
                    account_list[account_code] = account_ids[0]
                else:
                    account_error.append(account_code)
            except:
                _logger.error(
                    'Error importing account [%s], jumped: %s' % (
                        account_code, 
                        sys.exc_info()))
        
        self.pool.get('res.partner').message_new(
            cr, uid, {
                #'from': 1,
                #'to': 1,
                'subject': 'Account code not found: %s' % (account_error),                    
                }, custom_values=None, context=None)

        # --------------------------------------------------
        # Error if ledger not present (will not be created!)                
        # --------------------------------------------------
        if account_error: 
            # TODO comunicate!! 
            _logger.error('Account code not found: %s' % (account_error, ))

        # -----------------------------------------------------------------
        #                    Create partner-account:
        # -----------------------------------------------------------------
        cursor = self.pool.get(
            'micronaet.accounting').get_product_ledger(
                cr, uid, context=context)
        if not cursor:
            _logger.error(
                'Unable to connect, no importation product-account!')
            return False

        # Load all product ID from code:
        product_list = {}
        product_ids = self.search(cr, uid, [], context=context)
        for product in self.browse(cr, uid, product_ids, context=context):
            if not product.default_code:
                continue
            product_list[product.default_code] = product.id

        i = 0
        for record in cursor:
            i += 1
            if verbose_log_count and i % verbose_log_count == 0:
                _logger.info('Import: %s record imported / updated!' % i)                    
            try:
                # Field mapping:
                product_code = record['CKY_ART']
                account_cost = record['CKY_CNT_CPAR_COS']
                account_revenue = record['CKY_CNT_CPAR_RIC']
                
                if product_code not in product_list:
                    _logger.error(
                        'Product code not found: %s' % product_code)
                    continue

                # ---------------------
                # Create data to write:
                # ---------------------                    
                data = {}
                error = ''
                
                # Cost:
                if account_cost in account_list:
                    data['property_account_expense'] = account_list[
                        account_cost]
                else:
                    error += 'No expense: %s' % account_code

                # Revenue:
                if account_revenue in account_list:
                    data['property_account_income'] = account_list[
                        account_revenue]
                else:
                    error += 'No revenue: %s' % account_revenue

                # Update product:
                if data:
                    self.write(cr, uid, product_list[product_code], data, 
                        context=context)
                    _logger.info('Product updated: %s [%s]' % (
                        product_code, error, ))
                else:        
                    _logger.error('No account for product: %s' % (
                        product_code))
                        
            except:
                _logger.error(
                    'Error importing product-account [%s], jumped: %s' % (
                        record, 
                        sys.exc_info()))
        _logger.info('All product account is updated!')
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
