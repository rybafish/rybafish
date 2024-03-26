'''
    dpDB is the main data provider based on the database interface (dbi)
    
    It kinda impliments kinda "interface" to be usable in charts.
    
    Main calls are: 
        initHosts
        getData
            those two use database interface inside with minor adjustments
            depending on dbi itself.
        
    those two calls must be implemented in any dataprovider.
'''

from PyQt5.QtCore import QObject

from array import array

import pyhdb
import time

import datetime

from PyQt5.QtCore import QTimer

import dpDBCustom, kpiDescriptions
from kpiDescriptions import customKpi
from kpiDescriptions import kpiStylesNN, processVars

from PyQt5.QtCore import pyqtSignal

import sql

#import db
from dbi import dbi

import utils
from utils import cfg, log, yesNoDialog, formatTime, safeBool, safeInt
from utils import dbException, customKPIException, deb

import traceback
from os import getcwd
from profiler import profiler

class dataProvider(QObject):
    
    disconnected  = pyqtSignal()
    busy  = pyqtSignal(int)
    
    connection = None
    server = None
    timer = None
    timerkeepalive = None
    
    options = ['disconnectSignal', 'busySignal']
    
    # lock = False
    
    def __init__(self, server):
    
        super().__init__()
        self.dbProperties = {}
        
        log(f"Connecting to {server['dbi']}:\\\\{server['host']}:{server['port']}...")

        dbimpl = dbi(server['dbi'])
        self.dbi = dbimpl.dbinterface
        
        self.dbProperties['dbi'] = 'DB'
        
        try: 
            conn = self.dbi.create_connection(server, self.dbProperties)
        except dbException as e:
            log('dataprovider exception bubble up...')
            raise e
        
        if conn is None:
            log('[i] Failed to connect, dont know what to do next')
            raise Exception('Failed to connect, dont know what to do next...')
        else:
            log('connected')
            self.connection = conn
            self.server = server
            
    def terminate(self, closeConnection = False):
        if self.timer:
            self.timer.stop()
            self.timer = None
            self.timerkeepalive = None

        if self.connection and closeConnection:
            log('closing connection')
            close_connection(self.connection)
            self.connection = None
            log('closed')
            
        self.server = None
            
        return
            
            
    def reconnect(self):
        try: 
            conn = self.dbi.create_connection(self.server)
        except Exception as e:
            raise e
        
        if conn is None:
            log('[i] Failed to reconnect, dont know what to do next')
            raise Exception('Failed to reconnect, dont know what to do next...')
        else:
            log('re-connected')
            self.connection = conn
        
    def enableKeepAlive(self, window, keepalive):
    
        if not self.dbi.options.get('keepalive'):
            log('Keep-alives not supported by this DBI')
            return
    
        log('Setting up DB keep-alive requests: %i seconds' % (keepalive))
        self.timerkeepalive = keepalive
        self.timer = QTimer(window)
        self.timer.timeout.connect(self.keepAlive)
        self.timer.start(1000 * keepalive)
        
    def renewKeepAlive(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer.start(1000 * self.timerkeepalive)
    
    def close(self):
        if self.connection is not None:
            log('closing dataprovider connection')
            
            #self.connection.close()
            self.dbi.close_connection(self.connection)
            
        if self.timer:
            log('stopping dataprovider keep-alive timer')
            self.timer.stop()
        
    def keepAlive(self):
    
        if self.connection is None:
            log('no connection, disabeling the keep-alive timer')
            self.timer.stop()
            return

        try:
            log('chart keep-alive... ', 3, False, True)
            
            t0 = time.time()
            
            self.busy.emit(1)
            self.dbi.execute_query(self.connection, 'select * from dummy', [])
            
            if hasattr(self, 'fakeDisconnect'):
                log ('generate an exception...')
                log (10/0)
            
            self.busy.emit(0)
            t1 = time.time()
            log('ok: %s ms' % (str(round(t1-t0, 3))), 3, True)
        except dbException as e:
            log('Trigger autoreconnect...')
            try:
                conn = self.dbi.create_connection(self.server)
                if conn is not None:
                    self.connection = conn
                    log('Connection restored automatically')
                else:
                    log('Some connection issue, give up')
                    self.timer.stop()
                    self.connection = None
                    self.disconnected.emit()
            except dbException as e:
                log('Connection lost, give up')

                self.timer.stop()
                self.connection = None
                self.disconnected.emit()
        except Exception as e:
            log('[!] unexpected exception, disable the connection')
            log('[!] %s' % str(e))
            self.connection = None
            self.disconnected.emit()
        
    @profiler
    def initHosts(self, dpidx):
        '''
            dpidx - data provider index to link hosts to a dp
            hosts - list of widget.hosts
            
            returns:
                list of hosts
                list of kpis: sub-list for every host (service)
                list of corresponding KPI styles
            in progress:
                error text (mostly for custom KPI exceptions)

            old-style approach was: return nothing, fill provided hosts structure (linked from widget) << depricated with #739
            
        '''
        
        hosts = []
    
        tenant = self.dbProperties.get('tenant')
                    
        log(f'Init hosts dpDB wrapper. hosts: {hosts}')
        
        if not self.connection:
            log('No db connection...')
            return
            
        if hasattr(self.dbi, 'initHosts'):
            return self.dbi.initHosts(self.connection, dpidx, self.dbProperties)

        '''
            below is the default old-style hard-code implementation for HANA + S2J dbis
            as you see above it will be only used if dbi does not have its own initHosts
            implementation.
            
            it is not moved to dbi_hana and dbi_st04 beacause this will require the
            code duplication or another import, so, just leave this legacy impl here.
        '''
        
        # prepare data for populating hosts/services list
        # it is based on port/service name mapping available in m_services

        if tenant and tenant.lower() == 'systemdb':
            sql_string = 'select host, port, database_name, service_name from sys_databases.m_services order by host, port'
        else:
            sql_string = 'select host, port, null database_name, service_name from m_services order by host, port'
            
        rows = self.dbi.execute_query(self.connection, sql_string, [])
        
        # this is a dict to enrich hosts table with service names based on SQL above
        services = {}
        
        for r in rows:
            host, port, ten, srv = r
            
            if tenant and tenant.lower() != 'systemdb':
                ten = tenant
            
            skey = '%s:%s' % (host, port)
            services[skey] = [ten, srv]

        #extract hosts and services based on m_load_ views...
        sql_string = sql.hosts_info

        if cfg('ess'):
            #dirty but this will work
            sql_string = sql_string.replace('m_load_history', '_sys_statistics.host_load_history')

        rows = self.dbi.execute_query(self.connection, sql_string, [])
        
        if len(rows) <= 1:
            log('[W] no/limited telemetry available', 1)
            log('[W] try checking m_load_history views if there any data', 1)
            log('[W] potential reason: missing MONITORING role', 1)
        
        # populate hosts list
        # each item is a dict containing tenant, hostname, service_name and port
        if cfg('maphost'):
            for i in range(0, len(rows)):
            
                hm = cfg('maphost')
                pm = cfg('mapport')
                dm = cfg('mapdb')
            
                skey = '%s:%s' % (rows[i][0], rows[i][1])
                
                if skey in services:
                    ten, srv = services[skey]
                    ten = ten.replace(dm[0], dm[1])
                else:
                    ten, srv = None, None

                hosts.append({
                            'db':ten,
                            'host':rows[i][0].replace(hm[0], hm[1]),
                            'service':srv,
                            'port':rows[i][1].replace(pm[0], pm[1]),
                            #'from':rows[i][2],
                            #'to':rows[i][3]
                            'dpi': dpidx
                            })
        else:
            for i in range(0, len(rows)):
                skey = '%s:%s' % (rows[i][0], rows[i][1])
                
                if skey in services:
                    ten, srv = services[skey]
                else:
                    ten, srv = None, None
                    
                hosts.append({
                            'db':ten,
                            'host':rows[i][0],
                            'service':srv,
                            'port':rows[i][1],
                            #'from':rows[i][2],
                            #'to':rows[i][3]
                            'dpi': dpidx
                            })
                            
        #return hosts
        
        '''                 ' '
        '                     '
        '       K P I s       '
        '                     '
        ' '                 '''
        
        # load 'standard" KPIs
        kpis_sql = sql.kpis_info
        errorStr = None
        
        hostKPIs = []
        srvcKPIs = []
        kpiStylesNNN = {'host':{}, 'service':{}}
        
        rows = self.dbi.execute_query(self.connection, kpis_sql, [])
        
        #very similar logic called in dbi_sqlite.initHosts... somehow combine in one call?
        kpiDescriptions.initKPIDescriptions(rows, hostKPIs, srvcKPIs, kpiStylesNNN)

        # (re)load custom KPIs
        try:
            dpDBCustom.scanKPIsN(hostKPIs, srvcKPIs, kpiStylesNNN)

            # those two can generate same exception but due to very different post-check reason
            kpiDescriptions.clarifyGroups(kpiStylesNNN['host'])
            kpiDescriptions.clarifyGroups(kpiStylesNNN['service'])
        except customKPIException as e:
            log('[e] error loading custom kpis')
            log('[e] fix or delete the problemmatic yaml for proper connect')
            errorStr = str(e)
            # raise e             # seems only the dpDB raises exceptions so far...

        #now build new styles structures
        
        hostKPIsList = []
        hostKPIsStyles = []
        
        for host in hosts:
            if host['port'] == '':
                hostKPIsList.append(hostKPIs)               # append here because we add a new item for every host
                hostKPIsStyles.append(kpiStylesNNN['host']) # same here
            else:
                hostKPIsList.append(srvcKPIs)
                hostKPIsStyles.append(kpiStylesNNN['service'])

        return hosts, hostKPIsList, hostKPIsStyles, errorStr
        
    def splitKpis(self, kpiStylesNNN, kpis):
        '''
            devides KPIs per source
            '-' entry will contain default ones (m_load_history_...)
        '''
        kpisList = {}
        kpisList['-'] = []
        
        
        for kpi in kpis:
            if kpi not in kpiStylesNNN:
                #kpi disappeared on the fly, who cares
                log('[!] kpi description does not exist, skipping (%s)' % kpi)
                continue
                
            if customKpi(kpi):
                src = kpiStylesNNN[kpi]['sql']
                if src in kpisList:
                    kpisList[src].append(kpi)
                else:
                    kpisList[src] = [kpi]
            else:
                kpisList['-'].append(kpi)
                        
        return kpisList
        
    @profiler
    def getData(self, h, fromto, kpiIn, data, kpiStylesNNN, wnd = None):
        '''
        
            h - host structure
            fromto dict with 'from' abd 'to' keys (str)
            kpiIn - list of kpis to request, including custom ones (called cs-something)
        
            returns boolean
            False = some kpis were disabled due to sql errors
        '''
        
        # log(f'[GET DATA]: dbi: {self.dbi}')
        # log(f'[GET DATA]: prop: {self.dbProperties}')
        tzShift = self.dbProperties.get('timestampShift', 0)
        tzUTC = self.dbProperties.get('utcOffset', 0)

        kpisToDel = []

        deb(f'getData data keys: {data.keys()}')
        deb(f'getData requested kpis: {kpiIn}')

        for kpi in data.keys():
            if kpi in kpiIn or kpi == 'time':
                pass
            else:
                log(f'[w] extra clean-up required as {kpi} exists in data but not appear list of requested kpis', 2)
                log(f'[w] lenght to be deleted: {len(data[kpi])}', 2)
                kpisToDel.append(kpi)

        for kpi in kpisToDel:
            log(f'deleting {kpi}...', 2)
            del data[kpi]

        if tzShift:
            if fromto['from'] != '' and fromto['from'][0] != '-': # regular time
                ftime = datetime.datetime.strptime(fromto['from'], '%Y-%m-%d %H:%M:%S')
                ftime -= datetime.timedelta(seconds=tzShift)
                fromto['from'] = ftime.strftime('%Y-%m-%d %H:%M:%S')

            if fromto['to'] != '':
                ttime = datetime.datetime.strptime(fromto['to'], '%Y-%m-%d %H:%M:%S')
                ttime -= datetime.timedelta(seconds=tzShift)
                fromto['to'] = ttime.strftime('%Y-%m-%d %H:%M:%S')

        host = h.copy()

        if cfg('maphost'):
            hm = cfg('maphost')
            pm = cfg('mapport')
            host['host'] = host['host'].replace(hm[1], hm[0])
            host['port'] = host['port'].replace(pm[1], pm[0])

        sql_pref = 'select time,'
        tfilter = ''
        hfilter = ''
        orderby = 'order by time asc'
        
        log('getData host: %s' % (str(host)))
        log('getData kpis: %s' % (str(kpiIn)))
        
        if host['port'] == '':
            type = 'host'
        else:
            type = 'service'
            

        if self.connection is None:
            raise dbException('No valid db connection')
            
        # self.lock = True
        
        params = []
    
        kpiList = self.splitKpis(kpiStylesNNN, kpiIn)

        if host['port'] == '':
            t = 'h'
            hfilter = 'where host = ?'
            params.append(host['host'])
        else:
            t = 's'
            hfilter = 'where host = ? and port = ?'
            params.append(host['host'])
            params.append(host['port'])

        if fromto: # this to check fromto pair
            log('fromto: %s' % (str(fromto)))
            
            if fromto['from'] != '' and fromto['to'] == '':
                if fromto['from'][:1] == '-' :
                    hours = int(fromto['from'][1:])
                    params.append(hours)
                    tfilter = " time > add_seconds(now(), -3600 * ?)"
                    gtfilter = ' "STOP" > add_seconds(now(), -3600 * ?)'
                else:
                    params.append(fromto['from'])
                    tfilter = " time > ?"
                    gtfilter = ' "STOP" > ?'

            elif fromto['from'] == '' and fromto['to'] != '':
                params.append(fromto['to'])
                tfilter = " time < ?"
                gtfilter = ' "START" < ?'
            else:
                params.append(fromto['from'])
                params.append(fromto['to'])
                
                tfilter = " time between ? and ?"
                gtfilter = ' "STOP" >= ? and "START" <= ?'
                
        else:
            log('[!] code should not ever reach here (tfilter)', 2)
            tfilter = " time > add_seconds(now(), -3600*12)"
            gtfilter = ' "STOP" >= add_seconds(now(), -3600*12)'
        
        # allOk = True
        
        # loop through kpi sources
        for kpiSrc in kpiList.keys():
        
            nofilter = False
        
            kpisSql = []
            kpis = kpiList[kpiSrc]
            
            if len(kpis) == 0:
                continue
                
            subtype = kpiStylesNNN[kpis[0]].get('subtype')
            
            if host['port'] == '':
                if kpiSrc == '-':
                    if cfg('ess', False):
                        fromTable = 'from _sys_statistics.host_load_history_host'
                    else:
                        fromTable = 'from m_load_history_host'
                else:
                    sql = kpiDescriptions.customSql[kpiSrc]
                    sqlstr = kpiDescriptions.processVars(kpiSrc, sql)
                    fromTable = 'from (%s)' % sqlstr
            else:
                if kpiSrc == '-':
                    if cfg('ess', False):
                        fromTable = 'from _sys_statistics.host_load_history_service'
                    else:
                        fromTable = 'from m_load_history_service'

                else:
                    sql = kpiDescriptions.processVars(kpiSrc, kpiDescriptions.customSql[kpiSrc])
                    
                    fromTable = 'from (%s)' % sql
                                
            for kpi in kpis:
                if kpiSrc == '-':
                    kpisSql.append(kpi)
                else:
                    kpisSql.append(kpiStylesNNN[kpi]['sqlname'])
                    
            if kpiStylesNNN[kpi].get('nofilter'):
                nofilter = True
            
            cols = ', '.join(kpisSql)
            
            if subtype == 'multiline':
                firstKpi = kpis[0]
                style = kpiStylesNNN[firstKpi]
                groupby = style['groupby']
                cols += ', ' + groupby
            
            hfilter_now = hfilter # cannot modify hfilter as it is reused for the other KPI sources...
            gtfilter_now = gtfilter # cannot modify hfilter as it is reused for the other KPI sources...
            params_now = params.copy() # same for params list
            
            if nofilter == False: #normal KPI
                sql = '%s %s %s %s and%s %s' % (sql_pref, cols, fromTable, hfilter_now, tfilter, orderby)
            else:
                #need to remove host:port filter both from the SQL and parameters...
                hfilter_now = 'where'
                sql = '%s %s %s %s%s %s' % (sql_pref, cols, fromTable, hfilter_now, tfilter, orderby)
                
                if host['port'] == '':
                    params_now = params_now[1:]
                else:
                    params_now = params_now[2:]
            
            #if gantt to be checked here
            
            gantt = False
            
            if len(kpis) == 1: #only one kpi can be in gantt data source
                kpi = kpis[0]
                
                if subtype == 'gantt':
                    
                    # tfilter_mod = tfilter.replace('time', '"START"') # removed 2021-03-23
                
                    #sql = 'select entity, "START", "STOP", details %s %s%s order by entity, "START" desc' % (fromTable, hfilter, tfilter_mod)
                    #sql = 'select entity, "START", "STOP", details %s %s%s order by entity, seconds_between("START", "STOP") desc' % (fromTable, hfilter, tfilter_mod)
                    
                    if hfilter_now == 'where':
                        # no host/port filter due to nofilter kpi setting
                        pass
                    else:
                        # there is a filter so we have to add ' AND ' before the time filter...
                        # tfilter_mod = ' and ' + tfilter_mod
                        gtfilter_now = ' and ' + gtfilter_now
                        
                    title = ''
                    
                    if kpiStylesNNN[kpi].get('title') == True:
                        title += ', title'
                        
                    if kpiStylesNNN[kpi].get('gradient') == True:
                        title += ', gradient'

                    if kpiStylesNNN[kpi].get('manual_color') == True:
                        title += ', color'

                    sql = 'select entity, "START", "STOP", details%s %s %s%s order by entity desc, "START"' % (title, fromTable, hfilter_now, gtfilter_now)
                    gantt = True                    

            try:
                if not gantt:
                        self.getHostKpis(kpiStylesNNN, kpis, data, sql, params_now, kpiSrc, tzShift, tzUTC)
                else:
                    self.getGanttData(kpiStylesNNN, kpis[0], data, sql, params_now, kpiSrc, tzShift, tzUTC)
                    
            except dbException as e:
            
                log('Handling dbException for custom KPI..., type %s' % (str(e.type)), 2)
            
                reply = None
                
                #details = '>>' + s.replace('\\n', '\n').replace(cwd, '..')
                
                cwd = getcwd()
                
                details = traceback.format_exc()
                details = '>>' + details.replace('\\n', '\n').replace(cwd, '..')
                
                log(details, nots = True)

                if customKpi(kpis[0]):
                    if e.type != dbException.CONN:
                    #if True or str(e)[:22] == '[db]: sql syntax error':
                        log('yesNoDialog ---> disable %s?' % (kpiSrc))
                        reply = yesNoDialog('Error: custom SQL exception', 'SQL for custom KPIs %s terminated with the following error:\n\n%s\n\n Disable this KPI source (%s)?' % (', '.join(kpis), str(e), kpiSrc), parent=wnd)
                    else:
                        log('Custom KPI exception: ' + str(e), 2)
                        # ?
                        pass

                if reply == True:
                    # need to mark failed kpis as disabled
                    
                    badSrc = kpiSrc                    
                    
                    for kpi in kpiStylesNNN:
                        if kpiStylesNNN[kpi]['sql'] == badSrc:
                            kpiStylesNNN[kpi]['disabled'] = True
                            
                            log('disable custom kpi due to exception: %s%s' % (badSrc, kpi))

                            #also destroy the if already exist (from previous runs)
                            if kpi in data:
                                del(data[kpi])

                            # allOk = False
                            
                elif reply == False:
                    log('[W] Custom KPI exception ignored, so we just continue.', 2)
                else:
                    #reply = None, it was not a custom KPI, most likely a connection issue
                    self.connection = None
                    
                    log('[!] getHostKpis (%s) failed: %s' % (str(kpis), str(e)))
                    raise e
                    
            except Exception as e:
                    log('[!] dont know how to handle exception: %s, %s' % (str(kpis), str(e)))
                    raise e
                
        self.renewKeepAlive()
        
        # self.lock = False

        #print('before clnp', kpiIn)
        #remove disabled stuff
        
        for kpi in kpiIn.copy():
            #print('kpi: ', kpi)
            
            if kpi not in kpiStylesNNN or 'disabled' in kpiStylesNNN[kpi]:
                # this will affect the actual list of enabled kpis, which is good!
                kpiIn.remove(kpi)
                
        #print('after clnp', kpiIn)
        
        return 

    def getGanttData(self, kpiStylesNNN, kpi, data, sql, params, kpiSrc, tzShift, tzUTC):
        
        @profiler
        def normalizeGradient(brMin, brMax, fromTo = (0, 100)):
        
            (targetMin, targetMax) = fromTo
            #(targetMax, targetMin) = fromTo # I like it reversed...
            
            if cfg('dev'):
                log('Gantt gradient normalization', 5)
                log('targetMax %i,  targetMin %i' % (targetMax, targetMin), 5)
            
            delta = brMin
            
            if brMax != brMin:
                k = (targetMax - targetMin)/(brMax - brMin)
            else:
                k = 1
            
            for entity in data[kpi]:
                for i in range(len(data[kpi][entity])):
                    if cfg('dev'):
                        log('  %i -> %.2f' % (data[kpi][entity][i][5], ((data[kpi][entity][i][5] - delta) * k + targetMin)/100), 5)
                        
                    data[kpi][entity][i][5] = ((data[kpi][entity][i][5] - delta) * k + targetMin)/100
        
        try:
            #rows = db.execute_query(self.connection, sql, params)
            rows_list, cols_list, dbCursor, psid = self.dbi.execute_query_desc(self.connection, sql, params, None)
        except dbException as e:
            log('[!] db gantt execute_query: %s' % str(e))
            raise dbException(str(e), e.type)
        except Exception as e:
            log('[!] gantt execute_query: %s' % str(e))
            raise dbException('[db]: ' + str(e))


        tIndex = None
        brIndex = None
        cIndex = None
        
        rows = rows_list[0]
        
        log('Executed okay, %i rows' % len(rows))

        if len(rows) == 0:
            data[kpi] = {}
            
            '''
            we need to check if kpi is in data at all first, then...
            
            # should we iterrate through the entities and clear?... not sure
            
            if len(data[kpi]) > 0:
                data[kpi].clear() 
            '''
                
            return

        for i in range(len(cols_list[0])):
            col = cols_list[0][i]

            br = kpiStylesNNN[kpi].get('gradient')
            
            if br and col[0] == 'GRADIENT': #'GRADIENT'
                brIndex = i
                
                brMin = rows[0][brIndex]
                brMax = rows[0][brIndex]

            if col[0] == 'TITLE':
                tIndex = i

            if col[0] == 'COLOR':
                cIndex = i

        data[kpi] = {}
        
        t0 = time.time()
        
        titleValue = None
        brValue = None
        
        j = 0
        
        t1 = time.time()
        t1000 = t1
        
        lastShift = {}      #last index for each shift per entity, lastShift[entity][shift] = some index in data[kpi][entity] array

        for r in rows:
            entity = str(r[0])

            start = r[1]
            stop = r[2]

            if utils.cfg_servertz:
                start = utils.setTZ(start, tzUTC)
                stop = utils.setTZ(stop, tzUTC)

            start = start + datetime.timedelta(seconds=tzShift)
            stop = stop + datetime.timedelta(seconds=tzShift)

            dur = formatTime((stop - start).total_seconds(), skipSeconds=True, skipMs=True)
            desc = str(r[3]).replace('$duration', dur)

            if tIndex:
                titleValue = r[tIndex]

            if brIndex is not None:
                brValue = r[brIndex]
                
                if brValue > brMax:
                    brMax = brValue

                if brValue < brMin:
                    brMin = brValue
            else:
                if cIndex:
                    brValue = r[cIndex]
            
            # go through entities
            t1 = time.time()
            
            if entity in data[kpi]:
                shift = 0
                i = 0
                
                ls = lastShift[entity]
                #print('initial ls:', ls)

                # old approach description:
                # now for each bar inside the entity we check if there is something
                # still runing with the same shift
                
                # we are sure if something ends after start of current bar it is an intersection
                # because data is sorted by start ascending
                
                dataSize = len(data[kpi][entity])
                
                entry = data[kpi][entity]
                
                
                # shift calculator here:
                
                    
                #print('shift is: ', shift)

                if cfg('ganttOldImplementation', False):
                    # performance inefficient one
                    bkp = 0
                    while i < dataSize:
                        #print('%i/%i,  test if %s < %s' % (i, dataSize, start.strftime('%H:%M:%S'), data[kpi][entity][i][1].strftime('%H:%M:%S')))

                        if shift == entry[i][3] and start < entry[i][1]:
                            shift += 1
                            
                            i = 0   # and we need to check from the scratch
                        else:
                            i += 1
                else:
                    for shift in ls:
                        i = ls[shift]
                        
                        #t = start < entry[i][1] #intersect?
                        #print('%i,  test if %s < %s -->' % (shift, start.strftime('%H:%M:%S'), entry[i][1].strftime('%H:%M:%S')), t)
                        
                        if start < entry[i][1]: #we got an intersection, shift up!
                            #print('continue')
                            continue
                        else:
                            # no intersection in this shift, stop
                            break
                    else:
                        # did not detect any empty slot --> generate new entry
                        shift += 1
                        pass

                '''
                    #not a very improving attempt:
                    
                    bkp = 0
                    while i < dataSize:
                        if start < entry[i][1]: # if intersects...
                            if shift == entry[i][3]:
                                shift += 1
                                i = bkp
                        else:
                            bkp = i

                        i += 1
                '''

                ls[shift] = dataSize
                
                #print('final ls: ', ls)
                
                data[kpi][entity].append([start, stop, desc, shift, titleValue, brValue])
            else:
                data[kpi][entity] = [[start, stop, desc, 0, titleValue, brValue]]
                lastShift[entity] = {}
                lastShift[entity][0] = 0
                
            t2 = time.time()
            
            j += 1
            
            if t2 - t0 > 10 and j % 1000 == 0:
                log('Gantt render time per row: %i, %s, per 1000 = %s, cumulative: %s, and still running...' % (j, str(round(t2-t1, 3)), str(round(t2 - t1000, 3)), str(round(t2-t0, 3))), 2)
                t1000 = t2
        
        t2 = time.time()
        
        if t2 - t0 > 1:
            log('Gantt render time: %s' % (str(round(t2-t0, 3))), 3)
        
        if brIndex is not None:
            normalizeGradient(brMin, brMax)
        
            t3 = time.time()
            log('Gantt gradient normalization time: %s' % (str(round(t3-t2, 3))), 3)
        
        '''
        for e in data[kpi]:
            print('entity:', e)
            
            for i in data[kpi][e]:
                print(i[2], i[0], i[1], i[3])
        '''
    
    @profiler
    def getHostKpis(self, kpiStylesNNN, kpis, data, sql, params, kpiSrc, tzShift, tzUTC):
        '''
            performs query to a data source for specific host.port
            also for custom metrics
            
            sql - ready to be executed SQL
        '''
        
        def printDump(data):
            for k in data:
                print('[%s]' % k)
                
                if  isinstance(data[k][0], int):
                    print('\t', data[k])
                else:
                    i = 0
                    print('type: ', type(data[k][0]))
                    for x in range(len(data[k])):
                        # print('\t%i -'%(i), r)
                        if x > 0:
                            print(f'{i:3}, {x=} {data[k][x]}, delta = {data[k][x]-data[k][x-1]}')
                        else:
                            print(f'{i:3}, {x=} {data[k][x]}')
                        i += 1
            
        @profiler
        def multilineStats(rows, kpis, orderby, desc):
            
            #for r in rows:
            #    print(r)
            #print(kpis)
            
            t0 = time.time()
            gb = []
            
            gbs = {} #dict of lists for group by, key = groupby name, elements: 0 - min, 1 - max, 2 - avg
            
            t = None
            tCount = 0
            
            gbi = 1 + len(kpis) # groupby index = time + kpis + 1
            
            for row in rows:
                if row[0] != t:
                    t = row[0]
                    tCount += 1

                grpby = row[gbi]

                if grpby not in gb:
                    gb.append(row[gbi])
                    
                v = row[1]
                    
                if grpby not in gbs:
                    gbs[grpby] = [v, v, v]
                else:
                    if gbs[grpby][0] > v and v != -1:
                        gbs[grpby][0] = v

                    if gbs[grpby][1] < v:
                        gbs[grpby][1] = v

                    if gbs[grpby][1] > 0:
                        gbs[grpby][2] += v
                        
            #print(gbs)
            
            if orderby == 'max': 
                gbsSorted =  sorted(gbs, key=lambda x: (gbs[x][1]), reverse=desc)
            elif orderby == 'avg': 
                gbsSorted =  sorted(gbs, key=lambda x: (gbs[x][2]), reverse=desc)
            elif orderby == 'deviation': 
                gbsSorted =  sorted(gbs, key=lambda x: (gbs[x][1] - gbs[x][0]), reverse=desc)
            elif orderby == 'name': 
                gbsSorted =  sorted(gbs, key=lambda x: (x), reverse=desc)
            else:
                gbsSorted =  sorted(gbs, key=lambda x: (gbs[x][1]), reverse=desc)
            
            gb.sort()
            
            t1 = time.time()
            
            log('multiline Stats processing: %s' % (str(round(t1-t0, 3))), 4)
            
            return tCount, gbsSorted

        t0 = time.time()
        
        try:
            rows = self.dbi.execute_query(self.connection, sql, params)
        except dbException as e:
            log('[!] db execute_query: %s' % str(e))
            raise dbException(str(e), e.type)
        except Exception as e:
            log('[!] execute_query: %s' % str(e))
            raise dbException('[db]: ' + str(e))
            
        if len(kpis) > 0:
            #print(kpis, kpiSrc)
            subtype = kpiStylesNNN[kpis[0]].get('subtype')
        
        trace_lines = len(rows)
        
        t1 = time.time()
        
        if kpiSrc == '-':
            timeKey = 'time'
        else:
            timeKey = 'time:' + kpiSrc

        kpis_ = [timeKey] + kpis # need a copy of kpis list (+time entry)
        
        multiline = False
        
        if subtype == 'multiline':
            multiline = True
            others = False
            
            gb = []
            
            stacked = kpiStylesNNN[kpis[0]]['stacked']
            stacked = processVars(kpiSrc, stacked)
            stacked = safeBool(stacked)
            
            orderby = kpiStylesNNN[kpis[0]]['orderby']
            orderdesc = kpiStylesNNN[kpis[0]]['descending']
            
            others = kpiStylesNNN[kpis[0]].get('others')
            
            if others:
                others = processVars(kpiSrc, others)
                others = safeBool(others)
                
                if others:
                    lc = kpiStylesNNN[kpis[0]]['legendCount']
                    lc = processVars(kpiSrc, lc)
                    lc = safeInt(lc, 5)
                    others = lc
            
        i = 0 # just the loop iterration number (row number)
        ii = 0 # data index counter, equals to the row number for regular kpis and very not for multiline...

        t = None
        
        try:
            
            if len(rows) == 0:
                for key in data:
                    if key in kpis_:
                        data[key].clear()

            for row in rows:
            
                #print(i, ii, row[0], row[1])
            
                if i == 0: # allocate memory
                
                    if multiline:
                    
                        '''
                            the data[k] for multiline kpi will be a list and it will look like this:
                            data[timekey] - usual list
                            data[mlKpi] - list of two values 'groupby label', [values (one per timestamp]
                            data[mlKpi][0] - label
                            data[mlKpi][1] - values array similar to regular kpi
                            data[mlKpi][2] - list (tuple) of max/last values for the legend
                            max and last calculated in.... for the consistensy.
                            
                            [time:02_memory_components.yaml]
                                    0 - 1630517953.107
                                    1 - 1630518009.033
                                    2 - 1630518069.035
                                    3 - 1630518129.041
                                    4 - 1630518189.096
                                    5 - 1630518253.407
                                    6 - 1630518309.044
                                    7 - 1630518369.043
                                    
                            [cs-allocator]
                                    0 - ['Column Store Tables', [464118236, 464118236, 464118236, 464118236, 464118236, 464118236, 464118236, 464118236]]
                                    1 - ['System', [453584127, 450314181, 450317757, 450578589, 450412413, 431187386, 431186706, 431189802]]
                                    2 - ['Statement Execution & Intermediate Results', [369756384, 312537013, 312537061, 311471349, 311486077, 288974322, 288897930, 291208874]]
                                    3 - ['Row Store Tables', [214905584, 214905584, 214905584, 214905584, 214906400, 214905584, 214905584, 214905584]]
                                    4 - ['Caches', [153347011, 131180488, 131180488, 131180392, 132221968, 133214824, 133399136, 133399232]]
                                    5 - ['Monitoring & Statistical Data', [67250464, 67251328, 67259376, 67248672, 67288496, 67319056, 67272912, 67314992]]                            
                        '''
                    
                        tCount, gb = multilineStats(rows, kpis, orderby, orderdesc)
                        
                        gbi = 1 + len(kpis) # groupby index = time + kpis + 1
                        
                        gbc = len(gb) #groupby count
                        
                        for j in range(0, len(kpis_)):
                            if j == 0: #time
                                data[timeKey] = [0] * (tCount)
                                log('allocate data[%s]: %i' %(timeKey, tCount), 5)
                            else:
                                data[kpis_[j]] = [None] * gbc
                                log('allocate data[%s]: %i' %(kpis_[j], gbc), 5)
                                
                                for k in range(0, gbc):
                                    data[kpis_[j]][k] = [None] * 2
                                    data[kpis_[j]][k][0] = gb[k]
                                    data[kpis_[j]][k][1] = [-1] * (tCount)
                                    log('allocate data[%s]/%i: %i' %(kpis_[j], k, tCount + 1), 5)

                        t = row[0]
                        #printDump(data)
                        
                    else:
                    
                        for j in range(0, len(kpis_)):
                        
                            if j == 0: #time
                                data[timeKey] = [0] * (trace_lines)  #array('d', [0]*data_size) ??
                                log('allocate data[%s]: %i' %(timeKey, trace_lines), 4)
                            else:
                                '''
                                if kpis_[j] in data:
                                    log('clean data[%s]' % (kpis_[j]))
                                    del(data[kpis_[j]]) # ndata is a dict
                                '''
                                    
                                #log('allocate %i for %s' % (trace_lines, kpis_[j]))
                                data[kpis_[j]] = [0] * (trace_lines)  #array('l', [0]*data_size) ??
                                log('allocate data[%s]: %i' %(kpis_[j], trace_lines), 4)

                if multiline:
                    if t != row[0]:
                        #next time frame
                        
                        t = row[0]
                        ii += 1
                        
                else:
                    ii = i # it is one step behind for some reason
                    
                for j in range(0, len(kpis_)):
                    if j == 0: #time column always 1st
                        ts = row[j]

                        if utils.cfg_servertz:
                            ts = utils.setTZ(ts, tzUTC) # set explicit timezone

                        tzdelta = self.dbProperties.get('utcOffset', 0)

                        tsi = ts.timestamp()
                        data[timeKey][ii] = tsi + tzShift
                        
                    else:

                        rawValue = row[j]

                        if multiline:
                            gbv = row[gbi]
                            k = gb.index(gbv)
                            
                            data[kpis_[j]][k][1][ii] = int(rawValue)
                            
                        else:
                    
                            if rawValue is None:
                                data[kpis_[j]][i] = -1
                            else:
                                if 'perSample' in kpiStylesNNN[kpis_[j]]:
                                
                                    # /sample --> /sec
                                    # do NOT normalize here, only devide by delta seconds

                                    if i == 0:
                                        if len(data[timeKey]) > 1:
                                            normValue = rawValue / (data[timeKey][1] - data[timeKey][0])
                                        else:
                                            normValue = -1 # no data to calculate
                                    else:
                                        normValue = rawValue / (data[timeKey][i] - data[timeKey][i-1])
                                    
                                    data[kpis_[j]][i] = int(normValue)
                                else:
                                    #normal values
                                    data[kpis_[j]][i] = int(rawValue) # integer only zone
                
                i+=1
                    
        except ValueError:
            log('non-integer kpi value returned: %s' % (str(row[j])))
            raise Exception('Integer only allowed as kpi value')

        
        # postprocessing after data extraction loop 
        
        #kpis_ = ['time:02_2_heap_allocators.yaml', 'cs-allocator']

        if multiline and others and others >= len(gb):
            # there is no enough group by entries to have also 'others'
            others = False

        if multiline and others and kpis_[0] in data:
        
            t00 = time.time()
        
            frames = len(data[kpis_[0]]) # must be time line
            othersData = [-1] * (frames)
            
            for j in range(1, len(kpis_)):
                kpi = kpis_[j]
                                
                scan = data[kpi]
                                
                for i in range(frames):
                    
                    others_value = -1 
                    for gbi in range(len(gb)):
                    
                        if gbi >= others and scan[gbi][1][i] > 0:
                        
                            if others_value == -1: # otherwise we will have decreased values because of th initial 1
                                others_value = 0
                                
                            others_value += scan[gbi][1][i]
                            
                    if others_value >= 0:
                        othersData[i] = others_value
            
                # explicitly (hopefuly) deallocate everything above 'others'

                for gbi in range(others+1, len(gb)):
                    data[kpi][gbi][1].clear()
                    data[kpi][gbi].clear()
                    
                del data[kpi][others+1:]
        
                # now need to replace N+1 whith others and delete all the rest data and kpis

                data[kpi][others][0] = 'Others'
                data[kpi][others][1] = othersData
                    
            gb = gb[:others] # compensate gb list as it is calculates above for all entries
            gb.append('Others')
            
            t01 = time.time()
            
            log('Multiline \'others\' processing time: %s' % str(round(t01-t00, 3)), 4)
                    
        # stacked to be processed separately...
        if multiline and stacked and kpis_[0] in data:
            # kpis_[0] in data actually checks if the data dict actuallny not empty, otherwise fails in "frames = len(data[kpis_[0]]) # must be time line"
        
            t00 = time.time()

            #print('kpis_', kpis_)
            #print('gb', gb)
            #print('gbi', gbi)
            #print('gbv', gbv)
            
            #printDump(data)
            
            for j in range(1, len(kpis_)):
                kpi = kpis_[j]
                
                #print('kpi:', kpi)
                #print(data.keys())
                
                frames = len(data[kpis_[0]]) # must be time line
                scan = data[kpi]
                
                #print('frames', frames)
                
                for i in range(frames):
                    # print(i)
                    
                    acc_value = -1 # have to make it -1 to be consistent with all the other kpis
                    
                    for gbi in range(len(gb)):
                    
                        if scan[gbi][1][i] > 0:             # otherwise consistent decreases the stacked values, #568
                        
                            if acc_value == -1:
                                # otherwise accumulated values are -1
                                acc_value = 0
                                
                            acc_value += scan[gbi][1][i]
                            
                        scan[gbi][1][i] = acc_value
                        
            t01 = time.time()
            
            log('Multiline \'stacked\' processing time: %s' % str(round(t01-t00, 3)), 4)

        t2 = time.time()

        log('%i rows, get time: %s, get/parse time %s' % (trace_lines, str(round(t1-t0, 3)), str(round(t2-t1, 3))))
        # printDump(data)
