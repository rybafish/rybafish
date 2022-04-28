'''
    Database interface implementation for SAP HANA DB
'''

import pyhdb
import time

#### low-level pyhdb magic requred because of missing implementation of CLOSERESULTSET  ####

from pyhdb.protocol.message import RequestMessage
from pyhdb.protocol.segments import RequestSegment
from pyhdb.protocol.parts import ResultSetId, StatementId

from pyhdb.protocol.constants import message_types, type_codes

from dbCursor import cursor_mod
from pyhdb.protocol.constants import function_codes #for the cursor_mod

from _constants import build_date, version

import kpiDescriptions
import sql

import sys

from utils import cfg, hextostr
from utils import log as ulog
from utils import dbException

from dbi_extention import getDBProperties

from os import getlogin

def log(s, p = 3):
    ulog('[HDB] ' + s, p)

class hdbi ():

    name = 'HDB'
    options = {'keepalive': True, 'largeSQL': True}
    
    # those two are missing in PyHDB
    message_types.CLOSERESULTSET = 69 
    message_types.DROPSTATEMENTID = 70
    
    
    logline = 'db configuration:'

    for k in pyhdb.protocol.constants.DEFAULT_CONNECTION_OPTIONS:
        logline +=('    %s = %s\n' % (k, str(pyhdb.protocol.constants.DEFAULT_CONNECTION_OPTIONS[k])))
        
    log(logline, 4)

    largeSql = False
    
    def __init__(self):
        log('Using HDB as DB driver implementation')

    def create_connection (self, server, dbProperties = None):

        t0 = time.time()
        try: 
            # normal connection
            
            connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'])
            connection.large_sql = False
            
            if cfg('internal', True):
                setApp = "set 'APPLICATION' = 'RybaFish %s'" % version
                self.execute_query_desc(connection, setApp, [], 0)
                
                setApp = "set 'APPLICATIONUSER' = '%s'" % getlogin()
                self.execute_query_desc(connection, setApp, [], 0)

        except Exception as e:
    #    except pyhdb.exceptions.DatabaseError as e:
            log('[!]: connection failed: %s\n' % e)
            connection = None
            raise dbException(str(e))

        t1 = time.time()
        
        getDBProperties(connection, self.execute_query, log, dbProperties)
        
        t2 = time.time()
        
        log('(re)connect/properties: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))
        
        return connection

    def console_connection (self, server, dbProperties = None, data_format_version2 = False):

        longdate = cfg('longdate', True)

        t0 = time.time()
        
        try: 
            if self.largeSql:
                old_ms = pyhdb.protocol.constants.MAX_MESSAGE_SIZE
                old_ss = pyhdb.protocol.constants.MAX_SEGMENT_SIZE
                pyhdb.protocol.constants.MAX_MESSAGE_SIZE = 2**19
                pyhdb.protocol.constants.MAX_SEGMENT_SIZE = pyhdb.protocol.constants.MAX_MESSAGE_SIZE - 32
                
                if longdate:
                    log('largesql console with longdates')
                    connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'], data_format_version2 = longdate)
                else:
                    log('largesql console without longdates')
                    connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'])
                    
                connection.large_sql = True
                self.largeSql = False
                
                old_ms = pyhdb.protocol.constants.MAX_MESSAGE_SIZE
                old_ss = pyhdb.protocol.constants.MAX_SEGMENT_SIZE
            else:
                # normal connection

                if longdate:
                    log('console connection with longdates')
                    connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'], data_format_version2 = longdate)
                else:
                    log('console connection without longdates')
                    connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'])

                connection.large_sql = False
                self.largeSql = False
                
            if cfg('internal', True):
                setApp = "set 'APPLICATION' = 'RybaFish %s'" % version
                self.execute_query_desc(connection, setApp, [], 0)
                
                setApp = "set 'APPLICATIONUSER' = '%s'" % getlogin()
                self.execute_query_desc(connection, setApp, [], 0)
            
        except Exception as e:
    #    except pyhdb.exceptions.DatabaseError as e:
            log('[!]: connection failed: %s\n' % e)
            connection = None
            raise dbException(str(e))

        t1 = time.time()
        
        log('sql (re)connect: %s' % (str(round(t1-t0, 3))))
        
        return connection

    def get_connection_id(self, conn):
        rows = self.execute_query(conn, "select connection_id from m_connections where own = 'TRUE'", [])

        if len(rows):
            connection_id = rows[0][0]
            return connection_id
        else:
            return None
        

    def destroy(self):
        log('destroy call (ignored)')
        pass
        
    def close_connection(self, c):
        log('close connection call...')
        try:
            c.close() # fails with OperationalError always...
        except pyhdb.exceptions.OperationalError:
            pass
            
        return
        
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
        except pyhdb.exceptions.DatabaseError as e:
        
            log('[!] SQL Error: %s' % sql_string[0:256])
            log('[!] SQL Error: %s' % (e))

            if str(e).startswith('Lost connection to HANA server'):
                log('[!] SQL Error: related to connection')
                raise dbException(str(e), dbException.CONN)
            
            raise dbException(str(e))
        except Exception as e:
            log("[!] unexpected DB exception, sql: %s" % sql_string)
            log("[!] unexpected DB exception: %s" % str(e))
            log("[!] unexpected DB exception: %s" % sys.exc_info()[0])
            raise dbException(str(e))
            
        try:
            ps = cursor.get_prepared_statement(psid)

            cursor.execute_prepared(ps, [params])
            
            rows = cursor.fetchall()
            
            self.drop_statement(connection, psid)
            
            #close_result(connection, cursor._resultset_id)

        except pyhdb.exceptions.DatabaseError as e:
            log('[!] sql execution issue: %s\n' % e)
            raise dbException(str(e))
        except Exception as e:
            log('[E] unexpected error: %s' % str(e))
            raise dbException(str(e))

        return rows

    def drop_statement(self, connection, statement_id):

        log('psid to drop --> %s' % (hextostr(statement_id)), 4)

        if statement_id is None or connection is None:
            return

        t0 = time.time()
        
        request = RequestMessage.new(
                    connection,
                    RequestSegment(message_types.DROPSTATEMENTID, StatementId(statement_id))
                    )

        response = connection.send_request(request)
        
        t1 = time.time()
        
        log('psid drop took %s' % (str(round(t1-t0, 3))), 4)

    def close_result(self, connection, _resultset_id):
        
        request = RequestMessage.new(
                    connection,
                    RequestSegment(message_types.CLOSERESULTSET, (ResultSetId(_resultset_id)))
                    )

        response = connection.send_request(request)
        
        # no exception...
        # no result check...
        # never failed... (what if connection issue...)
        return

    def execute_query_desc(self, connection, sql_string, params, resultSize):
        '''
            The method mainly used by SQL console because it also needs a result set description.
            
            additionaly it is use in Gantt customKPIs because of the dynamic number of return columns 
            
            It also used a modified version of the pyhdb cursor implementation because of the https://github.com/rybafish/rybafish/issues/97
        '''

        if not connection:
            log('no db connection...')
            return

        #cursor = connection.cursor()
        cursor = cursor_mod(connection)
        
        # prepare the statement...
        
        log('[SQL]: %s' % sql_string, 5)

        if len(params) > 0:
            log('[PRMS]: %s' % str(params), 5)

        try:
            psid = cursor.prepare(sql_string)
        except pyhdb.exceptions.DatabaseError as e:
        
            log('DatabaseError: ' + str(e.code))
        
            if str(e).startswith('Lost connection to HANA server'):
                raise dbException(str(e), dbException.CONN)
        
            log('[!] SQL Error: %s' % sql_string)
            log('[!] SQL Error: %s' % (e))
            
            raise dbException(str(e))
        except Exception as e:
            log("[!] unexpected DB exception, sql: %s" % sql_string)
            log("[!] unexpected DB exception: %s" % str(e))
            log("[!] unexpected DB exception: %s" % sys.exc_info()[0])
            raise dbException(str(e))
            
        metadata = cursor._prepared_statements[psid]._params_metadata
        
        scalarOutput = False
        
        if len(metadata) > len(params):
            #scalar output detected so now do this dirty parameters preparation and even fake result fetch later....
            scalarOutput = True
            
            
            if resultSize is None:
                log('[E] resultSize is None in scope of execute_query_desc only supposed for Gantt chart extraction')
                log('[E] it does not support scalar output!')
                raise dbException('Unsupported use of execute_query_desc, check logs.')
                
            for p in metadata:
                # p - ParameterMetadata object
                log('Okay, Scalar output parameter: [%s]' % (str(p)), 3)
                
                if(self.ifLOBType(p.datatype)):
                    params.append('') # don't even ask... PyHDB...
                else:
                    params.append(None)
            
        try:
            ps = cursor.get_prepared_statement(psid)

            if len(params) > 0:
                log('[PRMS]: %s' % str(params), 5)
                
            cursor.execute_prepared(ps, [params])
            
            columns_list = cursor.description_list.copy()
            
            if cursor._function_code == function_codes.DDL:
                log('that was a ddl...', 4)
                rows_list = None
            else:
                rows_list = []
            
                if scalarOutput:
                    cols_list = []
                    
                    cols = [] #columns
                    
                    for p in metadata:
                        cols.append((p.id, p.datatype, 'SCALAR'))
                    
                    columns_list = [(cols),]
                    
                    if cursor.description_list:
                        columns_list.append(cursor.description_list[0])
                        
                    rows = cursor.fetchmany(1, 0) # we always expect just one line, and we hardcode the resultset number for scalars to be the first one (zero)
                    
                    log('row with scalar output(s): %s' % str(rows), 5)
                    
                    if len(rows[0]) != len(cols):
                        raise dbException('Inconsistent metadata for scalar output row, some HANA revisions are affected, some are not, see RybaFish issue #555')
                    
                    rows_list.append(rows)
            
                    log('columns_list with scalar(s)  ----> %s' % str(columns_list), 4)
                    
                '''
                for clmn in columns_list:
                    log('--> %s' % str(clmn), 5)
                    pass
                '''
                
                log('results to fetch: %i' % len(cursor.description_list), 5)
                
                scalar_shift = 1 if scalarOutput else 0

                for i in range(len(cursor.description_list)):
                    #log('fetch many %i' % (i + scalar_shift), 5)
                    
                    if resultSize is not None:
                        rows = cursor.fetchmany(resultSize, i+scalar_shift)
                    else:
                        # unlimited fetch for gantt charts
                        # all this scalar tricks are not supported here
                        rows = cursor.fetchall()
                    
                    rows_list.append(rows)
                    
                # cursor.close() does nothing anyway...

        except pyhdb.exceptions.DatabaseError as e:
            log('[!] sql execution issue: %s\n' % e)
            raise dbException(str(e))
        except Exception as e:
            log('[E] unexpected DB error: %s' % str(e))
            raise dbException(str(e))
            
        # drop_statement(connection, psid) # might be useful to test LOB.read() issues

        return rows_list, columns_list, cursor, psid
        
    '''
    def DEPR_get_data(connection, kpis, times, data):
        ''
            requests list of kpis from connection c where time between times.from times.to into &data
            
            to do: tenant, hostm port
        ''
        
        if not connection:
            log('no db connection...')
            return
            
        params = []
        
        kpis = ['time', 'cpu', 'memory_used']
        
        sql_string = 'select time, cpu, memory_used from m_load_history_service where time > add_seconds(now(), -3600*12) order by time asc'
            
        t0 = time.time()
        
        rows = self.execute_query(connection, sql_string, params)
        
        kpi_map = {}
        for kpi in kpiDescriptions.kpiStyles:
            kpi_map[kpi[5]] = kpi[2]
        

        trace_lines = len(rows)
        
        t1 = time.time()
        
        i = 0
        for row in rows:
            if i == 0: # allocate memory
                
                for j in range(0, len(kpis)):
                    
                    if j == 0: #time
                        data['time'] = [0] * (trace_lines)  #array('d', [0]*data_size) ??
                    else:
                        data[kpi_map[kpis[j]]] = [0]* (trace_lines)  #array('l', [0]*data_size) ??
            
            for j in range(0, len(kpis)):
                if j == 0: #time column always 1st
                    data['time'][i] = row[j].timestamp()
                else:
                    data[kpi_map[kpis[j]]][i] = row[j]
            
            i+=1

        t2 = time.time()

        log('trace get time: %s, get/parse time %s (%i rows)' % (str(round(t1-t0, 3)), str(round(t2-t1, 3)), trace_lines))

    def DEPR_initHosts(c, hosts, hostKPIs, srvcKPIs):
        '
            this one to be called once after the connect to prepare info on hosts/services available
            AND KPIs
        '

        kpis_sql = 'select view_name, column_name from m_load_history_info order by display_hierarchy'

        if not c:
            log('no db connection...')
            return

        sql_string = sql.hosts_info

        t0 = time.time()
        
        rows = self.execute_query(c, sql_string)
        
        for i in range(0, len(rows)):
            hosts.append({
                        'host':rows[i][0],
                        'port':rows[i][1],
                        'from':rows[i][2],
                        'to':rows[i][3]
                        })

        rows = self.execute_query(c, kpis_sql)
        
        for kpi in rows:
        
            if kpi[1] == '': #hierarchy nodes
                continue
                
            sqlName = kpi[1].lower()
        
            if kpi[0].lower() == 'm_load_history_host':
                if kpiDescriptions.findKPIsql('h', sqlName):
                    hostKPIs.append(sqlName)
            else:
                if kpiDescriptions.findKPIsql('s', sqlName):
                    srvcKPIs.append(sqlName)

        t1 = time.time()
        
        log('hostsInit time: %s' % (str(round(t1-t0, 3))))
    '''
        
    def ifNumericType(self, t):
        if t in (type_codes.TINYINT, type_codes.SMALLINT, type_codes.INT, type_codes.BIGINT,
            type_codes.DECIMAL, type_codes.REAL, type_codes.DOUBLE):
            return True
        else:
            return False

    def ifRAWType(self, t):
        if t == type_codes.VARBINARY:
            return True
        else:
            return False

    def ifTSType(self, t):
        if t in (type_codes.TIMESTAMP, type_codes.LONGDATE):
            return True
        else:
            return False

    def ifVarcharType(self, t):
        if t == type_codes.VARCHAR or t == type_codes.NVARCHAR:
            return True
        else:
            return False
            
    def ifDecimalType(self, t):
        if t in (type_codes.DECIMAL, type_codes.REAL, type_codes.DOUBLE):
            return True
        else:
            return False

    def ifLOBType(self, t):
        if t in (type_codes.CLOB, type_codes.NCLOB, type_codes.BLOB, type_codes.TEXT):
            return True
        else:
            return False
            
    def ifBLOBType(self, t):
        if t == type_codes.BLOB:
            return True
        else:
            return False        