'''
    simple dataprovider implementation for offline tests
    
    contains limited implementation of main dataprovider calls
'''
import datetime

from array import array
import math, time, random

import dpDBCustom, kpiDescriptions

from utils import log, cfg, msgDialog
import utils

class dataProvider:

    options = []

    def __init__(self):
        self.dbProperties = {}
        self.dbProperties['dbi'] = 'DMY'
        log('dummy data provider init()')
        
    def initHosts(self, dpidx):
    
        hosts = []
        KPIsList = []
        kpiStylesNNN = []
        
        # host and two services for kpis
        KPIsList.append([])
        KPIsList.append([])
        KPIsList.append([])

        # host and two services for styles
        kpiStylesNNN.append({})
        kpiStylesNNN.append({})
        kpiStylesNNN.append({})
        
        
        # this better to be replaced with interface using initKPIDescriptions and kpis.findKPI finction
        # but a bit later, works as is...
    
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
            'sUnit':        'Byte',
            'dUnit':        'MB',
            'label':        'Memory used',
            'description':  'Service Memory Usage',
            'color':        '#0D0',
            'style':        'solid'
        }

        kpiStylesNNN[1]['cpu'] = kpiDescriptions.createStyle(kpiDummy)
        kpiStylesNNN[1]['indexserverMemUsed'] = kpiDescriptions.createStyle(kpiDummyMem)

        kpiStylesNNN[2]['cpu'] = kpiDescriptions.createStyle(kpiDummy)
        kpiStylesNNN[2]['indexserverMemUsed'] = kpiDescriptions.createStyle(kpiDummyMem)
        
        kpiDummy['type'] = 'host'
        kpiDummy['style'] = 'dashed'
        kpiDummy['description'] = 'Host CPU'
        kpiStylesNNN[0]['cpu'] = kpiDescriptions.createStyle(kpiDummy)
    
        KPIsList[0].append('cpu')
        KPIsList[1].append('cpu')
        KPIsList[1].append('indexserverMemUsed')
        KPIsList[2].append('cpu')
        KPIsList[2].append('indexserverMemUsed')
        
        stime = datetime.datetime.now() - datetime.timedelta(seconds= 18 * 3600)
        stime -= datetime.timedelta(seconds = stime.timestamp() % 3600)
                
        etime = datetime.datetime.now()

        if cfg('dev?'):
            stime = datetime.datetime.strptime('2023-10-30 00:00:00', '%Y-%m-%d %H:%M:%S')
            etime = datetime.datetime.strptime('2023-10-30 02:00:00', '%Y-%m-%d %H:%M:%S')

        hosts.append({
                    'host':'dummy1',
                    'port':'',
                    'from':stime,
                    'to':etime,
                    'dpi': dpidx
                    })

        hosts.append({
                    'host':'dummy1',
                    'port':'30040',
                    'from':stime,
                    'to':etime,
                    'dpi': dpidx
                    })
                    
        hosts.append({
                    'host':'dummy1',
                    'port':'30041',
                    'from':stime,
                    'to':etime,
                    'dpi': dpidx
                    })
                    
                    
        # fake old KPIs structures...
        hostKPIs = []
        srvcKPIs = []
        kpiStylesNNold = {'host':{}, 'service':{}}
                    
        try:
            dpDBCustom.scanKPIsN(hostKPIs, srvcKPIs, kpiStylesNNold)
        except Exception as e:
            kpiDescriptions.removeDeadKPIs(srvcKPIs, 'service')
            kpiDescriptions.removeDeadKPIs(hostKPIs, 'host')

            msgDialog('Custom KPIs Error', 'There were errors during custom KPIs load.\n\n' + str(e))
            
        #unpack to shiny new ones
        for h in range(len(hosts)):
            if hosts[h]['port'] == '':
                KPIsList[h] += hostKPIs
                kpiStylesNNN[h].update(kpiStylesNNold['host'])
            else:
                KPIsList[h] += srvcKPIs
                kpiStylesNNN[h].update(kpiStylesNNold['service'])
            
        return hosts, KPIsList, kpiStylesNNN, None
                    
    def close(self):
        pass

    def getData(self, host, fromto, kpis, data, kpiStylesNN, wnd=None):
        
        #time.sleep(0.1)

        ctime = datetime.datetime.now() - datetime.timedelta(seconds= 18 * 3600)
        ctime -= datetime.timedelta(seconds= ctime.timestamp() % 3600)

        if cfg('dev?'):
            # ctime = datetime.datetime.strptime('2023-10-30 00:00:00', '%Y-%m-%d %H:%M:%S')
            ctime = datetime.datetime.strptime(fromto['from'], '%Y-%m-%d %H:%M:%S')

        if 'cs-exp_st' in kpis:
            t0 = ctime + datetime.timedelta(seconds=(3600*8))
            # t0 = datetime.datetime.strptime('2023-10-30 00:00:00', '%Y-%m-%d %H:%M:%S')
            t1 = t0 + datetime.timedelta(seconds=(3600*1))

            t2 = t1 + datetime.timedelta(seconds=(3600*0.5))
            t3 = t2 + datetime.timedelta(seconds=(3600*2))

            t4 = t0 + datetime.timedelta(seconds=(3600*1))
            t5 = t4 + datetime.timedelta(seconds=(3600*6))
            # t4 = datetime.datetime.strptime('2023-10-30 01:00:00', '%Y-%m-%d %H:%M:%S')
            # t5 = datetime.datetime.strptime('2023-10-30 01:30:00', '%Y-%m-%d %H:%M:%S')

            t6 = t5 + datetime.timedelta(seconds=(-1600))
            t7 = t6 + datetime.timedelta(seconds=(3600*1))

            t8 = t7 + datetime.timedelta(seconds=(-1300))
            t9 = t8 + datetime.timedelta(seconds=(3600 + 3600/4))

            t10 = ctime + datetime.timedelta(seconds=(3600*9+1200))
            t11 = t10 + datetime.timedelta(seconds=(3600*2+660))
            
            #data['time'] = None
            
            data['cs-exp_st'] = {}


            tzUTC = 0
            t0 = utils.setTZ(t0, tzUTC)
            t1 = utils.setTZ(t1, tzUTC)
            t2 = utils.setTZ(t2, tzUTC)
            t3 = utils.setTZ(t3, tzUTC)
            t4 = utils.setTZ(t4, tzUTC)
            t5 = utils.setTZ(t5, tzUTC)
            t6 = utils.setTZ(t6, tzUTC)
            t7 = utils.setTZ(t7, tzUTC)
            t8 = utils.setTZ(t8, tzUTC)
            t9 = utils.setTZ(t9, tzUTC)
            t10 = utils.setTZ(t10, tzUTC)
            t11 = utils.setTZ(t11, tzUTC)

            if host['port'] == '30040' and host['host'] == 'dummy1':
                data['cs-exp_st']['Stacy'] = [[t0, t1, '0:00 - 1:00', 0, '4gb'], [t2, t3, '1:30 - 3:30', 0, 'x gb']]

            if host['port'] == '30040' and host['host'] == 'dummy1':
                data['cs-exp_st']['SASCHA'] = [[t0, t1, 'mem: 34 GB \nhash: 2392133lkwejw9872', 0, ''], [t2, t3, 'asdf', 1, 'x gb']]
                data['cs-exp_st']['LUCIA'] = [[t4, t5, 'select...', 0, ''], [t6, t7, 'asdf', 0, ''], [t8, t9, 'asdfldfkjsdlfjksdl\nfjsdlfj sldkfj sldkfj l asdlf', 0, '']]
            else:
                pass
                # data['cs-exp_st']['RAYMOND'] = [[t10, t11, 'select * from ExpensiveView', 0, '']]
            
            for e in data['cs-exp_st']:
                print('%s:'% e)
                
                for l in data['cs-exp_st'][e]:
                    print ('    ', str(l[0]), '-' , str(l[1]))

        if False:
            data_size = round(18*3600/10)
        else:
            if fromto['to']:
                seconds = (datetime.datetime.strptime(fromto['to'], '%Y-%m-%d %H:%M:%S') - ctime).total_seconds()
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
            # ctime = utils.setTZ(ctime, 0)
            data['time'][i] = ctime.timestamp()

            if host['port'] == '':
                data['cpu'][i] = round(50.0 + 50.0*math.sin(i/100))
            else:
                if host['port'] == '30040' and host['host'] == 'dummy1':
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
