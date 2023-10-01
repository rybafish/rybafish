from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFrame,
    QSplitter, QStyleFactory, QTableWidget,
    QTableWidgetItem, QPushButton, QAbstractItemView,
    QCheckBox, QMainWindow, QAction, QMenu, QFileDialog,
    QMessageBox, QTabWidget, QPlainTextEdit, QInputDialog, 
    QApplication
    )
    
from PyQt5.QtGui import QPainter, QIcon, QDesktopServices

from PyQt5.QtCore import Qt, QUrl, QEvent, QRect, QProcess, QThread

from yaml import safe_load, dump, YAMLError #pip install pyyaml

import kpiTable, hostsTable
import chartArea
import configDialog, aboutDialog
import dpDBCustom

import dpTrace

import dpDummy
import dpDB
from dbi import dbi
import sqlConsole

import datetime

from indicator import indicator

from utils import resourcePath

from utils import loadConfig
from utils import log, deb
from utils import cfg
from utils import Layout
from utils import dbException, msgDialog

from SQLBrowserDialog import SQLBrowserDialog

import utils

import customSQLs

import kpiDescriptions

import sys, os

import time

from _constants import build_date, version

from updatesCheck import checkUpdates
from csvImportDialog import csvImportDialog

from profiler import profiler

class hslWindow(QMainWindow):

    statusbar = None
    primaryConf = None # primary connection dictionary, keys: host, port, name, dbi, user, pwd, etc
    configurations = {}
    
    kpisTable = None
    
    threadID = None

    def __init__(self):
    
        self.layoutDumped = False
    
        self.sqlTabCounter = 0 #static tab counter

        self.tabs = None
    
        super().__init__()
        
        self.threadID = int(QThread.currentThreadId())
        log(f'[thread] main window thread: {self.threadID}', 5)
        
        self.initUI()
        
        if cfg('updatesCheckInterval', '7'):
            if self.layout is not None:
                checkUpdates(self, self.updatesCB, self.layout.lo.get('updateNextCheck'), self.layout.lo.get('updateVersionCheck'))
        
    # def tabChanged(self, newidx):
    
    def updatesCB(self, status, buildDate = None):
    
        interval = cfg('updatesCheckInterval', '7')
        
        if interval:
            try:
                interval = int(interval)
            except ValueError:
                log('[!] unexpected updateCheckInterval: %s' % str(interval), 2)
                interval = 7
        else:
            interval = 7
            
        log('Updates callback, status: [%s]' % status, 4)
    
        today = datetime.datetime.now().date()


        '''
        if 'updateVersionCheck' in self.layout.lo:
            self.layout.lo.pop('updateVersionCheck')
        '''

        if 'updateNextCheck' in self.layout.lo:
            self.layout.lo.pop('updateNextCheck')

        if status in (''):
            self.layout['updateNextCheck'] = today + datetime.timedelta(days=interval)
        elif status == 'ignoreWeek':
            self.layout['updateNextCheck'] = today + datetime.timedelta(days=7)
        elif status == 'ignoreYear':
            self.layout['updateNextCheck'] = today + datetime.timedelta(days=365)
        elif status == 'ignoreVersion':
            self.layout['updateNextCheck'] = today + datetime.timedelta(days=interval)
            self.layout['updateVersionCheck'] = buildDate

        self.layout.dump()
        
    def closeTab(self):
        indx = self.tabs.currentIndex()
        
        if indx > 0: #print need a better way to identify sql consoles...
            cons = self.tabs.currentWidget()
            
            cons.delayBackup()
            
            abandone = False
            
            if cons.sqlRunning:
                tabname = cons.tabname.rstrip(' *')
                log(f'CloseTab: Seems the sql still running in {tabname}, need to show a warning', 4)
                
                answer = utils.yesNoDialog('Warning', 'It seems the SQL is still running.\n\nAre you sure you want to close the console and abandon the execution?')
                            
                if not answer:
                    return False
                else:
                    abandone = True            

            status = cons.close(abandoneExecution=abandone)
            
            if status == True:
                self.statusbar.removeWidget(cons.indicator)
                self.tabs.removeTab(indx)
    
        
    def switchTab(self, index):
        self.tabs.setCurrentIndex(index)
        
    def keyPressEvent(self, event):
        #log('window keypress: %s' % (str(event.key())))

        modifiers = event.modifiers()

        if (modifiers == Qt.ControlModifier and event.key() == 82) or event.key() == Qt.Key_F5:
            log('reload request!')
            self.chartArea.reloadChart()
            
        elif modifiers == Qt.AltModifier and Qt.Key_0 < event.key() <= Qt.Key_9:
            self.switchTab(event.key() - Qt.Key_1)
            
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

        if hasattr(profiler, 'report'):
            profiler.report()
            
        if cfg('dev'):
            utils.configReportStats()

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

    def dumpLayout(self, closeTabs=True, crashMode=False, mode=None):
    # def dumpLayout(self, closeTabs=True, crashMode=False, abandonFlag=None):
        '''
            dumps a layout.yaml

            abandonFlag is a list to return abandon value if any
            
            in normal execution it will also trigger close of the consoles (with backup and disconnection)
            in crashMode (called on uncought exception) it is questionable if calling clos() makes any sense
        '''
    
        if self.primaryConf:
            connection = self.primaryConf.get('name')
        else:
            connection = None

        if self.layoutDumped:
            log('self.layoutDumped', 5)
            return
            
        if self.layout is None:
            log('self.layout is None', 5)
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
        
        if connection:
            self.layout['connectionName'] = connection
        else:
            if self.primaryConf:
                log('[?] Not possible point', 5)
                self.layout['connectionName'] = None
        
        self.layout['pos'] = [self.pos().x(), self.pos().y()]
        self.layout['size'] = [self.size().width(), self.size().height()]
        
        if SQLBrowserDialog.layout:
            self.layout['SQLBrowser.Layout'] = SQLBrowserDialog.layout
        
        # block the position on topof the file
                
        self.layout['mainSplitter'] = self.mainSplitter.sizes()
        self.layout['kpiSplitter'] = self.kpiSplitter.sizes()

        hostTableWidth = []
        KPIsTableWidth = []
        
        for i in range(self.hostTable.columnCount()):
            hostTableWidth.append(self.hostTable.columnWidth(i))

        for i in range(self.kpisTable.columnCount()):
            KPIsTableWidth.append(self.kpisTable.columnWidth(i))

        if self.chartArea.widget.legend:
            self.layout['legend'] = True
        else:
            self.layout['legend'] = False

        self.layout['hostTableWidth'] = hostTableWidth
        self.layout['KPIsTableWidth'] = KPIsTableWidth

        # print(self.pos().x(), self.pos().y())
        
        tabs = []
        
        self.layout['currentTab'] = self.tabs.currentIndex()
        
        tabname = None
        somethingRunning = False
        for i in range(self.tabs.count() -1, 0, -1):
            w = self.tabs.widget(i)
            if w.sqlRunning:
                somethingRunning = True
                tabname = w.tabname.rstrip(' *')
                break
                
        abandone = False
        
        if somethingRunning and not crashMode and mode != 'secondaryConnection':
            # log('There is something running, need to show a warning', 4)
            log(f'dumpLayout: Seems the sql still running in {tabname}, need to show a warning', 4)
            
            if mode == 'reconnect':
                wMessage = f'It\'s not recommended to reconnect having stuff running ({tabname})\nIt will hang untl finished anyway.\n\nProceed anyway?'
            else:
                wMessage = f'It seems there is something still running ({tabname}).\n\nAre you sure you want to exit and abandone the execution?'

            answer = utils.yesNoDialog('Warning', wMessage)
            if not answer:
                self.layoutDumped = False
                return False
            else:
                abandone = True
                # if abandonFlag is not None:
                #     abandonFlag.append('yep')
            
        if cfg('saveOpenTabs', True):
            for i in range(self.tabs.count() -1, 0, -1):
                w = self.tabs.widget(i)
                
                if isinstance(w, sqlConsole.sqlConsole):
                    
                    if not crashMode:       # during the crash processing explicit backups done outside before dumpLayout call
                        w.delayBackup()
                    
                    if w.fileName is not None or w.backup is not None:
                        pos = w.cons.textCursor().position()
                        block = w.cons.edit.verticalScrollBar().value()
                        
                        if w.backup:
                            bkp = os.path.abspath(w.backup)
                        else:
                            bkp = None
                        
                        tabs.append([w.fileName, bkp, pos, block])
                        
                    if closeTabs:
                        log('Do the close tab sequence (for one tab)', 5)
                        # self.statusbar.removeWidget(w.indicator) <<< this will fail when called from the parallel thread (if smth crashed in parallel thread)
                        w.close(cancelPossible=False, abandoneExecution=abandone)
                        self.tabs.removeTab(i)

            tabs.reverse()
                    
            if len(tabs) > 0:
                self.layout['tabs'] = tabs
            else:
                if 'tabs' in self.layout.lo:
                    self.layout.lo.pop('tabs')

        self.layout['variables'] = kpiDescriptions.vrsStr
        
        if kpiDescriptions.Variables.width:
            self.layout['variablesLO'] = {'width': kpiDescriptions.Variables.width, 'height': kpiDescriptions.Variables.height}
            
        log('--> dumpLayout vars: %s' % str(kpiDescriptions.vrsStr), 4)
        #print('dumping', self.layout['variables'])
        
        if 'running' in self.layout.lo:
            self.layout.lo.pop('running')
            
        if kpiDescriptions.customColors:
            colorsHTML = kpiDescriptions.colorsHTML(kpiDescriptions.customColors)
            self.layout['customColors'] = colorsHTML
        else:
            if 'customColors' in self.layout.lo:
                del self.layout.lo['customColors']
           
        self.layout.dump()
        
        return True
        
        
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
        
        log('Exit request...')
        
        log('before dump layout', 5)
        
        status = None
        
        if cfg('saveLayout', True):
            status = self.dumpLayout()
        
        if status == False:
            log('termination aborted....')
            return
            
        log('dump layout done', 5)
                    
        self.close()

    def menuReloadCustomSQLs(self):
        customSQLs.loadSQLs()
    
    def menuReloadCustomKPIs(self):
        '''
            delete and rebuild custom kpis
            
            1st step - delete existing custom kpis from KPIs lists and KPIsStyles
            2nd step - scann/add back new definitions
            
            by the way - delete stuff from data arrays?
        '''

        hosts = self.chartArea.widget.hosts
        
        ## step one: remove from the existing lists
        
        for h in range(len(hosts)):

            hostKPIsStyles = self.chartArea.hostKPIsStyles[h]
            hostKPIsList = self.chartArea.hostKPIsList[h]

            log(f'{h}: {hostKPIsList=}')
            
            for kpiName in list(hostKPIsStyles):
                kpi = hostKPIsStyles[kpiName]
                if kpi.get('sql'):
                    del(hostKPIsStyles[kpiName]) # delete style dict entry
                    hostKPIsList.remove(kpiName) # delete list entry
                
            # del host custom groups
            kpis_len = len(hostKPIsList)
            i = 0
            
            while i < kpis_len:
                if hostKPIsList[i][:1] == '.' and (i == len(hostKPIsList)-1 or hostKPIsList[i+1][:1] == '.'):
                    del(hostKPIsList[i])
                    kpis_len -= 1
                else:
                    i += 1


        ## load custom KPI definitions into temp structures...
        # this is executed just once, data loaded into old host/port structures
        # and then distributed/copied to new structures
        hostKPIs = []
        srvcKPIs = []
        kpiStylesNN = {'host':{}, 'service':{}}

        try:
            dpDBCustom.scanKPIsN(hostKPIs, srvcKPIs, kpiStylesNN)
        except Exception as e:
            self.chartArea.disableDeadKPIs()
            msgDialog('Custom KPIs Error', 'There were errors during custom KPIs load. Load of the custom KPIs STOPPED because of that.\n\n' + str(e))

        # now append detected custom KPIs back into lists
        for h in range(len(hosts)):
            hostKPIsStyles = self.chartArea.hostKPIsStyles[h]
            hostKPIsList = self.chartArea.hostKPIsList[h]

            if hosts[h]['port'] == '':
                hostKPIsList += hostKPIs
                for kpiName in kpiStylesNN['host'].keys():
                    hostKPIsStyles[kpiName] = kpiStylesNN['host'][kpiName]
            else:
                hostKPIsList += srvcKPIs
                for kpiName in kpiStylesNN['service'].keys():
                    hostKPIsStyles[kpiName] = kpiStylesNN['service'][kpiName]


            #not really sure if this one can be called twice...
            kpiDescriptions.clarifyGroups(hostKPIsStyles)
            log(f'{h}: {hostKPIsList=}')
            
        self.chartArea.widget.initPens()
        self.chartArea.widget.update()
        
        #trigger refill
        log('refill due to menuReloadCustomKPIs ', 5)
        self.kpisTable.refill(self.hostTable.currentRow())
        
        self.statusMessage('Custom KPIs reload finish', False)
    
    def menuReloadConfig(self):
        loadConfig()
        utils.initGlobalSettings()
        self.statusMessage('Configuration file reloaded.', False)
    
    def menuLayoutRestore(self):
        size = self.layout['save_size']
        spl = self.layout['save_mainSplitter']
        pos = self.layout['save_pos']
        
        if pos and spl and size:
            self.move(pos[0], pos[1])
            self.resize(size[0], size[1])
            self.mainSplitter.setSizes(spl)
        
        
    def menuLayout(self):
        self.layout['save_size'] = [self.size().width(), self.size().height()]
        self.layout['save_pos'] = [self.pos().x(), self.pos().y()]
        self.layout['save_mainSplitter'] = self.mainSplitter.sizes()
        
        self.statusMessage('Layout saved', False)
    
    def menuFont(self):
        id = QInputDialog

        sf = cfg('fontScale', 1)
        
        sf, ok = id.getDouble(self, 'Input the scaling factor', 'Scaling Factor', sf, 0, 5, 2)
        
        if ok:
            self.chartArea.widget.calculateMargins(sf)
            self.chartArea.adjustScale(sf)
        
    def menuAbout(self):
        abt = aboutDialog.About(self)
        abt.exec_()

    def menuSQLFolder(self):
        prc = QProcess()
        prc.startDetached('explorer.exe', [cfg('scriptsFolder', 'scripts')])
        
    def menuSQLBrowser(self):
        
        def extractFile(filename):
            try:
                with open(file) as f:
                    txt = f.read()
            except Exception as e:
                txt = '-- [E]: ' + str(e)
                
            return txt
        
        (result, file, offset) = SQLBrowserDialog.getFile(self)
        
        tabIndex = self.tabs.currentIndex()
        w = self.tabs.widget(tabIndex)
        
        if result == 'open' or (file and not isinstance(w, sqlConsole.sqlConsole)):
            # chart tab is actually PyQt5.QtWidgets.QSplitter, it does not have proper class on top
            console = self.newConsole(generateName=True)
            txt = extractFile(file)
            console.cons.insertTextS(txt)
            
            cursor = console.cons.textCursor()
            
            if offset:
                cursor.setPosition(offset, cursor.MoveAnchor)
            else:
                cursor.setPosition(0, cursor.MoveAnchor)
                
            console.cons.setTextCursor(cursor)
            
        elif result == 'edit':
            self.newConsole(filename=file, generateName=False)
            
        elif result == 'insert':
            if isinstance(w, sqlConsole.sqlConsole):
                txt = extractFile(file)

                if len(txt) >= 2:
                    if txt[-1] == '\n' and txt[-2] != '\n':
                        txt += '\n'
                    elif txt[-1] != '\n':
                        txt += '\n\n'

                pos = w.cons.textCursor().position()
                w.cons.insertTextS(txt)
                
                if offset:
                    pos += offset
                
                cursor = w.cons.textCursor()
                cursor.setPosition(pos, cursor.MoveAnchor)
                w.cons.setTextCursor(cursor)
            else:
                self.statusMessage('Warning: SQL Console needs to be open to use this option.', True)
    
    def menuVariablesHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/variables'))

    def menuVariables(self):
        # detect the sql source for currently selected custom KPI if any

        idx = None
        
        h = self.hostTable.currentRow()
        kpi = self.kpisTable.currentRow()
        
        if h >= 0 and kpi >= 0 and kpi < len(self.kpisTable.kpiNames):
            kpiName = self.kpisTable.kpiNames[kpi]
            
            ht = kpiDescriptions.hType(h, self.chartArea.widget.hosts)
                        
            if kpiName in kpiDescriptions.kpiStylesNN[ht]:
                idx = kpiDescriptions.kpiStylesNN[ht][kpiName].get('sql')
        
        # pass this value to be selected in variables UI
        vrs = kpiDescriptions.Variables(self, idx)

        vrs.exec_()
        
        if h >= 0:
            log('refill due to menuVariables ', 5)
            self.kpisTable.refill(h)
        
    def menuCSV(self):
        '''
            show the CSV import dialog in modal mode
            
            DBI is to be managed outside (here) connection to me banaged inside (there
        '''
        
        validDPs = [] # list of data providers with dpDB type, others are not suitable for import
        
        for dp in self.chartArea.ndp:
            if type(dp) == dpDB.dataProvider:
                validDPs.append(dp)
        
        if not validDPs:
            if datetime.datetime.now().second % 17 == 0:
                motivation = 'Stay safe, smile once in a while, It\'s not so bad.'
            else:
                motivation = 'Stay safe.'
            msgDialog('No database connection', 'You need to open connection to the database first.\n\n'+motivation, parent=self)
            return
        
        csvImport = csvImportDialog(parent=self, ndp=validDPs)
        csvImport.exec_()
        
        csvWidth = csvImport.size().width()
        csvHeight = csvImport.size().height()
        
        self.layout['csvImportLO'] = {'width': csvWidth, 'height': csvHeight}
        
        log('csvImport done')

    def menuSQLHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/sqlconsole'))

    def menuDocHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/doc'))

    def menuConfHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/config'))
        
    def menuChangelogHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/changelog'))

    def menuCustomConfHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/customKPI'))
    
    def menuContextSQLsConfHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/contextSQLs'))

    def menuTips(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/tips'))
        
    def menuDummy(self):
        dp = dpDummy.dataProvider() # generated data

        dpidx = self.chartArea.appendDP(dp)

        if cfg('saveKPIs', True):
            self.chartArea.initDP(dpidx, self.layout['kpis'])
        else:
            self.chartArea.initDP(dpidx)

    def menuConfig(self):
        self.processConnection()

    def menuConfigSecondary(self):
        self.processConnection(secondary=True)
        
    def updateWindowTitle(self):

        dp = None
        conf = self.primaryConf

        if self.chartArea.ndp:
            dp = self.chartArea.ndp[0]

        if conf is None and dp is None: # normally, only on start
            self.setWindowTitle('RybaFish Charts [%s]' % version)
            return

        if dp is None:
            dp = {}             # safity first

        sid = dp.dbProperties.get('sid', '')

        if conf:
            user = conf.get('user', '') + '@' + sid
        else:
            user = ''

        tenant = dp.dbProperties.get('tenant')

        if tenant and conf:
            windowStr = ('%s %s@%s' % (conf.get('user'), tenant, sid))
        else:
            if tenant:
                windowStr = tenant
            else:
                windowStr = user

        dbver = dp.dbProperties.get('version')

        if dbver:
            windowStr += ', ' + dbver

        windowStr += ' - ' + version

        if self.chartArea.widget.timeZoneDelta:
            tz = ' time: ' + utils.secondsToTZ(self.chartArea.widget.timeZoneDelta)
        else:
            tz = ''

        self.setWindowTitle(f'RybaFish Charts [{windowStr}]{tz}')


    def processConnection(self, secondary=False):
        '''
        shows the connection dialog and triggers connection
        both primary and secondary

        !! it will redifine self.primaryConnection configuration if not secondary

        initial connection shown in the dialog will be based on self.primaryConf
        if not yet connected in this session - primaryConnection loaded from layout.yaml
        '''

        log(f'processConnection, {secondary=}')
        
        conf = None

        if secondary:
            connConf = None
        else:
            if self.primaryConf is None:
                connConf = cfg('server')
            else:
                connConf = self.primaryConf
            
        if not connConf:
            connConf = {}
            
        if not connConf.get('name') and self.layout and not secondary:
            connConf['setToName'] = self.layout['connectionName']

        conf, ok = configDialog.Config.getConfig(connConf, self)

        conf['usage'] = None

        if ok and not secondary:
            self.primaryConf = conf.copy()
        
        if cfg('dev') and False:
            log(f'after connection dialog {connConf=}, {self.primaryConf}', 6) # #815
        
        if ok and conf['ok']:
        
            try:
            
                if cfg('saveLayout', True) and len(self.chartArea.widget.hosts):
                    log('connect dump layout')
                    
                    if secondary:
                        dumpMode = 'secondaryConnection'
                    else:
                        dumpMode = 'reconnect'

                    status = self.dumpLayout(closeTabs=False, mode=dumpMode)

                    # abandoneReturn = []
                    # self.dumplayout(closetabs = false, abandonflag=abandonereturn)

                    # if abandoneReturn:
                    #     abandon = True
                    # else:
                    #     abandon = False

                    if status == False:
                        # abort the reconnection, probably due to user cancel on warning (on running sql)
                        return

                    log('dump done')

                    self.layoutDumped = False

                if not secondary:
                    # need to disconnect open consoles first...
                    self.statusMessage('Disconnecing open consoles...', False)

                    for i in range(self.tabs.count()):

                        w = self.tabs.widget(i)

                        if isinstance(w, sqlConsole.sqlConsole) and w.conn is not None:
                            tabname = w.tabname.rstrip(' *')
                            '''
                            if abandon:
                                log(f'ignoring close for {tabname} due to abandone = True', 4) # bug #781
                                w.dbi = None
                                w.conn = None
                                w.connection_id = None
                                w.sqlRunning = False
                            else:
                                log(f'closing connection of {tabname}...')
                                w.disconnectDB()
                            '''
                            log(f'closing connection of {tabname}...')
                            w.disconnectDB()
                            w.indicator.status = 'disconnected'
                            w.indicator.repaint()
                            log('disconnected...')

                # close damn chart console
                
                if not secondary:
                    self.chartArea.cleanDPs()
                    self.configurations.clear()

                self.statusMessage('Connecting...', False)
                self.repaint()

                self.chartArea.setStatus('sync', True)
                
                # 2022-11-23
                #self.chartArea.dp = dpDB.dataProvider(conf) # db data provider
                dp = dpDB.dataProvider(conf) # db data provider

                if hasattr(dp, 'dbProperties'):
                    if dp.dbProperties.get('usage'):
                        usage = dp.dbProperties.get('usage')
                        log(f'usage detected, updating conf: {usage}', 5)

                        conf['usage'] = usage

                        if not secondary:
                            log('also updating the primaryConf prop', 5)
                            self.primaryConf['usage'] = usage

                dpidx = self.chartArea.appendDP(dp)
                self.configurations[dpidx] = conf

                log(f'Dataprovider added, idx: {dpidx}', 5)
                
                if 'disconnectSignal' in dp.options:
                    dp.disconnected.connect(self.chartArea.dpDisconnected)
                    
                if 'busySignal' in dp.options:
                    dp.busy.connect(self.chartArea.dpBusy)
                    
                self.chartArea.setStatus('idle')

                for i in range(self.tabs.count()):
                    w = self.tabs.widget(i)
                
                    if not secondary and isinstance(w, sqlConsole.sqlConsole):
                        w.config = conf

                if cfg('saveKPIs', True):
                    if self.layout and 'kpis' in self.layout.lo:
                        log('dumplayout, init kpis:' + str(self.layout['kpis']), 5)
                        self.chartArea.initDP(dpidx, self.layout['kpis'].copy())
                        
                        if self.layout['legend']:
                            self.chartArea.widget.legend = 'hosts'
                            
                        # self.kpisTable.host = None
                        log('removed explicit host = None (3), was the implicit one just performed??', 5)
                    else:
                        log('--> dumplayout, no kpis', 5)
                        self.chartArea.initDP(dpidx)
                        # self.kpisTable.host = None
                        log('removed explicit host = None (4), was the implicit one just performed??', 5)


                    '''
                    #397, 2021-06-17
                    starttime = datetime.datetime.now() - datetime.timedelta(seconds= 12*3600)
                    starttime -= datetime.timedelta(seconds= starttime.timestamp() % 3600)
                    
                    self.chartArea.fromEdit.setText(starttime.strftime('%Y-%m-%d %H:%M:%S'))
                    self.chartArea.toEdit.setText('')
                    '''
                        
                        
                else:
                    self.chartArea.initDP(dpidx)
                    
                   
                '''
                if not secondary:
                    log('refill due to non-secondary connection', 5)
                    #self.hostTable.setCurrentCell(0, 0)
                    #self.kpisTable.refill(self.hostTable.currentRow())
                    log('now this logic moved inside initDP', 5)
                '''
                
                if cfg('saveKPIs', True):
                    if self.layout and 'kpis' in self.layout.lo:
                        self.statusMessage('Loading saved kpis...', True)

                if hasattr(dp, 'dbProperties'):
                    '''
                    
                    moved inside inidDP()
                    
                    if 'timeZoneDelta' in self.chartArea.dp.dbProperties:
                        self.chartArea.widget.timeZoneDelta = self.chartArea.dp.dbProperties['timeZoneDelta']
                    else:
                        self.chartArea.widget.timeZoneDelta = 0
                    '''
                        
                    if not conf['noreload']:
                        log('reload from menuConfig #1', 4)
                        self.chartArea.reloadChart()
                        
                else:
                    log('reload from menuConfig #2', 4)
                    self.chartArea.reloadChart()
                    
                # if 'sid' in dp.dbProperties:
                #     sid = dp.dbProperties['sid']
                # else:
                #     sid = ''

                sid = dp.dbProperties.get('sid', '')
                propStr = conf['user'] + '@' + sid
                
                # sid = dp.dbProperties.get('sid', '')
                # tenant = dp.dbProperties.get('tenant')

                # if tenant:
                #     windowStr = ('%s %s@%s' % (conf['user'], tenant, sid))
                # else:
                #     windowStr = propStr

                # dbver = dp.dbProperties.get('version')

                # if dbver:
                #     windowStr += ', ' + dbver

                # windowStr += ' - ' + version

                if not secondary:
                    self.tabs.setTabText(0, propStr)
                    self.updateWindowTitle()
                # self.setWindowTitle('RybaFish Charts [%s]' % windowStr)
                
                #setup keep alives
                
                if cfg('keepalive'):
                    try:
                        keepalive = int(cfg('keepalive'))
                        dp.enableKeepAlive(self, keepalive)
                    except ValueError:
                        log('wrong keepalive setting: %s' % (cfg('keepalive')))
                                
            except dbException as e:
                self.chartArea.indicator.status = 'disconnected'
                log('Connect or init error:')
                if hasattr(e, 'message'):
                    log(e.message)
                else:
                    log(e)
                    
                msgBox = QMessageBox(self)
                msgBox.setWindowTitle('Connection error')
                msgBox.setText('Connection failed: %s ' % (str(e)))
                iconPath = resourcePath('ico', 'favicon.png')
                msgBox.setWindowIcon(QIcon(iconPath))
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.exec_()
                
                self.statusMessage('', False)

            '''
            except Exception as e:
                log('Init exception NOT related to DB')
                log(str(e))

                msgBox = QMessageBox(self)
                msgBox.setWindowTitle('Error')
                msgBox.setText('Init failed: %s \n\nSee more deteails in the log file.' % (str(e)))
                iconPath = resourcePath('ico', 'favicon.png')
                msgBox.setWindowIcon(QIcon(iconPath))
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.exec_()
                
                self.statusMessage('', False)
            '''
                    
        else:
            # cancel or parsing error
            
            if ok and conf['ok'] == False: #it's connection string dict in case of [Cancel]
                msgBox = QMessageBox(self)
                msgBox.setWindowTitle('Connection string')
                
                if conf.get('error'):
                    msgText = conf['error']
                else:
                    msgText = 'Could not start the connection. Please check the connection string: host, port, etc.'
                    
                msgBox.setText(msgText)
                iconPath = resourcePath('ico', 'favicon.png')
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
    
    
    def newConsole(self, filename=None, generateName=False):
        conf = self.primaryConf
        
        self.statusMessage('Connecting console...', True)
        
        if generateName == True:
            tabName = self.generateTabName()
        else:
            tabName = 'sqlopen'
        
        try:
            console = sqlConsole.sqlConsole(self, conf, tabName)
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
        
        console.alertSignal.connect(self.popUp)
        console.tabSwitchSignal.connect(self.switchTab)
        console.sqlBrowserSignal.connect(self.menuSQLBrowser)
        console.fontUpdateSignal.connect(self.syncConsoleFonts)
        
        ind = indicator()
        console.indicator = ind
        
        ind.iClicked.connect(console.reportRuntime)
        
        # ind.iToggle.connect(console.updateRuntime)

        self.statusbar.addPermanentWidget(ind)
        
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        
        if filename:
            console.openFile(filename)
        
        if self.layout == None:
            # switch backups off to avoid conflicts...
            console.noBackup = True
            
        console.cons.setFocus()
        
        return console
        
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
        
            filename = os.path.abspath(filename)

            if filename in openfiles:
                # the file is already open
                idx = openfiles[filename]
                
                self.tabs.setCurrentIndex(idx)
                continue
                
            self.newConsole(filename=filename, generateName=False)

    #def populateConsoleTab(self):
    
    def generateTabName(self):
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
                
        return tname
        

    def openSecondaryConsole(self, dpidx):
        if not self.configurations:
            log('[W] no configurations found!', 2)

        if dpidx not in self.configurations or True:
            log(f'[!] {dpidx} is not known configuration')
            log(f'known indexes are: {self.configurations.keys()}')

        conf = self.configurations[dpidx]
        self.sqlConsoleCall(configuration=conf, dpidx=dpidx)

    def sqlConsoleCall(self, configuration=None, dpidx=None):
        # to be called from menuSQLConsole (menu signal) and my code (secondary connection)
        conf = None
        dpid = None

        if configuration is None:
            log('menuSQLConsole...')
            secondary = False
            conf = self.primaryConf
        else:
            if dpidx is not None:
                dp = self.chartArea.ndp[dpidx]
                prop = dp.dbProperties
                dpid = str(prop.get('tenant', ''))
            else:
                dpid = '?? '+configuration.get('dbi') + ' / ' + configuration.get('host')+':'+configuration('port')

            user = configuration.get('user')

            if user:
                dpid += f' ({user})'

            log('menuSQLConsole, secondary connection...')

            secondary = True
            conf = configuration.copy()
            conf['secondary'] = True

        if conf is None:
            self.statusMessage('No configuration...', False)
            return

        self.statusMessage('Connecting...', True)

        ind = indicator()
        self.statusbar.addPermanentWidget(ind)

        ind.status = 'sync'
        ind.repaint()

        tname = self.generateTabName()

        try:
            console = sqlConsole.sqlConsole(self, conf, tname, dpid=dpid) # self = window
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

        # ind.iToggle.connect(console.updateRuntime)

        console.nameChanged.connect(self.changeActiveTabName)
        console.cons.closeSignal.connect(self.closeTab)
        self.tabs.addTab(console, tname)

        console.selfRaise.connect(self.raiseTab)
        console.statusMessage.connect(self.statusMessage)

        console.alertSignal.connect(self.popUp)
        console.tabSwitchSignal.connect(self.switchTab)
        console.sqlBrowserSignal.connect(self.menuSQLBrowser)
        console.fontUpdateSignal.connect(self.syncConsoleFonts)

        self.tabs.setCurrentIndex(self.tabs.count() - 1)

        if console.unsavedChanges:
            # if autoloaded from backup
            # cannot be triggered from inside as signal not connected on __init__
            self.changeActiveTabName(console.tabname + ' *')

        if self.layout == None:
            # no backups to avoid conflicts...
            console.noBackup = True

        console.cons.setFocus()

        self.statusMessage('', False)
        console.indicator.status = 'idle'
        console.indicator.repaint()
        
    def menuSQLConsole(self):
        self.sqlConsoleCall()

    def menuColorize(self):
        if cfg('colorize', False) == False:
            utils.cfgSet('colorize', True)
            
        else:
            utils.cfgSet('colorize', False)
            
        self.chartArea.widget.update()
    
    def menuTZ(self):

            i = self.hostTable.currentRow()
            if len(self.chartArea.widget.hosts) > 0:
                dpidx = self.chartArea.widget.hosts[i]['dpi']
            else:
                self.statusMessage('Seems there are no hosts/data providers: you need to connect first', True)
                return

            self.chartArea.adjustTimeZones(dpidx)
            self.updateWindowTitle()

    def menuEss(self):
        def reinitDPs():
            '''
                local method to re-init relevant DPs (HDB)
            '''
            for dpidx in range(len(self.chartArea.ndp)):
                dp = self.chartArea.ndp[dpidx]
                if type(dp) == dpDB.dataProvider and dp.dbi.name == 'HDB':
                    log(f're-init dp[{dpidx}], ({dp.dbi.name})')
                    self.chartArea.initDP(dpidx, kpis.copy(), message = 'Re-initializing hosts information...')
                else:
                    log(f'dp[{dpidx}] skipped, {type(dp)}')
    
        if cfg('ess', False) == False:
            utils.cfgSet('ess', True)
            self.essAct.setText('Switch back to m_load_history...')
            kpis = self.formatKPIs()
            reinitDPs()
        
            self.chartArea.setStatus('sync', True)
                        
            # self.kpisTable.host = None
            log('removed explicit host = None (1), was the implicit one just performed??', 5)

            self.statusMessage('Now reload...', True)
            self.chartArea.reloadChart()
            self.chartArea.setStatus('idle', True)
        
        else:
            utils.cfgSet('ess', False)
            self.essAct.setText('Switch to ESS load history')
            self.essAct.setStatusTip('Switches from online m_load_history views to ESS tables, will trigger hosts re-init')

            kpis = self.formatKPIs()
        
            self.chartArea.setStatus('sync', True)
            #self.chartArea.initDP(kpis.copy(), message = 'Re-initializing hosts information...')
            reinitDPs()

            # self.kpisTable.host = None
            log('removed explicit host = None (2), was the implicit one just performed??', 5)
            
            self.statusMessage('Now reload...', True)
            self.chartArea.reloadChart()
            self.chartArea.setStatus('idle', True)
    
    def menuImport(self):
        fname = QFileDialog.getOpenFileNames(self, 'Import nameserver_history.trc...',  None, 'Import nameserver history trace (*.trc)')
        log(fname[0])
        
        
        if len(fname[0]) > 0:
        
            fileUTCshift = cfg('import_timezone_offset')
            #self.chartArea.dp = dpTrace.dataProvider(fname[0], timezone_offset=fileUTCshift) # db data provider
            #self.chartArea.initDP(message='Parsing the trace file, will take a minute or so...')

            self.chartArea.cleanDPs()
            self.configurations.clear()
            # new style, #739
            dp = dpTrace.dataProvider(fname[0], timezone_offset=fileUTCshift) # db data provider
            dpidx = self.chartArea.appendDP(dp)
            self.chartArea.initDP(dpidx, message='Parsing the trace file, will take a minute or so...')

            toTime = self.chartArea.widget.hosts[0]['to']
            fromTime = toTime - datetime.timedelta(hours = 10)
            
            self.updateWindowTitle()

            self.chartArea.toEdit.setText(toTime.strftime('%Y-%m-%d %H:%M:%S'))
            self.chartArea.fromEdit.setText(fromTime.strftime('%Y-%m-%d %H:%M:%S'))
            
            self.chartArea.reloadChart()

    def menuSQLToolbar(self):
        state = self.tbAct.isChecked()
        if state:
            utils.cfgPersist('sqlConsoleToolbar', True, self.layout.lo)
        else:
            utils.cfgPersist('sqlConsoleToolbar', False, self.layout.lo)
            
        for i in range(self.tabs.count() -1, 0, -1):
            w = self.tabs.widget(i)
            if isinstance(w, sqlConsole.sqlConsole):
                if state:
                    w.toolbarEnable()
                else:
                    w.toolbarDisable()

            
            
    def popUp(self):
    
        state = self.windowState()

        self.setWindowState(state & ~Qt.WindowMinimized | Qt.WindowActive)
        
        if not self.isActiveWindow():
            self.show()           # this one really brings to foreground
            self.activateWindow() # this one supposed to move focus
    
    def raiseTab(self, tab):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            
            if w is tab:
                self.tabs.setCurrentIndex(i)
                break
    
    
    '''
    def chartIndicator(self, status):
         self.chartArea.indicator.status = 'disconnected'
    '''
    
    def setTabName(self, str):
        self.tabs.setTabText(0, str)
        
    def syncConsoleFonts(self, mode):
        if mode == 'console':
            fontSize = cfg('console-fontSize')
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if isinstance(w, sqlConsole.sqlConsole):
                    w.cons.zoomFont(mode='=', tosize=fontSize)
        if mode == 'resultSet':
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if isinstance(w, sqlConsole.sqlConsole):
                    w.resultFontUpdate()


    def initUI(self):
    
        global rybaSplash
        
        #QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, False)
        #QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, False) 

        if cfg('saveLayout', True):
            self.layout = Layout(True)
            
            if not self.layout['nomode13']:
                utils.purgeLogs(mode=13)
                self.layout['nomode13'] = True

            if self.layout['variables']:
                # kpiDescriptions.vrs = self.layout['variables']
                log('-----addVars hslWindow-----', component='variables')
                
                try:
                    for idx in self.layout['variables']:
                        kpiDescriptions.addVars(idx, self.layout['variables'][idx])
                except utils.vrsException as e:
                    log(str(e), 2)
                    
                log('-----addVars hslWindow-----', component='variables')
            
            if 'settings' in self.layout.lo:
                for setting in self.layout.lo['settings']:
                    utils.cfgSet(setting, self.layout.lo['settings'][setting])
                    
            if 'customColors' in self.layout.lo:
                kpiDescriptions.colorsHTMLinit(self.layout.lo['customColors'])
            
            if self.layout['variablesLO']:
                kpiDescriptions.Variables.width = self.layout['variablesLO']['width']
                kpiDescriptions.Variables.height = self.layout['variablesLO']['height']

            if self.layout['csvImportLO']:
                csvImportDialog.width = self.layout['csvImportLO']['width']
                csvImportDialog.height = self.layout['csvImportLO']['height']
            
            if self.layout['SQLBrowser.Layout']:
                SQLBrowserDialog.layout = self.layout['SQLBrowser.Layout']
                
            if self.layout['running']:

                try:
                    import pyi_splash
                    pyi_splash.close()
                    rybaSplash = False
                except:
                    pass

                answer = utils.yesNoDialog('Warning', 'Another RybaFish is already running, all the layout and autosave features will be disabled.\n\nExit now?', ignore = True)
                
                if answer == True or answer is None:
                    sys.exit(0)

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

        #link kpisTable structures to the chartArea
        kpisTable.hostKPIsList = self.chartArea.hostKPIsList
        kpisTable.hostKPIsStyles = self.chartArea.hostKPIsStyles
        
        # bottm part left+right
        self.kpiSplitter = QSplitter(Qt.Horizontal)
        self.kpiSplitter.addWidget(self.hostTable)
        self.kpiSplitter.addWidget(kpisTable)
        self.kpiSplitter.setSizes([200, 500])
        
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
                self.kpiSplitter.setSizes([200, 500])
            
            
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
        #self.chartArea.indSignal.connect(self.chartIndicator)
        ind.iClicked.connect(self.chartArea.indicatorSignal)
        
        # as console is fully sync it does not have runtime and corresponding signals
        
        self.setCentralWidget(self.tabs)
        
        # service stuff
        self.statusbar = self.statusBar()
        self.statusbar.addPermanentWidget(ind)

        #menu
        iconPath = resourcePath('ico', 'favicon.png')

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

        configSecAct = QAction('Secondary connection', self)
        configSecAct.setStatusTip('Open a secondary connection')
        configSecAct.triggered.connect(self.menuConfigSecondary)

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
        
        if cfg('experimental'):
            fileMenu.addAction(configSecAct)

        fileMenu.addAction(importAct)
        
        fileMenu.addAction(sqlConsAct)
        fileMenu.addAction(openAct)
        
        fileMenu.addAction(saveAct)
        
        if cfg('dev'):
            fileMenu.addAction(dummyAct)

        fileMenu.addAction(exitAct)
        
        actionsMenu = menubar.addMenu('&Actions')
        
        if cfg('experimental'):
            fontAct = QAction('&Adjust Fonts', self)
            fontAct.setStatusTip('Adjust margins after font change (for example after move to secondary screen)')
            fontAct.triggered.connect(self.menuFont)
            actionsMenu.addAction(fontAct)

        varsMenu = menubar.addMenu('Variables')
        
        varsAct = QAction('Show variables', self)
        varsAct.setShortcut('Alt+V')
        varsAct.setStatusTip('Shows current variables for all KPIs')
        varsAct.triggered.connect(self.menuVariables)
        
        varsMenu.addAction(varsAct)

        vhelpAct = QAction('Variables help', self)
        vhelpAct.setStatusTip('Go to RybaFish.net variables tutorial')
        vhelpAct.triggered.connect(self.menuVariablesHelp)

        varsMenu.addAction(vhelpAct)

        sqlMenu = menubar.addMenu('SQL')
        sqlAct = QAction('SQL Browser', self)
        sqlAct.setShortcut('F11')
        sqlAct.setStatusTip('Open SQL Browser')
        sqlAct.triggered.connect(self.menuSQLBrowser)
        sqlMenu.addAction(sqlAct)

        sqlFolderAct = QAction('Open scripts folder', self)
        sqlFolderAct.setStatusTip('Open SQL folder in explorer (ms windows only...)')
        sqlFolderAct.triggered.connect(self.menuSQLFolder)
        sqlMenu.addAction(sqlFolderAct)
        

        self.tzAct = QAction('Manage Time Zones', self)
        layoutMenu = menubar.addMenu('&Layout')
        
        layoutAct = QAction('Save window layout', self)
        layoutAct.setStatusTip('Saves the window size and position to be able to restore it later')
        layoutAct.triggered.connect(self.menuLayout)
        
        layoutMenu.addAction(layoutAct)

        layoutAct = QAction('Restore window layout', self)
        layoutAct.setStatusTip('Restores the window size and position')
        layoutAct.triggered.connect(self.menuLayoutRestore)
        
        layoutMenu.addAction(layoutAct)
            
        # issue #255
        reloadConfigAct = QAction('Reload &Config', self)
        reloadConfigAct.setStatusTip('Reload configuration file. Note: some values used during the connect or other one-time-actions (restart required).')
        reloadConfigAct.triggered.connect(self.menuReloadConfig)
        actionsMenu.addAction(reloadConfigAct)

        reloadCustomSQLsAct = QAction('Reload Context &SQLs', self)
        reloadCustomSQLsAct.setStatusTip('Reload definition of context SQLs')
        reloadCustomSQLsAct.triggered.connect(self.menuReloadCustomSQLs)
        
        actionsMenu.addAction(reloadCustomSQLsAct)

        reloadCustomKPIsAct = QAction('Reload Custom &KPIs', self)
        reloadCustomKPIsAct.setStatusTip('Reload definition of custom KPIs')
        reloadCustomKPIsAct.setShortcut('Ctrl+K')
        reloadCustomKPIsAct.triggered.connect(self.menuReloadCustomKPIs)

        actionsMenu.addAction(reloadCustomKPIsAct)

        self.colorizeAct = QAction('Colorize KPIs', self)
        self.colorizeAct.setStatusTip('Ignore standard KPI styles and use raduga colors instead')
        self.colorizeAct.triggered.connect(self.menuColorize)

        actionsMenu.addAction(self.colorizeAct)

        self.tbAct = QAction('SQL Console Toolbar', self, checkable=True)
        self.tbAct.setStatusTip('Toggle the toolbar in SQL consoles.')
        
        if cfg('sqlConsoleToolbar', True):
            self.tbAct.setChecked(True)
            
        self.tbAct.triggered.connect(self.menuSQLToolbar)

        sqlMenu.addAction(self.tbAct)

        self.tzAct.setStatusTip('View/adjust data provider (server) time zone')
        if cfg('dev'):
            self.tzAct.setShortcut('Alt+Z')
        self.tzAct.triggered.connect(self.menuTZ)

        actionsMenu.addAction(self.tzAct)

        self.essAct = QAction('Switch to ESS load history', self)
        self.essAct.setStatusTip('Switches from online m_load_history views to ESS tables')
        self.essAct.triggered.connect(self.menuEss)

        actionsMenu.addAction(self.essAct)

        csvAct = QAction('Import CSV-file', self)
        csvAct.setStatusTip('Import CSV file into database')
        # csvAct.setShortcut('Alt+F12')
        csvAct.triggered.connect(self.menuCSV)
        
        actionsMenu.addSeparator()
        actionsMenu.addAction(csvAct)

        # help menu part
        aboutAct = QAction(QIcon(iconPath), '&About', self)
        aboutAct.setStatusTip('About this app')
        aboutAct.triggered.connect(self.menuAbout)

        confSQLAct = QAction('SQL Console Reference', self)
        confSQLAct.setStatusTip('Short SQL Console reference')
        confSQLAct.triggered.connect(self.menuSQLHelp)

        docHelpAct = QAction('Documentation', self)
        docHelpAct.setStatusTip('Visit user reference page')
        docHelpAct.triggered.connect(self.menuDocHelp)

        confHelpAct = QAction('Configuration', self)
        confHelpAct.setStatusTip('Configuration options description')
        confHelpAct.triggered.connect(self.menuConfHelp)

        confCustomHelpAct = QAction('Custom KPIs', self)
        confCustomHelpAct.setStatusTip('Short manual on custom KPIs')
        confCustomHelpAct.triggered.connect(self.menuCustomConfHelp)

        confContextHelpAct = QAction('Context SQLs', self)
        confContextHelpAct.setStatusTip('Short manual on context SQLs')
        confContextHelpAct.triggered.connect(self.menuContextSQLsConfHelp)

        confTipsAct = QAction('Tips and tricks', self)
        confTipsAct.setStatusTip('Tips and tricks description')
        confTipsAct.triggered.connect(self.menuTips)

        confChangeAct = QAction('Changelog', self)
        confChangeAct.setStatusTip('Changelog and recent features')
        confChangeAct.triggered.connect(self.menuChangelogHelp)
        
        helpMenu = menubar.addMenu('&Help')
        
        helpMenu.addAction(docHelpAct)
        helpMenu.addAction(confSQLAct)
        helpMenu.addAction(confHelpAct)
        helpMenu.addAction(confCustomHelpAct)
        helpMenu.addAction(confContextHelpAct)
        helpMenu.addAction(confTipsAct)
        helpMenu.addAction(confChangeAct)
        helpMenu.addAction(aboutAct)
        
        # finalization        

        if self.layout is not None and self.layout['pos'] and self.layout['size']:
            pos = self.layout['pos']
            size = self.layout['size']
            
            log('Screen Y DPI, logical: %i, physical %i' % (self.logicalDpiY(), self.physicalDpiY()))
            log('Screen X DPI, logical: %i, phisical %i' % (self.logicalDpiX(), self.physicalDpiX()))
            
            r = QRect(pos[0], pos[1], size[0], size[1])

            if QApplication.desktop().screenCount() == 1:
                # only when just one screen is available...
                if not QApplication.desktop().screenGeometry().contains(r) and not cfg('dontAutodetectScreen'):
                    #the window will not be visible so jump to the main screen:
                    (pos[0], pos[1]) = (100, 50)
            
            self.move(pos[0], pos[1])
            self.resize(size[0], size[1])
        else:
            self.setGeometry(200, 200, 1400, 800)
        
        self.updateWindowTitle()
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
                
                console.alertSignal.connect(self.popUp)
                console.tabSwitchSignal.connect(self.switchTab)
                console.sqlBrowserSignal.connect(self.menuSQLBrowser)
                console.fontUpdateSignal.connect(self.syncConsoleFonts)
                
                ind.iClicked.connect(console.reportRuntime)
                
                # ind.iToggle.connect(console.updateRuntime)
                
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
                        console.cons.setFocus()
                        
            indx = self.layout['currentTab']
                        
            if isinstance(indx, int):
                self.tabs.setCurrentIndex(indx)

                w = self.tabs.widget(indx)
                
                #if isinstance(w, sqlConsole.sqlConsole):
                #    w.cons.setFocus()
                
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
        #kpisTable.adjustScale.connect(self.chartArea.adjustScale)
        kpisTable.setScale.connect(self.chartArea.setScale)
        kpisTable.vrsUpdate.connect(self.chartArea.repaintRequest)
        kpisTable.refreshRequest.connect(self.chartArea.repaintRequest)

        # host table row change signal
        self.hostTable.hostChanged.connect(kpisTable.refill)

        self.hostTable.adjustTimeZones.connect(self.chartArea.adjustTimeZones)
        self.hostTable.openSecondaryConsole.connect(self.openSecondaryConsole)

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
        
        #self.chartArea.setFocus() set above
        
        log('init finish()')

        customSQLs.loadSQLs()

        # offline console tests
        
        if cfg('developmentMode'):
        
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
            
            console.alertSignal.connect(self.popUp)
            console.tabSwitchSignal.connect(self.switchTab)
            console.sqlBrowserSignal.connect(self.menuSQLBrowser)
            console.fontUpdateSignal.connect(self.syncConsoleFonts)
            
            self.tabs.setCurrentIndex(self.tabs.count() - 1)

            self.SQLSyntax = SQLSyntaxHighlighter(console.cons.document())
            #console.cons.setPlainText('select * from dummy;\n\nselect \n    *\n    from dummy;\n\nselect * from m_host_information;');

            ind = indicator()
            console.indicator = ind
            self.statusbar.addPermanentWidget(ind)
            
            ind.iClicked.connect(console.reportRuntime)

            # ind.iToggle.connect(console.updateRuntime)
                            
            console.dummyResultTable()
        
        self.statusMessage('', False)
        
        if self.chartArea.dp:
            assert False, 'Should not ever reach this self.chartArea.initDP()'
            self.chartArea.initDP()
