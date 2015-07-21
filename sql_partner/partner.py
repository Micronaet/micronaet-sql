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

class res_company(orm.Model):
    ''' Extra fields for setup the module
    '''

    _inherit = 'res.company'
    
    def get_from_to_dict(self, cr, uid, context=None):
        ''' Return a company proxy for get from to clause
        '''        
        company_id = self.search(cr, uid, [], context = context)
        if not company_id:
            return False
        return self.browse(cr, uid, company_id, context = context)[0]
        
    _columns = {
        'sql_supplier_from_code': fields.char(
            'SQL supplier from code >=', size=10, required=False, 
            readonly=False),
        'sql_supplier_to_code': fields.char(
            'SQL supplier from code <', size=10, required=False, 
            readonly=False),
        'sql_customer_from_code': fields.char(
            'SQL customer from code >=', size=10, required=False, 
            readonly=False),
        'sql_customer_to_code': fields.char(
            'SQL customer from code <', size=10, required=False, 
            readonly=False),
        'sql_destination_from_code': fields.char(
            'SQL destination from code >=', size=10, required=False, 
            readonly=False),
        'sql_destination_to_code': fields.char(
            'SQL destination from code <', size=10, required=False, 
            readonly=False),
    }

class account_fiscal_position(orm.Model):
    ''' Link for fiscal position (accounting)
    '''    
    
    _inherit = 'account.fiscal.position'
    
    _columns = {
        'account_CEI': fields.char('Italy, CEE, Extra CEE', size=1), 
        }
    
    

class res_partner(orm.Model):
    ''' Extend res.partner
    '''    
    _inherit = 'res.partner'
    
    # -------------------------------------------------------------------------
    #                                 Utility
    # -------------------------------------------------------------------------
    def get_partner_from_sql_code(self, cr, uid, code, context=None):
        ''' Return partner_id read from the import code passed
            (search in customer, supplier, destiantion)
        '''
        
        partner_id = self.search(cr, uid, ['|', '|',
            ('sql_supplier_code', '=', code),
            ('sql_customer_code','=', code),
            ('sql_destination_code', '=', code),
            ])
            
        if partner_id:
            return partner_id[0]
        return False

    # -------------------------------------------------------------------------
    #                             Scheduled action
    # -------------------------------------------------------------------------
    def schedule_sql_partner_import(self, cr, uid, verbose_log_count=100, 
            capital=True, write_date_from=False, write_date_to=False, 
            create_date_from=False, create_date_to=False, sync_vat=False,
            address_link=False, only_block=False, dest_merged=False, 
            context=None):
        ''' Import partner from external DB
        
            verbose_log_count: number of record for verbose log (0 = nothing)
            write_date_to: sync only modify element from
            write_date_from: sync only modify element to
            create_date_from: sync only create element from
            create_date_to: sync only create element to
            sync_vat: Merge supplier with partner if vat was fount
            capital: if table has capital letters (usually with mysql in win)
            address_link: partner has address (module to be installed)
            only_block: 'destination', 'customer', 'supplier'
            dest_merged: if destination has same code of customer / supplier
        '''

        sql_pool = self.pool.get('micronaet.accounting')

        # TODO Load account.fiscal.position with CEI fields
        # 2. Read dict or try to set up link automatically
        # 3. Load dict for associate fields in creation
        
        # Load country for get ID from code
        country_pool = self.pool.get('res.country')
        countries = {}
        country_ids = country_pool.search(cr, uid, [], context=context)
        country_proxy = country_pool.browse(
            cr, uid, country_ids, context=context)
        for item in country_proxy:
            countries[item.code] = item.id
            
        try:
            _logger.info('Start import SQL: customer, supplier, destination')
            company_pool = self.pool.get('res.company')
            company_proxy = company_pool.get_from_to_dict(
                cr, uid, context=context)
            if not company_proxy:
                _logger.error('Company parameters not setted up!')

            import_loop = [
                (1,                                     # order
                'sql_customer_code',                    # key field
                company_proxy.sql_customer_from_code,   # form_code
                company_proxy.sql_customer_to_code,     # to_code
                'customer'),                            # type
                
                (2,
                'sql_supplier_code', 
                company_proxy.sql_supplier_from_code, 
                company_proxy.sql_supplier_to_code, 
                'supplier'),
                
                (3,
                'sql_destination_code', 
                company_proxy.sql_destination_from_code, 
                company_proxy.sql_destination_to_code,
                'destination'),
                ]
            if dest_merged: # dest has same code of customer or supplier
                import_loop.extend([        
                    # Extra step for customer destination:               
                    (4,
                    'sql_destination_code', 
                    company_proxy.sql_customer_from_code, 
                    company_proxy.sql_customer_to_code,
                    'customer_destination'),
                     
                    # Extra step for supplier destination:               
                    #(5,
                    #'sql_destination_code', 
                    #company_proxy.sql_supplier_from_code, 
                    #company_proxy.sql_supplier_to_code,
                    #'supplier_destination'),                     
                    ])
                    
            # -----------------------------------------------------------------
            # Add parent for destination in required:
            # -----------------------------------------------------------------
            # For link destination speedly:
            parents = {}
            destination_parents = {}                 
            if address_link:
                _logger.info('Read parent for destinations')
                cursor = sql_pool.get_parent_partner(cr, uid, context=context)
                if not cursor:
                    _logger.error("Unable to connect to parent (destination)!")
                else:
                    for record in cursor:
                        destination_parents[record['CKY_CNT']] = record[
                            'CKY_CNT_CLI_FATT']

            for order, key_field, from_code, to_code, block in import_loop:
                # If same from/to code or jump function enabled
                if (only_block and only_block != block) or (
                        from_code == to_code):
                    _logger.warning("Jump block: %s!" % block)
                    continue

                cursor = sql_pool.get_partner(
                    cr, uid, from_code=from_code, to_code=to_code, 
                    write_date_from=write_date_from, 
                    write_date_to=write_date_to, 
                    create_date_from=create_date_from, 
                    create_date_to=create_date_to, 
                    context=context) 
                if not cursor:
                    _logger.error("Unable to connect, no partner!")
                    continue # next block

                _logger.info('Start import %s from: %s to: %s' % (
                    block, from_code, to_code))                          
                i = 0
                for record in cursor:
                    i += 1
                    if verbose_log_count and i % verbose_log_count == 0:
                        _logger.info('%s: %s record imported / updated!' % (
                            block, i))                             
                        
                    try:
                        ref = record['CKY_CNT']
                        
                        # Cust / Supp not destination
                        if block in ('customer', 'supplier') and (
                                ref in destination_parents): 
                            # will be written in extra bloc
                            continue
                        # Destination with parent found    
                        if 'destination' in block and (
                                ref not in destination_parents): 
                            if block == 'destination':    
                                _logger.error('Dest. without parent %s' % key)
                            continue

                        data = {
                            key_field: ref,
                            'name': record['CDS_CNT'],
                            'sql_import': True,
                            'is_company': True,
                            'street': record['CDS_INDIR'] or False,
                            'city': record['CDS_LOC'] or False,
                            'zip': record['CDS_CAP'] or False,
                            'phone': record['CDS_TEL_TELEX'] or False,
                            'email': record['CDS_INET'] or False,
                            'fax': record['CDS_FAX'] or False,
                            #'mobile': record['CDS_INDIR'] or False,
                            'website': record['CDS_URL_INET'] or False,
                            'vat': record['CSG_PIVA'] or False,
                            'country_id': countries.get(record[
                                'CKY_PAESE'], False),
                            }
                            
                        domain = [(key_field, '=', ref)]
                        # Customer not destination:                        
                        if block == 'customer': 
                            data['customer'] = True
                            data['type'] = 'default'
                            data['ref'] = ref

                        # Supplier not destination:
                        elif block == 'supplier': 
                            data['supplier'] = True
                            data['type'] = 'default'

                        # Destination or cust/supp destination (parent pres.)
                        elif address_link: # and ref in destination_parents:
                            data['type'] = 'delivery'
                            data['is_address'] = True
                            
                            parent_code = destination_parents[ref]
                            if parent_code:
                                # as customer / supplier are loaded before:
                                data['parent_id'] = parents.get(
                                    parent_code, False)
                                    
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
                            # TODO when we are here?
                            #_logger.error(
                            #    'Destination: %s without parent code' % ref)
                            continue

                        partner_ids = self.search(
                            cr, uid, domain, context=context)

                        # Search per vat (only for customer and supplier)
                        if sync_vat and not partner_ids and block in (
                                'customer', 'supplier'): 
                            partner_ids = self.search(cr, uid, [
                                ('vat', '=', record['CSG_PIVA'])])

                        if len(partner_ids) > 1:
                            _logger.warning(
                                'Found more than one key: %s (%s)' % (
                                    ref, len(partner_ids)))

                        # -----------------------------------------------------
                        # Update / Create
                        # -----------------------------------------------------
                        if partner_ids:
                            try:
                                partner_id = partner_ids[0]
                                self.write(cr, uid, partner_id, data, 
                                    context=context)
                            except:
                                del(data['vat'])
                                try: # Remove vat for vat check problems:
                                    self.write(cr, uid, partner_id, data, 
                                        context=context)
                                except:    
                                    _logger.error(
                                        '%s. Error update partner [%s]: %s' % (
                                            i, partner_id, sys.exc_info()))
                                    continue
                        else:
                            try:
                                partner_id = self.create(
                                    cr, uid, data, context=context)
                            except:
                                del(data['vat'])
                                try: # Remove vat for vat check problems:
                                    partner_id = self.create(cr, uid, data, 
                                        context=context)
                                except:    
                                    _logger.error(
                                        '%s. Error create partner [%s]: %s' % (
                                            i, partner_id, sys.exc_info()))
                                    continue

                        # Save referente for destination:
                        if address_link and 'destination' not in block:
                            parents[ref] = partner_id

                    except:
                        _logger.error(
                            'Error importing partner [%s], jumped: %s' % (
                                ref, sys.exc_info()))
                                            
                _logger.info('All %s is updated!' % block)
        except:
            _logger.error('Error generic import partner: %s' % (
                sys.exc_info(), ))
            return False
        return True

    # -------------------------------------------------------------------------
    #                                 Columns
    # -------------------------------------------------------------------------
    _columns = {
        'sql_import': fields.boolean('SQL import'),
        'sql_supplier_code': fields.char('SQL supplier code', size=10),
        'sql_customer_code': fields.char('SQL customer code', size=10),
        'sql_destination_code': fields.char('SQL destination code', size=10),
        'account_CEI': fields.char('Italy, CEE, Extra CEE', size=1),
        }
    
    _defaults = {
        'sql_import': lambda *a: False,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
