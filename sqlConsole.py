from PyQt5.QtWidgets import (QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem,
        QTabWidget, QApplication, QAbstractItemView)

from PyQt5.QtGui import QTextCursor, QColor, QFont
from PyQt5.QtCore import QTimer

from PyQt5.QtCore import Qt

import time

import db

import utils
import re

import lobDialog

from utils import dbException, log

from SQLSyntaxHighlighter import SQLSyntaxHighlighter

class resultSet(QTableWidget):
    '''
        Implements the result set widget, basically QTableWidget with minor extensions
    
    '''

    def __init__(self):
        self.closeResult = False     # True in case of LOBs, CLOSERESULTSET message to be sent
                                # this actually to be set by the driver, and not in the application level... << print create an issue for this
        self._resultset_id = None    # filled manually right after execute_query
        self._connection = None    # filled manually right after execute_query
        
        self.cols = [] #column descriptions
        self.rows = [] # actual data 
        
        self.headers = [] # column names
        
        super().__init__()
        
        self.setWordWrap(False)
        self.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: lightgray }")
        
        self.cellDoubleClicked.connect(self.dblClick) # LOB viewer

        self.keyPressEvent = self.resultKeyPressHandler
        
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        
    def autoCloseResult(self):
        log('closing the LOB result set')
        db.close_result(self._connection, self._resultset_id) 
        self.closeResult = False
        
    def triggerResultTimer(self, window):
        log('Setting closeResultTimer')
        self.timer = QTimer(window)
        self.timer.timeout.connect(self.autoCloseResult)
        self.timer.start(1000 * 60)
        
    def destroy(self):
        
        '''
            __del__ seems to be potentially implicidly delayed so let's use a normal explicit method
            Actually this seems to be exactly the right place to put
            CLOSERESULTSET call, as before this we might need to call BLOB.read()
        '''
        if self.closeResult:
            log('The resultSet had LOBs so send CLOSERESULTSET')
            
            db.close_result(self._connection, self._resultset_id) 
            self.closeResult = False
            
    def __del__(self):
        print('result set actually deleted')
    
    def csvRow(self, r):
        
        values = []
        
        # print varchar values to be quoted by "" to be excel friendly
        for i in range(self.columnCount()):
            #values.append(table.item(r, i).text())

            val = self.rows[r][i]
            vType = self.cols[i][1]

            if db.ifBLOBType(vType):
                values.append(str(val.encode()))
            else:
                if db.ifNumericType(vType):
                    values.append(utils.numberToStrCSV(val))
                elif db.ifRAWType(vType):
                    values.append(val.hex())
                else:
                    if val is None:
                        values.append(utils.cfg('nullStringCSV', '?'))
                    else:
                        values.append(str(val))
                
            
        return ';'.join(values)

    def resultKeyPressHandler(self, event):
    
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.ControlModifier:
            if event.key() == Qt.Key_A:
                self.selectAll()
            
            if event.key() == Qt.Key_C or event.key() == Qt.Key_Insert:
            
                '''
                    copy cells or rows implementation
                '''
            
                sm = self.selectionModel()
                
                rowIndex = []
                for r in sm.selectedRows():
                    rowIndex.append(r.row())
                    
                if rowIndex: 
                    # process rows
                    
                    rowIndex.sort()
                    
                    csv = ';'.join(self.headers) + '\n'
                    for r in rowIndex:
                        csv += self.csvRow(r) + '\n'
                        
                    QApplication.clipboard().setText(csv)
                    
                else:
                    # copy one cell
                    for c in sm.selectedIndexes():
                        #csv = self.result.item(c.row(), c.column()).text()

                        value = self.rows[c.row()][c.column()]
                        vType = self.cols[c.column()][1]
                        
                        if value is None:
                            csv = utils.cfg('nullStringCSV', '?')
                        else:
                            if db.ifBLOBType(vType):
                                csv = str(value.encode())
                            else:
                                if db.ifNumericType(vType):
                                    csv = utils.numberToStrCSV(value)
                                elif db.ifRAWType(vType):
                                    csv = value.hex()
                                else:
                                    csv = str(value)
                        
                        QApplication.clipboard().setText(csv)
                        # we only copy first value, makes no sence otherwise
                        break;
        else:
            super().keyPressEvent(event)
            
    def populate(self):
        '''
            populates the result set based on
            self.rows, self.cols
        '''
    
        self.clear()
    
        cols = self.cols
        rows = self.rows
    
        row0 = []

        for c in cols:
            row0.append(c[0])
            
        self.headers = row0.copy()
           
        self.setColumnCount(len(row0))

        self.setHorizontalHeaderLabels(row0)
        self.resizeColumnsToContents();
        
        self.setRowCount(len(rows))
        
        adjRow = 5 if len(rows) >=5 else len(rows)
        
        #fill the result table
        for r in range(len(rows)):
                
            for c in range(len(row0)):
                
                val = rows[r][c]
                
                #if cols[c][1] == 4 or cols[c][1] == 3 or cols[c][1] == 1:
                if db.ifNumericType(cols[c][1]):
                
                    if db.ifDecimalType(cols[c][1]):
                        val = utils.numberToStr(val, 3)
                    else:
                        val = utils.numberToStr(val)
                    
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif db.ifLOBType(cols[c][1]): #LOB
                    #val = val.read()
                    if db.ifBLOBType(cols[c][1]):
                        if val is None:
                            val = utils.cfg('nullString', '?')
                        else:
                            val = str(val.encode())
                    else:
                        val = str(val)
                    item = QTableWidgetItem(val)
                    #item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop);
                    #print(val)
                elif db.ifRAWType(cols[c][1]): #VARBINARY
                    val = val.hex()
                    
                    item = QTableWidgetItem(val)
                else:
                    if val is None:
                        val = utils.cfg('nullString', '?')
                    else:
                        val = str(val)
                        
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter);
                    
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.setItem(r, c, item) # Y-Scale

            if r == adjRow - 1:
                self.resizeColumnsToContents();
                
                for i in range(len(row0)):
                    if self.columnWidth(i) >= 512:
                        self.setColumnWidth(i, 512)
                        
    def dblClick(self, i, j):
    
        if db.ifLOBType(self.cols[j][1]):
            blob = self.rows[i][j].read()
            self.rows[i][j].seek(0) #rewind just in case
        else:
            blob = str(self.rows[i][j])

        lob = lobDialog.lobDialog(blob)
        
        lob.exec_()

        return False
        
        
class sqlConsole(QWidget):
    
    def __init__(self, window, config):
    
        self.window = None # required for the timer
        
        self.conn = None
        self.lock = False
        self.config = None
        self.timer = None
        self.rows = []
    
        self.haveHighlighrs = False
    
        self.results = [] #list of resultsets
        self.resultTabs = None #tabs widget



        super().__init__()
        self.initUI()

        if config is None:
            return
        
        try: 
            self.conn = db.create_connection(config)
            self.config = config
        except dbException as e:
            raise e
            return

        if cfg('keepalive-cons'):
            keepalive = int(cfg('keepalive-cons'))
            self.enableKeepAlive(self, keepalive)
            
    def newResult(self):
        
        result = resultSet()
        
        if len(self.results) > 0:
            rName = 'Results ' + str(len(self.results))
        else:
            rName = 'Results'
        
        self.results.append(result)
        self.resultTabs.addTab(result, rName)
        
        self.resultTabs.setCurrentIndex(len(self.results) - 1)
        
        return result
        
    def closeResults(self):
    
        for i in range(len(self.results) - 1, -1, -1):
            self.resultTabs.removeTab(i)
            self.results[i].clear()
            self.results[i].destroy()
            
            del(self.results[i])
            
    def enableKeepAlive(self, window, keepalive):
        log('Setting up DB keep-alive requests: %i seconds' % (keepalive))
        self.timerkeepalive = keepalive
        self.timer = QTimer(window)
        self.timer.timeout.connect(self.keepAlive)
        self.timer.start(1000 * keepalive)
        
    def renewKeepAlive(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer.start(1000 * self.timerkeepalive)

    def keepAlive(self):
    
        if self.conn is None:
            return

        try:
            log('console keep alive... ', False, True)
            
            t0 = time.time()
            db.execute_query(self.conn, 'select * from dummy', [])
            t1 = time.time()
            log('ok: %s ms' % (str(round(t1-t0, 3))), True)
        except dbException as e:
            log('Trigger autoreconnect...')
            try:
                conn = db.create_connection(self.config)
                if conn is not None:
                    self.conn = conn
                    log('Connection restored automatically')
                else:
                    log('Some connection issue, give up')
                    self.conn = None
            except:
                log('Connection lost, give up')
                # print disable the timer?
                self.conn = None

    def clearHighlighting(self):
        self.lock = True
        
        txt = self.cons.toPlainText()
        cursor = QTextCursor(self.cons.document())

        cursor.setPosition(0,QTextCursor.MoveAnchor);
        cursor.setPosition(len(txt),QTextCursor.KeepAnchor);
        
        format = cursor.charFormat()
        
        format.setBackground(QColor('white'));
        cursor.setCharFormat(format);
        
        self.lock = False
        
    def searchWord(self, str):
        if self.lock:
            return
            
        self.lock = True
        #print('lets search/highlight: ' + str)
        
        #for i in range(self.cons.blockCount()):
        #    txtline = self.cons.document().findBlockByLineNumber(i)
            
        #line = txtline.text()
        line = self.cons.toPlainText()
        
        st = 0
        
        while st >=0:
            st = line.find(str, st)
            
            if st >= 0:
                # really this should be a \b regexp here instead of isalnum
                '''
                if (st>0 and not (line[st-1]).isalnum()) and (st < len (line) and not (line[st+1]).isalnum()):
                    self.highlight(self.cons.document(), st, st+len(str))
                '''
                
                sample = line[st-1:st+len(str)+1]

                #mask = '\\b%s\\b' % (str)
                #mask = r'.\b%s\b.' % (str)
                mask = r'\W%s\W' % (str)
                
                if re.match(mask, sample):
                    self.highlight(self.cons.document(), st, st+len(str))
                else:
                    pass
                    #print('nope (%s -- %s)' % (sample, mask))
                
                st += len(str)
                    
        self.lock = False
            
        return
        
    def highlight(self, block, start, stop):
        #print ('highlight here: ', block.text(), start, stop)
        cursor = QTextCursor(block)

        cursor.setPosition(start, QTextCursor.MoveAnchor)
        cursor.setPosition(stop, QTextCursor.KeepAnchor)
        
        format = cursor.charFormat()
        
        format.setBackground(QColor('#0F0'))
        cursor.setCharFormat(format)
        
        self.haveHighlighrs = True
    
    def consSelection(self):
        if self.lock:
            return
        cursor = self.cons.textCursor()
        selected = cursor.selectedText()
        
        if len(selected) == 0 and self.haveHighlighrs:
            self.clearHighlighting()
            
            self.haveHighlighrs = False
            return

        txtline = self.cons.document().findBlockByLineNumber(cursor.blockNumber())
        line = txtline.text()

        if re.match('\w+$', selected):
            if re.search('\\b%s\\b' % selected, line):
                #we are not sure that this is exactly same found as the one selected...
                self.searchWord(selected)

        return
            
        
        # https://stackoverflow.com/questions/27716625/qtextedit-change-font-of-individual-paragraph-block
        # https://stackoverflow.com/questions/1849558/how-do-i-use-qtextblock
        # cursor.setPosition(0)
                        
    def log(self, text, error = False):
        #self.logArea.setPlainText(self.logArea.toPlainText() + '\n' + text)
        
        if error:
            self.logArea.appendHtml('<font color = "red">%s</font>' % text);
        else:
            self.logArea.appendPlainText(text)
        
    def dummyResultTable(self):
    
        row0 = []
    
        cols = [
            ['Name',11],
            ['LOB String',26],
            ['Txt',11],
        ]
        
        rows = [
                ['name','select * from dummy', 'no idea'],
                ['name','select * from dummy', 'no idea'],
                ['name','select * from dummy', 'no idea']
            ]
            
        return
        #create headers
        for c in cols:
            row0.append(c[0])
            
        self.headers = row0.copy()
           
        self.result.setColumnCount(len(row0))
        self.result.setRowCount(0)
        self.result.setHorizontalHeaderLabels(row0)
        self.result.resizeColumnsToContents();
        
        self.result.setRowCount(len(rows))
        
        adjRow = 5 if len(rows) >=5 else len(rows)
        
        #fill the result table
        
        for r in range(len(rows)):
                
            for c in range(len(row0)):
                
                val = rows[r][c]
                
                if cols[c][1] == 4 or cols[c][1] == 3 or cols[c][1] == 1:
                    val = utils.numberToStr(val)
                    
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif cols[c][1] == 26: #LOB
                    # val = val.read()
                    val = val
                    item = QTableWidgetItem(val)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop);
                else:
                    if val is None:
                        val = utils.cfg('nullString', '?')
                    else:
                        val = str(val)
                        
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter);
                    
                
                self.result.setItem(r, c, item) # Y-Scale

            if r == adjRow - 1:
                self.result.resizeColumnsToContents();
                
                for i in range(len(row0)):
                    if self.result.columnWidth(i) >= 512:
                        self.result.setColumnWidth(i, 512)
                            
    def consKeyPressHandler(self, event):
    
        def executeSelection():
        
            txt = ''
            statements = []
            F9 = True
            

            def isItCreate(s):
                '''
                    if in create procedure now?
                '''
                
                if re.match('^\s*create procedure\W.*', s, re.IGNORECASE):
                    return True
                else:
                    return False
                    
            def isItEnd(s):
                '''
                    it shall ignor whitspaces
                    and at this point ';' already 
                    checked outside, so just \bend\b regexp check


                    The logic goes like this
                    
                    if there is a selection:
                        split and execute stuff inside
                    else:
                        f9 mode - detect and execute one line

                '''
                #if s[-3:] == 'end':
                if re.match('.*\W*end\s*$', s, re.IGNORECASE):
                    return True
                else:
                    return False
                    
            def selectSingle(start, stop):
                cursor = QTextCursor(self.cons.document())

                cursor.setPosition(start,QTextCursor.MoveAnchor)
                cursor.setPosition(stop,QTextCursor.KeepAnchor)
                
                self.cons.setTextCursor(cursor)
            
            def statementDetected(start, stop):

                str = txt[start:stop]
                
                if str == '': 
                    #typically only when start = 0, stop = 1
                    if not (start == 0 and stop <= 1):
                        log('[w] unusual empty string matched')
                    return
                    
                statements.append(str)
            
            cursor = self.cons.textCursor()

            selectionMode = False
            
            txt = self.cons.toPlainText()
            length = len(txt)

            if not cursor.selection().isEmpty():
                F9 = False
                selectionMode = True
                scanFrom = cursor.selectionStart()
                scanTo = cursor.selectionEnd()
            else:
                F9 = True
                scanFrom = 0
                scanTo = length
                if F9:
                    #detect and execute just one statement
                    cursorPos = self.cons.textCursor().position()
                else:
                    cursorPos = None
            
            str = ''
            
            i = 0
            start = stop = 0
            
            insideString = False
            insideProc = False
            
            # main per character loop:

            for i in range(scanFrom, scanTo):
                c = txt[i]

                #print('['+c+']')
                if not insideString and c == ';':
                    #print(i)
                    if not insideProc:
                        str = ''
                        stop = i
                        continue
                    else:
                        if isItEnd(str[-10:]):
                            insideProc = False
                            str = ''
                            stop = i
                            continue
                
                if str == '':
                    if c in (' ', '\n', '\t'):
                        # warning: insideString logic skipped here (as it is defined below this line
                        continue
                    else:
                        if F9 and (start <= cursorPos < stop):
                            selectSingle(start, stop)
                            break
                        else:
                            if not F9:
                                statementDetected(start, stop)
                            
                        start = i
                        str = str + c
                else:
                    str = str + c

                if not insideString and c == '\'':
                    insideString = True
                    continue
                    
                if insideString and c == '\'':
                    insideString = False
                    continue
                    
                if not insideProc and isItCreate(str[:64]):
                    insideProc = True


            #print(cursorPos)
            #print(scanFrom, scanTo)
            #print(start, stop)
            #print(str)
            
            if stop == 0:
                # no semicolon met
                stop = scanTo
            
            #if F9 and (start <= cursorPos < stop):
            #print so not sure abous this change
            if F9 and (start <= cursorPos <= stop):
                selectSingle(start, stop)
            else:
                if not F9:
                    statementDetected(start, stop)
                
            self.closeResults()
            
            #print('\n---\nso what we have to execute: ')
            if F9 and (start <= cursorPos < stop):
                #print('-> [%s] ' % txt[start:stop])
                
                result = self.newResult()
                executeStatement(txt[start:stop], result)
            else:
                for st in statements:
                    #print('--> [%s]' % st)
                    
                    result = self.newResult()
                    executeStatement(st, result)
                    
                    #self.update()
                    self.repaint()

            return
        
        def executeStatement(sql, result):
            '''
                executes the string without any analysis
                result filled
            '''
            
            self.renewKeepAlive()
            
            if len(sql) >= 2**17 and self.conn.large_sql != True:
                log('reconnecting to hangle large SQL')
                print('replace by a pyhdb.constant? pyhdb.protocol.constants.MAX_MESSAGE_SIZE')
                
                db.largeSql = True
                
                try: 
                    self.conn = db.create_connection(self.config)
                except dbException as e:
                    err = str(e)
                    #
                    self.log('DB Exception:' + err, True)
                    
                    self.connect = None
                    return
                    
            if self.conn is None:
                self.log('Error: No connection')
                return
                
            #execute the query
            
            try:
                t0 = time.time()
                
                #print('clear rows array here?')
                
                suffix = ''
                
                if len(sql) > 128:
                    txtSub = sql[:128]
                    suffix = '...'
                else:
                    txtSub = sql
                    
                txtSub = txtSub.replace('\n', ' ')
                txtSub = txtSub.replace('\t', ' ')
                
                self.log('\nExecute: ' + txtSub + suffix)
                self.logArea.repaint()
                
                result.rows, result.cols, dbCursor = db.execute_query_desc(self.conn, sql, [])
                
                rows = result.rows
                cols = result.cols
                
                t1 = time.time()

                logText = 'Query execution time: %s s' % (str(round(t1-t0, 3)))
                
                if rows is None or cols is None:
                    # it was a DDL or something else without a result set so we just stop
                    
                    logText += ', ' + str(dbCursor.rowcount) + ' rows affected'
                    
                    self.log(logText)
                    
                    result.clear()
                    return

                resultSize = len(rows)
                
                for c in cols:
                    if db.ifLOBType(c[1]):
                        result.closeResult = True
                        result._connection = self.conn
                        result._resultset_id = dbCursor._resultset_id
                        
                        result.triggerResultTimer(self.window)
                        break
                
                lobs = ', +LOBs' if result.closeResult else ''
                
                logText += '\n' + str(len(rows)) + ' rows fetched' + lobs
                if resultSize == utils.cfg('maxResultSize', 1000): logText += ', note: this is the resultSize limit'
                
                self.log(logText)
            except dbException as e:
                err = str(e)
                self.log('DB Exception:' + err, True)
                return

            result.populate()
                
            return
        
        if event.key() == Qt.Key_F8 or  event.key() == Qt.Key_F9:
            executeSelection()
            
        else:
            QPlainTextEdit.keyPressEvent(self.cons, event)
            #self.consSelection()
        
    def initUI(self):
        vbar = QVBoxLayout()
        hbar = QHBoxLayout()
        
        #self.cons = QPlainTextEdit()
        self.cons = QPlainTextEdit()
        
        fontSize = utils.cfg('console-fontSize', 10)
        
        try: 
            font = QFont ('Consolas', fontSize)
        except:
            font = QFont ()
            font.setPointSize(fontSize)
            
        self.cons.setFont(font)
        
        self.resultTabs = QTabWidget()
        #self.newResult() #do we need an empty one?
        
        spliter = QSplitter(Qt.Vertical)
        self.logArea = QPlainTextEdit()
        
        self.cons.keyPressEvent = self.consKeyPressHandler
        self.cons.selectionChanged.connect(self.consSelection) #does not work

        #self.cons.setPlainText('select * from (select * from m_load_history_info)')
        #self.cons.setPlainText('select connection_id, statement_string from m_active_statements;\nselect connection_id, statement_string from m_active_statements;\n')
        
        spliter.addWidget(self.cons)
        spliter.addWidget(self.resultTabs)
        spliter.addWidget(self.logArea)
        
        spliter.setSizes([300, 200, 10])
        
        vbar.addWidget(spliter)
        
        self.setLayout(vbar)
        
        self.SQLSyntax = SQLSyntaxHighlighter(self.cons.document())
        #console = QPlainTextEdit()