'''
    Abstract DB interface.
    Actual implementation(s) to be imported and used through dbi

    The class have to impement the following:
    
    - name property
    - options property
    
    Charts (used in dbDP.py):
        create_connection
        execute_query
        execute_query_desc - only for gantt charts, can be ignored on first stages
                           - might be used internally in create_connection to set
                             env variables (dbi_hana).
        
        close_connection
    
    ***    
    Requred for SQL Console, used in sqlConsole.py
    ***
    
        console_connection (self, server, dbProperties = None, data_format_version2 = False):
            - returns connection
            - may have additional init things if requred, like large SQL handling, 
              longdate suppor init, etc. Can be just the same as chart connection.
            
            
        execute_query_desc(self, connection, sql_string, params, resultSize):
            - returns:
                rows_list: list (!) of row arrays. Most cases just one result set
                cols_list: list (!) of column descriptions (1:1 to rows list)
                dbCursor: link to cursor for whatever reasons
                psid: statement ID, again, for whatever reason
                
                see some details in hdb impl
                
        drop_statement(connection, psid)
            - most likely can be just empty

        getAutoComplete(schema, term)
            - this forms an sql query for the ctrl+space functionality in console
            just skip it if you are not sure, it will be safely ignored
        
        type checks for LOBs processing and correct result render
            ifNumericType
            ifRAWType
            ifTSType
            ifVarcharType
            ifDecimalType
            ifLOBType
            ifBLOBType
        
    HANA Specific yet requred on the DBI level
        drop_statement - to keep prepared statements cleat
        close_result - to release MVCC
'''
import dbi_hana
import dbi_st04
import dbi_sqlite

from utils import log, cfg

dbidict = {'HANA DB': 'HDB'}

if cfg('experimental'):
    dbidict['HANA Cloud'] = 'HDB'

if cfg('S2J', False):
    dbidict['ABAP Proxy'] = 'S2J'
    

dbidict['SQLite DB'] = 'SLT'
dbidictRev = {} # reverse dict

for k in dbidict:
    dbidictRev[dbidict[k]] = k

class dbi:

    dbinterface = None

    def __init__ (self, dbtype):
    
        log('[DBI] init: %s' % dbtype)
        
        if dbi.dbinterface is None or dbi.dbinterface.name != dbtype:
        
            if dbi.dbinterface is not None:
                log('[DBI] stopping the old DBI instance')
                dbi.dbinterface.destroy()
                del dbi.dbinterface
            else:
                log('[DBI] seems initial DBI instance request')
    
            if dbtype == 'HDB':
                dbi.dbinterface = dbi_hana.hdbi()
            elif dbtype == 'S2J':
                dbi.dbinterface = dbi_st04.s2j()
            elif dbtype == 'SLT':
                dbi.dbinterface = dbi_sqlite.sqlite()
            else:
                raise Exception(f'Unknown DB driver name: {dbidictRev.get(dbtype)} - {dbtype}')
        else:
            log('[DBI] reusing existing instance')
