from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFrame, 
    QSplitter, QStyleFactory, QTableWidget,
    QTableWidgetItem, QPushButton, QAbstractItemView,
    QCheckBox, QMainWindow, QAction, QMenu, QFileDialog,
    QMessageBox, QTabWidget, QPlainTextEdit, QInputDialog, 
    QApplication
    )
    
from PyQt5.QtGui import QPainter, QIcon, QDesktopServices

from PyQt5.QtCore import Qt, QUrl, QEvent, QRect, QProcess

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
from utils import log
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

from profiler import profiler

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
                log('Sems the sql still running, need to show a warning', 4)
                
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
    
        if self.connectionConf:
            connection = self.connectionConf.get('name')
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
            if self.connectionConf:
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
        
        self.layout['hostTableWidth'] = hostTableWidth
        self.layout['KPIsTableWidth'] = KPIsTableWidth

        # print(self.pos().x(), self.pos().y())
        
        tabs = []
        
        self.layout['currentTab'] = self.tabs.currentIndex()
        
        
        somethingRunning = False
        for i in range(self.tabs.count() -1, 0, -1):
            w = self.tabs.widget(i)
            if w.sqlRunning:
                somethingRunning = True
                break
                
        abandone = False
        
        if somethingRunning:
            log('There is something running, need to show a warning', 4)
            
            answer = utils.yesNoDialog('Warning', 'It seems there is something still running.\n\nAre you sure you want to exit and abandone the execution?')
                        
            if not answer:
                self.layoutDumped = False
                return False
            else:
                abandone = True
            
        if cfg('saveOpenTabs', True):
            for i in range(self.tabs.count() -1, 0, -1):
                w = self.tabs.widget(i)
                
                if isinstance(w, sqlConsole.sqlConsole):
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
                        #log('close tab call...', 5)
                        w.close(None, abandoneExecution = abandone)

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
    
        kpiStylesNN = kpiDescriptions.kpiStylesNN
        
        for type in ('host', 'service'):
            for kpiName in list(kpiStylesNN[type]):

                kpi = kpiStylesNN[type][kpiName]
                
                if kpi['sql'] is not None:
                    del(kpiStylesNN[type][kpiName])
                    
                    if type == 'host':
                        if kpiName in self.chartArea.hostKPIs:
                            self.chartArea.hostKPIs.remove(kpiName)
                    else:
                        if kpiName in self.chartArea.srvcKPIs:
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
        log('menuReloadCustomKPIs refill', 5)
        self.kpisTable.refill(self.hostTable.currentRow())
        
        self.statusMessage('Custom KPIs reload finish', False)
    
    def menuReloadConfig(self):
        loadConfig()
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
            log('menuVariables refill', 5)
            self.kpisTable.refill(h)
        
    def menuSQLHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/sqlconsole'))

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
            
        if not connConf:
            connConf = {}
            
        if not connConf.get('name') and self.layout:
            connConf['setToName'] = self.layout['connectionName']
            
        conf, ok = configDialog.Config.getConfig(connConf, self)
        
        log('config dialog, ok? %s' % str(ok), 5)
        
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
                        
                # close damn chart console

                if self.chartArea.dp is not None:
                    self.chartArea.dp.close()
                    del self.chartArea.dp
                    self.chartArea.refreshCB.setCurrentIndex(0) # will disable the timer on this change

                self.statusMessage('Connecting...', False)
                self.repaint()

                self.chartArea.setStatus('sync', True)
                
                if dbi.dbinterface is not None:
                    dbi.dbinterface.destroy()
                    
                self.chartArea.dp = dpDB.dataProvider(conf) # db data provider
                
                if 'disconnectSignal' in self.chartArea.dp.options:
                    self.chartArea.dp.disconnected.connect(self.chartArea.dpDisconnected)
                    
                if 'busySignal' in self.chartArea.dp.options:
                    self.chartArea.dp.busy.connect(self.chartArea.dpBusy)
                    
                self.chartArea.setStatus('idle')

                for i in range(self.tabs.count()):
                
                    w = self.tabs.widget(i)
                
                    if isinstance(w, sqlConsole.sqlConsole):
                        w.config = conf
                        
                if cfg('saveKPIs', True):
                    if self.layout and 'kpis' in self.layout.lo:
                        log('--> dumplayout, init kpis:' + str(self.layout['kpis']), 5)
                        self.chartArea.initDP(self.layout['kpis'].copy())
                        
                        if self.layout['legend']:
                            self.chartArea.widget.legend = 'hosts'
                            
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
                    
                if 'sid' in self.chartArea.dp.dbProperties:
                    sid = self.chartArea.dp.dbProperties['sid']
                else:
                    sid = ''
                
                propStr = conf['user'] + '@' + sid
                
                tenant = self.chartArea.dp.dbProperties.get('tenant')
                
                if tenant:
                    windowStr = ('%s %s@%s' % (conf['user'], tenant, sid))
                else:
                    windowStr = propStr
                    
                dbver = self.chartArea.dp.dbProperties.get('version')
                    
                if dbver:
                    windowStr += ', ' + dbver
                
                windowStr += ' - ' + version
                
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
                msgBox.setText('Could not start the connection. Please check the connection string: host, port, etc.')
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
        conf = self.connectionConf
        
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
        
        ind = indicator()
        console.indicator = ind
        
        ind.iClicked.connect(console.reportRuntime)
        
        ind.iToggle.connect(console.updateRuntime)
                    
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
        
        tname = self.generateTabName()
                
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
        
        console.alertSignal.connect(self.popUp)
        console.tabSwitchSignal.connect(self.switchTab)
        console.sqlBrowserSignal.connect(self.menuSQLBrowser)
        
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
            
    
    def menuColorize(self):
        if cfg('colorize', False) == False:
            utils.cfgSet('colorize', True)
            
        else:
            utils.cfgSet('colorize', False)
            
        self.chartArea.widget.update()
    
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
        
            fileUTCshift = cfg('import_timezone_offset')
            self.chartArea.dp = dpTrace.dataProvider(fname[0], timezone_offset=fileUTCshift) # db data provider
            
            #wrong approach, #697
            #self.chartArea.dp.dbProperties = {}
            #self.chartArea.dp.dbProperties['timeZoneDelta'] = -3*3600
            
            self.chartArea.initDP(message = 'Parsing the trace file, will take a minute or so...')

            toTime = self.chartArea.widget.hosts[0]['to']
            fromTime = toTime - datetime.timedelta(hours = 10)
            
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
        
    def initUI(self):
    
        global rybaSplash
        
        #QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, False)
        #QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, False) 

        if cfg('saveLayout', True):
            self.layout = Layout(True)
            
            if self.layout['variables']:
                # kpiDescriptions.vrs = self.layout['variables']
                log('-----addVars hslWindow-----')
                
                try:
                    for idx in self.layout['variables']:
                        kpiDescriptions.addVars(idx, self.layout['variables'][idx])
                except utils.vrsException as e:
                    log(str(e), 2)
                    
                log('-----addVars hslWindow-----')
            
            if 'settings' in self.layout.lo:
                for setting in self.layout.lo['settings']:
                    utils.cfgSet(setting, self.layout.lo['settings'][setting])
                    
            if 'customColors' in self.layout.lo:
                kpiDescriptions.colorsHTMLinit(self.layout.lo['customColors'])
            
            if self.layout['variablesLO']:
                kpiDescriptions.Variables.width = self.layout['variablesLO']['width']
                kpiDescriptions.Variables.height = self.layout['variablesLO']['height']
            
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

        varsMenu = menubar.addMenu('Variables')
        
        varsAct = QAction('Show variables', self)
        varsAct.setShortcut('Alt+V')
        varsAct.setStatusTip('Shows current variables for all KPIs')
        varsAct.triggered.connect(self.menuVariables)
        
        varsMenu.addAction(varsAct)

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

        actionsMenu.addAction(self.tbAct)
        
        self.essAct = QAction('Switch to ESS load history', self)
        self.essAct.setStatusTip('Switches from online m_load_history views to ESS tables')
        self.essAct.triggered.connect(self.menuEss)

        actionsMenu.addAction(self.essAct)

        # help menu part
        aboutAct = QAction(QIcon(iconPath), '&About', self)
        aboutAct.setStatusTip('About this app')
        aboutAct.triggered.connect(self.menuAbout)

        confSQLAct = QAction('SQL Console Reference', self)
        confSQLAct.setStatusTip('Short SQL Console reference')
        confSQLAct.triggered.connect(self.menuSQLHelp)

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
        
        
        self.setWindowTitle('RybaFish Charts [%s]' % version)
        
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
        