from PyQt5.QtWidgets import (QWidget, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QCheckBox, QMenu, QAbstractItemView)
    
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPen, QPainter

from PyQt5.QtCore import pyqtSignal

import kpiDescriptions
from kpiDescriptions import kpiStylesNN 

from utils import log
from utils import log, cfg

class myCheckBox(QCheckBox):
    host = ''
    name = ''
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
    def __init__(self, pen):
        super().__init__()
        self.penStyle = pen

    def paintEvent(self, QPaintEvent):
        
        qp = QPainter()
        
        #super().paintEvent(QPaintEvent)
        
        qp.begin(self)
        qp.setPen(self.penStyle)
        qp.drawLine(4, self.size().height() / 2, self.width() - 4, self.size().height()  / 2)
        qp.end()

class kpiTable(QTableWidget):
    kpiStyles = kpiDescriptions.kpiStyles
    
    silentMode = True
    kpiNames = [] # list of current kpis
    
    host = None # current host 
    
    kpiScales = {} # pointer (?) to chartArea.widget.scales, updated solely by chartArea.widget.alignScales

    hostKPIs = [] # link to chartArea list of available host KPIs
    srvcKPIs = [] # link to chartArea list of available service KPIs
    
    rowKpi = [] #list of current kpis
        
    checkboxToggle = pyqtSignal([int,'QString'])
    
    adjustScale = pyqtSignal(['QString', 'QString'])
    
    setScale = pyqtSignal([int, 'QString', int])

    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)

        if cfg('experimental'):
            increaseScale = cmenu.addAction('Increase')
            decreaseScale = cmenu.addAction('Decrease')
            resetScale = cmenu.addAction('Reset')
        
            action = cmenu.exec_(self.mapToGlobal(event.pos()))

            kpi = self.kpiNames[self.currentRow()]

            if action == increaseScale:
                self.adjustScale.emit('increase', kpi)
                
            if action == decreaseScale:
                self.adjustScale.emit('decrease', kpi)
            
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
        
        self.setScale.emit(self.host, self.kpiNames[item.row()], newScale)
        
    def loadScales(self):
        # for kpi in scales: log(kpi)
        pass

    def __init__(self):
        super().__init__()

        self.initTable()
        
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
        
        if len(self.hosts) == 0:
            return
        
        self.silentMode = True
        
        self.host = host
        
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
                
                cb = myCheckBox(host, kpiName)
                cb.setStyleSheet("QCheckBox::indicator { width: 10px; height: 10px; margin-left:16px;}")

                if kpiName in self.nkpis[host]:
                    cb.setChecked(True)

                style = kpiStyles[kpiName]
                cb.stateChanged.connect(self.checkBoxChanged)
                self.setCellWidget(i, 0, cb)
                self.setCellWidget(i, 2, kpiCell(style['pen'])) # kpi pen style
                self.setItem(i, 1, QTableWidgetItem(style['label'])) # text name
                
                self.setItem(i, 9, QTableWidgetItem(style['desc'])) # descr
                self.setItem(i, 10, QTableWidgetItem(style['group'])) # group
            else:
                # kpi groups
                
                self.setCellWidget(i, 0, None) # no checkbox
                self.setCellWidget(i, 2, None) # no pen style
                self.setItem(i, 1, QTableWidgetItem(kpiName[1:])) # text name
                self.item(i, 1).setFont(QFont('SansSerif', 8, QFont.Bold))
                
                self.setItem(i, 9, QTableWidgetItem()) # clean up

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
            log('update scales? why oh why...')
            return
            
        #log('kpiTable: updateScales() host: %i' % (self.host))
        
        self.silentMode = True
        
        #log(self.kpiScales[self.host])
        kpis = len(self.kpiScales[self.host])
        
        for i in range(0, len(self.kpiNames)):
            
            if self.kpiNames[i] in self.kpiScales[self.host].keys():
                
                kpiScale = self.kpiScales[self.host][self.kpiNames[i]]
                
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
        self.setColumnWidth(3, 50) # y-scale
        self.setColumnWidth(4, 20) # Unit
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
