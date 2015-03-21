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
    """

    _inherit = "sale.order"

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
    
    # -------------------------------------------------------------------------
    #                                 Scheduled action
    # -------------------------------------------------------------------------
    def schedule_etl_sale_order(self, cr, uid, context=None):
        """Import OC and create sale.order
        """        
        _logger.info("Start import OC header")
        query_pool = self.pool.get('micronaet.accounting')
        empty_date = query_pool.get_empty_date()
        log_info = ""

        # ---------------------------------------------------------------------
        #                                 UTILITY
        # ---------------------------------------------------------------------
        def get_oc_key(record):
            """ Compose and return key for OC
            """
            return (
                record['CSG_DOC'].strip(),
                record['NGB_SR_DOC'],
                record['NGL_DOC'],
                )

        # ---------------------------------------------------------------------
        #                               IMPORT HEADER
        # ---------------------------------------------------------------------
        # Operation for manage deletion:
        order_ids = self.search(cr, uid, [
            ('accounting_order', '=', True),
            ('accounting_state', 'not in', ('close', )),
            ], context=context)
        updated_ids = []

        # Start importation from SQL:
        import pdb; pdb.set_trace()
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
                oc_id = self.search(cr, uid, [
                    ('name', '=', name),
                    ('accounting_order', '=', True)
                    ], context=context)
                if oc_id:
                    # --------------------
                    # Update header order:
                    # --------------------
                    oc_id = oc_id[0]
                    if oc_id not in updated_ids:
                        updated_ids.append(oc_id)

                    oc_proxy = self.browse(cr, uid, oc_id, context=context)

                    # Possible error during importation:
                    #   1. partner not the same,
                    #   2. deadline changed (see in the line for value),
                    #   3. record deleted (after)
                    
                    # TODO:
                    header = {}
                    if header: # TODO not working for now, is necessary?
                        update = self.write(
                            cr, uid, oc_id, header, context=context)

                    try: # Note: the lines are removed when remove the header
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

        import pdb; pdb.set_trace()
        # Mark as closed order not present in accounting:
        # Rule: order before - order update = order to delete
        if order_ids:
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
        order_line_ids = line_pool.search(cr, uid, [
            ('order_id', 'in', updated_ids)], context=context)
        # TODO lines for order deleted?    

        # Load all OC line in openerp DB in dict
        DB_line = {}
        for ol in line_pool.browse(cr, uid, order_line_ids, context=context):
            if ol.order_id.id not in DB_line:
                DB_line[ol.order_id.id] = []

            # ---------------
            # DB Line record:
            # ---------------
            DB_line[ol.order_id.id].append([
                ol.id,                     # ID
                False,                     # finded
                ol.product_id.id,          # product_id
                ol.date_deadline,          # deadline
                ol.product_uom_qty,        # q.
                ol.product_uom_maked_qty,  # q. maked (partial prod or tot)
                ol.sync_state,             # state for production-accounting
                ], )

        # -------------------------
        # Read database order line:
        # -------------------------
        import pdb; pdb.set_trace()
        cr_oc_line = query_pool.get_oc_line(cr, uid, context=context)
        if not cr_oc_line:
            _logger.error("Cannot connect to MSSQL OC_RIGHE")
            return
            
        for oc_line in cr_oc_line:
            try:
                if oc_line['CDS_VARIAZ_ART'] == 'B':
                    continue # TODO jump B line? (only for warning check)
                oc_key = get_oc_key(oc_line)
                if oc_key not in oc_header:
                    _logger.error(
                        "Header order not found: OC-%s" % (oc_key[2]))
                    continue

                # Get product browse from code:
                product_browse = browse_product_ref(
                    self, cr, uid, oc_line['CKY_ART'].strip(), context=context)
                if not product_browse:
                    _logger.info(
                        _("No product found (OC line jumped): %s") % (
                            oc_line['CKY_ART'], ))
                    continue

                order_id = oc_header[oc_key][0]
                date_deadline = oc_line['DTT_SCAD'].strftime(
                    "%Y-%m-%d") if oc_line[
                        'DTT_SCAD'] and oc_line[
                            'DTT_SCAD'] != empty_date else False

                # NOTE this is ID of line in OC (not sequence=order)
                sequence = oc_line['NPR_RIGA']
                uom_id = product_browse.uom_id.id if product_browse else False
                conversion = (
                    oc_line['NCF_CONV'] if oc_line['NCF_CONV'] else 1.0)
                
                # pack * unit item * conversion
                quantity = (oc_line['NGB_COLLI'] or 1.0) * (
                    oc_line['NQT_RIGA_O_PLOR'] or 0.0) * 1.0 / conversion

                # Save deadline in OC header (only first time):
                if not oc_header[oc_key][1]:
                    # take the first deadline and save in header
                    if date_deadline:
                        oc_header[oc_key][1] = True
                        mod = self.write(cr, uid, order_id, {
                            'date_deadline': date_deadline}, context=context)

                # common part of record (update/create):
                data = {
                    'name': oc_line['CDS_VARIAZ_ART'],
                    'product_id': product_browse.id,
                    'product_uom_qty': quantity,
                    'product_uom': uom_id,
                    'price_unit': (oc_line['NPZ_UNIT'] or 0.0) * conversion,
                    'tax_id': [
                        (6, 0, [product_browse.taxes_id[0].id, ])
                        ] if product_browse and product_browse.taxes_id
                            else False, # CSG_IVA
                    #'production_line': True,
                    #    product_browse.supply_method == 'produce', #TODO <<<< vedere come fare a capire se è di produzione
                    #'to_produce': True,
                    'date_deadline': date_deadline,
                    'order_id': order_id,
                    'sequence': sequence, # id of row (not order field)
                    }
                
                # --------------------
                # Syncronization part:
                # --------------------
                mod = False
                if order_id in DB_line:
                    # list of all the order line in OpenERP 
                    # [ID, finded, product_id, deadline, q., maked, state]                    
                    for element in DB_line[order_id]: # All line in odoo order
                        # product and deadline
                        if (element[1] == False and
                            element[2] == product_browse.id and
                            date_deadline == element[3]):

                            #TODO if oc_line['CDS_VARIAZ_ART'] = 'B' # Susp. line
                            #    # Postulate: maked = this q!
                            
                            # Approx test:
                            #if abs(element[4] - quantity) < 1.0: # Q. different
                            data["accounting_state"] = "new"
                            element[1] = True # set this line as assigned!
                            #else:
                            #    data["accounting_state"] = "modified"

                            # Modify record:
                            oc_line_id = element[0]
                            mod = line_pool.write(
                                cr, uid, oc_line_id, data, context=context)
                            break # exit this for (no other lines as analyzed)

                if not mod: # Create record, not found: (product_id-date_deadline)
                    oc_line_id = line_pool.create(
                        cr, uid, data, context=context)

            except:
                _logger.error("Problem with oc line record: %s\n%s" % (
                    oc_line,
                    sys.exc_info()
                ))
        import pdb; pdb.set_trace()

        # TODO testare bene gli ordini di produzione che potrebbero avere delle mancanze!
        _logger.info("End importation OC header and line!")
        return

    _columns = {
        'date_deadline': fields.date('Deadline'),
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
        #'date_previous_deadline': lambda *x: False,
        #'date_delivery': lambda *x: False,
        'accounting_order': lambda *x: False,
        'accounting_state': lambda *x: 'new',
        }

class sale_order_line_extra(osv.osv):
    """ Create extra fields in sale.order.line obj
    """
    
    _inherit = "sale.order.line"

    _columns = {
        'accounting_state': fields.selection([
            ('new', 'New'),
            ('production', 'Production'), 
            ('producted', 'Producted'), 
            ('closed', 'Closed/Deleted'), 
        ],'Accounting state', select=True, readonly=True),
        'date_deadline': fields.date('Deadline'),
        
        'partner_id': fields.related('order_id','partner_id', type='many2one', 
            relation='res.partner', string='Partner', store=True), # TODO {}
        'default_code': fields.related('product_id', 'default_code', 
            type='char', 
            string='Code', store=False), 
            
        # For production
        'mrp_production_id':fields.many2one(
            'mrp.production', 'Production order', required=False,
            ondelete='set null',),
        
        #'partner_id': fields.related(
        #    'order_id','partner_id', type='many2one', relation='res.partner',
        #    string='Partner', store=True),
    }
    _defaults = {
        'accounting_state': lambda *a: 'new',
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
