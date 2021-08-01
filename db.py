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

# those two are missing in PyHDB
message_types.CLOSERESULTSET = 69 
message_types.DROPSTATEMENTID = 70

#### low-level pyhdb magic requred because of missing implementation of CLOSERESULTSET  ####


from datetime import datetime

import kpiDescriptions
import sql

import sys

from utils import log, cfg, hextostr
from utils import dbException

from os import getlogin

logline = 'db configuration:'

for k in pyhdb.protocol.constants.DEFAULT_CONNECTION_OPTIONS:
    logline +=('    %s = %s\n' % (k, str(pyhdb.protocol.constants.DEFAULT_CONNECTION_OPTIONS[k])))
    
log(logline, 4)

largeSql = False

def create_connection (server, dbProperties = None):

    t0 = time.time()
    try: 
        # normal connection
        connection = pyhdb.connect(host=server['host'], port=server['port'], user=server['user'], password=server['password'])
        connection.large_sql = False
        
        if cfg('internal', True):
            setApp = "set 'APPLICATION' = 'RybaFish %s'" % version
            execute_query_desc(connection, setApp, [], 0)
            
            setApp = "set 'APPLICATIONUSER' = '%s'" % getlogin()
            execute_query_desc(connection, setApp, [], 0)

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
                if cfg('sidmapping'):
                    sm = cfg('sidmapping')
                    dbProperties['sid'] = row[1].replace(sm[0], sm[1])
                else:
                    dbProperties['sid'] = row[1]

        if 'timeZoneDelta' not in dbProperties:
            dbProperties['timeZoneDelta'] = 0
        if 'sid' not in dbProperties:
            dbProperties['sid'] = '???'
            
            
        if cfg('skipTenant', False) == False:
            
            rows = []
            
            try:
                rows = execute_query(connection, 'select database_name from m_database', [])

                if len(rows) == 1:
                    dbProperties['tenant'] = rows[0][0]
                else:
                    dbProperties['tenant'] = '???'
                    log('[w] tenant cannot be identitied')
                    log('[w] response rows array: %s' % str(rows))
                    
            except dbException as e:
                rows.append(['???'])
                log('[w] tenant request error: %s' % str(e))
                
                dbProperties['tenant'] = None
            
    
    t2 = time.time()
    
    log('(re)connect/properties: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))
    
    return connection

def console_connection (server, dbProperties = None, data_format_version2 = False):

    global largeSql
    
    longdate = cfg('longdate', True)

    t0 = time.time()
    
    try: 
        if largeSql:
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
            largeSql = False
            
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
            largeSql = False
            
        if cfg('internal', True):
            setApp = "set 'APPLICATION' = 'RybaFish %s'" % version
            execute_query_desc(connection, setApp, [], 0)
            
            setApp = "set 'APPLICATIONUSER' = '%s'" % getlogin()
            execute_query_desc(connection, setApp, [], 0)
        
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

    log('[SQL]: %s' % sql_string, 5)
    
    if len(params) > 0:
        log('[PRMS]: %s' % str(params), 5)

    try:
        cursor = connection.cursor()
        
        psid = cursor.prepare(sql_string)
    except pyhdb.exceptions.DatabaseError as e:
        log('[!] SQL Error: %s' % sql_string[0:256])
        log('[!] SQL Error: %s' % (e))
        
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
        
        drop_statement(connection, psid)
        
        #close_result(connection, cursor._resultset_id)

    except pyhdb.exceptions.DatabaseError as e:
        log('[!] sql execution issue: %s\n' % e)
        raise dbException(str(e))
    except Exception as e:
        log('[E] unexpected error: %s' % str(e))
        raise dbException(str(e))

    return rows

def drop_statement(connection, statement_id):

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

def close_result(connection, _resultset_id):
    
    request = RequestMessage.new(
                connection,
                RequestSegment(message_types.CLOSERESULTSET, (ResultSetId(_resultset_id)))
                )

    response = connection.send_request(request)
    
    # no exception...
    # no result check...
    # never failed... (what if connection issue...)
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
    
    log('[SQL]: %s' % sql_string, 5)

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
    
    if len(metadata) > 0:
        #scalar output detected so now do this dirty parameters preparation and even fake result fetch later....
        scalarOutput = True
        for p in metadata:
            # p - ParameterMetadata object
            log('Okay, Scalar output parameter: [%s]' % (str(p)), 3)
            
            if(ifLOBType(p.datatype)):
                params.append('') # don't even ask... PyHDB...
            else:
                params.append(None)
        
    try:
        ps = cursor.get_prepared_statement(psid)

        cursor.execute_prepared(ps, [params])
        
        columns_list = cursor.description_list.copy()
        
        if cursor._function_code == function_codes.DDL:
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
                    
                rows = cursor.fetchmany(1, 0) # what is the number of scalar output?
                
                log('scalar row: %s' % str(rows), 5)
                
                rows_list.append(rows)
        
                log('scalar detected... is it truth? does it harm', 5)
                log('columns_list (with scalar!)  ----> %s' % str(columns_list), 5)
                
            
            for clmn in columns_list:
                #log('--> %s' % str(clmn), 5)
                #log('--> %s' % str(clmn), 5)
                pass
            
            log('results to fetch: %i' % len(cursor.description_list), 5)
            
            scalar_shift = 1 if scalarOutput else 0
            
            for i in range(len(cursor.description_list)):
                #log('fetch many %i' % (i + scalar_shift), 5)
                rows = cursor.fetchmany(resultSize, i+scalar_shift)
                
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