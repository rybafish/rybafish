from PyQt5.QtWidgets import (QWidget, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QCheckBox, QMenu, QAbstractItemView)
    
from PyQt5.QtGui import QFont
    
from PyQt5.QtCore import Qt

from PyQt5.QtCore import pyqtSignal

from utils import log

class hostsTable(QTableWidget):

    hosts = [] # pointer (?) to chartArea.widget.hosts, updated by... import?
    
    hostChanged = pyqtSignal([int])

    def __init__(self):
        super().__init__()
        self.initTable()

    def cellChanged(self, nrow, ncol, prow, pcol):

        #self.setVisible(False)
        #log('new row is %i' % (nrow))
        self.hostChanged.emit(nrow)
    
    def hostsUpdated(self):
        '''
            Fills the hosts table based on self.hosts variable
            (which is link to chartArea.widget.hosts
            
            currently without cleaning, so to be called for empty table right after connection
        '''
        log('signal hostsUpdated(): %i' % (len(self.hosts)))
        self.setRowCount(len(self.hosts))
        
        i = 0
        
        for host in self.hosts:
        
            log(f'hostsUpdated: {host}', 5)
        
            self.setRowHeight(i, 10)
            
            self.setItem(i, 2, QTableWidgetItem(host['host']))
            self.setItem(i, 3, QTableWidgetItem(host['port']))
            
            if 'db' in host:
                self.setItem(i, 1, QTableWidgetItem(host['db']))
            else:
                self.setItem(i, 1, QTableWidgetItem(''))
                
            if 'service' in host:
                self.setItem(i, 4, QTableWidgetItem(host['service']))
            else:
                self.setItem(i, 4, QTableWidgetItem(''))

            if 'from' in host:
                if self.columnCount() == 5:
                    self.setColumnCount(7)
                    self.setHorizontalHeaderLabels(['', 'DB', 'host', 'port', 'service', 'from', 'to'])
                
                self.setItem(i, 5, QTableWidgetItem(host['from'].strftime('%Y-%m-%d %H:%M:%S')))
                self.setItem(i, 6, QTableWidgetItem(host['to'].strftime('%Y-%m-%d %H:%M:%S')))
                    

            if 'from' not in host:
                if self.columnCount() == 7:
                    self.setColumnCount(5)

            i+=1
            
        self.resizeColumnsToContents();

        # change of the host to first one with following implicit call of refill(0)
        self.setCurrentCell(0, 0)
        
            
    def initTable(self):

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.currentCellChanged.connect(self.cellChanged) # not sure why overload doesnt work
        
        #self.horizontalHeader().setStyleSheet("background-color: red");
        #self.horizontalHeader().setBackground('red');
        
        self.setWordWrap(False)
        
        self.setRowCount(1)
        self.setRowHeight(0, 10)
        
        #self.setColumnCount(7)
        self.setColumnCount(5)

        self.horizontalHeader().setFont(QFont('SansSerif', 8))
        self.setFont(QFont('SansSerif', 8))
        
        self.verticalHeader().setVisible(False)
        
        #self.setHorizontalHeaderLabels(['', 'DB', 'host', 'service', 'port', 'from', 'to'])
        self.setHorizontalHeaderLabels(['', 'DB', 'host', 'port', 'service'])
        
        self.horizontalHeader().setMinimumSectionSize(8)
        
        self.setColumnWidth(0, 1)  # checkbox
        self.setColumnWidth(1, 30) # DB
        self.setColumnWidth(2, 80) # host
        self.setColumnWidth(3, 40) # port
        self.setColumnWidth(4, 60) # Service
        #self.setColumnWidth(5, 120) # from
        #self.setColumnWidth(6, 120) # to
