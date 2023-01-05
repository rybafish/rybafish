from hdbcli.dbapi import ProgrammingError
from hdbcli.dbapi import DatabaseError
from hdbcli import dbapi

import time
from _constants import build_date, version

import kpiDescriptions
import sql
import sys

from utils import cfg, hextostr
from utils import getlog
from dbi_extention import getDBProperties
from os import getlogin
from profiler import profiler

import re
from utils import dbException

log = getlog('HDB')


class hdbi ():
    name = 'HDBCLI'
    options = {'keepalive': True, 'largeSQL': True}

    def __init__(self):
        log('Using HDBCLI as DB driver implementation')
        self._resultset_id_list = None
            
    def create_connection (self, server, dbProperties = None):
        t0 = time.time()
        
        try: 
            if server.get('ssl'):
                log('Opening regular connection (ssl)', 4)
                connection = dbapi.connect(address=server['host'], port=server['port'], user=server['user'], password=server['password'], encrypt = True, ValidateServerCertificate = False, compress = True)
            elif server.get('ssl') and server['user'] == '' and server['password'] == '':
                log('Opening LDAP connection (ssl)', 5)
                connection = dbapi.connect(address=server['host'], port=server['port'], encrypt = True, ValidateServerCertificate = False, authenticationMethods='ldap', compress = True)
            elif server['user'] == '' and server['password'] == '':
                log('Opening LDAP connection (no ssl)', 5)
                connection = dbapi.connect(address=server['host'], port=server['port'], authenticationMethods='ldap', compress = True)
            else:
                log('Opening regular connection (no ssl)', 5)
                connection = dbapi.connect(address=server['host'], port=server['port'], user=server['user'], password=server['password'], compress = True)
            
            if cfg('internal', True):
                setApp = "set 'APPLICATION' = 'RybaFish %s'" % version
                self.execute_query_desc(connection, setApp, [], 0)
                
                setApp = "set 'APPLICATIONUSER' = '%s'" % getlogin()
                self.execute_query_desc(connection, setApp, [], 0)

        except Exception as e:
            log('[!]: connection failed: %s\n' % e)
            connection = None
            raise DatabaseError(str(e))

        t1 = time.time()
        
        getDBProperties(connection, self.execute_query, log, dbProperties)
        
        t2 = time.time()
        
        log('(re)connect/properties: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))
        
        return connection
    
    def execute_query_desc(self, connection, sql_string, params, resultSize, noLogging=False):    
        '''
            The method mainly used by SQL console because it also needs a result set description.
            
            additionaly it is use in Gantt customKPIs because of the dynamic number of return columns 
            
            It also used a modified version of the pyhdb cursor implementation because of the https://github.com/rybafish/rybafish/issues/97
            
        Return structure
            The call returns:
            rows_list - list of 2-dimentional arrays of results sets, see below
            cols_list - list (of lists) of descriptions, see below
            cursor - cursor might be used for some additional interaction with the db layer, extract list of result set ids...
            psid - statement id to be used in...
            
            the interface supports multiple result sets this is why rows_list and columns_list are double-layered
            in case of single resultset, i.e. select 1 a, 2 b, 3 c from dumy)
            
            row_list = [                # first resultset
                    [1, 2 , 3]          # row itself
            ]
            col_list = [                # first resultset
                ['A', <int>],           # first column named A, type - integer
                ['B', <int>],           # ...
                ['C', <int>]
            ]
            
            top level of both lists has the same number of elements (resultsets)
        '''

        if not connection:
            log('no db connection...')
            return

        cursor = connection.cursor()
        
        if not noLogging:
            log('[SQL]: %s' % sql_string, 5)

            if len(params) > 0:
                log('[PRMS]: %s' % str(params), 5)

        try:
            psid = cursor.prepare(sql_string)
        except BaseException as e:
        
            log('DatabaseError: ' + str(e.errorcode))
        
            if str(e).startswith('Lost connection to HANA server'):
                raise DatabaseError(str(e))
        
            log('[!] SQL Error: %s' % sql_string)
            log('[!] SQL Error: %s' % (e))
            
            raise dbException(str(e.errortext))
        except Exception as e:
            log("[!] unexpected DB exception, sql: %s" % sql_string)
            log("[!] unexpected DB exception: %s" % str(e))
            log("[!] unexpected DB exception: %s" % sys.exc_info()[0])
            raise dbException(str(e))
            
            
        try:
            cursor.executeprepared((params))
            columns_list = cursor.fetchall
            
            rows_list = []
            columns_list = []
            try:
                if re.match("SELECT.{1,}", sql_string.upper()):
                    if resultSize is not None:
                        rows = cursor.fetchmany(resultSize)
                    else:
                        rows = cursor.fetchall()
                    columns_list.append(cursor.description)
                    rows_list.append(rows)

                if re.match("SET.{1,}", sql_string.upper()) or re.match("CREATE.{1,}", sql_string.upper())  or re.match("DROP.{1,}", sql_string.upper()) or re.match("ALTER.{1,}", sql_string.upper()):
                    log('that was a ddl...', 4)
                    rows_list = None
                    columns_list = None
            except ProgrammingError as e:
                log(e, 4)

        except BaseException as e:
            log('[!] sql execution issue: %s\n' % e)
            raise DatabaseError(str(e))
        except Exception as e:
            log('[E] unexpected DB error: %s' % str(e))
            raise DatabaseError(str(e))
            
        return rows_list, columns_list,None, None

    
    def execute_query(self, connection, sql_string, params):

        if not connection:
            log('no db connection...')
            return

        # prepare the statement...

        log('[SQL]: %s' % sql_string, 5)
        
        if len(params) > 0:
            log('[PRMS]: %s' % str(params), 5)

        try:
            cursor = connection.cursor()
            
            psid = cursor.prepare(sql_string)
        except DatabaseError as e:
        
            log('[!] SQL Error: %s' % sql_string[0:256])
            log('[!] SQL Error: %s' % (e))

            if str(e).startswith('Lost connection to HANA server'):
                log('[!] SQL Error: related to connection')
                raise dbException(str(e))
            
            raise dbException(str(e))
        except Exception as e:
            log("[!] unexpected DB exception, sql: %s" % sql_string)
            log("[!] unexpected DB exception: %s" % str(e))
            log("[!] unexpected DB exception: %s" % sys.exc_info()[0])
            raise dbException(str(e))
            
        try:

            cursor.executeprepared((params))
            
            rows = cursor.fetchall()

        except DatabaseError as e:
            log('[!] sql execution issue: %s\n' % e)
            raise DatabaseError(str(e))
        except Exception as e:
            log('[E] unexpected error: %s' % str(e))
            raise DatabaseError(str(e))

        return rows

    def checkTable(self, conn, tableName):
        r = self.execute_query(conn, f"select table_name from tables where schema_name = session_user and table_name = ?", [tableName])
        
        if r:
            return True
        else:
            return False

    
    def console_connection(self, server, dbProperties = None, data_format_version2 = False):

        longdate = cfg('longdate', True)

        t0 = time.time()
        
        sslsupport = server.get('ssl')
        
        try: 
            log(f'Regular consolse, longdate={longdate}, ssl={sslsupport}')
            if server.get('ssl'):
                log('Opening regular connection (ssl)', 4)
                connection = dbapi.connect(address=server['host'], port=server['port'], user=server['user'], password=server['password'], encrypt = True, ValidateServerCertificate = False, compress = True)
            elif server.get('ssl') and server['user'] == '' and server['password'] == '':
                log('Opening LDAP connection (ssl)', 5)
                connection = dbapi.connect(address=server['host'], port=server['port'], encrypt = True, ValidateServerCertificate = False, authenticationMethods='ldap', compress = True)
            elif server['user'] == '' and server['password'] == '':
                log('Opening LDAP connection (no ssl)', 5)
                connection = dbapi.connect(address=server['host'], port=server['port'], authenticationMethods='ldap', compress = True)
            else:
                log('Opening regular connection (no ssl)', 5)
                connection = dbapi.connect(address=server['host'], port=server['port'], user=server['user'], password=server['password'], compress = True)

                
            if cfg('internal', True):
                setApp = "set 'APPLICATION' = 'RybaFish %s'" % version
                self.execute_query_desc(connection, setApp, [], 0)
                
                setApp = "set 'APPLICATIONUSER' = '%s'" % getlogin()
                self.execute_query_desc(connection, setApp, [], 0)
            
        except Exception as e:
    #    except pyhdb.exceptions.DatabaseError as e:
            log('[!]: connection failed: %s\n' % e)
            connection = None
            raise DatabaseError(str(e))

        t1 = time.time()
        
        log('sql (re)connect: %s' % (str(round(t1-t0, 3))))
        
        return connection

    def get_connection_id(self, conn):
    
        if not conn:
            log('[w] get_connection_id call with non existing connection', 2)
            return None
    
        try:
            rows = self.execute_query(conn, "select connection_id from m_connections where own = 'TRUE'", [])
        except DatabaseError as e:
            log(f'[E] exception in get_connection_id: {e}', 2)
            return None

        if len(rows):
            connection_id = rows[0][0]
            log('connection id: {connection_id}', 4)
            return connection_id
        else:
            log('[W] connection id not detected', 2)
            return None
        

    def destroy(self):
        log('destroy call (ignored)')
        pass
        
    def close_connection(self, connection):
        log('close connection call...', 5)
        try:
            connection.close() # fails with OperationalError always...
        except dbapi.OperationalError:
            log('close exception...', 5)

        except Exception as e:
            log(f'Close connection exception: {str(e)} (ignored)', 2)
            
        connection = None
        
        log('closed...', 5)
            
        return

    def ifNumericType(self, t):
        return False

    def ifRAWType(self, t):
        return False

    def ifTSType(self, t):
        return False

    def ifVarcharType(self, t):
        return False
            
    def ifDecimalType(self, t):
        return False

    def ifLOBType(self, t):
        return False
            
    def ifBLOBType(self, t):
        return False  