import datetime

from array import array
import math, time, random

import dpDBCustom, kpiDescriptions

from kpiDescriptions import customKpi

from utils import log, cfg

class dataProvider:

    def __init__(self):
        log('dummy data provider init()')
        
    def initHosts(self, hosts, hostKPIs, srvcKPIs):
    
        kpiDummy = {
            'hierarchy':    '1',
            'type':         'service',
            'name':         'cpu',
            'group':        'cpu',
            'label':        'CPU',
            'description':  'Service CPU',
            'sUnit':        '%',
            'dUnit':        '%',
            'color':        '#F00',
            'style':        'solid'
        }

        kpiDummyMem = {
            'hierarchy':    '2',
            'type':         'service',
            'name':         'indexserverMemUsed',
            'group':        'mem',
            'sUnit':        'Byte/sample',
            'dUnit':        'MB/sec',
            'label':        'Memory used',
            'description':  'Service Memory Usage',
            'color':        '#0D0',
            'style':        'solid'
        }

    
        kpiDescriptions.kpiStylesNN['service']['cpu'] = kpiDescriptions.createStyle(kpiDummy)
        kpiDescriptions.kpiStylesNN['service']['indexserverMemUsed'] = kpiDescriptions.createStyle(kpiDummyMem)
        
        kpiDummy['type'] = 'host'
        kpiDummy['style'] = 'dashed'
        kpiDummy['description'] = 'Host CPU'
        kpiDescriptions.kpiStylesNN['host']['cpu'] = kpiDescriptions.createStyle(kpiDummy)
    
        hostKPIs.append('cpu')
        srvcKPIs.append('cpu')
        srvcKPIs.append('indexserverMemUsed')
        #srvcKPIs.append('memory_allocation_limit')
        
        stime = datetime.datetime.now() - datetime.timedelta(seconds= 18 * 3600)
        stime -= datetime.timedelta(seconds = stime.timestamp() % 3600)
        
        #etime = stime + datetime.timedelta(seconds = 5*3600)
        
        etime = datetime.datetime.now()
        
        hosts.append({
                    'host':'dummy1',
                    'port':'',
                    'from':stime,
                    'to':etime
                    })

        hosts.append({
                    'host':'dummy1',
                    'port':'30040',
                    'from':stime,
                    'to':etime
                    })
                    
        hosts.append({
                    'host':'dummy1',
                    'port':'30041',
                    'from':stime,
                    'to':etime
                    })
                    
        if cfg('experimental'):
            dpDBCustom.scanKPIsN(hostKPIs, srvcKPIs, kpiDescriptions.kpiStylesNN)
                    
    def getData(self, host, fromto, kpis, data):
        
        #time.sleep(1.7)
        
        ctime = datetime.datetime.now() - datetime.timedelta(seconds= 18 * 3600)
        ctime -= datetime.timedelta(seconds= ctime.timestamp() % 3600)

        if False:
            data_size = round(18*3600/10)
        else:
            seconds = (datetime.datetime.now() - ctime).total_seconds()
            data_size = int(seconds/10)

        #data_size = round(1000)
        
        timeline = array('d', [0]*data_size) # for some reason floats rounds up to minutes?! so use doubles...
        dataset1 = array('l', [0]*data_size)
        dataset2 = [0]*data_size

        data['time'] = timeline
        
        if host['port'] == '':
            data['cpu'] = dataset1
        else:
        
            if 'cpu' in kpis:
                data['cpu'] = dataset1
                
            if 'indexserverMemUsed' in kpis:
                data['indexserverMemUsed'] = dataset2
    
    
        for i in range(0,len(timeline)):
            data['time'][i] = ctime.timestamp()

            if host['port'] == '':
                data['cpu'][i] = round(50.0 + 50.0*math.sin(i/100))
            else:
                if host['port'] == '30040':
                    #dataset1[i] = round(40.0 + 40.0*math.sin(i/100))
                    
                    if i % 5 > random.randint(0, 80):
                        dataset1[i] = random.randint(0, 80)
                    else:
                        if random.randint(0, 100) < 2:
                            dataset1[i] = random.randint(0, 2)
                        else:
                            dataset1[i] = 0
                    #index mem
                    dataset2[i] = round(200.0*1024*1024*1024+ i /12 + 100.0*1024*1024*1024*math.sin(7+i/600)) 
                else:
                    dataset1[i] = round(30.0 + 30.0*math.sin(i/122+1))
                    dataset2[i] = round(120.0*1024*1024*1024+ i /12 + 10*1024*1024*1024*math.sin(7+i/800))

            ctime = ctime + datetime.timedelta(seconds=(10))
