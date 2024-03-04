import sys #temp

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPen, QColor

from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLineEdit, QLabel, QPushButton, QTableWidget, QTableWidgetItem

import random

kpiKeys = []
kpiGroup = {}

radugaColors = []
radugaPens = []

customColors = {}       # color customization

import utils
        
from utils import deb, log, cfg
from utils import vrsException
from utils import resourcePath
from collections import UserDict

currentIndex = None

vrsStrDef = {}      # yaml definition, strings
vrsDef = {}         # yaml definition, dicts
vrsStrErr = {}      # True/False in case of parsing issues

vrsRepl = {}        # dict of pairs from/to per sqlIdx for character replacements

vrsStr = {}         # current string representation (for KPIs table)
vrs = {}            # actual dict

def logvar(msg, logl=3):
    log(msg, component='variables', loglevel=logl)

class Style(UserDict):
    exclude = ['sql'] # keys excluded from vars processing
    def __init__(self, idx, *args):
        self.idx = idx
        super().__init__(*args)
        
    def __missing__(self, key):
        log('[!] Style key missing: %s' % key, 1)
        raise KeyError(key)
            
    def __getitem__(self, key):
        if key in self.data:
            value = self.data[key]
            
            # if key == 'y_range': log(f'Style getitem[{self.idx}]: {key}/{value}')
            
            if self.idx and type(value) in (str, list):
                if self.idx in vrs and value != '' and key not in Style.exclude:
                    value = processVars(self.idx, value)
                    # if key == 'y_range': log(f'Post-process:[{self.idx}]: {key}/{value}')
                    
            return value
            
        if hasattr(self.__class__, "__missing__"):
            return self.__class__.__missing__(self, key)
            
        raise KeyError(key)

def addCustomColor(kpiKey, color):
    '''
        adds color customization
        
        kpiKey is in form hostname:port/kpi
        
        color is QColor
    '''
    
    customColors[kpiKey] = (color.red(), color.green(), color.blue())
    #customColorsPen[kpiKey] = QPen(color)

def colorsHTML(colors):
    d = {}
    
    for key, value in colors.items():
        # v = value[0]*256*256 + value[1]*256 + value[2]
        # d[key] = '#' + hex(v)[2:]

        r, g, b = value[0], value[1], value[2]
        d[key] = f'#{r:02x}{g:02x}{b:02x}'


    return d
    

def colorsHTMLinit(colors):
    '''
        to be called once during layout load
    '''

    for key, value in colors.items():
        
        v = value.lstrip('#')

        if len(v) != 6:
            log(f'invalid color, cannot be decoded: "{v}"', 2) # #948
            continue

        r = int(v[0:2], 16)
        g = int(v[2:4], 16)
        b = int(v[4:6], 16)

        customColors[key] = (r, g, b)
    
def customPen(kpiKey, defaultPen):
    '''
        extracts custom pen if available,
        if not - the default one returned
    '''

    # dirty parsing of thr host:port/kpi string
    split1 = kpiKey.split(':')
    split2 = split1[1].split('/')
    
    host = split1[0]
    port = split2[0]
    kpi = split2[1]
    
    c = customColors.get(kpiKey)
    
    if c:
        clr = QColor(c[0], c[1], c[2])
        
        pen = QPen(defaultPen)
        pen.setColor(clr)
    
        return pen
        
    return defaultPen
        
class Variables(QDialog):

    width = None
    height = None
    x = None
    y = None

    def __init__(self, hwnd, idx = None):
        super().__init__(hwnd)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.initUI(idx)

    def fillVariables(self, mode = None):
    
        if mode == 'defaults':
            lvrsStr = vrsStrDef
            vrsStr.clear()      # #832.2 fix?
            #lvrs = vrsDef -- those already parsed/replaced, cannot use those
        else:
            lvrsStr = vrsStr
            #lvrs = vrs -- those already parsed/replaced, cannot use those
            
            
        # need to parse str variables representation and build a dict to display in form of table
        # duplicated code from add Vars, sorry
        lvrs = {}
        
        for idx in lvrsStr:
            
            lvrs[idx] = {}
            
            vlist = [s.strip() for s in lvrsStr[idx].split(',')]
            
            vNames = []
            for v in vlist:
                p = v.find(':')
                if p > 0:
                    vName = v[:p].strip()
                    vVal = v[p+1:].strip()
                    
                lvrs[idx][vName] = vVal
    
        r = 0
        
        '''
        print('lvrsStr')
        for idx in lvrsStr:
            print(idx, ' --> ', lvrsStr[idx])
            print(idx, ' --> ', lvrs[idx])
        '''

        #print('\nvrs')
        for idx in lvrs:
            #print(idx, ' --> ', lvrs[idx])
            r += len(lvrs[idx])
            
        #print()

        self.vTab.setRowCount(r)

        row = 0
        for idx in lvrs:
            i = 0
            for var in lvrs[idx]:
                val = lvrs[idx][var]
                #print(idx, var, val)

                # idx
                if i == 0:
                    item1 = QTableWidgetItem(idx)
                else:
                    item1 = QTableWidgetItem('') # must be empty
                    
                item1.setFlags(item1.flags() & ~Qt.ItemIsEditable)
                self.vTab.setItem(row, 0, item1)
                    
                # variable
                item2 = QTableWidgetItem(var)
                item2.setFlags(item2.flags() & ~Qt.ItemIsEditable)
                self.vTab.setItem(row, 1, item2)
                
                #value
                self.vTab.setItem(row, 2, QTableWidgetItem(val))
                
                i += 1
                row += 1
                
        self.vTab.resizeColumnsToContents()
        
    def resetVars(self):
        self.fillVariables('defaults')
    
    def processVars(self):
    
        global vrs
        global vrsStr
        
        rowsCount = self.vTab.rowCount()
        
        vrsNew = {}
        
        idx = ''
        nvrsStr = {}
        nvrs = {}
        
        for i in range(rowsCount):
            if self.vTab.item(i, 0) and self.vTab.item(i, 0).text() != '' and self.vTab.item(i, 0).text() != idx:
                idx = self.vTab.item(i, 0).text()
                nvrs[idx] = {}
                
            var = self.vTab.item(i, 1).text()
            val = self.vTab.item(i, 2).text()
            
            nvrs[idx][var] = val

        #print('\nnew vrs:')
        
        #combone string representation...
        for idx in nvrs:
            #print(idx, '-->', nvrs[idx])
            
            nvrsStr[idx] = ', '.join(['%s: %s' % (key, value) for (key, value) in nvrs[idx].items()])
            
        #print('\nvrsStr')
        for idx in nvrsStr:
            #print(idx, ' --> ', nvrsStr[idx])
            
            try:
                addVars(idx, nvrsStr[idx], overwrite=True) #use common processing
            except vrsException as ex:
                utils.msgDialog('Error', f'There is an error parsing {idx}:\n\n{ex}\n\nChanges were not applied.')
            
        '''
        vrsStr = nvrsStr
        vrs = nvrs
        '''
            
        Variables.width = self.size().width()
        Variables.height = self.size().height()
        
        Variables.x = self.pos().x()
        Variables.y = self.pos().y()
        
        self.accept()
        
    def highlightIdx(self, idx):
        logvar(f'Need to highlight {idx}', 5)
        
        for i in range(self.vTab.rowCount()):
            item = self.vTab.item(i, 0)
            if item is not None and item.text() == idx:
                self.vTab.setCurrentItem(item)
        
        
    def initUI(self, idx):
    
        iconPath = resourcePath('ico', 'favicon.png')
        
        vbox = QVBoxLayout()
        ocBox = QHBoxLayout()
        
        self.vTab = QTableWidget()
        
        self.vTab.setColumnCount(3)
        
        self.vTab.setHorizontalHeaderLabels(['KPI file', 'Variable', 'Value'])
        
        vbox.addWidget(self.vTab)
        
        rButton = QPushButton('Reset all to defaults')
        
        if len(vrsDef) == 0:
            rButton.setDisabled(True)
        
        okButton = QPushButton('Ok')
        cButton = QPushButton('Cancel')
        
        okButton.clicked.connect(self.processVars)
        rButton.clicked.connect(self.resetVars)
        cButton.clicked.connect(self.reject)
        
        ocBox.addStretch(1)
        ocBox.addWidget(okButton)
        ocBox.addWidget(rButton)
        ocBox.addWidget(cButton)
        
        vbox.addLayout(ocBox)
        
    
        self.setLayout(vbox)
        
        #self.setWindowIcon(QIcon(iconPath))
        
        #self.setGeometry(300, 300, 300, 150)
        
        self.resize(500, 300)
        self.setWindowTitle('Variables')
        
        self.fillVariables()
        self.highlightIdx(idx)
        
        if self.width and self.height:
            self.resize(self.width, self.height)

        if self.x and self.y:
            self.move(self.x, self.y)


def addVarsRepl(sqlIdx, repl):
    global vrsRepl
    
    vrsRepl[sqlIdx] = repl
    
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
        logvar('%s already in the dict, anyway...' % sqlIdx, 4)
        
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
        
    logvar('yaml variables for %s defined as %s' % (sqlIdx, str(vrsDef[sqlIdx])))
    

def addVars(sqlIdx, vStr, overwrite = False):
    '''
        this one called on manual update of variables from the KPIs table
        
        (seems) it also actualizes vrs dict
    '''

    global vrs
    global vrsStr
    global vrsDef
    global vrsRepl
    
    def repl(idx, s):
        r = vrsRepl.get(idx)
        
        if r:
            smod = s.replace(r[0], r[1])
            if s != smod:
                logvar(f'Variable replace {idx}: {s} --> {smod}', 4)
            else:
                logvar(f'Didn\'t make any changes {idx}: {s} --> {smod}', 4)
            
                
            return smod
        else:
            logvar(f'no replacement for {idx}, s = {s}')
            return s
        
    def validate(s):
        '''
            very simple validation routine
        '''
        vlist = [s.strip() for s in vStr.split(',')]
        
        for v in vlist:
            if v.find(':') <= 0:
                logvar('Not a valid variable definition: [%s]' % v, 2)
                return False
                
        return True
    
    logvar('addVars input: %s' % (str(vStr)))
        
    for idx in vrs:
        logvar('    %s --> %s' % (idx, str(vrs[idx])), 5)
    
    if vStr == None:
        return

    if not validate(vStr):
        logvar('[E] Variables parsing error!', 2)
        
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
        logvar(f'setting defaults for {sqlIdx}', 5)
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
                #log('Variable already in the list, will update...: %s -> %s' % (vName, vVal), 4)
                vrs[sqlIdx][vName] = repl(sqlIdx, vVal)
            else:
                # log(f'Overwrite is off, so only do the replacement {vName}', 4)
                vrs[sqlIdx][vName] = repl(sqlIdx, vrs[sqlIdx][vName])
        else:
            vrs[sqlIdx][vName] = repl(sqlIdx, vVal)
            
    #keysDelete = []
    # go throuth the result and remove the stuff that was not supplied in the input string, #602
    if sqlIdx in vrsDef:
        # otherwise it is probably an initial load
        for v in vrs[sqlIdx]:
            if v not in vNames:
                if v in vrsDef[sqlIdx]:
                    logvar('Variable \'%s\' seems missing in %s, restoring default from YAML' % (v, sqlIdx))
                    vrs[sqlIdx][v] = vrsDef[sqlIdx][v]
                else:
                    logvar('Seems variable \'%s\' is excluded from %s, it will be IGNORED' % (v, sqlIdx))
                    #log('Seems variable \'%s\' is excluded from %s, it will be erased from the runtime values' % (v, sqlIdx))
                    #keysDelete.append(v)
                    
    # go through defined variables and add missing ones
    
    if sqlIdx not in vrsDef:
        logvar('[W] how come %s is missing in vrsDed??' % sqlIdx, 2)
    else:
        logvar('Variables YAML defaults: %s' % str(vrsDef[sqlIdx]), 5)
        for k in vrsDef[sqlIdx]:
            if k not in vrs[sqlIdx]:
                vrs[sqlIdx][k] = repl(sqlIdx, vrsDef[sqlIdx][k])
                logvar('[W] MUST NOT REACH THIS POINT #602\'%s\' was missing, setting to the default value from %s: %s' % (k, sqlIdx, vrsDef[sqlIdx][k]), 4)
        
    logvar(f'Actual variables for {sqlIdx} now are {vrs[sqlIdx]}', 4)


def processVars(sqlIdx, src):
    '''
        makes the actual replacement based on global variable vrs
        sqlIdx is a custom KPI file name with extention, example: 10_exp_st.yaml
        
        s is the string or list of strings for processing
        
        this function does not evaluate source definition, only vrs
        vrs actualization done in addVars - it restores missed values, etc
    '''

    global vrs
    
    # is it custom kpi at all?
    if not sqlIdx:
        return src

    # are there any variables?
    if sqlIdx not in vrs:
        return src


    outList = []
    
    if type(src) != list:
        srcList = [str(src)]
    else:
        srcList = src

    # go through list values
    for s in srcList:
        #if s is not None:
            #s = str(s)
        if type(s) == str:

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
        
        outList.append(s)
        
    # return the same type: single string or list of strings
    if type(src) != list:
        return outList[0]
    else:
        return outList
        
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
    
    if n == 0:
        return None
    
    pen = radugaPens[currentIndex]

    currentIndex += 1
    
    if currentIndex >= n:
        currentIndex = 0
    
    return pen

def resetRaduga():
    global currentIndex
    
    currentIndex = 0
    
kpiStylesN = {}
kpiStylesNN = {'host':{}, 'service':{}}     # supposed to keep all the kpi styles definitions

customSql = {}

def createStyle(kpi, custom = False, sqlIdx = None):

    #log(str(kpi))

    #style = {}
    style = Style(sqlIdx)
    
    # mandatory stuff
    
    style['type'] = 's' if kpi['type'] == 'service' else 'h'
    style['subtype'] = kpi.get('subtype')
    
    if custom:
        style['name'] = 'cs-' + kpi['name']
    else:
        style['name'] = kpi['name']
        
    if custom:
        style['sqlname'] = kpi.get('sqlname', '') # gantt subtype always uses START/STOP so no sql column name used
        style['nofilter'] = True if kpi.get('nofilter') else False
            
    # optional stuff
    group = kpi.get('group') or 0 # both None and '' to be translated to int(0)
    style['group'] = group
    style['desc'] = kpi.get('description', '')
    style['label'] = kpi.get('label', '')
        
    if 'sUnit' in kpi and 'dUnit' in kpi:
        sUnit = kpi['sUnit'].split('/')
        dUnit = kpi['dUnit'].split('/')
        
        if len(sUnit) > 1 and len(dUnit) > 1 and sUnit[1] == 'sample' and dUnit[1] == 'sec':
            # deb(f'{kpi["name"]}: {sUnit=}, {dUnit=}')
            style['sUnit'] = sUnit[0]
            style['dUnit'] = dUnit[0]
            style['perSample'] = True
        else:
            style['sUnit'] = kpi['sUnit']
            style['dUnit'] = kpi['dUnit']
    else:
        style['sUnit'] = ''
        style['dUnit'] = ''
    #create pen
    if 'color' in kpi:
        color = QColor(kpi['color'])
    else:
        color = QColor('#DDD')
        
        
        
    penStyles = {
        'solid': Qt.SolidLine,
        'dotted': Qt.DotLine,
        'dashed': Qt.DashLine,
        'dotline': Qt.DotLine,
        'bar': Qt.DotLine,
        'candle': Qt.DotLine,
        'unknown': Qt.DashDotDotLine
    }
        
    if 'style' in kpi:
        st = kpi.get('style', 'unknown')
        
        if st in penStyles:
            penStyle = penStyles[st]
        else:
            log(f'Unknown pen stile "{st}" for kpi "{kpi["name"]}", using weird one to get attention', 2)
            penStyle = penStyles['unknown']
            
        if st == 'unknown': log('[W] pen style unknown: %s - [%s]' % (kpi['name'], (kpi['style'])), 2)
    else:
        log(f"Pen style not defined for {kpi['name']}, using default", 4)
        if style['type'] == 'h':
            penStyle = Qt.DashLine
        else:
            penStyle = Qt.SolidLine
    
    if kpi['name'][:7] == '---#---':
        style['pen'] = '-'
    else:
        if kpi.get('subtype') == 'gantt':
            # gantt stuff
            style['width'] = kpi.get('width', 8)
            style['font'] = kpi.get('fontSize', 8)
            style['tfont'] = kpi.get('titleFontSize', style['font']-1)
            style['shift'] = kpi.get('shift', 2)
            style['title'] = kpi.get('title')
            style['gradient'] = kpi.get('gradient')
            style['manual_color'] = kpi.get('manual_color')

            if style['manual_color'] and style['gradient']:
                log('[W] Gantt style cannot have both manual_color and gradient enabled', 1)
                style['gradient'] = None
                raise utils.customKPIException(f"[W] Gantt style cannot have both manual_color and gradient enable KPI: {kpi['name']}")

            style['style'] = kpi.get('style', 'bar')
            
            if style['style'] not in ('bar', 'candle'):
                log('[W] unsupported gantt style (%s), using default' % style['style'], 2)
                style['style'] = 'bar'

            clr = QColor(color)
            style['brush'] = clr

            penColor = QColor(int(clr.red()*0.75), int(clr.green()*0.75), int(clr.blue()*0.75))
            style['pen'] = QPen(penColor, 1, Qt.SolidLine)

            brightnessTo = kpi.get('gradientTo', '#F00')
            clrFade = QColor(brightnessTo)
            style['gradientTo'] = clrFade

            yr = kpi.get('y_range')
            
            if type(yr) == list and len(yr) == 2:
                style['y_range'] = yr
            else:
                log('[W] unsupported y_range value for %s: %s, using default: 0, 100' % (kpi['name'], str(yr)), 2)
                style['y_range'] = [0, 100]
            
        elif kpi.get('subtype') == 'multiline':
        
            if 'splitby' not in kpi:
                log('[W] multiline KPI (%s) must have splitby definition, skipping!' % (kpi['name']), 2)
                return None

            style['groupby'] = kpi['splitby']
            style['stacked'] = kpi.get('stacked', False)
            style['multicolor'] = kpi.get('multicolor', False)
            style['descending'] = kpi.get('desc', False)
            style['legendCount'] = kpi.get('legendCount', 5)
            style['others'] = kpi.get('others', False)

            acml = kpi.get('async', False)

            if acml:
                if style['stacked']:
                    log('[E] KPI cannot have async and stacked options enabled at the same time: {sqlIdx}', 2)
                    raise utils.customKPIException(f"Unsupported async mode for stacked multiline KPI: {kpi['name']}")
                else:
                    style['async'] = True
            else:
                style['async'] = False

            ordby = kpi.get('orderby', 'unknown')
            if ordby not in ['max', 'avg', 'name', 'deviation']:
                log('[W] unsupported orderby value %s/%s, using default (max)' % (kpi['name'], kpi.get('orderby')), 2)
                    
            style['orderby'] = ordby
            
            if style['multicolor']:
                style['pen'] = QPen(QColor('#48f'), 1, Qt.SolidLine)
            else:
                style['pen'] = QPen(QColor(color), 1, Qt.SolidLine)
                
            style['brush'] = None
            style['style'] = 'multiline'
            
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

def getTimeKey(kpiStylesNNN, kpi):

    if customKpi(kpi):
        timeKey = 'time:' + kpiStylesNNN[kpi]['sql']
    else:
        timeKey = 'time'
        
    return timeKey

def getSubtype(kpiStylesNNN, kpi):
    if kpi in kpiStylesNNN:
        subtype = kpiStylesNNN[kpi]['subtype']
    else:
        subtype = None
        
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
        
def clarifyGroups(kpiStylesNNN):
    '''
        gives pre-defined names to most useful groups like memory and threads
        for the new style kpiStylesNNN needs to be called for every type: host/service
        (before multiplication) or just every host
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

        for kpi in kpiStylesNNN:
            if kpiStylesNNN[kpi]['group'] == grpIdx:
                kpiStylesNNN[kpi]['group'] = grpName

    def updateDunit(grpIdx, dUnit):
        for kpi in kpiStylesNNN:
            if kpiStylesNNN[kpi]['group'] == grpIdx:
                kpiStylesNNN[kpi]['dUnit'] = dUnit
        
    log('Clarify groups call...')

    if 'cpu' in kpiStylesNNN:
        update(kpiStylesNNN['cpu']['group'], 'cpu')

    if 'memory_used' in kpiStylesNNN:
        update(kpiStylesNNN['memory_used']['group'], 'mem')
        

    # those four for the dpTrace as it is based on ns KPI names

    if 'cpuused' in kpiStylesNNN:
        update(kpiStylesNNN['cpuused']['group'], 'cpu')

    if 'indexservercpu' in kpiStylesNNN:
        update(kpiStylesNNN['indexservercpu']['group'], 'cpu')

    if 'memoryused' in kpiStylesNNN:
        update(kpiStylesNNN['memoryused']['group'], 'mem')

    if 'indexservermemused' in kpiStylesNNN:
        update(kpiStylesNNN['indexservermemused']['group'], 'mem')

    if cfg('memoryGB'):
        updateDunit('mem', 'GB')
        
    # enforce threads scaling
    if thread_kpis[0] in kpiStylesNNN:
        update_hardcoded(kpiStylesNNN, thread_kpis, 33)

    if 'active_thread_count' in kpiStylesNNN:
        update(kpiStylesNNN['active_thread_count']['group'], 'thr')
        
    # now the same for ns... 
    if thread_kpis_ns[0] in kpiStylesNNN:
        update_hardcoded(kpiStylesNNN, thread_kpis_ns, 33)

    if 'indexserverthreads' in kpiStylesNNN:
        update(kpiStylesNNN['indexserverthreads']['group'], 'thr')

    if cfg('verifyGroupUnits', True):
        log('check group units...', 5)

        for checkUnit in ['sUnit', 'dUnit']:
            gunits = {}
            for kpi in kpiStylesNNN.keys():
                kv= kpiStylesNNN[kpi]
                # log(f'{kpi=}, {kv=}')
                if kv['group'] == 0 or kv['group'] == '0': # this look ugly... #809
                    continue # special non-scaled group

                if not kv['group'] in gunits:
                    gunits[kv['group']] = kv.get(checkUnit)
                    # log(f"{kv['group']} added: {kv.get(checkUnit)}")
                else:
                    if gunits[kv['group']] != kv.get(checkUnit) and kv['group']:
                        raise utils.customKPIException(f'''{checkUnit} does not match! group: {kv['group']}, kpi name: {kpi}
\'{gunits[kv['group']]}\' != \'{kpiStylesNNN[kpi].get(checkUnit)}\'. Review the KPI definition.

If required, disable this check by setting verifyGroupUnits: False''')
        else:
            log('no issues detected', 5)


def groups(hostKPIsStyles):
    # generates list of actual kpi groups

    groups = []

    for kpiStylesNNN in hostKPIsStyles:
        for kpi in kpiStylesNNN:
            if kpiStylesNNN[kpi]['group'] not in groups:
                groups.append(kpiStylesNNN[kpi]['group'])
                
    return groups

def normalize (kpi, value, d = 0):
    '''
    convert value for display purpose based on sUnit/dUnit
    used to calculate min/max for labels, etc in alignScales (once per getData)

    1048576 MB/Byte --> 1.0
    '''


    if 'sUnit' in kpi and 'dUnit' in kpi:
        sUnit, dUnit = kpi['sUnit'], kpi['dUnit']
    else:
        log(f'norm: {kpi}, no sunit/dunit, no normalization', 5)
        return value

    nValue = None
    
    if sUnit == 'Byte' and dUnit == 'GB':
        nValue = round(utils.GB(value, 'GB'), d)
    elif sUnit == 'Byte' and dUnit == 'MB':
        nValue = round(utils.GB(value, 'MB'), d)

    elif sUnit == 'usec' and dUnit == 'sec':
        nValue = round(value/1000000, d)

    # deb('[Norm] %s/%s: %s %i -> %s ' % (kpi['name'], kpi['sUnit'], kpi['dUnit'], value, str(nValue)))
    
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
        
def initKPIDescriptions(rows, hostKPIs, srvcKPIs, kpiStylesNN):
    '''
        this method unpacks standard HANA m_load_history_info rows and fills:
            - two lists of kps (hostKPIs, srvcKPIs)
            - dictionay of corresponding styles: kpiStylesNN
        
        Same interface reused in DB trace, dbi_sqlite
        
        Input rows list structure:
            ('2.10', '', '', 0, 'SQL', '', '', '', 0, 0) -- header/group
            ('2.10.01', 'M_LOAD_HISTORY_SERVICE', 'CONNECTION_COUNT', 0, 'Open Connections', 'Number of open SQL connections', '', '', 4251856, 1)
            
            r[0] - hierarchy (not used)
            r[1] - data source
            r[2] - sql column name for the kpi --> 'name'
            r[3] - scaling croup
            r[4] - human readable name         --> 'label' 
            r[5] - description
            r[6] - sUnit
            r[7] - dUnit
            r[8] - color
            r[9] - style (solid, dashed, etc)
        
        Output:
            hostKPIs, srvcKPIs are filled with the respective KPIs lists
            
            kpiStylesNN pre-created (outside) dict containing 'host' and 'service' keys,
            will contain styles for KPIs
    '''
    
    for kpi in rows:
    
        #log(f'[init kpi] {kpi}')
        
        if kpi[1].lower() == 'm_load_history_host':
            hType = 'host'
        else:
            hType = 'service'
    
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
                    'type':         hType,
                    'name':         kpiName,
                    'group':        utils.safeInt(kpi[3]),
                    'label':        kpi[4],
                    'description':  kpi[5],
                    'sUnit':        kpi[6],
                    'dUnit':        kpi[7],
                    'color':        utils.safeInt(kpi[8]),
                    'style':        nsStyle(utils.safeInt(kpi[9]))
                }
            
            kpiStylesNN[hType][kpiName] = createStyle(kpiDummy)
                    
        if kpi[1].lower() == 'm_load_history_host':
            hostKPIs.append(kpiName)
        else:
            srvcKPIs.append(kpiName)
            
    return
