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

class product_product(orm.Model):
    _name = 'product.product'
    _inherit = 'product.product'
    
    _columns = {
        'not_analysis': fields.boolean('Not in analysis', required=False),
    }
    _defaults = {
        'not_analysis': lambda *a: False,
    }
    
class micronaet_accounting(orm.Model):
    ''' Object for keep function with the query
        Record are only table with last date of access
    '''
    _name = "micronaet.accounting"
    _description = "Micronaet accounting"

    # Format parameters (for keys):   # TODO: test when year change:
    KEY_MM_HEADER_FORMAT = "%(CSG_DOC)s%(NGB_SR_DOC)s:" + \
        datetime.now().strftime("%y") + "-%(NGL_DOC)s"
    KEY_MM_LINE_FORMAT = "%(CSG_DOC)s%(NGB_SR_DOC)s:" + \
        datetime.now().strftime("%y") + \
        "-%(NGL_DOC)s[%(NPR_DOC)s.%(NPR_RIGA_ART)s]"

    KEY_OC_LINE_FORMAT = "%(CSG_DOC)s%(NGB_SR_DOC)s:" + \
        datetime.now().strftime("%y") + "-%(NGL_DOC)s[%(NPR_RIGA)s]"
    KEY_OC_FORMAT = "%(CSG_DOC)s%(NGB_SR_DOC)s:" + \
        datetime.now().strftime("%y") + "-%(NGL_DOC)s"

    #def get_mask(self, cr, uid, mask_name):
    #    ''' Return mask element configuring year value
    #    '''
    #    mask = self.get(mask_name)
        
    # -----------------
    # Utility function:
    # -----------------
    def connect(self, cr, uid, context=None):
        ''' Connect action for link to MSSQL DB
        '''
        try:
            connection = self.pool.get('res.company').mssql_connect(
                cr, uid, context=context)  # first company
            cursor=connection.cursor()
            if not cursor: 
                _logger.error("Can't access in Company MSSQL Database!")
                return False
            return cursor
        except:
            _logger.error("Executing connect: [%s]" % (
                sys.exc_info(), ))
            return False    

    def no_date(self, data_value):
        ''' Test for empty date
            Accounting program use 01/01/1900 for no date
        '''
        from datetime import datetime
        return data_value == datetime.strptime("1900-01-01", "%Y-%m-%d")

    def get_empty_date(self):
        ''' Return datetime object for empty date
            Mexal use 01/01/1900 for no date
        '''
        from datetime import datetime
        
        return datetime.strptime("1900-01-01", "%Y-%m-%d")
           
    # -------------------------------------------------------------------------   
    #                             Table access method
    # -------------------------------------------------------------------------   
    # -----------
    #  PAYMENTS -
    # -----------
    def get_payment(self, cr, uid, context=None):
        ''' Access to anagrafic table of payments
            Table: CP_PAGAMENTI
        '''
        table = "cp_pagamenti"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)
        try:#                        ID       Description
            cursor.execute("""SELECT NKY_PAG, CDS_PAG FROM %s;""" % table)
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing

    def get_payment_partner(self, cr, uid, context=None):
        ''' Access to anagrafic partner link to table of payments
            Table: PC_CONDIZIONI_COMM
            (only record with payment setted up)
        '''
        table = "pc_condizioni_comm"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor=self.connect(cr, uid, context=context)
        try:#                        ID       Description
            cursor.execute("""
                SELECT 
                    CKY_CNT, NKY_PAG 
                FROM %s 
                WHERE NKY_PAG>0;""" % table)
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing

    # ----------
    #  PARTNER -
    # ---------
    def get_partner(self, cr, uid, from_code, to_code, write_date_from=False, 
            write_date_to=False, create_date_from=False, create_date_to=False, 
            context=None):
        ''' Import partner, customer or supplier, depend on from to code passed
            Table: PA_RUBR_PDC_CLFR
            Extra where clause: from_code, to_code, write from/to,
            create from/to
        '''
        table = "pa_rubr_pdc_clfr"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()
            
        cursor=self.connect(cr, uid, context=context)
        
        # Compose where clause:
        where_clause = ""
        if from_code: 
            where_clause += "%s CKY_CNT >= '%s' " % (
                "AND" if where_clause else "", from_code)
        if to_code: 
            where_clause += "%s CKY_CNT < '%s' " % (
                "AND" if where_clause else "", to_code)
            
        if create_date_from:
            where_clause += "%s DTT_CRE >= '%s' " % (
                "AND" if where_clause else "", create_date_from)
        if create_date_to:
            where_clause += "%s DTT_CRE <= '%s' " % (
                "AND" if where_clause else "", create_date_to)
            
        if write_date_from:
            where_clause += "%s DTT_AGG_ANAG >= '%s' " % (
                "AND" if where_clause else "", write_date_from)
        if write_date_to:
            where_clause += "%s DTT_AGG_ANAG <= '%s' " % (
                "AND" if where_clause else "", write_date_to)

        try:
            cursor.execute(
                """
                SELECT 
                    CKY_CNT, CDS_CNT, CDS_RAGSOC_COGN, CDS_INDIR, CDS_CAP, 
                    CDS_LOC, CDS_PROV, CDS_TEL_TELEX, CSG_CFIS, CSG_PIVA, 
                    CDS_FAX, CDS_INET, CKY_PAESE, CDS_URL_INET, IST_NAZ
                FROM %s %s;""" % (
                    table, 
                    "WHERE %s" % (where_clause) if where_clause else "")
            )
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing

    def get_partner_commercial(self, cr, uid, from_code, to_code, 
            context=None):
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
                SELECT * 
                FROM %s WHERE CKY_CNT >= %s and CKY_CNT < %s;""" % (
                    table,
                    from_code,
                    to_code, 
            ))
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing

    def get_parent_partner(self, cr, uid, context=None):
        ''' Parent partner code for destination
            Table: PC_CONDIZIONI_COMM
        '''
        table = "pc_condizioni_comm"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)
        try:
            cursor.execute("""
                SELECT CKY_CNT, CKY_CNT_CLI_FATT 
                FROM %s 
                WHERE CKY_CNT_CLI_FATT != '';""" % table)
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False

    # -----------
    #  PRODUCTS -
    # -----------
    def is_active(self, record):
        ''' Test if record passed is an active product
        '''
        return record['IFL_ART_CANC'] == 'N' and record['IFL_ART_ANN'] == 'N'
        
    def get_product(self, cr, uid, active=True, write_date_from=False, 
            write_date_to=False, create_date_from=False, create_date_to=False, 
            context=None):
        ''' Access to anagrafic table of product and return dictionary read
            only active product
            Table: AR_ANAGRAFICHE
            Where clause: active, from_date, to_date
        '''
        table = "ar_anagrafiche"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context = context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)
        
        # Compose where clause:
        where_clause = ""
        if active: 
            where_clause += "%s IFL_ART_CANC='N' AND IFL_ART_ANN='N' " % (
                "AND" if where_clause else "")
            
        if create_date_from:
            where_clause += "%s DTT_CRE >= '%s' " % (
                "AND" if where_clause else "", create_date_from)
        if create_date_to:
            where_clause += "%s DTT_CRE <= '%s' " % (
                "AND" if where_clause else "", create_date_to)
            
        if write_date_from:
            where_clause += "%s DTT_AGG_ANAG >= '%s' " % (
                "AND" if where_clause else "", write_date_from)
        if write_date_to:
            where_clause += "%s DTT_AGG_ANAG <= '%s' " % (
                "AND" if where_clause else "", write_date_to)

        try:
            cursor.execute(
                """SELECT 
                        CKY_ART, IST_ART, CDS_ART, CSG_ART_ALT, CSG_UNIMIS_PRI, 
                        NMP_COSTD, CDS_AGGIUN_ART, NMP_UCA, IFL_ART_DBP, 
                        IFL_ART_CANC, IFL_ART_ANN, CKY_CAT_STAT_ART, 
                        NKY_CAT_STAT_ART, CKY_CNT_FOR_AB,
                        NKY_STRUTT_ART, DTT_CRE 
                   FROM %s %s;""" % (
                       table, 
                       "WHERE %s" % (where_clause) if where_clause else "")
            )
            
            # NOTE: TAX: AR_CONDIZIONI_COMM
            return cursor # with the query setted up                  
        except:
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing
    
    def get_product_language(self, cr, uid, lang_code, context=None):
        ''' Return list of term in lang_code passed
            Table: ah_des_art_lingua
        '''
        table = "ah_des_art_lingua"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()
        
        cursor = self.connect(cr, uid, context=context)
        try:
            cursor.execute("""
                SELECT CKY_ART, NKY_LIN, CDS_ART_LIN 
                FROM %s 
                WHERE 
                    NKY_LIN = '%s';""" % (
                    table, lang_code))
            return cursor
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False

    def get_product_quantity(self, cr, uid, store, year, context=None):
        ''' Return quantity element for product
            Table: AQ_QUANTITA
            CKY_ART NKY_DEP NDT_ANNO NQT_INV NQT_CAR NQT_SCAR 
            NQT_ORD_FOR NQT_ORD_CLI NQT_SOSP_CLI NQT_CLI_AUT NQT_INPR  
        '''
        table = "aq_quantita"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()
        
        cursor=self.connect(cr, uid, context=context)
        try:#                        Code     Inv      Car      Scar
            cursor.execute("""SELECT CKY_ART, NQT_INV, NQT_CAR, NQT_SCAR,
                                     NQT_ORD_FOR, NQT_ORD_CLI,
                                     NQT_SOSP_CLI, NQT_CLI_AUT, NQT_INPR
                              FROM %s
                              WHERE NKY_DEP=%s and NDT_ANNO=%s;""" % (
                                  table, store, year))
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing

    def get_product_price(self, cr, uid, context=None):
        ''' Return price table 
            Table: AR_PREZZI
        '''
        table = "ar_prezzi"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()
        
        cursor = self.connect(cr, uid, context=context)
        try:
            cursor.execute("""SELECT *
                              FROM %s;""" % (table, ))
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing

    def get_product_package(self, cr, uid, context=None):
        ''' Return quantity per package for product
            Table: AR_VAWC_PEROINKGPE
                   Extra table (not present in all installations)            
        '''        
        table = "ar_vawc_pesoinkgpe"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)
        try:#                        
            cursor.execute("""SELECT * FROM %s; """ % (table, ))
            return cursor 
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  
            
    def get_product_package_columns(self, cr, uid, context=None):
        ''' Return list of columns for table (used for get package code: 
                NGD_* where * is the CODE)
            Table: AR_VAWC_PEROINKGPE
                   Extra table (not present in all installations)            
        '''        
        table = "ar_vawc_pesoinkgpe"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor=self.connect(cr, uid, context=context)
        try:#                        
            cursor.execute("""
                SELECT 
                    COLUMN_NAME 
                FROM 
                    INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='dbmirror' 
                    AND TABLE_NAME='%s' AND COLUMN_NAME like 'NGD_%s';""" % (
                        table, "%")) 
            return cursor 
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  

    def get_product_level(self, cr, uid, store=1, context=None):
        ''' Access to anagrafic table of product and return dictionary read
            only active product (level for 
            Table: AB_UBICAZIONI
            @store: store dep. (every order level depend on the store chosen)
        '''
        table = "ab_ubicazioni"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor=self.connect(cr, uid, context=context)
        try:
            cursor.execute("""
                SELECT 
                    CKY_ART, NQT_SCORTA_MIN, NQT_SCORTA_MAX
                FROM 
                    %s %s;""" % (table, "WHERE NKY_DEP=%s" % (store, )))
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing

    # --------------------
    #  SUPPLIER ORDER OF -
    # --------------------
    def get_of_line_quantity_deadline(self, cr, uid, context=None):
        ''' Return quantity element for product
            Table: OF_RIGHE
        '''        
        table = "of_righe"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)
        try:
            cursor.execute("""
                SELECT 
                    NPR_RIGA, CKY_ART, DTT_SCAD, NGB_TIPO_QTA, 
                    NQT_RIGA_O_PLOR, NCF_CONV
                FROM %s;""" % (table, ))
            # Sort: NGL_DOC, NPR_SORT_RIGA                 
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing    

    # -------------------
    # CUSTOMER ORDER OC -
    # -------------------
    def get_oc_header(self, cr, uid, context=None):
        ''' Return list of OC order (header)
            Table: OC_TESTATE
        '''        
        table = "oc_testate"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context = context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)
        try:
            cursor.execute("""
                SELECT 
                    CSG_DOC, NGB_SR_DOC, NGL_DOC, DTT_DOC, CKY_CNT_CLFR, 
                    CKY_CNT_SPED_ALT, CKY_CNT_AGENTE, CKY_CNT_VETT, IST_PORTO, 
                    CDS_NOTE
                FROM %s;""" % table)
            return cursor # with the query setted up
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing    
        
    def get_oc_line(self, cr, uid, context=None):
        ''' Return quantity element for product
            Table: OC_RIGHE
        '''        
        table = "oc_righe"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor = self.connect(cr, uid, context=context)
        try:
            cursor.execute("""
                SELECT 
                    CSG_DOC, NGB_SR_DOC, NGL_DOC, NPR_RIGA, DTT_SCAD, CKY_ART, 
                    NGB_TIPO_QTA, NQT_RIGA_O_PLOR, NPR_SORT_RIGA, NCF_CONV, 
                    NPZ_UNIT, CDS_VARIAZ_ART, IST_RIGA_SOSP, NGB_COLLI
                FROM %s;""" % (table, ))
            # no: NPZ_UNIT, NGL_RIF_RIGA, NPR_SORT_RIGA, NKY_CAUM, NKY_DEP
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing    

    def get_oc_funz_line(self, cr, uid, context=None):
        ''' Object for extra data in OC line
            Table: OC_FUNZ_RIGHE
        '''        
        table = "oc_funz_righe"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        cursor=self.connect(cr, uid, context=context)
        try:
            cursor.execute("""
                SELECT 
                    NGB_SR_DOC, CSG_DOC, NGL_DOC, NPR_RIGA, NQT_MOVM_UM1, 
                    NMP_VALMOV_UM1, NGB_COLLI, NMP_PROVV_VLT
                FROM %s;""" % table)
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing    

    # ----------------
    #  MOVEMENT LINE -
    # ----------------
    def get_mm_header(self, cr, uid, where_document=None, context=None):
        ''' Return list of OC order (header)
            Table: MM_TESTATE
        '''    
        table = "mm_testate"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        if where_document is None:
            where_document = ()
        elif type(where_document) not in (list, tuple):     # single string
            where_document = (where_document, )
        else:
            where_document = tuple(where_document)            
            
        cursor = self.connect(cr, uid, context=context)
        query = """
            SELECT CSG_DOC, NGB_SR_DOC, NGL_DOC, NPR_DOC, CKY_CNT_CLFR, 
                DTT_DOC, CSG_DOC_ORI, NGB_SR_DOC_ORI, NGL_DOC_ORI, DTT_DOC_ORI,                                      
                CKY_CNT_SPED_ALT, NGB_CASTAT_CLIFOR, CDS_NOTE
            FROM %s%s;""" % (
                table,
                " WHERE CSG_DOC in %s" % (
                    where_document, ) if where_document else "")
        # VERY BAD!!! for remove , in list of documents
        query = query.replace(",);", ");") 
        try: 
            cursor.execute(query)
            return cursor # with the query setted up
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing    
        
    def get_mm_line(self, cr, uid, where_document=None, context=None):
        ''' Return quantity element for product
            Table: MM_RIGHE
            
            @where_document: ref of document for where clause (ex. BS)
        '''        
        query = "Not loaded"
        table = "mm_righe"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        if where_document is None:
            where_document = ()
        elif type(where_document) not in (list, tuple):     # single string
            where_document = (where_document, )
        else:
            where_document = tuple(where_document)            
            
        cursor=self.connect(cr, uid, context=context)
        query = """
            SELECT CSG_DOC, NGB_SR_DOC, NGL_DOC, NPR_DOC, CKY_CNT_CLFR, 
            NPR_RIGA_ART, CKY_ART, NPZ_UNIT, NDC_QTA, 
            CDS_VARIAB_ART, DTT_SCAD
            FROM %s%s;""" % (
                table, 
                " WHERE CSG_DOC in %s" % (
                    where_document, ) if where_document else "")
        # BAD!!! for remove , in list of documents                    
        query = query.replace(",);", ");") 
        try:             
            cursor.execute(query)
            return cursor # with the query setted up                  
        except: 
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False

    def get_mm_funz_line(self, cr, uid, where_document=None, context=None):
        ''' Return quantity element for product funz
            Table: MM_FUNZ_RIGHE
        '''        
        table = "mm_funz_righe"
        if self.pool.get('res.company').table_capital_name(
                cr, uid, context=context):
            table = table.upper()

        if where_document is None:
            where_document = ()
        elif type(where_document) not in (list, tuple):     # single string
            where_document = (where_document, )
        else:
            where_document = tuple(where_document)

        cursor=self.connect(cr, uid, context=context)
        query = """
                SELECT CSG_DOC, NGB_SR_DOC, NGL_DOC, NPR_DOC, CKY_CNT_CLFR, 
                NPR_RIGA_ART, NQT_MOVM_UM1, NMP_VALMOV_UM1
                FROM %s%s;""" % (
                    table,
                    " WHERE CSG_DOC in %s" % (
                        where_document, ) if where_document else "", )                    
        # BAD!!! for remove , in list of documents                
        query = query.replace(",);", ");") 
        try: #                       
            cursor.execute(query)
            return cursor # with the query setted up                  
        except:
            _logger.error("Executing query %s: [%s]" % (
                table,
                sys.exc_info(), ))
            return False  # Error return nothing
        
    _columns = {
        'name':fields.char(
            'SQL table', size=80, required=True, readonly=False,),
        'datetime': fields.datetime('Last read'),
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
