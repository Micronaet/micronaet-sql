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
    def get_of_header(self, cr, uid, context=None):
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

    def get_of_line(self, cr, uid, with_desc=False, context=None):
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
            where = ' WHERE IST_RIGA != \'D\''

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
    def load_converter(self, cr, uid, carriage_condition, transportation_reason, 
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
        _logger.info('Start update extra info OF header')
        query_pool = self.pool.get('micronaet.accounting')
        partner_pool = self.pool.get('res.partner')
        location_pool = self.pool.get('stock.location')

        cr_of = query_pool.get_of_header(cr, uid, context=context)
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
        self.load_converter(cr, uid, carriage_condition, 
            transportation_reason, payment, context=context)
            
        location_ids = location_pool.search(cr, uid, [
            ('name', '=', 'Stock')], context=context)            
        if not location_ids:
            _logger.error('Cannot found location: Stock')
            return    
        
        pricelist_id = 2 # TODO     
    
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
                dest_id = False        
                if dest_code:
                    dest_ids = partner_pool.search(cr, uid, ['|',
                        ('sql_supplier_code', '=', dest_code),
                        ('sql_destination_code', '=', dest_code),
                        ], context=context)
                    if dest_ids:    
                        dest_id = dest_ids[0]
                    else:
                        _logger.error('Destination not found: %s' % dest_code)    

                # Update transport readon: NKY_CAUM
                transportation_reason_code = of['NKY_CAUM']                
                transportation_reason_id = False
                if transportation_reason_code:
                    transportation_reason_id = transportation_reason.get(
                        transportation_reason_code, False)
                    if not transportation_reason_id:
                        _logger.error('Tranportation reason not found: %s' % (
                            transportation_reason_code))   
                                
                # Update payment
                payment_term_code = of['NKY_PAG']
                payment_term_id = False
                if payment_term_code:
                    payment_term_id = payment.get(
                        payment_term_code, False)
                    if not payment_term_id:
                        _logger.error('Payment code not found: %s' % (
                            payment_term_code))   

                # Update porto:
                #carriage_condition_code = of['IST_PORTO']                
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
                #carrier_code = of['CKY_CNT_VETT']

                # Parcels:
                #parcels = of['NGB_TOT_COLLI']
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
                    
                    'date_order': of['DTT_DOC'].strftime(
                        DEFAULT_SERVER_DATE_FORMAT),
                    'payment_term_id': payment_term_id,
                    'transportation_reason_id': transportation_reason_id,
                    'notes': of['CDS_NOTE'],
                    'location_id': location_ids[0],
                    'pricelist_id': pricelist_id, 
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
                    self.write(cr, uid, order_id, header, context=context)
                else:
                    _logger.info('Create header: %s' % name)
                    order_id = self.create(cr, uid, header, 
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
        product_pool = self.pool.get('product.product')
        
        cr_of_line = query_pool.get_of_line(cr, uid, context=context)
        if not cr_of_line:
            _logger.error('Cannot connect to MSSQL OF_RIGHE')
            return

        for of_line in cr_of_line:
            try:
                # -----------------------------
                # Get product browse from code:
                # -----------------------------
                name = 'MX-%s/%s' % (
                    of_line['NGL_DOC'], of_line['DTT_DOC'].strftime('%Y'))
                order_id = orders.get(name, False)
                if not order_id:
                    _logger.error('Order not found: %s' % name)  
                    continue

                # Product:
                product_code = oc_line['CKY_ART'].strip()
                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', product_code)], context=context)               
                if not product_ids:
                    _logger.info(
                        _('No product found (OC line jumped): %s') % (
                            product_code))                
                    continue                            
                product_browse = product_pool.browse(
                    cr, uid, product_ids, context=context)[0]

                date_planned = oc_line['DTT_SCAD'].strftime(
                    DEFAULT_SERVER_DATE_FORMAT)

                # NOTE ID of line in OC (not sequence=order)
                sequence = oc_line['NPR_RIGA']
                uom_id = product_browse.uom_id.id if product_browse else False
                conversion = (
                    oc_line['NCF_CONV'] if oc_line['NCF_CONV'] else 1.0)
                
                # pack * unit item * conversion
                quantity = (oc_line['NGB_COLLI'] or 1.0) * (
                    oc_line['NQT_RIGA_O_PLOR'] or 0.0) * 1.0 / conversion
                
                # HEADER: Save deadline in OC (only first time):
                #if not oc_header[oc_key][1]:
                #    # take the first deadline and save in header
                #    if date_deadline:
                #        oc_header[oc_key][1] = True
                #        mod = self.write(cr, uid, order_id, {
                #            'date_deadline': date_deadline}, context=context)

                # Discount block:    
                #discount = False
                #multi_discount_rates = False    
                account_scale = oc_line['CSG_SCN'].strip()
                discount = account_scale or False
                #if account_scale:
                #    try:
                #        res = line_pool.on_change_multi_discount(
                #            cr, uid, False, account_scale, 
                #            context=context)['value']
                #        discount = res.get('discount', False)
                #        multi_discount_rates = res.get(
                #            'multi_discount_rates', False)
                #    except:
                #        _logger.error(
                #            'Error calculating discount value: %s' % (
                #                account_scale))
                #        pass

                data = {
                    'product_id': product_browse.id,
                    'product_uom_qty': quantity,
                    'order_id': order_id,
                    'date_planned': date_planned,
                    'product_uom': uom_id,
                    'name': oc_line['CDS_VARIAZ_ART'],                    
                    'price_unit': (
                        oc_line['NPZ_UNIT'] or 0.0) * conversion,
                    # Correct depend on fiscal position    
                    'tax_id': [
                        (6, 0, [product_browse.taxes_id[0].id, ])
                        ] if product_browse and product_browse.taxes_id
                            else False, # CSG_IVA
                    'sequence': sequence,
                    'discount': discount,
                    #'multi_discount_rates': multi_discount_rates,
                    
                    # Related fields ------------------------------------------
                    #'partner_id': order_partner.get(order_id, False),
                    }

            except:
                _logger.error('Problem with oc line record: %s\n%s' % (
                    oc_line, sys.exc_info()))

        # TODO testare bene gli ordini di produzione che potrebbero avere delle mancanze!        
        _logger.info('End importation OF header and line!')
        return
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
