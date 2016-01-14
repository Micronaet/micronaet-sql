# -*- encoding: utf-8 -*-
###############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) 
#    
#    Italian OpenERP Community (<http://www.openerp-italia.com>)
#
##############################################################################
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
###############################################################################
import sys
import os
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
import logging


_logger = logging.getLogger(__name__)

class ResCompany(orm.Model):
    ''' Extend res.company for agent
    '''    
    _inherit = 'res.company'
    
    _columns = {
        'sql_agent_from_code': fields.char('From agent >=', size=3), 
        'sql_agent_to_code': fields.char('To agent <', size=3), 
        }

class MicronaetAccounting(orm.Model):
    ''' Extend micronaet.accounting for agent
    '''    
    _inherit = 'micronaet.accounting'
    
    def get_partner_agent_from_commercial(self, cr, uid, context=None):
        ''' Import partner extra commercial info
            Table: PC_CONDIZIONI_COMM
        '''
        table = "pc_condizioni_comm"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)        
        try:
            cursor.execute("""
                SELECT DISTINCT CKY_CNT_AGENTE 
                FROM %s WHERE CKY_CNT != null;""" % table)
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing

class ResPartner(orm.Model):
    ''' Extend res.partner for agent
    '''    
    _inherit = 'res.partner'
    
    _columns = {
        'is_agent': fields.boolean('Is agent'),
        'sql_agent_code': fields.char('Agent code', size=10),
        'agent_id': fields.many2one('res.partner', 'Agent', 
            domain=[('is_agent', '=', True)]),
        }
    
    # -------------------------------------------------------------------------
    #                              Scheduled action
    # -------------------------------------------------------------------------    
    def schedule_sql_partner_agent_import_norange(self, cr, uid, 
            only_precence=True, verbose_log_count=100, context=None):
        ''' Import partner agent info
            Variant of original procedure for import withoun range
        '''
        try:
            return True # TODO import procedure (maybe not range for agent
            partner_proxy = self.pool.get('res.partner')
            cursor = self.pool.get(
                'micronaet.accounting').get_partner_agent_from_commercial(
                    cr, uid, context=None)
            if not cursor:
                _logger.error(
                    "Unable to connect, no importation partner agent!")
                return False

            _logger.info('Start import agent (no range)')
            i = 0
            for record in cursor:
                i += 1
                if verbose_log_count and i % verbose_log_count == 0:
                    _logger.info('Import: %s record imported / updated!' % i)                    
                try:
                    # Search code to update:
                    partner_ids = partner_proxy.search(cr, uid, [
                        ('sql_agent_code', '=', record['CKY_CNT'])])
                    if partner_ids: # update
                        partner_proxy.write(
                            cr, uid, partner_ids, {
                                'is_agent': True,
                                'sql_agent_code': record['CKY_CNT_AGENTE'],
                                'agent_id': False, 
                                }, context=context)
                    else:
                        _logger.error(
                            'Agent code not fount (jump): %s' % record[
                                'CKY_CNT_AGENTE'])

                except:
                    _logger.error(
                        'Error importing agent [%s], jumped: %s' % (
                            record['CKY_CNT'], 
                            sys.exc_info()))
                            
            _logger.info('All partner agent is updated!')
        except:
            _logger.error('Error generic import partner agent: %s' % (
                sys.exc_info(), ))
            return False
        return True

    def schedule_sql_partner_agent_import(self, cr, uid, 
            only_precence=True, verbose_log_count=100, context=None):
        ''' Import partner agent info
        '''
        try:
            return True # TODO import procedure (maybe not range for agent
            partner_proxy = self.pool.get('res.partner')
            company_pool = self.pool.get('res.company')
            company_proxy = company_pool.get_from_to_dict(
                cr, uid, context=context)
            if not company_proxy:
                _logger.error('Company parameters not setted up!')

            # Customer range
            from_code = company_proxy.sql_agent_from_code
            to_code =  company_proxy.sql_agent_to_code
            
            cursor = self.pool.get(
                'micronaet.accounting').get_partner_commercial(
                    cr, uid, from_code, to_code, context=context) 
            if not cursor:
                _logger.error(
                    "Unable to connect, no importation partner commercial list!")
                return False

            _logger.info('Start import from: %s to: %s' % (
                from_code, to_code))
            i = 0
            for record in cursor:
                i += 1
                if verbose_log_count and i % verbose_log_count == 0:
                    _logger.info('Import: %s record imported / updated!' % i)
                    
                try:                        
                    data = {
                        'is_agent': record['CKY_CNT_AGENTE'],
                        'sql_agent_code': record['CKY_CNT_AGENTE'],
                        'agent_id': False, 
                        }

                    # Search code to update:
                    partner_ids = partner_proxy.search(cr, uid, [
                        ('sql_agent_code', '=', record['CKY_CNT'])])
                    if partner_ids: # update
                        partner_proxy.write(
                            cr, uid, partner_ids, data, context=context)

                except:
                    _logger.error(
                        'Error importing agent [%s], jumped: %s' % (
                            record['CKY_CNT'], 
                            sys.exc_info())
                    )
                            
            _logger.info('All partner agent is updated!')
        except:
            _logger.error('Error generic import partner agent: %s' % (
                sys.exc_info(), ))
            return False
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
