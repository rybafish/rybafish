from PyQt5.QtWidgets import QWidget, QFrame, QScrollArea, QVBoxLayout, QHBoxLayout, QPushButton, QFormLayout, QGroupBox, QLineEdit, QComboBox, QLabel, QMenu
from PyQt5.QtWidgets import QApplication, QMessageBox, QToolTip

from PyQt5.QtGui import QPainter, QColor, QPen, QPolygon, QIcon, QFont, QFontMetrics, QClipboard

from PyQt5.QtCore import QTimer

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
from kpiDescriptions import customKpi
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
    updateToTime = pyqtSignal(['QString'])
    
    statusMessage_ = pyqtSignal(['QString', bool])
    
    timeZoneDelta = 0 # to be set after connection

    hosts = [] # list of 'hosts': host + tenants/services. based on this we fill the KPIs table(s) - in order, btw
               # and why exactly do we have hosts in widget?..

    kpis = [] #list of kpis to be drawn << old one
    nkpis = [] #list of kpis to be drawn per host < new one

    kpiPen = {} #kpi pen objects dictionary
    
    highlightedKpi = None #kpi currently highlihed
    highlightedKpiHost = None # host for currently highlihed kpi
    
    highlightedPoint = None #point currently highlihed (currently just one)
    
    data = {} # dictionary of data sets + time line (all same length)
    scales = {} # min and max values
    
    ndata = [] # list of dicts of data sets + time line (all same length)
    nscales = [] # min and max values, list of dicts (per host)
    
    manual_scales = {} # if/when scale manually adjusted, per group! like 'mem', 'threads'

    #config section
    # to be filled during __init__ somehow
    conf_fontSize = 6
    
    
    font_height = 8 # to be calculated in __init__
    
    font_width1 = 16
    font_width2 = 30
    
    t_scale = 60*10 # integer: size of one minor grid step
    
    side_margin = 10
    top_margin = 8
    bottom_margin = 20
    step_size = 16
    
    y_delta = 0 # to make drawing space even to 10 parts (calculated in drawGrid)
    
    delta = 0 # offset for uneven time_from values

    #t_from = datetime.datetime.strptime("2019-05-01 12:00:00", "%Y-%m-%d %H:%M:%S")
    #t_to = datetime.datetime.now()
    
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
            
    
    def __init__(self):
        super().__init__()
        
        myFont = QFont ('SansSerif', self.conf_fontSize)
        fm = QFontMetrics(myFont)
        
        self.font_height = fm.height() - 2 # too much space otherwise
        
        self.bottom_margin = self.font_height*2 + 2 + 2
        
        log('font_height: %i' %(self.font_height))
        log('bottom_margin: %i' %(self.bottom_margin))
        
        self.font_width1 = fm.width('12:00') / 2
        self.font_width2 = fm.width('12:00:00') / 2
        self.font_width3 = fm.width('2019-06-17') / 2
        
        self.initPens()
                
    def initPens(self):
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
            
    def scanMetrics(self, grp):
        max_value = 0
        
        log('  scanMetrics(%s)' % grp)
        
        for h in range(0, len(self.hosts)):
            
            type = hType(h, self.hosts)
            
            for kpi in self.nscales[h].keys():   #check ns name (which is unique)
                    
                if kpi[:4] == 'time':
                    continue
                    
                if kpiStylesNN[type][kpi]['group'] == grp:
                    if max_value < self.nscales[h][kpi]['max']:
                        max_value = self.nscales[h][kpi]['max']
        
        if grp == 'mem':
            return self.ceiling(round(utils.GB(max_value)))
        else:
            return self.ceiling(max_value)
        
        
    def getGroupMax(self, grp):
    
        max_value = 0
    
        for h in range(0, len(self.hosts)):
            type = hType(h, self.hosts)
            
            for kpi in self.nscales[h].keys():

                if kpi[:4] == 'time':
                    continue

                if kpiStylesNN[type][kpi]['group'] == grp:
                    if max_value < self.nscales[h][kpi]['max']:
                        max_value = self.nscales[h][kpi]['max']
        
        return self.ceiling(max_value)
    
    def alignScales(self):
        '''
            align scales to normal values, prepare text labels (including max value, scale)
            for the KPIs table
        '''
        
        groups = []
        groupMax = {}
        
        log('  alignScales()')
        mem_max = self.scanMetrics('mem')
        thr_max = self.scanMetrics('thr')
        
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
                
                #log(scaleKpi)
                    
                '''
                    max and last values calculated before by renewMaxValues
                '''
                scaleKpi['y_min'] = 0 # we always start at 0...
                
                #memory group
                #if kpiDescriptions.kpiGroup[kpi] == 'mem':
                
                groupName = kpiStylesNN[type][kpi]['group']
                
                if groupName == 'mem':
                #elif kpi in ('indexserverMemUsed', 'indexserverMemLimit'):
                    #log(kpi)
                    max = scaleKpi['max']
                
                    scaleKpi['unit'] = 'GB'
                    
                    scaleKpi['max_label'] = str(round(utils.GB(scaleKpi['max']), 1))
                    scaleKpi['last_label'] = str(round(utils.GB(scaleKpi['last_value']), 1))
                    
                    if 'mem' in self.manual_scales:
                        mem_max = self.manual_scales['mem']

                    scaleKpi['y_max'] = utils.antiGB(mem_max)
                    #scaleKpi['label'] = str(mem_max)
                    scaleKpi['label'] = ('%i / %i' % (mem_max / 10, mem_max))
                
                elif groupName == 'cpu':
                    scaleKpi['y_max'] = 100
                    scaleKpi['max_label'] = scaleKpi['max']
                    scaleKpi['last_label'] = scaleKpi['last_value']
                    scaleKpi['label'] = '10 / 100'
                    scaleKpi['unit'] = '%'
                        
                else:
                    # all the rest:
                    # 0 group means no groupping at all, individual scales
                    # != 0 means some type of group (not mem and not cpu)
                    
                    if groupName == 0:
                        if 'manual_scale' in kpiStylesNN[type][kpi]:
                            max_value = kpiStylesNN[type][kpi]['manual_scale']
                        else:
                            max_value = self.nscales[h][kpi]['max']
                            max_value = self.ceiling(max_value)
                        
                    else: 
                        if groupName in self.manual_scales:
                            max_value = self.manual_scales[groupName]
                        else:
                            max_value = groupMax[groupName]
                    
                    #calculated in renewMaxValues
                    scaleKpi['max_label'] = scaleKpi['max']
                    scaleKpi['last_label'] = scaleKpi['last_value']
                    
                    #calculated here
                    scaleKpi['y_max'] = max_value
                    #scaleKpi['label'] = str(max_value)
                    scaleKpi['label'] = ('%i / %i' % (max_value / 10, max_value))
                    
                    scaleKpi['unit'] = kpiStylesNN[type][kpi]['sUnit']
                    
        
    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)

        startHere = cmenu.addAction("Make this a FROM time")
        stopHere = cmenu.addAction("Make this a TO time")
        
        copyTS = cmenu.addAction("Copy current timestamp")
        
        action = cmenu.exec_(self.mapToGlobal(event.pos()))

        # from / to menu items
        pos = event.pos()
        time = self.t_from + datetime.timedelta(seconds= (pos.x() - self.side_margin)/self.step_size*self.t_scale - self.delta) 
        
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
            time = time - datetime.timedelta(seconds= even_offset - self.t_scale)
            
            ts = time.strftime('%Y-%m-%d %H:%M:%S')

            clipboard = QApplication.clipboard()
            clipboard.setText(ts)
    
    def checkForHint(self, pos):
        '''
            1 actually we have to check the x scale 
             and check 2 _pixels_ around and scan Y variations inside
             
             because when we have 50 data points in same pixel (easy)
             we don't know actual Y, it's too noizy
             
        '''
        
        found = None
        
        for host in range(0, len(self.hosts)):
            
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
                self.setToolTip('')
                
                # self.update()
                
            self.statusMessage('No values around...')
            self.update() # - update on any click
            
        return
        
    def scanForHint(self, pos, host, kpis, scales, data):
        tolerance = 2 # number of pixels of allowed miss
        
        wsize = self.size()
        
        trgt_time = self.t_from + datetime.timedelta(seconds= ((pos.x() - self.side_margin)/self.step_size*self.t_scale) - self.delta)
        trgt_time = trgt_time.timestamp()
        
        x_scale = self.step_size / self.t_scale
        
        type = hType(host, self.hosts)
        
        for kpi in kpis:
        
            if kpi[:4] == 'time':
                continue
        
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
                return

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
                
            y_scale = (wsize.height() - self.top_margin - self.bottom_margin - 2 - 1)/(scales[kpi]['y_max'] - scales[kpi]['y_min'])

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
                        
                    self.highlightedKpi = None

                #if kpiDescriptions.kpiGroup[kpi] == 'mem':
                if kpiStylesNN[type][kpi]['group'] == 'mem':
                    scaled_value = round(utils.GB(data[kpi][j], scales[kpi]['unit']), 1)
                else:
                    scaled_value = data[kpi][j]
                
                log('click on %i.%s = %i, %f' % (host, kpi, data[kpi][j], scaled_value))
                self.kpiPen[type][kpi].setWidth(2)
                    
                self.highlightedKpi = kpi
                self.highlightedKpiHost = host
                self.highlightedPoint = j
                
                hst = self.hosts[host]['host']
                if self.hosts[host]['port'] != '':
                    hst += ':'+str(self.hosts[host]['port'])
                    
                tm = datetime.datetime.fromtimestamp(data[timeKey][j]).strftime('%Y-%m-%d %H:%M:%S')
                
                self.statusMessage('%s, %s.%s = %0.1f %s at %s' % (hst, type, kpi, scaled_value, scales[kpi]['unit'], tm))
                
                self.setToolTip('%s, %s.%s = %0.1f %s at %s' % (hst, type, kpi, scaled_value, scales[kpi]['unit'], tm))
                # if want instant need to re-define mouseMoveEvent()
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
        
        time = self.t_from + datetime.timedelta(seconds= ((pos.x() - self.side_margin)/self.step_size*self.t_scale) - self.delta)
        
        self.checkForHint(pos)
            
    def resizeWidget(self):
        seconds = (self.t_to - self.t_from).total_seconds()
        number_of_cells = int(seconds / self.t_scale) + 1
        self.resize(number_of_cells * self.step_size + self.side_margin*2, self.size().height()) #dummy size
        
    def drawChart(self, qp):
    
        '''
            draws enabled charts
            scales need to be calculated/adjusted beforehand
        '''
    
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
                
        for h in range(0, len(self.hosts)):
            if len(self.ndata[h]) == 0:
                continue
                
                
            type = hType(h, self.hosts)
            for kpi in self.nkpis[h]:
            
                if kpi not in self.ndata[h]:
                    # alt-added kpis here, already in kpis but no data requested
                    return
            
                #log('lets draw %s (host: %i)' % (str(kpi), h))

                timeKey = kpiDescriptions.getTimeKey(type, kpi)
                
                array_size = len(self.ndata[h][timeKey])
                time_array = self.ndata[h][timeKey]

                points = [0]*array_size
            
                t0 = time.time()

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

                # log(h)
                # log(kpi)
                # log(self.nscales[h][kpi]['y_max'])
                # log('y_scale = %s' % str(y_scale))
                
                x_left_border = 0 - self.pos().x() # x is negative if scrolled to the right
                x_right_border = 0 - self.pos().x() + self.parentWidget().size().width()

                iii = 0
                #for i in range(0, array_size):
                
                i = -1
                while i < array_size-1:
                    i+=1
                    #log(self.data['time'][i])
                    
                    #if time_array[i] < from_ts or time_array[i] > self.t_to.timestamp() - self.delta:
                    if time_array[i] < from_ts:
                        #nobody asked to draw this...
                        continue
                        
                    x = (time_array[i] - from_ts) # number of seconds
                    x = self.side_margin +  x * x_scale

                    #log('x = %i' % (x))

                    #if x < self.side_margin:
                    #if x < x_left_border - self.side_margin or x > wsize.width() - self.side_margin: 
                    #if x < x_left_border + self.side_margin or x > x_right_border: 

                    if x < x_left_border - 30 or x > x_right_border: 

                        if False and x < x_left_border and i+1000 < array_size: #turbo rewind!!!
                            x = (time_array[i+1000] - from_ts) # number of seconds
                            x = self.side_margin +  x * x_scale
                            
                            if x < x_left_border:
                                i+=1000
                                
                                iii += 1
                                continue
                            
                        if x > x_right_border:
                            break
                    
                        #if  x + self.pos().x() < 0
                        # skip the stuff before the widget starts...
                        # not before the scroll visible area 
                        # as we have no any idea what is the visible area...
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
        qp.drawLine(self.side_margin, wsize.height() - self.bottom_margin - 1, wsize.width() - self.side_margin, wsize.height() - self.bottom_margin - 1)
        
    def drawGrid(self, qp):
        '''
            draws grid and labels
            based on scale and timespan        
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
        qp.drawRect(self.side_margin, top_margin, wsize.width()-self.side_margin*2, wsize.height()-top_margin-self.bottom_margin-1)

        qp.setPen(QColor('#000'))
        qp.setFont(QFont('SansSerif', self.conf_fontSize))
        
        t_scale = self.t_scale
        
        seconds = (self.t_to - self.t_from).total_seconds()
        
        qp.setPen(QColor('#DDD'))
        

        # vertical scale
        
        for j in range(1,10):
            y = top_margin + j * y_step
            
            if j == 5:
                qp.setPen(QColor('#AAA'))
            
            qp.drawLine(self.side_margin, y, wsize.width()-self.side_margin, y)
            
            if j == 5:
                qp.setPen(QColor('#DDD'))
        
        #x is in pixels
        x = self.side_margin+self.step_size
        
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
        
            if x < x_left_border or x > x_right_border:
                x += self.step_size
                
                continue
                
            qp.drawLine(x, top_margin + 1, x, wsize.height() - bottom_margin - 2)
            
            #log('%i <-' % ((x - side_margin)/step_size))
            
            c_time = self.t_from + datetime.timedelta(seconds=(x - side_margin)/self.step_size*t_scale - delta)
            
            major_line = False
            date_mark = False
            
            if t_scale <= 60*60:
                label = c_time.strftime("%H:%M:%S")
            else:
                label = c_time.strftime("%H:%M")
                
                
            sec_scale = None
            min_scale = None
            hrs_scale = None
            
            if t_scale == 10:
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
            
                qp.setPen(QColor('#AAA'))
                qp.drawLine(x, top_margin + 1, x, wsize.height() - bottom_margin - 2)

                qp.setPen(QColor('#000'))
                
                if len(label) == 5: # 00:00
                    label_width = self.font_width1
                else:
                    label_width = self.font_width2
                qp.drawText(x-label_width, wsize.height() - bottom_margin + self.font_height, label);
                
                if date_mark:
                    label = c_time.strftime('%Y-%m-%d')
                    qp.drawText(x-self.font_width3, wsize.height() - bottom_margin + self.font_height*2, label);
                    
                qp.setPen(QColor('#DDD'))
        
            x += self.step_size
        #log(seconds / t_scale * 10)
        
        t2 = time.time()
        
        #log('grid: prep/draw: %s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3))))
        
        
    def paintEvent(self, QPaintEvent):

        #log(' --- paint event ---')
    
        t0 = time.time()
        qp = QPainter()
        
        size = self.size()
        super().paintEvent(QPaintEvent)
        
        qp.begin(self)
        
        t1 = time.time()
        self.drawGrid(qp)
        t2 = time.time()
        self.drawChart(qp)
        t3 = time.time()
        
        qp.end()

        t4 = time.time()
        
        #QToolTip.showText(self.mapToGlobal(QPoint(10, 10)), '123\n456', self)
        
        #log('paintEvent: prep/grid/chart/end: %s/%s/%s/%s' % (str(round(t1-t0, 3)), str(round(t2-t1, 3)), str(round(t3-t2, 3)), str(round(t4-t3, 3))))

class chartArea(QFrame):

    #scalesUpdated = pyqtSignal(['QString'])
    
    statusMessage_ = pyqtSignal(['QString', bool])
    
    connected = pyqtSignal(['QString'])
    
    kpiToggled = pyqtSignal([int])
    
    hostsUpdated = pyqtSignal()
    scalesUpdated = pyqtSignal()
    
    connection = None # db connection
    
    hostKPIs = [] # list of available host KPIS, sql names
    srvcKPIs = [] # list of available srvc KPIS, sql names
    
    dbProperties = {} # db properties, like timeZone, kpis available, etc
    
    dp = None # data provider object
    
    timer = None
    refreshCB = None
    
    def statusMessage(self, str, repaint = False):
        if repaint: 
            self.statusMessage_.emit(str, True)
        else:
            self.statusMessage_.emit(str, False)
            
    def keyPressEvent(self, event):
    
        super().keyPressEvent(event)
    
        if event.key() == Qt.Key_Left:
            #x = 0 - self.widget.pos().x() # pos().x() is negative if scrolled to the right
            #self.scrollarea.horizontalScrollBar().setValue(x - self.widget.step_size*10)

            self.scrollarea.horizontalScrollBar().setValue(self.widget.width()/2 - self.width()/2)
            
        if event.key() == Qt.Key_Home:
            self.scrollarea.horizontalScrollBar().setValue(0)
            
        if event.key() == Qt.Key_End:
            self.scrollarea.horizontalScrollBar().setValue(self.widget.width() - self.width() + 22) # this includes scrollArea margins etc, so hardcoded...

    def initDP(self):
        '''
            this one to be called after creating a data provider
            to be called right after self.chartArea.dp = new dp
        '''
        
        for host in range(len(self.widget.hosts)):
            for kpi in self.widget.nkpis[host]:
                log('clear %i/%s...' % (host, kpi))
                
                #print('the same code in checkbocks callback - make a function')
                self.widget.nkpis[host].remove(kpi) # kpis is a list
                if kpi in self.widget.ndata[host]:
                    #might be empty for alt-added
                    del(self.widget.ndata[host][kpi]) # ndata is a dict
            
            self.widget.ndata[host].clear()
            
        self.widget.ndata.clear()
        
        self.widget.hosts.clear()
        self.widget.nkpis.clear()
        
        self.widget.update()
        
        self.hostKPIs.clear()
        self.srvcKPIs.clear()
        
        self.statusMessage('Connected, init basic info...')
        self.repaint()
        
        self.dp.initHosts(self.widget.hosts, self.hostKPIs, self.srvcKPIs)
        self.widget.allocate(len(self.widget.hosts))
        self.widget.initPens()

        self.hostsUpdated.emit()
        
        self.statusMessage('ready')
        
        
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
            it's memoty only so far
        '''
        log('setScale signal: %s -> %i' % (kpi, newScale))
        
        type = hType(host, self.widget.hosts)
        
        group = kpiStylesNN[type][kpi]['group']
        
        if  group == 0:
            kpiStylesNN[type][kpi]['manual_scale'] = newScale
        else:
            self.widget.manual_scales[group] = newScale
            
        self.widget.alignScales()
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
        self.scalesUpdated.emit()
        self.widget.update()
        
    def connectionLost(self, err_str = ''):
        '''
            very synchronous call, it holds controll until connection status resolved
        '''
        self.statusMessage('Connection error (%s)' % err_str, True)
        
        msgBox = QMessageBox()
        msgBox.setWindowTitle('Connection lost')
        msgBox.setText('Connection failed, reconnect?')
        msgBox.setStandardButtons(QMessageBox.Yes| QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        iconPath = resourcePath('ico\\favicon.ico')
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
    
    def checkboxToggle(self, host, kpi):
        def substract(list1, list2):
            res = [item for item in list1 if item not in list2]
            return res
            
        def request_kpis(self, host_d, host, kpi, kpis):
            '''
                
            '''
            allOk = None
            self.statusMessage('Request %s:%s/%s...' % (host_d['host'], host_d['port'], kpi), True)

            while allOk is None:
                try:
                    t0 = time.time()
                    self.dp.getData(self.widget.hosts[host], fromto, kpis, self.widget.ndata[host])  
                    self.widget.nkpis[host] = kpis
                    allOk = True
                    
                    t1 = time.time()
                    self.statusMessage('%s added, %s s' % (kpi, str(round(t1-t0, 3))), True)
                except utils.dbException as e:
                    reconnected = self.connectionLost(str(e))
                    
                    if reconnected == False:
                        allOk = False
                        
            return allOk
        
        modifiers = QApplication.keyboardModifiers()

        host_d = self.widget.hosts[host]
        
        allOk = None
        
        if kpi in self.widget.nkpis[host]:
        
            if modifiers == Qt.ControlModifier:
                for hst in range(0, len(self.widget.hosts)):
                    if (host_d['port'] == '' and self.widget.hosts[hst]['port'] == '') or (host_d['port'] != '' and self.widget.hosts[hst]['port'] != ''):
                        
                        if kpi in self.widget.nkpis[hst]:
                            self.widget.nkpis[hst].remove(kpi)
                            del(self.widget.ndata[hst][kpi])
            else:
                self.widget.nkpis[host].remove(kpi) # kpis is a list
                if kpi in self.widget.ndata[host]:
                    #might be empty for alt-added
                    del(self.widget.ndata[host][kpi]) # ndata is a dict
            
            self.widget.update()
        else:
            fromto = {'from': self.fromEdit.text(), 'to': self.toEdit.text()}
            
            if modifiers == Qt.ControlModifier:
                kpis = {}
                if host_d['port'] == '':
                    
                    for hst in range(0, len(self.widget.hosts)):
                        kpis[hst] = self.widget.nkpis[hst].copy() #otherwise it might be empty --> key error later in get_data
                        
                        if self.widget.hosts[hst]['port'] == '' and kpi not in self.widget.nkpis[hst]:
                            #self.widget.nkpis[hst].append(kpi)
                            kpis[hst] = self.widget.nkpis[hst] + [kpi]
                else:
                    log('adding kpi: %s' % (kpi))
                    log('hosts: %s' % (str(self.widget.hosts)))
                    for hst in range(0, len(self.widget.hosts)):
                        kpis[hst] = self.widget.nkpis[hst].copy() #otherwise it might be empty --> key error later in get_data

                        if self.widget.hosts[hst]['port'] != '' and kpi not in self.widget.nkpis[hst]:
                            #self.widget.nkpis[hst].append(kpi)
                            kpis[hst] = self.widget.nkpis[hst] + [kpi]
            else:
                #self.widget.nkpis[host].append(kpi)
                kpis = self.widget.nkpis[host] + [kpi]
                
            if modifiers == Qt.AltModifier:
                #pass
                self.widget.nkpis[host] = kpis
            else:
                if modifiers == Qt.ControlModifier:
                    self.statusMessage('Request all/%s...' % (kpi), True)
                    t0 = time.time()

                    while allOk is None:
                        try:
                            t0 = time.time()
                            for hst in range(0, len(self.widget.hosts)):
                                t1 = time.time()
                                if (host_d['port'] == '' and self.widget.hosts[hst]['port'] == '') or (host_d['port'] != '' and self.widget.hosts[hst]['port'] != ''):
                                    # self.dp.getData(self.widget.hosts[hst], fromto, self.widget.nkpis[hst], self.widget.ndata[hst])
                                    self.dp.getData(self.widget.hosts[hst], fromto, kpis[hst], self.widget.ndata[hst])
                                    self.widget.nkpis[hst] = kpis[hst]
                                    
                                    t2 = time.time()
                                    self.statusMessage('%s:%s %s added, %s s' % (self.widget.hosts[hst]['host'], self.widget.hosts[hst]['port'], kpi, str(round(t2-t0, 3))), True)
                                    
                            self.statusMessage('All hosts %s added, %s s' % (kpi, str(round(t2-t0, 3))))
                            allOk = True
                        except utils.dbException as e:
                            log('[!] getData: %s' % str(e))
                            reconnected = self.connectionLost(str(e))
                            
                            if reconnected == False:
                                allOk = False
                        
                else:
                    for hst in range(0, len(self.widget.hosts)):
                        if hst == host:
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
        #print('also stop keep alive timer here')
        #print('it will be kinda refreshed in get_data renewKeepAlive')
        
        log('trigger auto refresh...')
        self.reloadChart()
        self.timer.start(1000 * self.refreshTime)
        
    
    def refreshChanged(self, i):

        txtValue = self.refreshCB.currentText()
        
        if self.timer is not None:
            self.refreshTime = 0
            self.timer.stop()
            self.timer = None

        if txtValue == 'none':
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
            self.timer = QTimer(self.window())
            self.timer.timeout.connect(self.refreshTimer)
            self.timer.start(1000 * self.refreshTime)
        
        
    def scaleChanged(self, i):

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
        self.widget.resizeWidget()
        
        self.widget.update()
        
        
    def renewMaxValues(self):
        '''
            scans max value and last value for kpi
            
            all hosts all kpis from self.ndata[*].keys() list (all enabled kpis)
            
            creates/fills self.scalesN[h] array
            defines max and last_value keys
            
            this one ignores groups/scales at all, just raw values
        '''
    
        log('  renewMaxValues()')
        
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
                    
                timeKey = kpiDescriptions.getTimeKey(type, kpi)
                
                array_size = len(self.widget.ndata[h][timeKey])
                scales[timeKey] = {'min': data[timeKey][0], 'max': data[timeKey][array_size-1]}

                #log('  scan %i -> %s' % (h, kpi))
                #log('  timekey: ' + timeKey)
                #log('  array size: %i' % (array_size))

                try:
                    for i in range(0, array_size):
                        t = data[timeKey][i]
                        if t >= t_from:
                    
                            if scales[kpi]['max'] < data[kpi][i]:
                                scales[kpi]['max'] = data[kpi][i]

                        if  t > t_to: #end of window no need to scan further
                            break
                except Exception as e:
                    log('error: i = %i, array_size = %i' % (i, array_size))
                    log('timeKey = %s, kpi: = %s' % (timeKey, kpi))
                    log('scales[kpi][max] = %i' % (scales[kpi]['max']))
                    
                    log('scales[kpi] = %s' % str(scales[kpi]))

                    log('exception text: %s' % (str(e)))
                    
                    for j in range(10):
                        log('data[%i] = %s' % (j, str(data[kpi][j])))
                        
                    for j in range(1, 10):
                        k = array_size - (10 - j)
                        log('data[%s][%i] = %s' % (kpi, k, str(data[kpi][k])))
                        log('data[%s][%i] = %s' % (timeKey, k, str(data[timeKey][k])))
                        
                    raise e
                        
                scales[kpi]['last_value'] = data[kpi][i]
        
        t1 = time.time()
        
        self.widget.alignScales()
        self.scalesUpdated.emit()

    def reloadChart(self):
        self.statusMessage('Reload...')
        self.repaint()
        
        timer = None
        
        if self.timer is not None:
            timer = True
            self.timer.stop()
        
        t0 = time.time()
        log('  reloadChart()')
        
        #time.sleep(2)
        fromTime = self.fromEdit.text()
        toTime = self.toEdit.text()
        
        if fromTime[:1] == '-' and toTime == '':
            hours = int(fromTime[1:])
            starttime = datetime.datetime.now() - datetime.timedelta(seconds= hours*3600)
            starttime -= datetime.timedelta(seconds= starttime.timestamp() % 3600)
            self.widget.t_from = starttime
        else:
            try:
                self.widget.t_from = datetime.datetime.strptime(fromTime, '%Y-%m-%d %H:%M:%S')
                self.fromEdit.setStyleSheet("color: black;")
                self.setFocus()
            except:
                self.fromEdit.setStyleSheet("color: red;")
                self.statusMessage('datetime syntax error')
                return
            
        if toTime == '':
            self.widget.t_to = datetime.datetime.now() + datetime.timedelta(seconds= self.widget.timeZoneDelta)
        else:
            try:
                self.widget.t_to = datetime.datetime.strptime(toTime, '%Y-%m-%d %H:%M:%S')
                self.toEdit.setStyleSheet("color: black;")
            except:
                self.statusMessage('datetime syntax error')
                return
              
        fromto = {'from': self.fromEdit.text(), 'to': self.toEdit.text()}
        
        allOk = None
        while allOk is None:
            try:
                for host in range(0, len(self.widget.hosts)):
                    if len(self.widget.nkpis[host]) > 0:
                        self.dp.getData(self.widget.hosts[host], fromto, self.widget.nkpis[host], self.widget.ndata[host])
                allOk = True
            except utils.dbException as e:
                reconnected = self.connectionLost(str(e))
                
                if reconnected == False:
                    allOk = False

        self.renewMaxValues()
        
        # I wander what this logic used to do...
        '''
        #if self.connection:
        #if len(self.widget.data): # because we also trigger reload before the data come (somewhere)...
        if len(self.widget.ndata): # because we also trigger reload before the data come (somewhere)...
            #mintime = utils.strftime(datetime.datetime.fromtimestamp(self.widget.scales['time']['min']))
            #maxtime = utils.strftime(datetime.datetime.fromtimestamp(self.widget.scales['time']['max']))
            
            #log('data time min/max: %s %s' % (mintime, maxtime))
            log('not really sure why we check ndata emptiness...')
            pass
        else:
            log('why oh why...')
            return
        '''
        
        # self.scalesUpdated.emit() <-- there's a call now inside the renewMaxValues()
        
        self.widget.resizeWidget()
        
        if toTime == '': # probably we want to see the most recent data...
            self.scrollarea.horizontalScrollBar().setValue(self.widget.width() - self.width() + 22) # this includes scrollArea margins etc, so hardcoded...
            
        self.widget.update()
        
        
        t1 = time.time()
        self.statusMessage('Reload finish, %s s' % (str(round(t1-t0, 3))))
        
        if timer:
            self.timer.start(1000 * self.refreshTime)

    def __init__(self):
        
        '''
            create top controls like from... to... reload, etc
            
            all this crap to be moved some place else one day...
        '''
        
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
        
        self.scaleCB.addItem('10 seconds')
        self.scaleCB.addItem('1 minute')
        self.scaleCB.addItem('5 minutes')
        self.scaleCB.addItem('10 minutes')
        self.scaleCB.addItem('15 minutes')
        self.scaleCB.addItem('1 hour')
        self.scaleCB.addItem('4 hours')
        
        self.scaleCB.setFocusPolicy(Qt.ClickFocus)
        
        self.scaleCB.setCurrentIndex(3)
        
        self.scaleCB.currentIndexChanged.connect(self.scaleChanged)
        
        if cfg('experimental'):
            self.refreshCB = QComboBox()
            
            self.refreshCB.addItem('none')
            
            if cfg('experimental'):
                self.refreshCB.addItem('10 seconds')
                self.refreshCB.addItem('30 seconds')
                
            self.refreshCB.addItem('1 minute')
            self.refreshCB.addItem('5 minutes')
            self.refreshCB.addItem('15 minutes')
            self.refreshCB.addItem('30 minutes')
            
            self.refreshCB.setFocusPolicy(Qt.ClickFocus)
            
            self.refreshCB.currentIndexChanged.connect(self.refreshChanged)

        fromLabel = QLabel('from:')
        toLabel = QLabel('to:')

        starttime = datetime.datetime.now() - datetime.timedelta(seconds= 12*3600)
        starttime -= datetime.timedelta(seconds= starttime.timestamp() % 3600)
                
        self.fromEdit = QLineEdit(starttime.strftime('%Y-%m-%d %H:%M:%S'))

        font = self.fromEdit.font()
        fm = QFontMetrics(font)
        fromtoWidth = fm.width(' 2019-06-17 22:59:00 ') #have no idea why spaces required...
        # fromtoWidth = fm.width(starttime.strftime('%Y-%m-%d %H:%M:%S'))
        
        log('fromtoWidth: %i' % (fromtoWidth))
        
        self.fromEdit.setFixedWidth(fromtoWidth);
        
        self.toEdit = QLineEdit()
        self.toEdit.setFixedWidth(fromtoWidth);
        
        #fromEdit.setFont(QFont('SansSerif', 8))
        
        reloadBtn = QPushButton("rld")
        reloadBtn.setFixedWidth(32);
        reloadBtn.clicked.connect(self.reloadChart)
        
        self.fromEdit.returnPressed.connect(self.reloadChart)
        self.toEdit.returnPressed.connect(self.reloadChart)
        
        hbar.addWidget(self.scaleCB)
        hbar.addStretch(10)
        
        if cfg('experimental'):
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
        self.scrollarea.setWidgetResizable(False)

        lo.addLayout(hbar)
        lo.addWidget(self.scrollarea)
        
        self.widget = myWidget()
        
        #log(type(self.dp))
        #log(type(self.dp).__name__)
        
        if hasattr(self.dp, 'dbProperties'):
            self.widget.timeZoneDelta = self.dp.dbProperties['timeZoneDelta']
        
        # register widget --> chartArea signals
        self.widget.updateFromTime.connect(self.updateFromTime)
        self.widget.updateToTime.connect(self.updateToTime)
        
        # trigger upddate of scales in table?
        
        # dummy size calculation
        # those values to be moved somewhere
        # with the init as well
        
        #self.widget.t_scale = 60*60

        self.reloadChart()
        self.widget.resizeWidget()
        
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