from PyQt5.QtWidgets import QWidget, QFrame, QScrollArea, QVBoxLayout, QHBoxLayout, QPushButton, QFormLayout, QGroupBox, QLineEdit, QComboBox, QLabel, QMenu
from PyQt5.QtWidgets import QApplication, QMessageBox, QToolTip

from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPolygon, QIcon, QFont, QFontMetrics, QClipboard, QPixmap, QRegion

from PyQt5.QtCore import QTimer, QRect, QSize

import os
import time
import datetime
import math
import random

from array import array

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QPoint, QEvent

from PyQt5.QtCore import pyqtSignal

# my stuff
import kpiDescriptions
from kpiDescriptions import kpiStylesNN, hType
from utils import resourcePath

import importTrace
import utils

from utils import log, cfg

import dpDummy
import dpTrace
import dpDB

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

    kpis = [] #list of kpis to be drawn << old one
    nkpis = [] #list of kpis to be drawn per host < new one

    kpiPen = {} #kpi pen objects dictionary
    
    highlightedEntity = None # gantt kpi currently highlihed
    highlightedRange = None # gantt kpi currently highlihed
    
    highlightedKpi = None #kpi currently highlihed
    highlightedKpiHost = None # host for currently highlihed kpi
    
    highlightedPoint = None #point currently highlihed (currently just one)
    
    #data = {} # dictionary of data sets + time line (all same length)
    #scales = {} # min and max values
    
    ndata = [] # list of dicts of data sets + time line (all same length)
    nscales = [] # min and max values, list of dicts (per host)
    
    manual_scales = {} # if/when scale manually adjusted, per group! like 'mem', 'threads'

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
    
    delta = 0 # offset for uneven time_from values
    
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
        
    def __init__(self):
        super().__init__()
        
        if cfg('fontSize') is not None:
            self.conf_fontSize = cfg('fontSize')
            
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
        
    def calculateMargins(self, scale = 1):
    
        myFont = QFont ('SansSerif', self.conf_fontSize)
        fm = QFontMetrics(myFont)
        
        self.font_height = scale * fm.height() - 2 # too much space otherwise
        
        self.bottom_margin = self.font_height*2 + 2 + 2
        
        log('font_height: %i' %(self.font_height))
        log('bottom_margin: %i' %(self.bottom_margin))
        
        self.font_width1 = scale * fm.width('12:00') / 2
        self.font_width2 = scale * fm.width('12:00:00') / 2
        self.font_width3 = scale * fm.width('2019-06-17') / 2
        
                
    def initPens(self):
    
        if utils.cfg('raduga'):
            kpiDescriptions.generateRaduga(utils.cfg('raduga'))
    
        for t in kpiStylesNN:
            self.kpiPen[t] = {}
            for kpi in kpiStylesNN[t]:
                self.kpiPen[t][kpi] = kpiStylesNN[t][kpi]['pen']

    def ceiling(self, num):
    
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
    
        for h in range(0, len(self.hosts)):
            type = hType(h, self.hosts)
            
            # for the issue https://github.com/rybafish/rybafish/issues/30
            # log('self.nscales[h].keys(): ' + str(self.nscales[h].keys()))
            
            for kpi in self.nscales[h].keys():

                if kpi[:4] == 'time':
                    continue

                if kpiStylesNN[type][kpi]['group'] == grp:
                    if max_value < self.nscales[h][kpi]['max']:
                        max_value = self.nscales[h][kpi]['max']
        
        #return self.ceiling(max_value)
        #return self.ceiling(kpiDescriptions(kpiStylesNN[type][kpi], max_value))
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
        
        groups = kpiDescriptions.groups()
        
        for g in groups:
            if g != '0':
                groupMax[g] = self.getGroupMax(g)

        for h in range(0, len(self.hosts)):
        
            # for kpi in self.nkpis[h]:
            for kpi in self.nscales[h].keys():
            
                if kpi[:4] == 'time':
                    continue
                    
                #self.nscales[h][kpi] = {}
                
                type = hType(h, self.hosts)
                
                scaleKpi = self.nscales[h][kpi] # short cut

                if kpiDescriptions.getSubtype(type, kpi) == 'gantt':
                
                    #scaleKpi['y_max'] = ''
                    scaleKpi['y_max'] = ''
                    scaleKpi['max_label'] = '%i' % (self.nscales[h][kpi]['total'])
                    scaleKpi['last_label'] = ''
                    scaleKpi['label'] = '%i' % (self.nscales[h][kpi]['entities'])
                    scaleKpi['yScale'] = ''
                    scaleKpi['unit'] = ''
                    continue
                
                #log(scaleKpi)
                    
                '''
                    max and last values calculated before by renewMaxValues
                '''
                scaleKpi['y_min'] = 0 # we always start at 0...
                scaleKpi['y_max'] = None
                
                #memory group
                #if kpiDescriptions.kpiGroup[kpi] == 'mem':
                
                groupName = kpiStylesNN[type][kpi]['group']
                
                if groupName == 'cpu':
                    scaleKpi['y_max'] = 100
                    scaleKpi['max_label'] = str(scaleKpi['max'])
                    
                    if 'last_value' in scaleKpi:
                        scaleKpi['last_label'] = str(scaleKpi['last_value']) 
                    else: 
                        scaleKpi['last_label'] = '?'
                        
                    scaleKpi['label'] = '10 / 100'
                    scaleKpi['yScale'] = 100
                    scaleKpi['unit'] = '%'
                        
                else:
                    # all the rest:
                    # 0 group means no groupping at all, individual scales
                    # != 0 means some type of group (not mem and not cpu)
                    
                    if groupName == 0:
                        if 'manual_scale' in kpiStylesNN[type][kpi]:
                            max_value = kpiStylesNN[type][kpi]['manual_scale']
                            yScale = max_value_n = max_value
                        else:
                            max_value = self.nscales[h][kpi]['max']
                            #max_value = self.ceiling(max_value)
                            max_value_n = kpiDescriptions.normalize(kpiStylesNN[type][kpi], max_value)
                            yScale = self.ceiling(int(round(max_value_n)))
                    else: 
                        if groupName in self.manual_scales:
                            #print('manual scale')
                            #print(kpiStylesNN[type][kpi]['sUnit'], '-->', kpiStylesNN[type][kpi]['dUnit'])
                            max_value = self.manual_scales[groupName] 
                            #yScale = max_value_n = max_value # 2021-07-15, #429
                            yScale = max_value                # 2021-07-15, #429
                            max_value_n = kpiDescriptions.normalize(kpiStylesNN[type][kpi], max_value) #429
                        else:
                            max_value = groupMax[groupName]
                            max_value_n = kpiDescriptions.normalize(kpiStylesNN[type][kpi], max_value)
                            
                            if max_value_n <= 10 and max_value != max_value_n:
                                kpiStylesNN[type][kpi]['decimal'] = 2
                            elif max_value_n <= 100 and max_value != max_value_n:
                                kpiStylesNN[type][kpi]['decimal'] = 1

                            yScale = self.ceiling(int(max_value_n))
                    
                    '''
                        max_value_n, yScale must be defined by this line
                        even when no any difference with max_value
                    '''
                    
                    d = kpiStylesNN[type][kpi].get('decimal', 0) # defined couple lines above
                    
                    scaleKpi['max_label'] = utils.numberToStr(kpiDescriptions.normalize(kpiStylesNN[type][kpi], scaleKpi['max'], d), d)
                    if 'last_value' in scaleKpi and scaleKpi['last_value'] is not None:
                        scaleKpi['last_label'] = utils.numberToStr(kpiDescriptions.normalize(kpiStylesNN[type][kpi], scaleKpi['last_value'], d), d)
                    else:
                        scaleKpi['last_label'] = '-1'
                        
                    # scaleKpi['y_max'] = max_value
                    scaleKpi['y_max'] = kpiDescriptions.denormalize(kpiStylesNN[type][kpi], yScale)
                    
                    dUnit = kpiStylesNN[type][kpi]['sUnit'] # not converted

                    if max_value_n == max_value:
                        dUnit = kpiStylesNN[type][kpi]['sUnit'] # not converted
                    else:
                        max_value_n = self.ceiling(max_value_n) # normally it's already aligned inside getMaxSmth
                        dUnit = kpiStylesNN[type][kpi]['dUnit'] # converted
                    
                    #scaleKpi['label'] = ('%s / %s' % (utils.numberToStr(max_value_n / 10), utils.numberToStr(max_value_n)))
                    scaleKpi['yScale'] = yScale
                    scaleKpi['label'] = ('%s / %s' % (utils.numberToStr(yScale / 10), utils.numberToStr(yScale)))
                    
                    if 'perSample' in kpiStylesNN[type][kpi]:
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

        startHere = cmenu.addAction("Make this a FROM time")
        stopHere = cmenu.addAction("Make this a TO time")
        
        copyTS = cmenu.addAction("Copy this timestamp")

        cmenu.addSeparator()
        copyVAPNG = cmenu.addAction("Copy screen")
        saveVAPNG = cmenu.addAction("Save screen")
        copyPNG = cmenu.addAction("Copy chart area")
        savePNG = cmenu.addAction("Save chart area")

        copyLegend = None
        
        if self.legend:
            cmenu.addSeparator()
            copyLegend = cmenu.addAction("Copy Legend to clipboard")
            putLegend = cmenu.addAction("Remove Legend")

        else:
            cmenu.addSeparator()
            putLegend = cmenu.addAction("Add Legend")
        
        if self.gotGantt:
            cmenu.addSeparator()
            
            if self.hideGanttLabels:
                toggleGanttLabels = cmenu.addAction("Show Gantt Labels")
            else:
                toggleGanttLabels = cmenu.addAction("Hide Gantt Labels")
        
        if self.highlightedEntity is not None:
            copyGanttEntity = cmenu.addAction("Copy highlighted gantt entity")
            copyGanttDetails = cmenu.addAction("Copy highlighted gantt details")
            

        if cfg('developmentMode'):
            cmenu.addSeparator()
            fakeDisconnection = cmenu.addAction("fake disconnection")
        
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
            if not os.path.isdir('screens'):
                os.mkdir('screens')
                
            fn = 'screen_'+datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')+'.png'
            fn = os.path.join('screens', fn)
            
            log('Saving PNG image (%s)' % fn)
            
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
            #self.legend = not self.legend
            
            if self.legend is None:
                self.legend = 'hosts'
            else:
                self.legend = None
            
            self.repaint()
        
        if action == saveVAPNG:
            if not os.path.isdir('screens'):
                os.mkdir('screens')
                
            fn = 'screen_'+datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')+'.png'
            fn = os.path.join('screens', fn)
            
            log('Saving PNG image (%s)' % fn)
            
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
            even_offset = 0 # time.timestamp() % self.t_scale
            #time = time - datetime.timedelta(seconds= even_offset - self.t_scale - self.delta)
            time = time - datetime.timedelta(seconds= even_offset)
            
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            
            clipboard = QApplication.clipboard()
            clipboard.setText(ts)
            
        if self.highlightedEntity and action == copyGanttDetails:
        
            entity = self.highlightedEntity
            kpi = self.highlightedKpi
            host = self.highlightedKpiHost
            range_i = self.highlightedRange

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

        if not found:
            if (self.highlightedKpi):
            
                hlType = hType(self.highlightedKpiHost, self.hosts)
            
                self.kpiPen[hlType][self.highlightedKpi].setWidth(1)
                
                self.highlightedKpiHost = None
                self.highlightedKpi = None

                self.highlightedEntity = None
                self.highlightedRange = None

                self.setToolTip('')
                
                # self.update()
                
            self.statusMessage('No values around...')
            self.update() # - update on any click
            
        return
        
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
        
        type = hType(host, self.hosts)
        
        top_margin = self.top_margin + self.y_delta
        
        reportDelta = False
        
        found_some = False
        
        for kpi in kpis:
        
            if kpi[:4] == 'time':
                continue
                
            if kpiDescriptions.getSubtype(type, kpi) == 'gantt':
            
                height = kpiStylesNN[type][kpi]['width']
                ganttShift = kpiStylesNN[type][kpi]['shift']
            
                if kpi not in data: # alt+clicked, but not refreshed yet
                    continue
                    
                gc = data[kpi]
                
                if len(gc) == 0:
                    continue
                    
                i = 0
                
                yr = kpiStylesNN[type][kpi]['y_range']

                for entity in gc:
                
                    #exactly same calculation as in drawChart:
                    y_scale = (wsize.height() - top_margin - self.bottom_margin - 2 - 1) / len(gc)
                    y_shift = y_scale/100*yr[0] * len(gc)
                    y_scale = y_scale * (yr[1] - yr[0])/100
                    
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
                        
                        self.highlightedKpi = kpi
                        self.highlightedKpiHost = host
                        self.highlightedEntity = entity
                        self.highlightedRange = reportRange

            
                        # self.statusMessage('%s, %s.%s, %s: %s' % (hst, type, kpi, entity, desc))
    
                        t0 = t[0].time().isoformat(timespec='milliseconds')
                        t1 = t[1].time().isoformat(timespec='milliseconds')

                        '''
                        t0 = t[0].isoformat(sep=' ', timespec='milliseconds')
                        t1 = t[1].isoformat(sep=' ', timespec='milliseconds')
                        '''

                        '''
                        t0 = t[0].strftime('%H:%M:%S.%f')[:-3]
                        t1 = t[1].strftime('%H:%M:%S.%f')[:-3]                        
                        '''

                        interval = '[%s - %s]' % (t0, t1)
                        
                        det = '%s, %s.%s, %s: %s/%i %s' % (hst, type, kpi, entity, interval, t[3], t[2])
                        
                        self.statusMessage(det)
                        log('gantt clicked %s' % (det))

                        self.update()
                        return True
                        
                    i += 1
             
                continue # no regular kpi scan procedure requred
                
            '''
                regular kpis scan
            '''
        
            timeKey = kpiDescriptions.getTimeKey(type, kpi)
            
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
                #kpi not found but we still need to check others! 2021-07-15, #386
                continue

            j = i
                
            y_min = data[kpi][i]
            y_max = data[kpi][i]

            while i < array_size and timeline[i] <= trgt_time + time_delta:
                # note: for really zoomed in time scales there's a possibility
                # that this loop will not be execuded even once
                
                if timeline[j] < trgt_time:
                    j+=1 # scan for exact value in closest point

                if y_min > data[kpi][i]:
                    y_min = data[kpi][i]

                if y_max < data[kpi][i]:
                    y_max = data[kpi][i]

                i+=1
                
            j -= 1 # THIS is the point right before the trgt_time
            
            found_some = False

            if (scales[kpi]['y_max'] - scales[kpi]['y_min']) == 0:
                log('delta = %i, skip %s' % (scales[kpi]['y_max'] - scales[kpi]['y_min'], str(kpi)))
                break
                
            y_scale = (wsize.height() - top_margin - self.bottom_margin - 2 - 1)/(scales[kpi]['y_max'] - scales[kpi]['y_min'])

            ymin = y_min
            ymin = scales[kpi]['y_min'] + ymin*y_scale
            ymin = round(wsize.height() - self.bottom_margin - ymin) - 2

            ymax = y_max
            ymax = scales[kpi]['y_min'] + ymax*y_scale
            ymax = round(wsize.height() - self.bottom_margin - ymax) - 2
            
            #log('%s = %i' % (kpi, self.data[kpi][i]))
            #log('on screen y = %i, from click: %i' % (y, pos.y()))
            #log('on screen %i/%i, from click: %i' % (ymin, ymax, pos.y()))
            
            #if abs(y - pos.y()) <= 2:
            if pos.y() <= ymin + tolerance and pos.y() >= ymax - tolerance: #it's reversed in Y calculation...
                if (self.highlightedKpi):
                
                    if self.highlightedKpi == kpi and self.highlightedKpiHost == host:
                        reportDelta = True
                        
                    self.highlightedKpi = None

                d = kpiStylesNN[type][kpi].get('decimal', 0)
                normVal = kpiDescriptions.normalize(kpiStylesNN[type][kpi], data[kpi][j], d)

                scaled_value = utils.numberToStr(normVal, d)
                
                log('click on %s(%i).%s = %i, %s' % (self.hosts[host]['host'], host, kpi, data[kpi][j], scaled_value))
                self.kpiPen[type][kpi].setWidth(2)
                    
                self.highlightedKpi = kpi
                self.highlightedKpiHost = host
                self.highlightedPoint = j
                
                if reportDelta:
                    deltaVal = normVal - self.highlightedNormVal
                    deltaVal = ', delta: ' + utils.numberToStr(abs(deltaVal), d)
                else:
                    deltaVal = ''

                self.highlightedNormVal = normVal
                    
                tm = datetime.datetime.fromtimestamp(data[timeKey][j]).strftime('%Y-%m-%d %H:%M:%S')
                
                self.statusMessage('%s, %s.%s = %s %s at %s%s' % (hst, type, kpi, scaled_value, scales[kpi]['unit'], tm, deltaVal))
                
                self.setToolTip('%s, %s.%s = %s %s at %s' % (hst, type, kpi, scaled_value, scales[kpi]['unit'], tm))
                # if want instant hit - need to re-define mouseMoveEvent()
                # https://stackoverflow.com/questions/13720465/how-to-remove-the-time-delay-before-a-qtooltip-is-displayed
                
                found_some = True
                break
                
        if not found_some:
            return False
        else:
        
            self.update()
            return True
            
        log('click scan / kpi scan: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))

    '''
    def event_(self, event):
        if event.type() == QEvent.ToolTip:
            QToolTip.showText(self.mapToGlobal(event.pos()), '123\n456', self)
\            return True
        else:
            return super().event(event)
    '''
            
        
    def mousePressEvent(self, event):
        '''
            step1: calculate time
            step2: look through metrics which one has same/similar value
            step3: show tooltip?
            
        '''
        
        if event.button() == Qt.RightButton:
            return
        
        pos = event.pos()
        
        time = self.t_from + datetime.timedelta(seconds= ((pos.x() - self.side_margin - self.left_margin)/self.step_size*self.t_scale) - self.delta)
        
        self.checkForHint(pos)
            
    def resizeWidget(self):
        seconds = (self.t_to - self.t_from).total_seconds()
        number_of_cells = int(seconds / self.t_scale) + 1
        self.resize(number_of_cells * self.step_size + self.side_margin*2 + self.left_margin, self.size().height()) #dummy size
        
    def drawLegend(self, qp, startX, stopX):
    
        lkpis = []      # kpi names to be able to skip doubles
        lkpisl = []     # kpi labels
        lpens = []      # pens. None = host line (no pen)
        
        lLen = 128
    
        lFont = QFont ('SansSerif', utils.cfg('legend_font', 8))
        fm = QFontMetrics(lFont)

        raduga_i = 0
        
        drawTimeScale = cfg('legendTimeScale', True)
        
        for h in range(0, len(self.hosts)):
        
            type = hType(h, self.hosts)
            
            if self.legend == 'hosts' and len(self.nkpis[h]) > 0:
                # put a host label
                lpens.append(None)
                lkpisl.append('%s:%s' % (self.hosts[h]['host'], self.hosts[h]['port']))
        
            for kpi in self.nkpis[h]:
            
                gantt = False
            
                if self.legend == 'kpis':
                    '''
                    
                        DEPR ECA DEAD
                        
                    '''
                    if kpi in lkpis:
                        #skip as already there
                        continue
                        
                    if 'dUnit' in kpiStylesNN[type][kpi]:
                        unit = ' ' + kpiStylesNN[type][kpi]['dUnit']
                    else:
                        unit = ''
                        
                    label = kpiStylesNN[type][kpi]['label'] + ': ' + self.nscales[h][kpi]['label'] + unit
                            
                    lkpis.append(kpi)
                    lkpisl.append(label)

                if self.legend == 'hosts':

                    if kpiDescriptions.getSubtype(type, kpi) == 'gantt':
                        gantt = True
                        
                    if not gantt and kpi in self.nscales[h] and 'unit' in self.nscales[h][kpi]:
                        unit = ' ' + self.nscales[h][kpi]['unit']

                        label = kpiStylesNN[type][kpi]['label']
                        
                        if kpi in self.nscales[h]: #if those are scanned already
                            label += ': ' + self.nscales[h][kpi]['label'] + unit + ', max: ' + self.nscales[h][kpi]['max_label'] + unit + ', last: ' + self.nscales[h][kpi]['last_label'] + unit
                    else:
                            
                        label = kpiStylesNN[type][kpi]['label']

                    lkpis.append(kpi)
                    lkpisl.append(label)

                # legend width calc
                ll = fm.width(label)
                
                if ll > lLen:
                    lLen = ll
                    
                if gantt:
                    lpens.append([QBrush(kpiStylesNN[type][kpi]['brush']), self.kpiPen[type][kpi]])
                else:
                    if utils.cfg('raduga'):
                        lpens.append(kpiDescriptions.radugaPens[raduga_i % 32])
                        raduga_i += 1
                        
                    else:
                        lpens.append(self.kpiPen[type][kpi])


        fontHeight = fm.height()
        
        qp.setPen(QColor('#888'))
        qp.setBrush(QColor('#FFF'))
        
        #qp.drawRect(10 + self.side_margin, 10 + self.top_margin + self.y_delta, lLen + 58, fontHeight * len(lkpisl)+8)
        
        #print('legendRender, stopX, startX: a', self.legendRender, stopX, startX)
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
            
        self.legendWidth = lLen + 58

        qp.drawRect(leftX, 10 + self.top_margin + self.y_delta, self.legendWidth, self.legendHeight)
        
        # this if for Copy Legend action
        # so call for render will be with startX = 0, so we fake leftX
        
        #print('drawlegend, startX - leftX', startX, leftX)
        
        self.legendRegion = QRegion(10 + self.side_margin, 10 + self.top_margin + self.y_delta, self.legendWidth + 1, self.legendHeight + 1)
        
        i = 0
        
        qp.setFont(lFont)
        for kpi in lkpisl:
        
            if lpens[i] is not None:

                if isinstance(lpens[i], QPen):
                    # ah, this is wrong, so wrong...
                    # but for normal kpis this is just a QPen
                    # for others (but only gantt exist?) it is s LIST (!) [QBrush, QPen]

                    qp.setPen(lpens[i])
                    qp.drawLine(leftX + 4, 10 + self.top_margin + fontHeight * (i+1) - fontHeight/4 + self.y_delta, leftX + 40, 10 + self.top_margin + fontHeight * (i+1) - fontHeight/4 + self.y_delta)
                else:
                    # must be gantt, so we put a bar...
                    qp.setBrush(lpens[i][0])
                    qp.setPen(lpens[i][1])
                    qp.drawRect(leftX + 4, 10 + self.top_margin + fontHeight * (i+1) - fontHeight/4 + self.y_delta - 2, 36, 4)
                
                ident = 10 + 40
            else:
                ident = 4
            
            qp.setPen(QColor('#000'))
            qp.drawText(leftX + ident, 10 + self.top_margin + fontHeight * (i+1) + self.y_delta, str(kpi))
            
            i += 1
            
        if drawTimeScale:
            qp.drawText(leftX + 4, 10 + self.top_margin + fontHeight * (i+1) + self.y_delta + 6, 'Time scale: ' + self.timeScale)
                    
    def drawChart(self, qp, startX, stopX):
    
        '''
            draws enabled charts
            scales need to be calculated/adjusted beforehand
        '''
    
        def longestStr(str):
        
            l = 0
            ls = ''
            
            for s in str.split('\n'):
                if l < len(s):
                    l = len(s)
                    ls = s
            
            return ls
                
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
        
        for h in range(0, len(self.hosts)):
        
            #print('draw host:', self.hosts[h]['host'], self.hosts[h]['port'])

            if len(self.ndata[h]) == 0:
                continue
                
            type = hType(h, self.hosts)
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


                #print(kpiStylesNN[type][kpi]['subtype'])
                
                if kpiStylesNN[type][kpi]['subtype'] == 'gantt':
                    gantt = True
                    self.gotGantt = True
                else:
                    gantt = False
                
                timeKey = kpiDescriptions.getTimeKey(type, kpi)

                if gantt:
                
                    #gFont = QFont ('SansSerif', 8)
                    
                    gFont = QFont ('SansSerif', kpiStylesNN[type][kpi]['font'])
                    qp.setFont(gFont)
                    
                    fm = QFontMetrics(gFont)
                    fontHeight = fm.height()
                    
                    fontWidth = 0
                    
                    gc = self.ndata[h][kpi]
                    
                    for e in gc:
                        width = fm.width(e)
                        
                        if fontWidth < width:
                            fontWidth = width

                    # self.left_margin = fontWidth + 8

                    x_scale = self.step_size / self.t_scale

                    qp.setBrush(kpiStylesNN[type][kpi]['brush']) # bar fill color
                    
                    #print(kpiStylesNN[type][kpi])
                    
                    if len(gc) > 0:
                        yr = kpiStylesNN[type][kpi]['y_range']
                        
                        y_scale = (wsize.height() - top_margin - self.bottom_margin - 2 - 1) / len(gc)
                        y_shift = y_scale/100*yr[0] * len(gc)
                        y_scale = y_scale * (yr[1] - yr[0])/100
                    
                    i = 0
                    
                    hlDesc = None

                    height = kpiStylesNN[type][kpi]['width']
                    ganttShift = kpiStylesNN[type][kpi]['shift']
                    
                    for entity in gc:
                    
                        y = i * y_scale + y_scale*0.5 - height/2 + y_shift # this is the center of the gantt line
                    
                        range_i = 0
                        for t in gc[entity]:

                            x = (t[0].timestamp() - from_ts) # number of seconds
                            x = self.side_margin + self.left_margin +  x * x_scale
                            
                            if t[1] is None or t[0] is None:
                                log('[w] null instead of timestamp, skip', str(t))
                                continue

                            width = (t[1].timestamp() - t[0].timestamp()) * x_scale
                            
                            if self.highlightedKpi == kpi and self.highlightedKpiHost == h and self.highlightedEntity == entity and self.highlightedRange == range_i:
                                highlight = True
                            else:
                                highlight = False
                            
                            ganttPen = kpiStylesNN[type][kpi]['pen']
                            
                            if highlight == True:
                                ganttPen.setWidth(2)
                            else:
                                ganttPen.setWidth(1)
                            
                            qp.setPen(ganttPen)
                            
                            if kpiStylesNN[type][kpi]['style'] == 'bar':
                                qp.drawRect(x, y + top_margin - t[3]*ganttShift, width, height)
                            else:
                                qp.drawLine(x, y + top_margin + 8, x + width, y + top_margin)
                                
                                qp.drawLine(x + width, y + top_margin + 8, x + width, y + top_margin)
                                qp.drawLine(x, y + top_margin, x, y + top_margin + 8)
                                

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
                                
                                hlRect = QRect (x + xOff, y + top_margin - fontHeight*nl - 2 - yShift, cfg('ganttLabelWidth', 500), fontHeight * nl)
                            
                            range_i += 1


                        if stopX - startX > 400 and not self.hideGanttLabels:
                        
                            # only draw labels in case of significant refresh
                        
                            # qp.setBackground(QColor('red')) - does not work
                            # otherwise drawing area too small, it won't paint full text anyway
                            # to avoid only ugly artefacts...
                            #qp.setPen(QColor('#448')) # entity label color
                            
                            clr = ganttPen.color()
                            clr = QColor(clr.red()*0.6, clr.green()*0.6, clr.blue()*0.6)
                            
                            if self.highlightedEntity == entity:
                                gFont.setWeight(QFont.Bold)
                                qp.setFont(gFont)

                            
                            qp.setPen(clr) # entity label color
                            qp.drawText(startX + self.side_margin + fontHeight, y + top_margin + fontHeight / 2, entity);

                            if self.highlightedEntity == entity:
                                gFont.setWeight(QFont.Normal)
                                qp.setFont(gFont)
                        
                        i += 1

                        if hlDesc is not None:
                            ganttPen = kpiStylesNN[type][kpi]['pen']
                            
                            clr = ganttPen.color()
                            clr = QColor(clr.red()*0.6, clr.green()*0.6, clr.blue()*0.6)
                            qp.setPen(clr)
                            
                            qp.drawText(hlRect, Qt.AlignLeft, hlDesc)
                    continue
                
                array_size = len(self.ndata[h][timeKey])
                time_array = self.ndata[h][timeKey]

                points = [0]*array_size
            
                t0 = time.time()
                
                if utils.cfg('raduga'):
                    kpiPen = kpiDescriptions.radugaPens[raduga_i % 32]
                    raduga_i += 1
                else:
                    kpiPen = self.kpiPen[type][kpi]
                
                if kpi == self.highlightedKpi and h == self.highlightedKpiHost:
                    kpiPen.setWidth(2)
                    qp.setPen(kpiPen)
                else:
                    kpiPen.setWidth(1)
                    qp.setPen(kpiPen)
                
                start_point = 0
            
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
                
                # log(h)
                # log(kpi)
                # log(self.nscales[h][kpi]['y_max'])
                # log('y_scale = %s' % str(y_scale))
                
                # seems no longer required for drawing duet to starX/stopX
                #x_left_border = 0 - self.pos().x() # x is negative if scrolled to the right
                #x_right_border = 0 - self.pos().x() + self.parentWidget().size().width()

                iii = 0
                #for i in range(0, array_size):
                
                i = -1
                
                #to trace drawing area uncomment:
                #qp.drawLine(startX, 10, startX, 50)
                '''
                qp.drawLine(startX, 10, startX, 50)
                qp.drawLine(startX, 50, stopX-1, 50)
                qp.drawLine(stopX, 50, stopX-1, 90)
                qp.drawLine(startX, 10, stopX-1, 90)
                '''
                
                while i < array_size-1:
                    i+=1
                    #log(self.data['time'][i])
                    
                    #if time_array[i] < from_ts or time_array[i] > self.t_to.timestamp() - self.delta:
                    if time_array[i] < from_ts:
                        #nobody asked to draw this...
                        continue
                        
                    x = (time_array[i] - from_ts) # number of seconds
                    x = self.side_margin + self.left_margin +  x * x_scale

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
                    else:
                        if start_point == 0:
                            t1 = time.time()
                            start_point = i
                            
                    y = self.ndata[h][kpi][i]
                    
                    if y < 0:
                        y = wsize.height() - self.bottom_margin - 1
                    else:
                        y = self.nscales[h][kpi]['y_min'] + y*y_scale
                        y = round(wsize.height() - self.bottom_margin - y) - 2

                    if False and x0 == int(x) and y0 == int(y): # it's same point no need to draw
                        points_to_skip += 1
                        continue
                        
                    #log('y = %i' % (y))
                    
                    # i wander how much this slows the processing...
                    # to be measured
                    if self.highlightedPoint == i and kpi == self.highlightedKpi and h == self.highlightedKpiHost:
                        #log('i wander how much this slows the processing...')
                        qp.drawLine(x-5, y-5, x+5, y+5)
                        qp.drawLine(x-5, y+5, x+5, y-5)

                    x0 = int(x)
                    y0 = int(y)
                        
                    try: 
                        points[points_to_draw] = QPoint(x, y)
                        points_to_draw += 1
                        #points[i-start_point] = QPoint(x, y)
                    except:
                        log('failed: %s %i = %i, x, y = (%i, %i)' % (kpi, i, self.data[kpi][i], x, y))
                        log('scales: %s' % (str(self.scales[kpi])))
                        break

                #log('points_to_draw: %i' % points_to_draw)
                #log('points_to_draw: %s' % str(points[:points_to_draw]))
                
                if start_point == 0:
                    t1 = time.time()
                #log('start: %i' % start_point)
                #log(points[:10])
                t2 = time.time()
                # qp.drawPolyline(QPolygon(points[:array_size-start_point]))
                #log('points to draw: %i' % (points_to_draw))
                #log('points: %s' % str(points[:10]))
                
                qp.drawPolyline(QPolygon(points[:points_to_draw]))
                
                points.clear()
                
                t3 = time.time()
                
                #log('%s: skip/calc/draw: %s/%s/%s, (skip: %i)' % (kpi, str(round(t1-t0, 3)), str(round(t2-t1, 3)), str(round(t3-t2, 3)), points_to_skip))
                #log('iii = %i' % (iii))
        
        # this supposed to restore the border for negative values (downtime)...
        
        #qp.setPen(QColor('#F00'))
        #qp.drawLine(12786, 110, 12787, 110)
        
        qp.setPen(QColor('#888'))
        qp.drawLine(self.side_margin + self.left_margin, wsize.height() - self.bottom_margin - 1, wsize.width() - self.side_margin, wsize.height() - self.bottom_margin - 1)
        
        
        if self.legend is not None:
            self.drawLegend(qp, startX, stopX)
        
    def drawGrid(self, qp, startX, stopX):
        '''
            draws grid and labels
            based on scale and timespan        
        '''
        
        #prnt('grid %i:%i' % (startX, stopX))
        #print('grid: ', self.gridColor.getRgb())
        
        '''
        
        what is that???
        
        for h in range(0, len(self.hosts)):

            if len(self.nkpis) == 0: # sometimes hosts filled before nkpis
                break

            type = hType(h, self.hosts)

            for kpi in self.nkpis[h]:
            
                if kpiDescriptions.getSubtype(type, kpi) == 'gantt':
                    # self.left_margin = 100
                    break
        '''

        
        t0 = time.time()
        
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
        
        t_scale = self.t_scale
        
        seconds = (self.t_to - self.t_from).total_seconds()
        
        qp.setPen(self.gridColor)

        # vertical scale
        
        for j in range(1,10):
            y = top_margin + j * y_step
            
            if j == 5:
                qp.setPen(self.gridColorMj) #50% CPU line
            
            qp.drawLine(self.side_margin + self.left_margin + 1, y, wsize.width()-self.side_margin - 1, y)
            
            if j == 5:
                qp.setPen(self.gridColor)
        
        #x is in pixels
        x = self.side_margin + self.left_margin +self.step_size
        
        #have to align this to have proper marks
        
        self.delta = self.t_from.timestamp() % t_scale
        
        if t_scale == 60*60*4:
            self.delta -= 3600 # not sure, could be a bug (what if negative?)
        
        bottom_margin = self.bottom_margin
        side_margin = self.side_margin
        delta = self.delta
        
        t1 = time.time()
        
        x_left_border = 0 - self.pos().x() # x is negative if scrolled to the right
        x_right_border = 0 - self.pos().x() + self.parentWidget().size().width()

        while x < ((seconds / t_scale + 1) * self.step_size):
        
            #if x < x_left_border or x > x_right_border:
            if x < startX - self.font_width3 or x > stopX + self.font_width3: 
                x += self.step_size
                
                continue
                
            qp.drawLine(x, top_margin + 1, x, wsize.height() - bottom_margin - 2)
            
            c_time = self.t_from + datetime.timedelta(seconds=(x - side_margin - self.left_margin)/self.step_size*t_scale - delta)
            
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
                hrs_scale = 60*24*4
                
            min = int(c_time.strftime("%H")) *60 + int(c_time.strftime("%M"))
            
            if sec_scale is not None:
                if c_time.timestamp() % sec_scale == 0:
                    major_line = True

                if c_time.timestamp() % hrs_scale == 0:
                    date_mark = True
            elif min % min_scale == 0:
                major_line = True
                
                if min % hrs_scale == 0:
                    date_mark = True
                    
            if major_line:
            
                qp.setPen(self.gridColorMj)
                qp.drawLine(x, top_margin + 1, x, wsize.height() - bottom_margin - 2)

                qp.setPen(QColor('#000'))
                
                if len(label) == 5: # 00:00
                    label_width = self.font_width1
                else:
                    label_width = self.font_width2
                qp.drawText(x-label_width, wsize.height() - bottom_margin + self.font_height, label)
                
                if date_mark:
                    label = c_time.strftime('%Y-%m-%d')
                    qp.drawText(x-self.font_width3, wsize.height() - bottom_margin + self.font_height*2, label)
                    
                qp.setPen(self.gridColor)
        
            x += self.step_size
        #log(seconds / t_scale * 10)
        
        t2 = time.time()
        
        #log('grid: prep/draw: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))
        
        
    def paintEvent(self, QPaintEvent):

        if self.paintLock:
            # paint locked  for some reason
            return
            
        startX = QPaintEvent.rect().x()
        stopX = startX + QPaintEvent.rect().width()

        # prnt(' --- paint event ---  from: %i, to: %i, %s' % (startX, stopX, str(self.paintLock)))
        
        t0 = time.time()
        qp = QPainter()
        
        super().paintEvent(QPaintEvent)
        
        qp.begin(self)

        t1 = time.time()
        self.drawGrid(qp, startX, stopX)
        t2 = time.time()
        self.drawChart(qp, startX, stopX)
        t3 = time.time()
        
        qp.end()

        t4 = time.time()
        
        #log('paintEvent: prep/grid/chart/end: %s/%s/%s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3)), str(round(t3-t2, 3)), str(round(t4-t3, 3))))

class chartArea(QFrame):
    
    statusMessage_ = pyqtSignal(['QString', bool])
    
    connected = pyqtSignal(['QString'])
    
    kpiToggled = pyqtSignal([int])
    
    hostsUpdated = pyqtSignal()
    scalesUpdated = pyqtSignal()
    
    selfRaise = pyqtSignal(object)
    
    connection = None # db connection
    
    hostKPIs = [] # list of available host KPIS, sql names
    srvcKPIs = [] # list of available srvc KPIS, sql names
    
    dbProperties = {} # db properties, like timeZone, kpis available, etc
    
    dp = None # data provider object
    
    timer = None
    refreshCB = None
    
    lastReloadTime = None #reload timer
    lastHostTime = None #one host timer
    
    #last refresh time range
    fromTime = None
    toTime = None
    
    def indicatorSignal(self):
        self.selfRaise.emit(self.parentWidget())
    
    def disableDeadKPIs(self):
        
        chart = self.widget
        
        if len(chart.nkpis) == 0:
            log('[w] disableDeadKPIs: no kpis at all, exit')
            return
            
        for host in range(0, len(chart.hosts)):
            type = hType(host, chart.hosts)

            delKpis = []
            for kpi in chart.nkpis[host]:
                if kpi not in kpiStylesNN[type]:
                    delKpis.append(kpi)
                    
            for kpi in delKpis:
                log('[w] kpi %s is dsabled so it is removed from the list of selected KPIs for the host' % (kpi))
                
                chart.nkpis[host].remove(kpi)
                
                if type == 'service' and kpi in self.srvcKPIs:
                    self.srvcKPIs.remove(kpi)
                else:
                    if kpi in self.hostKPIs:
                        self.hostKPIs.remove(kpi)
                    
            delKpis = []
            
            for kpi in self.widget.nscales[host]:
                if kpi != 'time' and kpi not in kpiStylesNN[type]:
                    delKpis.append(kpi)
                   
            for kpi in delKpis:
                log('[w] removing %s from nscales becaouse it does not exist (disabled?)' % (kpi), 2)
                del self.widget.nscales[host][kpi]
                log('[w] removing %s from data ' % (kpi), 2)
                del self.widget.ndata[host][kpi]

    def statusMessage(self, str, repaint = False):
        if repaint: 
            self.statusMessage_.emit(str, True)
        else:
            self.statusMessage_.emit(str, False)
            
    def keyPressEventZ(self, event):
    
        def reportHighlight(host, kpi, point):
            #this is black magic copy paste from scanforhint
            type = hType(host, self.widget.hosts)
            timeKey = kpiDescriptions.getTimeKey(type, kpi)
            
            d = kpiStylesNN[type][kpi].get('decimal', 0)
            normVal = kpiDescriptions.normalize(kpiStylesNN[type][kpi], self.widget.ndata[host][kpi][point], d)

            scaled_value = utils.numberToStr(normVal, d)
            tm = datetime.datetime.fromtimestamp(self.widget.ndata[host][timeKey][point]).strftime('%Y-%m-%d %H:%M:%S')
            
            unit = self.widget.nscales[host][kpi]['unit']

            hst = self.widget.hosts[host]['host']
            if self.widget.hosts[host]['port'] != '':
                hst += ':'+str(self.widget.hosts[host]['port'])
            
            self.setToolTip('%s, %s.%s = %s %s at %s' % (hst, type, kpi, scaled_value, unit, tm))

            self.statusMessage('%s, %s.%s = %s %s at %s' % (hst, type, kpi, scaled_value, unit, tm))
            
        modifiers = QApplication.keyboardModifiers()

        if event.key() == Qt.Key_Left:
            if modifiers == Qt.AltModifier and self.widget.highlightedPoint:
                # move highlighted point one step left
                host = self.widget.highlightedKpiHost
                kpi = self.widget.highlightedKpi
                
                if self.widget.highlightedPoint > 0:
                    self.widget.highlightedPoint -= 1
                    self.widget.update()
                    
                    reportHighlight(host, kpi, self.widget.highlightedPoint)
            else:
                x = 0 - self.widget.pos().x() # pos().x() is negative if scrolled to the right
                self.scrollarea.horizontalScrollBar().setValue(x - self.widget.step_size*10)

        elif event.key() == Qt.Key_Right:
            if modifiers == Qt.AltModifier and self.widget.highlightedPoint:
                # move highlighted point one step right
                
                host = self.widget.highlightedKpiHost
                kpi = self.widget.highlightedKpi
                dSize = len(self.widget.ndata[host][kpi])
                
                if self.widget.highlightedPoint < dSize:
                    self.widget.highlightedPoint += 1
                    self.widget.update()
                    
                    reportHighlight(host, kpi, self.widget.highlightedPoint)

            else:
                x = 0 - self.widget.pos().x() 
                self.scrollarea.horizontalScrollBar().setValue(x + self.widget.step_size*10)
            
        elif event.key() == Qt.Key_Home:
            self.scrollarea.horizontalScrollBar().setValue(0)
            
        elif event.key() == Qt.Key_End:
            self.scrollarea.horizontalScrollBar().setValue(self.widget.width() - self.width() + 22) # this includes scrollArea margins etc, so hardcoded...
            
        else: 
            super().keyPressEvent(event)

    def cleanup(self):
        log('cleanup call...')
        
        for host in range(len(self.widget.hosts)):

            if len(self.widget.nkpis) > 0:
                for kpi in self.widget.nkpis[host]:
                    #print('the same code in checkbocks callback - make a function')
                    self.widget.nkpis[host].remove(kpi) # kpis is a list
                    
                    if kpi in self.widget.ndata[host]:
                        #might be empty for alt-added
                        del(self.widget.ndata[host][kpi]) # ndata is a dict
            else:
                log('[w] kpis list is empty')

            # this part not required in checkbocks callback ')
            
            if len(self.widget.nscales)> 0:
                self.widget.nscales[host].clear() # this one is missing in in checkbocks callback 
                                                  # kinda on purpose, it leaves min/max/etc in kpis table (to be checked)
            if len(self.widget.ndata)> 0:
                self.widget.ndata[host].clear()
            
        self.widget.nscales.clear()
        self.widget.ndata.clear()
        
        log('cleanup complete')
        
    def initDP(self, kpis = None, message = None):
        '''
            this one to be called after creating a data provider
            to be called right after self.chartArea.dp = new dp
        '''

        log('before cleanup:' + str(kpis))
        self.cleanup()
        log('after cleanup:' + str(kpis))
            
        self.widget.ndata.clear()

        self.widget.hosts.clear()
        self.widget.nkpis.clear()

        self.widget.update()
        
        self.hostKPIs.clear()
        self.srvcKPIs.clear()
        
        if message:
            self.statusMessage(message)
        else:
            self.statusMessage('Connected, init basic info...')
            
        self.repaint()
        
        self.dp.initHosts(self.widget.hosts, self.hostKPIs, self.srvcKPIs)
        self.widget.allocate(len(self.widget.hosts))
        self.widget.initPens()
        
        if kpis:
            log('initDP processing', 5)
            log(str(kpis), 5)
            for i in range(len(self.widget.hosts)):
                host = self.widget.hosts[i]
                hst = '%s:%s' % (host['host'], host['port'])
                
                log(hst, 5)
                
                if hst in kpis:
                
                    log('host: ' + hst, 5)
                
                    if hst[-1] == ':':
                        kpis_n = list(set(self.hostKPIs) & set(kpis[hst])) # intersect to aviod non-existing kpis
                    else:
                        kpis_n = list(set(self.srvcKPIs) & set(kpis[hst])) # intersect to aviod non-existing kpis
                        
                    log(str(kpis_n), 5)
                    
                    self.widget.nkpis[i] = kpis_n

            #self.statusMessage('Loading saved kpis...')
            #self.repaint()

            log('reload from init dp', 4)
            # removed for the sake #372
            # self.reloadChart()

        self.hostsUpdated.emit()
        
        self.statusMessage('ready')

    def scrollSignal(self, mode, size):
        x = 0 - self.widget.pos().x() 
        self.scrollarea.horizontalScrollBar().setValue(x + mode*self.widget.step_size*size)

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
            newPos = self.widget.timeToPos(time)
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
        
    def setScale(self, host, kpi, newScale):
        '''
            scale changed to manual value
        '''
        log('setScale signal: %s -> %i' % (kpi, newScale))
        
        type = hType(host, self.widget.hosts)
        
        group = kpiStylesNN[type][kpi]['group']
        
        if  group == 0:
            kpiStylesNN[type][kpi]['manual_scale'] = newScale
        else:
            self.widget.manual_scales[group] = newScale
            
        self.widget.alignScales()
        log('self.scalesUpdated.emit() #5', 5)
        self.scalesUpdated.emit()
        self.widget.update()
        
    def adjustScale(self, mode, kpi):
        log('increaseScale signal: %s' % (kpi))
        
        if 'mem' in self.widget.manual_scales.keys():
            mem_max = self.widget.manual_scales['mem']
        else:
            mem_max = self.widget.scanMetrics('mem')
        
        if mode == 'increase':
            mem_max = self.widget.ceiling(mem_max + 1)
        else:
            mem_max =  self.widget.floor(mem_max - 1)
        
        self.widget.manual_scales['mem'] = mem_max
            
        self.widget.alignScales()
        log('self.scalesUpdated.emit() #6', 5)
        self.scalesUpdated.emit()
        self.widget.update()
        
    def connectionLost(self, err_str = ''):
        '''
            very synchronous call, it holds controll until connection status resolved
        '''
        self.statusMessage('Connection error (%s)' % err_str, True)
        
        msgBox = QMessageBox(self)
        msgBox.setWindowTitle('Connection lost')
        msgBox.setText('Connection failed, reconnect?')
        msgBox.setStandardButtons(QMessageBox.Yes| QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        iconPath = resourcePath('ico\\favicon.png')
        msgBox.setWindowIcon(QIcon(iconPath))
        msgBox.setIcon(QMessageBox.Warning)

        reply = None
        
        while reply != QMessageBox.No and self.dp.connection is None:
            reply = msgBox.exec_()
            if reply == QMessageBox.Yes:
                try:
                    self.statusMessage('Reconnecting to %s:%s...' % (self.dp.server['host'], str(self.dp.server['port'])), True)
                    self.dp.reconnect()
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
                    self.dp.getData(self.widget.hosts[host], fromto, kpis, self.widget.ndata[host])  
                    self.widget.nkpis[host] = kpis
                    
                    allOk = True
                    
                    t1 = time.time()
                    self.lastHostTime = t1-t0
                    self.statusMessage('%s added, %s s' % (kpi, str(round(t1-t0, 3))), True)
                except utils.dbException as e:
                    reconnected = self.connectionLost(str(e))
                    
                    if reconnected == False:
                        allOk = False
                        timer = False
                        
            # self.widget.paintLock = False
            
            if timer:
                self.timer.start(1000 * self.refreshTime)
            
            self.setStatus('idle', True)
            return allOk
        
        log('checkboxToggle %i %s' % (host, kpi), 5)
        
        modifiers = QApplication.keyboardModifiers()

        host_d = self.widget.hosts[host]
        
        allOk = None
        
        if kpi in self.widget.nkpis[host]:
        
            if modifiers & Qt.ControlModifier:
                for hst in range(0, len(self.widget.hosts)):
                    
                    # okay this is a confusing one:
                    # on Control+click we by default only "unckick" the kpi for all the hosts, same port
                    # but if the Shift also pressed - we ignore port and unclick bloody everything
                    
                    if (host_d['port'] == '' and self.widget.hosts[hst]['port'] == '') or (host_d['port'] != '' and (modifiers & Qt.ShiftModifier or self.widget.hosts[hst]['port'] == host_d['port'])):
                        
                        if cfg('loglevel', 3) > 3:
                            log('unclick, %s, %s:' % (str(hst), kpi))
                            log('kpis before unclick: %s' % (self.widget.nkpis[hst]))
                        if kpi in self.widget.nkpis[hst]:
                            self.widget.nkpis[hst].remove(kpi)
                            
                            if kpi in self.widget.ndata[hst]: #might be empty for alt-added (2019-08-30)
                                del(self.widget.ndata[hst][kpi])
                                
                        log('kpis after unclick: %s' % (self.widget.nkpis[hst]), 4)
                        log('data keys: %s' % str(self.widget.ndata[hst].keys()), 4)
                        
            else:       
                if cfg('loglevel', 3) > 3:
                    log('unclick, %s, %s:' % (str(host), kpi))
                    log('kpis before unclick: %s' % (self.widget.nkpis[host]))
                
                self.widget.nkpis[host].remove(kpi) # kpis is a list
                if kpi in self.widget.ndata[host]: #might be empty for alt-added
                    del(self.widget.ndata[host][kpi]) # ndata is a dict
                    
                if cfg('loglevel', 3) > 3:
                    log('kpis after unclick: %s' % (self.widget.nkpis[host]))
                    log('data keys: %s' % str(self.widget.ndata[host].keys()))
            
            self.widget.update()
        else:
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
                                        t1 = time.time()
                                        self.dp.getData(self.widget.hosts[hst], fromto, kpis[hst], self.widget.ndata[hst])
                                        self.widget.nkpis[hst] = kpis[hst]
                                        
                                        t2 = time.time()
                                        
                                        self.statusMessage('%s:%s %s added, %s s' % (self.widget.hosts[hst]['host'], self.widget.hosts[hst]['port'], kpi, str(round(t2-t1, 3))), True)
                                    
                            self.lastReloadTime = t2-t0
                            self.statusMessage('All hosts %s added, %s s' % (kpi, str(round(t2-t0, 3))))
                            allOk = True
                        except utils.dbException as e:
                            log('[!] getData: %s' % str(e))
                            self.setStatus('error')
                            reconnected = self.connectionLost(str(e))
                            
                            if reconnected == False:
                                allOk = False
                                
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
                '''
                t1 = time.time()
                self.statusMessage('%s added, %s s' % (kpi, str(round(t1-t0, 3))))
                self.renewMaxValues()
                self.widget.alignScales()
                self.scalesUpdated.emit()
                '''
         
                self.widget.update()
                
        #log('checkboxToggle result self.widget.nkpis:')
        #log(self.widget.nkpis)
        
        self.kpiToggled.emit(host)
        

    def refreshTimer(self):
        self.timer.stop()
        #print('also stop keep-alive timer here ((it will be kinda refreshed in get_data renewKeepAlive))')
        
        log('trigger auto refresh...')
        self.reloadChart()
        
        if self.timer: # need to check as it might be disabled inside reloadChart()
            self.timer.start(1000 * self.refreshTime)
    
    def refreshChanged(self, i):

        txtValue = self.refreshCB.currentText()
        
        if self.timer is not None:
            self.refreshTime = 0
            self.timer.stop()
            self.timer = None

        if txtValue == 'none':
            self.statusMessage('Autorefresh disabled.')
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
        
        # force move it to the end
        # self.scrollarea.horizontalScrollBar().setValue(self.widget.width() - self.width() + 22)
        
        self.widget.update()
        
        
    def renewMaxValues(self):
        '''
            scans max value and last value for kpi
            
            all hosts all kpis from self.ndata[*].keys() list (all enabled kpis)
            
            creates/fills self.scalesN[h] array
            defines max and last_value keys
            
            this one ignores groups/scales at all, just raw values
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
            
            type = hType(h, self.widget.hosts)

            # init zero dicts for scales
            # especially important for the first run

            scales.clear()

            for kpi in data.keys():
                scales[kpi] = {}
                
            #init zero max
            
            for kpi in data.keys():
                scales[kpi]['max'] = 0
                
            #scan for max

            for kpi in scales.keys():
            
                if kpi[:4] == 'time':
                    continue

                if type == 'service':
                    if kpi not in self.srvcKPIs:
                        log('kpi was removed so no renewMaxValues (%s)' % (kpi), 4)
                        continue
                else:
                    if kpi not in self.hostKPIs:
                        log('kpi was removed so no renewMaxValues (%s)' % (kpi), 4)
                        continue
                    
                if kpiDescriptions.getSubtype(type, kpi) == 'gantt':
                
                    eNum = 0
                    total = 0
                
                    for entity in data[kpi]:
                        total += len(data[kpi][entity])
                        eNum += 1
                        
                    scales[kpi]['entities'] = eNum
                    scales[kpi]['total'] = total
                    # print ('%i/%i' % (eNum, total))
                        
                    continue
                    
                timeKey = kpiDescriptions.getTimeKey(type, kpi)
                    
                # array_size = len(self.widget.ndata[h][timeKey]) # 2020-03-11
                array_size = len(data[timeKey])
                
                #print(data[timeKey][0], data[timeKey][array_size-1])
                
                if array_size == 0:
                    continue
                
                log('h: %i (%s), array_size: %i, timekey = %s, kpi = %s' %(h, self.widget.hosts[h]['host'], array_size, timeKey, kpi), 4)
                
                scales[timeKey] = {'min': data[timeKey][0], 'max': data[timeKey][array_size-1]}

                anti_crash_len = len(data[kpi])
                
                try:
                    for i in range(0, array_size):
                        t = data[timeKey][i]
                        
                        if i >= anti_crash_len:
                            log('[!] I am seriously considering crash here, my anti_crash_len=%i, array_size=%i, i = %i! host %i, kpi = %s, timeKey = %s' % (anti_crash_len, array_size, i, h, kpi, timeKey))
                            log('[!] host: %s' % (self.widget.hosts[h]))
                            
                            log('[!] len(kpi), len(time)', len(data[kpi]), len(data[timeKey]))
                            # continue - to have more details
                        
                        if t >= t_from:
                            '''
                            print(kpi, i)
                            print(scales[kpi])
                            print(data)
                            '''
                            if scales[kpi]['max'] < data[kpi][i]:
                                scales[kpi]['max'] = data[kpi][i]

                        if  t > t_to: #end of window no need to scan further
                            break

                except ValueError as e:
                    log('error: i = %i, array_size = %i' % (i, array_size))
                    log('timeKey = %s, kpi: = %s' % (timeKey, kpi))
                    log('scales[kpi][max] = %i' % (scales[kpi]['max']))
                    log('len(data[kpi]) = %i' % (len(data[kpi])))
                    
                    log('scales[kpi] = %s' % str(scales[kpi]))

                    log('exception text: %s' % (str(e)))
                    
                    for j in range(10):
                        log('data[%i] = %s' % (j, str(data[kpi][j])))
                        
                    for j in range(1, 10):
                        k = array_size - (10 - j) - 1
                        log('k = %i, kpi = %s, timeKey = %s' % (k, kpi, timeKey))
                        log('data[%s][%i] = %s' % (kpi, k, str(data[kpi][k])))
                        log('data[%s][%i] = %s' % (timeKey, k, str(data[timeKey][k])))
                        
                    raise e
                        
                if i > 0:
                    scales[kpi]['last_value'] = data[kpi][i]
                else:
                    scales[kpi]['last_value'] = None

        t1 = time.time()
        
        self.widget.alignScales()
        
        log('self.scalesUpdated.emit() #2', 5)
        self.scalesUpdated.emit()

    def reloadChart(self):

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
        
        #time.sleep(2)
        fromTime = self.fromEdit.text().strip()
        toTime = self.toEdit.text().strip()

        #backup for ESC
        self.fromTime = fromTime
        self.toTime = toTime
        
        if fromTime[:1] == '-' and toTime == '':
            try:
                hours = int(fromTime[1:])
                starttime = datetime.datetime.now() - datetime.timedelta(seconds= hours*3600)
                starttime -= datetime.timedelta(seconds= starttime.timestamp() % 3600)
                self.widget.t_from = starttime
                self.fromEdit.setStyleSheet("color: black;")
            except:
                self.fromEdit.setStyleSheet("color: red;")
                self.statusMessage('datetime syntax error')
                return
        else:
            try:
                
                if len(fromTime) == 10:
                    self.widget.t_from = datetime.datetime.strptime(fromTime, '%Y-%m-%d')
                    
                    self.fromEdit.setText(fromTime + ' 00:00:00')
                else:
                    self.widget.t_from = datetime.datetime.strptime(fromTime, '%Y-%m-%d %H:%M:%S')
                    
                self.fromEdit.setStyleSheet("color: black;")
                
                if self.fromEdit.hasFocus() or self.toEdit.hasFocus():
                    self.setFocus()
            except:
                self.fromEdit.setStyleSheet("color: red;")
                self.statusMessage('datetime syntax error')
                return
            
        if toTime == '':
            self.widget.t_to = datetime.datetime.now() + datetime.timedelta(seconds= self.widget.timeZoneDelta)
        else:
            try:
                if len(toTime) == 10:
                    self.widget.t_to = datetime.datetime.strptime(toTime, '%Y-%m-%d')
                    
                    self.toEdit.setText(toTime + ' 00:00:00')
                else:
                    self.widget.t_to = datetime.datetime.strptime(toTime, '%Y-%m-%d %H:%M:%S')
                    
                self.toEdit.setStyleSheet("color: black;")
            except:
                self.statusMessage('datetime syntax error')
                return
              
        fromto = {'from': self.fromEdit.text(), 'to': self.toEdit.text()}
        
        allOk = None
        
        self.setStatus('sync', True)
        
        self.reloadLock = True
        
        actualRequest = False
        
        while allOk is None:
            try:
                for host in range(0, len(self.widget.hosts)):
                    if len(self.widget.nkpis[host]) > 0:
                        self.dp.getData(self.widget.hosts[host], fromto, self.widget.nkpis[host], self.widget.ndata[host])
                        actualRequest = True
                allOk = True

            except utils.dbException as e:
                self.setStatus('error', True)
                reconnected = self.connectionLost(str(e))
                
                if reconnected == False:
                    log('reconnected == False')
                    self.setStatus('sync', True)
                    allOk = False
                    timerF = False
                    self.refreshCB.setCurrentIndex(0) # will disable the timer on this change
                    log('timer = False 1')

        self.renewMaxValues()
        
        self.widget.resizeWidget()
        
        self.widget.update()

        #autoscroll to the right
        if toTime == '': # probably we want to see the most recent data...
            self.scrollarea.horizontalScrollBar().setValue(self.widget.width() - self.width() + 22) # this includes scrollArea margins etc, so hardcoded...
            
            #+ scrollRangeChanged logic as a little different mechanism works
        
        t1 = time.time()
        self.lastReloadTime = t1-t0
        
        if actualRequest:
            self.statusMessage('Reload finish, %s s' % (str(round(t1-t0, 3))))
        else:
            self.statusMessage('Ready')
        
        if timerF == True:
            self.timer.start(1000 * self.refreshTime)

        self.reloadLock = False
        self.setStatus('idle', True)

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
        fromtoWidth = scale * fm.width(' 2019-06-17 22:59:00 ') #have no idea why spaces required...

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

    def __init__(self):
        
        '''
            create top controls like from... to... reload, etc
            
            all this crap to be moved some place else one day...
        '''
        
        self.indicator = None
        
        super().__init__()


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
        
        grp = QGroupBox()
        hbar = QHBoxLayout();
        
        self.scaleCB = QComboBox()
        
        if cfg('experimental'):
            self.scaleCB.addItem('1 second')
            
        self.scaleCB.addItem('10 seconds')
        self.scaleCB.addItem('1 minute')
        self.scaleCB.addItem('5 minutes')
        self.scaleCB.addItem('10 minutes')
        self.scaleCB.addItem('15 minutes')
        self.scaleCB.addItem('30 minutes')
        self.scaleCB.addItem('1 hour')
        self.scaleCB.addItem('4 hours')
        
        self.scaleCB.setFocusPolicy(Qt.ClickFocus)
        
        self.scaleCB.setCurrentIndex(3)
        
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
        
        self.widget._parent = self

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