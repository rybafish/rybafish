'''
    SQLite database interface implementation
    
    EVN, 2022-11-15
'''

import sqlite3

from utils import cfg
from utils import getlog
from utils import dbException

from profiler import profiler

# from dbi_extention import getDBProperties seems not relevant

log = getlog('SQLite')

class sqlite():

    name = 'SLT'
    options = {'keepalive': False, 'largeSQL': False}

    def __init__(self):
        log('Using SQLite as DB driver implementation (SLT)')
        
    def create_connection(self, server, dbProperties = None):
        dbFile = server['host']
        log(f'Open connection: {dbFile}')

        try:
            conn = sqlite3.connect(dbFile, check_same_thread=False)
        except sqlite3.Error as e:
            log(f'Cannot open SQLite source "{dbFile}": {e}', 2)
            raise dbException('Cannot open SQLite source: ' + str(e))

        if dbProperties is not None:
            dbProperties['dbi'] = 'SLT'
            dbProperties['tenant'] = dbFile

        #getDBProperties(self.s, self.execute_query, log, dbProperties)
        
        log(f'created connection: {conn}')
        
        return conn
        
    def execute_query(self, connection, sql_string, params):

        log(f'[SQL] {sql_string}', 4)
        
        if params:
            log(f'[SQL] {params}', 4)
        
        try:
            cur = connection.cursor()
            cur.execute(sql_string, params)
            
            rows = cur.fetchall()

        except sqlite3.Error as e:
            log(f'SQL Executionex ception in: {sql_string}:: {e}', 2)
            raise dbException(f'Cannot execute: {sql_string}:: {e}')
        
        return rows
        
    def destroy(self):
        log('DBI Destroy call...')

    def close_connection(self, connection):
        log('Close the connection', 5)
        connection.close()
        
    '''
        Console specific stuff below
    '''

    def console_connection(self, server):
        conn = self.create_connection(server)
        log(f'Console connection: {conn}')
        return conn

    def drop_statement(self, stid):
        pass
        
    def get_connection_id(self, conn):
        # not sure this makes any sense for sqlite
        return None

    def execute_query_desc(self, connection, sql_string, params, resultSize):
    
        def detectType(t):
            #log(f'detectType: {t}: {type(t)}')
            if type(t) == int:
                return 1
                
            if type(t) == float:
                return 2

            if type(t) == str:
                return 3
                
            return -1

        @profiler
        def scanType(rows, idx):
        
            columnType = None
            needsConversion = False
            
            for r in rows:
                v = r[idx]
                
                t = detectType(v)
                
                if columnType is None:
                    columnType = t
                    continue
                    
                #if columnType == 1 and (t == 2):
                    # requires conversion from int to float, who cares.
                
                if columnType == 1 and (t == 3):
                    #downgrade to str
                    needsConversion = True
                    columnType = t
                    break
                
                if columnType == 3 and (t == 2 or t == 1):
                    needsConversion = True
                    break

                if columnType == -1:
                    break
                    
            if needsConversion == True:
                with profiler('SQLite column convertion'):
                    for r in rows:
                        if type(r[idx]) != str:
                            r[idx] = str(r[idx])
                    
            return columnType
    
        rows = []
        cols = []
                
                
        #connection = sqlite3.connect('accesslogs.db')
        
        log(f'connection: {connection}')
                
        log(f'[SQL] {sql_string}', 4)
        
        if params:
            log(f'[SQL] {params}', 4)
                
        try:
            cur = connection.cursor()
            #cur.execute(sql_string, params)
            cur.execute(sql_string, params)
            
            rows_tuples = cur.fetchmany(resultSize)
            
            with profiler('SQLite rows convertion'):
                for r in rows_tuples:
                    rows.append(list(r))
            
            if len(rows):
                for i in range(len(cur.description)):
                    typeCode = scanType(rows, i)
                    #log(f'{cur.description[i][0]:32} {typeCode:3}', 5)
                    cols.append((cur.description[i][0], typeCode, None))
            else:
                for c in cur.description:
                    cols.append((c[0], -1, None))

        except sqlite3.Error as e:
            log(f'SQL Execution exception in: {sql_string}:: {e}', 2)
            raise dbException(f'Cannot execute: {sql_string}:: {e}')

        return [rows], [cols], None, None
        
    def ifLOBType(self, t):
        return False

    def ifRAWType(self, t):
        return False
        
    def ifNumericType(self, t):
        if t in (1, 2):
            return True
        else:
            return False

    def ifDecimalType(self, t):
        if t == 2:
            return True
        else:
            return False
        
    def ifVarcharType(self, t):
        if t == 3:
            return True
        else:
            return False
        
    def ifTSType(self, t):
        return False
        
        