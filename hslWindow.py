from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFrame, 
    QSplitter, QStyleFactory, QTableWidget,
    QTableWidgetItem, QPushButton, QAbstractItemView,
    QCheckBox, QMainWindow, QAction, QMenu, QFileDialog,
    QMessageBox, QTabWidget, QPlainTextEdit, QInputDialog, 
    QApplication
    )
    
from PyQt5.QtGui import QPainter, QIcon, QDesktopServices

from PyQt5.QtCore import Qt, QUrl, QEvent, QRect

from yaml import safe_load, dump, YAMLError #pip install pyyaml

import kpiTable, hostsTable
import chartArea
import configDialog, aboutDialog
import dpDBCustom

import dpTrace

import dpDummy
import dpDB
import sqlConsole

import datetime

from indicator import indicator

from utils import resourcePath

from utils import loadConfig
from utils import log
from utils import cfg
from utils import Layout
from utils import dbException, msgDialog

import utils

import customSQLs

import kpiDescriptions

import sys, os

import time

class hslWindow(QMainWindow):

    statusbar = None
    connectionConf = None
    
    kpisTable = None

    def __init__(self):
    
        self.layoutDumped = False
    
        self.sqlTabCounter = 0 #static tab counter

        self.tabs = None
    
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
                self.statusbar.removeWidget(cons.indicator)
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

        if cfg('saveLayout', True):
            self.dumpLayout()
        '''
        for i in range(self.tabs.count() -1, 0, -1):

            w = self.tabs.widget(i)
            
            if isinstance(w, sqlConsole.sqlConsole):
                w.delayBackup()
                status = w.close(False) # can not abort
        
        clipboard = QApplication.clipboard()
        event = QEvent(QEvent.Clipboard)
        QApplication.sendEvent(clipboard, event)
        '''
        
    def formatKPIs(self):
        '''
            formats list of kpis for dumpLayout and ESS reconnection
        '''

        kpis = {}
        for i in range(len(self.chartArea.widget.hosts)):
            host = self.chartArea.widget.hosts[i]
            hst = '%s:%s' % (host['host'], host['port'])
            
            if i < len(self.chartArea.widget.nkpis) and self.chartArea.widget.nkpis[i]:
                # this a list assignement we have to copy, otherwise this
                # will be implicitly erased in cleanup() at it is the same list
                kpis[hst] = self.chartArea.widget.nkpis[i].copy() 
        
        return kpis
        
    def dumpLayout(self, closeTabs = True):

        if self.layoutDumped:
            return
            
        if self.layout is None:
            return

        log('--> dumpLayout', 5)
            
        self.layoutDumped = True
    
        kpis = self.formatKPIs()
    
        log('--> dumpLayout kpis: %s' % str(kpis), 5)
        
        if len(kpis) == 0:
            log('--> no KPIs... maybe check if connected at all and if not - dont reset kpis?')
        
        if kpis:
            self.layout['kpis'] = kpis
        else:
            if 'kpis' in self.layout.lo:
                del self.layout.lo['kpis']
                
        #log('--> dumpLayout, kpis: ' + str(kpis))
        
        self.layout['pos'] = [self.pos().x(), self.pos().y()]
        self.layout['size'] = [self.size().width(), self.size().height()]
        
        self.layout['mainSplitter'] = self.mainSplitter.sizes()
        self.layout['kpiSplitter'] = self.kpiSplitter.sizes()

        hostTableWidth = []
        KPIsTableWidth = []
        
        for i in range(self.hostTable.columnCount()):
            hostTableWidth.append(self.hostTable.columnWidth(i))

        for i in range(self.kpisTable.columnCount()):
            KPIsTableWidth.append(self.kpisTable.columnWidth(i))

        self.layout['hostTableWidth'] = hostTableWidth
        self.layout['KPIsTableWidth'] = KPIsTableWidth

        # print(self.pos().x(), self.pos().y())
        
        tabs = []
        
        self.layout['currentTab'] = self.tabs.currentIndex()
        
        if cfg('saveOpenTabs', True):
            for i in range(self.tabs.count() -1, 0, -1):
                w = self.tabs.widget(i)
                
                if isinstance(w, sqlConsole.sqlConsole):
                    w.delayBackup()
                    
                    if w.fileName is not None or w.backup is not None:
                        pos = w.cons.textCursor().position()
                        block = w.cons.edit.verticalScrollBar().value()
                        #print('scroll position:', block)
                        #block = w.cons.firstVisibleBlock().position()
                        
                        if w.backup:
                            bkp = os.path.abspath(w.backup)
                        else:
                            bkp = None
                        
                        tabs.append([w.fileName, bkp, pos, block])
                        #tabs.append([w.fileName, bkp, pos])
                        
                        
                    if closeTabs:
                        w.close(None) # can not abort (and dont need to any more!)

                        self.tabs.removeTab(i)

            tabs.reverse()
                    
            if len(tabs) > 0:
                self.layout['tabs'] = tabs
            else:
                if 'tabs' in self.layout.lo:
                    self.layout.lo.pop('tabs')
                
        if 'running' in self.layout.lo:
            self.layout.lo.pop('running')
           
        self.layout.dump()
        
        
    def menuQuit(self):
    
        '''
        for i in range(self.tabs.count() -1, 0, -1):
            w = self.tabs.widget(i)
            if isinstance(w, sqlConsole.sqlConsole):
                
                status = w.close(True) # can abort
                
                if status == True:
                    self.tabs.removeTab(i)
                
                if status == False:
                    return
        '''
        
        if cfg('saveLayout', True):
            self.dumpLayout()
                    
        self.close()

    def menuReloadCustomSQLs(self):
        customSQLs.loadSQLs()
    
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
        kpis_len = len(self.chartArea.hostKPIs)
        i = 0
        
        while i < kpis_len:
            if self.chartArea.hostKPIs[i][:1] == '.' and (i == len(self.chartArea.hostKPIs) - 1 or self.chartArea.hostKPIs[i+1][:1] == '.'):
                del(self.chartArea.hostKPIs[i])
                kpis_len -= 1
            else:
                i += 1

        # del service custom groups
        kpis_len = len(self.chartArea.srvcKPIs)
        i = 0
        
        while i < kpis_len:
            if self.chartArea.srvcKPIs[i][:1] == '.' and (i == len(self.chartArea.srvcKPIs) - 1 or self.chartArea.srvcKPIs[i+1][:1] == '.'):
                del(self.chartArea.srvcKPIs[i])
                kpis_len -= 1
            else:
                i += 1
                

        try:
            dpDBCustom.scanKPIsN(self.chartArea.hostKPIs, self.chartArea.srvcKPIs, kpiStylesNN)
        except Exception as e:
            self.chartArea.disableDeadKPIs()
            msgDialog('Custom KPIs Error', 'There were errors during custom KPIs load. Load of the custom KPIs STOPPED because of that.\n\n' + str(e))
        
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
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/config'))

    def menuCustomConfHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/customKPI'))
    
    def menuContextSQLsConfHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/contextSQLs'))

    def menuTips(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/tips'))
        
    def menuDummy(self):
        self.chartArea.dp = dpDummy.dataProvider() # generated data

        if cfg('saveKPIs', True):
            self.chartArea.initDP(self.layout['kpis'])
        else:
            self.chartArea.initDP()
        
    def menuConfig(self):
        
        if self.connectionConf is None:
            connConf = cfg('server')
        else:
            connConf = self.connectionConf
            
        conf, ok = configDialog.Config.getConfig(connConf, self)
        
        if ok:
            self.connectionConf = conf
        
        if ok and conf['ok']:
        
            try:
            
                if cfg('saveLayout', True) and len(self.chartArea.widget.hosts):
                    log('connect dump layout')
                    
                    self.dumpLayout(closeTabs = False)
                    
                    log('done')

                    self.layoutDumped = False

                # need to disconnect open consoles first...
                self.statusMessage('Disconnecing open consoles...', False)
                
                for i in range(self.tabs.count()):
                
                    w = self.tabs.widget(i)
                
                    if isinstance(w, sqlConsole.sqlConsole) and w.conn is not None:
                        log('closing connection...')
                        w.disconnectDB()
                        w.indicator.status = 'disconnected'
                        w.indicator.repaint()
                        log('disconnected...')

                self.statusMessage('Connecting...', False)
                self.repaint()

                self.chartArea.setStatus('sync', True)
                self.chartArea.dp = dpDB.dataProvider(conf) # db data provider
                self.chartArea.setStatus('idle')


                for i in range(self.tabs.count()):
                
                    w = self.tabs.widget(i)
                
                    if isinstance(w, sqlConsole.sqlConsole):
                        w.config = conf
                        
                if cfg('saveKPIs', True):
                    if self.layout and 'kpis' in self.layout.lo:
                        log('--> dumplayout, init kpis:' + str(self.layout['kpis']), 5)
                        self.chartArea.initDP(self.layout['kpis'].copy())
                        self.kpisTable.host = None
                    else:
                        log('--> dumplayout, no kpis', 5)
                        self.chartArea.initDP()
                        self.kpisTable.host = None
                       

                    '''
                    #397, 2021-06-17
                    starttime = datetime.datetime.now() - datetime.timedelta(seconds= 12*3600)
                    starttime -= datetime.timedelta(seconds= starttime.timestamp() % 3600)
                    
                    self.chartArea.fromEdit.setText(starttime.strftime('%Y-%m-%d %H:%M:%S'))
                    self.chartArea.toEdit.setText('')
                    '''
                        
                        
                else:
                    self.chartArea.initDP()
                
                if cfg('saveKPIs', True):
                    if self.layout and 'kpis' in self.layout.lo:
                        self.statusMessage('Loading saved kpis...', True)

                if hasattr(self.chartArea.dp, 'dbProperties'):
                    self.chartArea.widget.timeZoneDelta = self.chartArea.dp.dbProperties['timeZoneDelta']
                    if not conf['noreload']:
                        log('reload from menuConfig #1', 4)
                        self.chartArea.reloadChart()
                else:
                    log('reload from menuConfig #2', 4)
                    self.chartArea.reloadChart()
                    
                propStr = conf['user'] + '@' + self.chartArea.dp.dbProperties['sid']
                
                tenant = self.chartArea.dp.dbProperties.get('tenant')
                
                if tenant:
                    windowStr = ('%s %s@%s' % (conf['user'], tenant, self.chartArea.dp.dbProperties['sid']))
                else:
                    windowStr = propStr
                
                self.tabs.setTabText(0, propStr)
                self.setWindowTitle('RybaFish Charts [%s]' % windowStr)
                
                #setup keep alives
                
                if cfg('keepalive'):
                    try:
                        keepalive = int(cfg('keepalive'))
                        self.chartArea.dp.enableKeepAlive(self, keepalive)
                    except:
                        log('wrong keepalive setting: %s' % (cfg('keepalive')))
                                
            except dbException as e:
                log('Connect or init error:')
                if hasattr(e, 'message'):
                    log(e.message)
                else:
                    log(e)
                    
                msgBox = QMessageBox(self)
                msgBox.setWindowTitle('Connection error')
                msgBox.setText('Connection failed: %s ' % (str(e)))
                iconPath = resourcePath('ico\\favicon.png')
                msgBox.setWindowIcon(QIcon(iconPath))
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.exec_()
                
                self.statusMessage('', False)

            except Exception as e:
                log('Init exception not related to DB')
                log(str(e))

                msgBox = QMessageBox(self)
                msgBox.setWindowTitle('Error')
                msgBox.setText('Init failed: %s \n\nSee more deteails in the log file.' % (str(e)))
                iconPath = resourcePath('ico\\favicon.png')
                msgBox.setWindowIcon(QIcon(iconPath))
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.exec_()
                
                self.statusMessage('', False)
                    
        else:
            # cancel or parsing error
            
            if ok and conf['ok'] == False: #it's connection string dict in case of [Cancel]
                msgBox = QMessageBox(self)
                msgBox.setWindowTitle('Connection string')
                msgBox.setText('Could not start the connection. Please check the connection string: host, port, etc.')
                iconPath = resourcePath('ico\\favicon.png')
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
            and with dumpLayout!
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
            
            self.statusMessage('Connecting console...', True)
            
            try:
                console = sqlConsole.sqlConsole(self, conf, 'sqlopen')
            except:
                self.statusMessage('Failed', True)
                log('[!] error creating console for the file')
                return
                
            
            self.statusMessage('', False)
            
            console.nameChanged.connect(self.changeActiveTabName)
            console.cons.closeSignal.connect(self.closeTab)

            self.tabs.addTab(console, console.tabname)
            
            console.selfRaise.connect(self.raiseTab)
            console.statusMessage.connect(self.statusMessage)
            
            ind = indicator()
            console.indicator = ind
            
            ind.iClicked.connect(console.reportRuntime)
            
            ind.iToggle.connect(console.updateRuntime)
                        
            self.statusbar.addPermanentWidget(ind)
            
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
            
            console.openFile(filename)

            if self.layout == None:
                # no backups to avoid conflicts...
                console.noBackup = True

    #def populateConsoleTab(self):

    def menuSQLConsole(self):
    
        conf = self.connectionConf
        
        if conf is None:
            self.statusMessage('No configuration...', False)
            return
            
        self.statusMessage('Connecting...', True)

        ind = indicator()
        self.statusbar.addPermanentWidget(ind)

        ind.status = 'sync'
        ind.repaint()
        
        log('menuSQLConsole...')
        
        noname = True
        
        while noname:
            self.sqlTabCounter += 1
            idx = self.sqlTabCounter
            
            if idx > 1:
                tname = 'sql' + str(idx)
            else:
                tname = 'sql'
                
            for i in range(self.tabs.count() -1, 0, -1):
                w = self.tabs.widget(i)
                if isinstance(w, sqlConsole.sqlConsole):
                    if w.tabname == tname or w.tabname == tname + ' *': # so not nice...
                        break
            else:
                noname = False
                
        # console = sqlConsole.sqlConsole(self, conf, tname) # self = window

        try:
            console = sqlConsole.sqlConsole(self, conf, tname) # self = window
            log('seems connected...')
        except dbException as e:
            log('[!] failed to open console expectedly')
            self.statusMessage('Connection error', True)

            self.statusbar.removeWidget(ind)
            return
        '''
        except Exception as e:
            log('[!] failed to open console unexpectedly: ' + str(e))
            self.statusMessage('Connection error?', True)
            return
        '''
        
        console.indicator = ind
        ind.iClicked.connect(console.reportRuntime)

        ind.iToggle.connect(console.updateRuntime)
        
        console.nameChanged.connect(self.changeActiveTabName)
        console.cons.closeSignal.connect(self.closeTab)
        self.tabs.addTab(console, tname)
        
        console.selfRaise.connect(self.raiseTab)
        console.statusMessage.connect(self.statusMessage)
        
        self.tabs.setCurrentIndex(self.tabs.count() - 1)

        if console.unsavedChanges:
            # if autoloaded from backup
            # cannot be triggered from inside as signal not connected on __init__
            self.changeActiveTabName(console.tabname + ' *')
        
        if self.layout == None:
            # no backups to avoid conflicts...
            console.noBackup = True
        
        self.statusMessage('', False)
        console.indicator.status = 'idle'
        console.indicator.repaint()
            
    
    def menuEss(self):
    
        if cfg('ess', False) == False:
            utils.cfgSet('ess', True)
            self.essAct.setText('Switch back to m_load_history...')
            #self.statusMessage('You need to reconnect in order to have full ESS data available', False)
        

            kpis = self.formatKPIs()
        
            self.chartArea.setStatus('sync', True)
            self.chartArea.initDP(kpis.copy(), message = 'Re-initializing hosts information...')
            self.kpisTable.host = None
            
            self.statusMessage('Now reload...', True)
            self.chartArea.reloadChart()
            self.chartArea.setStatus('idle', True)
        
        else:
            utils.cfgSet('ess', False)
            self.essAct.setText('Switch to ESS load history')
            self.essAct.setStatusTip('Switches from online m_load_history views to ESS tables, will trigger hosts re-init')

            kpis = self.formatKPIs()
        
            self.chartArea.setStatus('sync', True)
            self.chartArea.initDP(kpis.copy(), message = 'Re-initializing hosts information...')
            self.kpisTable.host = None
            
            self.statusMessage('Now reload...', True)
            self.chartArea.reloadChart()
            self.chartArea.setStatus('idle', True)
    
    def menuImport(self):
        fname = QFileDialog.getOpenFileNames(self, 'Import nameserver_history.trc...',  None, 'Import nameserver history trace (*.trc)')
        log(fname[0])
        
        
        if len(fname[0]) > 0:
            self.chartArea.dp = dpTrace.dataProvider(fname[0]) # db data provider
            
            self.chartArea.initDP(message = 'Parsing the trace file, will take a minute or so...')

            toTime = self.chartArea.widget.hosts[0]['to']
            fromTime = toTime - datetime.timedelta(hours = 10)
            
            self.chartArea.toEdit.setText(toTime.strftime('%Y-%m-%d %H:%M:%S'))
            self.chartArea.fromEdit.setText(fromTime.strftime('%Y-%m-%d %H:%M:%S'))
            
            self.chartArea.reloadChart()
        
    def raiseTab(self, tab):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            
            if w is tab:
                self.tabs.setCurrentIndex(i)
                break
    
    
    def setTabName(self, str):
        self.tabs.setTabText(0, str)
        
    def initUI(self):

        if cfg('saveLayout', True):
            self.layout = Layout(True)
            
            if self.layout['running']:

                try:
                    import pyi_splash
                    pyi_splash.close()
                except:
                    pass

                answer = utils.yesNoDialog('Warning', 'Another RybaFish is already running, all the layout and autosave features will be disabled.\n\nExit now?', ignore = True)
                #answer = utils.yesNoDialog('Warning', 'RybaFish is already running or crashed last time, all the layout and autosave features will be disabled.\n\nExit now?', ignore = True)
                
                if answer == True or answer is None:
                    exit(0)
                
                if answer == 'ignore':
                    log('Ignoring the layout')
                else:
                    self.layout = None
            else:
                self.layout['running'] = True
                self.layout.dump()
        else:
            self.layout = Layout()
            
        
        # bottom left frame (hosts)
        hostsArea = QFrame(self)
        self.hostTable = hostsTable.hostsTable()
 
        # bottom right frame (KPIs)
        self.kpisTable = kpiTable.kpiTable()
        kpisTable = self.kpisTable


        # top (main chart area)
        self.chartArea = chartArea.chartArea()

        ind = indicator()
        self.chartArea.indicator = ind
        self.chartArea.indicator.status = 'disconnected'

        # establish hard links:
        kpisTable.kpiScales = self.chartArea.widget.nscales
        self.chartArea.widget.hosts = self.hostTable.hosts
        
        kpisTable.hosts = self.chartArea.widget.hosts #why do we have hosts inside widget? because we have all data there...
        kpisTable.hostKPIs = self.chartArea.hostKPIs
        kpisTable.srvcKPIs = self.chartArea.srvcKPIs
        kpisTable.nkpis = self.chartArea.widget.nkpis
        
        # bottm part left+right
        self.kpiSplitter = QSplitter(Qt.Horizontal)
        self.kpiSplitter.addWidget(self.hostTable)
        self.kpiSplitter.addWidget(kpisTable)
        self.kpiSplitter.setSizes([200, 380])
        
        
        self.tabs = QTabWidget()
        
        # self.tabs.currentChanged.connect(self.tabChanged)
        
        # main window splitter
        self.mainSplitter = QSplitter(Qt.Vertical)
        
        kpisWidget = QWidget()
        lo = QVBoxLayout(kpisWidget)
        lo.addWidget(self.kpiSplitter)
        
        self.mainSplitter.addWidget(self.chartArea)
        self.mainSplitter.addWidget(kpisWidget)
        
        if self.layout is not None:
            if self.layout['mainSplitter']:
                self.mainSplitter.setSizes(self.layout['mainSplitter'])
            else:
                self.mainSplitter.setSizes([300, 90])

            if self.layout['kpiSplitter']:
                self.kpiSplitter.setSizes(self.layout['kpiSplitter'])
            else:
                self.kpiSplitter.setSizes([200, 380])
            
            
            if self.layout['hostTableWidth']:
                hostTableWidth = self.layout['hostTableWidth']
            
                for i in range(self.hostTable.columnCount()):
                    if i > len(hostTableWidth) - 1:
                        break
                    self.hostTable.setColumnWidth(i, hostTableWidth[i])

            if self.layout['KPIsTableWidth']:
                KPIsTableWidth = self.layout['KPIsTableWidth']
            
                for i in range(self.kpisTable.columnCount()):
                    if i > len(KPIsTableWidth) - 1:
                        break
                    self.kpisTable.setColumnWidth(i, KPIsTableWidth[i])
        else:
            self.mainSplitter.setSizes([300, 90])
            self.kpiSplitter.setSizes([200, 380])
            
        
        self.mainSplitter.setAutoFillBackground(True)

        # central widget
        #self.setCentralWidget(mainSplitter)
        
        kpisWidget.autoFillBackground = True
        
        self.tabs.addTab(self.mainSplitter, 'Chart')
        
        self.chartArea.selfRaise.connect(self.raiseTab)
        ind.iClicked.connect(self.chartArea.indicatorSignal)

        # as console is fully sync it does not have runtime and corresponding signals
        
        self.setCentralWidget(self.tabs)
        
        # service stuff
        self.statusbar = self.statusBar()
        self.statusbar.addPermanentWidget(ind)

        #menu
        iconPath = resourcePath('ico\\favicon.png')

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

        importAct = QAction('&Import nameserver history trace', self)
        importAct.setShortcut('Ctrl+I')
        importAct.setStatusTip('Import nameserver.trc')
        importAct.triggered.connect(self.menuImport)

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

        fileMenu.addAction(importAct)
        
        fileMenu.addAction(sqlConsAct)
        fileMenu.addAction(openAct)
        
        fileMenu.addAction(saveAct)
        
        if cfg('dev'):
            fileMenu.addAction(dummyAct)

        fileMenu.addAction(exitAct)
        
        actionsMenu = menubar.addMenu('&Actions')
        
        if cfg('experimental'):
            # fileMenu.addAction(aboutAct) -- print not sure why its here

            fontAct = QAction('&Adjust Fonts', self)
            fontAct.setStatusTip('Adjust margins after font change (for example after move to secondary screen)')
            fontAct.triggered.connect(self.menuFont)
            
            actionsMenu.addAction(fontAct)
            
        # issue #255
        reloadConfigAct = QAction('Reload &Config', self)
        reloadConfigAct.setStatusTip('Reload configuration file. Note: some values used during the connect or other one-time-actions (restart required).')
        reloadConfigAct.triggered.connect(self.menuReloadConfig)
        actionsMenu.addAction(reloadConfigAct)

        reloadCustomKPIsAct = QAction('Reload Custom &KPIs', self)
        reloadCustomKPIsAct.setStatusTip('Reload definition of custom KPIs')
        reloadCustomKPIsAct.triggered.connect(self.menuReloadCustomKPIs)

        actionsMenu.addAction(reloadCustomKPIsAct)

        if cfg('experimental'):
            reloadCustomSQLsAct = QAction('Reload Context &SQLs', self)
            reloadCustomSQLsAct.setStatusTip('Reload definition of context SQLs')
            reloadCustomSQLsAct.triggered.connect(self.menuReloadCustomSQLs)
            
            actionsMenu.addAction(reloadCustomSQLsAct)

        self.essAct = QAction('Switch to ESS load history', self)
        self.essAct.setStatusTip('Switches from online m_load_history views to ESS tables')
        self.essAct.triggered.connect(self.menuEss)

        actionsMenu.addAction(self.essAct)

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

        if cfg('experimental'):
            confContextHelpAct = QAction('Context SQLs', self)
            confContextHelpAct.setStatusTip('Short manual on context SQLs')
            confContextHelpAct.triggered.connect(self.menuContextSQLsConfHelp)

        confTipsAct = QAction('Tips and tricks', self)
        confTipsAct.setStatusTip('Tips and tricks description')
        confTipsAct.triggered.connect(self.menuTips)
        
        helpMenu = menubar.addMenu('&Help')
        helpMenu.addAction(confHelpAct)
        
        
        helpMenu.addAction(confCustomHelpAct)
        
        if cfg('experimental'):
            helpMenu.addAction(confContextHelpAct)
        
        helpMenu.addAction(confTipsAct)
            
        helpMenu.addAction(aboutAct)

        # finalization        

        if self.layout is not None and self.layout['pos'] and self.layout['size']:
            pos = self.layout['pos']
            size = self.layout['size']
            
            #print('screen number', QApplication.desktop().screenNumber())
            #print('number of screens', QApplication.desktop().screenCount())
            #print('available geometry:', QApplication.desktop().availableGeometry())
            #print('screen geometry:', QApplication.desktop().screenGeometry())
            
            r = QRect(pos[0], pos[1], size[0], size[1])

            if QApplication.desktop().screenCount() == 1:
                # only when just one screen is available...
                if not QApplication.desktop().screenGeometry().contains(r) and not cfg('dontAutodetectScreen'):
                    #the window will not be visible so jump to the main screen:
                    (pos[0], pos[1]) = (100, 50)
            
            #self.setGeometry(pos[0] + 8, pos[1] + 31, size[0], size[1])
            #self.setGeometry(pos[0], pos[1], size[0], size[1])
            
            self.move(pos[0], pos[1])
            self.resize(size[0], size[1])
        else:
            self.setGeometry(200, 200, 1400, 800)
        
        self.setWindowTitle('RybaFish Charts')
        
        self.setWindowIcon(QIcon(iconPath))
        
        scrollPosition = []
        
        if cfg('saveOpenTabs', True) and self.layout is not None and self.layout['tabs']:
            for t in self.layout['tabs']:
                if len(t) != 4:
                    continue
                    
                console = sqlConsole.sqlConsole(self, None, '?')

                console.nameChanged.connect(self.changeActiveTabName)
                console.cons.closeSignal.connect(self.closeTab)

                self.tabs.addTab(console, console.tabname)
                
                ind = indicator()
                console.indicator = ind
                console.indicator.status = 'disconnected'
                
                console.selfRaise.connect(self.raiseTab)
                console.statusMessage.connect(self.statusMessage)
                
                ind.iClicked.connect(console.reportRuntime)
                
                ind.iToggle.connect(console.updateRuntime)
                
                self.statusbar.addPermanentWidget(ind)
                
                self.tabs.setCurrentIndex(self.tabs.count() - 1)
                
                if t[0] is not None or t[1] is not None:
                    # such a tab should not ever be saved (this call will just open fileOpen dialog), anyway... 
                    # should we even create such a tab?
                    console.openFile(t[0], t[1])
                    
                    pos = t[2]
                    block = t[3]
                    
                    scrollPosition.append(block)
                    
                    if isinstance(pos, int) and isinstance(block, int):
                        cursor = console.cons.textCursor()
                        cursor.setPosition(pos, cursor.MoveAnchor)
                        console.cons.setTextCursor(cursor)
                        
            indx = self.layout['currentTab']
            
            if isinstance(indx, int):
                self.tabs.setCurrentIndex(indx)

                w = self.tabs.widget(indx)
                
                if isinstance(w, sqlConsole.sqlConsole):
                    w.cons.setFocus()
                
            else:
                self.tabs.setCurrentIndex(0)

        # if the cursor points to a pair bracket, the highlighting will disappear on the next call...
        self.show()

        #scroll everything to stored position
        for i in range(self.tabs.count() -1, 0, -1):
            w = self.tabs.widget(i)
            if isinstance(w, sqlConsole.sqlConsole):
            
                if i - 1 < len(scrollPosition):
                    block = scrollPosition[i - 1]
                    
                    w.cons.edit.verticalScrollBar().setValue(block)
                else:
                    log('[w] scroll position list out of range, ignoring scrollback...')
        

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
        
        log('self.scalesUpdated.emit() #0', 5)
        self.chartArea.scalesUpdated.emit() # it really not supposed to have any to update here

        #bind statusbox updating signals
        self.chartArea.statusMessage_.connect(self.statusMessage)
        self.chartArea.widget.statusMessage_.connect(self.statusMessage)

        self.chartArea.connected.connect(self.setTabName)
        log('init finish()')


        if cfg('experimental'):
            customSQLs.loadSQLs()

        # offline console tests
        
        if cfg('developmentMode'):
        
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
            
            console.selfRaise.connect(self.raiseTab)
            console.statusMessage.connect(self.statusMessage)
            
            self.tabs.setCurrentIndex(self.tabs.count() - 1)

            self.SQLSyntax = SQLSyntaxHighlighter(console.cons.document())
            #console.cons.setPlainText('select * from dummy;\n\nselect \n    *\n    from dummy;\n\nselect * from m_host_information;');

            ind = indicator()
            console.indicator = ind
            self.statusbar.addPermanentWidget(ind)
            
            ind.iClicked.connect(console.reportRuntime)

            ind.iToggle.connect(console.updateRuntime)
            
            if cfg('developmentMode'): 
                console.cons.setPlainText('''select 0 from dummy;
create procedure ...
(
(as begin)
select * from dummy);
end;

where timestamp between '2020-02-10 00:00:00' and '2020-02-16 23:59:59' -- test comment

where not "NAME1" = '' and "DOKST" in ('D0', 'D2') and (1 = 2)

select 1 from dummy;
select 2 from dummy;
select 3 from dummy;''');
                
            console.dummyResultTable()
        
        self.statusMessage('', False)
        
        if self.chartArea.dp:
            self.chartArea.initDP()
        