from datetime import datetime

from array import array
import math

import kpiDescriptions

import time

import kpis
import re

from utils import log

def getKPI(kName):

    for k in kpis.mapKPIs:
        if k[0].lower() == kName:
            return(k[1], k[2])
            
    return None, None

def getKpiDesc(type, kName):

    if type == 'host':
        source  = 'M_LOAD_HISTORY_HOST'
    else:
        source  = 'M_LOAD_HISTORY_SERVICE'

    for kpi in kpis.kpis:
        if kpi[1] == source and kpi[2] == kName:
            return list(kpi)
            
    return None


class dataProvider:

    options = []
    
    def __init__(self, files, timezone_offset=None):
        self.files = []
        
        self.data = {}
        self.ports = []
        self.lastIndx = []
        
        self.TZShift = 0
        
        if len(files) == 1:
            m = re.search('_utc(-?)(\d+)\.trc$', files[0], flags=re.IGNORECASE)
            
            if m is not None:
                sign = m.groups()[0]
                utc_offset = m.groups()[1]
                
                utc_offset = int(utc_offset)
                
                if sign == '-':
                    timezone_offset = -1 * utc_offset
                    
                if sign == '':
                    timezone_offset = utc_offset
                    
                log('trace timezone_offset owerriden due to filename containing utc shift, change the filename to avoid that', 2)
        
        if timezone_offset is not None:
        
            # same logic as in dbi_extention, but probably the opposite side
            dbUTCDelta = timezone_offset

            hostNow = datetime.now().timestamp()
            hostUTCDelta = (datetime.fromtimestamp(hostNow) - datetime.utcfromtimestamp(hostNow)).total_seconds()
            
            self.TZShift = int(dbUTCDelta) - int(hostUTCDelta)
            
            log(f'trace import using UTC offset: {dbUTCDelta}, calculated shift: {self.TZShift}', 2)
        
        
        self.supportedKPIs = ['indexserverCpu', 'indexserverMemUsed', 'indexserverMemLimit']

        self.files = files
        log('trace dp: %s' % str(files))
        
    def close(self):
        pass

    def initHosts(self, hosts, hostKPIs, srvcKPIs):
        '''
            performs initial load, extract hosts and metadata
            
            plus actual KPIs data loaded and calculated
            
            KPIDescriptions? not sure
            
        '''
    
        max_lines = 0
        row_len = 0
        
        ii = {} # row counter per port
        
        data = self.data
        
        for filename in self.files:
            t0 = time.time()
            
            if max_lines > 0:
                trace_lines = max_lines
            else:
                trace_lines = len(open(filename).readlines())
                
            f = open(filename)
            
            #scan first lines to count number of ports
            i = -1 
            host = ''
            for line in f:
                row = line.rstrip().split(';')
                
                if i == -1: # header row
                    #titles = row
                    
                    titles = []
                    
                    for r in row:
                        titles.append(r.lower())

                    row_len = len(row)
                    
                    if 'port' in titles:
                        portIdx = titles.index('port')
                    elif 'tenant' in titles:
                        portIdx = titles.index('tenant')
                    else:
                        portIdx = None
                        
                    hostIdx = titles.index('host')
                    
                else:
                
                    if portIdx is not None:
                        port = row[portIdx]
                    else:
                        port = 0
                    
                    if host == '':
                        host = row[hostIdx]
                    
                    if port in self.ports:
                        #break
                        continue
                    else:
                        self.ports.append(port)
                
                i += 1
                
            trace_lines = int((trace_lines - 1) / i)
            
            t1 = time.time()
            log('ports: %s' % str(self.ports))
            log('ports scan time: %s' % str(round(t1-t0, 3)))

            rows = []
            for kpi in titles:
                (type, kpiName) = getKPI(kpi)
                
                if type:
                    
                    desc = (getKpiDesc(type, kpiName))
                    
                    #desc[4] = int(desc[4])
                    
                    if desc is not None:
                    
                        desc[2] = kpi # replace name by nameserver naming...
                    
                        try:
                            desc[3] = int(desc[3])  #group
                            desc[8] = int(desc[8])  #color
                            desc[9] = int(desc[9])  #style
                        except:
                            log('--> kpi style exception: %s, %s, %s' % (desc[3], desc[8], desc[9]), 2)
                            
                        rows.append(desc)
                        
                    else:
                        log('KPI %s not defined in default kpis description' % kpi, 3)
                            
                else:
                    log('KPI %s not defined in nameserver mapping' % kpi, 6)

                
            kpiDescriptions.initKPIDescriptions(rows, hostKPIs, srvcKPIs)
            
            t1 = time.time()
            
            log('lines per port: %i' % trace_lines)
            log('init time: %s' % str(round(t1-t0, 3)))
            
            # allocate stuff
            for port in self.ports:
            
                #data[port] = [0]* (row_len)
                if port == '':
                    data[port] = [0]* (len(hostKPIs)+1)
                else:
                    data[port] = [0]* (len(srvcKPIs)+1)
                
                ii[port] = 0
                
                if port == '':
                    for i in range(0, len(hostKPIs)+1):
                        data[port][i] = [-1]* (trace_lines + 1)
                else:
                    for i in range(0, len(srvcKPIs)+1):
                        data[port][i] = [-1]* (trace_lines + 1)
                        
            log(f'allocations done, {trace_lines+1} per port', 5)

            f.seek(0) # and destroy
            
            log('seek to trace beggining: done', 5)
            
            i = -1
            prow = [0]*row_len
            
            ctime = None
            
            # main data parsing here
            for line in f:
                row = line.rstrip().split(';')
                
                if i == -1:
                    i += 1
                    continue
                
                if portIdx is not None:
                    port = row[portIdx]
                else:
                    port = 0
                
                #iterrate values
                    
                for j in range(0, len(row)):
                    col = titles[j]
                    value = row[j]
                    
                    indx = ii[port] # actual row number
                    
                    '''
                        check the kpi name
                        and skip it if it is not in the corresponding list
                    '''
                    if col != 'time':
                        if port == '':
                            if col not in hostKPIs:
                                continue
                            else:
                                colindx = hostKPIs.index(col) + 1
                        else:
                            if col not in srvcKPIs:
                                continue
                            else:
                                #log('%s --> %i' % (col, srvcKPIs.index(col)))
                                colindx = srvcKPIs.index(col) + 1
                        
                    if col != 'time' and value == '':
                        #if port == '30003' and col == 'indexserverCpu':
                        #    log('repeat %s %i %i --> %i' % (port, colindx, indx, data[port][colindx][indx - 1]))
                            
                        #data[port][colindx][indx] = data[port][colindx][indx - 1] # god knows what that means actually.
                        data[port][colindx][indx] = prow[j] # god knows what that means actually.
                        continue
                        
                    #log('%s = %s' % (col, value))
                        
                    if col == 'time':
                        if i == 0:
                            ctime = float(value) #init time
                            #log('initidal time: %f' % ctime)
                        else:
                            if value == '':
                                ctime = ctime
                            else:
                                if value[0] == '>':
                                    ctime = ctime + float(value[1:])  #init time + delta (old style)
                                else:
                                    ctime = float(value) #cloud + new traces have explicit timing
                                    
                            #log('next time: %f' % ctime)
                        
                        data[port][0][indx] = ctime + self.TZShift
                            
                    else: 
                        if value[:1] == '>':
                            value = prow[j] + int(value[1:])
                        elif value[:1] == '<':
                            value = prow[j] - int(value[1:])

                    if col not in ('host', 'tenant', 'time'):
                        if value == '':
                            value = prow[j]
                            
                        value = int(value)
                        data[port][colindx][indx] = value

                    if col == 'time':
                        prow[j] = ctime
                    else:
                        prow[j] = value
                    
                ii[port] += 1
                i += 1
                
                if ii[port] >= trace_lines:
                    log('line count reached: %i', trace_lines)
                    break
            
        t2 = time.time()
        log('parsing time %s' % str(round(t2-t1, 3)))
        
        for ik in ii.keys():
            log(f'{ik} --> {ii[ik]} rows parsed')
        
        port = ''
        s = ''
        
        # here in ns notation
        log('copy kpis...', 5)
        self.hostKPIs = hostKPIs.copy()
        self.srvcKPIs = srvcKPIs.copy()
        
        log('clarifyGroups', 5)
        kpiDescriptions.clarifyGroups()
        
        log('clarifyGroups done ok', 5)

        self.lastIndx = ii.copy()
        
        log('for port in self.ports...', 5)

        for port in self.ports:
            log(f'port number: {port}')
            
            lastIndx = ii[port] - 1
            
            log(f'lastIndx: {lastIndx}')
            log(f'from: {data[port][0][0]}')
            log(f'to: {data[port][0][lastIndx]}')
            
            stime = datetime.fromtimestamp(data[port][0][0])
            etime = datetime.fromtimestamp(data[port][0][lastIndx])
            
            log(f'start/stop assigned')

            hosts.append({
                        'host':host,
                        'port':port,
                        'from':stime,
                        'to':etime
                        })
                        
        log('dbTrace initHosts done fine', 5)
                        
    def getData(self, host, fromto, kpis, data, wnd=None):
        #log('get data request: %i.%s' % (host, str(kpis)))
        #print('get data request:', host, fromto, kpis)

        port = host['port'] 

        if host['port'] == '':
            type = 'host'
        else:
            type = 'service'
        
        data_size = self.lastIndx[port]
        timeline = array('d', [0]*data_size) 

        data['time'] = timeline

        for kpi in kpis:

            ds = [0]*data_size
        
            data[kpi] = ds
        
        for i in range(0, data_size):
            data['time'][i] = self.data[port][0][i]
            
        timeKey = 'time'
        
        for kpi in kpis:
            if port == '':
                colindx = self.hostKPIs.index(kpi) + 1
            else:
                colindx = self.srvcKPIs.index(kpi) + 1
            
            #probably some kind of memcopy will be faster 1000 times
            for i in range(0, data_size):
                
                rawValue = self.data[port][colindx][i]
                
                if 'perSample' in kpiDescriptions.kpiStylesNN[type][kpi]:
                    if i == 0:
                        normValue = rawValue / (data['time'][1] - data['time'][0])
                    else:
                        normValue = rawValue / (data['time'][i] - data['time'][i-1])
                    
                    data[kpi][i] = int(normValue)
                    
                else:
                    data[kpi][i] = rawValue
        
        return
