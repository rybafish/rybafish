from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem, QApplication, QAbstractItemView

from PyQt5.QtGui import QTextCursor, QColor, QFont
from PyQt5.QtCore import QTimer

from PyQt5.QtCore import Qt

import time

import db

import utils

import re

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
'''

class sqlConsole(QWidget):
    conn = None
    
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
            values.append(str(self.rows[r][i]))
            
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
        print('lets search/highlight: ' + str)
        
        #for i in range(self.cons.blockCount()):
        #    txtline = self.cons.document().findBlockByLineNumber(i)
            
        #line = txtline.text()
        line = self.cons.toPlainText()
        
        st = 0
        while st >=0:
            st = line.find(str, st)
            
            if st >= 0:
                # really this should be a \b regexp here instead of isalnum
                if (st>0 and not (line[st-1]).isalnum()) and (st < len (line) and not (line[st+1]).isalnum()):
                    self.highlight(self.cons.document(), st, st+len(str))
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
            
                sm = self.result.selectionModel()
                
                #process rows
                rowIndex = []
                for r in sm.selectedRows():
                    rowIndex.append(r.row())
                    
                if rowIndex:
                    rowIndex.sort()
                    
                    csv = ';'.join(self.headers) + '\n'
                    for r in rowIndex:
                        csv += self.csvRow(self.result, r) + '\n'
                        
                    QApplication.clipboard().setText(csv)
                    
                else:
                    for c in sm.selectedIndexes():
                        #csv = self.result.item(c.row(), c.column()).text()

                        csv = str(self.rows[c.row()][c.column()])
                        QApplication.clipboard().setText(csv)
                        # we only copy first value, makes no sence otherwise
                        break;
                        
    def consKeyPressHandler(self, event):
        
        if event.key() == Qt.Key_F8:
            txt = self.cons.toPlainText()
            
            if len(txt) >= 2**17 and self.conn.large_sql != True:
                log('reconnecting to hangle large SQL')
                
                db.largeSql = True
                
                try: 
                    self.conn = db.create_connection(self.config)
                except dbException as e:
                    err = str(e)
                    self.log.setPlainText('DB Exception:' + err)
                    self.connect = None
                    return
                    
            if self.conn is None:
                self.log.setPlainText('Error: No connection')
                return
            
            try:
                t0 = time.time()
                
                self.log.setPlainText('Execute the query...')
                self.log.repaint()
                
                self.rows, cols = db.execute_query_desc(self.conn, txt, [])
                
                rows = self.rows
                
                resultSize = len(rows)
                
                t1 = time.time()
                
                logText = 'Query execution time: %s s\n' % (str(round(t1-t0, 3)))
                logText += str(len(rows)) + ' rows fetched'
                if resultSize == utils.cfg('resultSize', 1000): logText += ', note: this is the resultSize limit'
                
                self.log.setPlainText(logText)
            except dbException as e:
                err = str(e)
                self.log.setPlainText('DB Exception:' + err)
                return

            row0 = []
            
            #print('[headers]')
            for c in cols:
                row0.append(c[0])
                #print(c)
               
            self.headers = row0.copy()
               
            self.result.setColumnCount(len(row0))
            self.result.setRowCount(0)
            self.result.setHorizontalHeaderLabels(row0)
            self.result.resizeColumnsToContents();
            
            self.result.setRowCount(len(rows))
            
            adjRow = 5 if len(rows) >=5 else len(rows)
            
            for r in range(len(rows)):
                    
                for c in range(len(row0)):
                    
                    val = rows[r][c]
                    
                    if cols[c][1] == 4 or cols[c][1] == 3 or cols[c][1] == 1:
                        val = utils.numberToStr(val)
                        
                        item = QTableWidgetItem(val)
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter);
                    else:
                        if val is None:
                            val = '?'
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
        #self.result = QPlainTextEdit()
        #splitOne = QSplitter(Qt.Horizontal)
        spliter = QSplitter(Qt.Vertical)
        self.log = QPlainTextEdit()
        
        self.cons.keyPressEvent = self.consKeyPressHandler
        self.cons.selectionChanged.connect(self.consSelection) #does not work


        self.result.keyPressEvent = self.resultKeyPressHandler
        
        self.result.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
                
        self.cons.setPlainText('select * from (select * from m_load_history_info)')
        
        spliter.addWidget(self.cons)
        spliter.addWidget(self.result)
        spliter.addWidget(self.log)
        
        spliter.setSizes([300, 200, 10])
        
        vbar.addWidget(spliter)
        
        self.setLayout(vbar)
        
        self.SQLSyntax = SQLSyntaxHighlighter(self.cons.document())
        #console = QPlainTextEdit()