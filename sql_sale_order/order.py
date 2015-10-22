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

class SaleOrderSql(orm.Model):
    """Update basic obiect for import accounting elements
       NOTE: in this procedure there's some fields that are created
             from another module, TODO correct for keep module "modular"
    """

    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    #                              Utility function
    # -------------------------------------------------------------------------
    def get_uom(self, cr, uid, name, context=None):
        uom_id = self.pool.get('product.uom').search(cr, uid, [
            ('name', '=', name), ])
        if uom_id:
            return uom_id[0] # take the first
        else:
            return False
    
    # =========================================================================
    #                               SCHEDULED ACTION
    # =========================================================================
    def schedule_etl_sale_order(self, cr, uid, update=False, delete=False,
             context=None):
        """ Import OC and create sale.order
            self: instance
            cr: database cursor
            uid: user ID
            update: if False create only new record, True try a sync wiht key
            delete: if True delete order no more present
        """
        _logger.info('Start import OC header mode: "%s"' % (
            'update' if update else 'new only'))
        query_pool = self.pool.get('micronaet.accounting')
        empty_date = query_pool.get_empty_date()
        log_info = ''

        # --------
        # Utility:
        # --------
        def get_oc_key(record):
            """ Compose and return key for OC
            """
            return (record['CSG_DOC'].strip(), record['NGB_SR_DOC'],
                record['NGL_DOC'])

        # ---------------------------------------------------------------------
        #                               IMPORT HEADER
        # ---------------------------------------------------------------------
        # Operation for manage deletion:
        if delete:
            order_ids = self.search(cr, uid, [
                ('accounting_order', '=', True),
                ('accounting_state', 'not in', ('close', )),
                ], context=context)
        if update:        
            updated_ids = []

        # Start importation from SQL:
        cr_oc = query_pool.get_oc_header(cr, uid, context=context)
        if not cr_oc:
            _logger.error("Cannot connect to MSSQL OC_TESTATE")
            return

        # Converter 
        oc_header = {} # (ref, type, number): ODOO ID
        for oc in cr_oc:
            try:
                name = "MX-%s/%s" % (
                    oc['NGL_DOC'],
                    oc['DTT_DOC'].strftime("%Y"),
                    )
                oc_ids = self.search(cr, uid, [
                    ('name', '=', name),
                    ('accounting_order', '=', True)
                    ], context=context)
                if update and oc_ids:
                    # --------------------
                    # Update header order:
                    # --------------------
                    oc_id = oc_ids[0]
                    if oc_id not in updated_ids:
                        updated_ids.append(oc_id)

                    oc_proxy = self.browse(cr, uid, oc_id, context=context)

                    # TODO:
                    header = {}
                    if header: # TODO not working for now, is necessary?
                        update = self.write(
                            cr, uid, oc_id, header, context=context)

                    try: # Note: the lines are removed when remove the header
                        if delete:
                            order_ids.remove(oc_id)
                    except:
                        pass # no error
                else:
                    # --------------------
                    # Create header order:
                    # --------------------
                    partner_proxy = browse_partner_ref(
                        self, cr, uid, oc['CKY_CNT_CLFR'], context=context)
                    if not partner_proxy or not partner_proxy.id:
                        _logger.error(
                            "No partner found (created minimal): %s" % (
                                oc['CKY_CNT_CLFR']))
                        try:
                            partner_id = self.pool.get('res.partner').create(
                                cr, uid, {
                                    'name': _("Customer %s") % (
                                        oc['CKY_CNT_CLFR']),
                                    'active': True,
                                    #'property_account_position': 1, # TODO?
                                    'is_company': True,
                                    #'employee': False,
                                    'parent_id': False,
                                    'sql_customer_code': oc['CKY_CNT_CLFR'],
                                    }, context=context)
                            # TODO reload partner_proxy function?    
                        except:
                             _logger.error(
                                 "Error creating minimal partner: %s [%s]" % (
                                     oc['CKY_CNT_CLFR'],
                                     sys.exc_info()))
                             continue # TODO jump this OC?
                    else:
                        partner_id = partner_proxy.id

                    oc_id = self.create(cr, uid, {
                        'name': name,
                        'accounting_order': True, # importation flag
                        'origin': False,
                        'picking_policy': 'direct',
                        'order_policy': 'manual',
                        'date_order': oc['DTT_DOC'].strftime("%Y-%m-%d"),
                        'partner_id': partner_id,
                        'user_id': uid,
                        'note': oc['CDS_NOTE'].strip(), # Terms and conditions
                        #'invoice_quantity': 'order', # order procurement
                        'pricelist_id':
                            partner_proxy.property_product_pricelist.id if
                                partner_proxy else 1,  # TODO put default!
                        #'partner_invoice_id': partner_id,
                        #'partner_shipping_id': partner_id, # TODO if present?
                        }, context=context)

                # Save reference for lines (deadline purpose):
                oc_key = get_oc_key(oc)
                if (oc_key) not in oc_header:
                    # (ID, Deadline) # No deadline in header take first line
                    oc_header[oc_key] = [oc_id, False]
            except:
                _logger.error("Problem with record: %s > %s"%(
                    oc, sys.exc_info()))

        # Mark as closed order not present in accounting:
        # Rule: order before - order update = order to delete
        if delete and order_ids:
            try:
                self.write(cr, uid, order_ids, {
                    'accounting_state': 'close'}, context=context)
            except:
                _logger.error("Error closing order ids: %s" % order_ids)

        # ---------------------------------------------------------------------
        #                               IMPORT LINE
        # ---------------------------------------------------------------------
        _logger.info("Start import OC lines")
        line_pool = self.pool.get('sale.order.line')
        DB_line = {}
        if update:
            order_line_ids = line_pool.search(cr, uid, [
                ('order_id', 'in', updated_ids)], context=context)
            # TODO lines for order deleted?    

            # Load all OC line in openerp DB in dict
            for ol in line_pool.browse(cr, uid, order_line_ids, 
                    context=context):
                key = (ol.order_id.id, ol.product_id.id, ol.date_deadline)
                if key in DB_line:
                    pass # TODO raise error?
                    # TODO test if present b or not b else error!
                    
                # TODO test if is present: ol.product_uom_maked_qty  
                DB_line[key] = [
                    ol.id,               # ID
                    False,               # finded
                    ol.product_uom_qty,  # q. total
                    0.0,                 # counter: product_uom_maked_sync_qty,
                    ol.sync_state,       # syncro state
                    ]

        # -------------------------
        # Read database order line:
        # -------------------------
        cr_oc_line = query_pool.get_oc_line(cr, uid, context=context)
        if not cr_oc_line:
            _logger.error('Cannot connect to MSSQL OC_RIGHE')
            return
        
        i = 0
        for oc_line in cr_oc_line:
            try:
                i += 1
                if i % 100 == 0:
                    _logger.info('Sync %s lines' % i)
                    
                oc_key = get_oc_key(oc_line)
                if oc_key not in oc_header:
                    _logger.error(
                        'Header order not found: OC-%s' % (oc_key[2]))
                    continue

                # -----------------------------
                # Get product browse from code:
                # -----------------------------
                product_browse = browse_product_ref(
                    self, cr, uid, oc_line['CKY_ART'].strip(), context=context)
                if not product_browse:
                    _logger.info(
                        _('No product found (OC line jumped): %s') % (
                            oc_line['CKY_ART'], ))
                    continue

                order_id = oc_header[oc_key][0]
                date_deadline = oc_line['DTT_SCAD'].strftime(
                    "%Y-%m-%d") if oc_line[
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

                # HEADER: Save deadline in OC (only first time):
                if not oc_header[oc_key][1]:
                    # take the first deadline and save in header
                    if date_deadline:
                        oc_header[oc_key][1] = True
                        mod = self.write(cr, uid, order_id, {
                            'date_deadline': date_deadline}, context=context)

                # common part of record (update/create):
                data = { # update
                    'product_uom_qty': quantity,
                    'order_id': order_id,
                    }
                data_create = { # create
                    'product_id': product_browse.id,
                    'date_deadline': date_deadline,
                    'product_uom': uom_id,
                    'name': oc_line['CDS_VARIAZ_ART'],
                    # TODO related with {}
                    'family_id': 
                        product_browse.product_tmpl_id.family_id.id 
                           if (product_browse.product_tmpl_id and 
                               product_browse.product_tmpl_id.family_id) \
                           else False,
                    'price_unit': (
                        oc_line['NPZ_UNIT'] or 0.0) * conversion,
                    'tax_id': [
                        (6, 0, [product_browse.taxes_id[0].id, ])
                        ] if product_browse and product_browse.taxes_id
                            else False, # CSG_IVA
                    'sequence': sequence,        
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
                        element[3] += data['product_uom_qty'] # counter
                        data['product_uom_maked_sync_qty'] = element[3]
                        if element[1]: # TODO not B first or error??
                            del data['product_uom_qty'] # leave prev.
                        else: # Create B line
                            element[1] = True # set line as assigned!
                        line_pool.write(
                            cr, uid, oc_line_id, data, 
                            context=context)
                            # TODO sync_state = ?
                    else: # Line not produced:              
                        data['sequence'] = sequence # only with no B line
      
                        if not element[1]: # error or B created first
                            #if abs(element[4] - quantity) < 1.0: 
                            #data["accounting_state"] = "new" # TODO serve?
                            element[1] = True # set line as assigned!

                            # Modify record:
                        line_pool.write(
                            cr, uid, oc_line_id, data, 
                            context=context)
                else: # Create record, not found: (product_id-date_deadline)
                    # Update record with value for creation:                    
                    data.update(data_create)
                    if oc_line['IST_RIGA_SOSP'] == 'B':
                        account_maked = data.get('product_uom_qty', 0.0)
                        data['product_uom_maked_sync_qty'] = account_maked
                    else:
                        account_maked = 0.0
                        
                    oc_line_id = line_pool.create(
                        cr, uid, data, context=context)
                        
                    # TODO needed?!?    
                    DB_line[key] = [oc_line_id, True, 
                        data.get('product_uom_qty', 0.0), account_maked, '']
                    # product_uom_maked_sync_qty
                    # data.get('sync_state', False), # TODO change?
            except:
                _logger.error('Problem with oc line record: %s\n%s' % (
                    oc_line, sys.exc_info()))

        # TODO testare bene gli ordini di produzione che potrebbero avere delle mancanze!
        _logger.info('End importation OC header and line!')
        return

    _columns = {
        'accounting_order': fields.boolean(
            'Accounting order',
            help='Automatic generation from importation'),
        'accounting_state': fields.selection([
            ('new', 'New'), # New
            ('production', 'Production'), # Some line are in production
            ('closed', 'Closed'), # Order delivered or deleted
            ],'Accounting state', select=True, readonly=True), 
        }

    _defaults = {
        'accounting_order': lambda *x: False,
        'accounting_state': lambda *x: 'new',
        }

class sale_order_line_extra(osv.osv):
    """ Create extra fields in sale.order.line obj
    """    
    _inherit = "sale.order.line"

    # related optimize modification function:
    def _get_new_name(self, cr, uid, ids, context=None):
        ''' Check when partner are modify the line to update
        '''
        return self.pool.get('sale.order.line').search(cr, uid, [
            ('order_id', 'in', ids)], context=context)
         
    _columns = {
        'accounting_state': fields.selection([
            ('new', 'New'),
            ('production', 'Production'), 
            ('producted', 'Producted'), 
            ('closed', 'Closed/Deleted'), 
        ],'Accounting state', select=True, readonly=True),

        # Optimize modification:
        'partner_id': fields.related('order_id', 'partner_id', type='many2one', 
            relation='res.partner', string='Partner', 
            store={'sale.order': (_get_new_name, ['partner_id'], 10)}), 
        'default_code': fields.related('product_id', 'default_code', 
            type='char', 
            string='Code', store=False), 
            
        # For production
        'mrp_production_id': fields.many2one(
            'mrp.production', 'production order', ondelete='set null'),
            
        # TODO not used, for sync
        'account_id': fields.integer('Account ID'),
        # TODO Transform in related and put in a module
        'family_id': fields.many2one(
            'product.template', 'Family', readonly=True,
            #domain=[('is_family', '=', True)],
            help='Parent family product belongs',
            ),
        }
    _defaults = {
        'accounting_state': lambda *a: 'new',
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
