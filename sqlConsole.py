from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem, QApplication, QAbstractItemView

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


'''
    types
    1 - integer?
    2 - smallint
    3 - integer
    5 - decimal

    7 - double
    
    9 - varchar
    11 - nvarchar

    14 - date
    15 - time
    16 - timestamp
    
    26 - LOB
'''

class sqlConsole(QWidget):
    conn = None
    cursor = None # single cursor supported
    
    closeResult = False # True in case of LOBs, CLOSERESULTSET message to be sent
    
    headers = [] # column names
    
    lock = False
    
    config = None
    
    rows = []
    
    haveHighlighrs = False
    
    
    def __init__(self, config):
        super().__init__()
        self.initUI()
        
        if config is None:
            return
        
        try: 
            self.conn = db.create_connection(config)
            self.config = config
        except dbException as e:
            raise e
                        
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
            
    def csvRow(self, table, r):
        
        values = []
        
        # print varchar values to be quoted by "" to be excel friendly
        for i in range(table.columnCount()):
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


    def clearHighlighting(self):
        print('clear highlights')
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
                
    def resultKeyPressHandler(self, event):
    
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.ControlModifier:
            if event.key() == Qt.Key_A:
                self.result.selectAll()
            
            if event.key() == Qt.Key_C or event.key() == Qt.Key_Insert:
            
                '''
                    copy cells or rows implementation
                '''
            
                sm = self.result.selectionModel()
                
                rowIndex = []
                for r in sm.selectedRows():
                    rowIndex.append(r.row())
                    
                if rowIndex: 
                    # process rows
                    
                    rowIndex.sort()
                    
                    csv = ';'.join(self.headers) + '\n'
                    for r in rowIndex:
                        csv += self.csvRow(self.result, r) + '\n'
                        
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
                        
    def log(self, text, error = False):
        #self.logArea.setPlainText(self.logArea.toPlainText() + '\n' + text)
        
        if error:
            self.logArea.appendHtml('<font color = "red">%s</font>' % text);
        else:
            self.logArea.appendPlainText(text)
        
    def dblClick(self, i, j):
    
        if db.ifLOBType(self.cols[j][1]):
            blob = self.rows[i][j].read()
            self.rows[i][j].seek(0) #rewind just in case
        else:
            blob = str(self.rows[i][j])

        lob = lobDialog.lobDialog(blob)
        
        lob.exec_()

        return False
        
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
        
        self.result.cellDoubleClicked.connect(self.dblClick)
        
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
    
        def executeStatement():
            txt = self.cons.textCursor().selectedText()
            
            if txt == '':
                txt = self.cons.toPlainText()
            else:
                ParagraphSeparator = u"\u2029"

                txt = txt.replace(ParagraphSeparator, '\n')
            
            if len(txt) >= 2**17 and self.conn.large_sql != True:
                log('reconnecting to hangle large SQL')
                print('replace by a pyhdb.constant?')
                
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
                
            if self.closeResult:
                log('connection had LOBs so call CLOSERESULTSET...')
                db.close_cursor(self.conn, self.cursor)
                self.closeResult = False
            
            try:
                t0 = time.time()
                
                print('clear rows array here?')
                
                suffix = ''
                
                if len(txt) > 128:
                    txtSub = txt[:128]
                    suffix = '...'
                else:
                    txtSub = txt
                    
                txtSub = txtSub.replace('\n', ' ')
                txtSub = txtSub.replace('\t', ' ')
                
                self.log('\nExecute: ' + txtSub + suffix)
                self.logArea.repaint()
                
                self.rows, self.cols, self.cursor = db.execute_query_desc(self.conn, txt, [])
                
                rows = self.rows
                cols = self.cols
                
                t1 = time.time()

                logText = 'Query execution time: %s s' % (str(round(t1-t0, 3)))
                
                if rows is None or cols is None:
                    # it was a DDL or something else without a result set so we just stop
                    
                    logText += ', ' + str(self.cursor.rowcount) + ' rows affected'
                    
                    self.log(logText)
                    return

                resultSize = len(rows)
                
                for c in cols:
                    if db.ifLOBType(c[1]):
                        self.closeResult = True
                        break
                
                lobs = ', +LOBs' if self.closeResult else ''
                
                logText += '\n' + str(len(rows)) + ' rows fetched' + lobs
                if resultSize == utils.cfg('maxResultSize', 1000): logText += ', note: this is the resultSize limit'
                
                self.log(logText)
            except dbException as e:
                err = str(e)
                self.log('DB Exception:' + err, True)
                return

            # draw the result
            # probably new tab also to be created somewhere here?
            row0 = []
            
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
                    self.result.setItem(r, c, item) # Y-Scale

                if r == adjRow - 1:
                    self.result.resizeColumnsToContents();
                    
                    for i in range(len(row0)):
                        if self.result.columnWidth(i) >= 512:
                            self.result.setColumnWidth(i, 512)
        
        def detectStatement():
            def isItCreate(s):
                '''
                    should also check case, etc...
                    
                    regexp \breate\s+procedure\b
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
                '''
                #if s[-3:] == 'end':
                if re.match('.*\W*end\s*$', s, re.IGNORECASE):
                    return True
                else:
                    return False

            txt = self.cons.toPlainText()
            length = len(txt)
            
            cursorPos = self.cons.textCursor().position()
            
            str = ''
            
            i = 0
            start = stop = 0
            
            insideString = False
            insideProc = False
            
            # process the part before the cursor
            for i in range(cursorPos):
                c = txt[i]

                if not insideString and c == ';':
                    if not insideProc:
                        str = ''
                        continue
                    else:
                        if isItEnd(str[-10:]):
                            insideProc = False
                            str = ''
                            continue
                
                if str == '':
                    if c in (' ', '\n', '\t'):
                        # warning: insideString logic skipped here (as it is defined below this line
                        continue
                    else:
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
                    
            # now get the rest of the string
            finish = False
            
            print('interm result:', str)
            print('instring:', insideString)
            
            if i > 0:
                i+= 1
            
            while not finish and i < length:
            
                c = txt[i]
            
                if not insideString and c == ';':
                    if not insideProc:
                        stop = i+1
                        finish = True
                    else:
                        if isItEnd(str[-10:]):
                            insideProc = False
                            continue
                            
                if str == '':
                    if c in (' ', '\n', '\t'):
                        pass
                    else:
                        start = i
                        str = str + c
                else:
                    str = str + c

                if not insideString and c == '\'':
                    insideString = True
                    
                if insideString and c == '\'':
                    insideString = False
                    
                if not insideProc and isItCreate(str[:64]):
                    insideProc = True
                    
                i+= 1
                
                '''
                if c == ';' or i == length:
                    stop = i
                    finish = True
                '''
            
            if stop == 0:
                return False
            
            '''
            if c == ';':
                str = str[:-1]
                stop -= 1
            '''
            
            cursor = QTextCursor(self.cons.document())

            cursor.setPosition(start,QTextCursor.MoveAnchor);
            cursor.setPosition(stop,QTextCursor.KeepAnchor);
            
            self.cons.setTextCursor(cursor)        
            
            return True

        if event.key() == Qt.Key_F9:
            if detectStatement():
                executeStatement()
        
        if event.key() == Qt.Key_F8:
            executeStatement()
            
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
        
        self.result = QTableWidget()
        self.result.setWordWrap(False)
        self.result.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: lightgray }")
        
        self.result.cellDoubleClicked.connect(self.dblClick) # LOB viewer
        
        #self.result = QPlainTextEdit()
        #splitOne = QSplitter(Qt.Horizontal)
        spliter = QSplitter(Qt.Vertical)
        self.logArea = QPlainTextEdit()
        
        self.cons.keyPressEvent = self.consKeyPressHandler
        self.cons.selectionChanged.connect(self.consSelection) #does not work


        self.result.keyPressEvent = self.resultKeyPressHandler
        
        self.result.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
                
        #self.cons.setPlainText('select * from (select * from m_load_history_info)')
        #self.cons.setPlainText('select connection_id, statement_string from m_active_statements;\nselect connection_id, statement_string from m_active_statements;\n')
        
        spliter.addWidget(self.cons)
        spliter.addWidget(self.result)
        spliter.addWidget(self.logArea)
        
        spliter.setSizes([300, 200, 10])
        
        vbar.addWidget(spliter)
        
        self.setLayout(vbar)
        
        self.SQLSyntax = SQLSyntaxHighlighter(self.cons.document())
        #console = QPlainTextEdit()