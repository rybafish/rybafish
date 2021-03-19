from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPen, QColor

import random

kpiKeys = []
kpiGroup = {}

radugaColors = []
radugaPens = []

import utils
        
from utils import log, cfg

def removeDeadKPIs(kpis, type):

    for kpi in kpis:
        if kpi[:1] != '.' and kpi not in kpiStylesNN[type]:
            print('deleting', kpi)
            kpis.remove(kpi)
            
    return

def generateRaduga(n):

    #random.seed(cfg('radugaSeed', 1))

    colors = utils.cfg('raduga')
    
    for c in colors:
        
        color = QColor(c)
        pen = QPen(color)
        
        radugaColors.append(color)
        radugaPens.append(pen)
    
kpiStylesN = {}
kpiStylesNN = {'host':{}, 'service':{}}

customSql = {}

def createStyle(kpi, custom = False, sqlIdx = None):

    style = {}
    
    #try: 
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
            if 'subtype' in kpi and kpi['subtype'] == 'gantt':
                style['sqlname'] = 'None'
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
        if 'subtype' in kpi and kpi['subtype'] == 'gantt':
            # gantt stuff
            if 'width' in kpi:
                style['width'] = int(kpi['width'])
            else:
                style['width'] = 8

            if 'font' in kpi:
                style['font'] = int(kpi['font'])
            else:
                style['font'] = 8

            if 'shift' in kpi:
                style['shift'] = int(kpi['shift'])
            else:
                style['shift'] = 2
            
            if 'style' in kpi and (kpi['style'] == 'bar' or kpi['style'] == 'candle'):
                style['style'] = kpi['style']
            else:
                style['style'] = 'bar'
                
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
            # regular kpis
            style['pen'] = QPen(color, 1, penStyle)

    style['sql'] = sqlIdx
    '''
    except Exception as e:
        log(str(kpi))
        log(style)
        log('Error creating a style: %s' % str(e))
        
        return None
    '''
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

    thread_kpis_ns = ['indexserverthreads',
            'waitingthreads',
            'totalthreads',
            'activesqlexecutors',
            'waitingsqlexecutors',
            'totalsqlexecutors']

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
            

        # those two for dpTrace as it is based on ns KPI names
        if 'cpuused' in kpiStylesNN[h]:
            update(kpiStylesNN[h]['cpuused']['group'], 'cpu')

        if 'memoryused' in kpiStylesNN[h]:
            update(kpiStylesNN[h]['memoryused']['group'], 'mem')

        if cfg('memoryGB'):
            updateDunit('mem', 'GB')
            
        # enforce threads scaling
        if thread_kpis[0] in kpiStylesNN[h]:
            update_hardcoded(kpiStylesNN[h], thread_kpis, 33)

        if 'active_thread_count' in kpiStylesNN[h]:
            update(kpiStylesNN[h]['active_thread_count']['group'], 'thr')
            
        # now the same for ns... 
        if thread_kpis_ns[0] in kpiStylesNN[h]:
            update_hardcoded(kpiStylesNN[h], thread_kpis_ns, 33)

        if 'indexserverthreads' in kpiStylesNN[h]:
            update(kpiStylesNN[h]['indexserverthreads']['group'], 'thr')
        

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
        
def initKPIDescriptions(rows, hostKPIs, srvcKPIs):
    '''
        Same interface to be reused for DB trace
        
        Output:
            hostKPIs, srvcKPIs are filled with the respective KPIs lists
            
            kpiStylesNN - GLOBAL <--- list of KPIs...
    '''
    
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
                    'style':        nsStyle(kpi[9])
                }
            
            kpiStylesNN[type][kpiName] = createStyle(kpiDummy)
                    
        if kpi[1].lower() == 'm_load_history_host':
            hostKPIs.append(kpiName)
        else:
            srvcKPIs.append(kpiName)
