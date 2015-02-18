# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) and the
#    Italian OpenERP Community (<http://www.openerp-italia.com>)
#
#    ########################################################################
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
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
from datetime import datetime, timedelta


# Constant:
EMPTY_DATA = datetime(1900,1,1,0,0,0) # '1900-01-01 00:00:00'

def get_date(value, is_datetime = False):
    ''' Return OpenERP data format 
        value: MS or My SQL data format (datetime)
        datetime: Select the format in date or datetime
    '''
    if value == EMPTY_DATA or not value:
        return False
    
    if is_datetime:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return value.strftime("%Y-%m-%d")

def get_float(value):
    ''' Return OpenERP float
        value: MS or My SQL float format
    '''
    if value:     
        return value
    return False

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
