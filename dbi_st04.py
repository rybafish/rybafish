'''
    smoke two joints proxy implementation 
    
    it is single-connection proxy
'''

import socket
from datetime import datetime

from io import StringIO
import csv

from utils import cfg
from utils import log as ulog
from utils import dbException

from dbi_extention import getDBProperties

def log(s, p = 3):
    ulog('[S2J] ' + s, p)


class s2j():

    name = 'S2J'
    options = {'keepalive': False, 'largeSQL': False}

    s = None
    lock = None

    def __init__(self):
        log('Using S2J as DB driver implementation')
        
    def create_connection(self, server, dbProperties = None):
    
        host = server['host']
        port = server['port']
        
        log('open connection...')
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2j.s = s
        self.s = s
        
        try:
            self.s.connect((host, port))
        #except ConnectionRefusedError as e:
        except (ConnectionError, socket.gaierror) as e:
            error = 'Cannot connect to ABAP proxy: ' + str(e)
            raise dbException(error)
            
        getDBProperties(self.s, self.execute_query, log, dbProperties)
        
        return self.s
        
    def execute_query(self, connection, sql_string, params):
        def substituteParams(s, params):
        
            np = len(params)
            
            res = ''
            
            shift = 0
            
            for i in range(np):
                pos = sql_string.find('?', shift)
                
                if pos >= 0:
                    res += sql_string[shift:pos]
                    res += "'" + str(params[i]) + "'"
                    
                    shift = pos + 1
                    
                else:
                    raise Exception('SQL parsing: wrong number of parameters')
                
            res += sql_string[shift:]
                
            return res
            
        if s2j.lock:
            raise dbException('Proxy is locked: wait for the other query to finish first.')
            
        log('DBI LOCK SET')
        s2j.lock = True
        
        log('sql: %s' % sql_string)
        
        if params:
            log('params: [%s]' % str(params))
            
            sql_string = substituteParams(sql_string, params)
            
            log('sql: [%s]' % (sql_string))
            
        sql = sql_string + '\n\n'
        sql = sql.encode()
        
        self.s.sendall(sql)
        
        resp = ''
        
        try:
            while True:
                data = self.s.recv(1024)

                if data:
                    #print('Received:')
                    #print(data.decode())
                    resp += data.decode()
                else:
                    #print('Terminated.')
                    break
                    
                if resp[-2:] == '\n\n':
                    break
        except ConnectionError as err:
            s2j.lock = False
            log('DBI LOCK UNSET')
            raise dbException(str(err))
        except Exception as er:
            s2j.lock = False
            log('DBI LOCK UNSET 2')
            raise dbException(str(er))
            
        resp = resp[:-1]

        if resp[:9] == '[ERROR]: ':
            s2j.lock = False
            log('DBI LOCK UNSET')
            raise dbException(resp[9:])
            
        self.rows = self.parseResponce(resp)
        
        s2j.lock = False
        log('DBI LOCK UNSET')
        
        log('SQL Results')
        log(str(self.rows), 5)
        
        return self.rows
        
    def destroy(self):
        log('DBI Destroy call...')
        if self.s is not None:
            log('Closing the connection...')
            # sock.shutdown(socket.SHUT_RDWR) ?
            self.s.close()
            
        s2j.lock = False
        log('DBI LOCK UNSET')

    
    def parseResponce(self, resp):
    
        '''
            takes csv resp string and creates a rows array
            ! also builds self.types list
        
            Note: local rows but self.types here!
        '''
    
        def convert_types():
            '''
                performs conversion of rows array
                based on types array
            '''
            for c in range(len(self.types)):
                for i in range(len(rows)):
                    
                    if self.types[c] == 'int':
                        rows[i][c] = int(rows[i][c])
                    elif self.types[c] == 'timestamp':
                        rows[i][c] = datetime.fromisoformat(rows[i][c])
                    else:
                        pass
        
        def check_integer(j):
            log('check column %i for int' % (j), 5)
            
            for ii in range(len(rows)):
                if not rows[ii][j].isdigit():
                    log('not a digit: (%i, %i): %s' % (ii, j, rows[ii][j]), 5)
                    log('not a digit: %s' % (str(rows[ii])), 5)
                    return False
                    
            return True
            
        def check_timestamp(j):
            log('check column %i for timestamp' % (j), 5)
            
            for ii in range(len(rows)):
                try:
                    v = datetime.fromisoformat(rows[ii][j])
                except:
                    log('not a timestamp: (%i, %i): %s' % (ii, j, rows[ii][j]), 5)
                    return False
                    
            return True
                
        f = StringIO(resp)
        reader = csv.reader(f, delimiter=',')
        
        
        rows = []
        
        self.header = next(reader)
        #header = reader.__next__()
        
        log('header:' + str(self.header), 5)
        
        cols = len(self.header)
        
        for row in reader:
            rows.append(row)
            
        self.types = ['']*cols
        
        #detect types
        for i in range(cols):
            if check_integer(i):
                self.types[i] = 'int'
            elif check_timestamp(i):
                self.types[i] = 'timestamp'
            else:
                self.types[i] = 'varchar'
        
        convert_types()
        
        log('types:' + str(self.types), 5)
        
        if len(rows) > 1:
            log('row sample:' + str(rows[1]), 5)
        
        return rows
        
    def close_connection(self, connection):
        log('Close connection (ignoring)', 5)
        
    '''
        Console specific stuff below
    '''    
    def console_connection (self, server, dbProperties = None, data_format_version2 = False):
        if s2j.s is not None:
            self.s = s2j.s
            return s2j.s
        else:
            raise Exception('Chart not connected, cannot open console.')

    def get_connection_id(self, conn):
        return None

    def execute_query_desc(self, connection, sql_string, params, resultSize):
    # self.rows_list, self.cols_list, dbCursor, psid = self.dbi.execute_query_desc(cons.conn, sql, [], resultSizeLimit)
    
        self.execute_query(connection, sql_string, params)
        
        #log('rows:\n%s' % str(self.rows), 5)
        
        cols = []
        
        
        for i in range(len(self.types)):
            cols.append([self.header[i], self.types[i], None])
        
        rlist = [self.rows]
        clist = [cols]

        log('columns for above: %s' % str(clist), 5)
        log('types for above: %s' % str(self.types), 5)
        
        return rlist, clist, None, None
    
    def drop_statement(self, connection, psid):
        pass
        
    def ifLOBType(self, t):
        return False
        
    def ifBLOBType(self, t):
        return False
        
    def ifNumericType(self, t):
        if t == 'int':
            return True
        else:
            return False
        
    def ifRAWType(self, t):
        return False
        
    def ifTSType(self, t):
        return False
        
    def ifVarcharType(self, t):
        if t == 'varchar':
            return True
        else:
            return False
        
    def ifDecimalType(self, t):
        return False