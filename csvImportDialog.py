import re
import os.path

from PyQt5.QtWidgets import (QPushButton, QDialog, QWidget, QLineEdit, QAction, QStyle, QCheckBox,
                             QHBoxLayout, QVBoxLayout, QApplication, QLabel, QStatusBar, QPlainTextEdit, QTableWidget, QSplitter, QFileDialog, QComboBox)

from QPlainTextEditLN import QPlainTextEditLN
    
from PyQt5.QtCore import Qt

from PyQt5.QtGui import QIcon, QFont

import utils
from utils import cfg, deb

from QResultSet import QResultSet

log = utils.getlog('csv')

from profiler import profiler

class dummyDBI:
    def ifNumericType(self, t):
        if t in ('int', 'decimal'):
            return True
        else:
            return False

    def ifDecimalType(self, t):
        if t == 'decimal':
            return True
        else:
            return False
    
    def ifLOBType(self, t):
        return False

    def ifRAWType(self, t):
        return False

    def ifVarcharType(self, t):
        if t == 'varchar':
            return True
        else:
            return False

    def ifTSType(self, t):
        return t == 'timestamp'
    
class csvImportDialog(QDialog):

    height = None
    width = None
    lastDir = ''
    
    def __init__(self, parent=None, ndp=[]):

        super(csvImportDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.actualDPs = []
        self.ndp = ndp
        
        self.cols = None
        self.rows = None
        
        self.lastChange = None

        self.initUI()
        
    def resizeEvent (self, event):
        # save the window size before layout dump in hslwindow
        csvImportDialog.width = self.size().width()
        csvImportDialog.height = self.size().height()
    
    def wheelEventMod (self, event):
        '''
            scroll modification for the csvText - to have horizontal scroll on shift+wheel
        '''
    
        p = event.angleDelta()
        
        if p.y() < 0:
            mode = 1
        else:
            mode = -1
            
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.ShiftModifier:
            #x = 0 - self.pos().x() 
            x = self.csvText.horizontalScrollBar().value()
            
            step = self.csvText.horizontalScrollBar().singleStep() * 2 #pageStep()
            self.csvText.horizontalScrollBar().setValue(x + mode * step)
        else:
            #super().wheelEvent(event)
            y = self.csvText.verticalScrollBar().value()
            
            step = self.csvText.verticalScrollBar().singleStep() * 2
            self.csvText.verticalScrollBar().setValue(y + mode * step)
            
    def isValidName(self, name):
        '''
            returns true if the target object name seems valid
        '''
        
        if name.isalnum() and not name[0].isnumeric():
            return True
            
        nlist = name.split('.')
        
        if len(nlist) > 2:
            return False
            
        print(nlist)
            
        for subname in nlist:
            if subname[0] == subname[-1] and subname[0] == '"':
                subname = subname[1:-1]
                
            if not re.match('^[a-zA-Z_]\w*$', subname):
                return False
            
        return True
        
    def validateTargetName(self):
    
        target = self.targetObject.text()
            
        if not self.isValidName(target):
            self.targetObject.setStyleSheet("color: red;")
            self.log(f'Invalid target object name: {target}', True)
            
            self.createText.setPlainText('-- object name is not valid')
            return False
        else:
            self.targetObject.setStyleSheet("color: black;")
            
        return True
    
    def generateCreateStatement(self):
            
        #typesMapping = {'int': 'bigint', 'varchar': 'varchar', 'timestamp':'timestamp'}
        
        target = self.targetObject.text()
        
        createTable = f'-- Generated create table statement, you can adjust it before import:\ncreate table {target} ('
        
        createCols = ''
        
        maxLen = 16
        for c in self.cols:
            if maxLen < len(c[0]) + 4:
                maxLen = len(c[0]) + 4
            
        for c in self.cols:
            
            #colType = typesMapping[c[1]] if c[1] in typesMapping else c[1]
         
            if c[1] == 'varchar':
                length = f'({c[2]})'
            else:
                length = ''
            
            colType = c[1]
            if colType == 'int' and c[2] >= 1024**3:
                # need to check integer values here, everything over  2,147,483,647 is BIGINT
                # it's actually 2*1023**3, but just to be on the safe side,
                colType = 'bigint'
            
            createCols += f'\n    {c[0]:{maxLen}}{colType}{length},'
            
        createCols = createCols[:-1]
            
        statement = createTable+createCols+'\n);'
        
        self.createText.setPlainText(statement)
        
        return True

    def syncTargetObject(self):
        '''
            The method tries to get object name from createText value
        '''
        
        create = self.createText.toPlainText()
        create = create.splitlines()
        
        testCreate = []
        
        i = 0
        for l in create:
            l = l.strip()
            
            if l and l[:2] != '--':
                testCreate.append(l)
                
            i += 1
            
            if i > 5:
                # it is very unlikely to have table name after 5 rows
                break
                
        create = ' '.join(testCreate)
        
        m = re.search(r'create\s+table\s+(\S+)\s+', create, re.I)
        
        tableName = ''
        
        if m:
            tableName = m[1]
            
        if tableName:
            self.targetObject.setText(tableName)
        
        self.validateTargetName()
            
        return
        
        
    @profiler
    def doImport(self, dummy=None):
    
        if self.lastChange == 'createText':
            self.syncTargetObject()
        
        idx = self.dpCB.currentIndex()
        
        if not self.cols or not self.rows:
            self.log('The data is not prepared. Load or paste csv and press the "Prepare Import" button.', True)
            return
        
        if idx < 0:
            self.log('No dataproviders?')
            return
            
        dp = self.actualDPs[idx]
        dbi = dp.dbi
        
        targetObject = self.targetObject.text()
        
        log(f'Data provider type: {type(dp)}', 4)
        log(f'DBI type: {type(dbi)}', 4)

        if not hasattr(dp, 'server'):
            raise utils.csvException('DB configuration is not valid, please report this issue.')
            
        self.log(f'Creating import connection: {dp.server.get("host")}')
        self.repaint()
        
        try:
            conn = dp.dbi.create_connection(dp.server)
        except utils.dbException as e:
            log(f'[E] Cannot open import connection: {e}', 2)
            raise(f'Cannot open import connection: {e}')
            
        self.log('Connected')
        
        targetNorm = utils.sqlNameNorm(targetObject)
        if dbi.checkTable(conn, targetNorm) == False:
            self.log(f'Need to create target object {targetObject}')
            
            sql = self.createText.toPlainText()
            
            try:
                dbi.execute_query_desc(conn, sql, params=[], resultSize=1)
            except utils.dbException as e:
                self.log(f'Failed to create target object {targetObject}: {e}, aborted.', True)
                return False
                
            self.log('Create statement executed...')
        else:
            self.logText.appendHtml(f'<font color="blue">Target object already exists: {targetObject}</font>, will try to use existing one (append data)...')
            
        self.repaint()
        
        v = '?, '*len(self.cols)
        v = v[:-2]
        sql = f'insert into {targetObject} values ({v})'
        
        self.log(f'statement for insert: {sql}')
        
        self.repaint()
        
        with profiler('csv import loop'):
            i = 0
            nolog = False
            try:
                for r in self.rows:
                    i += 1
                    dbi.execute_query_desc(conn, sql, params=r, resultSize=1, noLogging=nolog)
                    
                    if i == 13:
                        log('[SQL] switching sql logging off for the sake of performance', 4)
                        nolog = True
                    
                dbi.execute_query_desc(conn, 'commit', params=[], resultSize=0)
                dbi.close_connection(conn)
                    
            except utils.dbException as e:
                self.log(f'[SQL] error executing {sql}')
                self.log(f'[SQL] params {r}')
                self.log(f'Failed to perform inserts on line {i}: {e}, aborting.', True)
                
                try:
                    dbi.close_connection(conn)
                except utils.dbException as e:
                    self.log(f'Failed to close connection: {e}')
                    
                return False
            
        self.log(f'Finished okay, {i} rows inserted and commited. You can close the window now.')
            
        return True

    def m_load_check(self):
        '''check if the table is m_load_hostory and do a simple structure verification'''

        def find(name):
            for col in self.cols:
                if col[0].lower().strip() == name:
                    return col

        target = self.targetObject.text().lower().strip()

        if target in ('m_load_history_host', 'm_load_history_service'):

            errors = []

            host = find('host')
            time = find('time')
            port = find('port')

            if not host:
                errors.append('There is no mandatory HOST column')
            elif host[1] != 'varchar':
                errors.append('HOST column must be type VARCHAR or NVARCHAR')

            if not time:
                errors.append('There is no mandatory TIME column')
            elif time[1] != 'timestamp':
                errors.append('TIME column must be type TIMESTAMP')

            if target == 'm_load_history_service':
                if not port:
                    errors.append('There is no mandatory PORT column')
                elif port[1] not in ('int', 'integer', 'bigint'):
                    errors.append('PORT column must have integer type')

            for col in self.cols:
                if not col[0].strip().lower() in ('time', 'port', 'host'):
                    if col[1] not in ('integer', 'bigint', 'int'):
                        errors.append(f'{col[0].strip()} seems not an integer type...')

            return errors
        else:
            return None


    @profiler
    def doParse(self, dummy=None):
    
        if self.lastChange == 'createText':
            self.syncTargetObject()
            
        if not self.validateTargetName():
            # stop ?
            pass
            #return
    
        txt = self.csvText.toPlainText()
        
        trim = self.trimCB.isChecked()

        try:
            self.cols, self.rows = utils.parseCSV(txt, delimiter=';', trim=trim)
        except utils.csvException as e:
            self.log(f'CSV parsing error: {e}', True)
            return
            
        if self.generateCreateStatement():
            self.previewTable.rows = self.rows
            self.previewTable.cols = self.cols
            self.previewTable.populate()


            if cfg('importCheckM_LOAD', True):
                errors = self.m_load_check()

                if errors:
                    self.logText.appendHtml('Standard <font color="red">table structure warning:</font>');
                    for e in errors:
                        self.log(e)
                    self.log('-')
        else:
            return
        
        self.log(f'Import prepared, target object: {self.targetObject.text()}')
        self.log(f'{len(self.rows)} rows, {len(self.cols)} columns.')
        
    def loadCSV(self):
        fname = self.fileName.text()
        log(f'loading {fname}', 4)
        
        try:
            with open(fname, mode='r') as f:
                csvImportDialog.lastDir = os.path.dirname(fname)
                print('lastDir --> ', self.lastDir)
                txt = f.read()
                self.csvText.setPlainText(txt)
        except FileNotFoundError:
            self.log(f'File not found: \'{fname}\'', True)

    def openFile(self):
        fname = QFileDialog.getOpenFileName(self, 'Open file', self.lastDir,'*.csv')
        if len(fname) > 0 and fname[0]:
            self.fileName.setText(fname[0])
            self.loadCSV()

            # self.lastDir = os.path.dirname(fname[0])
            file = os.path.basename(fname[0])
            file = os.path.splitext(file)[0] # no extention
            
            self.targetObject.setText(file)
            
        
    def log(self, message, error=False):
        if error:
            message = utils.escapeHtml(message)
            self.logText.appendHtml(f'<font color = "red">{message}</font>');
            log('(log) [w] ' + message, 2)
        else:
            self.logText.appendPlainText(message)
            log('(log) ' + message, 2)
        
    def targetChanged(self, txt):
        self.lastChange = 'targetObject'
        
    def createChanged(self):
        self.lastChange = 'createText'
    
    def reload(self):
        self.loadCSV()
        file = self.fileName.text()
        file = os.path.basename(file)
        file = os.path.splitext(file)[0] # no extention
        self.targetObject.setText(file)


    def initUI(self):

        iconPath = utils.resourcePath('ico', 'favicon.png')
        
        # create layouts
        mainVL = QVBoxLayout()
        #createVL = QVBoxLayout()
        buttonsHL = QHBoxLayout()
        sp1 = QSplitter(Qt.Vertical)
        
        # create widgets
        
        self.fileName = QLineEdit()
        #self.fileName.addAction(QIcon(iconPath), QLineEdit.TrailingPosition)

        fileIcon = self.style().standardIcon(QStyle.SP_DialogOpenButton)
        openAct = QAction(fileIcon, "Open the csv from disk", self)
        openAct.triggered.connect(self.openFile)
        
        self.fileName.addAction(openAct, QLineEdit.TrailingPosition)
        
        # self.csvText = QPlainTextEdit() # 'paste csv data here or open a csv file'
        self.csvText = QPlainTextEditLN() # 'paste csv data here or open a csv file'
        
        self.csvText.wheelEvent = self.wheelEventMod # dirty horizontal scroll hack
        
        self.logText = QPlainTextEdit()
        self.csvText.setLineWrapMode(QPlainTextEdit.NoWrap)
        
        self.targetObject = QLineEdit('<TargetObject>')
        self.targetObject.textChanged.connect(self.targetChanged)
        
        self.createText = QPlainTextEdit('-- Generated create table statement')
        self.createText.textChanged.connect(self.createChanged)
        self.previewTable = QResultSet(None)
        
        self.dpCB = QComboBox()
        self.trimCB = QCheckBox('Trim spaces around values')

        self.trimCB.setChecked(cfg('importTrim', True))
        
        fontSize = utils.cfg('console-fontSize', 10)
        
        try: 
            font = QFont ('Consolas', fontSize)
        except:
            font = QFont ()
            font.setPointSize(fontSize)
            
        self.createText.setFont(font)
        self.csvText.setFont(font)

        ddbi = dummyDBI()
        self.previewTable.dbi = ddbi            # this is dummy dbi used only for the preview formatting
                                                # actual dbi will be self.dbi
        
        self.previewTable.setRowCount(2)
        self.previewTable.setColumnCount(4)
        
        parseBtn = QPushButton('Prepare Import')
        parseBtn.clicked.connect(self.doParse)
        importBtn = QPushButton('Import')
        importBtn.clicked.connect(self.doImport)
        #okBtn = QPushButton('Ok')
        cancelBtn = QPushButton('Close')
        cancelBtn.clicked.connect(self.reject)
        reloadBtn = QPushButton('Reload')
        reloadBtn.clicked.connect(self.reload)
        
        # csv loader wrapper object
        wrapperCSV = QWidget()
        loCSV = QVBoxLayout()
        loCSVinternal = QHBoxLayout()
        loCSVinternal.addWidget(QLabel('File:'))
        loCSVinternal.addWidget(self.fileName)
        loCSVinternal.addWidget(reloadBtn)
        
        loCSV.addLayout(loCSVinternal)
        loCSV.addWidget(self.csvText)
        wrapperCSV.setLayout(loCSV)
        
        # create statement wrapper object
        wrapperCreate = QWidget()
        loCreate = QVBoxLayout()
        loCreateInternal = QHBoxLayout()
        loCreateInternal.addWidget(self.targetObject)
        loCreateInternal.addWidget(parseBtn)
        loCreateInternal.addWidget(QLabel('Parse the CSV input and prepare the import.'))
        loCreateInternal.addStretch(1)
        loCreateInternal.addWidget(self.trimCB)
        loCreate.addLayout(loCreateInternal)
        loCreate.addWidget(self.createText)
        wrapperCreate.setLayout(loCreate)
        
        #preview table wrapper
        wrapperPreview = QWidget()
        loPreview = QVBoxLayout()
        loPreview.addWidget(QLabel('Preview:'))
        loPreview.addWidget(self.previewTable)
        
        '''
        loTarget = QHBoxLayout()
        loTarget.addWidget(QLabel('Target DB:'))
        loTarget.addWidget(self.dpCB)
        loTarget.addStretch(1)
        
        loPreview.addLayout(loTarget)
        '''
        
        wrapperPreview.setLayout(loPreview)

        #log wrapper
        wrapperLog = QWidget()
        loLog = QVBoxLayout()
        loLog.addWidget(self.logText)
        
        '''
        font = self.logText.font()
        font.setPointSize(6)
        self.logText.setFont(font)
        '''
        
        wrapperLog.setLayout(loLog)
        

        #buttons line
        buttonsHL.addStretch(10)
        buttonsHL.addWidget(QLabel('Target DB:'))
        buttonsHL.addWidget(self.dpCB)

        buttonsHL.addStretch(1)
        buttonsHL.addWidget(importBtn)
        buttonsHL.addWidget(cancelBtn)
        buttonsHL.addStretch(1)
        
        #assign everything
        sp1.addWidget(wrapperCSV)
        sp1.addWidget(wrapperCreate)
        sp1.addWidget(wrapperPreview)
        sp1.addWidget(wrapperLog)
        
        mainVL.addWidget(sp1)
        mainVL.addLayout(buttonsHL)

        self.setLayout(mainVL)
        
        self.resize(900, 600)
        
        for dp in self.ndp:
            if hasattr(dp, 'dbi'):
                dbName = f'[{dp.dbi.name}]'
                
                if hasattr(dp, 'dbProperties'):
                    tenant = dp.dbProperties.get('tenant')
                    
                    if tenant:
                        dbName += f' {tenant}'

                self.dpCB.addItem(dbName)
                self.actualDPs.append(dp)
        
        h = sp1.size().height()
        vsizes = [int(h*x) for x in [0.3, 0.3, 0.3, 0.01]]
        
        sp1.setSizes(vsizes)
        
        if self.width and self.height:
            self.resize(self.width, self.height)

        self.setWindowIcon(QIcon(iconPath))
        self.setWindowTitle('CSV Import')
        

if __name__ == '__main__':
    
    app = QApplication([])
    dialog = csvImportDialog()
    
    dialog.exec_()
    
    profiler.report()
