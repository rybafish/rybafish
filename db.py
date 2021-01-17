import pyhdb
import time

from utils import cfg

#### low-level pyhdb magic requred because of missing implementation of CLOSERESULTSET  ####

from pyhdb.protocol.message import RequestMessage
from pyhdb.protocol.segments import RequestSegment
from pyhdb.protocol.parts import ResultSetId

from pyhdb.protocol.constants import message_types, type_codes

from dbCursor import cursor_mod
from pyhdb.protocol.constants import function_codes #for the cursor_mod

message_types.CLOSERESULTSET = 69 # SAP HANA SQL Command Network Protocol Reference
                                  # this one is still missing in pyhdb 2019-12-15

#### low-level pyhdb magic requred because of missing implementation of CLOSERESULTSET  ####


from datetime import datetime

import kpiDescriptions
import sql

import sys

from utils import log, cfg
from utils import dbException

logline = 'db configuration:'

for k in pyhdb.protocol.constants.DEFAULT_CONNECTION_OPTIONS:
    logline +=('    %s = %s\n' % (k, str(pyhdb.protocol.constants.DEFAULT_CONNECTION_OPTIONS[k])))
    
log(logline)

largeSql = False

def create_connection (server, dbProperties = None):

    t0 = time.time()
    try: 
        # normal connection
        connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'])
        connection.large_sql = False
        
    except Exception as e:
#    except pyhdb.exceptions.DatabaseError as e:
        log('[!]: connection failed: %s\n' % e)
        connection = None
        raise dbException(str(e))

    t1 = time.time()

    if dbProperties is not None:
    
        rows = execute_query(connection, 'select distinct key, value from m_host_information where key in (?, ?)', ['timezone_offset', 'sid'])
        
        for row in rows:
            if row[0] == 'timezone_offset':
                dbUTCDelta = row[1]
                
                hostNow = datetime.now().timestamp()
                hostUTCDelta = (datetime.fromtimestamp(hostNow) - datetime.utcfromtimestamp(hostNow)).total_seconds()
                
                dbProperties['timeZoneDelta'] = int(dbUTCDelta) - int(hostUTCDelta)
            elif row[0] == 'sid':
                dbProperties['sid'] = row[1]

        if 'timeZoneDelta' not in dbProperties:
            dbProperties['timeZoneDelta'] = 0
        if 'sid' not in dbProperties:
            dbProperties['sid'] = '???'
    
    t2 = time.time()
    
    log('(re)connect/properties: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))
    
    return connection

def console_connection (server, dbProperties = None, data_format_version2 = False):

    global largeSql
    
    if cfg('experimental'):
        longdate = cfg('longdate', True)
    else:
        longdate = False

    t0 = time.time()
    
    try: 
        if largeSql:
            old_ms = pyhdb.protocol.constants.MAX_MESSAGE_SIZE
            old_ss = pyhdb.protocol.constants.MAX_SEGMENT_SIZE
            pyhdb.protocol.constants.MAX_MESSAGE_SIZE = 2**19
            pyhdb.protocol.constants.MAX_SEGMENT_SIZE = pyhdb.protocol.constants.MAX_MESSAGE_SIZE - 32
            
            if longdate:
                connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'], data_format_version2 = longdate)
            else:
                connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'])
                
            connection.large_sql = True
            largeSql = False
            
            old_ms = pyhdb.protocol.constants.MAX_MESSAGE_SIZE
            old_ss = pyhdb.protocol.constants.MAX_SEGMENT_SIZE
        else:
            # normal connection

            if longdate:
                connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'], data_format_version2 = longdate)
            else:
                connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'])

            connection.large_sql = False
            largeSql = False
            
        
    except Exception as e:
#    except pyhdb.exceptions.DatabaseError as e:
        log('[!]: connection failed: %s\n' % e)
        connection = None
        raise dbException(str(e))

    t1 = time.time()
    
    log('sql (re)connect: %s' % (str(round(t1-t0, 3))))
    
    return connection

def close_connection (c):
    try:
        c.close() # fails with OperationalError always...
    except pyhdb.exceptions.OperationalError:
        pass
        
    return
    
def execute_query(connection, sql_string, params):

    if not connection:
        log('no db connection...')
        return

    # prepare the statement...

    if cfg('loglevel') >= 5:
        log('[SQL]: %s' % sql_string)

    try:
        cursor = connection.cursor()
        
        psid = cursor.prepare(sql_string)
    except pyhdb.exceptions.DatabaseError as e:
        log('[!] SQL Error: %s' % sql_string)
        log('[!] SQL Error: %s' % (e))
        
        raise dbException(str(e))
    except Exception as e:
        log("[!] unexpected DB exception, sql: %s" % sql_string)
        log("[!] unexpected DB exception:", str(e))
        log("[!] unexpected DB exception:", sys.exc_info()[0])
        raise dbException(str(e))
        
    try:
        ps = cursor.get_prepared_statement(psid)

        cursor.execute_prepared(ps, [params])
        
        rows = cursor.fetchall()
        
        close_result(connection, cursor._resultset_id)

    except pyhdb.exceptions.DatabaseError as e:
        log('[!]: sql execution issue %s\n' % e)
        raise dbException(str(e))
    except Exception as e:
        log('[E] unexpected error: %s' % str(e))
        raise dbException(str(e))

    return rows

def close_result(connection, _resultset_id):
    
    request = RequestMessage.new(
                connection,
                RequestSegment(message_types.CLOSERESULTSET, (ResultSetId(_resultset_id)))
                )

    response = connection.send_request(request)
    
    # no exception...
    # no result check...
    return

def execute_query_desc(connection, sql_string, params, resultSize):
    '''
        The method used solely by SQL console because it also needs a result set description.
        It also used a modified version of the pyhdb cursor implementation because of the https://github.com/rybafish/rybafish/issues/97
    '''

    if not connection:
        log('no db connection...')
        return

    #cursor = connection.cursor()
    cursor = cursor_mod(connection)

    # prepare the statement...
    
    if cfg('loglevel') >= 5:
        log('[SQL]: %s' % sql_string)

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
        log("[!] unexpected DB exception:", str(e))
        log("[!] unexpected DB exception:", sys.exc_info()[0])
        raise dbException(str(e))
        
    try:
        ps = cursor.get_prepared_statement(psid)

        cursor.execute_prepared(ps, [params])

        if cursor._function_code == function_codes.DDL:
            rows = None
        else:
            rows = cursor.fetchmany(resultSize)
            
            cursor.close()

        # rows = cursor.fetchmany(resultSize)

    except pyhdb.exceptions.DatabaseError as e:
        log('[!]: sql execution issue %s\n' % e)
        raise dbException(str(e))
    except Exception as e:
        log('[E] unexpected error: %s' % str(e))
        raise dbException(str(e))

    columns = cursor.description

    return rows, columns, cursor
    
def get_data(connection, kpis, times, data):
    '''
        requests list of kpis from connection c where time between times.from times.to into &data
        
        to do: tenant, hostm port
    '''
    
    if not connection:
        log('no db connection...')
        return
        
    params = []
    
    kpis = ['time', 'cpu', 'memory_used']
    
    sql_string = 'select time, cpu, memory_used from m_load_history_service where time > add_seconds(now(), -3600*12) order by time asc'
        
    t0 = time.time()
    
    rows = execute_query(connection, sql_string, params)
    
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

def initHosts(c, hosts, hostKPIs, srvcKPIs):
    '''
        this one to be called once after the connect to prepare info on hosts/services available
        AND KPIs
    '''

    kpis_sql = 'select view_name, column_name from m_load_history_info order by display_hierarchy'

    if not c:
        log('no db connection...')
        return

    sql_string = sql.hosts_info

    t0 = time.time()
    
    rows = execute_query(c, sql_string)
    
    for i in range(0, len(rows)):
        hosts.append({
                    'host':rows[i][0],
                    'port':rows[i][1],
                    'from':rows[i][2],
                    'to':rows[i][3]
                    })

    rows = execute_query(c, kpis_sql)
    
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
    
    
def ifNumericType(t):
    if t in (type_codes.TINYINT, type_codes.SMALLINT, type_codes.INT, type_codes.BIGINT,
        type_codes.DECIMAL, type_codes.REAL, type_codes.DOUBLE):
        return True
    else:
        return False

def ifRAWType(t):
    if t == type_codes.VARBINARY:
        return True
    else:
        return False

def ifTSType(t):
    if t in (type_codes.TIMESTAMP, type_codes.LONGDATE):
        return True
    else:
        return False

def ifVarcharType(t):
    if t == type_codes.VARCHAR or t == type_codes.NVARCHAR:
        return True
    else:
        return False
        
def ifDecimalType(t):
    if t in (type_codes.DECIMAL, type_codes.REAL, type_codes.DOUBLE):
        return True
    else:
        return False

def ifLOBType(t):
    if t in (type_codes.CLOB, type_codes.NCLOB, type_codes.BLOB, type_codes.TEXT):
        return True
    else:
        return False
        
def ifBLOBType(t):
    if t == type_codes.BLOB:
        return True
    else:
        return False        