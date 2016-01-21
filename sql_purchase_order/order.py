# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO, Open Source Management Solution
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
from utility import *


_logger = logging.getLogger(__name__)

class PurchaseOrderSql(orm.Model):
    '''Update basic object for import accounting elements
       NOTE: in this procedure there's some fields that are created
             from another module, TODO correct for keep module 'modular'
    '''
    _inherit = 'micronaet.accounting'
    
    # get_of_lines:
    def get_oc_header(self, cr, uid, context=None):
        ''' Return OF_TESTATE
        '''
        table = 'of_testate'
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)

        try:
            cursor.execute('''SELECT * FROM %s;''' % table)
            return cursor
        except: 
            _logger.error('Executing query %s: [%s]' % (
                table,
                sys.exc_info(), ))
            return False

    def get_oc_line(self, cr, uid, with_desc=False, context=None):
        ''' Return quantity element for product
            Table: OF_RIGHE
            cr: database cursor
            uid: user ID
            with_desc: load also description line
            context: context for parameters
        '''
        table = 'of_righe'
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)
        where = ''
        if not with_desc:
            where = ' WHERE IST_RIGA != 'D''

        try:
            cursor.execute('''
                SELECT * FROM %s%s;''' % (table, where))
            return cursor # with the query setted up                  
        except: 
            _logger.error('Executing query %s: [%s]' % (
                table,
                sys.exc_info(), ))
            return False

class PurchaseOrderSql(orm.Model):
    '''Update basic object for import accounting elements
       NOTE: in this procedure there's some fields that are created
             from another module, TODO correct for keep module 'modular'
    '''
    _inherit = 'purchase.order'

    # -----------------
    # Utility function:
    # -----------------
    def load_converter(self, cr, uid, ids, carriage_condition, transportation_reason, 
            payment, context=None):
        ''' Load useful converters
        '''    
        
        # Create a converter for carriage condition:
        cc_pool = self.pool.get('stock.picking.carriage_condition')
        cc_ids = cc_pool.search(cr, uid, [], context=context)
        for item in cc_pool.browse(cr, uid, cc_ids, context=context):
            if item.account_code:
                carriage_condition[item.account_code] = item.id

        # Create a converter for transportation reason:
        tr_pool = self.pool.get('stock.picking.transportation_reason')
        tr_ids = tr_pool.search(cr, uid, [], context=context)
        for item in tr_pool.browse(cr, uid, tr_ids, context=context):
            if item.import_id:
                transportation_reason[item.import_id] = item.id
                
        # Create a converter for payment:
        payment_pool = self.pool.get('account.payment.term')
        payment_ids = payment_pool.search(cr, uid, [], context=context)
        for item in payment_pool.browse(cr, uid, payment_ids, context=context):
            if item.import_id:
                payment[item.import_id] = item.id
        return        
    
    #def get_oc_key(self, record):
    #    ''' Compose and return key for OC
    #    '''
    #    return (record['CSG_DOC'].strip(), record['NGB_SR_DOC'],
    #        record['NGL_DOC'])

    def get_uom(self, cr, uid, name, context=None):
        uom_id = self.pool.get('product.uom').search(cr, uid, [
            ('name', '=', name), ])
        if uom_id:
            return uom_id[0] # take the first
        else:
            return False

    # -------------------------------------------------------------------------
    #                           Button event:
    # -------------------------------------------------------------------------
    def schedule_etl_purchase_order(self, cr, uid, context=None):
        ''' Button event for import all order (purchase)
        '''
        _logger.info('Start update extra info OC header')
        query_pool = self.pool.get('micronaet.accounting')
        partner_pool = self.pool.get('res.partner')

        cr_of= query_pool.get_of_header(cr, uid, context=context)
        if not cr_of:
            _logger.error('Cannot connect to MSSQL OF_TESTATE')
            return

        # -----------
        # Converters:
        # -----------
        orders = {}
        carriage_condition = {}
        transportation_reason = {}
        payment = {}
        self.load_converter(cr, uid, ids, carriage_condition, 
            transportation_reason, payment, context=context
            
        # ---------------------------------------------------------------------
        #                           HEADER:
        # ---------------------------------------------------------------------
        for of in cr_of:
            try:
                # -------------------------------------------------------------
                #                          Get data: 
                # -------------------------------------------------------------                
                # Partner:
                partner_code = of['CKY_CNT_CLFR']
                partner_ids = partner_pool.search(cr, uid, [
                    ('sql_supplier_code', '=', partner_code),
                    ], context=context)
                if not partner_ids:    
                    _logger.error(
                        'No partner found, code: %s' % partner_code)
                    continue
 
                # Destination:
                dest_code = of['CKY_CNT_SPED_ALT']
                dest_ids = partner_pool.search(cr, uid, ['|',
                    ('sql_supplier_code', '=', dest_code),
                    ('sql_destination_code', '=', dest_code),
                    ], context=context)
                if dest_ids:    
                    dest_id = dest_ids[0]
                else:    
                    _logger.error(
                        'No destination found, code: %s' % dest_code)
                    dest_id = False        
                    #continue

                # Update transport readon: NKY_CAUM
                transportation_reason_code = of['NKY_CAUM']                
                if transportation_reason_code:
                    transportation_reason_id = transportation_reason.get(
                        transportation_reason_code, False)
                    if transportation_reason_id:    
                        data['transportation_reason_id'
                            ] = transportation_reason_id
                        _logger.info('Tranportation reason update: %s' % name)
                    else:
                        _logger.warning(
                            'Tranportation reason not found: %s' % (
                                transportation_reason_code))
                                
                # Update payment
                payment_term_code = oc['NKY_PAG']
                payment_term_id = False
                if payment_term_code:
                    payment_term_id = payment.get(
                        payment_term_code, False)

                # Update porto:
                #carriage_condition_code = oc['IST_PORTO']                
                #if carriage_condition_code:
                #    carriage_condition_id = carriage_condition.get(
                #        carriage_condition_code, False)
                #    if carriage_condition_id:    
                #        data['carriage_condition_id'] = carriage_condition_id
                #        _logger.info('Carriage condition update: %s' % name)
                #    else:
                #        _logger.warning('Carriage condition not found: %s' % (
                #            carriage_condition_code))

                # Update note:
                # TODO 
                #carrier_code = oc['CKY_CNT_VETT']

                # Parcels:
                #parcels = oc['NGB_TOT_COLLI']
                #if parcels:
                #    data['parcels'] = parcels
                #    _logger.info('Update parcels: %s' % name)

                # Key field:
                name = 'MX-%s/%s' % (
                    of['NGL_DOC'], of['DTT_DOC'].strftime('%Y'))

                of_ids = self.search(cr, uid, [
                    ('name', '=', name),
                    #('accounting_order', '=', True), # No more used!
                    ], context=context)

                header = {
                    'name': name,
                    'partner_id': partner_ids[0],
                    'destination_partner_id': dest_id,
                    
                    'date_order': of['DTT_DOC'][:10],
                    'payment_term_id': payment_term_id,
                    'transportation_reason_id': transportation_reason_id,
                    'notes': of['CDS_NOTE']
                    #'goods_description_id':
                    #'transportation_method':                    
                    #'carriage_condition_id':
                    #'partner_ref': 
                    #'currency_id'
                    #'used_bank_id'
                    #'fiscal_position'
                    #'payment_note':
                    #'delivery_note':
                    #'note'TODO???
                    #'incoterm_id'
                    #'minimum_planned_date'
                    }                    
                    
                if of_ids:
                    _logger.info('Update header: %s' % name)
                    order_id = of_ids[0]
                    self.write(cr, uid, order_id, data, context=context)
                else:
                    _logger.info('Create header: %s' % name)
                    order_id = self.create(cr, uid, ids, data, 
                        context=context)
                        
                # Save for line:
                orders[name] = order_id

            except:
                _logger.error('Problem with record: %s > %s'%(
                    of, sys.exc_info()))

        # ---------------------------------------------------------------------
        #                           LINE:
        # ---------------------------------------------------------------------
        _logger.info('Start import OF lines')
        line_pool = self.pool.get('sale.order.line')
        cr_of_line = query_pool.get_of_line(cr, uid, context=context)
        if not cr_oc_line:
            _logger.error('Cannot connect to MSSQL OF_RIGHE')
            return

        i = 0
        '''for oc_line in cr_oc_line:
            try:
                i += 1
                if i % 100 == 0:
                    _logger.info('Sync %s lines' % i)
                    
                oc_key = get_oc_key(oc_line)
                if oc_key not in oc_header:
                    _logger.warning(
                        'Header order not found (old order?): OC-%s' % (
                            oc_key[2]))
                    continue

                # -----------------------------
                # Get product browse from code:
                # -----------------------------
                product_browse = browse_product_ref(
                    self, cr, uid, oc_line['CKY_ART'].strip(), 'Unit(s)', 
                    context=context)
                if not product_browse:
                    _logger.info(
                        _('No product found (OC line jumped): %s') % (
                            oc_line['CKY_ART'], ))
                    continue

                order_id = oc_header[oc_key][0]
                date_deadline = oc_line['DTT_SCAD'].strftime(
                    '%Y-%m-%d') if oc_line[
                        'DTT_SCAD'] and oc_line[
                            'DTT_SCAD'] != empty_date else False

                # NOTE ID of line in OC (not sequence=order)
                sequence = oc_line['NPR_RIGA']
                uom_id = product_browse.uom_id.id if product_browse else False
                conversion = (
                    oc_line['NCF_CONV'] if oc_line['NCF_CONV'] else 1.0)
                
                # pack * unit item * conversion
                quantity = (oc_line['NGB_COLLI'] or 1.0) * (
                    oc_line['NQT_RIGA_O_PLOR'] or 0.0) * 1.0 / conversion
                
                try:
                    family_id = product_browse.family_id.id
                except:
                    family_id = False    

                # HEADER: Save deadline in OC (only first time):
                if not oc_header[oc_key][1]:
                    # take the first deadline and save in header
                    if date_deadline:
                        oc_header[oc_key][1] = True
                        mod = self.write(cr, uid, order_id, {
                            'date_deadline': date_deadline}, context=context)

                # ---------------                    
                # Discount block:    
                # ---------------                    
                discount = False
                multi_discount_rates = False    
                account_scale = oc_line['CSG_SCN'].strip()
                if account_scale:
                    try:
                        res = line_pool.on_change_multi_discount(
                            cr, uid, False, account_scale, 
                            context=context)['value']
                        discount = res.get('discount', False)
                        multi_discount_rates = res.get(
                            'multi_discount_rates', False)
                    except:
                        _logger.error(
                            'Error calculating discount value: %s' % (
                                account_scale))
                        pass

                # Common part of record (update/create):
                data_update = { # update
                    'product_uom_qty': quantity,
                    'order_id': order_id,
                    }
                
                # Create only record:                
                data_create = { # create
                    # Notmal fields -------------------------------------------
                    'product_id': product_browse.id,
                    'date_deadline': date_deadline,
                    'product_uom': uom_id,
                    'name': oc_line['CDS_VARIAZ_ART'],
                    
                    'price_unit': (
                        oc_line['NPZ_UNIT'] or 0.0) * conversion,
                    'tax_id': [
                        (6, 0, [product_browse.taxes_id[0].id, ])
                        ] if product_browse and product_browse.taxes_id
                            else False, # CSG_IVA
                    'sequence': sequence,
                    'discount': discount,
                    'multi_discount_rates': multi_discount_rates,
                    
                    # Related fields ------------------------------------------
                    'accounting_order': True,
                    'family_id': family_id,
                    'partner_id': order_partner.get(order_id, False),
                    'is_manufactured': product_browse.internal_manufacture,
                    }

                # --------------------
                # Syncronization part:
                # --------------------
                key = (
                    order_id, 
                    data_create['product_id'], 
                    data_create['date_deadline'], )

                # Loop on all odoo order line for manage sync mode
                if update and key in DB_line:
                    # [ID, finded, q., maked, state]                    
                    element = DB_line[key]
                    oc_line_id = element[0]
                    #TODO totalize all key line for duplications
                     
                    # 4 case (all not B, all B, not B-B, B-not B                            
                    # TODO test instead of writing for speed up
                    if oc_line['IST_RIGA_SOSP'] == 'B':
                        element[3] += data_update['product_uom_qty'] # counter
                        data_update['product_uom_maked_sync_qty'] = element[3]
                        if element[1]: # TODO not B first or error??
                            del data_update['product_uom_qty'] # leave prev.
                        else: # Create B line
                            element[1] = True # set line as assigned!
                        line_pool.write(
                            cr, uid, oc_line_id, data_update, 
                            context=context)
                            # TODO sync_state = ?
                    else: # Line not produced:              
                        data_update['sequence'] = sequence # only without B line
      
                        if not element[1]: # error or B created first
                            #if abs(element[4] - quantity) < 1.0: 
                            #data_update['accounting_state'] = 'new' #TODO need
                            element[1] = True # set line as assigned!

                            # Modify record:
                        line_pool.write(
                            cr, uid, oc_line_id, data_update, 
                            context=context)
                else: # Create record, not found: (product_id-date_deadline)
                    # Update record with value for creation:                    
                    data_update.update(data_create)
                    # TODO manage better!!!!!!
                    #if oc_line['IST_RIGA_SOSP'] == 'B':
                    #    account_maked = data_update.get(
                    #        'product_uom_qty', 0.0)
                    #    data_update[
                    #        'product_uom_maked_sync_qty'] = account_maked
                    #else:
                    #    account_maked = 0.0
                        
                    oc_line_id = line_pool.create(
                        cr, uid, data_update, context=context)
                        
                    # TODO needed?!?    
                    
                    #DB_line[key] = [oc_line_id, True,
                    #    data_update.get(
                    #        'product_uom_qty', 0.0), account_maked, '']
                    
                    # product_uom_maked_sync_qty
                    # data_update.get('sync_state', False), # TODO change?
            except:
                _logger.error('Problem with oc line record: %s\n%s' % (
                    oc_line, sys.exc_info()))'''

        # TODO testare bene gli ordini di produzione che potrebbero avere delle mancanze!        
        _logger.info('End importation OF header and line!')
        return
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
