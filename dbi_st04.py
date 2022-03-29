'''
    smoke two joints proxy implementation 
    
    it is single-connection proxy
'''

import socket
from datetime import datetime

from io import StringIO
import csv

from utils import log, cfg
from utils import dbException

class s2j():

    s = None

    def __init__(self):
        pass
        
    def create_connection(self, server, dbProperties = None):
    
        host = server['host']
        port = server['port']

        host = '127.0.0.1'
        port = 5000
        
        log('[S2J] open connection...')
        
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            self.s.connect((host, port))
        except ConnectionRefusedError as e:
            raise dbException(str(e))
        
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
            
        
        log('[S2J] %s' % sql_string)
        
        if params:
            log('[S2J] [%s]' % str(params))
            
            sql_string = substituteParams(sql_string, params)
            
            log('[S2J] [%s]' % (sql_string))
            
        sql = sql_string + '\n\n'
        sql = sql.encode()
        
        self.s.sendall(sql)
        
        resp = ''
        
        try:
            while True:
                data = self.s.recv(1024)

                if data:
                    print('Received:')
                    print(data.decode())
                    resp += data.decode()
                else:
                    print('Terminated.')
                    break
                    
                if resp[-2:] == '\n\n':
                    break
        except ConnectionResetError as e:
            raise dbException(str(err))
            
        print('=====================')
                
        resp = resp[:-1]

        rows = self.parseResponce(resp)
        
        return rows
        
    def parseResponce(self, resp):
    
        def convert_types():
            '''
                performs conversion of rows array
                based on types array
            '''
            for c in range(len(types)):
                for i in range(len(rows)):
                    
                    if types[c] == 'int':
                        rows[i][c] = int(rows[i][c])
                    elif types[c] == 'timestamp':
                        rows[i][c] = datetime.fromisoformat(rows[i][c])
                    else:
                        pass
        
        def check_integer(j):
            log('[S2J] check column %i for int' % (j))
            
            for ii in range(len(rows)):
                if not rows[ii][j].isdigit():
                    log('[S2J] not a digit: (%i, %i): %s' % (ii, j, rows[ii][j]))
                    log('[S2J] not a digit: %s' % (str(rows[ii])))
                    return False
                    
            return True
            
        def check_timestamp(j):
            log('[S2J] check column %i for timestamp' % (j))
            
            for ii in range(len(rows)):
                try:
                    v = datetime.fromisoformat(rows[ii][j])
                except:
                    return False
                    
            return True
                
        f = StringIO(resp)
        reader = csv.reader(f, delimiter=',')
        
        
        rows = []
        
        header = next(reader)
        #header = reader.__next__()
        
        log('[S2J] header:' + str(header))
        
        cols = len(header)
        
        for row in reader:
            rows.append(row)
            
        types = ['']*cols
        
        #detect types
        for i in range(cols):
            if check_integer(i):
                types[i] = 'int'
            elif check_timestamp(i):
                types[i] = 'timestamp'
            else:
                types[i] = 'varchar'
        
        convert_types()
        
        log('[S2J] types:' + str(types))
        log('[S2J] row sample:' + str(rows[1]))
        
        return rows
        
    def close_connection(self, connection):
        log('[S2J] Close connection')
        pass