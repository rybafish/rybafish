from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFrame, 
    QSplitter, QStyleFactory, QTableWidget,
    QTableWidgetItem, QPushButton, QAbstractItemView,
    QCheckBox, QMainWindow, QAction, QMenu, QFileDialog,
    QMessageBox, QTabWidget, QPlainTextEdit, QInputDialog, 
    QApplication
    )
    
from PyQt5.QtGui import QPainter, QIcon, QDesktopServices

from PyQt5.QtCore import Qt, QUrl, QEvent

from yaml import safe_load, dump, YAMLError #pip install pyyaml

import kpiTable, hostsTable
import chartArea
import configDialog, aboutDialog
import dpDBCustom

import dpDummy
import dpDB
import sqlConsole

from utils import resourcePath

from utils import loadConfig
from utils import log
from utils import cfg
from utils import dbException

import kpiDescriptions

import sys


import time

class hslWindow(QMainWindow):

    statusbar = None
    connectionConf = None
    
    kpisTable = None

    def __init__(self):
    
        self.sqlTabCounter = 0 #static tab counter
    
        super().__init__()
        self.initUI()
        
        
    # def tabChanged(self, newidx):
        
    def closeTab(self):
        indx = self.tabs.currentIndex()
        
        if indx > 0: #print need a better way to identify sql consoles...
            cons = self.tabs.currentWidget()
            
            cons.delayBackup()

            status = cons.close()
            
            if status == True:
                self.tabs.removeTab(indx)
    
        
    def keyPressEvent(self, event):
        #log('window keypress: %s' % (str(event.key())))

        modifiers = event.modifiers()

        if (modifiers == Qt.ControlModifier and event.key() == 82) or event.key() == Qt.Key_F5:
            log('reload request!')
            self.chartArea.reloadChart()
            
        elif modifiers == Qt.ControlModifier and event.key() == Qt.Key_W:
            self.closeTab()
        else:
            super().keyPressEvent(event)
            
    def statusMessage(self, message, repaint):
        if not self.statusbar:
            log('self.statusbar.showMessage(''%s'')' %  (message))
        else:
            self.statusbar.showMessage(message)
            
            if repaint:
                self.repaint()
        
    def closeEvent(self, event):
        log('Exiting...')
        
        for i in range(self.tabs.count() -1, 0, -1):

            w = self.tabs.widget(i)
            
            if isinstance(w, sqlConsole.sqlConsole):
                w.delayBackup()
                status = w.close(False) # can not abort
        
        clipboard = QApplication.clipboard()
        event = QEvent(QEvent.Clipboard)
        QApplication.sendEvent(clipboard, event)
        
    def menuQuit(self):
        for i in range(self.tabs.count() -1, 0, -1):
            w = self.tabs.widget(i)
            if isinstance(w, sqlConsole.sqlConsole):
                
                status = w.close(True) # can abort
                
                if status == True:
                    self.tabs.removeTab(i)
                
                if status == False:
                    return
                    
        self.close()

    def menuReloadCustomKPIs(self):
    
        kpiStylesNN = kpiDescriptions.kpiStylesNN
        
        for type in ('host', 'service'):
            for kpiName in list(kpiStylesNN[type]):

                kpi = kpiStylesNN[type][kpiName]
                
                if kpi['sql'] is not None:
                    del(kpiStylesNN[type][kpiName])
                    
                    if type == 'host':
                        self.chartArea.hostKPIs.remove(kpiName)
                    else:
                        self.chartArea.srvcKPIs.remove(kpiName)
        
        # del host custom groups
        for i in range(len(self.chartArea.hostKPIs)):
            if self.chartArea.hostKPIs[i][:1] == '.' and (i == len(self.chartArea.hostKPIs) - 1 or self.chartArea.hostKPIs[i+1][:1] == '.'):
                del(self.chartArea.hostKPIs[i])

        # del service custom groups
        for i in range(len(self.chartArea.srvcKPIs)):
            if self.chartArea.srvcKPIs[i][:1] == '.' and (i == len(self.chartArea.srvcKPIs) - 1 or self.chartArea.srvcKPIs[i+1][:1] == '.'):
                del(self.chartArea.srvcKPIs[i])

        dpDBCustom.scanKPIsN(self.chartArea.hostKPIs, self.chartArea.srvcKPIs, kpiStylesNN)
        self.chartArea.widget.initPens()
        self.chartArea.widget.update()
        
        #really unsure if this one can be called twice...
        kpiDescriptions.clarifyGroups()
        
        #trigger refill        
        self.kpisTable.refill(self.hostTable.currentRow())
        
        self.statusMessage('Custom KPIs reload finish', False)
    
    def menuReloadConfig(self):
        loadConfig()
        self.statusMessage('Configuration file reloaded.', False)
    
    def menuFont(self):
        id = QInputDialog

        sf = cfg('fontScale', 1)
        
        sf, ok = id.getDouble(self, 'Input the scaling factor', 'Scaling Factor', sf, 0, 5, 2)
        
        if ok:
            self.chartArea.widget.calculateMargins(sf)
            self.chartArea.adjustScale(sf)
        
    def menuAbout(self):
        abt = aboutDialog.About()
        abt.exec_()
        
    def menuConfHelp(self):
        QDesktopServices.openUrl(QUrl('http://rybafish.net/config'))

    def menuCustomConfHelp(self):
        QDesktopServices.openUrl(QUrl('http://rybafish.net/customKPI'))
        
        
    def menuDummy(self):
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
                
                self.chartArea.initDP()
                
                if hasattr(self.chartArea.dp, 'dbProperties'):
                    self.chartArea.widget.timeZoneDelta = self.chartArea.dp.dbProperties['timeZoneDelta']
                    self.chartArea.reloadChart()

                self.tabs.setTabText(0, conf['user'] + '@' + self.chartArea.dp.dbProperties['sid'])
                
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
        
    def changeActiveTabName(self, name):
    
        i = self.tabs.currentIndex()

        # must be a better way verity if we attempt to update chart tab name
        if i == 0:
            return
            
        self.tabs.setTabText(i, name)
    
    def menuSave(self):
    
        indx = self.tabs.currentIndex()

        w = self.tabs.widget(indx)
    
        if not isinstance(w, sqlConsole.sqlConsole):
            return
            
        w.delayBackup()
        w.saveFile()
    
    def menuOpen(self):
        '''
            so much duplicate code with menuSqlConsole
        '''
        fname = QFileDialog.getOpenFileNames(self, 'Open file', '','*.sql')
        
        openfiles = {}
        
        for i in range(self.tabs.count()):
        
            w = self.tabs.widget(i)
        
            if isinstance(w, sqlConsole.sqlConsole):

                fn = w.fileName

                if fn is not None:
                    openfiles[fn] = i

        for filename in fname[0]:

            if filename in openfiles:
                # the file is already open
                idx = openfiles[filename]
                
                self.tabs.setCurrentIndex(idx)
                continue
                
            conf = self.connectionConf
               
            self.statusMessage('Connecting console...', False)
            
            console = sqlConsole.sqlConsole(self, conf, 'sqlopen')
            
            self.statusMessage('', False)
            
            console.nameChanged.connect(self.changeActiveTabName)
            console.cons.closeSignal.connect(self.closeTab)

            self.tabs.addTab(console, console.tabname)
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
            
            console.openFile(filename)

    def menuSQLConsole(self):
    
        conf = self.connectionConf
        
        if conf is None:
            self.statusMessage('No configuration...', False)
            return
            
        self.statusMessage('Connecting...', False)


        #idx = self.tabs.count()
        self.sqlTabCounter += 1
        idx = self.sqlTabCounter
        
        if idx > 1:
            tname = 'sql' + str(idx)
        else:
            tname = 'sql'
            
        console = sqlConsole.sqlConsole(self, conf, tname) # self = window
        console.nameChanged.connect(self.changeActiveTabName)
        console.cons.closeSignal.connect(self.closeTab)
        self.tabs.addTab(console, tname)
        
        self.tabs.setCurrentIndex(self.tabs.count() - 1)

        if console.unsavedChanges:
            # if autoloaded from backup
            # cannot be triggered from inside as signal not connected on __init__
            self.changeActiveTabName(console.tabname + ' *')
        
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
        self.kpisTable = kpiTable.kpiTable()
        kpisTable = self.kpisTable


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
        
        # self.tabs.currentChanged.connect(self.tabChanged)
        
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
        
        self.setCentralWidget(self.tabs)
        
        # service stuff
        self.statusbar = self.statusBar()

        #menu
        iconPath = resourcePath('ico\\favicon.ico')

        exitAct = QAction('&Exit', self)        
        exitAct.setShortcut('Alt+Q')
        exitAct.setStatusTip('Exit application')
        exitAct.triggered.connect(self.menuQuit)

        dummyAct = QAction('&Dummy', self)
        dummyAct.setShortcut('Alt+D')
        dummyAct.setStatusTip('Dummy Data provider')
        dummyAct.triggered.connect(self.menuDummy)

        configAct = QAction('&Connect', self)
        configAct.setShortcut('Alt+C')
        configAct.setStatusTip('Configure connection')
        configAct.triggered.connect(self.menuConfig)

        '''
        not ready
        
        importAct = QAction('&Import', self)
        importAct.setShortcut('Ctrl+I')
        importAct.setStatusTip('Import nameserver.trc')
        importAct.triggered.connect(self.menuImport)
        '''

        sqlConsAct = QAction('New &SQL Console', self)
        sqlConsAct.setShortcut('Alt+S')
        sqlConsAct.setStatusTip('Create SQL Console')
        sqlConsAct.triggered.connect(self.menuSQLConsole)

        openAct = QAction('&Open file in new sql console', self)
        openAct.setShortcut('Ctrl+O')
        openAct.setStatusTip('Open new console with the file')
        openAct.triggered.connect(self.menuOpen)

        saveAct = QAction('&Save sql to a file', self)
        saveAct.setShortcut('Ctrl+S')
        saveAct.setStatusTip('Saves sql from current console to a file')
        saveAct.triggered.connect(self.menuSave)

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(configAct)

        if cfg('experimental'):
            #fileMenu.addAction(importAct)
            fileMenu.addAction(dummyAct)
            fileMenu.addAction(sqlConsAct)
            fileMenu.addAction(openAct)
            fileMenu.addAction(saveAct)

        fileMenu.addAction(exitAct)
        
        if cfg('experimental'):
            actionsMenu = menubar.addMenu('&Actions')
            # fileMenu.addAction(aboutAct) -- print not sure why its here

            fontAct = QAction('&Adjust Fonts', self)
            fontAct.setStatusTip('Adjust margins after font change (for example after move to secondary screen)')
            fontAct.triggered.connect(self.menuFont)

            reloadConfigAct = QAction('Reload &Config', self)
            reloadConfigAct.setStatusTip('Reload configuration file. Note: some values used during the connect or other one-time-actions')
            reloadConfigAct.triggered.connect(self.menuReloadConfig)
            
            actionsMenu.addAction(fontAct)
            
            actionsMenu.addAction(reloadConfigAct)

        reloadCustomKPIsAct = QAction('Reload Custom &KPIs', self)
        reloadCustomKPIsAct.setStatusTip('Reload definition of custom KPIs')
        reloadCustomKPIsAct.triggered.connect(self.menuReloadCustomKPIs)

        actionsMenu.addAction(reloadCustomKPIsAct)

        # help menu part
        aboutAct = QAction(QIcon(iconPath), '&About', self)
        aboutAct.setStatusTip('About this app')
        aboutAct.triggered.connect(self.menuAbout)

        confHelpAct = QAction('Configuration', self)
        confHelpAct.setStatusTip('Configuration options description')
        confHelpAct.triggered.connect(self.menuConfHelp)

        confCustomHelpAct = QAction('Custom KPIs', self)
        confCustomHelpAct.setStatusTip('Short manual on custom KPIs')
        confCustomHelpAct.triggered.connect(self.menuCustomConfHelp)
        
        helpMenu = menubar.addMenu('&Help')
        helpMenu.addAction(confHelpAct)
        
        if cfg('experimental'):
            helpMenu.addAction(confCustomHelpAct)
            
        helpMenu.addAction(aboutAct)

        # finalization
        self.setGeometry(200, 200, 1400, 800)
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
        

        # offline console tests
        
        if (cfg('developmentMode')):
        
            #tname = sqlConsole.generateTabName()

            #idx = self.tabs.count()
            self.sqlTabCounter += 1
            idx = self.sqlTabCounter
            
            if idx > 1:
                tname = 'sql' + str(idx)
            else:
                tname = 'sql'
            
            console = sqlConsole.sqlConsole(self, None, tname)
            console.nameChanged.connect(self.changeActiveTabName)
            
            from SQLSyntaxHighlighter import SQLSyntaxHighlighter

            self.tabs.addTab(console, tname)
            self.tabs.setCurrentIndex(self.tabs.count() - 1)

            self.SQLSyntax = SQLSyntaxHighlighter(console.cons.document())
            #console.cons.setPlainText('select * from dummy;\n\nselect \n    *\n    from dummy;\n\nselect * from m_host_information;');
            
            if cfg('developmentMode'): 
                console.cons.setPlainText('''select 0 from dummy;
create procedure ...
(
(as begin)
select * from dummy);
end;

where timestamp between '2020-02-10 00:00:00' and '2020-02-16 23:59:59'

select 1 from dummy;
select 2 from dummy;
select 3 from dummy;''');
                
            console.dummyResultTable()
        
        self.statusMessage('', False)
        
        if self.chartArea.dp:
            self.chartArea.initDP()
        