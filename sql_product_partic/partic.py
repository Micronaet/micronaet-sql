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

    # ------------
    #  TRANSPORT -
    # ------------
    def get_partic_product_partner(self, cr, uid, year=False, context=None):
        ''' Access to anagrafic table of partic productpartner
            Table: tz_prz_cli_art
        '''
        table = 'tz_prz_cli_art'
        if self.pool.get('res.company').table_capital_name(cr, uid, 
                context=context):
           table = table.upper()

        cursor = self.connect(cr, uid, year=year, context=context)
        try:
            cursor.execute('''
                SELECT 
                    CKY_ART, CSG_ART_CLI_FOR, CKY_CNT 
                FROM %s;
                ''' % table)
            return cursor # with the query setted up                  
        except: 
            return False  # Error return nothing
    
class ResPartnerProductPartic(osv.osv):
    ''' Add product partic obj
    '''    
    _inherit = 'res.partner.product.partic'
    
    # -------------------------------------------------------------------------
    #                             Scheduled action
    # -------------------------------------------------------------------------
    def schedule_sql_product_partic_import(self, cr, uid, context=None):
        ''' Import partner product partic
        '''            
        try:
            _logger.info('Start import SQL: partner product partic')
            
            cursor = self.pool.get(
                'micronaet.accounting').get_partic_product_partner(
                    cr, uid, context=context)
            if not cursor:
                _logger.error('Unable to connect, no partic!')
                return True

            i = 0            
            product_pool = self.pool.get('product.product')
            partner_pool = self.pool.get('res.partner')
            for record in cursor:
                i += 1
                try:
                    item_code = record['CKY_ART']
                    partner_code = record['CKY_CNT']
                    customer_article = record['CSG_ART_CLI_FOR']
                    
                    product_ids =  product_pool.search(cr, uid, [
                        ('default_code', '=', item_code)], context=context)
                    if not product_ids:
                        _logger.error(
                            'Product code no found (jump): %s' % item_code)
                        continue    

                    partner_ids = partner_pool.search(cr, uid, [
                        '|',
                        ('sql_customer_code', '=', partner_code),
                        ('sql_supplier_code', '=', partner_code),
                        ], context=context)
                    if not partner_ids:
                        _logger.error(
                            'Partner code no found (jump): %s' % partner_code)
                        continue    
                         
                       
                    partic_ids = self.search(cr, uid, [
                        ('product_id', '=', product_ids[0]),
                        ('partner_id', '=', partner_ids[0]),                        
                        ], context=context)
                    if partic_ids:
                        self.write(cr, uid, partic_ids, {
                            'partner_code': customer_article,
                            }, context=context)    
                        _logger.info('Update partner: %s' % record)                     
                    else:
                        self.create(cr, uid, {
                            'product_id': product_ids[0],
                            'partner_id': partner_ids[0],
                            'partner_code': customer_article,
                            }, context=context)
                        _logger.info('Create partner: %s' % record)                     
                except:
                    _logger.error('Error importing partic [%s]' % (
                        sys.exc_info(), ))
                                            
        except:
            _logger.error('Error generic import partic: %s' % (
                sys.exc_info(), ))
            return False
        _logger.info('All transportation is updated!')
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
