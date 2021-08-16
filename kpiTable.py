from PyQt5.QtWidgets import (QWidget, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QCheckBox, QMenu, QAbstractItemView)
    
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPen, QPainter

from PyQt5.QtCore import pyqtSignal

import kpiDescriptions
from kpiDescriptions import kpiStylesNN 

from utils import log
from utils import log, cfg

class myCheckBox(QCheckBox):
    def __init__(self, host, name):
        super().__init__()
        self.host = host
        self.name = name

class scaleCell(QWidget):
    # depricated
    name = ''
    def __init__(self, text):
    
        log('scaleCell depricated')
        super().__init__()
        self.name = text
    
class kpiCell(QWidget):
    '''
        draws a cell with defined pen style
    '''
    def __init__(self, pen, brush = None, style = None):
        super().__init__()
        self.penStyle = pen
        
        if brush:
            self.brushStyle = QBrush(brush)
            
        self.style = style

    def paintEvent(self, QPaintEvent):
        
        qp = QPainter()
        
        #super().paintEvent(QPaintEvent)
        
        qp.begin(self)
        qp.setPen(self.penStyle)
        
        if self.style == 'bar':
            qp.setBrush(self.brushStyle) # bar fill color
            h = 8 / 2
            qp.drawRect(4, self.size().height() / 2 - h/2, self.width() - 8, h )
        elif self.style == 'candle':
            qp.drawLine(4, self.size().height() / 2 + 2 , self.width() - 4, self.size().height()  / 2 - 2)
            qp.drawLine(4, self.size().height() / 2 + 3 , 4 , self.size().height()  / 2)
            qp.drawLine(self.width() - 4, self.size().height() / 2, self.width() - 4, self.size().height()  / 2 - 3)
        else:
            qp.drawLine(4, self.size().height() / 2, self.width() - 4, self.size().height()  / 2)
        qp.end()

class kpiTable(QTableWidget):

    # so not sure why signals have to be declared here instead of 
    # __init__ (does not work from there)
    checkboxToggle = pyqtSignal([int,'QString'])

    adjustScale = pyqtSignal(['QString', 'QString'])
    
    setScale = pyqtSignal([int, 'QString', int])

    def __init__(self):

        self.silentMode = True
        self.kpiNames = [] # list of current kpis
        
        self.host = None # current host 
        
        self.kpiScales = {} # pointer (?) to chartArea.widget.scales, updated solely by chartArea.widget.alignScales

        self.hostKPIs = [] # link to chartArea list of available host KPIs
        self.srvcKPIs = [] # link to chartArea list of available service KPIs
        
        self.rowKpi = [] #list of current kpis

        super().__init__()

        self.initTable()
    
    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)

        if cfg('experimental-disabled'):
            increaseScale = cmenu.addAction('Increase')
            decreaseScale = cmenu.addAction('Decrease')
            resetScale = cmenu.addAction('Reset')
        
            action = cmenu.exec_(self.mapToGlobal(event.pos()))

            kpi = self.kpiNames[self.currentRow()]

            if action == increaseScale:
                self.adjustScale.emit('increase', kpi)
                
            if action == decreaseScale:
                self.adjustScale.emit('decrease', kpi)
           
    def edit(self, index, trigger, event):
    
        if index.column() != 3:
            # Not Y-Scale
            return False
            
        result = super(kpiTable, self).edit(index, trigger, event)
        
        if result and index.column() == 3:
            self.silentMode = True
            
            kpi = self.kpiNames[index.row()]
            scale = self.kpiScales[self.host][kpi]
            
            scaleValue = scale['yScale']
            self.item(index.row(), 3).setText(str(scaleValue))
            
            self.silentMode = False
            
        return result
        
    def itemChange(self, item):
        '''
            manual scale enter
            
            need to check if correct column changed, btw
        '''

        if self.silentMode:
            return
        
        try:
            newScale = int(item.text())
        except:
            log('exception, not an integer value: %s' % (item.text()))
            return
        
        #log('kpiScales: %s' % (str(self.kpiScales[self.host])), 5)
        self.setScale.emit(self.host, self.kpiNames[item.row()], newScale)
        
        #self.setFont(QFont('SansSerif', 8, QFont.Bold))
        
    def loadScales(self):
        # for kpi in scales: log(kpi)
        pass
        
    def checkBoxChanged(self, state):
        '''
            enable / disable certain kpi
            connected to a change signal (standard one)
        '''
        
        if state == Qt.Checked:
            txt = 'on'
        else:
            txt = 'off'
            
        self.checkboxToggle.emit(self.sender().host, self.sender().name)
        
    def refill(self, host):
        '''
            popupates KPIs table
            to be connected to hostChanged signal (hostsTable)
        '''
        
        log('refill: %s' % str(host), 5)
        
        if len(self.hosts) == 0:
            return

        if len(self.nkpis) == 0:
            log('[w] refill kips list is empty, return')
            return
        
        self.silentMode = True
        
        self.host = host
        
        #print('replace this by hType?')

        if self.hosts[host]['port'] == '':
            t = 'h'
            usedKPIs = self.hostKPIs
        else:
            t = 's'
            usedKPIs = self.srvcKPIs
            
        if t == 'h':
            kpiStyles = kpiStylesNN['host']
            kpiList = self.hostKPIs
        else:
            kpiStyles = kpiStylesNN['service']
            kpiList = self.srvcKPIs
            
        # go fill the table
        self.setRowCount(len(kpiList))
        
        kpis = [] # list of kpi tuples in kpiDescription format (ones to be displayed depending on host/service + checkboxes
        
        #put enabled ones first:
        for kpin in self.nkpis[host]:
            kpis.append(kpin)

        #populate rest of KPIs (including groups):
        for kpi in kpiList:
                if kpi not in kpis:
                    kpis.append(kpi)

        i = 0
        ####################################################################
        #### ### ##     ## ##### #########   ###     ## ### ## #####     ###
        ####  ## ## ###### ##### ######## ######## ##### # ### ##### #######
        #### # # ##   #### ## ## #########  ###### ###### #### #####   #####
        #### ##  ## ###### # # # ########### ##### ###### #### ##### #######
        #### ### ##     ##  ###  ########   ###### ###### ####    ##     ###
        ####################################################################
        
        self.kpiNames = [] # index for right mouse click events
        
        for kpiName in kpis:
            self.setRowHeight(i, 10)
            
            self.kpiNames.append(kpiName) # index for right mouse click events
            
            if kpiName[:1] != '.':
                #normal kpis
                
                log('myCheckBox, %s.%s' % (str(host), kpiName))
                cb = myCheckBox(host, kpiName)
                cb.setStyleSheet("QCheckBox::indicator { width: 10px; height: 10px; margin-left:16px;}")

                if kpiName in self.nkpis[host]:
                    cb.setChecked(True)

                '''
                if kpiName not in kpiStyles:
                    # it can disappear as a result of custom KPI reload
                    log('%s not in the list of KPI styles, removing' % (kpiName))
                    continue 
                '''
                
                if kpiName not in kpiStyles:
                    log('[!] kpiTable refill: kpi is missing, %s' % kpiName, 2)
                    continue
                    
                style = kpiStyles[kpiName]
                cb.stateChanged.connect(self.checkBoxChanged)
                self.setCellWidget(i, 0, cb)
                
                if 'style' in style:
                    self.setCellWidget(i, 2, kpiCell(style['pen'], style['brush'], style['style'])) # customized styles
                else:
                    self.setCellWidget(i, 2, kpiCell(style['pen'], )) # kpi pen style
                
                if 'disabled' in style.keys():
                    item = QTableWidgetItem(style['label'])
                    item.setForeground(QBrush(QColor(255, 0, 0)))
                    self.setItem(i, 1, item) # text name
                else:
                    self.setItem(i, 1, QTableWidgetItem(style['label'])) # text name
                
                self.setItem(i, 9, QTableWidgetItem(style['desc'])) # descr
                
                grp = str(style['group'])
                
                if grp == '0':
                    grp = ''
                
                self.setItem(i, 10, QTableWidgetItem(grp)) # group
                
            else:
                # kpi groups
                
                self.setCellWidget(i, 0, None) # no checkbox
                self.setCellWidget(i, 2, None) # no pen style
                self.setItem(i, 1, QTableWidgetItem(kpiName[1:])) # text name
                self.item(i, 1).setFont(QFont('SansSerif', 8, QFont.Bold))
                
                self.setItem(i, 9, QTableWidgetItem()) # no desc
                self.setItem(i, 10, QTableWidgetItem()) # no group

            if kpiName in self.kpiScales[self.host].keys():
                
                kpiScale = self.kpiScales[self.host][kpiName]
                
                self.setItem(i, 3, QTableWidgetItem(str(kpiScale['label']))) # Y-Scale
                self.setItem(i, 4, QTableWidgetItem(str(kpiScale['unit'])))
                self.setItem(i, 5, QTableWidgetItem(str(kpiScale['max_label'])))
                self.setItem(i, 8, QTableWidgetItem(str(kpiScale['last_label'])))
            else:
                #cleanup 
                self.setItem(i, 3, QTableWidgetItem())
                self.setItem(i, 4, QTableWidgetItem())
                self.setItem(i, 5, QTableWidgetItem())
                self.setItem(i, 8, QTableWidgetItem())
            
            i+=1
        
        self.silentMode = False
        return
        
    def updateScales(self):
        '''
            this one to fill/update table metrics values
            like max value/last value and also the scales
            
            based on self.kpiScales
            kpiScales calculated OUTSIDE, in chartArea.widget.alignScales()
            
            to be called outside afted alignScales() by a signal
        '''
        if self.host is None:
            log('update scales? why oh why...', 5)
            return
            
        log('kpiTable: updateScales() host: %i' % (self.host), 4)
        
        self.silentMode = True
   
        log('kpiScales: %s' % (str(self.kpiScales[self.host])), 5)
        kpis = len(self.kpiScales[self.host])
        
        #check if stuff to be disabled here...
        
        type = kpiDescriptions.hType(self.host, self.hosts)
        
        for i in range(0, len(self.kpiNames)):
            
            if self.kpiNames[i] in self.kpiScales[self.host].keys():
                
                kpiScale = self.kpiScales[self.host][self.kpiNames[i]]
                
                if self.kpiNames[i] not in kpiStylesNN[type]:
                    log('[!] kpiTable, kpi does not exist: %s' % self.kpiNames[i])
                    continue
                style = kpiStylesNN[type][self.kpiNames[i]]
                
                if 'disabled' in style.keys():
                    log('style is disabled: %s' % str(style['name']))
                    item = QTableWidgetItem(style['label'])
                    item.setForeground(QBrush(QColor(255, 0, 0)))
                    self.setItem(i, 1, item) # text name
                else:
                    self.setItem(i, 1, QTableWidgetItem(style['label']))

                self.setItem(i, 3, QTableWidgetItem(str(kpiScale['label']))) # Y-Scale
                self.setItem(i, 4, QTableWidgetItem(str(kpiScale['unit'])))
                self.setItem(i, 5, QTableWidgetItem(str(kpiScale['max_label'])))
                self.setItem(i, 8, QTableWidgetItem(str(kpiScale['last_label'])))
        
        self.silentMode = False
        
    def initTable(self):
        self.setColumnCount(11)
        self.SelectionMode(QAbstractItemView.NoSelection) #doesn't work for some reason

        self.horizontalHeader().setFont(QFont('SansSerif', 8))
        self.setFont(QFont('SansSerif', 8))

        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)

        self.setHorizontalHeaderLabels(['', 'KPI', 'Style', 'Y-Scale', 'Unit', 'Max', 'Average', 'Sum', 'Last', 'Description', 'Group'])
        
        # self.setHorizontalHeaderLabels(['', 'KPI', 'Style', 'Y-Scale', 'Unit', 'Max', 'Average', 'Sum', 'Last', 'Description', 'mntr'])
        #self.updateScales()
        
        self.setColumnWidth(0, 1)
        self.setColumnWidth(1, 140) #kpi
        self.setColumnWidth(2, 30) # Style (Pen)
        self.setColumnWidth(3, 70) # y-scale
        self.setColumnWidth(4, 50) # Unit
        self.setColumnWidth(5, 80) # Max 
        self.setColumnWidth(6, 50) # AVG
        self.setColumnWidth(7, 20) # Sum
        self.setColumnWidth(8, 80) # Last
        self.setColumnWidth(9, 220) # desc
        self.setColumnWidth(10, 40) # group
        #self.setColumnWidth(10, 30) # threshold
        
        self.itemChanged.connect(self.itemChange)
        
    def initTable_old(self):
        
        kpis = len(self.kpiStyles)

        self.setRowCount(kpis)
        
        for i in range(0, kpis): 
            self.setRowHeight(i, 10)
            
            self.kpiNames.append(self.kpiStyles[i][2])
            
            #dummy check box, as no action assigned
            cb = myCheckBox(self.kpiStyles[i][2])
            cb.setStyleSheet("QCheckBox::indicator { width: 10px; height: 10px; margin-left:16px;}")
            cb.stateChanged.connect(self.checkBoxChanged)
            self.setCellWidget(i, 0, cb)
            
            #meaningful properties
            self.setItem(i, 1, QTableWidgetItem(self.kpiStyles[i][4])) # text name
            self.setCellWidget(i, 2, kpiCell(self.kpiStyles[i][3])) # kpi name
            
            self.setItem(i, 9, QTableWidgetItem(self.kpiStyles[i][6])) # descr
