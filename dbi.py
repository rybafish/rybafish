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
        
    Requred for SQL Console, used in sqlConsole.py
        console_connection
        execute_query_desc
        
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

class dbi:

    dbinterface = None

    def __init__ (self, dbtype = 'S2J'):
    
        if dbtype == 'HDB':
            self.dbinterface = dbi_hana.hdbi()
        elif dbtype == 'S2J':
            self.dbinterface = dbi_st04.s2j()
        else:
            raise Exception('Unknown DB driver name: %s' % dbtype)