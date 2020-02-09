from PyQt5.QtWidgets import (QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem,
        QTabWidget, QApplication, QAbstractItemView, QMenu, QFileDialog)

from PyQt5.QtGui import QTextCursor, QColor, QFont, QFontMetricsF, QPixmap
from PyQt5.QtCore import QTimer

from PyQt5.QtCore import Qt, QSize

import time

import db

import utils
from utils import cfg

import re

import lobDialog

from utils import dbException, log

from SQLSyntaxHighlighter import SQLSyntaxHighlighter

import binascii
import datetime
import os

from PyQt5.QtCore import pyqtSignal

class console(QPlainTextEdit):

    executionTriggered = pyqtSignal()

    def __init__(self):
        self.braketsHighlighted = False
        self.braketsHighlightedPos = []
        
        super().__init__()

        fontSize = utils.cfg('console-fontSize', 10)
        
        try: 
            font = QFont ('Consolas', fontSize)
        except:
            font = QFont ()
            font.setPointSize(fontSize)
            
        self.setFont(font)

        self.setTabStopDistance(QFontMetricsF(font).width(' ') * 4)
        
        self.cursorPositionChanged.connect(self.cursorPositionChangedSignal) # why not just overload?
        
        '''
        self.cons.keyPressEvent = self.consKeyPressHandler
        self.cons.cursorPositionChanged.connect(self.cursorPositionChanged)
        
        self.cons.selectionChanged.connect(self.consSelection) #does not work
        '''
        
    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)

        menuExec = cmenu.addAction('Execute selection')
        menuDummy = cmenu.addAction('test')
        
        action = cmenu.exec_(self.mapToGlobal(event.pos()))

        if action == menuExec:
            self.executionTriggered.emit()
            
        if action == menuDummy:
            print('dummy menu')
            
    def keyPressEvent (self, event):
        
        modifiers = QApplication.keyboardModifiers()

        if event.key() == Qt.Key_F8 or  event.key() == Qt.Key_F9:
            self.executionTriggered.emit()

        elif modifiers & Qt.ControlModifier and modifiers & Qt.ShiftModifier and event.key() == Qt.Key_U:
            cursor = self.textCursor()
            
            txt = cursor.selectedText()
            
            cursor.insertText(txt.upper())
            
        elif modifiers == Qt.ControlModifier and event.key() == Qt.Key_U:
            cursor = self.textCursor()
            
            txt = cursor.selectedText()
            
            cursor.insertText(txt.lower())
    
        else:
            #have to clear each time in case of input right behind the braket
            if self.braketsHighlighted:
                self.clearBraketsHighlight()
                
            # print explisit call of the normal processing? this looks real weird
            # shouldnt it be just super().keyPressEvent(event) instead?
            # may be if I inherited QPlainTextEdit...
            #QPlainTextEdit.keyPressEvent(self.cons, event)
            super().keyPressEvent(event)

    def clearBraketsHighlight(self):
        if self.braketsHighlighted:
            pos = self.braketsHighlightedPos
            self.highlightBraket(self.document(), pos[0], False)
            self.highlightBraket(self.document(), pos[1], False)
            self.braketsHighlighted = False

    def cursorPositionChangedSignal(self):
        self.checkBrakets()
        
    def highlightBraket(self, block, pos, mode):
        #print ('highlight here: ', block.text(), start, stop)
        cursor = QTextCursor(block)

        cursor.setPosition(pos, QTextCursor.MoveAnchor)
        cursor.setPosition(pos+1, QTextCursor.KeepAnchor)
        
        format = cursor.charFormat()
        
        font = cursor.charFormat().font()
        
        if mode == True:
            font.setBold(True)
            format.setForeground(QColor('#C22'))
            format.setBackground(QColor('#CCF'))
            format.setFont(font)
        else:
            font.setBold(False)
            format.setForeground(QColor('black'));
            format.setBackground(QColor('white'));
            format.setFont(font)

        '''
        if mode == True:
            format.setBackground(QColor('#8AF'))
        else:
            format.setBackground(QColor('white'));
        '''
            
        cursor.setCharFormat(format)
        
        self.haveHighlighrs = True
        
    def checkBrakets(self):
    
        if self.braketsHighlighted:
            self.clearBraketsHighlight()
    
        cursor = self.textCursor()
        pos = cursor.position()

        text = self.toPlainText()

        textSize = len(text)
        
        def scanPairBraket(pos, shift):
        
            braket = text[pos]
        
            #print('scanPairBraket', pos, braket, shift)
        
            depth = 0
        
            if braket == ')':
                pair = '('
            elif braket == '(':
                pair = ')'
            elif braket == '[':
                pair = ']'
            elif braket == ']':
                pair = '['
            else:
                return -1
            
            i = pos + shift
            
            if braket in (')', ']'):
                # skan forward
                stop = 0
                step = -1
            else:
                stop = textSize-1
                step = 1
                
            
            while i != stop:
                i += step
                ch = text[i]
                
                if ch == braket:
                    depth += 1
                    continue
                
                if ch == pair:
                    if depth == 0:
                        return i
                    else:
                        depth -=1
                    
            return -1
            
        # text[pos] - symboll right to the cursor
        # when pos == textSize text[pos] - crash
        
        bPos = None
        
        if pos > 0 and text[pos-1] in ('(', '[', ')', ']', ):
            brLeft = True
        else:
            brLeft = False
            
        if pos < textSize and text[pos] in ('(', '[', ')', ']', ):
            brRight = True
        else:
            brRight = False
            
            
        if brLeft or brRight:
        
            if brLeft:
                bPos = pos-1
                if text[pos-1] in ('(', '['):
                    shift = 0
                else:
                    shift = 0
                pb = scanPairBraket(bPos, shift)
            else:
                bPos = pos
                shift = 0
                pb = scanPairBraket(bPos, shift)

            #print(brLeft, brRight, bPos, pb)
            
            if pb >= 0:
                self.braketsHighlighted = True
                self.braketsHighlightedPos = [bPos, pb]
                self.highlightBraket(self.document(), bPos, True)
                self.highlightBraket(self.document(), pb, True)        

class resultSet(QTableWidget):
    '''
        Implements the result set widget, basically QTableWidget with minor extensions
        
        Created to show the resultset (one result tab), destroyed when re-executed.

        Table never refilled.
    '''

    def __init__(self, conn):
        self._resultset_id = None    # filled manually right after execute_query

        self._connection = conn
        
        self.LOBs = False            # if the result contains LOBs
        self.detached = None         # supposed to be defined only if LOBs = True
        self.detachTimer = None      # results detach timer
        
        self.fileName = None
        self.unsavedChanges = False
        
        self.cols = [] #column descriptions
        self.rows = [] # actual data 
        
        self.headers = [] # column names
        
        super().__init__()
        
        verticalHeader = self.verticalHeader()
        verticalHeader.setSectionResizeMode(verticalHeader.Fixed)
        
        scale = 1

        
        itemFont = QTableWidgetItem('').font()
        #QFont ('SansSerif', 10)
        rowHeight = scale * QFontMetricsF(itemFont).height() + 7
        
        #rowHeight = 19
        
        verticalHeader.setDefaultSectionSize(rowHeight)
        
        self.setWordWrap(False)
        self.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: lightgray }")
        
        self.cellDoubleClicked.connect(self.dblClick) # LOB viewer

        self.keyPressEvent = self.resultKeyPressHandler
        
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)

        copyColumnName = cmenu.addAction('Copy Column Name')
        copyTableScreen = cmenu.addAction('Take a Screenshot')
        
        action = cmenu.exec_(self.mapToGlobal(event.pos()))

        i = self.currentColumn()

        if action == copyColumnName:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.cols[i][0])

        if action == copyTableScreen:
            w = self.verticalHeader().width() + self.horizontalHeader().length() + 1
            h = self.verticalHeader().length() + self.horizontalHeader().height() + 1
            #pixmap = QPixmap(self.size())
            
            if w > self.size().width():
                w = self.size().width()
            
            if h > self.size().height():
                h = self.size().height()
            
            pixmap = QPixmap(QSize(w, h))
            
            self.render(pixmap)
            
            QApplication.clipboard().setPixmap(pixmap)
                
    def detach(self):
        if self._resultset_id is None:
            # could be if the result did not have result: for example DDL or error statement
            # but it's strange we are detachung it...
            print('atttemnted to detach resultset with no _resultset_id')
            return
            
        result_str = binascii.hexlify(bytearray(self._resultset_id)).decode('ascii')
        
        if self.detached == False:
            log('closing the resultset: %s' % result_str)
            db.close_result(self._connection, self._resultset_id) 
            self.detached = True
        else:
            log('[?] already detached?: %s' % result_str)

    def detachCB(self):
        print('detach timer triggered')
        #print('do we need to stop the timer?')
        self.detachTimer.stop()
        self.detachTimer = None
        self.detach()
        
    def triggerDetachTimer(self, window):
        log('Setting detach timer')
        self.detachTimer = QTimer(window)
        self.detachTimer.timeout.connect(self.detachCB)
        self.detachTimer.start(1000 * 256)
    
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
                if val is None:
                    values.append(utils.cfg('nullStringCSV', '?'))
                elif db.ifNumericType(vType):
                    values.append(utils.numberToStrCSV(val, False))
                elif db.ifRAWType(vType):
                    values.append(val.hex())
                elif db.ifTSType(vType):
                    values.append(val.isoformat(' ', timespec='milliseconds'))
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
                    # copy column
                    
                    rowIndex = []
                    colIndex = {}

                    # very likely not the best way to order list of pairs...
                    
                    for c in sm.selectedIndexes():
                    
                        r = c.row() 
                    
                        if r not in rowIndex:
                            rowIndex.append(r)
                            
                        if r in colIndex.keys():
                            colIndex[r].append(c.column())
                        else:
                            colIndex[r] = []
                            colIndex[r].append(c.column())
                    
                    rowIndex.sort()
                    
                    rows = []
                    
                    for r in rowIndex:
                        colIndex[r].sort()

                        values = []
                        
                        for c in colIndex[r]:
                        
                            value = self.rows[r][c]
                            vType = self.cols[c][1]
                            
                            if value is None:
                                values.append(utils.cfg('nullStringCSV', '?'))
                            else:
                                if db.ifBLOBType(vType):
                                    values.append(str(value.encode()))
                                else:
                                    if db.ifNumericType(vType):
                                        values.append(utils.numberToStrCSV(value, False))
                                    elif db.ifRAWType(vType):
                                        values.append(value.hex())
                                    elif db.ifTSType(vType):
                                        values.append(value.isoformat(' ', timespec='milliseconds'))
                                    else:
                                        values.append(str(value))
                                        
                        rows.append( ';'.join(values))

                    result = '\n'.join(rows)
                    
                    QApplication.clipboard().setText(result)
                        
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
                
                if val is None:
                    val = utils.cfg('nullString', '?')
                    
                    item = QTableWidgetItem(val)
                elif db.ifNumericType(cols[c][1]):
                
                    if db.ifDecimalType(cols[c][1]):
                        #val = utils.numberToStr(val, 3)
                        val = utils.numberToStrCSV(val)
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
                elif db.ifTSType(cols[c][1]):
                    val = val.isoformat(' ', timespec='milliseconds') 
                    item = QTableWidgetItem(val)
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
            if self.detached:
                self.log('warning: LOB resultset already detached')
                
                if db.ifBLOBType(self.cols[j][1]):
                    blob = str(self.rows[i][j].encode())
                else:
                    blob = str(self.rows[i][j])
            else:
                blob = self.rows[i][j].read()
                
            self.rows[i][j].seek(0) #rewind just in case
        else:
            blob = str(self.rows[i][j])

        lob = lobDialog.lobDialog(blob)
        
        lob.exec_()

        return False
        
        
class sqlConsole(QWidget):

    nameChanged = pyqtSignal(['QString'])

    def keyPressEvent(self, event):
   
        modifiers = QApplication.keyboardModifiers()
       
        if modifiers == Qt.ControlModifier:
            if event.key() == Qt.Key_S:
                fname = QFileDialog.getSaveFileName(self, 'Save as...', '','*.sql')
                    
            elif event.key() == Qt.Key_O:
                fname = QFileDialog.getOpenFileName(self, 'Open file', '','*.sql')
                filename = fname[0]
                
                try:
                    with open(filename, 'r') as f:
                        data = f.read()
                except Exception as e:
                    print (str(e))
                    
                tabname = os.path.basename(filename)
                tabname = tabname.split('.')[0]
                
                self.cons.setPlainText(data)
                self.cons.fileName = filename

                self.nameChanged.emit(tabname)
               
        super().keyPressEvent(event)

    def close(self):

        try: 
            db.close_connection(self.conn)
        except dbException as e:
            raise e
            return
        except:
            return

        print('<---- close')
        super().close()

    def __init__(self, window, config):
    
        self.window = None # required for the timer
        
        self.conn = None
        self.lock = False
        self.config = None
        self.timer = None           # keep alive timer
        self.rows = []
    
        self.haveHighlighrs = False
        self.highlightedWords = []
    
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
            
    def newResult(self, conn):
        
        result = resultSet(conn)
        result.log = self.log
        
        if len(self.results) > 0:
            rName = 'Results ' + str(len(self.results))
        else:
            rName = 'Results'
        
        self.results.append(result)
        self.resultTabs.addTab(result, rName)
        
        self.resultTabs.setCurrentIndex(len(self.results) - 1)
        
        return result
        
    def closeResults(self):
        '''
            closes all results tabs, detaches resultsets if any LOBs
        '''
        '''
        if self.detachResults:
            if self.detachTimer is not None:
                self.detachTimer.stop()
                self.detachTimer = None
                
            self.detachResultSets()
        '''
    
        for i in range(len(self.results) - 1, -1, -1):
            self.resultTabs.removeTab(i)
            
            result = self.results[i]
            result.clear()
            
            if result.LOBs and not result.detached:
                result.detach()
            
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

        format = cursor.charFormat()
        format.setBackground(QColor('white'))

        #utils.timerStart()
        
        for w in self.highlightedWords:
            cursor.setPosition(w[0],QTextCursor.MoveAnchor)
            cursor.setPosition(w[1],QTextCursor.KeepAnchor)

            cursor.setCharFormat(format)
            
        self.highlightedWords.clear()
        #utils.timeLap('remove hl')
        #utils.timePrint()
        
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
        
        while st >= 0:
            st = line.find(str, st)
            
            if st >= 0:
                # really this should be a \b regexp here instead of isalnum
                '''
                if (st>0 and not (line[st-1]).isalnum()) and (st < len (line) and not (line[st+1]).isalnum()):
                    self.highlight(self.cons.document(), st, st+len(str))
                '''
                
                if st > 0:
                    sample = line[st-1:st+len(str)+1]
                else:
                    sample = line[0:len(str)+1]

                #mask = r'.?\b%s\b.?' % (str)
                #mask = r'.\b%s\b.' % (str)
                mask = r'\W?%s\W' % (str)
                
                if re.match(mask, sample):
                    self.highlight(self.cons.document(), st, st+len(str))
                    #print('lets highlight: ' + str)
                else:
                    pass
                    #print('nope [%s]/(%s)' % (sample, mask))
                
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
        
        self.highlightedWords.append([start, stop])
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
            ['Decimal',5],
            ['Timestamp',16],
        ]
        
        rows = [
                ['name 1','select * from dummy fake blob 1', 1/12500, datetime.datetime.now()],
                ['name 2','select * from dummy blob 2', 2/3, datetime.datetime.now()],
                ['name 3','select 1/16 from dummy blob 3', 1/16, datetime.datetime.now()],
                ['name 4','select 10000 from dummy blob 3', 10000, datetime.datetime.now()]
            ]
        
        result = self.newResult(self.conn)
        
        result.rows = rows
        result.cols = cols
        
        result.populate()
    
    def executeSelection(self):
    
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
                it shall ignore whitspaces
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
        
        #if F9 and (start <= cursorPos < stop):
        #print so not sure abous this change
        if F9 and (start <= cursorPos <= stop):
            #print('-> [%s] ' % txt[start:stop])
            
            result = self.newResult(self.conn)
            
            self.executeStatement(txt[start:stop], result)
        else:
            for st in statements:
                #print('--> [%s]' % st)
                
                result = self.newResult(self.conn)
                self.executeStatement(st, result)
                
                #self.update()
                self.repaint()

        return
    
    def executeStatement(self, sql, result):
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
            
            resultSizeLimit = cfg('resultSize', 1000)
            
            result.rows, result.cols, dbCursor = db.execute_query_desc(self.conn, sql, [], resultSizeLimit)
            
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

            result._resultset_id = dbCursor._resultset_id   #requred for detach (in case of detach)
            result.detached = False
            result_str = binascii.hexlify(bytearray(dbCursor._resultset_id)).decode('ascii')
            print('saving the resultset id: %s' % result_str)
            
            for c in cols:
                if db.ifLOBType(c[1]):
                    self.detachResults = True
                    result.LOBs = True
                    
                    result.triggerDetachTimer(self.window)
                    break
                    
            if result.LOBs == False and resultSize == resultSizeLimit:
                print('detaching due to possible SUSPENDED')
                result.detach()
                print('done')
            
            lobs = ', +LOBs' if result.LOBs else ''
            
            logText += '\n' + str(len(rows)) + ' rows fetched' + lobs
            if resultSize == utils.cfg('maxResultSize', 1000): logText += ', note: this is the resultSize limit'
            
            self.log(logText)
        except dbException as e:
            err = str(e)
            self.log('DB Exception:' + err, True)
            return

        result.populate()
            
        return
            
    def consKeyPressHandler(self, event):
        
        # modifiers = QApplication.keyboardModifiers()
        
        if event.key() == Qt.Key_F8 or  event.key() == Qt.Key_F9:
            executeSelection()

        else:
            #have to clear each time in case of input right behind the braket
            if self.braketsHighlighted:
                self.clearBraketsHighlight()
                
            # print explisit call of the normal processing? this looks real weird
            # shouldnt it be just super().keyPressEvent(event) instead?
            # may be if I inherited QPlainTextEdit...
            QPlainTextEdit.keyPressEvent(self.cons, event)

        
    def initUI(self):
        vbar = QVBoxLayout()
        hbar = QHBoxLayout()
        
        #self.cons = QPlainTextEdit()
        self.cons = console()
        
        self.cons.executionTriggered.connect(self.executeSelection)
        
        self.resultTabs = QTabWidget()
        
        spliter = QSplitter(Qt.Vertical)
        self.logArea = QPlainTextEdit()
        
        spliter.addWidget(self.cons)
        spliter.addWidget(self.resultTabs)
        spliter.addWidget(self.logArea)
        
        spliter.setSizes([300, 200, 10])
        
        vbar.addWidget(spliter)
        
        self.setLayout(vbar)
        
        self.SQLSyntax = SQLSyntaxHighlighter(self.cons.document())
        #console = QPlainTextEdit()