import datetime

from array import array
import math

import kpiDescriptions

import time

from utils import log


class dataProvider:
    files = []
    
    data = {}
    ports = []
    lastIndx = []
    
    def __init__(self, files):
        self.files = files
        log('trace dp: %s' % str(files))
        
    def initHosts(self, hosts, hostKPIs, srvcKPIs):
    
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
                    titles = row
                    
                    row_len = len(row)
                    
                    portIdx = titles.index('port')
                    hostIdx = titles.index('host')
                    
                else:
                    port = row[portIdx]
                    
                    if host == '':
                        host = row[hostIdx]
                    
                    if port in self.ports:
                        break
                    else:
                        self.ports.append(port)
                
                i += 1
                
            #trace_lines = int(trace_lines / i)
            trace_lines = int(trace_lines / 2) # host + service, number of ports may change...
            

            for kpi in titles:
                if kpiDescriptions.findKPIns('h', kpi):
                    hostKPIs.append(kpi)
                    
                if kpiDescriptions.findKPIns('s', kpi):
                    srvcKPIs.append(kpi)

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
                        data[port][i] = [-8]* (trace_lines)
                else:
                    for i in range(0, len(srvcKPIs)+1):
                        data[port][i] = [-8]* (trace_lines)

            f.seek(0)
            
            i = -1
            prow = [0]*row_len
            
            ctime = None
            
            for line in f:
                row = line.rstrip().split(';')
                
                if i == -1:
                    i += 1
                    continue
                
                port = row[portIdx]
                
                #iterrate values
                for j in range(0, len(row)):
                    col = titles[j]
                    value = row[j]
                    
                    indx = ii[port] # actual row number
                    
                    '''
                        check the kpi name
                        and skip it if it is not in the corresponding list

                    if col not in (kpiDescriptions.kpiKeys) and col != 'time':
                        continue
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
                                ctime = ctime + float(value[1:])  #init time + delta
                            #log('next time: %f' % ctime)
                            
                        data[port][0][indx] = ctime
                            
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

                        #if port == '30003' and col == 'indexserverCpu':
                        #    log('%s %i %i --> %i' % (port, colindx, indx, value))
                        
                        #log('--> %i' % (value))
                        #log('%s[%i][%i]--> %i' % (port, i, j, value))
                        
                    if col == 'time':
                        prow[j] = ctime
                    else:
                        prow[j] = value
                    
                #if i >= 5*6000:
                #    break
                
                #log('%s ----> %i' % (port, ii[port]))
                ii[port] += 1
                i += 1
            
        t2 = time.time()
        log('parsing time %s' % str(round(t2-t1, 3)))
        
        port = '30003'
        #port = '30001'
        #port = ''
        s = ''
        
        #log(titles)
        for i in range(0,8):
            if port == '':
                rlen = len(hostKPIs) + 1
            else:
                rlen = len(srvcKPIs) + 1
                
            for j in range(0, rlen):
                s += str(data[port][j][i]) + ','
                
            log(s)
            s = ''


        # here in ns notation
        self.hostKPIs = hostKPIs.copy()
        self.srvcKPIs = srvcKPIs.copy()
        
        #we need to have sql names not ns names...
        
        for i in range(0, len(hostKPIs)):
            log(hostKPIs[i])
            hostKPIs[i] = kpiDescriptions.decodeKPIns('h', hostKPIs[i])
            log(hostKPIs[i])

        for i in range(0, len(srvcKPIs)):
            log(srvcKPIs[i])
            srvcKPIs[i] = kpiDescriptions.decodeKPIns('s', srvcKPIs[i])
            log(srvcKPIs[i])
            

        self.lastIndx = ii.copy()
        for port in self.ports:
            lastIndx = ii[port] - 1
            
            stime = datetime.datetime.fromtimestamp(data[port][0][0])
            etime = datetime.datetime.fromtimestamp(data[port][0][lastIndx])

            hosts.append({
                        'host':host,
                        'port':port,
                        'from':stime,
                        'to':etime
                        })

    def getData(self, host, fromto, kpis, data):
        log('get data request: %i.%s' % (host, str(kpis)))
        
        port = self.ports[host] #host index = port = 'host' from hosts table
        
        data_size = self.lastIndx[port]
        timeline = array('d', [0]*data_size) 

        data['time'] = timeline

        for kpi in kpis:

            ds = [0]*data_size
        
            data[kpi] = ds
        
        for i in range(0, data_size):
            data['time'][i] = self.data[port][0][i]
            
        for kpi in kpis:
            if port == '':
                colindx = self.hostKPIs.index(kpi) + 1
            else:
                colindx = self.srvcKPIs.index(kpi) + 1
            
            #probably copy command will be faster 1000 times
            for i in range(0, data_size):
                data[kpi][i] = self.data[port][colindx][i]
        
        return
