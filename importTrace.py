import csv
import time

import kpiDescriptions

from utils import log

def importTrace (filename, data, scales, max_lines = 0):

    '''
        imports standard old-school nameserver_history.trc
        
        parsed result written into data
        
        host/tenant/port fields just ignored so far
    '''

    i = 0
    
    t0 = time.time()
    
    if max_lines > 0:
        trace_lines = max_lines
    else:
        trace_lines = len(open(filename).readlines())
        
    t1 = time.time()
    
    log('count time: %s' % str(round(t1-t0, 3)))
    
    f = open(filename)
        #trcReader = csv.reader(csvfile, delimiter=';')
    
    i = -1 
    for line in f:
        row = line.rstrip().split(';')

        if i == -1: # header row
            titles = row
            
            for j in range(0, len(row)):
                data[titles[j]] = [0]* (trace_lines - 1) # minus header row

        else:
            for j in range(0, len(row)):
                col = titles[j]
                value = row[j]
                
                #log('%s - %s' % (col, value))

                if col not in (kpiDescriptions.kpiKeys) and col != 'time':
                    continue
                
                if col == 'time':
                    if i == 0:
                        value = float(value) #init time
                    else:
                        value = data['time'][i-1] + float(value[1:])  #init time + delta
                        
                    data['time'][i] = value

                else: 
                    if value[:1] == '>':
                        value = data[col][i-1] + int(value[1:])
                    elif value[:1] == '<':
                        value = data[col][i-1] - int(value[1:])
                    #elif value[:1] == '':
                    #    value = data[col][i-1]
                    #else:
                    #    value = int(value)
                
                if col not in ('host', 'tenant', 'time'):
                    if value == '':
                        value = data[col][i-1]
                        
                    data[col][i] = int(value)

                if col not in ('host', 'tenant', 'port'):
                    if i == 0:
                        scales[col] = {'min': data[col][i], 'max': data[col][i], 'unit': '?'}
                    else:
                        if scales[col]['min'] > data[col][i]:
                            scales[col]['min'] = data[col][i]
                            
                        if scales[col]['max'] < data[col][i]:
                            scales[col]['max'] = data[col][i]
        
                if i == trace_lines - 3: 
                    scales[col]['last_value'] = data[col][i]
        
        i += 1
        
        if max_lines > 0 and i >= max_lines-2:
            break

    '''
        i = -1
        for row in trcReader:
            
            if i == -1: # header row
                titles = row
                
                for j in range(0, len(row)):
                    data[titles[j]] = [0]* (trace_lines - 1) # minus header row
                    
            else:
                for j in range(0, len(row)):
                    col = titles[j]
                    value = row[j]
                    
                    if col not in ('indexserverCpu', 'time', 'indexserverMemUsed'):
                        pass
                    
                    if col == 'time':
                        if i == 0:
                            value = float(value) #init time
                        else:
                            value = data['time'][i-1] + float(value[1:])  #init time + delta
                            
                        data['time'][i] = value

                    else: 
                        if value[:1] == '>':
                            value = data[col][i-1] + int(value[1:])
                        elif value[:1] == '<':
                            value = data[col][i-1] + int(value[1:])
                    
                    if col not in ('host', 'tenant', 'time'):
                        if value == '':
                            value = data[col][i-1]
                            
                        data[col][i] = int(value)
                

                    if col not in ('host', 'tenant', 'port', 'indexserverCpu'):
                        if i == 0:
                            scales[col] = {'min': data[col][i], 'max': data[col][i]}
                        else:
                            if scales[col]['min'] > data[col][i]:
                                scales[col]['min'] = data[col][i]
                                
                            if scales[col]['max'] < data[col][i]:
                                scales[col]['max'] = data[col][i]
            
            i += 1
            
    '''
    
    t2 = time.time()
    log('parsing time: %s' % str(round(t2-t1, 3)))

    # scales['indexserverCpu'] = {'min': 0, 'max': 100, 'unit': '%'}
    # scales['indexserverMemUsed']['min'] = 0
    # scales['indexserverMemLimit']['min'] = 0
