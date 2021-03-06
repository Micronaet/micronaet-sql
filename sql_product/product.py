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

class ProductProduct(orm.Model):
    ''' Extend product.product
    '''    
    _inherit = 'product.product'
    
    _columns = {
        'sql_import': fields.boolean('SQL import', required=False),
        'accounting_structured': fields.char('Accounting structured', size=2),
        'statistic_category': fields.char('Statistic category', size=10),
        }
    
    _defaults = {
        'sql_import': lambda *a: False,
        'statistic_category': lambda *x: False,
        }

    def get_product_from_sql_code(self, cr, uid, code, context = None):
        ''' Return product_id read from the import code passed
            (all product also pre-deleted
        '''
        product_ids = self.search(cr, uid, [('default_code', '=', code)])

        if product_ids:
            return product_ids[0]
        return False

    def get_is_to_import_product(self, cr, uid, item_id, context = None):
        ''' Return if the product is to import (MM) from ID
        '''
        product_id = self.search(cr, uid, [('id', '=', item_id)])
        if product_id:
            product_browse = self.search(cr, uid, product_id, context=context)
            return not product_browse[0].not_analysis

        return True #False # Jump line with product not found

    # -------------------------------------------------------------------------
    #                                  Scheduled action
    # -------------------------------------------------------------------------
    def schedule_sql_product_import(self, cr, uid, verbose_log_count=100, 
            write_date_from=False, write_date_to=False, create_date_from=False,
            create_date_to=False, multi_lang=False, with_price=False,
            context=None):
        ''' Import product from external SQL DB
            self: instance
            cr: cursor
            uid: user ID
            verbose_log_count: verbose read record every X (0 for nothing)
            write_date_from: write to
            write_date_to: write to
            create_date_from: create from 
            create_date_to: create to
            with_price: if force price (sale) 
            multi_lang: dict of extra language, ex.: {1: 'en_US'} where key
                        is ID in accounting, value is language code
            context: args passed            
        '''        
        if context is None:
            context = {'lang': 'it_IT'}
        if not multi_lang:
            multi_lang = {}    
            
        _logger.info('Start import product via SQL database:')
        #'''
        #    Start import product, parameters:
        #    verbose count: %s - from write %s - to write %s
        #    from create % - to create %s - multi lang: %s''' % (
        #        verbose_log_count,
        #        write_date_from,
        #        write_date_to,
        #        create_date_from,
        #        create_date_to,
        #        multi_lang,          
        #        ))
        product_pool = self.pool.get('product.product')
        accounting_pool = self.pool.get('micronaet.accounting')
        
        # ---------------------------------------------------------------------
        #         UOM check if mx_link_uom module is installed:
        # ---------------------------------------------------------------------
        uom_pool = self.pool.get('product.uom')
        product_uom = {}
        try:
            uom_ids = uom_pool.search(cr, uid, [
                ('account_ref', '!=', False)], context=context)
            for uom in uom_pool.browse(cr, uid, uom_ids, context=context):
                product_uom[uom.account_ref.upper()] = uom.id
        except:
            pass # no product_uom population         
        # ---------------------------------------------------------------------

        product_translate = {} # for next translation
            
        # --------------------------
        # Get route for manufacture: 
        # --------------------------
        #TODO >> use a check bool??
        route_pool = self.pool.get('stock.location.route')
        route_ids = route_pool.search(cr, uid, [
            ('name', '=', 'Manufacture')], context=context)
        to_manufacture = (1, ) # TODO parametrize (list of structured record)
        if route_ids:
            manufacture = [(6, 0, [route_ids[0]])]
        else:
            manufacture = False

        try:
            cursor = accounting_pool.get_product( 
                cr, uid, active=False, 
                write_date_from=write_date_from,
                write_date_to=write_date_to, 
                create_date_from=create_date_from,
                create_date_to=create_date_to, 
                context=context) 
            if not cursor:
                _logger.error(
                    "Unable to connect no importation of packing for product!")
                return False

            i = 0
            for record in cursor:
                try:
                    i += 1
                    if verbose_log_count and i % verbose_log_count == 0:
                        _logger.info('Import %s: record import/update!' % i)                             

                    default_code = record['CKY_ART']
                    data = {
                        # TODO IFL_ART_DBP o DBV for supply_method='produce'
                        'name': record['CDS_ART'] + (
                            record['CDS_AGGIUN_ART'] or ''),
                        # TODO description_sale = name??     
                        'default_code': default_code,
                        'sql_import': True,
                        'active': True,
                        'accounting_structured': record['NKY_STRUTT_ART'],
                        'statistic_category': "%s%s" % (
                            record['CKY_CAT_STAT_ART'] or '', 
                            "%02d" % int(
                                record['NKY_CAT_STAT_ART'] or '0') if record[
                                    'CKY_CAT_STAT_ART'] else '',
                            ),
                        # TODO parametrize cost price
                        #'standard_price': record[], # cost
                        }
                    # -------------------------    
                    # Test if is to manufacture
                    # -------------------------    
                    if manufacture and record[
                            'NKY_STRUTT_ART'] in to_manufacture:
                        data['route_ids'] = manufacture
                     
                    # 03 mar 2020 Remove because Account not the master data:
                    #if accounting_pool.is_active(record):
                    #    data['state'] = 'sellable'
                    #else:
                    #    data['state'] = 'obsolete'
                        
                    product_ids = product_pool.search(cr, uid, [
                        ('default_code', '=', default_code)])
                    

                    if product_ids:
                        if len(product_ids) > 1:
                            _logger.warning('Multiple article: %s (%s)' % (
                                default_code,
                                len(product_ids), 
                                ))
                        product_id = product_ids[0]
                        del data['default_code'] # no write code (notification)
                        
                        # TODO check if lang is italian in normal creation
                        product_pool.write(cr, uid, product_id, data, 
                            context=context)
                    else:
                        # -----------------------------------------------------
                        # Product UOM:
                        # -----------------------------------------------------
                        # XXX only for creation?!?:
                        uom_ref = record['CSG_UNIMIS_PRI']
                        if uom_ref:
                            uom_ref = uom_ref.upper()
                            uom_id = product_uom.get(uom_ref, False)
                            if uom_id:
                                data['uom_id'] = uom_id
                                data['uom_po_id'] = uom_id
                                #data['uos_id'] = uom_id                             
                            else:
                                _logger.error('No UOM ref: %s' % uom_ref)    
                        # -----------------------------------------------------
                        
                        product_id = product_pool.create(cr, uid, data, 
                            context=context)
                            
                    product_translate[default_code] = product_id # for transl.
                except:
                    _logger.error('Error import product [%s], jumped: %s' % (
                        default_code, 
                        sys.exc_info(), ))

            # --------------
            # Update prices:            
            # --------------
            if with_price:
                # TODO parameterize in call?
                cursor_price = accounting_pool.get_product_price(
                    cr, uid, context=context)
                if not cursor_price:
                    _logger.error(
                        "Unable to connect no importation of price!")
                    return False
                
                _logger.info('Start update pricelist in product')
                i = 0
                for record in cursor_price:
                    i += 1
                    if verbose_log_count and i % verbose_log_count == 0:
                        _logger.info('Update price record #%s' % i)                             

                    try:
                        default_code = record['CKY_ART']
                        product_id = product_translate.get(default_code, False)
                        if not product_id:
                            _logger.error('Product not found %s for price' % (
                                default_code))
                            continue
                        
                        if record['NPZ_LIS_1']:
                            lst_price = record['NPZ_LIS_1']
                        else:
                            # This installation use 2 price
                            lst_price = record['NPZ_LIS_2']                        
                        product_pool.write(cr, uid, product_id, {
                            'lst_price': lst_price,
                            }, context=context)
                    except:
                        _logger.error('Product not found %s for price' % (
                            default_code))
                        
            
            # ------------------------
            # Update translated terms:            
            # ------------------------
            if multi_lang:
                for lang_code, lang in multi_lang.iteritems():
                    _logger.info('Update language terms: %s' % lang)
                    context_lang = {'lang': lang, }
                    cursor = accounting_pool.get_product_language(
                        cr, uid, lang_code, context=context)
                    if not cursor:
                        _logger.error("Cannot load cursor for %s" % lang)
                        continue

                    # Start update terms:
                    i = 0
                    for record in cursor:
                        try:
                            # Write new terms:
                            default_code = record['CKY_ART']
                            name = record['CDS_ART_LIN']
                            if default_code not in product_translate:
                                _logger.error(
                                    'Code not found: %s' % default_code)
                                continue # next
                                
                            self.write(
                                cr, uid, 
                                product_translate[default_code],
                                {'name': name}, 
                                context=context_lang,
                                )
                        except:
                            _logger.error(
                                'Lang error: code: %s, jumped: %s' % (
                                    default_code, 
                                    sys.exc_info(), ))
                        
            _logger.info('All product is updated!')
        except:
            _logger.error('Error generic import product: %s' % (
                sys.exc_info(), ))
            return False
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
