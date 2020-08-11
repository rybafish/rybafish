from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPen, QColor

import random

kpiKeys = []
kpiGroup = {}

radugaColors = []
radugaPens = []

import utils
        
from utils import log, cfg

def generateRaduga(n):

    #random.seed(cfg('radugaSeed', 1))

    colors = utils.cfg('raduga')
    
    for c in colors:
        
        color = QColor(c)
        pen = QPen(color)
        
        radugaColors.append(color)
        radugaPens.append(pen)
    
    '''
    for i in range(n):
    
        r = random.randint(0, 8)
        g = random.randint(0, 8)
        b = random.randint(0, 8)
        
        r = r*16+64
        g = g*16+64
        b = b*16+64
        
        color = QColor(r, g, b)
        pen = QPen(color)
        
        radugaColors.append(color)
        radugaPens.append(pen)
    '''

'''
    0 - index?
    1 - type
    2 - group
    3 - nameserver name
    4 - brush
    5 - label text
    6 - sql name
    7 - desc
'''

'''
    not a very nice idea have tuuples here as they are immutable...
    wouldn't it be much better have dicts... probably init them from csv/yaml rather than python
'''

kpiStylesN = {}
kpiStylesNN = {'host':{}, 'service':{}}

customSql = {}

kpiStyles = [
    #i, t, grp, ns_name,                           brush,                                          text name, sql_name, description
    (0, 'h','cpu','cpuUsed',                      QPen(QColor('#E00'), 1, Qt.DashLine),           'CPU', 'cpu', 'CPU Used by All Processes'),
    (0, 'h','mem','memoryUsed',                   QPen(QColor('#0E4'), 1, Qt.DashLine),           'Database Used Memory', 'memory_used', 'Memory used for all HANA processes'),
    (0, 'h','mem','memoryResident',               QPen(QColor('#0A0'), 1, Qt.DashLine),           'Database Resident Memory', 'memory_resident', 'Physical memory used for all HANA processes'),
    (0, 'h','mem','memoryTotalResident',          QPen(QColor('#0A0'), 1, Qt.DashLine),           'Total Resident Memory', 'memory_total_resident', 'Physical memory used for all processes'),
    (0, 'h','mem','memoryLimit',                  QPen(QColor('#060'), 1, Qt.DashLine),           'Database Allocation Limit', 'memory_allocation_limit', 'Memory allocation limit for all processes of HANA instance'),
    
    (0, 'h','','networkIn',                       QPen(QColor('#0AA'), 1, Qt.DashDotLine),           'Network In', 'network_in', 'Bytes read from network by all processes'),
    (0, 'h','','networkOut',                      QPen(QColor('#A0A'), 1, Qt.DashDotLine),           'Network Out', 'network_out', 'Bytes written to network by all processes'),

    (0, 'h','','swapIn',                          QPen(QColor('#0AA'), 1, Qt.DashLine),           'Swap In', 'swap_in', 'Bytes read from swap by all processes'),
    (0, 'h','','swapOut',                         QPen(QColor('#A0A'), 1, Qt.DashLine),           'Swap Out', 'swap_out', 'Bytes written To swap by all processes'),

    (0, 's','cpu','indexserverCpu',               QPen(QColor('#E00'), 1, Qt.SolidLine),          'CPU', 'cpu', 'CPU Used by Service'),
    (0, 's','cpu','indexserverCpuSys',            QPen(QColor('#A00'), 1, Qt.SolidLine),          'System CPU', 'system_cpu', 'OS Kernel/System CPU used by Service'),
    
    # mem
    (0, 's','mem','-',                            '-',                                           'Memory', '', ''),
    (0, 's','mem','indexserverMemUsed',           QPen(Qt.green, 1, Qt.SolidLine),                'Memory Used', 'memory_used', 'Memory used by Service'),
    (0, 's','mem','indexserverMemLimit',          QPen(QColor('#080'), 1, Qt.SolidLine),          'Memory Limit', 'memory_allocation_limit', 'Memory allocation limit for Service'),
    
    # sql
    (0, 's', '','-',                            '-',                                              'SQL', '', ''),
    (0, 's', '','sqlBlockedTrans',                QPen(QColor('#C2C'), 1, Qt.SolidLine),          'Blocked Transactions', 'blocked_transaction_count','-'),
    (0, 's', '','sqlStatements',                  QPen(QColor('#FD0'), 1, Qt.SolidLine),          'Statemens per second', 'statement_count','-'),
    (0, 's', '','pendingRequestCount',            QPen(QColor('#0FF'), 1, Qt.SolidLine),          'Pending Session Request Count', 'pending_session_count','Number of pending requests'),
    
    #threads
    (0, 's', '','-',                            '-',                                              'Threads', '', ''),
    (0, 's', 'thr','indexserverThreads',          QPen(QColor('#00A'), 1, Qt.SolidLine),          'Active Threads', 'active_thread_count','Number of active threads'),
    (0, 's', 'thr','waitingThreads',              QPen(QColor('#0F2'), 1, Qt.SolidLine),          'Waiting Threads', 'waiting_thread_count','Number of waiting threads'),
    
    
    (0, 's', '','-',                            '-',                                              'Random Stuff', '', ''),
    (0, 's', '','dataWriteSize',                QPen(QColor('#C00'), 1, Qt.DotLine),          'Data Write Size', 'data_write_size','Bytes written to data area'),
    (0, 's','','indexserverSwapIn',               QPen(QColor('#0DD'), 1, Qt.SolidLine),          'Swap In', 'swap_in', 'Bytes read from swap by Service'),
    
    (0, 's', '','admissionTMP',                   QPen(QColor('#F48'), 1, Qt.SolidLine),          'Admission Control Queue', 'admission_control_queue_size','-'),
    #(0, '',' sqlConnections',                  QPen(QColor('#8AF'), 1, Qt.SolidLine),          'Open Connections'),
    ()
]

kpiStyles.remove(())

for kpi in kpiStyles:
    if len(kpi) > 0:
        kpiKeys.append(kpi[3])
        
        kpiGroup[kpi[3]] = kpi[2]
            
def findKPIsql(t, sqlName):
    for kpi in kpiStyles:
        if kpi[1] == t and kpi[6] == sqlName:
            return kpi

    return None

def findKPIns(t, nsName):
    for kpi in kpiStyles:
        if kpi[1] == t and kpi[3] == nsName:
            return kpi
            
    #log('ns kpi not found: %s.%s' % (t, nsName))

    return None
   
def decodeKPIns(t, nsName):
    for kpi in kpiStyles:
        if kpi[1] == t and kpi[3] == nsName:
            return kpi[6]

    return None
    
#new styles approach starting here
def createStyle(kpi, custom = False, sqlIdx = None):

    style = {}
    
    try: 
        # mandatory stuff
        if 'subtype' in kpi:
            style['subtype'] = kpi['subtype']
        else:
            style['subtype'] = None
        
        if 'name' in kpi:
            if custom:
                style['name'] = 'cs-' + kpi['name']
            else:
                style['name'] = kpi['name']
        else:
            return None
            
        if 'type' in kpi:
            if kpi['type'] == 'service':
                style['type'] = 's'
            else:
                style['type'] = 'h'
        else:
            return None
            
        if custom:
            if 'sqlname' in kpi:
                style['sqlname'] = kpi['sqlname']
            else:
                return None
                
        # optional stuff
        if 'group' in kpi:
            style['group'] = kpi['group']
        else:
            style['group'] = ''
            
        if 'description' in kpi:
            style['desc'] = kpi['description']
        else:
            style['desc'] = ''

        if 'label' in kpi:
            style['label'] = kpi['label']
        else:
            style['label'] = ''

        if 'sUnit' in kpi and 'dUnit' in kpi:
            sUnit = kpi['sUnit'].split('/')
            dUnit = kpi['dUnit'].split('/')
            
            if len(sUnit) > 1 and len(dUnit) > 1 and sUnit[1] == 'sample' and dUnit[1] == 'sec':
                style['sUnit'] = sUnit[0]
                style['dUnit'] = dUnit[0]
                style['perSample'] = True
            else:
                style['sUnit'] = kpi['sUnit']
                style['dUnit'] = kpi['dUnit']
        else:
            style['sUnit'] = '-'

        #create pen
        if 'color' in kpi:
            color = QColor(kpi['color'])
        else:
            color = QColor('#DDD')
            
        if 'style' in kpi and kpi['style'] != '':
            if kpi['style'] == 'solid':
                penStyle = Qt.SolidLine
            elif kpi['style'] == 'dotted':
                penStyle = Qt.DotLine
            elif kpi['style'] == 'dashed':
                penStyle = Qt.DashLine
            elif kpi['style'] == 'dotline':
                penStyle = Qt.DotLine
            elif kpi['style'] == 'bar' or kpi['style'] == 'candle':
                penStyle = Qt.SolidLine
            else:
                log('[W] pen style unknown: %s - [%s]' % (kpi['name'], (kpi['style'])))
                penStyle = Qt.DashDotDotLine
        else:
            if style['type'] == 'h':
                penStyle = Qt.DashLine
            else:
                penStyle = Qt.SolidLine
        
        if kpi['name'][:7] == '---#---':
            style['pen'] = '-'
        else:
            if kpi['style'] == 'bar' or kpi['style'] == 'candle':
                style['style'] = kpi['style']
                clr = QColor(color)
                style['brush'] = clr
                penColor = QColor(clr.red()*0.75, clr.green()*0.75, clr.blue()*0.75)
                style['pen'] = QPen(penColor, 1, penStyle)
                
                if 'y_range' in kpi and kpi['y_range'] != '':
                    yr = kpi['y_range']
                    style['y_range'] = [None]*2
                    style['y_range'][0] = 100 - max(0, yr[0])
                    style['y_range'][1] = 100 - min(100, yr[1])
                else:
                    style['y_range'] = [0, 100]
                
            else:
                style['pen'] = QPen(color, 1, penStyle)

        style['sql'] = sqlIdx
        
    except Exception as e:
        log(str(kpi))
        log('Error creating a style: %s' % str(e))
        
        return None
    return style
    
def customKpi (kpi):
    if kpi[:3] == 'cs-':
        return True
    else:
        return False

def getTimeKey(type, kpi):

    if customKpi(kpi):
        timeKey = 'time:' + kpiStylesNN[type][kpi]['sql']
    else:
        timeKey = 'time'
        
    return timeKey

def getSubtype(type, kpi):

    subtype = kpiStylesNN[type][kpi]['subtype']
        
    return subtype
        
def nsStyle (idx):
    
    defStyles = ['', 'solid', 'dashed', 'dotted', 'dotline']
    
    if idx <= len(defStyles):
        return defStyles[idx]
    else:
        return defStyles[0]

def hType (i, hosts):
    '''
        returns host type based on host index
        currently host/service
        used for kpiStylesNN[type]
    '''
    if hosts[i]['port'] == '':
        return 'host'
    else:
        return 'service'
        
def clarifyGroups():
    '''
        gives pre-defined names to most useful groups
    '''

    thread_kpis = ['active_thread_count',
            'waiting_thread_count',
            'total_thread_count',
            'active_sql_executor_count',
            'waiting_sql_executor_count',
            'total_sql_executor_count']

    def update_hardcoded(kpis, kpiList, grp):
        for kpi in kpis:
            if kpis[kpi]['name'] in kpiList:
                kpis[kpi]['group'] = grp
            
    def update(grpIdx, grpName):
        if grpIdx == 0:
            return;
    
        if grpIdx == grpName:
            return
    
        for h in kpiStylesNN:
            for kpi in kpiStylesNN[h]:
                if kpiStylesNN[h][kpi]['group'] == grpIdx:
                    kpiStylesNN[h][kpi]['group'] = grpName
                    
    def updateDunit(grpIdx, dUnit):
        for h in kpiStylesNN:
            for kpi in kpiStylesNN[h]:
                if kpiStylesNN[h][kpi]['group'] == grpIdx:
                    kpiStylesNN[h][kpi]['dUnit'] = dUnit
        

    for h in kpiStylesNN:
        if 'cpu' in kpiStylesNN[h]:
            update(kpiStylesNN[h]['cpu']['group'], 'cpu')
            
        if 'memory_used' in kpiStylesNN[h]:
            update(kpiStylesNN[h]['memory_used']['group'], 'mem')
            
            if cfg('memoryGB'):
                updateDunit('mem', 'GB')
            
        if thread_kpis[0] in kpiStylesNN[h]:
            update_hardcoded(kpiStylesNN[h], thread_kpis, 33)

        if 'active_thread_count' in kpiStylesNN[h]:
            update(kpiStylesNN[h]['active_thread_count']['group'], 'thr')
        

def groups():
    # generates list of actual kpi groups

    groups = []

    for h in kpiStylesNN:
        for kpi in kpiStylesNN[h]:
            if kpiStylesNN[h][kpi]['group'] not in groups:
                groups.append(kpiStylesNN[h][kpi]['group'])
                
    return groups

def normalize (kpi, value, d = 0):

    if 'sUnit' in kpi and 'dUnit' in kpi:
        sUnit, dUnit = kpi['sUnit'], kpi['dUnit']
    else:
        return value

    nValue = None
    
    if sUnit == 'Byte' and dUnit == 'GB':
        nValue = round(utils.GB(value, 'GB'), d)
    elif sUnit == 'Byte' and dUnit == 'MB':
        nValue = round(utils.GB(value, 'MB'), d)

    elif sUnit == 'usec' and dUnit == 'sec':
        nValue = round(value/1000000, d)

    # ('[N] %s: %s -> %s %i -> %s ' % (kpi['name'], kpi['sUnit'], kpi['dUnit'], value, str(nValue)))
    
    if nValue is not None:
        return nValue
    else:
        return value

def denormalize (kpi, value):

    if 'sUnit' in kpi and 'dUnit' in kpi:
        sUnit, dUnit = kpi['sUnit'], kpi['dUnit']
    else:
        return value

    nValue = None
    
    if sUnit == 'Byte' and dUnit == 'GB':
        nValue = utils.antiGB(value, 'GB')
    elif sUnit == 'Byte' and dUnit == 'MB':
        nValue = utils.antiGB(value, 'MB')

    elif sUnit == 'usec' and dUnit == 'sec':
        nValue = value*1000000

    # ('[dN] %s: %s -> %s %i -> %s ' % (kpi['name'], kpi['sUnit'], kpi['dUnit'], value, str(nValue)))
    
    if nValue is not None:
        return nValue
    else:
        return value