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
from openerp.osv import osv, orm, fields
from openerp.tools.translate import _
import logging


_logger = logging.getLogger(__name__)

class res_company(orm.Model):
    ''' Extra fields for res.company object
    '''
    _name="res.company"
    _inherit="res.company"

    # Button event:
    def test_database_connection(self, cr, uid, ids, context = None):
        ''' Test if with the current configuration OpenERP can connect to database
        '''
        cursor = self.mssql_connect(cr, uid, company_id = 0, as_dict = True, context = context)
        if cursor:
            raise osv.except_osv(_('Connection test:'), _("OpenERP succesfully connected with SQL database using this parameters!"))
        else:
            raise osv.except_osv(_('Connection error:'), _("OpenERP cannot connect with SQL database using this parameters!"))
        return True

    def table_capital_name(self, cr, uid, company_id = 0, context = None):
        ''' Test if table MySQL has capital name
        '''
        try: 
            if not company_id:
                company_id = self.search(cr, uid, [], context=context)[0]
            
            company_proxy = self.browse(cr, uid, company_id, context=context)
            
            return company_proxy.capital_name
        except:
            return True
                
    def mssql_connect(self, cr, uid, company_id = 0, as_dict = True, context = None):
        ''' Connect to the ids (only one) passed and return the connection for manage DB
            ids = select company_id, if not present take the first company
        '''
        import sys

        try: # Every error return no cursor
            if not company_id:
                company_id = self.search(cr, uid, [], context=context)[0]
            
            company_proxy=self.browse(cr, uid, company_id, context=context)
            
            if company_proxy.mssql_type=='mssql':
                try:
                    import pymssql
                except:
                    _logger.error('Error no module pymssql installed!')                            
                    return False
                    
                conn = pymssql.connect(host = r"%s:%s"%(company_proxy.mssql_host, company_proxy.mssql_port), 
                                       user = company_proxy.mssql_username, 
                                       password = company_proxy.mssql_password, 
                                       database = company_proxy.mssql_database,
                                       as_dict=as_dict)

            elif company_proxy.mssql_type=='mysql':
                try:
                     import MySQLdb, MySQLdb.cursors
                except:
                    _logger.error('Error no module MySQLdb installed!')                            
                    return False
                    
                conn=MySQLdb.connect(host = company_proxy.mssql_host,
                                   user = company_proxy.mssql_username,
                                   passwd = company_proxy.mssql_password,
                                   db = company_proxy.mssql_database,
                                   cursorclass=MySQLdb.cursors.DictCursor,
                                   charset='utf8',
                                   )
            else:
                return False

            return conn #.cursor()
        except:
            return False

    _columns = {
        'mssql_host': fields.char('MS SQL server host', size=64, required=False, readonly=False, help="Host name, IP address: 10.0.0.2 or hostname: server.example.com"),
        'mssql_port': fields.integer('MS SQL server port', required=False, readonly=False, help="Host name, example: 1433 (form MSSQL), 3306 (for MySQL)"),
        'mssql_username': fields.char('MS SQL server username', size=64, required=False, readonly=False, help="User name, example: sa or root"),
        'mssql_password': fields.char('MS SQL server password', size=64, required=False, readonly=False, password=True),
        'mssql_database': fields.char('MS SQL server database name', size=64, required=False, readonly=False),
        'capital_name': fields.boolean('MS SQL capital name', help = 'If true the table has all the capital letter name'),
        'mssql_type': fields.selection([
            ('mysql','MySQL'),
            ('mssql','MS SQL Server'),            
        ],'Type', select=True,),
        # add fields.many2many for recipient for notification
    }    
    _defaults = {
        'mssql_port': lambda *a: 3306,
        'mssql_type': lambda *a: 'mysql',
        'capital_name': lambda *a: True,
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
