import sys

from PyQt5.QtWidgets import QWidget, QFrame, QScrollArea, QVBoxLayout, QHBoxLayout, QPushButton, QFormLayout, QGroupBox, QLineEdit, QComboBox, QLabel, QMenu
from PyQt5.QtWidgets import QApplication, QMessageBox, QToolTip, QAction

from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPolygon, QIcon, QFont, QFontMetrics, QClipboard, QPixmap, QRegion

from PyQt5.QtCore import QTimer, QRect, QSize

import os
import time
import datetime
import math
import random
import re

from array import array

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QPoint, QEvent

from PyQt5.QtCore import pyqtSignal

# my stuff
import kpiDescriptions
from kpiDescriptions import kpiStylesNN, hType
#, processVars
from utils import resourcePath

import importTrace
import utils

from utils import log, deb, cfg, safeBool, safeInt

import dpDummy
import dpTrace
import dpDB

from tzDialog import tzDialog

from profiler import profiler

class myWidget(QWidget):

    '''
                 _/|  /|     _/|     _/  _/|   _/   /_/_/_/ _/_/_/_/_/ _/     _/ _/_/_/_/ _/_/_/_/
                _/ | /_|    _/_|    _/  _/_|  _/   /           _/     _/     _/ _/       _/
               _/  |/ _|   _/ _|   _/  _/ _| _/    \_/_/_     _/     _/     _/ _/_/_/   _/_/_/
              _/      _|  _/--_|  _/  _/  _| /         _/    _/     _/     _/ _/       _/
             _/       _| _/   _| _/  _/   __/   _/_/_/_/    _/      _/_/_/   _/       _/
    '''

    updateFromTime = pyqtSignal(['QString'])
    updateToTime = pyqtSignal(['QString'])
    
    zoomSignal = pyqtSignal(int, int)
    scrollSignal = pyqtSignal(int, float)
    
    statusMessage_ = pyqtSignal(['QString', bool])
    
    timeZoneDelta = 0 # to be set after connection

    hosts = [] # list of 'hosts': host + tenants/services. based on this we fill the KPIs table(s) - in order, btw
               # and why exactly do we have hosts in widget?..

    kpis = [] #list of kpis to be drawn << old one, depricated
    nkpis = [] #list of kpis to be drawn *per host* < new one

    kpiPen = {} #kpi pen objects dictionary
    
    highlightedEntity = None # gantt kpi currently highlihed
    highlightedRange = None # gantt kpi currently highlihed
    
    highlightedKpi = None #kpi currently highlihed
    highlightedKpiHost = None # host for currently highlihed kpi
    
    highlightedPoint = None #point currently highlihed (currently just one)
    highlightedNormVal = None
    
    highlightedGBI = None # multiline groupby index 
    
    #data = {} # dictionary of data sets + time line (all same length)
    #scales = {} # min and max values
    
    ndata = [] # list of dicts of data sets + time line (all same length), depricated
    nscales = [] # min and max values, list of dicts *per host*
    
    nscalesml = [] # min and max values for multiline groupbys, list of dicts *per host*
    
    manual_scales = {} # if/when scale manually adjusted, per group! like 'mem', 'threads'
                       # since #562 it is two values: from - to. From in 99% is 0

    # config section
    # to be filled during __init__ somehow
    conf_fontSize = 6
    
    font_height = 8 # to be calculated in __init__
    
    font_width1 = 16
    font_width2 = 30
    
    t_scale = 60*10 # integer: size of one minor grid step
    
    side_margin = 10
    left_margin = 0 # for side labels like Gantt chart...
    top_margin = 8
    bottom_margin = 20
    step_size = 16
    
    y_delta = 0 # to make drawing space even to 10 parts (calculated in drawGrid)
    
    delta = 0 # offset for uneven time_from values: gap from start of the grid to time_from
    
    zoomLock = False # also used in scrollRangeChanged
    paintLock = False
    
    gridColor = QColor('#DDD')
    gridColorMj = QColor('#AAA')
    
    legend = None
    legendRegion = None
    legendHeight = None
    legendWidth = None
    
    legendRender = False # flag used only to copy the legend
    
    hideGanttLabels = False # do not render gantt entitiy names
    gotGantt = False # True if there is any gantt on the chart (screen window only)
    
    timeScale = ''
    tzChangeWarning = False


    def __init__(self):
        super().__init__()
        
        self.t_to = None
        self.t_from = None
        
        if cfg('fontSize') is not None:
            self.conf_fontSize = cfg('fontSize')
            
        self.tzInfo = None

        self.calculateMargins()
        
        self.initPens()
        
    def wheelEvent (self, event):
        if self.zoomLock:
            return
         
        pos = event.pos()

        p = event.angleDelta()
        
        self.zoomLock = True
        
        if p.y() < 0:
            mode = 1
        else:
            mode = -1
            
        modifiers = QApplication.keyboardModifiers()

        if modifiers == Qt.ControlModifier:
            self.zoomSignal.emit(mode, pos.x())
        elif modifiers == Qt.ShiftModifier or modifiers == Qt.AltModifier:
            self.scrollSignal.emit(mode, 0.5)
        elif modifiers == Qt.NoModifier:
            self.scrollSignal.emit(mode, 4)
        
        self.zoomLock = False
        
    def statusMessage(self, str, repaint = False):
        if repaint: 
            self.statusMessage_.emit(str, True)
        else:
            self.statusMessage_.emit(str, False)
            
    def allocate(self, size):
        '''
            create main data structures
            based on number of hosts
            to be called right after the initHosts
        '''
    
        for i in range(0, size):
            self.nkpis.append([])
            self.ndata.append({})
            self.nscales.append({})
            self.nscalesml.append({})
        
    def calculateMargins(self, scale = 1):
    
        myFont = QFont ('SansSerif', self.conf_fontSize)
        fm = QFontMetrics(myFont)
        
        self.font_height = int(scale * fm.height()) - 2 # too much space otherwise
        self.bottom_margin = int(self.font_height*2) + 2 + 2
        
        log('font_height: %i' %(self.font_height))
        log('bottom_margin: %i' %(self.bottom_margin))
        
        self.font_width1 = scale * fm.width('12:00') / 2
        self.font_width2 = scale * fm.width('12:00:00') / 2
        self.font_width3 = scale * fm.width('2019-06-17') / 2
        
                
    def initPens(self):
    
        '''
        if utils.cfg('colorize'):
            kpiDescriptions.generateRaduga(utils.cfg('raduga'))
        '''
        if utils.cfg('colorize'):
            kpiDescriptions.generateRaduga()
    
        for i in range(len(self.hosts)):
            self.kpiPen[i] = {}
            kpiStylesNNN = self.hostKPIsStyles[i]
            for kpi in kpiStylesNNN:
                self.kpiPen[i][kpi] = kpiStylesNNN[kpi]['pen']

    def ceiling(self, num):
    
        if num < 5:
            return 5

        if num < 10:
            return 10
            
        num_str = str(num)

        # 1st digit + 1
        l2 = int(num_str[:1])+1

        return int(l2*math.pow(10, len(num_str)-1))
        
    def floor(self, num):
        num_str = str(num)

        # 1st digit + 1

        l2 = int(num_str[:1])
        
        return int(l2*math.pow(10, len(num_str)-1))
            
    '''
    def scanMetrics(self, grp):
        # scanMetrics depricated and must be replaced by getGroupMax
    '''
        
    def getGroupMax(self, grp):
        '''
            returns raw max for a group
            should not be called for group 0
        '''
        
        max_value = 0
        
        for h in range(len(self.hosts)):
            # for the issue https://github.com/rybafish/rybafish/issues/30
            # log('self.nscales[h].keys(): ' + str(self.nscales[h].keys()))
            
            #for kpi in self.nscales[h].keys():
            
            kpiStylesNNN = self.hostKPIsStyles[h]
            for kpi in list(self.nscales[h].keys()):

                if kpi[:4] == 'time':
                    continue
                    
                if kpi not in kpiStylesNNN:
                    log('[!] the kpi is disabled... %s, so deleting it from nscales' % kpi)
                    del self.nscales[h][kpi]
                    continue

                if kpiStylesNNN[kpi]['group'] == grp:
                    if max_value < self.nscales[h][kpi]['max']:
                        max_value = self.nscales[h][kpi]['max']
        
        return max_value
    
    def alignScales(self):
        '''
            align scales to normal values, prepare text labels (including max value, scale)
            for the KPIs table
            
            based on renewMaxValues data <-- self.widget.nscales[h]
        '''
        
        groups = []
        groupMax = {}
        
        log('  alignScales()', 5)
        #mem_max = self.scanMetrics('mem')
        #thr_max = self.scanMetrics('thr')
        
        groups = kpiDescriptions.groups(self.hostKPIsStyles)
        
        for g in groups:
            if g != '0':
                groupMax[g] = self.getGroupMax(g)
                
        for h in range(len(self.hosts)):
        
            log(f'update scales {h}: {self.hosts[h]}')
        
            kpiStylesNNN = self.hostKPIsStyles[h]
            
            for kpi in self.nscales[h].keys():
            
                manualScale = False
            
                if kpi[:4] == 'time':
                    continue
                    
                #self.nscales[h][kpi] = {}
                                
                scaleKpi = self.nscales[h][kpi] # short cut

                if kpi not in kpiStylesNNN:
                    log('[!] the kpi is disaaableeed, %s' % kpi)
                    continue
                    
                if kpiStylesNNN[kpi].get('subtype') == 'gantt':
                
                    #scaleKpi['y_max'] = ''
                    scaleKpi['y_max'] = ''
                    scaleKpi['max_label'] = '%i' % (self.nscales[h][kpi]['total'])
                    scaleKpi['last_label'] = ''
                    scaleKpi['label'] = '%i' % (self.nscales[h][kpi]['entities'])
                    scaleKpi['yScale'] = ''
                    scaleKpi['unit'] = ''
                    scaleKpi['avg'] = ''
                    scaleKpi['avg_label'] = ''
                    continue
                
                #log(scaleKpi)
                    
                '''
                    max and last values calculated before by renewMaxValues
                '''
                scaleKpi['y_min'] = 0 # we always start at 0...
                scaleKpi['y_max'] = None
                
                #memory group
                #if kpiDescriptions.kpiGroup[kpi] == 'mem':
                
                groupName = kpiStylesNNN[kpi]['group']

                if groupName == 'cpu':
                    scaleKpi['y_max'] = 100
                    scaleKpi['max_label'] = str(scaleKpi['max'])
                    scaleKpi['avg_label'] = str(scaleKpi['avg'])
                    
                    if 'last_value' in scaleKpi:
                        scaleKpi['last_label'] = str(scaleKpi['last_value']) 
                    else: 
                        scaleKpi['last_label'] = '?'
                        
                    scaleKpi['label'] = '10 / 100'
                    scaleKpi['yScale'] = 100
                    scaleKpi['unit'] = '%'
                    kpiStylesNNN[kpi]['decimal'] = 0

                    subtype = kpiStylesNNN[kpi].get('subtype')

                    if subtype == 'multiline' and kpi in self.nscalesml[h]:
                        d = 0
                        for gb in self.nscalesml[h][kpi]:
                            mx = self.nscalesml[h][kpi][gb]['max']
                            lst = self.nscalesml[h][kpi][gb]['last']
                            self.nscalesml[h][kpi][gb]['max_label'] = utils.numberToStr(kpiDescriptions.normalize(kpiStylesNNN[kpi], mx, d), d)
                            self.nscalesml[h][kpi][gb]['last_label'] = utils.numberToStr(kpiDescriptions.normalize(kpiStylesNNN[kpi], lst, d), d)
                            self.nscalesml[h][kpi][gb]['avg_label'] = ''
                else:
                    # all the rest:
                    # 0 group means no groupping at all, individual scales
                    # != 0 means some type of group (not mem and not cpu)
                    
                    yScaleLow = 0
                    
                    kpiStylesNNN[kpi]['decimal'] = 0
                    
                    if groupName == 0:
                        if 'manual_scale' in kpiStylesNNN[kpi]:
                            manualScale = True
                            min_value = kpiStylesNNN[kpi]['manual_scale'][0]
                            max_value = kpiStylesNNN[kpi]['manual_scale'][1]
                            yScaleLow = min_value
                            yScale = max_value_n = max_value
                        else:
                            max_value = self.nscales[h][kpi]['max']
                            #max_value = self.ceiling(max_value)
                            max_value_n = kpiDescriptions.normalize(kpiStylesNNN[kpi], max_value)
                            yScale = self.ceiling(int(round(max_value_n)))
                    else: 
                        if groupName in self.manual_scales:
                            min_value = self.manual_scales[groupName][0]
                            max_value = self.manual_scales[groupName][1]
                            #yScale = max_value_n = max_value # 2021-07-15, #429
                            yScaleLow = min_value             # 2022-01-19  #562
                            yScale = max_value                # 2021-07-15, #429 
                            max_value_n = kpiDescriptions.normalize(kpiStylesNNN[kpi], max_value) #429

                            manualScale = True
                        else:
                            max_value = groupMax[groupName]
                            max_value_n = kpiDescriptions.normalize(kpiStylesNNN[kpi], max_value)
                            
                            if max_value_n <= 10 and max_value != max_value_n:
                                kpiStylesNNN[kpi]['decimal'] = 2
                            elif max_value_n <= 100 and max_value != max_value_n:
                                kpiStylesNNN[kpi]['decimal'] = 1

                            yScale = self.ceiling(int(max_value_n))
                                         
                    '''
                        max_value_n, yScale must be defined by this line
                        even when no any difference with max_value
                    '''
                    
                    d = kpiStylesNNN[kpi].get('decimal', 0) # defined couple lines above
                    
                    scaleKpi['max_label'] = utils.numberToStr(kpiDescriptions.normalize(kpiStylesNNN[kpi], scaleKpi['max'], d), d)
                    
                    if scaleKpi['avg'] is not None:
                        scaleKpi['avg_label'] = utils.numberToStr(kpiDescriptions.normalize(kpiStylesNNN[kpi], scaleKpi['avg'], d), d)
                    else:
                        scaleKpi['avg_label'] = ''
                        
                    if 'last_value' in scaleKpi and scaleKpi['last_value'] is not None:
                        scaleKpi['last_label'] = utils.numberToStr(kpiDescriptions.normalize(kpiStylesNNN[kpi], scaleKpi['last_value'], d), d)
                    else:
                        scaleKpi['last_label'] = '-1'
                        
                        
                    subtype = kpiStylesNNN[kpi].get('subtype')
                    
                    if subtype == 'multiline' and kpi in self.nscalesml[h]:
                        for gb in self.nscalesml[h][kpi]:
                            mx = self.nscalesml[h][kpi][gb]['max']
                            lst = self.nscalesml[h][kpi][gb]['last']
                            self.nscalesml[h][kpi][gb]['max_label'] = utils.numberToStr(kpiDescriptions.normalize(kpiStylesNNN[kpi], mx, d), d)
                            self.nscalesml[h][kpi][gb]['last_label'] = utils.numberToStr(kpiDescriptions.normalize(kpiStylesNNN[kpi], lst, d), d)
                            self.nscalesml[h][kpi][gb]['avg_label'] = ''
                        
                    # scaleKpi['y_max'] = max_value
                    scaleKpi['y_max'] = kpiDescriptions.denormalize(kpiStylesNNN[kpi], yScale)
                    
                    if yScaleLow != 0:
                        scaleKpi['y_min'] = kpiDescriptions.denormalize(kpiStylesNNN[kpi], yScaleLow)
                    
                    dUnit = kpiStylesNNN[kpi]['sUnit'] # not converted

                    # whole sUnit/dUnit logic lost here...
                    if max_value_n == max_value:
                        # normalized same as not normalized... 0?
                        deb(f'{kpi} dUnit = sUnit due to max_value_n == max_value: {max_value_n} == {max_value}')
                        deb(f'{kpi}, {manualScale=}')

                        if manualScale:
                            deb('dUnit due to manualScale')
                            dUnit = kpiStylesNNN[kpi]['dUnit']
                        else:

                            if max_value_n == 0: #cfg('sunit_debug', False):
                                deb('set to dUnit as max_value = 0')
                                dUnit = kpiStylesNNN[kpi]['dUnit'] # not converted
                            else:
                                deb('set to sUnit as not zero and manual scale')
                                dUnit = kpiStylesNNN[kpi]['sUnit'] # not converted

                    else:
                        # max_value_n = self.ceiling(max_value_n) # normally it's already aligned inside getMaxSmth
                        dUnit = kpiStylesNNN[kpi]['dUnit'] # converted
                    
                    scaleKpi['yScale'] = yScale
                    
                    if yScaleLow == 0:
                        scaleKpi['label'] = ('%s / %s' % (utils.numberToStr(yScale / 10), utils.numberToStr(yScale)))
                    else:
                        scaleKpi['yScaleLow'] = yScaleLow
                        scaleKpi['label'] = ('%s / %s - %s' % (utils.numberToStr((yScale - yScaleLow)/ 10), utils.numberToStr(yScaleLow), utils.numberToStr(yScale)))
                        
                    if manualScale:
                        scaleKpi['manual'] = True
                    else:
                        scaleKpi['manual'] = False
                        
                    if 'perSample' in kpiStylesNNN[kpi]:
                        scaleKpi['unit'] = dUnit + '/sec'
                    else:
                        scaleKpi['unit'] = dUnit
      
    def posToTime(self, x):
        time = self.t_from + datetime.timedelta(seconds= (x - self.side_margin - self.left_margin)/self.step_size*self.t_scale - self.delta) 
        
        return time

    def timeToPos(self, time):
    
        pos = 10
        
        offset = (time - self.t_from).total_seconds()

        pos = offset/self.t_scale*self.step_size + self.delta + self.side_margin + self.left_margin
        
        #time = self.t_from + datetime.timedelta(seconds= (x - self.side_margin)/self.step_size*self.t_scale - self.delta) 
        
        return pos
        
    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)
        
        between = False

        startHere = cmenu.addAction('Make this a FROM time')
        stopHere = cmenu.addAction('Make this a TO time')
        
        cmenu.addSeparator()
        copyTS = cmenu.addAction('Copy this timestamp')
        
        clipboard = QApplication.clipboard()
        ts1 = clipboard.text()
        
        if re.match('^\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d$', ts1): 
            between = True
            
            copyTSbetween = QAction('Compose between predicate')
            
            f = copyTSbetween.font()
            f.setBold(True)
            copyTSbetween.setFont(f)
            
            cmenu.addAction(copyTSbetween)

        cmenu.addSeparator()
        copyVAPNG = cmenu.addAction('Copy screen')
        saveVAPNG = cmenu.addAction('Save screen')
        copyPNG = cmenu.addAction('Copy chart area')
        savePNG = cmenu.addAction('Save chart area')

        copyLegend = None
        
        if self.legend:
            cmenu.addSeparator()
            copyLegend = cmenu.addAction('Copy Legend to clipboard')
            putLegend = cmenu.addAction('Hide Legend\tCtrl+L')

        else:
            cmenu.addSeparator()
            putLegend = cmenu.addAction('Show Legend\tCtrl+L')
        
        if self.gotGantt:
            cmenu.addSeparator()
            
            if self.hideGanttLabels:
                toggleGanttLabels = cmenu.addAction('Show Gantt Labels\tCtrl+Shift+L')
            else:
                toggleGanttLabels = cmenu.addAction('Hide Gantt Labels\tCtrl+Shift+L')
        
        if self.highlightedEntity is not None:
            copyGanttEntity = cmenu.addAction('Copy highlighted gantt entity')
            copyGanttDetails = cmenu.addAction('Copy highlighted gantt details')
            
        if self.highlightedGBI is not None:
            cmenu.addSeparator()
            copyMultilineGB = cmenu.addAction('Copy highlighted multiline KPI name')            

        if cfg('developmentMode'):
            cmenu.addSeparator()
            fakeDisconnection = cmenu.addAction('fake disconnection')
        
        action = cmenu.exec_(self.mapToGlobal(event.pos()))

        # from / to menu items
        pos = event.pos()

        time = self.posToTime(pos.x())
        
        if action is None:
            return
        
        if cfg('developmentMode') and action == fakeDisconnection:
            log('dp.fakeDisconnect = True')
            self._parent.dp.fakeDisconnect = True
        
        if action == savePNG:
            
            screensFolder = cfg('screensFolder', 'screens')
            
            if not os.path.isdir(screensFolder):
                os.mkdir(screensFolder)
                
            filename = 'screen_'+datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')+'.png'
            fn = os.path.join(screensFolder, filename)
            
            log('Saving PNG image (%s)' % filename)
            
            pixmap = QPixmap(self.size())
            self.render(pixmap)
            pixmap.save(fn)
            
            self.statusMessage('Screenshot saved as %s' % (fn))
        
        if action == copyLegend:
            if not self.legendWidth:
                return

            log('Creating a legend copy')
            
            pixmap = QPixmap(QSize(self.legendWidth + 1, self.legendHeight + 1))
            
            self.legendRender = True
            self.render(pixmap, sourceRegion = self.legendRegion)
            self.legendRender = False
            
            QApplication.clipboard().setPixmap(pixmap)
            
            self.statusMessage('Legend bitmap copied to the clipboard')
        
        if action == putLegend:
            if self.legend is None:
                self.legend = 'hosts'
            else:
                self.legend = None
            
            self.repaint()
        
        if action == saveVAPNG:
            screensFolder = cfg('screensFolder', 'screens')
            
            if not os.path.isdir(screensFolder):
                os.mkdir(screensFolder)
                
            filename = 'screen_'+datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')+'.png'
            fn = os.path.join(screensFolder, filename)
            
            log('Saving PNG image (%s)' % filename)
            
            pixmap = QPixmap(self.parentWidget().size())
            self.parentWidget().render(pixmap)
            pixmap.save(fn)
            
            self.statusMessage('Screenshot saved as %s' % (fn))
            
        if action == copyPNG:
            log('Creating a screen')
            
            pixmap = QPixmap(self.size())
            self.render(pixmap)
            
            QApplication.clipboard().setPixmap(pixmap)
            
            self.statusMessage('Clipboard updated')

        if action == copyVAPNG:
            log('Creating a screen of visible area')
            
            pixmap = QPixmap(self.parentWidget().size())
            self.parentWidget().render(pixmap)
            
            QApplication.clipboard().setPixmap(pixmap)
            
            self.statusMessage('Clipboard updated')
        
        if action == startHere:
            even_offset = time.timestamp() % self.t_scale
            time = time - datetime.timedelta(seconds= even_offset)
            
            self.updateFromTime.emit(time.strftime('%Y-%m-%d %H:%M:%S'))

        if action == stopHere:
            even_offset = time.timestamp() % self.t_scale
            time = time - datetime.timedelta(seconds= even_offset - self.t_scale)
            
            self.updateToTime.emit(time.strftime('%Y-%m-%d %H:%M:%S'))

        if action == copyTS:
            #even_offset = 0 # time.timestamp() % self.t_scale
            #time = time - datetime.timedelta(seconds= even_offset - self.t_scale - self.delta)
            #time = time - datetime.timedelta(seconds= even_offset)
            
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            
            clipboard = QApplication.clipboard()
            clipboard.setText(ts)

        if between and action == copyTSbetween:
            ts2 = time.strftime('%Y-%m-%d %H:%M:%S')
            
            if ts1 > ts2:
                ts1, ts2 = ts2, ts1
            
            predicate = "between '%s' and '%s'" % (ts1, ts2)
            
            clipboard.setText(predicate)
            
        if self.highlightedGBI is not None and action == copyMultilineGB:
            kpi = self.highlightedKpi
            host = self.highlightedKpiHost
            gb = self.highlightedGBI
            
            kpiStylesNNN = self.hostKPIsStyles[host]
            subtype =  kpiStylesNNN[kpi].get('subtype')

            if subtype != 'multiline':
                log('[W] unexpected multiline call while not multiline?', 1)
                return

            if kpi not in self.ndata[host]:
                log(f'[w] kpi is not there? ({kpi})', 2)
                return

            gbv = self.ndata[host][kpi][gb][0]
            
            clipboard = QApplication.clipboard()
            clipboard.setText(gbv)
            
            
        if self.highlightedEntity is not None and action == copyGanttDetails:
        
            entity = self.highlightedEntity
            kpi = self.highlightedKpi
            host = self.highlightedKpiHost
            range_i = self.highlightedRange

            if kpi not in self.ndata[host]:
                log(f'[w] kpi is not there? ({kpi})', 2)
                return

            if entity in self.ndata[host][kpi]:
            
                #can disappear after zoom as we dont remove highlights
            
                desc = self.ndata[host][kpi][entity][range_i][2]
                
                desc = desc.replace('\\n', '\n')
                
                clipboard = QApplication.clipboard()
                clipboard.setText(desc)
                
                self.statusMessage('Copied.')
            
        if self.highlightedEntity and action == copyGanttEntity:
            
            clipboard = QApplication.clipboard()
            clipboard.setText(self.highlightedEntity)
            
            self.statusMessage('Copied.')

        if self.gotGantt and action == toggleGanttLabels:
            if self.hideGanttLabels:
                self.hideGanttLabels = False
            else:
                self.hideGanttLabels = True
                
            self.repaint()

    
    def checkForHint(self, pos):
        '''
            1 actually we have to check the x scale 
            and check 2 _pixels_ around and scan Y variations inside
             
            because when we have 50 data points in same pixel (easy)
            we don't know actual Y, it's too noizy
        '''
        
        found = None
        
        for host in range(0, len(self.hosts)):
        
            if len(self.nkpis) == 0:
                return
            
            if len(self.nkpis[host]) > 0 :
                found = self.scanForHint(pos, host, self.nkpis[host], self.nscales[host], self.ndata[host])
                
                if found == True: #we only can find one kpi to highlight (one for all the hosts)
                    return

        self.collisionsCurrent = None
        self.collisionsDirection = None

        if not found:
            if (self.highlightedKpi):
            
                host = self.highlightedKpiHost
                
                if self.highlightedKpi in self.kpiPen[host]:
                    self.kpiPen[host][self.highlightedKpi].setWidth(1)
                
                self.highlightedKpiHost = None
                self.highlightedKpi = None
                self.highlightedPoint = None
                self.highlightedGBI = None

                self.highlightedEntity = None
                self.highlightedRange = None

                self.setToolTip('')
                
                # self.update()
                
            self.statusMessage('No values around...')
            self.update() # - update on any click
            
        return
        
    @profiler
    def scanForHint(self, pos, host, kpis, scales, data):
        tolerance = 2 # number of pixels of allowed miss
        
        wsize = self.size()
        
        hst = self.hosts[host]['host']
        if self.hosts[host]['port'] != '':
            hst += ':'+str(self.hosts[host]['port'])
            
        trgt_time = self.t_from + datetime.timedelta(seconds= ((pos.x() - self.side_margin - self.left_margin)/self.step_size*self.t_scale) - self.delta)
        trgt_time_dt = trgt_time
        trgt_time = trgt_time.timestamp()
        
        x_scale = self.step_size / self.t_scale
        
        kpiStylesNNN = self.hostKPIsStyles[host]
        
        top_margin = self.top_margin + self.y_delta
        
        reportDelta = False
        
        found_some = False
        
        #log('scanForHint very top', 5)

        for kpi in kpis:
        
            log('scanForHint kpi: %s' %(kpi), 5)

            if not kpi in scales:
                log(f'[w] kpi {kpi} not in scales, skip', 2)
                continue
        
            if kpi[:4] == 'time':
                continue
                

            if kpi not in kpiStylesNNN:
                continue
                
            subtype = kpiStylesNNN[kpi].get('subtype')
            
            if subtype == 'gantt':
            
                height = kpiStylesNNN[kpi]['width']
                ganttShift = kpiStylesNNN[kpi]['shift']
            
                if kpi not in data: # alt+clicked, but not refreshed yet
                    continue
                    
                gc = data[kpi]
                
                if len(gc) == 0:
                    continue
                    
                i = 0
                
                yr0, yr1 = kpiStylesNNN[kpi]['y_range']
                
                try:
                    #yr0p = processVars(sqlIdx, yr0)
                    #yr1p = processVars(sqlIdx, yr1)
                    yr0p = yr0
                    yr1p = yr1
                    yr0 = 100 - max(0, int(yr0p))
                    yr1 = 100 - min(100, int(yr1p))
                except ValueError:
                    log('[E] Cannot convert variable to integer! %s or %s' % (yr0p, yr1p), 1)
                    yr0 = 100
                    yr1 = 90

                for entity in gc:
                
                    #exactly same calculation as in drawChart:
                    y_scale = (wsize.height() - top_margin - self.bottom_margin - 2 - 1) / len(gc)
                    y_shift = y_scale/100*yr0 * len(gc)
                    y_scale = y_scale * (yr1 - yr0)/100
                    
                    y = i * y_scale + y_scale*0.5 - height/2 + y_shift # this is the center of the gantt line

                    j = 0

                    reportRange = None
                    
                    for t in gc[entity]:
                        #check ranges first
                        if t[0] <= trgt_time_dt <= t[1]:
                        
                            y0 = y + top_margin - t[3]*ganttShift
                            y1 = y0 + height
                            
                            #check Y second:                            
                            if y0 <= pos.y() <= y1:
                            
                                # okay, we have a match, but we need to find the highest one...
                            
                                if reportRange is None or reportRange < j:
                                # if reportRange is None or gc[entity][reportRange][3] < t[3]: -- more accurate, bu it is the same, right?
                                    reportRange = j
                            
                        j += 1
                        

                    if reportRange is not None:
                        t = gc[entity][reportRange]
                        
                        self.highlightedPoint = None #690
                        
                        self.highlightedKpi = kpi
                        self.highlightedKpiHost = host
                        self.highlightedEntity = entity
                        self.highlightedRange = reportRange
                        
            
                        t0 = t[0].time().isoformat(timespec='milliseconds')
                        t1 = t[1].time().isoformat(timespec='milliseconds')

                        interval = '[%s - %s]' % (t0, t1)
                        
                        det = '%s, %s, %s: %s/%i %s' % (hst, kpi, entity, interval, t[3], t[2])
                        
                        self.statusMessage(det)
                        log('gantt clicked %s' % (det))

                        self.update()
                        return True
                        
                    i += 1
             
                continue # no regular kpi scan procedure requred
                
            '''
                regular kpis scan
            '''
        
            timeKey = kpiDescriptions.getTimeKey(kpiStylesNNN, kpi)
            
            if timeKey not in data or kpi not in data:
                # this kpi timeset is empty
                # or data[key] is empty, alt-enabled stuff
                
                return
                
            timeline = data[timeKey]
            array_size = len(timeline)
                        
            i = 0
            time_delta = tolerance*(self.t_scale/self.step_size)
        
            while i < array_size and timeline[i] < trgt_time - time_delta:
                i+=1

            if i == array_size:
                #log('scanForHint continue...', 5)
                #kpi not found but we still need to check others! 2021-07-15, #386
                continue
            else:
                pass
                #log('scanForHint dont continue?..', 5)


            if 'async' in kpiStylesNNN[kpi]:
                asyncMultiline = kpiStylesNNN[kpi].get('async')
            else:
                asyncMultiline = False

            if subtype == 'multiline':
                rounds = len(data[kpi])
            else:
                rounds = 1
                
            bubbleStop = False
            
            # log('scanForHint [%s], rounds : %i' %(subtype, rounds), 5)
                
            for rc in range(rounds):
            
                # log('scanForHint rc: %i' %(rc), 5)

                if subtype == 'multiline':
                    scan = data[kpi][rc][1]
                    gb = data[kpi][rc][0]
                else:
                    gb = None
                    scan = data[kpi]

                j = i

                #log('scanForHint len(scan) %i' %(len(scan)), 5)
                #log('scanForHint i: %i' %(i), 5)
                
                if i == array_size: # crash #538
                    continue

                if scan[i] == -1: #initially for asyncMultiline: no data in this point
                    #but seems relevant for all
                    continue

                y_min = scan[i] # crash here, #538 
                y_max = scan[i]

                #print('\nok, scan')
                while i < array_size and timeline[i] <= trgt_time + time_delta:
                    # note: for really zoomed in time scales there's a possibility
                    # that this loop will not be execuded even once
                    
                    if timeline[j] < trgt_time and j < array_size - 1:
                        j+=1 # scan for exact value in closest point

                    if y_min > scan[j]:
                        y_min = scan[j]

                    if y_max < scan[j]:
                        y_max = scan[j]
                        
                    #print('i, j, ymin, ymax, value', i, j, y_min, y_max, scan[i])

                    i+=1
                    
                #if y_min != y_max:

                if asyncMultiline:
                    j = moveAsync('left', scan, i)
                else:
                    j -= 1 # THIS is the point right before the trgt_time

                if j is None:   # #831
                    continue

                found_some = False

                if (scales[kpi]['y_max'] - scales[kpi]['y_min']) == 0:
                    log('delta = %i, skip %s' % (scales[kpi]['y_max'] - scales[kpi]['y_min'], str(kpi)))
                    # bubbleStop = True ?
                    break
                
                y_scale = (wsize.height() - top_margin - self.bottom_margin - 2 - 1)/(scales[kpi]['y_max'] - scales[kpi]['y_min'])
                
                #y = self.nscales[h][kpi]['y_min'] + y*y_scale #562
                #y = (y - self.nscales[h][kpi]['y_min']) * y_scale #562

                ymin = y_min
                #ymin = scales[kpi]['y_min'] + ymin*y_scale                     #562
                ymin = (ymin - scales[kpi]['y_min']) *y_scale                   #562
                ymin = round(wsize.height() - self.bottom_margin - ymin) - 2

                ymax = y_max
                #ymax = scales[kpi]['y_min'] + ymax*y_scale                     #562
                ymax = (ymax - scales[kpi]['y_min'])*y_scale                    #562
                ymax = round(wsize.height() - self.bottom_margin - ymax) - 2
                
                #log('%s = %i' % (kpi, self.scan[i]))
                #log('on screen y = %i, from click: %i' % (y, pos.y()))
                #log('on screen %i/%i, from click: %i' % (ymin, ymax, pos.y()))
                
                #if abs(y - pos.y()) <= 2:
                
                #print('ymin, ymax', ymin, ymax)
                #print('y:', pos.y())
                
                if pos.y() <= ymin + tolerance and pos.y() >= ymax - tolerance: #it's reversed in Y calculation...
                    if (self.highlightedKpi):
                    
                        # if self.highlightedKpi == kpi and self.highlightedKpiHost == host:
                        # deb(f'{kpi=}')
                        # deb(kpiStylesNNN[kpi])
                        # deb(f'{self.highlightedKpi=}')

                        hlStyle = self.hostKPIsStyles[self.highlightedKpiHost][self.highlightedKpi]
                        # deb(hlStyle)

                        if kpiStylesNNN[kpi]['group'] == hlStyle['group']:
                            # print(kpi, kpiStylesNNN[kpi])
                            # print(kpi, kpiStylesNNN[self.highlightedKpi])
                            reportDelta = True
                            
                        self.highlightedKpi = None

                    d = kpiStylesNNN[kpi].get('decimal', 0)

                    normVal = kpiDescriptions.normalize(kpiStylesNNN[kpi], scan[j], d)

                    scaled_value = utils.numberToStr(normVal, d)
                    
                    if subtype == 'multiline':
                        self.highlightedGBI = rc # groupby index
                        ml = '/' + gb
                    else:
                        self.highlightedGBI = None
                        ml = ''

                    log('click on %s(%i).%s%s = %i, %s' % (self.hosts[host]['host'], host, kpi, ml, scan[j], scaled_value))
                    self.kpiPen[host][kpi].setWidth(2)
                        
                    self.highlightedKpi = kpi
                    self.highlightedKpiHost = host
                    self.highlightedPoint = j
                    
                    if self.highlightedEntity is not None:
                        #gantt to be unhighlighted
                        self.highlightedEntity = None
                        self.highlightedRange = None
                    
                    if reportDelta:
                        if self.highlightedNormVal is None:
                            deltaVal = ''
                        else:
                            deltaVal = normVal - self.highlightedNormVal
                            deltaVal = ', delta: ' + utils.numberToStr(abs(deltaVal), d)
                    else:
                        deltaVal = ''

                    self.highlightedNormVal = normVal
                        
                    if utils.cfg_servertz:
                        # dpidx = self.hosts[host]['dpi']
                        # utcOff = self.ndp[dpidx].dbProperties.get('utcOffset', 0)
                        # ts = datetime.datetime.fromtimestamp(data[timeKey][j], utils.getTZ(utcOff))
                        ts = datetime.datetime.fromtimestamp(data[timeKey][j], self.tzInfo)
                    else:
                        ts = datetime.datetime.fromtimestamp(data[timeKey][j])

                    tm = ts.strftime('%Y-%m-%d %H:%M:%S')
                    
                    self.statusMessage('%s, %s%s = %s %s at %s%s' % (hst, kpi, ml, scaled_value, scales[kpi]['unit'], tm, deltaVal))
                    
                    self.setToolTip('%s, %s%s = %s %s at %s' % (hst, kpi, ml, scaled_value, scales[kpi]['unit'], tm))
                    
                    found_some = True
                    #okay, stop
                    break
                    
            if found_some:
                #bubble up the success flag...
                break
                
        if not found_some:
            return False
        else:
        
            self.update()
            return True
            
        log('click scan / kpi scan: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))

    def mousePressEvent(self, event):
        '''
            step1: calculate time
            step2: look through metrics which one has same/similar value
        '''
        
        if event.button() == Qt.RightButton:
            return
        
        pos = event.pos()
        
        time = self.t_from + datetime.timedelta(seconds= ((pos.x() - self.side_margin - self.left_margin)/self.step_size*self.t_scale) - self.delta)
        
        self.checkForHint(pos)
            
    def resizeWidget(self):
        if self.t_to is None:
            return
            
        seconds = (self.t_to - self.t_from).total_seconds()
        number_of_cells = int(seconds / self.t_scale) + 1
        self.resize(number_of_cells * self.step_size + self.side_margin*2 + self.left_margin, self.size().height()) #dummy size
        
    def drawLegend(self, qp, startX, stopX):
    
        lkpis = []      # kpi names to be able to skip doubles (what doubles?..)
        lkpisl = []     # kpi labels
        # lpens = []      # pens. None = host line (no pen)  ### depricated with multilines support, 2021-08-31
        lmeta = []      # legend metadata, list of four values: [type, pen/brush, ident for marker, ident for text]
        
        lLen = 128
    
        lFont = QFont ('SansSerif', utils.cfg('legend_font', 8))
        fm = QFontMetrics(lFont)
        
        drawTimeScale = cfg('legendTimeScale', True)
        
        highlightedIndex = None
        
        if utils.cfg('colorize'):
            kpiDescriptions.resetRaduga()
        
        for h in range(len(self.hosts)):
        
            hostType = hType(h, self.hosts)
            kpiStylesNNN = self.hostKPIsStyles[h]
            
            dbinfo = ''

            if 'db' in self.hosts[h] and 'service' in self.hosts[h] and hostType == 'service':

                if cfg('legendTenantName') and self.hosts[h].get('db'):
                    dbinfo += self.hosts[h].get('db', '') + ' '

                if cfg('legendServiceName') and self.hosts[h].get('service'):
                    dbinfo += self.hosts[h].get('service', '')
                    
            if dbinfo != '':
                dbinfo = ', ' + dbinfo
            
            if self.legend == 'hosts' and len(self.nkpis[h]) > 0:
                # put a host label
                lkpisl.append('%s:%s%s' % (self.hosts[h]['host'], self.hosts[h]['port'], dbinfo))
                lmeta.append(['host', None, 0, 0])
        
            for kpi in self.nkpis[h]:
            
                gantt = False
                multiline = False
                stacked = False
                
                if kpi not in self.nscales[h]:
                    continue

                if self.legend == 'hosts': ## it is either hosts or None now so 'hosts' basically mean it is enabled
                
                    subtype = kpiStylesNNN[kpi].get('subtype')
                    
                    kpiKey = f"{self.hosts[h]['host']}:{self.hosts[h]['port']}/{kpi}"

                    if subtype == 'gantt':
                        gantt = True
                    elif subtype == 'multiline':
                        stacked = kpiStylesNNN[kpi]['stacked']
                        stacked = safeBool(stacked)
                        multiline = True
                        
                    label = kpiStylesNNN[kpi]['label']
                    
                    if not gantt and kpi in self.nscales[h] and 'unit' in self.nscales[h][kpi]:
                        unit = ' ' + self.nscales[h][kpi]['unit']
                        
                        if kpi in self.nscales[h]: #if those are scanned already
                        
                            if multiline:
                                kpiDescriptions.resetRaduga()
                                label += ': ' + self.nscales[h][kpi]['label'] + unit + ': <$b$>multiline'
                                
                                if stacked:
                                    label += ', stacked'

                                lkpis.append(kpi)
                                lkpisl.append(label)
                                lmeta.append(['multiline', None, 0, 16])
                                
                                legendCount = kpiStylesNNN[kpi]['legendCount']
                                legendCount = safeInt(legendCount, 5)
                                
                                others = kpiStylesNNN[kpi].get('others')
                                
                                if others:
                                    others = safeBool(others)
                                    
                                    if others:
                                        legendCount += 1

                                gbn = min(len(self.ndata[h][kpi]), legendCount)
                                for i in range(gbn):
                                
                                    gb = self.ndata[h][kpi][i][0]
                                    
                                    label = gb
                                    
                                    label += ': max: ' + str(self.nscalesml[h][kpi][gb]['max_label']) + unit
                                    label += ', last: ' + str(self.nscalesml[h][kpi][gb]['last_label']) + unit
                                
                                    lkpis.append(kpi)
                                    lkpisl.append(label)

                                    if kpiStylesNNN[kpi]['multicolor']:
                                        pen = kpiDescriptions.getRadugaPen()
                                    else:
                                        pen = self.kpiPen[h][kpi]
                                        
                                    if kpi == self.highlightedKpi and h == self.highlightedKpiHost and i == self.highlightedGBI:
                                        pen = QPen(pen)
                                        pen.setWidth(2)
                                    else:
                                        pen.setWidth(1)

                                    lmeta.append(['multiline', pen, 16, 44])
                            else: 
                                # regular kpi
                                label += ': ' + self.nscales[h][kpi]['label'] + unit + ', max: ' + self.nscales[h][kpi]['max_label'] + unit + ', last: ' + self.nscales[h][kpi]['last_label'] + unit

                                lkpis.append(kpi)
                                lkpisl.append(label)
                                
                                if utils.cfg('colorize'):
                                    pen = kpiDescriptions.getRadugaPen()
                                else:
                                    pen = kpiDescriptions.customPen(kpiKey, self.kpiPen[h][kpi])
                                    
                                if kpi == self.highlightedKpi and h == self.highlightedKpiHost:
                                    pen = QPen(pen)
                                    pen.setWidth(cfg('chartWidth', 1)*2)
                                else:
                                    pen.setWidth(cfg('chartWidth', 1))
                                    
                                lmeta.append(['', pen, 0, 44])
                                
                    else:
                    
                        # label defined before if

                        lkpis.append(kpi)
                        lkpisl.append(label)
                        
                        if kpiKey in kpiDescriptions.customColors:
                            c = kpiDescriptions.customColors[kpiKey]
                            pen = QPen(QColor(int(c[0]*0.75), int(c[1]*0.75), int(c[2]*0.75)))
                            brshColor = QColor(c[0], c[1], c[2])
                        else:
                            pen = self.kpiPen[h][kpi]
                            brshColor = kpiStylesNNN[kpi]['brush']
                        
                        lmeta.append(['gantt', [QBrush(brshColor), pen], 0, 44])
                    
        # calculates longest label width
        
        if len(lkpisl) != len(lmeta):
            
            log('[W] lkpisl != lmeta', 2)

            log('[W] dumping lkpisl array', 2)
            for z in lkpisl:
                log('[W] %s' % str(z), 2)

            log('[W] dumping lmeta array', 2)
            for z in lmeta:
                log('[W] %s' % str(z), 2)
        
        i = 0
        for label in lkpisl:
        
            ident = 4  + lmeta[i][3]
        
            ll = fm.width(label) + ident + 8
            
            if ll > lLen:
                lLen = ll
                
            i += 1

        fontHeight = fm.height()
        
        qp.setPen(QColor('#888'))
        qp.setBrush(QColor('#FFF'))
        
        if self.legendRender == False and (stopX - startX < 400):
            return
        
        if self.legendRender == True:
            #this is only a legend copy call
            leftX = 10 + self.side_margin
            
        else:
            if startX < self.side_margin:
                leftX = 10 + self.side_margin + startX
            else:
                leftX = 10 + startX

        if drawTimeScale:
            self.legendHeight = fontHeight * (len(lkpisl) + 1)+8 + 4
        else:
            self.legendHeight = fontHeight * (len(lkpisl))+8
            
        self.legendWidth = lLen

        qp.drawRect(leftX, 10 + self.top_margin + self.y_delta, self.legendWidth, self.legendHeight)
        
        # this if for Copy Legend action
        # so call for render will be with startX = 0, so we fake leftX
        
        self.legendRegion = QRegion(10 + self.side_margin, 10 + self.top_margin + self.y_delta, self.legendWidth + 1, self.legendHeight + 1)
        
        qp.setFont(lFont)
        
        i = 0
        
        for i in range(len(lmeta)):
        
            meta = lmeta[i]
            kpi = lkpisl[i]
            kpiPen = meta[1]
        
            #if lpens[i] is not None:
            if meta[0] == 'gantt':
                qp.setBrush(kpiPen[0])
                qp.setPen(kpiPen[1])
                qp.drawRect(leftX + 4, int(10 + self.top_margin + fontHeight * (i+1) - fontHeight/4 + self.y_delta - 2), 36, 4)
                
                ident = 4  + meta[3]
                
            elif meta[0] != 'host':
                if kpiPen:
                
                    '''
                    if highlightedIndex:
                        if highlightedIndex == i:
                            kpiPen.setWidth(2)
                        else:
                            kpiPen.setWidth(1)
                    '''

                    qp.setPen(kpiPen)
                    
                    pen_ident = meta[2]
                    
                    qp.drawLine(leftX + pen_ident + 4, int(10 + self.top_margin + fontHeight * (i+1) - fontHeight/4 + self.y_delta), \
                                    leftX + 40, int(10 + self.top_margin + fontHeight * (i+1) - fontHeight/4 + self.y_delta))
                
                ident = 4 + meta[3]
            else:
                ident = 4 + meta[3] 
            
            qp.setPen(QColor('#000'))
            
            splt = kpi.find('<$b$>') # check if the label has separator...
            if splt > 0:
                #dirty multiline text highlighter...
                black = kpi[:splt]
                blue = kpi[splt+5:]
                
                qp.drawText(leftX + ident, 10 + int(self.top_margin + fontHeight * (i+1) + self.y_delta), black)
                
                ident2 = fm.width(black)
                qp.setPen(QColor('#44E'))
                qp.drawText(leftX + ident + ident2, 10 + int(self.top_margin + fontHeight * (i+1) + self.y_delta), blue)
                
            else:
                #normal regular kpi
                qp.drawText(leftX + ident, 10 + int(self.top_margin + fontHeight * (i+1) + self.y_delta), str(kpi))
                        
        if drawTimeScale:
            qp.drawText(leftX + 4, 10 + int(self.top_margin + fontHeight * (i+2) + self.y_delta) + 6, 'Time scale: ' + self.timeScale)
              
    @profiler
    def drawChart(self, qp, startX, stopX):
    
        '''
            draws enabled charts
            scales need to be calculated/adjusted beforehand
        '''
    
        def adjustGradient(clr, clrTo, v):
        
            #clrTo = QColor('#F00')
            
            (toR, toG, toB) = (clrTo.red(), clrTo.green(), clrTo.blue())
            (frR, frG, frB) = (clr.red(), clr.green(), clr.blue())
            
            #print(v)
            #print(clr.red(), clr.green(), clr.blue())
            
            r = int(frR + (toR - frR) * v)
            g = int(frG + (toG - frG) * v)
            b = int(frB + (toB - frB) * v)
            
            clr = QColor(r, g, b)
            
            #print(clr.red(), clr.green(), clr.blue())
            
            return clr
            
        def longestStr(str):
        
            l = 0
            ls = ''
            
            for s in str.split('\n'):
                if l < len(s):
                    l = len(s)
                    ls = s
            
            return ls
            
        def calculateOne(asyncMultiline=False):
            #start_point = 0  # only requred for performance analysis, disabled
        
            x0 = 0
            y0 = 0
            
            points_to_draw = 0
            points_to_skip = 0
            
            if self.nscales[h][kpi]['y_max'] == 0:
                y_scale = 0
            else:
                y_scale = (wsize.height() - top_margin - self.bottom_margin - 2 - 1)/(self.nscales[h][kpi]['y_max'] - self.nscales[h][kpi]['y_min'])
                
            x_scale = self.step_size / self.t_scale


            if array_size >= 2:
                timeStep = time_array[1]-time_array[0]
            else:
                #actually no stuff will be drawn as just one data value available
                timeStep = 3600
                
            drawStep = timeStep*x_scale + 2
            
            i = -1

            while i < array_size-1:
                i+=1
                #log(self.data['time'][i])
                
                #if time_array[i] < from_ts or time_array[i] > self.t_to.timestamp() - self.delta:
                if time_array[i] < from_ts:
                    #nobody asked to draw this...
                    continue
                    
                x = (time_array[i] - from_ts) # number of seconds
                x = self.side_margin + self.left_margin + x * x_scale

                # if i > 0:
                #     deb(f'calculated x value is: ({(time_array[i] - from_ts) - (time_array[i-1] - from_ts)}): {x}')

                if x < startX - drawStep or x > stopX + drawStep:
                    
                    if i + 1000 < array_size:
                        x1000 = (time_array[i+1000] - from_ts) # number of seconds
                        x1000 = self.side_margin + self.left_margin +  x1000 * x_scale
                        
                        if x1000 < startX - drawStep:
                            #fast forward
                            i += 1000
                            
                    if x > stopX + drawStep:
                        break
                
                    #so skip this point as it's out of the drawing area
                    continue
                #else:
                #    if start_point == 0:
                #        t1 = time.time()
                #        start_point = i
                        
                #y = self.ndata[h][kpi][i]
                y = dataArray[i]
                
                if y < 0:
                    y = wsize.height() - self.bottom_margin - 1
                else:
                    #y = self.nscales[h][kpi]['y_min'] + y*y_scale #562
                    y = (y - self.nscales[h][kpi]['y_min']) * y_scale #562
                    y = round(wsize.height() - self.bottom_margin - y) - 2

                if False and x0 == int(x) and y0 == int(y): # it's same point no need to draw
                    points_to_skip += 1
                    continue
                    
                #log('y = %i' % (y))
                
                # I wander how much this slows the processing...
                # to be measured
                if self.highlightedPoint == i and kpi == self.highlightedKpi and h == self.highlightedKpiHost:
                
                    if highlight and (subtype != 'multiline' or self.highlightedGBI == rn):
                        qp.drawLine(int(x-5), int(y-5), int(x+5), int(y+5))
                        qp.drawLine(int(x-5), int(y+5), int(x+5), int(y-5))

                x0 = int(x)
                y0 = int(y)
                    
                    
                #print(x, y)

                if asyncMultiline and dataArray[i] == -1:
                    # just skip this point for the async multiline KPIs
                    # it might require additional check, like if the
                    # previous point for same kpi is not -1... i > 0?
                    # but so far looks good
                    # #799
                    pass
                else:
                    points[points_to_draw] = QPoint(int(x), int(y))
                    points_to_draw += 1
                '''
                try: 
                    points[points_to_draw] = QPoint(x, y)
                    points_to_draw += 1
                except:
                    log('failed: %s %i = %i, x, y = (%i, %i)' % (kpi, i, self.data[kpi][i], x, y))
                    log('scales: %s' % (str(self.scales[kpi])))
                    break
                '''

            #if start_point == 0:
            #   t1 = time.time()
                
            return points_to_draw
                
        #log('simulate delay()')
        #time.sleep(2)
        
        #if len(self.data) == 0 or len(self.data['time']) == 0: # no data loaded at all
        #    return
        
        wsize = self.size()

        from_ts = self.t_from.timestamp() - self.delta # compensate uneven offsets
        
        #log('self.ndata: %s' % str(self.ndata))
        if len(self.ndata) == 0:
            return

        t0 = time.time()
        
        
        top_margin = self.top_margin + self.y_delta
            
        raduga_i = 0
        

        self.gotGantt = False
        
        for h in range(len(self.hosts)):
        
            #print('draw host:', self.hosts[h]['host'], self.hosts[h]['port'])

            if len(self.ndata[h]) == 0:
                continue
                
            hostKey = self.hosts[h]['host'] + ':' + self.hosts[h]['port']
            
            kpiStylesNNN = self.hostKPIsStyles[h]
            
            for kpi in self.nkpis[h]:
                #print('draw kpi', kpi)
                #print('draw kpi, h', h)
                
                if kpi not in self.ndata[h]:
                    # alt-added kpis here, already in kpis but no data requested
                    continue
                    #return -- but draw the rest hosts/kpis

                if kpi not in self.nscales[h]:
                    # Sometimes (!) like in request_kpis -> exception -> yesNoDialog it is not modal
                    #               and unmotivated (?) paintEvent called with half-filled data structures
                    #               nkpis already filled but scales not calculated, sooo....
                    
                    return
            
                #log('lets draw %s (host: %i)' % (str(kpi), h))
                
                kpiKey = hostKey + '/' + kpi

                if kpi not in kpiStylesNNN:
                    log('[!] kpi removed: %s, skipping in drawChart and removing...' % (kpi), 2)
                    self.nkpis[h].remove(kpi)
                    continue
                    
                if kpiStylesNNN[kpi]['subtype'] == 'gantt':
                    gantt = True
                    self.gotGantt = True
                    
                    if kpiStylesNNN[kpi].get('title'):
                        title = True
                    else:
                        title = False

                    if kpiStylesNNN[kpi].get('gradient'):
                        gradient = True
                    else:
                        gradient = False

                    if kpiStylesNNN[kpi].get('manual_color'):
                        manual_color = True
                    else:
                        manual_color = False

                else:
                    gantt = False
                
                timeKey = kpiDescriptions.getTimeKey(kpiStylesNNN, kpi)
                
                if timeKey not in self.ndata[h] and kpiStylesNNN[kpi].get('subtype') != 'gantt':
                    # this is possible for example when custom KPI definition changed
                    # not relevant for gantt as it does not have time key at all
                    log('[!] here --> kpi removed: %s - %s, skipping!' % (timeKey, kpi), 2)
                    continue
                    
                if gantt:
                    gFont = QFont ('SansSerif', kpiStylesNNN[kpi]['font'])
                    gtFont = QFont ('SansSerif', kpiStylesNNN[kpi]['tfont'])
                    
                    fm = QFontMetrics(gFont)
                    tfm = QFontMetrics(gtFont)
                    
                    fontHeight = fm.height()
                    tFontHeight = tfm.height()
                    
                    fontWidth = 0
                    
                    gc = self.ndata[h][kpi]
                    
                    for e in gc:
                        width = fm.width(e)
                        
                        if fontWidth < width:
                            fontWidth = width

                    # self.left_margin = fontWidth + 8

                    x_scale = self.step_size / self.t_scale

                    if kpiKey in kpiDescriptions.customColors:
                        c = kpiDescriptions.customColors[kpiKey]
                        qp.setBrush(QColor(c[0], c[1], c[2])) # bar fill color
                        ganttBaseColor = QColor(c[0], c[1], c[2])
                    else:
                        qp.setBrush(kpiStylesNNN[kpi]['brush']) # bar fill color
                        ganttBaseColor = kpiStylesNNN[kpi]['brush']
                        
                    ganttFadeColor = kpiStylesNNN[kpi]['gradientTo']  # does not depend of custom colors
                                        
                    if len(gc) > 0:
                        yr0, yr1 = kpiStylesNNN[kpi]['y_range']
                        
                        sqlIdx = kpiStylesNNN[kpi]['sql']
                        
                        try:
                            #yr0p = processVars(sqlIdx, yr0)
                            #yr1p = processVars(sqlIdx, yr1)
                            yr0p = yr0
                            yr1p = yr1
                            yr0 = 100 - max(0, int(yr0p))
                            yr1 = 100 - min(100, int(yr1p))
                        except ValueError:
                            log('[E] Cannot convert all of the variables to integer! %s or %s' % (yr0p, yr1p), 1)
                            yr0 = 100
                            yr1 = 90
                        
                        y_scale = (wsize.height() - top_margin - self.bottom_margin - 2 - 1) / len(gc)
                        y_shift = y_scale/100*yr0 * len(gc)
                        y_scale = y_scale * (yr1 - yr0)/100
                    
                    i = 0
                    
                    hlDesc = None

                    height = kpiStylesNNN[kpi]['width']
                    ganttShift = kpiStylesNNN[kpi]['shift']
                    
                    for entity in gc:
                    
                        qp.setFont(gtFont)
                    
                        y = i * y_scale + y_scale*0.5 - height/2 + y_shift # this is the center of the gantt line
                                                                           # not true, this is the top edge (when corrected with top_margin) 
                                                                           
                        y = int(y)
                    
                        range_i = 0
                        for t in gc[entity]:

                            x = (t[0].timestamp() - from_ts) # number of seconds
                            x = int(self.side_margin + self.left_margin +  x * x_scale)
                            
                            if t[1] is None or t[0] is None:
                                log('[w] null instead of timestamp, skip', str(t))
                                continue

                            width = int((t[1].timestamp() - t[0].timestamp()) * x_scale)
                            
                            if self.highlightedKpi == kpi and self.highlightedKpiHost == h and self.highlightedEntity == entity and self.highlightedRange == range_i:
                                highlight = True
                            else:
                                highlight = False
                            
                            if kpiKey in kpiDescriptions.customColors:
                                c = kpiDescriptions.customColors[kpiKey]
                                ganttPen = QPen(QColor(int(c[0]*0.75), int(c[1]*0.75), int(c[2]*0.75)))
                            else:
                                ganttPen = kpiStylesNNN[kpi]['pen']
                            
                            clr = ganttPen.color()
                            
                            rgb = QColor(int(clr.red()*0.75), int(clr.green()*0.75), int(clr.blue()*0.75))
                            titlePen = QPen(rgb)
                            
                            if highlight == True:
                                ganttPen.setWidth(2)
                            else:
                                ganttPen.setWidth(1)
                            
                            qp.setPen(ganttPen)
                            
                            if kpiStylesNNN[kpi]['style'] == 'bar':

                                if gradient:
                                    bv = t[5]
                                    
                                    if bv is not None:
                                        rgb = adjustGradient(ganttBaseColor, ganttFadeColor, bv)
                                        qp.setBrush(rgb)
                                    
                                if manual_color:
                                    clr = t[5]

                                    if clr:
                                        rgb = QColor(clr)
                                    else:
                                        rgb = ganttBaseColor


                                    qp.setBrush(rgb)


                                    #rgb = QColor(clr.red()*0.75, clr.green()*0.75, clr.blue()*0.75)
                                    #qp.setPen(QPen(rgb))

                                #qp.drawRect(int(x), int(y + top_margin - t[3]*ganttShift), int(width), height)
                                qp.drawRect(x, y + top_margin - t[3]*ganttShift, width, height)
                                    
                                if title:
                                    tv = str(t[4])
                                    #print(tv)
                                    
                                    tWidth = tfm.width(tv)
                                    
                                    qp.setPen(titlePen)
                                    
                                    if tWidth+2 < width:
                                    
                                        halfFont = int(tFontHeight/1.625/2) + 1 #this is considering that fontHeight is 1.625 higher actual height
                                        fontOffset = int(height/2) + halfFont
                                        
                                        #qp.drawLine(x - 10, y + top_margin, x - 1, y + top_margin)
                                        #qp.drawLine(x - 10, y + top_margin - halfFont, x - 1, y + top_margin - halfFont)
                                        #qp.drawText(x, y + top_margin, 'X123X')
                                        
                                        qp.drawText(int(x + width/2 - tWidth/2), int(y + top_margin + fontOffset - t[3]*ganttShift), tv)
                                        
                            else:
                                qp.drawLine(x, y + top_margin + 8, x + width, y + top_margin)
                                
                                qp.drawLine(x + width, y + top_margin + 8, x + width, y + top_margin)
                                qp.drawLine(x, y + top_margin, x, y + top_margin + 8)
                                
                            qp.setPen(ganttPen)

                            #highlighting
                            if highlight:
                                
                                hlDesc = t[2].strip().replace('\\n', '\n')
                                
                                hlWidth = fm.width(longestStr(hlDesc))
                                
                                hlWidth = min(cfg('ganttLabelWidth', 500), hlWidth)
                                
                                # introduce an offset if the label goes off the right border
                                if x + hlWidth > wsize.width():
                                    xOff = wsize.width() - (hlWidth + x + self.side_margin) - 4 # 4 - right margin
                                else:
                                    xOff = 0
                                    
                                # don't put the label goes outside the left border
                                if x + xOff <= 0:
                                    xOff = - x + self.side_margin / 2
                                    
                                nl = hlDesc.count('\n') + 1
                                
                                yShift = t[3]*ganttShift
                                
                                hlRect = QRect(int(x + xOff), int(y + top_margin - fontHeight*nl - 2 - yShift), cfg('ganttLabelWidth', 500), int(fontHeight*nl))
                            
                            range_i += 1


                        qp.setFont(gFont)
                        
                        if stopX - startX > 400 and not self.hideGanttLabels:
                        
                            # only draw labels in case of significant refresh
                        
                            # qp.setBackground(QColor('red')) - does not work
                            # otherwise drawing area too small, it won't paint full text anyway
                            # to avoid only ugly artefacts...
                            #qp.setPen(QColor('#448')) # entity label color
                            
                            clr = ganttPen.color()
                            clr = QColor(int(clr.red()*0.6), int(clr.green()*0.6), int(clr.blue()*0.6))
                            
                            if self.highlightedEntity == entity:
                                gFont.setWeight(QFont.Bold)
                                qp.setFont(gFont)

                            
                            qp.setPen(clr) # entity label color
                            qp.drawText(int(startX + self.side_margin + fontHeight), int(y + top_margin + fontHeight/2), entity);

                            if self.highlightedEntity == entity:
                                gFont.setWeight(QFont.Normal)
                                qp.setFont(gFont)
                        
                        i += 1

                        if hlDesc is not None:
                            if kpiKey in kpiDescriptions.customColors:
                                c = kpiDescriptions.customColors[kpiKey]
                                ganttPen = QPen(QColor(int(c[0]*0.75), int(c[1]*0.75), int(c[2]*0.75)))
                            else:
                                ganttPen = kpiStylesNNN[kpi]['pen']
                            
                            clr = ganttPen.color()
                            clr = QColor(int(clr.red()*0.6), int(clr.green()*0.6), int(clr.blue()*0.6))
                            qp.setPen(clr)
                            
                            qp.drawText(hlRect, Qt.AlignLeft, hlDesc)
                    continue
                    
                # not gantt:
                
                array_size = len(self.ndata[h][timeKey])
                time_array = self.ndata[h][timeKey]

                if cfg('dev__'):
                    for i in range(len(time_array)):
                        if i > 0:
                            deb(f'{i:3} time delta: {time_array[i] - time_array[i-1]}')

                if utils.cfg('colorize'):
                    radugaSize = len(kpiDescriptions.radugaPens)
                    kpiPen = kpiDescriptions.radugaPens[raduga_i % radugaSize]
                    raduga_i += 1
                else:
                    kpiPen = kpiDescriptions.customPen(kpiKey, self.kpiPen[h][kpi])
                
                highlight = False
                
                if kpi == self.highlightedKpi and h == self.highlightedKpiHost:
                    highlight = True
                    if self.highlightedGBI is None:
                        kpiPen.setWidth(2)
                        qp.setPen(kpiPen)
                    else:
                        qp.setPen(kpiPen)
                else:
                    kpiPen.setWidth(1)
                    qp.setPen(kpiPen)

                t0 = time.time()

                points = [0]*array_size
                
                # 
                # a lot of logic moved from here to prepareOne
                # due to multiline support
                #
                
                subtype = kpiStylesNNN[kpi].get('subtype')
                # asyncMultiline = kpiStylesNNN[kpi].get('async')
                if 'async' in kpiStylesNNN[kpi]:
                    asyncMultiline = kpiStylesNNN[kpi].get('async')
                else:
                    asyncMultiline = False
                
                if subtype == 'multiline':
                    rounds = len(self.ndata[h][kpi])
                else:
                    rounds = 1
                    
                if subtype == 'multiline' and kpiStylesNNN[kpi]['multicolor']:
                    kpiDescriptions.resetRaduga()
                
                for rn in range(rounds):
                    if subtype == 'multiline':
                        dataArray = self.ndata[h][kpi][rn][1]
                    else:
                        dataArray = self.ndata[h][kpi]

                    if subtype == 'multiline':
                        if kpiStylesNNN[kpi]['multicolor']:
                            kpiPen = kpiDescriptions.getRadugaPen()

                    if highlight and (subtype != 'multiline' or self.highlightedGBI == rn):
                        kpiPen.setWidth(cfg('chartWidth', 1)*2)
                        qp.setPen(kpiPen)
                    else:
                        kpiPen.setWidth(cfg('chartWidth', 1))
                        qp.setPen(kpiPen)

                    points_to_draw = calculateOne(asyncMultiline)

                    with profiler('myWidget.drawPolyline'):
                        qp.drawPolyline(QPolygon(points[:points_to_draw]))
                
                points.clear()

                t3 = time.time()
                
                #log('%s: skip/calc/draw: %s/%s/%s, (skip: %i)' % (kpi, str(round(t1-t0, 3)), str(round(t2-t1, 3)), str(round(t3-t2, 3)), points_to_skip))
        
        qp.setPen(QColor('#888'))
        qp.drawLine(self.side_margin + self.left_margin, wsize.height() - self.bottom_margin - 1, wsize.width() - self.side_margin, wsize.height() - self.bottom_margin - 1)
        
        
        if self.legend is not None:
            self.drawLegend(qp, startX, stopX)
        
    @profiler
    def drawGrid(self, qp, startX, stopX):
        '''
            draws grid and labels
            based on scale and timespan        
        '''

        wsize = self.size()
        
        # calculate vertical size and force align it to 10
        # in order to have equal y-cells
        
        draw_height = wsize.height()-self.top_margin-self.bottom_margin-1
        y_step = int(draw_height / 10)
        self.y_delta = draw_height - y_step*10

        #adjust the margin
        top_margin = self.top_margin + self.y_delta
            

        qp.setPen(QColor('#888'))
        qp.drawRect(self.side_margin + self.left_margin, top_margin, wsize.width()-self.side_margin*2 - self.left_margin, wsize.height()-top_margin-self.bottom_margin-1)

        qp.setPen(QColor('#000'))
        qp.setFont(QFont('SansSerif', self.conf_fontSize))
        
        t_scale = self.t_scale  # seconds in one grid cell, based on zoom: '4 hours' = 4*3600

        deb(f't_to: {self.t_to}')
        deb(f't_from: {self.t_from}')
        seconds = (self.t_to - self.t_from).total_seconds()
        
        qp.setPen(self.gridColor)

        # vertical scale lines
        for j in range(1,10):
            y = top_margin + j * y_step
            
            if j == 5:
                qp.setPen(self.gridColorMj) #50% line
            
            qp.drawLine(self.side_margin + self.left_margin + 1, y, wsize.width()-self.side_margin - 1, y)
            
            if j == 5:
                qp.setPen(self.gridColor)
        
        #x is in pixels
        x = self.side_margin + self.left_margin + self.step_size

        # now have to align this to have proper marks

        # this is where the confusion is coming from t_from is in local timestamp
        # but we hope it to be in system TZ...
        
        tsfix = self.t_from.replace(tzinfo=self.tzInfo)
        self.delta = tsfix.timestamp() % t_scale # delta from start of the grid to time_from

        log(f'{t_scale=}', component='tz')
        log(f'delta calculation, {self.t_from.timestamp()}%{t_scale} = {self.delta}', component='tz')
        log(f'from: {self.t_from.timestamp()}', component='tz')

        if not cfg('bug795', False) and False:        # lol, seems a bug indeed, #866
            if t_scale == 60*60*4 or True:
                # tzCalc = datetime.datetime.strptime('2023-09-03 00:00:00', '%Y-%m-%d %H:%M:%S')
                # tzCalc = datetime.datetime.combine(datetime.date.today(), datetime.time(0,0,0))
                tzCalc = datetime.datetime.combine(self.t_from.date(), datetime.time(0,0,0))
                tzGridCompensation = tzCalc.timestamp() % (24*3600) % t_scale
                log(f'timestamp: {tzCalc=}', component='tz')
                log(f'timestamp: {tzCalc.timestamp()}', component='tz')
                log(f'{self.delta=}', component='tz')
                log(f'{tzGridCompensation=}', component='tz')
                self.delta -= tzGridCompensation    # not sure, could be a bug (what if negative?)
                log(f'{self.delta=}', component='tz')

        bottom_margin = self.bottom_margin
        side_margin = self.side_margin
        delta = self.delta

        x_left_border = 0 - self.pos().x() # x is negative if scrolled to the right
        x_right_border = 0 - self.pos().x() + self.parentWidget().size().width()

        while x < ((seconds / t_scale + 1) * self.step_size):
        
            #if x < x_left_border or x > x_right_border:
            if x < startX - self.font_width3 or x > stopX + self.font_width3: 
                x += self.step_size
                
                continue
                
            qp.drawLine(x, top_margin + 1, x, wsize.height() - bottom_margin - 2)
            
            # c_time = self.t_from + datetime.timedelta(seconds=(x - side_margin - self.left_margin)/self.step_size*t_scale - delta)
            c_time = self.t_from + datetime.timedelta(seconds=(x - side_margin - self.left_margin)/self.step_size*t_scale - delta)

            if False:
                log(f'grid time: {c_time}', component='tz')
                # tzCalc = datetime.datetime.combine(self.t_from.date(), datetime.time(0,0,0))
                # tzGridCompensation = tzCalc.timestamp() % (24*3600) % t_scale
                # log(f'timestamp: {tzCalc=}', component='tz')
                # log(f'timestamp: {tzCalc.timestamp()}', component='tz')
                # log(f'{tzGridCompensation=}', component='tz')
                # self.delta -= tzGridCompensation    # not sure, could be a bug (what if negative?)
                # log(f'{self.delta=}', component='tz')

            major_line = False
            date_mark = False
            
            if t_scale <= 60*60:
                label = c_time.strftime("%H:%M:%S")
            else:
                label = c_time.strftime("%H:%M")
                
                
            sec_scale = None
            min_scale = None
            hrs_scale = None
            
            if t_scale == 1:
                sec_scale = 10
                hrs_scale = 60*1
            elif t_scale == 10:
                sec_scale = 60
                hrs_scale = 60*5
            elif t_scale == 60:
                min_scale = 5
                hrs_scale = 5*4
            elif t_scale == 60*5:
                min_scale = 30
                hrs_scale = 30*4
            elif t_scale == 60*10:
                min_scale = 60
                hrs_scale = 60*4
            elif t_scale == 60*15:
                min_scale = 60*2
                hrs_scale = 60*2*4
            elif t_scale == 60*30:
                min_scale = 60*2
                hrs_scale = 60*2*4
            elif t_scale == 3600:
                min_scale = 60*4
                hrs_scale = 60*4*3 # god damit, 3, really?
            elif t_scale == 4*3600:
                min_scale = 60*24
                hrs_scale = 60*24*2
            elif t_scale == 8*3600:
                min_scale = 3600*24*2
                hrs_scale = 60*24*4
            elif t_scale == 12*3600:
                min_scale = 3600*24*2
                hrs_scale = 60*24*4

            # number of minutes since the grid start
            min = int(c_time.strftime("%H")) *60 + int(c_time.strftime("%M"))

            if sec_scale is not None:
                if c_time.timestamp() % sec_scale == 0:
                    major_line = True

                if c_time.timestamp() % hrs_scale == 0:
                    date_mark = True
            elif min % min_scale == 0:
                major_line = True
                
                if hrs_scale <= 60*24:
                    if min % hrs_scale == 0:
                        date_mark = True
                else:
                    if min == 0:
                        day = int(c_time.strftime("%d"))
                        if day % (hrs_scale/60/24) == 1:
                            date_mark = True

            ct = c_time.strftime('%Y-%m-%d %H:%M:%S')
            # log(f'{ct=}, {min=}, {major_line=}', component='tz')

            if major_line:
            
                qp.setPen(self.gridColorMj)
                qp.drawLine(x, top_margin + 1, x, wsize.height() - bottom_margin - 2)

                qp.setPen(QColor('#000'))
                
                if len(label) == 5: # 00:00
                    label_width = self.font_width1
                else:
                    label_width = self.font_width2
                 
                # #587
                                
                if t_scale < 8*3600 or date_mark:
                    # print(wsize.height(), bottom_margin, self.font_height, label)
                    qp.drawText(int(x-label_width), wsize.height() - bottom_margin + self.font_height, label)

                if date_mark:
                    label = c_time.strftime('%Y-%m-%d')
                    qp.drawText(int(x-self.font_width3), int(wsize.height() - bottom_margin + self.font_height*2), label)
                    
                qp.setPen(self.gridColor)
        
            x += self.step_size
        
    def paintEvent(self, QPaintEvent):

        if self.paintLock:
            # paint locked  for some reason
            return
            
        startX = QPaintEvent.rect().x()
        stopX = startX + QPaintEvent.rect().width()
        
        qp = QPainter()
        
        super().paintEvent(QPaintEvent)
        
        qp.begin(self)

        self.drawGrid(qp, startX, stopX)
        self.drawChart(qp, startX, stopX)
        
        qp.end()


    def toggleGanttLabels(self):
        if self.hideGanttLabels:
            self.hideGanttLabels = False
        else:
            self.hideGanttLabels = True

        self.repaint()
        
    def toggleLegend(self):
        if self.legend is None:
            self.legend = 'hosts'
        else:
            self.legend = None
        self.repaint()
        
    def checkDayLightSaving(self):
        '''
        Checks if there is a DL saving occured during the from-to period
        Displays a stupid warning if yes

        '''
        log(f'okay, check daylight, {self.tzChangeWarning=}, bug920={cfg("bug920")}', component='daylight')
        if self.tzChangeWarning == False and cfg('bug920', False) == False:
            date_from = self.t_from.date()
            date_to = self.t_to.date()
            tzCalc = datetime.datetime.combine(date_from, datetime.time(0,0,0))
            tzCalcTo = datetime.datetime.combine(date_to, datetime.time(0,0,0))
            tzGridCompensation = tzCalc.timestamp() % (24*3600)
            tzGridCompensationTo = tzCalcTo.timestamp() % (24*3600)
            log(f'real check: {tzCalc}, {tzCalcTo}', component='daylight')

            if tzGridCompensation != tzGridCompensationTo and self.tzChangeWarning == False:
                log('yes, daylight saving change detected...', component='daylight')
                log('Daylight change detected, display a warning. You can disable this check by setting bug920: True.', 2)
                title = 'Time zone change warning'
                message = f'A daylight saving adjustment took place during the period:\n from: {date_from} to: {date_to}\n\nPlease be informed that the data shown on the chart does not factor in this change; it is based on the time zone in the beggining of the period.\n\nAs a result, the data at the end of the period is one hour off.\n\nWe apologize for any confusion and kindly request your support in calling for the discontinuation of daylight saving adjustments as it does not make any sense in 21st Century.\n\nSorry for that, permanent fix is on the way.'

                msgBox = QMessageBox(self)
                msgBox.setWindowTitle(title)
                msgBox.setText(message)
                msgBox.setStandardButtons(QMessageBox.Ok)

                iconPath = resourcePath('ico', 'favicon.png')
                msgBox.setWindowIcon(QIcon(iconPath))
                msgBox.setIcon(QMessageBox.Warning)

                reply = msgBox.exec_()

                self.tzChangeWarning = True


def moveAsync(direction, d, i):
    '''this one to skip -1s in multiline async'''

    if direction == 'left':
        i -= 1
        while i > 0 and d[i] < 0:
            i -= 1
        if d[i] != -1 and i >= 0:
            return i
    else:
        i += 1
        while i < len(d)-1 and d[i] < 0:
            i += 1
        if i < len(d) and d[i] != -1:
            return i

    return None



class chartArea(QFrame):
    
    statusMessage_ = pyqtSignal(['QString', bool])
    
    connected = pyqtSignal(['QString'])
    
    kpiToggled = pyqtSignal([int])
    
    hostsUpdated = pyqtSignal()
    scalesUpdated = pyqtSignal()
    
    selfRaise = pyqtSignal(object)
    
    chartIndicator = pyqtSignal(['QString']) # indicator update request
    
    connection = None # db connection
    
    #those two depricated since #739
    hostKPIs = [] # list of available host KPIS, sql names
    srvcKPIs = [] # list of available srvc KPIS, sql names
    
    # those two gonna be per host:
    hostKPIsList = []          # list of KPIs 
    hostKPIsStyles =   []      # KPI styles to replace kpiStylesNN
    
    dbProperties = {} # db properties, like timeZone, kpis available, etc
    
    dp = None # data provider object, belongs to chart area
    ndp = [] # new dp approach, list now.
    
    timer = None
    refreshCB = None
    
    lastReloadTime = None #reload timer
    lastHostTime = None #one host timer
    
    #last refresh time range
    fromTime = None
    toTime = None
    
    collisionsCurrent = None
    collisionsDirection = None
    
    suppressStatus = None # supress status update, intended for autorefresh theshold vialation message
    
    def dpDisconnected(self):
        self.setStatus('disconnected', True)

    def dpBusy(self, flag):
    
        if flag:
            self.setStatus('sync', True)
        else:
            if self.timer:
                self.setStatus('autorefresh', True)
            else:
                self.setStatus('idle', True)


    def indicatorSignal(self):
        self.selfRaise.emit(self.parentWidget())

    
    def disableDeadKPIs(self):
        
        chart = self.widget
        
        if len(chart.nkpis) == 0:
            log('[w] disableDeadKPIs: no kpis at all, exit')
            return
            
        for host in range(len(chart.hosts)):
            kpiStylesNNN = self.hostKPIsStyles[host]

            delKpis = []
            for kpi in chart.nkpis[host]:
                if kpi not in kpiStylesNNN:
                    delKpis.append(kpi)
                    
            for kpi in delKpis:
                log('[w] kpi %s is dsabled so it is removed from the list of selected KPIs for the host' % (kpi))
                
                chart.nkpis[host].remove(kpi)
                
                if kpi in self.hostKPIsList[host]:
                    self.hostKPIsList[host].remove(kpi)
                    
            delKpis = []
            
            for kpi in self.widget.nscales[host]:
                if kpi != 'time' and kpi not in kpiStylesNNN:
                    delKpis.append(kpi)
                   
            for kpi in delKpis:
                log('[w] removing %s from nscales becaouse it does not exist (disabled?)' % (kpi), 2)
                del self.widget.nscales[host][kpi]
                if kpi in self.widget.ndata[host]:
                    log('[w] removing %s from data ' % (kpi), 2)
                    del self.widget.ndata[host][kpi]
                else:
                    log(f'[w] oops, {kpi} is missing, skip', 2)

    def statusMessage(self, str, repaint = False):
        if repaint: 
            self.statusMessage_.emit(str, True)
        else:
            self.statusMessage_.emit(str, False)
        
    @profiler
    def moveHighlight(self, direction):
        '''
            #639 
            to make it having sence regular there should be:
            
            for regular KPIs:
                1. loop to identify closest value to the selected timestamp
                2. calculate y-value on the screen for those values
                3. chose closest one to prevoiusly selected one
                
                4. somehow deal with collisions - same Y value possible
                
            Gantt KPIs:
                up/down should move through entity, should be simple, 
                but also consider timing
                
            Multiline KPIs:
                probably the simplised one as it is on the same Y-scale
                
            Still want to try to implement this?
            
        '''
        @profiler
        def getY(data, host, timeKey, kpi, pointTime, idxKnown=None, gbi=None):
            @profiler
            def scan(a, v, vals=None):
                '''Scans for a value t in ordered array a, returns index of first value greather t'''
                
                i = 0
                
                l = len(a)
                
                if l < 2:
                    return None
                
                while i<l and a[i]<v:
                    i += 1

                # scan for the latest non-negative... this is actually for asyncMultiline but we dont check here
                while i > 0 and i < l and vals[i] == -1:
                    i -= 1

                # scan for the first not negative...
                if i == 0 and vals[i] == -1:
                    while i < l and vals[i] == -1:
                        i += 1

                if i == l:
                    i -= 1
                    
                return i

            idx = None

            if kpi not in data:
                return None, None

            if gbi is None:
                dataArray = data[kpi]
            else:
                dataArray = data[kpi][gbi][1]

            if idxKnown is None and timeKey in data: #711
                idx = scan(data[timeKey], pointTime, dataArray) # despite multiline, time has the same layout
            else:
                idx = idxKnown
                
            if idx is None:
                log('No proper point in time detected', 5)
                return None, None

            # calculate y of that:
            if self.widget.nscales[host][kpi]['y_max'] == 0:
                y_scale = 0
            else:
                y_scale = (
                    (wsize.height() - self.widget.top_margin - self.widget.bottom_margin - 2 - 1)/
                    (self.widget.nscales[host][kpi]['y_max'] - self.widget.nscales[host][kpi]['y_min'])
                )
               
            if gbi is None:
                y = data[kpi][idx]
            else:
                y = data[kpi][gbi][1][idx]

            if y < 0:
                y = wsize.height() - self.widget.bottom_margin - 1
            else:
                #y = self.nscales[h][kpi]['y_min'] + y*y_scale #562
                y = (y - self.widget.nscales[host][kpi]['y_min']) * y_scale #562
                y = round(wsize.height() - self.widget.bottom_margin - y) - 2
            
            return y, idx
        
        h = self.widget.highlightedKpiHost
        kpiName = self.widget.highlightedKpi
        point = self.widget.highlightedPoint
        tgbi = self.widget.highlightedGBI

        data = self.widget.ndata[h]
        
        kpiStylesNNN = self.hostKPIsStyles[h]
        
        kpis = data.keys()
        
        
        timeKey = kpiDescriptions.getTimeKey(kpiStylesNNN, kpiName)

        if timeKey is None:
            log(f'Cannot identify time key for {kpiName} in {kpis}', 2)
            self.statusMessage('Cannot identify time key, check logs, please report this issue.')
            return
            
        subtype = kpiStylesNNN[kpiName].get('subtype')
        
        if subtype == 'gantt':
            self.statusMessage(f'Not implemented for {subtype} yet.')
            return

        pointTime = data[timeKey][point]
        # pointTS = datetime.datetime.fromtimestamp(pointTime)
                
        # this will be required in messy getY implementation
        wsize = self.widget.size()

        # extract current Y (idx ignored)
        targetY, idx = getY(data, h, timeKey, kpiName, None, idxKnown=point, gbi=tgbi)

        # now iterate through the KPIs of the same style and detect the closest one somehow
                
        ys = [] # list of tuples: (host, kpi, Y, gbi) gbi is not None for multilines
        
        collisions = 0
        
        surogateIdx = 0
                
        for checkHost in range(len(self.widget.nkpis)):
            if len(self.widget.nkpis[checkHost]) == 0:
                continue

            kpiStylesNNN = self.hostKPIsStyles[checkHost]
            
            for checkKPI in self.widget.nkpis[checkHost]:
            
                timeKey = kpiDescriptions.getTimeKey(kpiStylesNNN, checkKPI)
                subtype = kpiStylesNNN[checkKPI].get('subtype')
                
                if subtype == 'gantt':
                    continue

                if subtype == 'multiline':
                    rounds = len(self.widget.ndata[checkHost][checkKPI])
                else:
                    rounds = 1
                
                for rc in range(rounds):

                    if subtype == 'multiline':
                        gbi = rc
                    else:
                        gbi = None
                
                    y, idx = getY(self.widget.ndata[checkHost], checkHost, timeKey, checkKPI, pointTime, idxKnown=None, gbi=gbi)
                    if y is None:
                        continue

                    if y == targetY:
                        if not (checkHost == self.widget.highlightedKpiHost and checkKPI == self.widget.highlightedKpi and tgbi==gbi):
                            collisions += 1
                        
                    surogateIdx += 1
                        
                    if direction == 'up':
                        if y <= targetY:
                            ys.append((checkHost, checkKPI, y, idx, surogateIdx, gbi))
                    else:
                        if y >= targetY:
                            ys.append((checkHost, checkKPI, y, idx, surogateIdx, gbi))

        #ys = sorted(ys, lambda x: x[2], reverse=(direction=='up'))
        
        # collisions detected already means that we are in collisions _second_ time so + 1
        # but the original kpi is not listed in ys, so -1 
        log(f'--> collisions current: {self.collisionsCurrent}, detected: {collisions}', 5)
        
        compensate = 0
        if self.collisionsDirection != direction:
            compensate = 1
            
        if self.collisionsCurrent is None and collisions:
            if direction == 'up':
                self.collisionsCurrent = 0 + 1
            else:
                self.collisionsCurrent = collisions
            
        log(f'--> collisions current: {self.collisionsCurrent}, detected: {collisions}', 5)
        
        if not ys:
            self.statusMessage(f'Nothing identified {direction}')
            return
            
        #ys = sorted(ys, key=lambda x: (x[2], x[1], x[0]), reverse=(direction=='up'))
        
        if direction=='up':
            revOrder = True
        else:
            revOrder = False
        
        #ys = sorted(ys, key=lambda x: (x[2], sign*x[4]), reverse=revOrder)
        ys = sorted(ys, key=lambda x: (x[2], -1*(x[5] or 0), x[4]), reverse=revOrder) #652 add gbi into ordering...
        
        log(f'sorted, {revOrder=}', 5)

        for zz in ys:
            log(zz, 5)

        if self.collisionsCurrent is None:
            shift = 1
        else: 
            if direction == 'up':
                if collisions and compensate:
                    self.collisionsCurrent += 1
                shift = self.collisionsCurrent
            else:
                if collisions and compensate:
                    self.collisionsCurrent -= 1
                shift = collisions - self.collisionsCurrent + 1

        log(f'shift: {shift}, collisionsCurrent: {self.collisionsCurrent}', 5)
        
        if shift >= len(ys):
            self.statusMessage(f'Nothing identified {direction}')
            return
            
        yVal = ys[shift]
        
        if self.collisionsCurrent is not None:
            if collisions:
                if direction == 'up':
                    self.collisionsCurrent += 1
                    
                    if self.collisionsCurrent > collisions+1:
                        self.collisionsCurrent = None
                    
                else:
                    self.collisionsCurrent -= 1

                    if self.collisionsCurrent < 0:
                        self.collisionsCurrent = None
            else:
                self.collisionsCurrent = None
                
        log(f'<-- collisions current: {self.collisionsCurrent}, detected: {collisions}', 5)

        if yVal[5] is not None:
            log(f'checkHost={checkHost}, yVal[1]={yVal[1]}, yVal[5]={yVal[5]}')
            checkHost = yVal[0]     # so not sure here... need proper system to test, #706
            gb = self.widget.ndata[checkHost][yVal[1]][yVal[5]][0]
            mls = f'[{gb}] ({yVal[5]})'
        else:
            mls = ''

        log(f'okay, the leader is: {yVal[0]}/{yVal[1]}{mls}', 5)

        self.collisionsDirection = direction
        
        reportDelta = False
        if self.widget.highlightedKpi == yVal[1] and self.widget.highlightedKpiHost == yVal[0]:
            reportDelta = True

        self.widget.highlightedKpiHost = yVal[0]
        self.widget.highlightedKpi = yVal[1]
        self.widget.highlightedPoint = yVal[3]
        self.widget.highlightedGBI = yVal[5]

        self.reportHighlighted(reportDelta)
        self.widget.update()
        

    def reportHighlighted(self, reportDelta=False):
    
        point = self.widget.highlightedPoint
        host = self.widget.highlightedKpiHost
        kpi = self.widget.highlightedKpi
        
        #this is black magic copy paste from scanforhint
        kpiStylesNNN = self.hostKPIsStyles[host]
        timeKey = kpiDescriptions.getTimeKey(kpiStylesNNN, kpi)

        hst = self.widget.hosts[host]['host']
        if self.widget.hosts[host]['port'] != '':
            hst += ':'+str(self.widget.hosts[host]['port'])
        
        d = kpiStylesNNN[kpi].get('decimal', 0)
        
        subtype = kpiStylesNNN[kpi].get('subtype')
        
        if subtype == 'gantt':
            entity = self.widget.highlightedEntity
            reportRange = self.widget.highlightedRange
            
            t = self.widget.ndata[host][kpi][entity][reportRange]

            t0 = t[0].time().isoformat(timespec='milliseconds')
            t1 = t[1].time().isoformat(timespec='milliseconds')

            interval = '[%s - %s]' % (t0, t1)
            
            det = '%s, %s, %s: %s/%i %s' % (hst, kpi, entity, interval, t[3], t[2])
            
            self.statusMessage(det)
            return

            
        elif subtype == 'multiline':
            gbi = self.widget.highlightedGBI
            gb = self.widget.ndata[host][kpi][gbi][0]
            value = self.widget.ndata[host][kpi][gbi][1][point]
            normVal = kpiDescriptions.normalize(kpiStylesNNN[kpi], value, d)
            
            kpiLabel = f'{kpi}/{gb}'
        else:
            normVal = kpiDescriptions.normalize(kpiStylesNNN[kpi], self.widget.ndata[host][kpi][point], d)
            kpiLabel = kpi

        if reportDelta:
            deltaVal = normVal - self.widget.highlightedNormVal
            deltaVal = ', delta: ' + utils.numberToStr(abs(deltaVal), d)
        else:
            deltaVal = ''

        self.widget.highlightedNormVal = normVal

        scaled_value = utils.numberToStr(normVal, d)

        # host = self.widget.highlightedKpiHost

        if utils.cfg_servertz:
            dpidx = self.widget.hosts[host]['dpi']
            utcOff = self.ndp[dpidx].dbProperties.get('utcOffset', 0)
            ts = datetime.datetime.fromtimestamp(self.widget.ndata[host][timeKey][point], utils.getTZ(utcOff))
        else:
            ts = datetime.datetime.fromtimestamp(self.widget.ndata[host][timeKey][point])

        tm = ts.strftime('%Y-%m-%d %H:%M:%S')
        
        unit = self.widget.nscales[host][kpi]['unit']

        self.widget.setToolTip('%s, %s = %s %s at %s' % (hst, kpiLabel, scaled_value, unit, tm))
        self.statusMessage('%s, %s = %s %s at %s%s' % (hst, kpiLabel, scaled_value, unit, tm, deltaVal))
        
    @profiler
    def moveHighlightGantt(self, direction):
        def getClosest(d, target):
            '''
                finds closest interval in d to target based on center of intervals
                returns index
            '''
        
            closest = 0
            
            minDelta = abs((d[0][0].timestamp()+d[0][1].timestamp())/2 - target)
        
            for i in range(len(d)):
                delta = abs((d[i][0].timestamp()+d[i][1].timestamp())/2 - target)
                
                if minDelta > delta:
                    minDelta = delta
                    closest = i
        
            return closest
        
        host = self.widget.highlightedKpiHost
        kpi = self.widget.highlightedKpi
        entity = self.widget.highlightedEntity
        
        data = self.widget.ndata[host][kpi]
        
        entities = list(self.widget.ndata[host][kpi].keys())
        el = len(data[entity])
        
        changesDone = False
        
        if direction == 'right':
            if self.widget.highlightedRange < el-1:
                self.widget.highlightedRange += 1
                changesDone = True
                
        if direction == 'left':
            if self.widget.highlightedRange > 0:
                self.widget.highlightedRange -= 1
                changesDone = True

        if changesDone:
            self.widget.update()
            self.reportHighlighted()
            return
            
        entry = data[entity][self.widget.highlightedRange]
        
        midt = (entry[0].timestamp()+entry[1].timestamp())/2

        if direction == 'up':
            i = entities.index(entity)
            
            if i < len(entities)-1:
                self.widget.highlightedEntity = entities[i+1]
                self.widget.highlightedRange = getClosest(data[self.widget.highlightedEntity], midt)
                changesDone = True
                
        if direction == 'down':
            i = entities.index(entity)
            
            if i > 0:
                self.widget.highlightedEntity = entities[i-1]
                self.widget.highlightedRange = getClosest(data[self.widget.highlightedEntity], midt)
                changesDone = True
                
        if changesDone:
            self.widget.update()
            self.reportHighlighted()


    def keyPressEventZ(self, event):

        modifiers = QApplication.keyboardModifiers()

        if event.key() == Qt.Key_Up:
            if modifiers == Qt.AltModifier and self.widget.highlightedPoint is not None:
                self.moveHighlight('up')
            elif modifiers == Qt.AltModifier and self.widget.highlightedEntity:
                self.moveHighlightGantt('up')

        if event.key() == Qt.Key_Down:
            if modifiers == Qt.AltModifier and self.widget.highlightedPoint is not None:
                self.moveHighlight('down')
            elif modifiers == Qt.AltModifier and self.widget.highlightedEntity:
                self.moveHighlightGantt('down')
            
        if event.key() == Qt.Key_Left:
            if modifiers == Qt.AltModifier and self.widget.highlightedPoint is not None:
                # move highlighted point one step left
                host = self.widget.highlightedKpiHost
                kpi = self.widget.highlightedKpi


                kpiStylesNNN = self.hostKPIsStyles[host]
                subtype = kpiStylesNNN[kpi].get('subtype')
                gbi = self.widget.highlightedGBI

                if gbi is not None:
                    i = moveAsync('left', self.widget.ndata[host][kpi][gbi][1], self.widget.highlightedPoint)
                    if i is not None:
                        self.widget.highlightedPoint = i

                else:
                    if self.widget.highlightedPoint > 0:
                        self.widget.highlightedPoint -= 1

                self.reportHighlighted(True)
                self.widget.update()
            elif modifiers == Qt.AltModifier and self.widget.highlightedEntity is not None:
                self.moveHighlightGantt('left')
            else:
                x = 0 - self.widget.pos().x() # pos().x() is negative if scrolled to the right
                self.scrollarea.horizontalScrollBar().setValue(x - self.widget.step_size*10)

        elif event.key() == Qt.Key_Right:

            if modifiers == Qt.AltModifier and self.widget.highlightedPoint is not None:
                # move highlighted point one step right
                
                host = self.widget.highlightedKpiHost
                kpi = self.widget.highlightedKpi
                
                kpiStylesNNN = self.hostKPIsStyles[host]
                subtype = kpiStylesNNN[kpi].get('subtype')
                gbi = self.widget.highlightedGBI
                
                if subtype == 'multiline':
                    dSize = len(self.widget.ndata[host][kpi][0][1]) # this is time kpi but for multiline it equals to kpi data itelf...
                else:
                    dSize = len(self.widget.ndata[host][kpi])
                    
                if gbi is not None:
                    i = moveAsync('right', self.widget.ndata[host][kpi][gbi][1], self.widget.highlightedPoint)
                    if i is not None:
                        self.widget.highlightedPoint = i
                else:
                    if self.widget.highlightedPoint < dSize - 1:
                        self.widget.highlightedPoint += 1

                self.reportHighlighted(True)
                self.widget.update()
            elif modifiers == Qt.AltModifier and self.widget.highlightedEntity is not None:
                self.moveHighlightGantt('right')
            else:
                x = 0 - self.widget.pos().x() 
                self.scrollarea.horizontalScrollBar().setValue(x + self.widget.step_size*10)
            
        elif event.key() == Qt.Key_Home:
            self.scrollarea.horizontalScrollBar().setValue(0)
            
        elif event.key() == Qt.Key_End:
            self.scrollarea.horizontalScrollBar().setValue(self.widget.width() - self.width() + 22) # this includes scrollArea margins etc, so hardcoded...
            
        elif event.key() == Qt.Key_L and modifiers == Qt.ControlModifier:
            self.widget.toggleLegend()
        elif event.key() == Qt.Key_L and modifiers & Qt.ControlModifier and modifiers & Qt.ShiftModifier:
            self.widget.toggleGanttLabels()
        else:
            super().keyPressEvent(event)

    def cleanup(self):
        '''
            cleans internal widget structures:
            
                self.widget.ndata[host][kpi]
                self.widget.nkpis[host]
                
                self.widget.nscales[host]
                self.widget.ndata[host]
            
        '''
        
        for host in range(len(self.widget.hosts)):

            if len(self.widget.nkpis) > 0:
                if cfg('dev'):
                    log(f'[cleanup] self.widget.nkpis[{host}] --> {self.widget.nkpis[host]}')
                    
                for kpi in self.widget.nkpis[host]:
                    #print('the same code in checkbocks callback - make a function')
                    #why not just self.widget.nkpis[host].clear() (iutside the loop?)
                    self.widget.nkpis[host].remove(kpi) # kpis is a list
                    
                    if kpi in self.widget.ndata[host]:
                        #might be empty for alt-added
                        del(self.widget.ndata[host][kpi]) # ndata is a dict
                        

                log(f'clear styles {host}')
                self.hostKPIsList[host].clear()
                self.hostKPIsStyles[host].clear()
                        
            else:
                log('[w] kpis list is empty')

            # this part not required in checkbocks callback ')
            
            if len(self.widget.nscales)> 0:
                self.widget.nscales[host].clear() # this one is missing in in checkbocks callback 
                                                  # kinda on purpose, it leaves min/max/etc in kpis table (to be checked)
            if len(self.widget.ndata)> 0:
                self.widget.ndata[host].clear()
                
            self.hostKPIsList[host].clear()
            self.hostKPIsStyles[host].clear()
            
        self.widget.nscales.clear()
        self.widget.ndata.clear()
        
        # need to clear the kpis list as it will be reloaded anyhow
        log('clear styles top lists...')
        self.hostKPIsList.clear()
        self.hostKPIsStyles.clear()

        # 2022-07-14, #676
        self.widget.highlightedKpi = None
        self.widget.highlightedKpiHost = None
        self.widget.highlightedPoint = None
        self.widget.highlightedGBI = None

        # moved from outside for multidp
        self.widget.ndata.clear()
        self.widget.hosts.clear()
        self.widget.nkpis.clear()
        
        log('cleanup complete')
        
    def appendDP(self, dp):
        self.ndp.append(dp)
        
        log(f'list of DPs ({len(self.ndp)}):', 4)
        for dp in self.ndp:
            log(f'    {dp}, {type(dp)}', 4)
            
        idx = len(self.ndp) - 1
            
        return idx
        
    def initDP(self, dpidx, kpis=None, message=None):
        '''
            this one to be called after creating a data provider
            to be called right after dp = new dp
            
            It fills charts structures with actual data aboiut the data source:
            hosts, KPIs, KPI styles
            
            dpidx > 0 implies secondary connection, this is why cleanup will be skipped

            kpis - dict of kpis (per host) to enable on start (and trigger load)
            
            Input parameters
                dpidx - data provider index, integer
                    it, actually, will be only used to set host['dpi'] value
                    
                kpis - list of KPIs to enable, propageted from layout.yaml
                
                message - message to set during initHosts (potentially long execution)
                    it actually used only by dpTrace
                    
            Return value
                None, the results stored into chartarea+widget structures.
            
        '''

        def myIntersect(l1, l2):
            l = []
            
            for v in l1:
                if v in l2:
                    l.append(v)
                    
            return l
            
        dp = self.ndp[dpidx]  #extract the data provider instance
            
            
        if dpidx == 0:
            self.cleanup()
            self.widget.update()
            log('Cleanup complete')
        else:
            log('Secondary DP, no cleanup performed.')
        
        if message:
            self.statusMessage(message)
        else:
            self.statusMessage('Connected, init basic info...')
            
        self.repaint()
        
        try:
            newHosts, newKPIs, newStyles, err = dp.initHosts(dpidx)

            # append hosts, not replace if that would be requred, hosts would be cleared above
            for h in newHosts:
                self.widget.hosts.append(h)
                
            for kpisPerHost in newKPIs:
                self.hostKPIsList.append(kpisPerHost.copy())        # create a corresponding list of KPIs 
                
            for styles in newStyles:
                self.hostKPIsStyles.append(styles.copy())      # create a corresponding list of KPIs

            if err is not None:

                if type(err) == tuple: # modern error provider
                    eType = err[0]
                    errStr = err[1]
                else:
                    eType = 'customKPI'
                    errStr = err

                log('[!] initHosts customKPIException: %s' %  errStr, 2)

                if eType == 'customKPI':
                    msgHeader = 'Custom KPI Error'
                    msgText = 'There were errors during custom KPIs load. Load of the custom KPIs STOPPED because of that.\n\n' + errStr + '\n\nSee more details in rybafish.log file'
                else:
                    msgHeader = 'initHosts Error'
                    msgText = errStr

                if eType:
                    utils.msgDialog(msgHeader, msgText)

        except utils.vrsException as e:
            log('[!] variables processing exception: %s' % (str(e)), 1)
            utils.msgDialog('Initialization Error', 'Variables processing error. Check the variables definition, if the message persists, consider deleting layout.yaml\n\n%s' % (str(e)))
        #except Exception as e:
        #    log('[!] initHosts generic exception: %s, %s' % (str(type(e)), str(e)), 2)
        #    utils.msgDialog('Initialization Error', 'Generic initial error. Probably the app will go unstable, check the logs and consider reconnecting\n\n%s: %s' % (str(type(e)), str(e)))

        if len(self.widget.hosts) == 0 and cfg('noAccessWarning', False) == False:
            msgBox = QMessageBox(self)
            msgBox.setWindowTitle('Connection init error')
            msgBox.setText('Initial connection did not return any data from m_load_history* views.\n\nCheck if your user has proper access:\nMONITORING role?\n\nYou can disable this message by setting "noAccessWarning: True" in config.yaml\n\nYou still can open SQL console (Alt+S) and check manually:\nselect * from m_load_history_host;')
            msgBox.setStandardButtons(QMessageBox.Ok)
            iconPath = resourcePath('ico', 'favicon.png')
            msgBox.setWindowIcon(QIcon(iconPath))
            msgBox.setIcon(QMessageBox.Warning)

            reply = msgBox.exec_()
        
        self.widget.allocate(len(self.widget.hosts))
        self.widget.initPens()
        
        if kpis:
            log('initDP processing', 5)
            for h in range(len(self.widget.hosts)):
                host = self.widget.hosts[h]
                hstKey = '%s:%s' % (host['host'], host['port'])
                
                if hstKey in kpis:
                    kpis_n = kpis_n = myIntersect(kpis[hstKey], self.hostKPIsList[h])
                    self.widget.nkpis[h] = kpis_n

            log('reload from init dp', 4)
            
        if hasattr(dp, 'dbProperties') and 'timeZoneDelta' in dp.dbProperties:
        
            self.widget.timeZoneDelta = dp.dbProperties['timeZoneDelta']
            
            starttime = datetime.datetime.now() - datetime.timedelta(seconds= 12*3600)
            starttime -= datetime.timedelta(seconds= (starttime.timestamp() % 3600 - self.widget.timeZoneDelta))
                    
            self.fromEdit.setText(starttime.strftime('%Y-%m-%d %H:%M:%S'))
            self.toEdit.setText('')
        
        else:
            self.widget.timeZoneDelta = 0

        if utils.cfg_servertz:
            utcOffset = dp.dbProperties.get('utcOffset', 0)
            self.widget.tzInfo = utils.getTZ(utcOffset)

            log(f'Chart tzInfo set to UTC +{utcOffset}', 2)
            
        self.hostsUpdated.emit()
        
        self.statusMessage('ready')

    def scrollSignal(self, mode, size):
        x = 0 - self.widget.pos().x() 
        self.scrollarea.horizontalScrollBar().setValue(int(x + mode*self.widget.step_size*size))

        pass

    def zoomSignal(self, mode, pos):
        '''
            this is ctrl+scroll function
            it implicitly calls the scaleChanged for scaleCB
            which adjusts the tscale and refreshes the chart
            
            and that is why we can not move horizontalScrollBar in scaleChanged 
        '''
    
        time = self.widget.posToTime(pos)
        
        xfix = None
    
        idx = self.scaleCB.currentIndex()
        
        if mode == 1 and idx < self.scaleCB.count() - 1:
            xfix = self.widget.mapToParent(QPoint(pos, 0)).x() - self.geometry().x()
            self.scaleCB.setCurrentIndex(idx + 1)

        if mode == -1 and idx > 0:
            self.scaleCB.setCurrentIndex(idx - 1)
            xfix = self.widget.mapToParent(QPoint(pos, 0)).x() - self.geometry().x()
            
        if xfix is not None:
            newPos = int(self.widget.timeToPos(time))
            #newPos -= self.size().width()/2 #--> to the window center
            
            newPos -= xfix # --> move to the mouse pos
            
            self.scrollarea.horizontalScrollBar().setValue(newPos)
            
        
    def updateFromTime(self, fromTime):
        self.fromEdit.setText(fromTime)
        self.fromEdit.setStyleSheet("color: blue;")
        self.fromEdit.setFocus()
        
    def updateToTime(self, fromTime):
        self.toEdit.setText(fromTime)
        self.toEdit.setStyleSheet("color: blue;")
        self.fromEdit.setFocus()
        
    def repaintRequest(self):
        self.widget.repaint()
    
    def setScale(self, host, kpi, yMin, yMax):
        '''
            scale changed to manual value
        '''
        log('setScale signal: %s -> %i-%i' % (kpi, yMin, yMax))
        
        kpiStylesNNN = self.hostKPIsStyles[host]
        
        group = kpiStylesNNN[kpi]['group']

        if  group == 0:
            if yMax == -1:
                if 'manual_scale' in kpiStylesNNN[kpi]:
                    kpiStylesNNN[kpi].pop('manual_scale')
            else:
                kpiStylesNNN[kpi]['manual_scale'] = (yMin, yMax)
        else:
            if yMax == -1:
                if group in self.widget.manual_scales:
                    self.widget.manual_scales.pop(group)
            else:
                self.widget.manual_scales[group]= (yMin, yMax)
            
        self.widget.alignScales()
        log('self.scalesUpdated.emit() #5', 5)
        self.scalesUpdated.emit()
        self.widget.update()
        
        
    def connectionLost(self, dp, err_str='', nodialog=False):
        '''
            very synchronous call, it holds controll until connection status resolved
        '''
        self.statusMessage('Connection error (%s)' % err_str, True)

        if nodialog:
            log('connection lost, but we cannot block UI thread, so silently exit', 2)
            return False

        msgBox = QMessageBox(self)
        msgBox.setWindowTitle('Charts connection lost')
        msgBox.setText('Connection failed, reconnect?')
        msgBox.setStandardButtons(QMessageBox.Yes| QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        iconPath = resourcePath('ico', 'favicon.png')
        msgBox.setWindowIcon(QIcon(iconPath))
        msgBox.setIcon(QMessageBox.Warning)

        reply = None
        
        while reply != QMessageBox.No and dp.connection is None:
            reply = msgBox.exec_()
            if reply == QMessageBox.Yes:
                try:
                    self.statusMessage('Reconnecting to %s:%s...' % (dp.server['host'], str(dp.server['port'])), True)
                    
                    assert dp is not None, 'Dataprovider cannot be None during reconnection. Failed.'
                    dp.reconnect()
                        
                    self.statusMessage('Connection restored', True)
                except Exception as e:
                    log('Reconnect failed: %s' % e)
                    self.statusMessage('Reconnect failed: %s' % str(e))

        if reply == QMessageBox.Yes:
            return True
        else:
            return False
    
    def setStatus(self, st, repaint = False):
        
        if self.indicator:
            self.indicator.status = st

            if st == 'autorefresh' and self.timer:
                self.indicator.nextAutorefresh = datetime.datetime.now() + datetime.timedelta(seconds=self.refreshTime)
            
            if repaint:
                self.indicator.repaint()
    
    def checkboxToggle(self, host, kpi):
        def substract(list1, list2):
            res = [item for item in list1 if item not in list2]
            return res
            
        def request_kpis(self, host_d, host, kpi, kpis):
            '''
                
            '''
            allOk = None
            
            # this is REALLY not clear why paintEvent triggered here in case of yesNoDialog
            # self.widget.paintLock = True
            

            if len(self.ndp) == 0:
                log('Seems not connected, as self.ndp is empty')
                self.statusMessage('Not connected to the DB', True)
                return False

            log(f'request_kpis, {host_d}')
            
            dpidx = host_d['dpi']
            dp = self.ndp[dpidx]
            
            if dp is None:
                self.statusMessage('Not connected to the DB', True)
                return False
            
            self.setStatus('sync')
            
            sm = 'Request %s:%s/%s...' % (host_d['host'], host_d['port'], kpi)
            
            if self.lastHostTime is not None and self.lastHostTime > 1:
                sm += ' (last one-host request took: %s)' % str(round(self.lastHostTime, 3))
            
            self.statusMessage(sm, True)

            timer = False
            
            if self.timer is not None:
                timer = True
                self.timer.stop()
                
            while allOk is None:
                try:
                    t0 = time.time()
                    
                    log('request kpis: need to check here if all the kpis actually exist...')
                    log(f'host: {host}')
                    log(f'kpis: {kpis}')
                    
                    kpiStylesNNN = self.hostKPIsStyles[host]

                    for k in self.widget.nkpis[host]:
                        log(f'kpi: {k}')
                        if k not in kpiStylesNNN:
                            log('[!] okay, %s does not exist anymore, so deleting it from the list...' % k)
                            self.widget.nkpis[host].remove(k)
                        else:
                            log('ok')

                    dp.getData(self.widget.hosts[host], fromto, kpis, self.widget.ndata[host], self.hostKPIsStyles[host], wnd=self)
                    self.widget.nkpis[host] = kpis
                    
                    allOk = True
                    
                    t1 = time.time()
                    self.lastHostTime = t1-t0
                    self.statusMessage('%s added, %s s' % (kpi, str(round(t1-t0, 3))), True)
                except utils.dbException as e:
                    reconnected = self.connectionLost(dp, str(e))
                    
                    if reconnected == False:
                        allOk = False
                        timer = False
                        
            # self.widget.paintLock = False
            
            if timer:
                self.timer.start(1000 * self.refreshTime)
                self.setStatus('autorefresh', True)
            else:
                self.setStatus('idle', True)

            return allOk
        
        log('checkboxToggle %i %s' % (host, kpi), 5)
        
        modifiers = QApplication.keyboardModifiers()

        host_d = self.widget.hosts[host]
        
        allOk = None
        
        if kpi in self.widget.nkpis[host]:
            # remove kpi
            if modifiers & Qt.ControlModifier:
                for hst in range(0, len(self.widget.hosts)):
                    
                    # okay this is a confusing one:
                    # on Control+click we by default only "unckick" the kpi for all the hosts, same port
                    # but if the Shift also pressed - we ignore port and unclick bloody everything
                    
                    if (host_d['port'] == '' and self.widget.hosts[hst]['port'] == '') or (host_d['port'] != '' and (modifiers & Qt.ShiftModifier or self.widget.hosts[hst]['port'] == host_d['port'])):
                        
                        if cfg('loglevel', 3) > 3:
                            log('unclick, %s, %s:' % (str(hst), kpi))
                            log('kpis before unclick: %s' % (self.widget.nkpis[hst]))

                        if self.widget.highlightedKpiHost == hst and self.widget.highlightedKpi == kpi:
                            log('clean up highlightinh #1 (massive)', 4)
                            self.widget.highlightedKpi = None
                            self.widget.highlightedKpiHost = None
                            self.widget.highlightedEntity = None

                        if kpi in self.widget.nkpis[hst]:
                            self.widget.nkpis[hst].remove(kpi)
                            log(f'delete {kpi} from nkpis list for {hst}', 4)

                            if kpi in self.widget.ndata[hst]: #might be empty for alt-added (2019-08-30)
                                log(f'delete {kpi} data from {hst}', 4)
                                del(self.widget.ndata[hst][kpi])

                        log('kpis after unclick: %s' % (self.widget.nkpis[hst]), 4)
                        log('data keys: %s' % str(self.widget.ndata[hst].keys()), 4)
                        
            else:       
                if cfg('loglevel', 3) > 3:
                    log('unclick, %s, %s:' % (str(host), kpi))
                    log('kpis before unclick: %s' % (self.widget.nkpis[host]))

                if self.widget.highlightedKpiHost == host and self.widget.highlightedKpi == kpi:
                    log('clean up highlightinh #2', 4)
                    self.widget.highlightedKpi = None
                    self.widget.highlightedKpiHost = None
                    self.widget.highlightedEntity = None

                self.widget.nkpis[host].remove(kpi) # kpis is a list
                if kpi in self.widget.ndata[host]: #might be empty for alt-added
                    del(self.widget.ndata[host][kpi]) # ndata is a dict
                    
                if cfg('loglevel', 3) > 3:
                    log('kpis after unclick: %s' % (self.widget.nkpis[host]))
                    log('data keys: %s' % str(self.widget.ndata[host].keys()))
            
            self.widget.update()
        else:
            # add kpi
            fromto = {'from': self.fromEdit.text(), 'to': self.toEdit.text()}
            
            if modifiers & Qt.ControlModifier:
                # okay this is a confusing one:
                # on Control+click we by default only add the kpi for all the hosts, _same port_
                # BUT if Shift also pressed - we ignore the port and add bloody everything
                kpis = {}
                if host_d['port'] == '':
                    
                    for hst in range(0, len(self.widget.hosts)):
                        kpis[hst] = self.widget.nkpis[hst].copy() #otherwise it might be empty --> key error later in get_data
                        
                        if self.widget.hosts[hst]['port'] == '' and kpi not in self.widget.nkpis[hst]:
                            #self.widget.nkpis[hst].append(kpi)
                            kpis[hst] = self.widget.nkpis[hst] + [kpi]
                else:
                    if cfg('loglevel', 3) > 3:
                        log('adding kpi: %s' % (kpi))
                        log('hosts: %s' % (str(self.widget.hosts)))
                    for hst in range(0, len(self.widget.hosts)):
                        kpis[hst] = self.widget.nkpis[hst].copy() #otherwise it might be empty --> key error later in get_data

                        if (modifiers & Qt.ShiftModifier or self.widget.hosts[hst]['port'] == host_d['port']) and kpi not in self.widget.nkpis[hst]:
                            #self.widget.nkpis[hst].append(kpi)
                            kpis[hst] = self.widget.nkpis[hst] + [kpi]
            else:
                #self.widget.nkpis[host].append(kpi)
                kpis = self.widget.nkpis[host] + [kpi]
                
            if modifiers == Qt.AltModifier:
                #pass
                self.widget.nkpis[host] = kpis
            else:
                if modifiers & Qt.ControlModifier:
                    #list of kpis formed above, here we actually request
                    self.statusMessage('Request all/%s...' % (kpi), True)
                    t0 = time.time()

                    self.setStatus('sync', True)
                    while allOk is None:
                        try:
                            t2 = t0 = time.time()
                            
                            for hst in range(0, len(self.widget.hosts)):
                                if (host_d['port'] == '' and self.widget.hosts[hst]['port'] == '') or (host_d['port'] != '' and self.widget.hosts[hst]['port'] != ''):  # doesnt look right 27.01.2021
                                    
                                    if len(kpis[hst]) > 0:
                                        dpidx = self.widget.hosts[hst]['dpi']
                                        dp = self.ndp[dpidx]
                                        
                                        t1 = time.time()
                                        dp.getData(self.widget.hosts[hst], fromto, kpis[hst], self.widget.ndata[hst], self.hostKPIsStyles[hst], wnd=self)
                                        self.widget.nkpis[hst] = kpis[hst]
                                        
                                        t2 = time.time()
                                        
                                        self.statusMessage('%s:%s %s added, %s s' % (self.widget.hosts[hst]['host'], self.widget.hosts[hst]['port'], kpi, str(round(t2-t1, 3))), True)
                                    
                            self.lastReloadTime = t2-t0
                            self.statusMessage('All hosts %s added, %s s' % (kpi, str(round(t2-t0, 3))))
                            allOk = True
                        except utils.dbException as e:
                            log('[!] getData: %s' % str(e))
                            self.setStatus('error')
                            reconnected = self.connectionLost(dp, str(e))
                            
                            if reconnected == False:
                                allOk = False
                                
                    if self.timer:
                        self.setStatus('autorefresh', True)
                    else:
                        self.setStatus('idle', True)

                else:
                    for hst in range(0, len(self.widget.hosts)):
                        if hst == host:
                            # normal click after alt-click (somewhere before)
                            allOk = request_kpis(self, host_d, host, kpi, kpis)
                        else: 
                            #check for kpis existing in host list but not existing in data:
                            diff = substract(self.widget.nkpis[hst], self.widget.ndata[hst].keys())

                            if len(diff) > 0:
                                host_d = self.widget.hosts[hst]
                                
                                #it actually gets all the kpis, can it request only missed ones?
                                allOk = request_kpis(self, host_d, hst, kpi, self.widget.nkpis[hst])
                                
                        if allOk == False:
                            break

                    # allOk = request_kpis(self, host_d, host, kpi, kpis)

                if allOk: 
                    self.renewMaxValues()
                    self.widget.alignScales()
                    
                    log('self.scalesUpdated.emit() #1', 5)
                    self.scalesUpdated.emit()
         
                self.widget.update()
                
        #log('checkboxToggle result self.widget.nkpis:')
        #log(self.widget.nkpis)
        
        self.kpiToggled.emit(host)
        

    def refreshTimer(self):
        self.timer.stop()
        #print('also stop keep-alive timer here ((it will be kinda refreshed in get_data renewKeepAlive))')
        
        log('trigger auto refresh...')
        self.reloadChart(autorefresh=True)
        
        if self.timer: # need to check as it might be disabled inside reloadChart()
            self.timer.start(1000 * self.refreshTime)
    
    def refreshChanged(self, i):

        txtValue = self.refreshCB.currentText()
        
        if self.timer is not None:
            self.refreshTime = 0
            self.timer.stop()
            self.timer = None
            # self.indicator.nextAutorefresh = None

        if txtValue == 'none':
            if self.suppressStatus is None:
                self.statusMessage('Autorefresh disabled.')

            self.setStatus('idle', True)
            log('Autorefresh disabled.')
            return
        
        scale = 0

        try:
            (n, unit) = txtValue.split()

            n = int(n)

            if unit[:6] == 'minute':
                scale = 60
            elif unit[:6] == 'second':
                scale = 1
        except Exception as ex:
            log('[e] timer scale exception: %s' % str(ex))
            
        if scale == 0:
            log('[e] wrong scale (%s)' % (txtValue))
            return

        self.refreshTime = n * scale
        
        if self.timer is None:
            log('Fire up autorefresh: %i' % (self.refreshTime))
            self.statusMessage('Autorefresh triggered: %i seconds' % (self.refreshTime))
            self.timer = QTimer(self.window())
            self.timer.timeout.connect(self.refreshTimer)
            self.timer.start(1000 * self.refreshTime)
            self.setStatus('autorefresh', True)
        
    def scaleChanged(self, i):
        '''
            processes the change of scaleCB
            both manually and by zoomSignal (ctrl+scroll)
            
            that's why we can not change horizontalScrollBar position here
            as it's changed in zoomSignal
        '''

        txtValue = self.scaleCB.currentText()
        
        try:
            (n, unit) = txtValue.split()
            
            n = int(n)
            
            scale = 0
            
            if unit[:6] == 'second':
                scale = 1
            elif unit[:6] == 'minute':
                scale = 60
            elif unit[:4] == 'hour':
                scale = 3600
                
        except Exception as ex:
            log('[e] timer scale exception: %s, %s' % (str(ex), txtValue))
            
        self.widget.t_scale = n * scale
        
        #recalculate x-size and adjust
        self.widget.timeScale = txtValue
        
        self.widget.resizeWidget()
        
        self.widget.update()
        
        
    #  - does not work, #635
    
    @profiler
    def renewMaxValues(self):
        '''
            scans max value and last value for kpi
            
            all hosts all kpis from self.ndata[*].keys() list (all enabled kpis)
            
            creates/fills self.scalesN[h] array
            defines max and last_value keys
            
            this one ignores groups/scales at all, just raw values
            
            2021-11-09 also scan for AVG
        '''
    
        log('renewMaxValues()', 5)
        
        t0 = time.time()
        t_from = self.widget.t_from.timestamp()
        t_to = self.widget.t_to.timestamp()
        
        for h in range(0, len(self.widget.hosts)):
        
            if len(self.widget.ndata[h]) == 0: 
                # not data at all, skip
                continue
                
            data = self.widget.ndata[h]
            scales = self.widget.nscales[h]
            
            scalesml = self.widget.nscalesml[h]
            
            kpiStylesNNN = self.hostKPIsStyles[h]

            # init zero dicts for scales
            # especially important for the first run

            scales.clear()
            scalesml.clear()

            for kpi in data.keys():
                scales[kpi] = {}
                
            log(f'data keys: {data.keys()}', 4)
            log(f'scales keys: {scales.keys()}', 4)
            #init zero max
            
            for kpi in data.keys():
                scales[kpi]['max'] = 0
                scales[kpi]['avg'] = None
                
            #scan for max

            for kpi in scales.keys():
            
                if kpi[:4] == 'time':
                    continue

                subtype = kpiStylesNNN[kpi].get('subtype')

                if kpi not in self.hostKPIsList[h]:
                    log('kpi was removed so no renewMaxValues (%s)' % (kpi), 4)
                    continue
                    
                if subtype == 'gantt':
                
                    eNum = 0
                    total = 0
                
                    for entity in data[kpi]:
                        total += len(data[kpi][entity])
                        eNum += 1
                        
                    scales[kpi]['entities'] = eNum
                    scales[kpi]['total'] = total

                    continue
                    
                timeKey = kpiDescriptions.getTimeKey(kpiStylesNNN, kpi)
                    
                # array_size = len(self.widget.ndata[h][timeKey]) # 2020-03-11

                if not timeKey in data:
                    continue

                array_size = len(data[timeKey])
                
                if array_size == 0:
                    continue
                
                log('h: %i (%s), array_size: %i, timekey = %s, kpi = %s' %(h, self.widget.hosts[h]['host'], array_size, timeKey, kpi), 4)
                
                scales[timeKey] = {'min': data[timeKey][0], 'max': data[timeKey][array_size-1]}

                if subtype == 'multiline':
                    pass
                    # need to scan all values, not one set
                    # print('multiline action here, %s' % (kpi))
                    # print('\ttime frames:', len(data[kpi][0]))
                    # print('\tgroupbys:', len(data[kpi]))
                    
                if subtype == 'multiline':
                    scans = len(data[kpi])
                else:
                    scans = 1
                
                for sn in range(scans):
                
                    max_val = 0
                    sum_val = 0
                
                    if subtype == 'multiline':
                        gb = data[kpi][sn][0]
                        scan = data[kpi][sn][1]
                    else:
                        scan = data[kpi] # yep, this simple
                        
                        
                    anti_crash_len = len(scan)
                    deb(f'anti crash scan, {kpi} -> {anti_crash_len}')
                
                    try:
                        for i in range(0, array_size):
                            t = data[timeKey][i]
                            
                            if i >= anti_crash_len:
                                log('[!] I am seriously considering crash here, my anti_crash_len=%i, array_size=%i, i = %i! host %i, kpi = %s, timeKey = %s' % (anti_crash_len, array_size, i, h, kpi, timeKey))
                                log('[!] host: %s' % (self.widget.hosts[h]))
                                
                                log('[!] len(kpi), len(time)', len(scan), len(data[timeKey]))
                                # continue - to have more details
                            
                            if t >= t_from:
                                if max_val < scan[i]:
                                    max_val = scan[i]

                            if  t > t_to: #end of window no need to scan further
                                break
                               
                            sum_val += scan[i]
                            
                        if i > 0:
                            avg_val = sum_val/(i+1)
                        else:
                            avg_val = None

                    except ValueError as e:
                        log('error: i = %i, array_size = %i' % (i, array_size))
                        log('timeKey = %s, kpi: = %s' % (timeKey, kpi))
                        log('scales[kpi][max] = %i' % (scales[kpi]['max']))
                        log('len(data[kpi]) = %i' % (len(scan)))
                        
                        log('scales[kpi] = %s' % str(scales[kpi]))

                        log('exception text: %s' % (str(e)))
                        
                        log('sum_val value = %s' % (str(sum_val)))
                        
                        for j in range(10):
                            log('data[%i] = %s' % (j, str(data[kpi][j])))
                            
                        for j in range(1, 10):
                            k = array_size - (10 - j) - 1
                            log('k = %i, kpi = %s, timeKey = %s' % (k, kpi, timeKey))
                            log('data[%s][%i] = %s' % (kpi, k, str(scan[k])))
                            log('data[%s][%i] = %s' % (timeKey, k, str(data[timeKey][k])))
                            
                        raise e
                        
                    if scales[kpi]['max'] < max_val:
                        scales[kpi]['max'] = max_val
                        
                    if i > 0:
                        scales[kpi]['last_value'] = scan[i]
                    else:
                        scales[kpi]['last_value'] = None
                    
                    if subtype == 'multiline':
                        if kpi not in scalesml:
                            scalesml[kpi] = {}

                        if gb not in scalesml[kpi]:
                            scalesml[kpi][gb] = {}

                        scalesml[kpi][gb]['last'] = scan[i]
                        scalesml[kpi][gb]['max'] = max_val

                        scales[kpi]['avg'] = None
                    else:
                        if avg_val is not None:
                            scales[kpi]['avg'] = int(avg_val)
                        else:
                            scales[kpi]['avg'] = None
                    
        t1 = time.time()
        
        self.widget.alignScales()
        
        log('self.scalesUpdated.emit() #2', 5)
        self.scalesUpdated.emit()

    def understandTimes(self):
        #time.sleep(2)
        fromTime = self.fromEdit.text().strip()
        toTime = self.toEdit.text().strip()

        #backup for ESC
        self.fromTime = fromTime
        self.toTime = toTime
        
        if fromTime[:1] == '-' and toTime == '':
            try:
                hours = int(fromTime[1:])
                
                log('timeZoneDelta: %i' % self.widget.timeZoneDelta, 4)
                starttime = datetime.datetime.now() - datetime.timedelta(seconds= hours*3600 - self.widget.timeZoneDelta)
                starttime -= datetime.timedelta(seconds= starttime.timestamp() % 3600)

                self.widget.t_from = starttime
                self.fromEdit.setStyleSheet("color: black;")
            except:
                self.fromEdit.setStyleSheet("color: red;")
                self.statusMessage('datetime syntax error')
                return False
        else:
            try:
                if len(fromTime) >= 10:
                    lt = 19 - len(fromTime)
                    fromTime += ' 00:00:00'[9 - lt:]
                    self.fromEdit.setText(fromTime)

                tfrom = datetime.datetime.strptime(fromTime, '%Y-%m-%d %H:%M:%S')

                self.widget.t_from = tfrom
                    
                self.fromEdit.setStyleSheet("color: black;")
                
                if self.fromEdit.hasFocus() or self.toEdit.hasFocus():
                    self.setFocus()
            except:
                self.fromEdit.setStyleSheet("color: red;")
                self.statusMessage('datetime syntax error')
                return False
            
        if toTime == '':
            self.widget.t_to = datetime.datetime.now() + datetime.timedelta(seconds= self.widget.timeZoneDelta)
        else:
            try:
                if len(toTime) == 10:
                    self.widget.t_to = datetime.datetime.strptime(toTime, '%Y-%m-%d')

                    toTime += ' 23:59:59'
                    self.toEdit.setText(toTime)

                elif len(toTime) > 11 and len(toTime) <19:
                    lt = 19 - len(toTime)
                    toTime += ' 00:00:00'[9 - lt:]
                    self.toEdit.setText(toTime)

                self.widget.t_to = datetime.datetime.strptime(toTime, '%Y-%m-%d %H:%M:%S')
                    
                self.toEdit.setStyleSheet("color: black;")
            except:
                self.statusMessage('datetime syntax error')
                return False
                
        if utils.cfg_servertz:
            log(f'tzinfo update: {self.widget.tzInfo}', component='tz')
            self.widget.t_from = self.widget.t_from.replace(tzinfo=self.widget.tzInfo)
            self.widget.t_to = self.widget.t_to.replace(tzinfo=self.widget.tzInfo)

        return True

                
    def reloadChart(self, autorefresh=False):
    
        dp = None
        
        if self.understandTimes() == False:
            return

        # self.widget.checkDayLightSaving()

        if not self.ndp:
            self.statusMessage('Not connected to the DB', True)
            return

        if self.lastReloadTime is not None and self.lastReloadTime > 1:
            sm = 'Reload... (last reload request took: %s)' % str(round(self.lastReloadTime, 3))
        else:
            sm = 'Reload...'
            
        self.statusMessage(sm, True)
        self.repaint()
        
        timerF = None
        
        if self.timer is not None:
            timerF = True
            self.timer.stop()
        
        t0 = time.time()
        log('  reloadChart()', 5)
        log('  hosts: %s' % str(self.widget.hosts), 5)
                        
        fromto = {'from': self.fromEdit.text(), 'to': self.toEdit.text()}
        
        allOk = None
        
        self.setStatus('sync', True)
        
        self.reloadLock = True
        
        actualRequest = False
                
        while allOk is None:
            try:
                for host in range(0, len(self.widget.hosts)):
                    if len(self.widget.nkpis[host]) > 0:

                        log('--->> need to check here if all the kpis actually exist...')
                        
                        kpiStylesNNN = self.hostKPIsStyles[host]
                        
                        log(f'nkpis for host {host}: {self.widget.nkpis[host]}')
                        for k in self.widget.nkpis[host]:
                            log(f'kpi: {k}')
                            if k not in kpiStylesNNN:
                                log('[!] okay, %s does not exist anymore, so deleting it from the list...' % k)
                                self.widget.nkpis[host].remove(k)
                            else:
                                log('ok')
                                
                        log(f'{host=}')
                        log(f'{self.widget.hosts[host]}')
                        dpidx = self.widget.hosts[host]['dpi']
                        dp = self.ndp[dpidx]
                        
                        dp.getData(self.widget.hosts[host], fromto, self.widget.nkpis[host], self.widget.ndata[host], self.hostKPIsStyles[host], wnd=self)
                        actualRequest = True
                allOk = True

            except utils.dbException as e:
                self.setStatus('error', True)

                # modal dialog only possible if autorefresh consoles do not need reconnect themselves
                if autorefresh and cfg('reconnectTimer'):
                    reconnected = self.connectionLost(dp, str(e), nodialog=True)
                else:
                    reconnected = self.connectionLost(dp, str(e), nodialog=False)

                if reconnected == False:
                    log('reconnected == False')
                    allOk = False
                    timerF = False
                    self.refreshCB.setCurrentIndex(0) # will disable the timer on this change
                    self.setStatus('disconnected', True)
                    self.statusMessage(f'Chart Disconnected: {e}...')

        self.renewMaxValues()
        
        self.widget.resizeWidget()
        
        self.widget.update()

        toTime = self.toEdit.text().strip()
        #autoscroll to the right
        if toTime == '': # probably we want to see the most recent data...
            self.scrollarea.horizontalScrollBar().setValue(self.widget.width() - self.width() + 22) # this includes scrollArea margins etc, so hardcoded...
            
            #+ scrollRangeChanged logic as a little different mechanism works
        
        t1 = time.time()
        self.lastReloadTime = t1-t0
        
        if actualRequest:
            self.statusMessage('Reload finish, %s s' % (str(round(t1-t0, 3))))
            
            arThreshold = cfg('autorefreshThreshold', 0)
            
            if timerF and arThreshold > 0 and (t1-t0) > arThreshold:

                log('Stopping autorefresh as last refresh took too long: %s > autorefreshThreshold = %i' % (str(round(t1-t0, 3)), arThreshold), 2)
                self.statusMessage('Stopping autorefresh as last refresh took too long %s > autorefreshThreshold = %i' % (str(round(t1-t0, 3)), arThreshold))
                
                self.suppressStatus = True
                self.refreshCB.setCurrentIndex(0)
                self.suppressStatus = None

                timerF = False
                
        else:
            if allOk:
                self.statusMessage('Ready')
        
        if timerF == True and self.timer is not None:
            self.timer.start(1000 * self.refreshTime)
            self.setStatus('autorefresh', True)
        else:
            if allOk:
                self.setStatus('idle', True)

        self.reloadLock = False

    def scrollRangeChanged (self, min, max):
    
        ''' 
            called after tab change and on scroll area resize 
            
            "autoscroll to the right" - also still required
        '''
        toTime = self.toEdit.text()
        
        if self.widgetWidth == self.widget.width():
            # no widget change, return
            return
        else:
            self.widgetWidth = self.widget.width()
        
        
        if toTime == '' and not self.widget.zoomLock:
            self.scrollarea.horizontalScrollBar().setValue(max)
        
    def adjustScale(self, scale = 1):
        font = self.fromEdit.font()
        fm = QFontMetrics(font)
        fromtoWidth = int(scale * fm.width(' 2019-06-17 22:59:00 ')) #have no idea why spaces required...

        self.fromEdit.setFixedWidth(fromtoWidth);
        self.toEdit.setFixedWidth(fromtoWidth);
        
    def fromEditKeyPress(self, event):
        if event.key() == Qt.Key_Escape:
            self.fromEdit.setText(self.fromTime)
            self.fromEdit.setStyleSheet("color: black;")
        else:            
            QLineEdit.keyPressEvent(self.fromEdit, event)

    def toEditKeyPress(self, event):
        if event.key() == Qt.Key_Escape:
            self.toEdit.setText(self.toTime)
            self.toEdit.setStyleSheet("color: black;")
        else:            
            QLineEdit.keyPressEvent(self.toEdit, event)


    def alignTZ(self):
        '''Okay, there are two things
        1. TZ delta
        2. TZ shift

        TZ delta is only to adjust things on the screen, it does not affect actual TS
        TZ shift is _added_ to the TSs coming from the DP, like trace

        if the only DP has TZ shift, it also makes sence to inherit it to TZ delta
        '''

        mintz = None
        for i in range(len(self.ndp)):
            prop = self.ndp[i].dbProperties
            tzdelta = prop.get('timeZoneDelta', 0)
            if mintz is None:
                mintz = tzdelta
            else:
                if mintz > tzdelta:
                    mintz = tzdelta

        self.widget.timeZoneDelta = mintz

    def adjustTimeZones(self, dpidx):
        log(f'Got TZ change request: {dpidx}', 4)
        dp = self.ndp[dpidx]

        if hasattr(dp, 'dbProperties'):
            log(dp.dbProperties, 4)

        tzd = tzDialog(self, self.ndp)
        res = tzd.exec_()

        if res:
            self.alignTZ()



    def __init__(self):
        
        '''
            create top controls like from... to... reload, etc
            
            all this crap to be moved some place else one day...
        '''
        
        self.indicator = None
        
        super().__init__()

        '''
        the block commented out 2022-11-23
        
        mode = cfg('mode')
        
        if mode:
            if mode == 'db':
                log('init db connection...')
                self.dp = dpDB.dataProvider(cfg('server')) # db data provider
                
                log('connected')
                self.connected.emit(cfg('server')['user'] + '@' + self.dp.dbProperties['sid'])
            elif mode == 'trace':
                files = ['trc/vhtl2hapdb01_nameserver_history.trc']
                self.dp = dpTrace.dataProvider(files) # trace data provider
            else:
                self.dp = dpDummy.dataProvider() # generated data
        '''
        
        grp = QGroupBox()
        hbar = QHBoxLayout();
        
        self.scaleCB = QComboBox()
        
        self.scaleCB.addItem('1 second')
            
        self.scaleCB.addItem('10 seconds')
        self.scaleCB.addItem('1 minute')
        self.scaleCB.addItem('5 minutes')
        self.scaleCB.addItem('10 minutes')
        self.scaleCB.addItem('15 minutes')
        self.scaleCB.addItem('30 minutes')
        self.scaleCB.addItem('1 hour')
        self.scaleCB.addItem('4 hours')

        if cfg('experimental'):
            self.scaleCB.addItem('8 hours')
            self.scaleCB.addItem('12 hours')

        self.scaleCB.setFocusPolicy(Qt.ClickFocus)
        

        self.scaleCB.setCurrentIndex(4)

        self.scaleCB.currentIndexChanged.connect(self.scaleChanged)

        self.refreshCB = QComboBox()
        
        self.refreshCB.addItem('none')
        
        if cfg('experimental'):
            self.refreshCB.addItem('10 seconds')
        
        self.refreshCB.addItem('30 seconds')
            
        self.refreshCB.addItem('1 minute')
        self.refreshCB.addItem('5 minutes')
        self.refreshCB.addItem('10 minutes')
        self.refreshCB.addItem('15 minutes')
        self.refreshCB.addItem('30 minutes')
        
        self.refreshCB.setFocusPolicy(Qt.ClickFocus)
        
        self.refreshCB.currentIndexChanged.connect(self.refreshChanged)

        fromLabel = QLabel('from:')
        toLabel = QLabel('to:')

        starttime = datetime.datetime.now() - datetime.timedelta(seconds= 12*3600)
        starttime -= datetime.timedelta(seconds= starttime.timestamp() % 3600)
                
        self.fromEdit = QLineEdit(starttime.strftime('%Y-%m-%d %H:%M:%S'))
        self.toEdit = QLineEdit()

        if cfg('dev?') and False:
            self.fromEdit.setText('2023-10-29 20:00:00')
            self.toEdit.setText('2023-10-30 12:00:00')

        # set from/to editboxes width
        self.adjustScale()

        reloadBtn = QPushButton("rld")
        reloadBtn.setFixedWidth(32);
        reloadBtn.clicked.connect(self.reloadChart)
        
        self.fromEdit.returnPressed.connect(self.reloadChart)
        self.fromEdit.keyPressEvent = self.fromEditKeyPress
        self.toEdit.returnPressed.connect(self.reloadChart)
        self.toEdit.keyPressEvent = self.toEditKeyPress
        
        hbar.addWidget(self.scaleCB)
        hbar.addStretch(10)
        
        hbar.addWidget(QLabel('autorefresh: '))
        hbar.addWidget(self.refreshCB)
        hbar.addStretch(1)
        
        hbar.addWidget(fromLabel)
        hbar.addWidget(self.fromEdit)
        hbar.addWidget(toLabel)
        hbar.addWidget(self.toEdit)
        
        hbar.addWidget(reloadBtn)
        
        # optionally if we prefer to use group one day
        # grp.setLayout(hbar)
        lo = QVBoxLayout(self)
        
        # lo.addWidget(grp) ... if we prefer to use group one day
        
        
        '''
            Create main chart area
        '''
        self.scrollarea = QScrollArea()
        
        self.widgetWidth = 1024 # last widget width to controll autoscroll

        self.scrollarea.setWidgetResizable(False)
        
        self.scrollarea.keyPressEvent = self.keyPressEventZ # -- is it legal?!
        
        self.scrollarea.horizontalScrollBar().rangeChanged.connect(self.scrollRangeChanged)
        
        lo.addLayout(hbar)
        lo.addWidget(self.scrollarea)
        
        self.widget = myWidget()

        # self.widget.ndp = self.ndp
        
        self.widget._parent = self
        self.widget.hostKPIsStyles = self.hostKPIsStyles        # need to link as used widely in drawChart called from paint event

        try:
            if cfg('color-bg'):
                p = self.scrollarea.palette()
                bgcolor = QColor(cfg('color-bg'))
                p.setColor(self.scrollarea.backgroundRole(), bgcolor)
                self.scrollarea.setPalette(p)
                
                rgb = bgcolor.getRgb()
                
                if rgb[0] + rgb[1] + rgb[2] >= 250*3: #smthng close to white
                    self.widget.gridColor = QColor('#EEE')
                    self.widget.gridColorMj = QColor('#CCC')
                
        except:
            log('[E] wrong color-bg value')

        #log(type(self.dp))
        #log(type(self.dp).__name__)
        
        if hasattr(self.dp, 'dbProperties'):
            assert False, 'should not reach here: timeZoneDelta'
            self.widget.timeZoneDelta = self.dp.dbProperties['timeZoneDelta']
        
        # register widget --> chartArea signals
        self.widget.updateFromTime.connect(self.updateFromTime)
        self.widget.updateToTime.connect(self.updateToTime)
        self.widget.zoomSignal.connect(self.zoomSignal)
        
        self.widget.scrollSignal.connect(self.scrollSignal)
        
        # trigger upddate of scales in table?
        
        # dummy size calculation
        # those values to be moved somewhere
        # with the init as well
        
        #self.widget.t_scale = 60*60

        self.reloadChart()
        self.widget.resizeWidget()
        
        self.widget.timeScale = self.scaleCB.currentText()
        
        self.scrollarea.setWidget(self.widget)
        
        self.scrollarea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn);
        self.scrollarea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);
        
    def calcHeight(self):
    
        '''
            function calculates the height of chart area
            based on current scrollarea height AND scrollbar width
            
            but... scrollbar.height() returns 30 until it appears on screen
            so 17 hardcoded
        '''
        
        sbHeight = self.scrollarea.horizontalScrollBar().height()
        sbHeight = 17
        
        
        return self.scrollarea.height() - sbHeight - 2
        
    def resizeEvent(self, event):
        '''
            this to update chart widget width as it's built in
            the scrollarea and resize is locked
        '''
        #log('%i x %i  -> %i x %i (%i)' % (self.width(), self.height(), self.scrollarea.width(), self.scrollarea.height(), self.scrollarea.horizontalScrollBar().height()))
        self.widget.resize(self.widget.width(), self.calcHeight())
        super().resizeEvent(event)
        
    def paintEventz(self, QPaintEvent):
        qp = QPainter()
        
        size = self.size()
        super().paintEvent(QPaintEvent)
        
        qp.begin(self)
            
        qp.setPen(Qt.blue)

        qp.drawLine(0, 0, size.width(), size.height())
        qp.drawLine(size.width(), 0, 0,  size.height())
        
        qp.end()
        
    def cleanDPs(self):
        log('Clean up DPs and destroy DBIs...')
        doneSomething = False

        numDPs = len(self.ndp)

        # close and destroy all the DPs...
        
        log(f'DPs list before cleanup: {self.ndp}', 5)
        for dp in self.ndp:
            log(f'    {type(dp)} {dp}', 5)
        
        while self.ndp:
            dp = self.ndp.pop()
            if dp is not None:
                dp.close()

                # have no idea if this has any sense at all! 2022-11-23 (was here since s2j)
                if hasattr(dp, 'dbi') and dp.dbi is not None:
                    log('dbi.dbinterface.destroy() call', 5)
                    dp.dbi.destroy()
                
                del dp
                doneSomething = True
                
        if self.ndp:
            log(f'[W] DPs list before cleanup: {self.ndp}', 2)
            for dp in self.ndp:
                log(f'[W]    {type(dp)} {dp}', 2)
        else:
            log('DPs cleanup done', 5)
            
        if doneSomething:
            self.refreshCB.setCurrentIndex(0) # will disable the timer on this change
