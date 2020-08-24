from PyQt5.QtCore import QObject

from array import array

import pyhdb
import time

import datetime

from PyQt5.QtCore import QTimer

import dpDBCustom, kpiDescriptions
from kpiDescriptions import customKpi
from kpiDescriptions import kpiStylesNN

from PyQt5.QtCore import pyqtSignal

import sql

import db

from utils import cfg, log, yesNoDialog
from utils import dbException

class dataProvider():
    
    connection = None
    server = None
    timer = None
    timerkeepalive = None
    dbProperties = {}
    
    # lock = False
    
    def __init__(self, server):
    
        super().__init__()
    
        log('connecting to %s:%i...' % (server['host'], server['port']))
        
        try: 
            conn = db.create_connection(server, self.dbProperties)
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
            log('closing conection')
            close_connection(self.connection)
            self.connection = None
            log('closed')
            
        self.server = None
            
        return
            
            
    def reconnect(self):
        try: 
            conn = db.create_connection(self.server)
        except Exception as e:
            raise e
        
        if conn is None:
            log('[i] Failed to reconnect, dont know what to do next')
            raise Exception('Failed to reconnect, dont know what to do next...')
        else:
            log('re-connected')
            self.connection = conn
        
    def enableKeepAlive(self, window, keepalive):
        log('Setting up DB keep-alive requests: %i seconds' % (keepalive))
        self.timerkeepalive = keepalive
        self.timer = QTimer(window)
        self.timer.timeout.connect(self.keepAlive)
        self.timer.start(1000 * keepalive)
        
    def renewKeepAlive(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer.start(1000 * self.timerkeepalive)
    
    def keepAlive(self):
    
        if self.connection is None:
            log('no connection, disabeling the keep-alive timer')
            self.timer.stop()
            return

        try:
            log('chart keep alive... ', False, True)
            
            t0 = time.time()
            db.execute_query(self.connection, 'select * from dummy', [])
            
            if hasattr(self, 'fakeDisconnect'):
                print ('generate an exception...')
                print (10/0)
            
            t1 = time.time()
            log('ok: %s ms' % (str(round(t1-t0, 3))), True)
        except dbException as e:
            log('Trigger autoreconnect...')
            try:
                conn = db.create_connection(self.server)
                if conn is not None:
                    self.connection = conn
                    log('Connection restored automatically')
                else:
                    log('Some connection issue, give up')
                    self.timer.stop()
                    self.connection = None
            except:
                log('Connection lost, give up')

                self.timer.stop()
                self.connection = None
        except Exception as e:
            log('[!] unexpected exception, disable the connection')
            log('[!] %s' % str(e))
            self.connection = None
        
            
    def initHosts(self, hosts, hostKPIs, srvcKPIs):
    
        # kpis_sql = 'select view_name, column_name, display_line_color, display_line_style from m_load_history_info order by display_hierarchy'
        #kpis_sql = 'select view_name, column_name from m_load_history_info order by display_hierarchy'
        kpis_sql = sql.kpis_info

        if not self.connection:
            log('no db connection...')
            return

        log('init hosts: %s' % str(hosts))
        log('init hosts, hostKPIs: %s' % str(hostKPIs))
        log('init hosts, srvcKPIs: %s' % str(srvcKPIs))

        sql_string = sql.hosts_info

        t0 = time.time()
        
        rows = db.execute_query(self.connection, sql_string, [])
        
        for i in range(0, len(rows)):
            hosts.append({
                        'host':rows[i][0],
                        'port':rows[i][1],
                        'from':rows[i][2],
                        'to':rows[i][3]
                        })

        rows = db.execute_query(self.connection, kpis_sql, [])
        
        for kpi in rows:
        
            if kpi[1].lower() == 'm_load_history_host':
                type = 'host'
            else:
                type = 'service'
        
            if kpi[1] == '': #hierarchy nodes
                if len(kpi[0]) == 1:
                    continue # top level hierarchy node (Host/Service)
                else:
                    # Normal hierarchy node
                    kpiName = '.' + kpi[4]
            else:
                kpiName = kpi[2].lower()
                kpiDummy = {
                        'hierarchy':    kpi[0],
                        'type':         type,
                        'name':         kpiName,
                        'group':        kpi[3],
                        'label':        kpi[4],
                        'description':  kpi[5],
                        'sUnit':        kpi[6],
                        'dUnit':        kpi[7],
                        'color':        kpi[8],
                        'style':        kpiDescriptions.nsStyle(kpi[9])
                    }
                
                kpiStylesNN[type][kpiName] = kpiDescriptions.createStyle(kpiDummy)
                        
            if kpi[1].lower() == 'm_load_history_host':
                hostKPIs.append(kpiName)
            else:
                srvcKPIs.append(kpiName)

        t1 = time.time()

        dpDBCustom.scanKPIsN(hostKPIs, srvcKPIs, kpiDescriptions.kpiStylesNN)

        t2 = time.time()
        
        kpiDescriptions.clarifyGroups()
        
        log('hostsInit time: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))
        
    def splitKpis(self, type, kpis):
        '''
            devides KPIs per source
            '-' entry will contain default ones (m_load_history_...)
        '''
        kpisList = {}
        kpisList['-'] = []
        
        for kpi in kpis:
            if customKpi(kpi):
                src = kpiDescriptions.kpiStylesNN[type][kpi]['sql']
                if src in kpisList:
                    kpisList[src].append(kpi)
                else:
                    kpisList[src] = [kpi]
            else:
                kpisList['-'].append(kpi)
                        
        return kpisList
    def getData(self, host, fromto, kpiIn, data):
        '''
            returns boolean
            False = some kpis were disabled due to sql errors
        '''
                
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
            
            
        '''
        if self.lock:
            log('[w] getData lock set, exiting')
            return
        '''

        if self.connection is None:
            raise dbException('No valid db connection')
            
        # self.lock = True
        
        params = []
    
        kpiList = self.splitKpis(type, kpiIn)
        
        print('split kpis: ', kpiList)

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
                    tfilter = " and time > add_seconds(now(), -3600 * ?)"
                else:
                    params.append(fromto['from'])
                    tfilter = " and time > ?"

            elif fromto['from'] == '' and fromto['to'] != '':
                params.append(fromto['to'])
                tfilter = " and time < ?"
            else:
                params.append(fromto['from'])
                params.append(fromto['to'])
                
                tfilter = " and time between ? and ?"
                
        else:
            # ????
            tfilter = " and time > add_seconds(now(), -3600*12)"
        
        # allOk = True
        
        # loop through kpi sources
        for kpiSrc in kpiList.keys():
            kpisSql = []
            kpis = kpiList[kpiSrc]
            
            if len(kpis) == 0:
                continue
                
            if host['port'] == '':
                if kpiSrc == '-':
                    fromTable = 'from m_load_history_host'
                else:
                    fromTable = 'from (%s)' % kpiDescriptions.customSql[kpiSrc]
            else:
                if kpiSrc == '-':
                    fromTable = 'from m_load_history_service'
                else:
                    fromTable = 'from (%s)' % kpiDescriptions.customSql[kpiSrc]
                                
            for kpi in kpis:
                if kpiSrc == '-':
                    kpisSql.append(kpi)
                else:
                    kpisSql.append(kpiDescriptions.kpiStylesNN[type][kpi]['sqlname'])
                    
            cols = ', '.join(kpisSql)
            
            sql = '%s %s %s %s%s %s' % (sql_pref, cols, fromTable, hfilter, tfilter, orderby)
            
            '''
            print('sql_pref', sql_pref)
            print('cols', cols)
            print('fromTable', fromTable)
            print('hfilter', hfilter)
            print('tfilter', tfilter)
            print('orderby', orderby)
            '''
            
            #if gantt to be checked here
            
            gantt = False
            
            if len(kpis) == 1: #only one kpi can be in gantt data source
                kpi = kpis[0]
                
                if kpiDescriptions.getSubtype(type, kpi) == 'gantt':
                    
                    tfilter_mod = tfilter.replace('time', '"START"')
                
                    #sql = 'select entity, "START", "STOP", details %s %s%s order by entity, "START" desc' % (fromTable, hfilter, tfilter_mod)
                    #sql = 'select entity, "START", "STOP", details %s %s%s order by entity, seconds_between("START", "STOP") desc' % (fromTable, hfilter, tfilter_mod)
                    sql = 'select entity, "START", "STOP", details %s %s%s order by entity, "START"' % (fromTable, hfilter, tfilter_mod)
                    gantt = True                    

            try:
                if not gantt:
                    self.getHostKpis(type, kpis, data, sql, params, kpiSrc)
                else:
                    self.getGanttData(type, kpis[0], data, sql, params, kpiSrc)
                    
            except Exception as e:
            
                reply = False
                
                if customKpi(kpis[0]):
                    if True or str(e)[:22] == '[db]: sql syntax error':
                        log('yesNoDialog ---> disable %s?' % (kpiSrc))
                        reply = yesNoDialog('Error: custom SQL exception', 'SQL for custom KPIs %s terminated with the following error:\n\n%s\n\n Disable this KPI source (%s)?' % (', '.join(kpis), str(e), kpiSrc))
                    else:
                        log('Custom KPI exception: ' + str(e))
                        # ?
                        pass

                if reply == True:
                    # need to mark failed kpis as disabled
                    
                    #badSrc = kpiDescriptions.kpiStylesNN[type][kpis[0]]['sql']
                    badSrc = kpiSrc                    
                    
                    for kpi in kpiDescriptions.kpiStylesNN[type]:
                        if kpiDescriptions.kpiStylesNN[type][kpi]['sql'] == badSrc:
                            kpiDescriptions.kpiStylesNN[type][kpi]['disabled'] = True
                            
                            log('disable custom kpi due to exception: %s%s' % (badSrc, kpi))

                            #also destroy the if already exist (from previous runs)
                            if kpi in data:
                                del(data[kpi])

                            # allOk = False
                            
                else:
                    self.connection = None
                    
                    log('[!] getHostKpis (%s) failed: %s' % (str(kpis), str(e)))
                    raise e
                
        self.renewKeepAlive()
        
        # self.lock = False

        #print('before clnp', kpiIn)
        #remove disabled stuff
        
        for kpi in kpiIn.copy():
            #print('kpi: ', kpi)
            if 'disabled' in kpiDescriptions.kpiStylesNN[type][kpi]:
                # this will affect the actual list of enabled kpis, which is good!
                kpiIn.remove(kpi)
                
        #print('after clnp', kpiIn)
        
        return 

    def getGanttData(self, type, kpi, data, sql, params, kpiSrc):
        
        try:
            rows = db.execute_query(self.connection, sql, params)
        except Exception as e:
            log('[!] execute_query: %s' % str(e))
            #raise dbException('Database Exception')
            raise dbException('[db]: ' + str(e))
            
        log('Executed okay, %i rows' % len(rows))
        
        data[kpi] = {}
        
        for r in rows:
            
            entity = str(r[0])
            start = r[1]
            stop = r[2]
            desc = r[3]
               
            #print ('curr: %s - %s' % (str(start), str(stop)))
            
            if entity in data[kpi]:
                last = data[kpi][entity][-1]
                
                print ('last: %s - %s' % (str(last[0]), str(last[1])))
                
                if start < last[1]:
                    shift = last[3] + 1
                else:
                    shift = 0
                    
                data[kpi][entity].append([start, stop, desc, shift])
            else:
                data[kpi][entity] = [[start, stop, desc, 0]]
    
    def getHostKpis(self, type, kpis, data, sql, params, kpiSrc):
        '''
            performs query to a data source for specific host.port
            also for custom metrics
        '''

        t0 = time.time()
        
        try:
            rows = db.execute_query(self.connection, sql, params)
        except Exception as e:
            log('[!] execute_query: %s' % str(e))
            #raise dbException('Database Exception')
            raise dbException('[db]: ' + str(e))
        
        trace_lines = len(rows)
        
        t1 = time.time()
        
        i = 0
        
        if kpiSrc == '-':
            timeKey = 'time'
        else:
            timeKey = 'time:' + kpiSrc

        kpis_ = [timeKey] + kpis # need a copy of kpis list (+time entry)
        
        try:
            '''
            for j in range(len(kpis)):
                if 'perSample' in kpiStylesNN[type][kpis[j]]:
                    p rint('%s --> adjust!!!' % (kpis[j]))
                    p rint('%s --> %s' % (kpiStylesNN[type][kpis[j]]['sUnit'], kpiStylesNN[type][kpis[j]]['dUnit']))
            '''
        
            for row in rows:
                if i == 0: # allocate memory
                    
                    for j in range(0, len(kpis_)):
                    
                        if j == 0: #time
                            data[timeKey] = [0] * (trace_lines)  #array('d', [0]*data_size) ??
                            log('allocate data[%s]: %i' %(timeKey, trace_lines))
                        else:
                            '''
                            if kpis_[j] in data:
                                log('clean data[%s]' % (kpis_[j]))
                                del(data[kpis_[j]]) # ndata is a dict
                            '''
                                
                            #log('allocate %i for %s' % (trace_lines, kpis_[j]))
                            data[kpis_[j]] = [0] * (trace_lines)  #array('l', [0]*data_size) ??
                            log('allocate data[%s]: %i' %(kpis_[j], trace_lines))

                for j in range(0, len(kpis_)):
                    if j == 0: #time column always 1st
                        data[timeKey][i] = row[j].timestamp()
                    else:
                        rawValue = row[j]
                        if rawValue is None:
                            data[kpis_[j]][i] = -1
                        else:
                            if 'perSample' in kpiStylesNN[type][kpis_[j]]:
                            
                                # /sample --> /sec
                                # do NOT normalize here, only devide by delta seconds

                                if i == 0:
                                    normValue = rawValue / (data[timeKey][1] - data[timeKey][0])
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

        t2 = time.time()

        log('%i rows, get time: %s, get/parse time %s' % (trace_lines, str(round(t1-t0, 3)), str(round(t2-t1, 3))))
    