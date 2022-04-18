from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPen, QColor

import random

kpiKeys = []
kpiGroup = {}

radugaColors = []
radugaPens = []

import utils
        
from utils import log, cfg

from utils import vrsException

currentIndex = None

vrsStrDef = {}      # yaml definition, strings
vrsDef = {}         # yaml definition, dicts
vrsStrErr = {}      # True/False in case of parsing issues

vrsStr = {}         # current string representation (for KPIs table
vrs = {}            # actual dict


def addVarsDef(sqlIdx, vStr):
    '''
        builds a dict for default values as it is defined in yaml definition
        string representation also stored.
        
        It is used two cases:
            1) to reset everithing to defaults when update from kpiTable submitted --- not any more...
            2) to set variables to empty value in case it is missing in vrsStr
    '''
    
    global vrsStrDef
    global vrsDef
    
    vrsStrDef[sqlIdx] = vStr
    
    vlist = [s.strip() for s in vStr.split(',')]
    
    if sqlIdx in vrsDef:
        log('%s already in the dict, anyway...' % sqlIdx, 4)
        
    vrsDef[sqlIdx] = {}
        
    for v in vlist:
        p = v.find(':')
        if p > 0:
            vName = v[:p].strip()
            vVal = v[p+1:].strip()
        else:
            vName = v
            vVal = ''
            
        vrsDef[sqlIdx][vName] = vVal
        
    log('yaml variables for %s defined as %s' % (sqlIdx, str(vrsDef[sqlIdx])))
    

def addVars(sqlIdx, vStr, overwrite = False):
    '''
        this one called on manual update of variables from the KPIs table
    '''

    global vrs
    global vrsStr
    global vrsDef
    
    def validate(s):
        '''
            very simple validation routine
        '''
        vlist = [s.strip() for s in vStr.split(',')]
        
        for v in vlist:
            if v.find(':') <= 0:
                log('Not a valid variable definition: [%s]' % v, 3)
                return False
                
        return True
    
    log('addVars input: %s' % (str(vStr)), 5)
        
    for idx in vrs:
        log('%s --> %s' % (idx, str(vrs[idx])), 5)
    
    if vStr == None:
        return
    '''
    if overwrite:
        if sqlIdx in vrs:
            log('full refresh of %s vars' % (sqlIdx), a4)
            
            vrs[sqlIdx].clear()
    '''
    
    if not validate(vStr):
        log('[E] Variables parsing error!')
        
        #vrsStr[sqlIdx] = None
        msg = 'Variables cannot have commas inside'
        vrsStrErr[sqlIdx] = '[!] '  + msg
        raise vrsException(msg)
        
        return
    else:
        vrsStrErr[sqlIdx] = False
        
    #if sqlIdx not in vrs or True: 2022-04-17
    if sqlIdx not in vrs:
        vrs[sqlIdx] = {}

    if sqlIdx not in vrsStr or overwrite:
        vrsStr[sqlIdx] = vStr

    vlist = [s.strip() for s in vStr.split(',')]
    
    vNames = []
    for v in vlist:
        p = v.find(':')
        if p > 0:
            vName = v[:p].strip()
            vVal = v[p+1:].strip()
            
            vNames.append(vName)
        else:
            '''
            vName = v
            vVal = ''
            '''
            return 
            
        if vName in vrs[sqlIdx]:
            if overwrite:
                log('Variable already in the list, will update...: %s -> %s' % (vName, vVal), 2)
                vrs[sqlIdx][vName] = vVal
        else:
            vrs[sqlIdx][vName] = vVal
            
    # go throuth the result and remove the stuff that was not supplied in the input string, #602
    if sqlIdx in vrsDef:
        # otherwise it is probably an initial load
        for v in vrs[sqlIdx]:
            if v not in vNames:
                log('Variable \'%s\' seems missing in %s, restoring default from YAML' % (v, sqlIdx))
                vrs[sqlIdx][v] = vrsDef[sqlIdx][v]
            
    # go through defined variables and add missing ones
    
    if sqlIdx not in vrsDef:
        log('[W] how come %s is missing in vrsDed??' % sqlIdx, 2)
    else:
        log('Variables YAML defaults: %s' % str(vrsDef[sqlIdx]), 5)
        for k in vrsDef[sqlIdx]:
            if k not in vrs[sqlIdx]:
                vrs[sqlIdx][k] = vrsDef[sqlIdx][k]
                log('[W] MUST NOT REACH THIS POINT #602\'%s\' was missing, setting to the default value from %s: %s' % (k, sqlIdx, vrsDef[sqlIdx][k]), 4)
        
    log('Actual variables for %s defined as %s' % (sqlIdx, str(vrs[sqlIdx])), 4)


def processVars(sqlIdx, s):
    '''
        makes the actual replacement based on global variable vrs
        sqlIdx is a custom KPI file name with extention, example: 10_exp_st.yaml
        
        s is the string for processing
    '''

    global vrs
    
    s = str(s)
    
    # is it custom kpi at all?
    if sqlIdx is None:
        return s

    # are there any variables?
    if sqlIdx not in vrs:
        return s

    #log('---process vars...---------------------------------------', 5)
    #log('sqlIdx: ' + str(sqlIdx))
    #log('vrs: ' + str(vrs[sqlIdx]))
    #log('>>' + s, 5)
    #log('  -- -- -- --', 5)

    if sqlIdx in vrs:
        for v in vrs[sqlIdx]:
            if v == '':
                continue
                
            s = s.replace('$'+v, str(vrs[sqlIdx][v]))
        
    #log('<<' + s, 5)
    #log('---------------------------------------------------------', 5)
    return s

def removeDeadKPIs(kpis, type):

    for kpi in kpis:
        if kpi[:1] != '.' and kpi not in kpiStylesNN[type]:
            print('deleting', kpi)
            kpis.remove(kpi)
            
    return

def generateRaduga():

    #random.seed(cfg('radugaSeed', 1))

    colors = utils.cfg('raduga')
    
    for c in colors:
        
        color = QColor(c)
        pen = QPen(color)
        
        radugaColors.append(color)
        radugaPens.append(pen)
        
    resetRaduga()
    

def getRadugaPen():
    global currentIndex
    
    n = len(radugaPens)
    
    pen = radugaPens[currentIndex]

    currentIndex += 1
    
    if currentIndex >= n:
        currentIndex = 0
    
    return pen

def resetRaduga():
    global currentIndex
    
    currentIndex = 0
    
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
        if 'nofilter' in kpi:
            style['nofilter'] = True
        else:
            style['nofilter'] = False
            
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

            if 'fontSize' in kpi:
                style['font'] = int(kpi['fontSize'])
            else:
                style['font'] = 8

            if 'titleFontSize' in kpi:
                style['tfont'] = int(kpi['titleFontSize'])
            else:
                style['tfont'] = style['font'] - 1 

            if 'shift' in kpi:
                style['shift'] = int(kpi['shift'])
            else:
                style['shift'] = 2
            
            if 'style' in kpi and (kpi['style'] == 'bar' or kpi['style'] == 'candle'):
                style['style'] = kpi['style']
            else:
                style['style'] = 'bar'

            if 'title' in kpi:
                style['title'] = kpi['title']
            else:
                style['title'] = None

            if 'gradient' in kpi:
                style['gradient'] = kpi['gradient']
            else:
                style['gradient'] = None

            if 'gradientTo' in kpi:
                brightnessTo = kpi['gradientTo']
            else:
                brightnessTo = '#F00'
                
            clr = QColor(color)
            style['brush'] = clr

            clrFade = QColor(brightnessTo)
            style['gradientTo'] = clrFade

            penColor = QColor(clr.red()*0.75, clr.green()*0.75, clr.blue()*0.75)
            style['pen'] = QPen(penColor, 1, penStyle)
            
            if 'y_range' in kpi and kpi['y_range'] != '':
                yr = kpi['y_range']
                
                style['y_range'] = [None]*2

                '''
                y1 = int(processVars(sqlIdx, yr[0]))
                y2 = int(processVars(sqlIdx, yr[1]))
                
                style['y_range'][0] = 100 - max(0, y1)
                style['y_range'][1] = 100 - min(100, y2)
                '''
                
                style['y_range'][0] = yr[0]
                style['y_range'][1] = yr[1]
            else:
                style['y_range'] = [0, 100]
                
        elif 'subtype' in kpi and kpi['subtype'] == 'multiline':
        
            if 'splitby' not in kpi:
                log('[W] multiline KPI (%s) must have splitby definition, skipping!' % (kpi['name']), 2)
                return None

            style['groupby'] = kpi['splitby']
            
            if 'stacked' in kpi:
                style['stacked'] = kpi['stacked']
            else:
                style['stacked'] = False

            style['orderby'] = 'max'
            
            if 'orderby' in kpi:
                if kpi['orderby'] in ['max', 'avg', 'name', 'deviation']:
                    style['orderby'] = kpi['orderby']
            
            if 'multicolor' in kpi:
                style['multicolor'] = kpi['multicolor']
            else:
                style['multicolor'] = False

            if 'desc' in kpi:
                style['desc'] = kpi['desc']
            else:
                style['desc'] = True

            if 'legendCount' in kpi:
                style['legendCount'] = kpi['legendCount']
            else:
                style['legendCount'] = 5
                
            if style['multicolor']:
                style['pen'] = QPen(QColor('#48f'), 1, Qt.SolidLine)
            else:
                style['pen'] = QPen(QColor(color), 1, Qt.SolidLine)
                
            style['brush'] = None
            style['style'] = 'multiline'
            #kpi['groupby'] = None
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
    
        print(kpi)
    
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
