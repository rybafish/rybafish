# things shared by S2J and HANA interfaces
import re
from datetime import datetime
from utils import cfg, dbException

def getDBProperties(connection, queryFunction, log, dbProperties):
    '''
        supplement initial DB connection with additional DB information
        extract main DB properties like timezone, SID, version, tenant name etc (HANA DB)

        Currently used for HDB, S2J.
    '''
    if dbProperties is not None:

        noprodcheck_sql = 'select distinct key, value from m_host_information where key in (?, ?, ?)'
        prms = ['timezone_offset', 'sid', 'build_version']

        if cfg('no_tenants', False):
            sql = noprodcheck_sql
        else:
            sql =  '''select 'usage' key, usage value from m_database union
            select distinct key, value from m_host_information where key in (?, ?, ?)'''

        try:
            rows = queryFunction(connection, sql, prms)
        except dbException as e:
            # failback in case of exception for no tenants DB
            log('[E] excecption during connection:', 2)
            log(f'{e}', 2)
            rows = queryFunction(connection, noprodcheck_sql, prms)

        for row in rows:
            if row[0] == 'timezone_offset':
                dbUTCDelta = row[1]

                hostNow = datetime.now().timestamp()
                hostUTCDelta = (datetime.fromtimestamp(hostNow) - datetime.utcfromtimestamp(hostNow)).total_seconds()

                dbProperties['timeZoneDelta'] = int(dbUTCDelta) - int(hostUTCDelta)
                dbProperties['utcOffset'] = int(dbUTCDelta)
            elif row[0] == 'sid':
                if cfg('mapsid'):
                    sm = cfg('mapsid')
                    dbProperties['sid'] = row[1].replace(sm[0], sm[1])
                else:
                    dbProperties['sid'] = row[1]
            elif row[0] == 'build_version':
                ver = row[1]
                # example: 2.00.045.00.1575639312

                m = re.match('^\s*(\d\.\d+\.\d+)', ver)

                if m:
                    ver = m.group(1)

                dbProperties['version'] = ver
            elif row[0] == 'usage':
                dbProperties['usage'] = row[1]
                if row[1] == 'prod' or True:
                    log(f'wow, usage: {row[1]}', 2)
                else:
                    log(f'wow, usage: {row[1]}', 4)

        if 'timeZoneDelta' not in dbProperties:
            dbProperties['timeZoneDelta'] = 0
        if 'sid' not in dbProperties:
            dbProperties['sid'] = '???'


        if cfg('skipTenant', False) == False:

            rows = []

            try:
                rows = queryFunction(connection, 'select database_name from m_database', [])

                if len(rows) == 1:
                    if cfg('mapdb'):
                        dbmap = cfg('mapdb')
                        dbProperties['tenant'] = rows[0][0].replace(dbmap[0], dbmap[1])
                    else:
                        dbProperties['tenant'] = rows[0][0]
                else:
                    dbProperties['tenant'] = '???'
                    log('[w] tenant cannot be identitied')
                    log('[w] response rows array: %s' % str(rows))

            except dbException as e:
                rows.append(['???'])
                log('[w] tenant request error: %s' % str(e))

                dbProperties['tenant'] = None

    if cfg('dev'):
        log(f'dbProperties: {dbProperties}', 5)

def getAutoComplete(schema, term):
    '''returns sql for autocomplete statement'''
    if schema == 'PUBLIC':
        sql = 'select distinct schema_name object, \'SCHEMA\' type from schemas where lower(schema_name) like ? union select distinct object_name object, object_type type from objects where (schema_name = ? or schema_name = current_schema) and lower(object_name) like ? order by 1'
        params = [term, schema, term]
    else:
        sql = 'select distinct object_name object, object_type type from objects where schema_name = ? and lower(object_name) like ? order by 1'
        params = [schema, term]

    return sql, params
