from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFrame, 
    QSplitter, QStyleFactory, QTableWidget,
    QTableWidgetItem, QPushButton, QAbstractItemView,
    QCheckBox, QMainWindow, QAction, QMenu, QFileDialog,
    QMessageBox, QTabWidget, QPlainTextEdit
    )

from PyQt5.QtGui import QPainter, QIcon

from PyQt5.QtCore import Qt

from PyQt5.QtSql import QSqlDatabase, QSqlQuery

from yaml import safe_load, dump, YAMLError #pip install pyyaml

import kpiTable, hostsTable
import chartArea
import configDialog, aboutDialog

import dpDummy
import dpDB
import sqlConsole

from utils import resourcePath

from utils import log
from utils import cfg
from utils import dbException

import sys


import time

class hslWindow(QMainWindow):

    statusbar = None
    connectionConf = None

    def __init__(self):
        super().__init__()
        self.initUI()
        
    def keyPressEvent(self, event):
        #log('window keypress: %s' % (str(event.key())))

        if (event.modifiers() == Qt.ControlModifier and event.key() == 82) or event.key() == Qt.Key_F5:
            log('reload request!')
            self.chartArea.reloadChart()
            
        else:
            super().keyPressEvent(event)
            
    def statusMessage(self, message, repaint):
        if not self.statusbar:
            log('self.statusbar.showMessage(''%s'')' %  (message))
        else:
            self.statusbar.showMessage(message)
            
            if repaint:
                self.repaint()
        
    def menuQuit(self):
        sys.exit(0)

    def menuFont(self):
        self.chartArea.widget.calculateMargins()
        
    def menuAbout(self):
        abt = aboutDialog.About()
        abt.exec_()
        
    def menuDummy(self):
        '''
            Эту лабуду бы вынести в chartArea?
            Или наоборот здесь ей самое место?
            
            Просто data provider это атрибут chartArea, почему я их тут создавать должен
            пусть CA и создаёт, а отсюда параметры только передать?
        '''
        self.chartArea.dp = dpDummy.dataProvider() # generated data
        self.chartArea.initDP()
        
    def menuConfig(self):
        
        if self.connectionConf is None:
            connConf = cfg('server')
        else:
            connConf = self.connectionConf
            
        conf, ok = configDialog.Config.getConfig(connConf)
        
        if ok:
            self.connectionConf = conf
        
        if ok and conf['ok']:
        
            try:
                self.statusMessage('Connecting...', False)
                self.repaint()

                self.chartArea.dp = dpDB.dataProvider(conf) # db data provider
                
                if hasattr(self.chartArea.dp, 'dbProperties'):
                    self.chartArea.widget.timeZoneDelta = self.chartArea.dp.dbProperties['timeZoneDelta']
                    self.chartArea.reloadChart()

                self.tabs.setTabText(0, conf['user'] + '@' + self.chartArea.dp.dbProperties['sid'])
                
                self.chartArea.initDP()
                
                #setup keep alives
                
                if cfg('keepalive'):
                    try:
                        keepalive = int(cfg('keepalive'))
                        self.chartArea.dp.enableKeepAlive(self, keepalive)
                    except:
                        log('wrong keepalive setting: %s' % (cfg('keepalive')))
                                
            except dbException as e:
                log('connect or init error:')
                if hasattr(e, 'message'):
                    log(e.message)
                else:
                    log(e)
                    
                msgBox = QMessageBox()
                msgBox.setWindowTitle('Connection error')
                msgBox.setText('Connection failed: %s ' % (str(e)))
                iconPath = resourcePath('ico\\favicon.ico')
                msgBox.setWindowIcon(QIcon(iconPath))
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.exec_()
                
                self.statusMessage('', False)
                # raise(e)
                    
        else:
            # cancel or parsing error
            
            if ok and conf['ok'] == False: #it's connection string dict in case of [Cancel]
                msgBox = QMessageBox()
                msgBox.setWindowTitle('Connection string')
                msgBox.setText('Could not start the connection. Please check the connection string: host, port, etc.')
                iconPath = resourcePath('ico\\favicon.ico')
                msgBox.setWindowIcon(QIcon(iconPath))
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.exec_()
                
                self.statusMessage('', False)
                
            
    def menuImport(self):
        fname = QFileDialog.getOpenFileNames(self, 'Import...',  None, 'Nameserver trace files (*.trc)')
        log(fname[0])
        log('But I dont work...')

        if len(fname[0]) > 0:
            msgBox = QMessageBox()
            msgBox.setWindowTitle('Import')
            msgBox.setText('Not implemented yet')
            iconPath = resourcePath('ico\\favicon.ico')
            msgBox.setWindowIcon(QIcon(iconPath))
            msgBox.setIcon(QMessageBox.Warning)
            msgBox.exec_()
        
    def setTabName(self, str):
        self.tabs.setTabText(0, str)
        
    def initUI(self):      
        # bottom left frame (hosts)
        hostsArea = QFrame(self)
        self.hostTable = hostsTable.hostsTable()
 
        # bottom right frame (KPIs)
        kpisTable = kpiTable.kpiTable()


        # top (main chart area)
        self.chartArea = chartArea.chartArea()

        # establish hard links:
        kpisTable.kpiScales = self.chartArea.widget.nscales
        self.chartArea.widget.hosts = self.hostTable.hosts
        
        kpisTable.hosts = self.chartArea.widget.hosts #why do we have hosts inside widget? because we have all data there...
        kpisTable.hostKPIs = self.chartArea.hostKPIs
        kpisTable.srvcKPIs = self.chartArea.srvcKPIs
        kpisTable.nkpis = self.chartArea.widget.nkpis
        
        # bottm part left+right
        kpiSplitter = QSplitter(Qt.Horizontal)
        kpiSplitter.addWidget(self.hostTable)
        kpiSplitter.addWidget(kpisTable)
        kpiSplitter.setSizes([200, 380])
        
        
        self.tabs = QTabWidget()
        
        console = sqlConsole.sqlConsole()
        
        # main window splitter
        mainSplitter = QSplitter(Qt.Vertical)
        
        kpisWidget = QWidget()
        lo = QVBoxLayout(kpisWidget)
        lo.addWidget(kpiSplitter)
        
        mainSplitter.addWidget(self.chartArea)
        mainSplitter.addWidget(kpisWidget)
        mainSplitter.setSizes([300, 90])
        
        mainSplitter.setAutoFillBackground(True)

        # central widget
        #self.setCentralWidget(mainSplitter)
        
        kpisWidget.autoFillBackground = True
        
        self.tabs.addTab(mainSplitter, 'Chart')
        
        if cfg('experimental'):
            self.tabs.addTab(console, 'Sql')
        
        self.setCentralWidget(self.tabs)
        
        # service stuff
        self.statusbar = self.statusBar()

        #menu
        iconPath = resourcePath('ico\\favicon.ico')

        exitAct = QAction('&Exit', self)        
        exitAct.setShortcut('Alt+Q')
        exitAct.setStatusTip('Exit application')
        exitAct.triggered.connect(self.menuQuit)


        aboutAct = QAction(QIcon(iconPath), '&About', self)
        aboutAct.setStatusTip('About this app')
        aboutAct.triggered.connect(self.menuAbout)

        dummyAct = QAction('&Dummy', self)
        dummyAct.setShortcut('Alt+D')
        dummyAct.setStatusTip('Dummy Data provider')
        dummyAct.triggered.connect(self.menuDummy)

        configAct = QAction('&Connect', self)
        configAct.setShortcut('Alt+C')
        configAct.setStatusTip('Configure connection')
        configAct.triggered.connect(self.menuConfig)

        importAct = QAction('&Import', self)
        importAct.setShortcut('Ctrl+I')
        importAct.setStatusTip('Import nameserver.trc')
        importAct.triggered.connect(self.menuImport)

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(aboutAct)
        fileMenu.addAction(configAct)

        if cfg('experimental'):
            fileMenu.addAction(importAct)
            fileMenu.addAction(dummyAct)

        fileMenu.addAction(exitAct)
        
        if cfg('experimental'):
            actionsMenu = menubar.addMenu('&Actions')
            fileMenu.addAction(aboutAct)

            fontAct = QAction('&Adjust Fonts', self)
            fontAct.setStatusTip('Adjust margins after font change (for example after move to secondary screen)')
            fontAct.triggered.connect(self.menuFont)
            
            actionsMenu.addAction(fontAct)

        # finalization
        self.setGeometry(200, 200, 1400, 800)
        #self.setWindowTitle('SAP HANA Studio Light')
        # self.setWindowTitle('HANA Army Knife')
        self.setWindowTitle('Ryba Fish Charts')
        
        self.setWindowIcon(QIcon(iconPath))
        
        self.show()

        '''
            set up some interactions
        '''
        # bind kpi checkbox signal
        kpisTable.checkboxToggle.connect(self.chartArea.checkboxToggle)
        
        # bind change scales signal
        kpisTable.adjustScale.connect(self.chartArea.adjustScale)
        kpisTable.setScale.connect(self.chartArea.setScale)

        # host table row change signal
        self.hostTable.hostChanged.connect(kpisTable.refill)

        # to fill hosts
        self.chartArea.hostsUpdated.connect(self.hostTable.hostsUpdated)

        # refresh
        self.chartArea.kpiToggled.connect(kpisTable.refill)
        # update scales signal
        self.chartArea.scalesUpdated.connect(kpisTable.updateScales)
        self.chartArea.scalesUpdated.emit() # it really not supposed to have any to update here

        #bind statusbox updating signals
        self.chartArea.statusMessage_.connect(self.statusMessage)
        self.chartArea.widget.statusMessage_.connect(self.statusMessage)

        self.chartArea.connected.connect(self.setTabName)
        log('init finish()')
        
        if self.chartArea.dp:
            self.chartArea.initDP()
        