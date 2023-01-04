from hdbcli import dbapi
import time
from _constants import build_date, version

import kpiDescriptions
import sql
import sys

from utils import cfg, hextostr
from utils import getlog
from utils import dbException
from dbi_extention import getDBProperties
from os import getlogin
from profiler import profiler

log = getlog('HDB')

class hdbi ():
    name = 'HDB'
    options = {'keepalive': True, 'largeSQL': True}
    largeSql = False
    def __init__(self):
        log('Using HDBCLI as DB driver implementation')
            
    def create_connection (self, server, dbProperties = None):
        t0 = time.time()
        try: 
        # normal connection
            if server.get('ssl'):
                log('Opening connection with SSL support', 4)
                connection = dbapi.connect(address=server['host'], port=server['port'], username=server['user'], password=server['password'], encrypt = True, sslValidateCertificate = False, authenticationMethods='password')
            else:
                log('Opening regular connection (no ssl)', 5)
                connection = dbapi.connect(address=server['host'], port=server['port'], user=server['user'], password=server['password'])
                
            connection.large_sql = False
            
            if cfg('internal', True):
                setApp = "set 'APPLICATION' = 'RybaFish %s'" % version
                self.execute_query_desc(connection, setApp, [], 0)
                
                setApp = "set 'APPLICATIONUSER' = '%s'" % getlogin()
                self.execute_query_desc(connection, setApp, [], 0)

        except Exception as e:
            log('[!]: connection failed: %s\n' % e)
            connection = None
            raise dbException(str(e))

        t1 = time.time()
        
        getDBProperties(connection, self.execute_query, log, dbProperties)
        
        t2 = time.time()
        
        log('(re)connect/properties: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))
        
        return connection