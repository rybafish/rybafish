import sys

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, 
                             QTableWidget, QTableWidgetItem, QCheckBox, QMenu, QAbstractItemView, QItemDelegate, QColorDialog, QApplication, QLabel)
    
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPen, QPainter, QFontMetrics

from PyQt5.QtCore import pyqtSignal

import kpiDescriptions

from utils import log, deb
from utils import cfg
from utils import vrsException

import time

class myCheckBox(QCheckBox):
    def __init__(self, host, name):
        super().__init__()
        self.host = host
        self.name = name

'''
class vrsItem(QTableWidgetItem):
    def __init__(self, txt):
        
        super().__init__(txt)
'''
        

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
        
        self.multicolor = False
        
        if brush:
            self.brushStyle = QBrush(brush)
            
        self.style = style

    def paintEvent(self, QPaintEvent):
        
        qp = QPainter()
        
        #super().paintEvent(QPaintEvent)
        
        qp.begin(self)
        
        if self.penStyle is None:
            qp.end()
            return
            
        qp.setPen(self.penStyle)
        
        if self.style == 'bar':
            qp.setBrush(self.brushStyle) # bar fill color
            h = int(8/2)
            qp.drawRect(4, int(self.size().height()/2 - h/2), self.width() - 8, h )
        elif self.style == 'candle depricated': # depricated 2022-09-23
            qp.drawLine(4, self.size().height() / 2 + 2 , self.width() - 4, self.size().height()  / 2 - 2)
            qp.drawLine(4, self.size().height() / 2 + 3 , 4 , self.size().height()  / 2)
            qp.drawLine(self.width() - 4, self.size().height() / 2, self.width() - 4, self.size().height()  / 2 - 3)
        elif self.style == 'multiline':
            '''
            qp.drawLine(4, self.size().height() / 2 - 3, self.width() - 4, self.size().height()  / 2 - 3)
            qp.drawLine(4, self.size().height() / 2, self.width() - 4, self.size().height()  / 2)
            qp.drawLine(4, self.size().height() / 2 + 3, self.width() - 4, self.size().height()  / 2 + 3)
            '''
            #qp.setPen(QPen(QColor('#48f'), 1, Qt.SolidLine))
            
            if self.multicolor:
                kpiDescriptions.resetRaduga()
                pen = kpiDescriptions.getRadugaPen()
                qp.setPen(pen)
                
            qp.drawLine(4, int(self.size().height()/2 + 3), self.width() - 4, int(self.size().height()/2) + 3)

            if self.multicolor:
                pen = kpiDescriptions.getRadugaPen()
                qp.setPen(pen)
            
            qp.drawLine(4, int(self.size().height()/2), self.width() - 4, int(self.size().height()/2))

            if self.multicolor:
                pen = kpiDescriptions.getRadugaPen()
                qp.setPen(pen)
                
                kpiDescriptions.resetRaduga()
            
            qp.drawLine(4, int(self.size().height()/2) - 3, self.width() - 4, int(self.size().height()/2) - 3)
            
        else:
            qp.drawLine(4, int(self.size().height()/2), self.width() - 4, int(self.size().height()/2))
            
        qp.end()

class kpiTable(QTableWidget):

    # so not sure why signals have to be declared here instead of 
    # __init__ (does not work from there)
    checkboxToggle = pyqtSignal([int,'QString'])

    adjustScale = pyqtSignal(['QString', 'QString'])
    
    # setScale = pyqtSignal([int, 'QString', int, int])
    setScale = pyqtSignal([int, 'QString', object, object]) # details in issue #715
    
    vrsUpdate = pyqtSignal()
    refreshRequest = pyqtSignal()

    def __init__(self):

        self.silentMode = True
        self.kpiNames = [] # list of current kpis for RMC and variables dialog
        
        self.host = None # current host 
        
        self.kpiScales = {} # link to chartArea.widget.scales, updated solely by chartArea.widget.alignScales

        self._hostKPIs = [] # link to chartArea list of available host KPIs
        self._srvcKPIs = [] # link to chartArea list of available service KPIs
        
        # those two gonna be per host, new style #739
        self.hostKPIsList = []          # link to the list of KPIs  (chartArea)
        self.hostKPIsStyles =  []       # link to KPI styles (chartArea)
        
        self.rowKpi = [] #list of current kpis
        
        self.vrsLock = False # suppress variables signal on cell update

        self.filter = ''
        
        super().__init__()

        self.filterWidget = QLabel(' Filter: hey')
        self.filterWidget.setParent(self)
        self.filterWidget.setMargin(2)
        self.filterWidget.setStyleSheet("QLabel { background-color : #acf; color :black; }");
        # f = self.filterWidget.font()

        f = self.font()
        # f.setPixelSize(16)
        fm = QFontMetrics(f)
        deb(f'font heifgh: {fm.height()}')

        self.filterWidget.setFont(f)

        self.filterWidget.hide()
        self.filterWidget.move(21+1, 1)
        self.filterWidget.setToolTip('[ESC] to remove the filter')

        self.initTable()
        self.filterResize()
    
    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)

        #if cfg('dev'):
        changeColor = cmenu.addAction('Change KPI Color')
        resetColor = cmenu.addAction('Reset KPI Color to default')
        cmenu.addSeparator()
        resetAll = cmenu.addAction('Reset all colors to defaults')
        
        action = cmenu.exec_(self.mapToGlobal(event.pos()))

        if action == resetAll:
            kpiDescriptions.customColors.clear()

            i = self.currentRow()
            
            cellCheckBox = self.cellWidget(i, 0)
            
            if isinstance(cellCheckBox, myCheckBox):
                self.refill(cellCheckBox.host)
                
            self.refreshRequest.emit()
        
        if action == resetColor:
            i = self.currentRow()
            
            cellCheckBox = self.cellWidget(i, 0)

            if isinstance(cellCheckBox, myCheckBox):
                kpi = cellCheckBox.name
                kpiKey = self.hosts[cellCheckBox.host]['host'] + ':' + self.hosts[cellCheckBox.host]['port'] + '/' + kpi
                
                if kpiKey in kpiDescriptions.customColors:
                    del kpiDescriptions.customColors[kpiKey]
                    
                    self.refill(cellCheckBox.host)
                    
            self.refreshRequest.emit()
        
        if action == changeColor:
            i = self.currentRow()
            
            cellCheckBox = self.cellWidget(i, 0)
            
            if isinstance(cellCheckBox, myCheckBox):
                kpi = cellCheckBox.name
                kpiStyles = self.hostKPIsStyles[cellCheckBox.host]
                
                kpiKey = self.hosts[cellCheckBox.host]['host'] + ':' + self.hosts[cellCheckBox.host]['port'] + '/' + kpi
                
                if 'brush' in kpiStyles[kpi]:
                    # gantt chart have brush color, and pen is derivative
                    pen = kpiDescriptions.customPen(kpiKey, kpiStyles[kpi]['pen'])
                    initColor = pen.color()
                else:
                    pen = kpiDescriptions.customPen(kpiKey, kpiStyles[kpi]['pen'])
                    initColor = pen.color()
                    
                if initColor is None:
                    log('Cannot identify KPI pen color', 2)
                    return
                
                targetColor = QColorDialog().getColor(initial=initColor, parent=self)
                
                if targetColor.isValid():
                    if targetColor == initColor:
                        pass
                    else:
                        styleKey = self.hosts[cellCheckBox.host]['host'] + ':' + self.hosts[cellCheckBox.host]['port'] + '/' + kpi
                        kpiDescriptions.addCustomColor(styleKey, targetColor)
                        
                        self.refill(cellCheckBox.host)
                else:
                    pass
                
            else:
                log('Cannot identify KPI host/name', 2)
        
    def edit(self, index, trigger, event):

        if index.column() not in (3, 11):
            # Not Y-Scale
            # and not Variables
            return False
            
        result = super(kpiTable, self).edit(index, trigger, event)

        if result and index.column() == 11:
            # variables
            #return super(kpiTable, self).edit(index, trigger, event)
            self.silentMode = True

            log(f'edit self.host: {self.host}')

            kpiName = self.kpiNames[index.row()]
                    
            kpiStyles = self.hostKPIsStyles[self.host]
                
            style = kpiStyles[kpiName]
            
            idx = style['sql']

            if kpiDescriptions.vrsStrErr.get(idx):
                label = '[!!!] ' + kpiDescriptions.vrsStr.get(idx, ' ?')
            else:
                label = kpiDescriptions.vrsStr.get(idx)

            self.item(index.row(), 11).setText(label)
            
            self.silentMode = False
        
        if result and index.column() == 3: # manual scale
            self.silentMode = True
            
            kpi = self.kpiNames[index.row()]
            
            if kpi not in self.kpiScales[self.host]:
                return False
            
            scale = self.kpiScales[self.host][kpi]
            
            scaleValue = scale['yScale']
            scaleValueLow = scale.get('yScaleLow')
            
            if scaleValueLow and scale.get('manual'):
                label = '%i-%i' % (scaleValueLow, scaleValue)
            else:
                label = str(scaleValue)
                
            self.item(index.row(), 3).setText(label)
            
            self.silentMode = False
            
        return result
        
    def itemChange(self, item):
        '''
            manual scale enter
            
            need to check if correct column changed, btw
        '''
        
        if self.silentMode:
            return

        if item.column() == 3:  # scale change
        
            try:
                s = item.text()
                
                if s.find('-') > 0:
                    yMin = int(s[:s.find('-')].strip())
                    yMax = int(s[s.find('-')+1:].strip())
                else:
                    yMin = 0
                    yMax = int(item.text())
            except:
                log('Not an integer value: %s, removing the manual scale' % (item.text()))
                self.setScale.emit(self.host, self.kpiNames[item.row()], -1, -1)
                return

            self.setScale.emit(self.host, self.kpiNames[item.row()], yMin, yMax)
        
        elif item.column() == 11:
            log('okay, variables updated: %s' % (item.text()), 4)
            
            kpiName = self.kpiNames[item.row()]
            style = self.hostKPIsStyles[self.host][kpiName]
            
            if 'sql' in style:
                idx = style['sql']
            else:
                log('Not a custom KPI? %s' % (kpiName), 2)
                return
                
            item_text = item.text()
            
            if item_text.strip() == '':
            
                if idx in kpiDescriptions.vrsStrDef:
                    item_text = kpiDescriptions.vrsStrDef[idx]
                else:
                    item_text = ''

                log('[variables] Resetting to default definition from cached stuff', 4)
                log(f'[variables] which is: {item_text}', 4)
                    
                # item.setText(item_text) #833, it is called imlicitly

            if not self.vrsLock:
                log('-----addVars kpiTable ----->', 4)
            
                try:
                    kpiDescriptions.addVars(idx, item_text, True)
                except vrsException as ex:
                    self.vrsLock = True
                    item.setText(str(ex))
                    self.vrsLock = False
                
                log('<-----addVars kpiTable -----', 4)
                
            log('item change refill', 5)
            self.refill(self.host)
            
            self.vrsUpdate.emit()
        
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
            host - host structure 
            
            popupates KPIs table
            to be connected to hostChanged signal (hostsTable)
        '''
        
        log(f'refill: {str(host)}, filter: {self.filter}', 5)
        if host == -1:
            log('[W] KPIs refill aborted to avoid confusion', 2)
            log('[W] setting self.host = None', 2)
            self.host = None
            self.setRowCount(0)
            return
        
        if len(self.hosts) == 0:
            return

        if len(self.nkpis) == 0:
            log('[w] refill kips list is empty, return')
            return
        
        self.silentMode = True
        
        self.host = host
        log(f'refill self.host: {self.host}', 5)
                        
        kpiList = self.hostKPIsList[host]
        kpiStyles = self.hostKPIsStyles[host]
        
        hostKey = self.hosts[host]['host'] + ':' + self.hosts[host]['port']
            
        # go fill the table
        # self.setRowCount(len(kpiList))

        kpis = [] # list of kpi tuples in kpiDescription format (ones to be displayed depending on host/service + checkboxes
        
        #put enabled ones first:
        for kpin in self.nkpis[host]:
            kpis.append(kpin)
            
        #log(f'{kpiList=}')
        #populate rest of KPIs (including groups):


        grp = False              # pass through group

        for kpi in kpiList:
                if kpi not in kpis:

                    style = kpiStyles.get(kpi)
                    if style:
                        pass
                        # print(f"{style['label']}, {self.filter}")
                        # print(style['label'].find(self.filter))

                    else:
                        if grp and kpi[0] == '.': # new group started, clear
                            grp = False

                    if not self.filter:
                        kpis.append(kpi)
                    elif (style and style['label'].lower().find(self.filter.lower()) != -1) or grp or not style:
                        # print(f'add kpi: {style}/{self.filter}')
                        kpis.append(kpi)

                    if not style and self.filter and kpi.lower().find(self.filter.lower()) != -1:
                        if kpi[0] == '.':
                            grp = True # group name matches the filter - enable pass through until next group


        # print('list of kpis before cleanup:')
        # print(kpis)

        kpis_new = []
        kpilen = len(kpis)

        for i in range(kpilen):
            kpi = kpis[i]
            if kpi[0] == '.':
                if i < kpilen-1 and kpis[i+1][0] == '.': # next one is also a group, skip
                    # print(f'skip: {kpi}')
                    continue
            # print(f'append: {kpi}')

            if i == kpilen-1 and kpi[0] == '.': # the last kpi is group (and it is empy)
                continue

            kpis_new.append(kpi)


        kpis = kpis_new
        
        # print('list of kpis after cleanup:')
        # print(kpis)

        self.setRowCount(len(kpis))

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
            
            kpiKey = f'{hostKey}/{kpiName}'
            
            if kpiName[:1] != '.':
                #normal kpis
                
                #log('myCheckBox, %s.%s' % (str(host), kpiName), 5)
                cb = myCheckBox(host, kpiName)
                # cb.setStyleSheet("QCheckBox::indicator { width: 10px; height: 10px; margin-left:16px;}")
                cb.setStyleSheet("QCheckBox::indicator { width: 10px; height: 10px; margin-left: 10px;}")

                if kpiName in self.nkpis[host]:
                    cb.setChecked(True)

                '''
                if kpiName not in kpiStyles:
                    # it can disappear as a result of custom KPI reload
                    log('%s not in the list of KPI styles, removing' % (kpiName))
                    continue 
                '''
                
                #log(f'{kpiName=}, {type(kpiStyles)}')
                if kpiName not in kpiStyles:
                    log('[!] kpiTable refill: kpi is missing, %s' % kpiName, 2)
                    continue
                    
                style = kpiStyles[kpiName]
                
                cb.stateChanged.connect(self.checkBoxChanged)
                self.setCellWidget(i, 0, cb)
                
                if 'style' in style:

                    if kpiKey in kpiDescriptions.customColors:
                        c = kpiDescriptions.customColors[kpiKey]
                        pen = QPen(QColor(int(c[0]*0.75), int(c[1]*0.75), int(c[2]*0.75)))
                        brshColor = QColor(c[0], c[1], c[2])

                    else:
                        pen = style['pen']
                        brshColor = style['brush']
                
                    #cell = kpiCell(style['pen'], style['brush'], style['style']) # customized styles
                    cell = kpiCell(pen, brshColor, style['style']) # customized styles

                    if 'multicolor' in style :
                        cell.multicolor = style['multicolor']

                    self.setCellWidget(i, 2, cell) 
                else:
                    pen = kpiDescriptions.customPen(kpiKey, style['pen'])
                    '''
                    if kpiKey in kpiDescriptions.customColors:
                        c = kpiDescriptions.customColors[kpiKey]
                        pen = QPen(QColor(c[0], c[1], c[2]))
                        print(f'kpiKey --> {c}')
                    else:
                        pen = style['pen']
                    '''

                    self.setCellWidget(i, 2, kpiCell(pen, )) # kpi pen style

                # variables/placeholders mapping
                
                if style.get('sql'):
                    # sql exists and not None
                    
                    #idx = style['sql']
                    desc = style['desc'] #kpiDescriptions.processVars(idx, style['desc'])
                    label = style['label'] # '123' #kpiDescriptions.processVars(idx, style['label'])
                else:
                    desc = style['desc']
                    label = style['label']
                    
                if 'disabled' in style.keys():
                    item = QTableWidgetItem(label)
                    item.setForeground(QBrush(QColor(255, 0, 0)))
                    self.setItem(i, 1, item) # text name
                else:
                    self.setItem(i, 1, QTableWidgetItem(label)) # text name
                
                self.setItem(i, 9, QTableWidgetItem(desc)) # descr
                
                grp = str(style['group'])
                
                if grp == '0':
                    grp = ''
                
                self.setItem(i, 10, QTableWidgetItem(grp)) # group

                if 'sql' in style and style['sql'] in kpiDescriptions.vrsStr:
                    if not self.vrsLock:
                        vrs = kpiDescriptions.vrsStr[style['sql']]
                        
                        # if vrs is not None:
                        
                        if kpiDescriptions.vrsStrErr.get(style['sql']):
                            vrs = kpiDescriptions.vrsStrErr.get(style['sql'])
                    
                        self.setItem(i, 11, QTableWidgetItem(vrs))
                        #self.setItem(i, 11, vrsItem(vrs))
                        
                else:
                    self.setItem(i, 11, QTableWidgetItem()) # no variables
                
            else:
                # kpi groups
                
                self.setCellWidget(i, 0, None) # no checkbox
                self.setCellWidget(i, 2, None) # no pen style
                self.setItem(i, 1, QTableWidgetItem(kpiName[1:])) # text name
                self.item(i, 1).setFont(QFont('SansSerif', 8, QFont.Bold))
                
                self.setItem(i, 9, QTableWidgetItem()) # no desc
                self.setItem(i, 10, QTableWidgetItem()) # no group
                self.setItem(i, 11, QTableWidgetItem()) # no variables

            if kpiName in self.kpiScales[self.host].keys():
                
                kpiScale = self.kpiScales[self.host][kpiName]
                
                scaleItem = QTableWidgetItem(str(kpiScale['label']))
                
                if kpiScale.get('manual'):
                    scaleItem.setForeground(QBrush(QColor(0, 0, 255)))
                    
                scaleItem.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)

                self.setItem(i, 3, QTableWidgetItem(scaleItem)) # Y-Scale
                
                # Unit
                item = QTableWidgetItem(str(kpiScale['unit']))
                item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                self.setItem(i, 4, item)

                # MAX value
                item = QTableWidgetItem(str(kpiScale['max_label']))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(i, 5, item)
                
                # AVG value
                item = QTableWidgetItem(str(kpiScale['avg_label']))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(i, 6, item)

                # Last value
                item = QTableWidgetItem(str(kpiScale['last_label']))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(i, 8, item)
            else:
                #cleanup 
                self.setItem(i, 3, QTableWidgetItem())
                self.setItem(i, 4, QTableWidgetItem())
                self.setItem(i, 5, QTableWidgetItem())
                self.setItem(i, 6, QTableWidgetItem())
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
        log(f'updateScales host: {self.host}')
        
        if self.host is None:
            log('update scales? why oh why...', 5)
            return
            
        log('kpiTable: updateScales() host: %i' % (self.host), 4)
        
        self.silentMode = True
   
        log('kpiScales: %s' % (str(self.kpiScales[self.host])), 5)
        kpis = len(self.kpiScales[self.host])
        
        #check if stuff to be disabled here...
                
        for i in range(0, len(self.kpiNames)):
            
            if self.kpiNames[i] in self.kpiScales[self.host].keys():
                
                kpiScale = self.kpiScales[self.host][self.kpiNames[i]]
                
                if self.kpiNames[i] not in self.hostKPIsStyles[self.host]: 
                    log('[!] kpiTable, kpi does not exist: %s' % self.kpiNames[i])
                    continue

                style = self.hostKPIsStyles[self.host][self.kpiNames[i]]
                
                if style.get('sql'):
                    # sql exists and not None
                    
                    idx = style['sql']
                    #desc = kpiDescriptions.processVars(idx, style['desc'])
                    label = style['label'] # kpiDescriptions.processVars(idx, style['label'])
                else:
                    #desc = style['desc']
                    label = style['label']
                    
                if 'disabled' in style.keys():
                    log('style is disabled: %s' % str(style['name']))
                    item = QTableWidgetItem(label)
                    item.setForeground(QBrush(QColor(255, 0, 0)))
                    self.setItem(i, 1, item) # text name
                else:
                    self.setItem(i, 1, QTableWidgetItem(label))

                scaleItem = QTableWidgetItem(str(kpiScale['label']))
                
                if kpiScale.get('manual'):
                    scaleItem.setForeground(QBrush(QColor(0, 0, 255)))
                    
                self.setItem(i, 3, scaleItem) # Y-Scale
                
                self.setItem(i, 4, QTableWidgetItem(str(kpiScale['unit'])))
                self.setItem(i, 5, QTableWidgetItem(str(kpiScale['max_label'])))
                self.setItem(i, 6, QTableWidgetItem(str(kpiScale['avg_label'])))
                self.setItem(i, 8, QTableWidgetItem(str(kpiScale['last_label'])))
        
        self.silentMode = False
        
    def filterResize(self):
        w = self.columnWidth(1) - 1
        # h = self.rowHeight(0)
        h = self.horizontalHeader().height()
        self.filterWidget.resize(w, h)

    def columnResized(self, idx, oldSize, newSize):
        '''protect checkbox column removed from table at all'''

        if idx == 0: # and newSize < 10:
            self.setColumnWidth(0, 21)
        if idx == 1:
            self.filterResize()


    def updateFilter(self):
        '''update filter widget and manage it's visibility based solely on self.filter value'''

        prefix = ' KPI filter: '

        if self.filter:
            self.filterWidget.setText(prefix + self.filter)

            if self.filterWidget.isHidden():
                self.filterWidget.show()

        else:
            if not self.filterWidget.isHidden():
                self.filterWidget.hide()

    def keyPressEvent (self, event):
        #log keypress
        modifiers = QApplication.keyboardModifiers()

        k = event.text()
        kcode = event.key()

        if modifiers & Qt.AltModifier:
            super().keyPressEvent(event)
            return

        if k.isalnum() or k == '_':
            self.filter += k

        elif kcode == Qt.Key_Backspace:
            if len(self.filter) > 0:
                self.filter = self.filter[:-1]

        elif kcode == Qt.Key_Escape:
            self.filter = ''
        else:
            super().keyPressEvent(event)
            return

        self.updateFilter()

        self.refill(self.host)


    def initTable(self):
        self.setColumnCount(12)
        self.SelectionMode(QAbstractItemView.NoSelection) #doesn't work for some reason

        self.horizontalHeader().setFont(QFont('SansSerif', 8))
        self.setFont(QFont('SansSerif', 8))

        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)

        self.setHorizontalHeaderLabels(['', 'KPI', 'Style', 'Y-Scale', 'Unit', 'Max', 'Average', ' ', 'Last', 'Description', 'Group', 'Variables'])
        self.horizontalHeader().setMinimumSectionSize(0)
        
        self.setColumnWidth(0, 21)
        self.setColumnWidth(1, 140) #kpi
        self.setColumnWidth(2, 30) # Style (Pen)
        self.setColumnWidth(3, 70) # y-scale
        self.setColumnWidth(4, 50) # Unit
        self.setColumnWidth(5, 80) # Max 
        self.setColumnWidth(6, 50) # AVG
        self.setColumnWidth(7, 20) # Sum -- remove
        self.setColumnWidth(8, 80) # Last
        self.setColumnWidth(9, 110) # desc
        self.setColumnWidth(10, 40) # group
        self.setColumnWidth(11, 200) # variables
        #self.setColumnWidth(10, 30) # threshold
        
        self.itemChanged.connect(self.itemChange)
        self.horizontalHeader().sectionResized.connect(self.columnResized)
