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
    ''' Object for keep function with the query
        Record are only table with last date of access
    '''
    _inherit = "micronaet.accounting"

    # -------------------
    #  GOODS DESCRIPTION:
    # -------------------
    def get_goods_description(self, cr, uid, year=False, context=None):
        ''' Access to anagrafic table of goods desc.
            Table: MB_ASP_EST_BENI
        '''
        if self.pool.get('res.company').table_capital_name(cr, uid, 
                context=context):
            table = "MB_ASP_EST_BENI" 
        else:
            table = "mb_asp_est_beni"

        cursor = self.connect(cr, uid, year=year, context=context)
        try:
            cursor.execute("""
                SELECT NKY_ASPBEN, CDS_ASPBEN FROM %s WHERE CDS_ASPBEN != '';
                """ % table)
            return cursor
        except: 
            return False


class stock_picking_goods_description(osv.osv):
    ''' Extend stock.picking.goods_description
    '''    
    _inherit = 'stock.picking.goods_description'
    
    # -------------------------------------------------------------------------
    #                             Scheduled action
    # -------------------------------------------------------------------------
    def schedule_good_description_import(self, cr, uid, context=None):
        ''' Import goods description
        '''            
        try:
            _logger.info('Start import SQL: good descriptions')
            
            cursor = self.pool.get(
                'micronaet.accounting').get_goods_description(
                    cr, uid, context=context)
            if not cursor:
                _logger.error('Unable to connect, no good description!')
                return True

            i = 0
            for record in cursor:
                i += 1
                try:
                    import_id = record['NKY_ASPBEN']
                    data = {
                        'import_id': import_id,
                        'name': record['CDS_ASPBEN'],
                        }                    
                    goods_ids = self.search(cr, uid, [
                        ('import_id', '=', import_id)], context=context)

                    # Update / Create
                    if goods_ids:
                        goods_id = goods_ids[0]
                        self.write(cr, uid, goods_id, data, 
                            context=context)
                    else:
                        goods_id = self.create(
                            cr, uid, data, context=context)
                except:
                    _logger.error('Error importing goods desc.[%s]' % (
                        sys.exc_info(), ))
                                            
        except:
            _logger.error('Error generic import goods description: %s' % (
                sys.exc_info(), ))
            return False
        _logger.info('All goods description is updated!')
        return True

    # -------------------------------------------------------------------------
    #                                 Columns
    # -------------------------------------------------------------------------
    _columns = {
        'import_id': fields.integer('SQL import'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
