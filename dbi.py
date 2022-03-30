'''
    Abstract BD interface.
    Actual implementation(s) to be imported and used through dbi

    The class have to impement the following:
    
    Charts (used in dbDP.py):
        create_connection
        execute_query
        execute_query_desc - only for gantt charts, so can be ignored during first stages
                           + it is also used internally in create_connection to set env variables.
        
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
                
        drop_statement(connection, psid)
            - most likely can be just empty
        
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

from utils import log, cfg

class dbi:

    dbinterface = None

    def __init__ (self, dbtype = 'HDB'):
    
        log('DBI init: %s' % dbtype)
    
        if dbtype == 'HDB':
            self.dbinterface = dbi_hana.hdbi()
        elif dbtype == 'S2J':
            self.dbinterface = dbi_st04.s2j()
        else:
            raise Exception('Unknown DB driver name: %s' % dbtype)