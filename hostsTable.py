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

            self.setRowHeight(i, 10)
            
            self.setItem(i, 1, QTableWidgetItem(host['host']))
            self.setItem(i, 2, QTableWidgetItem(host['port']))
            self.setItem(i, 3, QTableWidgetItem(host['from'].strftime('%Y-%m-%d %H:%M:%S')))
            self.setItem(i, 4, QTableWidgetItem(host['to'].strftime('%Y-%m-%d %H:%M:%S')))
            
            i+=1
            
        self.hostChanged.emit(0) # does work
            
    def initTable(self):

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.currentCellChanged.connect(self.cellChanged) # not sure why overload doesnt work
        
        #self.horizontalHeader().setStyleSheet("background-color: red");
        #self.horizontalHeader().setBackground('red');
        
        self.setWordWrap(False)
        
        self.setRowCount(1)
        self.setRowHeight(0, 10)
        
        self.setColumnCount(5)

        self.horizontalHeader().setFont(QFont('SansSerif', 8))
        self.setFont(QFont('SansSerif', 8))
        
        self.verticalHeader().setVisible(False)
        
        self.setHorizontalHeaderLabels(['', 'host', 'port', 'from', 'to'])
        
        self.horizontalHeader().setMinimumSectionSize(8)
        
        self.setColumnWidth(0, 1)  # checkbox
        self.setColumnWidth(1, 80) # host
        self.setColumnWidth(2, 40) # port
        self.setColumnWidth(3, 120) # from
        self.setColumnWidth(4, 120) # to
