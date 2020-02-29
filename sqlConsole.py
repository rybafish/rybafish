from PyQt5.QtWidgets import (QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem,
        QTabWidget, QApplication, QAbstractItemView, QMenu, QFileDialog, QMessageBox)

from PyQt5.QtGui import QTextCursor, QColor, QFont, QFontMetricsF, QPixmap, QIcon
from PyQt5.QtGui import QTextCharFormat, QBrush, QPainter

from PyQt5.QtCore import QTimer, QPoint

from PyQt5.QtCore import Qt, QSize

import time

import db

import utils
from utils import cfg

import re

import lobDialog, searchDialog
from utils import dbException, log

from SQLSyntaxHighlighter import SQLSyntaxHighlighter

import datetime
import binascii
import os


from utils import resourcePath

from PyQt5.QtCore import pyqtSignal

def generateTabName():
    
    base = 'sql'
    i = 0
    
    while i < 100:
        if i > 0:
            fname = 'sql%i' % i
        else:
            fname = 'sql'
            
        print('checking ', fname)
        if not os.path.isfile(fname+'.sqbkp'):
            return fname
            
        i += 1


class console(QPlainTextEdit):

    executionTriggered = pyqtSignal()
    closeSignal = pyqtSignal()
    goingToCrash = pyqtSignal()
    
    openFileSignal = pyqtSignal()
    saveFileSignal = pyqtSignal()
    
    connectSignal = pyqtSignal()
    disconnectSignal = pyqtSignal()

    def __init__(self):
        self.lock = False
        
        self.haveHighlighrs = False
        self.highlightedWords = []
        
        self.braketsHighlighted = False
        #self.braketsHighlightedPos = []
        
        self.modifiedLayouts = []

        self.lastSearch = ''    #for searchDialog
        
        super().__init__()

        fontSize = utils.cfg('console-fontSize', 10)
        
        try: 
            font = QFont ('Consolas', fontSize)
        except:
            font = QFont ()
            font.setPointSize(fontSize)
            
        self.setFont(font)
        
        
        #self.setStyleSheet('{selection-background-color: #48F; selection-color: #fff;}')
        self.setStyleSheet('selection-background-color: #48F')

        self.setTabStopDistance(QFontMetricsF(font).width(' ') * 4)
        
        self.cursorPositionChanged.connect(self.cursorPositionChangedSignal) # why not just overload?
        self.selectionChanged.connect(self.consSelection)
        
    def clearHighlighting(self):
        self.lock = True
        
        txt = self.toPlainText()
        cursor = QTextCursor(self.document())

        format = cursor.charFormat()
        format.setBackground(QColor('white'))

        #utils.timerStart()
        
        for w in self.highlightedWords:
            cursor.setPosition(w[0],QTextCursor.MoveAnchor)
            cursor.setPosition(w[1],QTextCursor.KeepAnchor)

            cursor.setCharFormat(format)
            
        self.highlightedWords.clear()
        
        self.lock = False
        
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
        
    def searchWord(self, str):
        if self.lock:
            return
            
        self.lock = True
        #print('lets search/highlight: ' + str)
        
        #for i in range(self.cons.blockCount()):
        #    txtline = self.cons.document().findBlockByLineNumber(i)
            
        #line = txtline.text()
        line = self.toPlainText()
        
        st = 0
        
        while st >= 0:
            st = line.find(str, st)
            
            if st >= 0:
                # really this should be a \b regexp here instead of isalnum
                
                if st > 0:
                    sample = line[st-1:st+len(str)+1]
                else:
                    sample = line[0:len(str)+1]

                #mask = r'.?\b%s\b.?' % (str)
                #mask = r'.\b%s\b.' % (str)
                mask = r'\W?%s\W' % (str)
                
                if re.match(mask, sample):
                    self.highlight(self.document(), st, st+len(str))
                    #print('lets highlight: ' + str)
                else:
                    pass
                    #print('nope [%s]/(%s)' % (sample, mask))
                
                st += len(str)
                    
        self.lock = False
            
        return
        
    def consSelection(self):
    
        return
    
        if self.lock:
            return
            
        cursor = self.textCursor()
        selected = cursor.selectedText()
        
        if len(selected) == 0 and self.haveHighlighrs:
            self.clearHighlighting()
            
            self.haveHighlighrs = False
            return

        txtline = self.document().findBlockByLineNumber(cursor.blockNumber())
        line = txtline.text()

        if re.match('\w+$', selected):
            if re.search('\\b%s\\b' % selected, line):
                #we are not sure that this is exactly same found as the one selected...
                self.searchWord(selected)

        return
        
    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)

        menuExec = cmenu.addAction('Execute selection\tF8')
        cmenu.addSeparator()
        menuOpenFile = cmenu.addAction('Open File in this console')
        menuSaveFile = cmenu.addAction('Save File\tCtrl+S')
        cmenu.addSeparator()
        menuDisconnect = cmenu.addAction('Disconnect from the DB')
        menuConnect = cmenu.addAction('(re)connecto to the DB')
        menuClose = cmenu.addAction('Close console\tCtrl+W')

        if cfg('developmentMode'):
            cmenu.addSeparator()
            menuTest = cmenu.addAction('Test menu')
            createDummyTable = cmenu.addAction('Generate test result')
            createClearResults = cmenu.addAction('Clear results')

        action = cmenu.exec_(self.mapToGlobal(event.pos()))


        if cfg('developmentMode'):
            if action == createDummyTable:
                self._parent.closeResults()
                self._parent.dummyResultTable2(10 * 1000)

            if action == createClearResults:
                self._parent.closeResults()


        if action == menuExec:
            self.executionTriggered.emit()
        elif action == menuDisconnect:
            self.disconnectSignal.emit()
        elif action == menuConnect:
            self.connectSignal.emit()
        elif action == menuOpenFile:
            self.openFileSignal.emit()
        elif action == menuSaveFile:
            self.saveFileSignal.emit()
        elif action == menuClose:
            self.closeSignal.emit()
        elif cfg('developmentMode') and action == menuTest:
            cursor = self.textCursor()
            cursor.removeSelectedText()
            cursor.insertText('123')
            self.setTextCursor(cursor)
            pass
            
    def findString(self, str):
    
        self.lastSearch = str
    
        def select(start, stop):
            cursor = QTextCursor(self.document())

            cursor.setPosition(start,QTextCursor.MoveAnchor)
            cursor.setPosition(stop,QTextCursor.KeepAnchor)
            
            self.setTextCursor(cursor)
            
        text = self.toPlainText().lower()
        
        st = self.textCursor().position()
        
        st = text.find(str.lower(), st)
        
        if st >= 0:
            select(st, st+len(str))
        else:
            #search from the start
            st = text.find(str, 0)
            if st >= 0:
                select(st, st+len(str))
        
    def duplicateLine (self):
        cursor = self.textCursor()
        
        if cursor.selection().isEmpty():
            txtline = self.document().findBlockByLineNumber(cursor.blockNumber())
            
            #self.moveCursor(QTextCursor.EndOfLine, QTextCursor.MoveAnchor)
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.MoveAnchor)
            cursor.insertText('\n' + txtline.text())
        else:
            txt = cursor.selectedText()

            cursor.clearSelection()
            cursor.insertText(txt)

    def moveLine(self, direction):

        cursor = self.textCursor()
        pos = cursor.position()
        
        lineFrom = self.document().findBlock(pos)

        startPos = lineFrom.position()
        endPos = startPos + len(lineFrom.text())

        if direction == 'down':
            lineTo = self.document().findBlock(endPos + 1)
        else:
            lineTo = self.document().findBlock(startPos - 1)

        cursor.beginEditBlock() #deal with unso/redo
        # select original line
        cursor.setPosition(startPos, QTextCursor.MoveAnchor)
        cursor.setPosition(endPos, QTextCursor.KeepAnchor)
        
        textMove = cursor.selectedText()
        
        # replace it by text from the new location
        cursor.insertText(lineTo.text())

        # now put moving text in place
        startPos = lineTo.position()
        endPos = startPos + len(lineTo.text())

        cursor.setPosition(startPos, QTextCursor.MoveAnchor)
        cursor.setPosition(endPos, QTextCursor.KeepAnchor)

        cursor.insertText(textMove)
        
        cursor.endEditBlock() #deal with unso/redo
        
        self.repaint()
        
        cursor.setPosition(startPos, QTextCursor.MoveAnchor)
        cursor.setPosition(startPos + len(textMove), QTextCursor.KeepAnchor)
        
        self.setTextCursor(cursor)
        
    def tabKey(self):
        
        cursor = self.textCursor()
        
        cursor.beginEditBlock() # deal with undo/redo
        
        txt = cursor.selectedText()
        
        stPos = cursor.selectionStart()
        endPos = cursor.selectionEnd()
        
        stLine = self.document().findBlock(stPos).blockNumber()
        endLineBlock = self.document().findBlock(endPos)
        endLine = endLineBlock.blockNumber()
        
        #check the selection end position
        if stLine != endLine and endLineBlock.position() < endPos:
            endLine += 1 # endLine points to the next line after the block we move
        
        if not cursor.hasSelection() or (stLine == endLine):
            cursor.removeSelectedText()
            cursor.insertText('    ')
        else:

            for i in range(stLine, endLine):
                line = self.document().findBlockByLineNumber(i)
                pos = line.position()

                #move selection start to start of the line
                if i == stLine:
                    stPos = pos

                cursor.setPosition(pos, QTextCursor.MoveAnchor)
                cursor.insertText('    ')
                
            #calculate last line end position to update selection
            endPos = pos + len(line.text()) + 1
            
            cursor.clearSelection()
            cursor.setPosition(stPos, QTextCursor.MoveAnchor)
            cursor.setPosition(endPos, QTextCursor.KeepAnchor)
            
        self.setTextCursor(cursor)
        
        cursor.endEditBlock() 
        
    def shiftTabKey(self):
        
        cursor = self.textCursor()
        
        cursor.beginEditBlock() # deal with undo/redo
        
        txt = cursor.selectedText()
        
        stPos = cursor.selectionStart()
        endPos = cursor.selectionEnd()
        
        stLine = self.document().findBlock(stPos).blockNumber()
        endLineBlock = self.document().findBlock(endPos)
        endLine = endLineBlock.blockNumber()
        
        #check the selection end position
        if endLineBlock.position() < endPos:
            endLine += 1 # endLine points to the next line after the block we move
        
        if not cursor.hasSelection() or (stLine == endLine):
            #cursor.removeSelectedText()
            
            line = self.document().findBlockByLineNumber(stLine)
            pos = line.position()
            cursor.setPosition(pos, QTextCursor.MoveAnchor)

            txt = line.text()[:4]
            
            if len(txt) > 0 and txt[0] == '\t':
                cursor.deleteChar()
            else:
                l = min(len(txt), 4)
                for j in range(l):

                    if txt[j] == ' ':
                        cursor.deleteChar()
                    else:
                        break
            
        else:

            for i in range(stLine, endLine):

                line = self.document().findBlockByLineNumber(i)
                pos = line.position()
                cursor.setPosition(pos, QTextCursor.MoveAnchor)

                #move selection start to start of the line
                if i == stLine:
                    stPos = pos

                txt = line.text()[:4]
                
                l = min(len(txt), 4)
                
                if len(txt) > 0 and txt[0] == '\t':
                    cursor.deleteChar()
                else:
                    for j in range(l):
                        if txt[j] == ' ':
                            cursor.deleteChar()
                        else:
                            break
                
            #calculate last line end position to update selection

            if endLine < self.document().blockCount():
                endPos = pos + len(line.text()) + 1
            else:
                endPos = pos + len(line.text())
            
            cursor.clearSelection()
            cursor.setPosition(stPos, QTextCursor.MoveAnchor)
            
            cursor.setPosition(endPos, QTextCursor.KeepAnchor)
            
        self.setTextCursor(cursor)
        
        cursor.endEditBlock() 
    
    def keyPressEvent (self, event):
        
        modifiers = QApplication.keyboardModifiers()

        if event.key() == Qt.Key_F8 or  event.key() == Qt.Key_F9:
            self.executionTriggered.emit()

        elif modifiers & Qt.ControlModifier and event.key() == Qt.Key_D:
            self.duplicateLine()

        elif modifiers & Qt.ControlModifier and event.key() == Qt.Key_Down:
            self.moveLine('down')

        elif modifiers & Qt.ControlModifier and event.key() == Qt.Key_Up:
            self.moveLine('up')

        elif event.key() == Qt.Key_Backtab and not (modifiers & Qt.ControlModifier):
            self.shiftTabKey()

        elif event.key() == Qt.Key_Tab and not (modifiers & Qt.ControlModifier):
            self.tabKey()
            
        elif modifiers & Qt.ControlModifier and modifiers & Qt.ShiftModifier and event.key() == Qt.Key_U:
            cursor = self.textCursor()
            
            txt = cursor.selectedText()
            
            cursor.insertText(txt.upper())
            
        elif modifiers == Qt.ControlModifier and event.key() == Qt.Key_U:
            cursor = self.textCursor()
            
            txt = cursor.selectedText()
            
            cursor.insertText(txt.lower())
            
        elif modifiers == Qt.ControlModifier and event.key() == Qt.Key_F:
                search = searchDialog.searchDialog(self.lastSearch)
                
                search.findSignal.connect(self.findString)
                
                search.exec_()
    
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
            #pos = self.braketsHighlightedPos
            #self.highlightBraket(self.document(), pos[0], False)
            #self.highlightBraket(self.document(), pos[1], False)
            
            for lol in self.modifiedLayouts:
            
                lo = lol[0]
                af = lol[1]
                
                    
                #lo.clearAdditionalFormats()
                lo.setAdditionalFormats(af)
                
            self.modifiedLayouts.clear()
            
            self.viewport().repaint()
            
            self.braketsHighlighted = False

    def cursorPositionChangedSignal(self):
    
        if cfg('noBraketsHighlighting'):
            return
    
        self.checkBrakets()
        
    def highlightBrakets(self, block, pos1, pos2, mode):
        #print ('highlight here: ', pos1, pos2)
    
        txtblk1 = self.document().findBlock(pos1)
        txtblk2 = self.document().findBlock(pos2)
        
        delta1 = pos1 - txtblk1.position()
        delta2 = pos2 - txtblk2.position()
        
        charFmt = QTextCharFormat()
        charFmt.setForeground(QColor('#F00'))
        
        #fnt = charFmt.font().setWeight(QFont.Bold)
        #charFmt.setFont(fnt)
        
        lo1 = txtblk1.layout()
        r1 = lo1.FormatRange()
        r1.start = delta1
        r1.length = 1
        
        if txtblk1.position() == txtblk2.position():
            lo2 = lo1
            
            r2 = lo2.FormatRange()
            r2.start = delta2
            r2.length = 1
            
            r1.format = charFmt
            r2.format = charFmt

            af = lo1.additionalFormats()
            
            lo1.setAdditionalFormats(af + [r1, r2])
            
            self.modifiedLayouts = [[lo1, af]]
        else:
            lo2 = txtblk2.layout()

            r2 = lo2.FormatRange()
            r2.start = delta2
            r2.length = 1

            r1.format = charFmt
            r2.format = charFmt
            
            af1 = lo1.additionalFormats()
            af2 = lo2.additionalFormats()
            
            lo1.setAdditionalFormats(af1 + [r1])
            lo2.setAdditionalFormats(af2 + [r2])
            
            self.modifiedLayouts = [[lo1, af1], [lo2, af2]]
        
        self.viewport().repaint()
        
    def highlightBraketDepr(self, block, pos, mode):
        #print ('highlight here: ', block.text(), start, stop)
        
        cursor = QTextCursor(block)

        cursor.setPosition(pos, QTextCursor.MoveAnchor)
        cursor.setPosition(pos+1, QTextCursor.KeepAnchor)
        
        format = cursor.charFormat()
        
        font = cursor.charFormat().font()
        
        if mode == True:
            font.setBold(True)
            format.setForeground(QColor('#C22'))
            #format.setBackground(QColor('#CCF'))
            format.setFont(font)
        else:
            font.setBold(False)
            format.setForeground(QColor('black'));
            #format.setBackground(QColor('white'));
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
                #self.braketsHighlightedPos = [bPos, pb]
                #self.highlightBraket(self.document(), bPos, True)
                #self.highlightBraket(self.document(), pb, True)        
                self.highlightBrakets(self.document(), bPos, pb, True)

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
        
        self.cols = [] #column descriptions
        self.rows = [] # actual data 
        
        self.headers = [] # column names
        
        super().__init__()
        
        verticalHeader = self.verticalHeader()
        verticalHeader.setSectionResizeMode(verticalHeader.Fixed)
        
        scale = 1

        
        itemFont = QTableWidgetItem('').font()
        #QFont ('SansSerif', 10)
        #rowHeight = scale * QFontMetricsF(itemFont).height() + 7 
        rowHeight = scale * QFontMetricsF(itemFont).height() + 8
        
        #rowHeight = 19
        
        verticalHeader.setDefaultSectionSize(rowHeight)
        
        self.setWordWrap(False)
        self.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: lightgray }")
        
        self.cellDoubleClicked.connect(self.dblClick) # LOB viewer

        self.keyPressEvent = self.resultKeyPressHandler
        
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

        # any style change resets everything to some defaults....
        # like selected color, etc. just gave up.

        #self.setStyleSheet('QTableWidget::item {padding: 2px; border: 1px}')
        #self.setStyleSheet('QTableWidget::item {margin: 3px; border: 1px}')
        
        #self.setStyleSheet('QTableWidget::item {padding: 2px; border: 1px; selection-background-color}')
        #self.setStyleSheet('QTableWidget::item:selected {padding: 2px; border: 1px; background-color: #08D}')
        
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
            log('attempted to detach resultset with no _resultset_id')
            return
            
        result_str = binascii.hexlify(bytearray(self._resultset_id)).decode('ascii')
        
        if self._connection is None:
            return
        
        if self.detached == False:
            log('closing the resultset: %s' % result_str)
            try:
                db.close_result(self._connection, self._resultset_id) 
                self.detached = True
            except Exception as e:
                log('[!] Exception: ' + str(e))
        else:
            log('[?] already detached?: %s' % result_str)

    def detachCB(self):
        print('detach timer triggered')
        
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
    
        #for c in cols:
        #    print(c)
    
        row0 = []

        for c in cols:
            row0.append(c[0])
            
        self.headers = row0.copy()
           
        self.setColumnCount(len(row0))

        self.setHorizontalHeaderLabels(row0)
        self.resizeColumnsToContents();
        
        self.setRowCount(len(rows))
        
        adjRow = 10 if len(rows) >= 10 else len(rows)
        
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
                    
                    if cfg('highlightLOBs'):
                        item.setBackground(QBrush(QColor('#f4f4f4')))
                    
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop);

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
                
                '''
                if db.ifNumericType(cols[c][1]):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                '''
                
                self.setItem(r, c, item) # Y-Scale
                
                #self.setBackgroundColor(r, c, QColor('#123'))

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
                if self.rows[i][j]:
                    blob = self.rows[i][j].read()
                else:
                    self.log('null value')
                
            self.rows[i][j].seek(0) #rewind just in case
        else:
            blob = str(self.rows[i][j])

        lob = lobDialog.lobDialog(blob)
        
        lob.exec_()

        return False
        
        
class sqlConsole(QWidget):

    nameChanged = pyqtSignal(['QString'])

    def __init__(self, window, config, tabname = None):
    
        self.window = None # required for the timer
        
        self.conn = None
        self.config = None
        self.timer = None           # keep alive timer
        self.rows = []
        
        self.fileName = None
        self.unsavedChanges = False
        
        self.backup = None
    
        self.results = [] #list of resultsets
        self.resultTabs = None #tabs widget

        super().__init__()
        self.initUI()
        
        if tabname is not None:
            self.tabname = tabname
            
            if os.path.isfile(tabname+'.sqbkp'):
                #looks we had a backup?
                self.openFile(tabname+'.sqbkp')
                
                self.unsavedChanges = True

        self.cons.textChanged.connect(self.textChangedS)
        
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
            
        self.cons.connectSignal.connect(self.connectDB)
        self.cons.disconnectSignal.connect(self.disconnectDB)

    def textChangedS(self):
        
        if self.unsavedChanges == False: #and self.fileName is not None:
            if self.cons.toPlainText() == '':
                return
                
            self.unsavedChanges = True
                
            self.nameChanged.emit(self.tabname + ' *')
    
    def delayBackup(self):
    
        if self.unsavedChanges == False:
            return
    
        if self.fileName is not None:
            filename = self.fileName + '.sqbkp'
            self.backup = filename
        else:
            filename = self.tabname + '.sqbkp'
            self.backup = filename
            
        fnsecure = filename

        # apparently filename is with normal slashes, but getcwd with backslashes on windows, :facepalm:
        cwd = os.getcwd()
        cwd = cwd.replace('\\','/') 
        
        fnsecure = filename.replace(cwd, '..')
    
        try:
            with open(filename, 'w') as f:
            
                data = self.cons.toPlainText()

                f.write(data)
                f.close()

                log('%s backup saved' % fnsecure)
        
        except Exception as e:
            # so sad...
            log('[!] %s backup NOT saved' % fnsecure)
            log('[!]' + str(e))
            
    def keyPressEvent(self, event):
   
        modifiers = QApplication.keyboardModifiers()

        '''
        
        those both now operated from main window...
        
        if modifiers == Qt.ControlModifier:
            if event.key() == Qt.Key_S:
                self.delayBackup()
                self.saveFile()
            elif event.key() == Qt.Key_O:
                self.openFile()
        '''
                
        super().keyPressEvent(event)

    def saveFile(self):
        if self.fileName is None:
            fname = QFileDialog.getSaveFileName(self, 'Save as...', '','*.sql')
            
            filename = fname[0]
            
            if filename == '':
                return
            
            self.fileName = filename

        else:
            filename = self.fileName

        try:
            with open(filename, 'w') as f:
            
                data = self.cons.toPlainText()

                f.write(data)
                f.close()

                basename = os.path.basename(filename)
                self.tabname = basename.split('.')[0]
                self.nameChanged.emit(self.tabname)
                
                self.unsavedChanges = False
                
                if self.backup is not None:
                    try:
                        log('delete backup: %s' % self.backup)
                        os.remove(self.backup)
                    except:
                        log('delete backup faileld, passing')
                        # whatever...
                        pass

                self.log('File saved')
                
        except Exception as e:
            self.log ('Error: ' + str(e), True)
    
    def openFile(self, filename = None):
    
        if filename is None:
            fname = QFileDialog.getOpenFileName(self, 'Open file', '','*.sql')
            filename = fname[0]

        if filename == '':
            return
        
        try:
            with open(filename, 'r') as f:
                data = f.read()
                f.close()
        except Exception as e:
            log ('Error: ' + str(e), True)
            self.log ('Error: ' + str(e), True)
            
            
        basename = os.path.basename(filename)
        self.tabname = basename.split('.')[0]
        
        ext = basename.split('.')[1]
        
        self.cons.setPlainText(data)
        
        if ext == 'sqbkp':
            pass
        else:
            self.fileName = filename

        self.unsavedChanges = False

        self.nameChanged.emit(self.tabname)
    
    def close(self, cancelPossible = True):
    
        log('closing sql console...')
        
        self.closeResults()
    
        if self.unsavedChanges:
            answer = utils.yesNoDialog('Unsaved changes', 'There are unsaved changes in "%s" tab, do yo want to save?' % self.tabname, cancelPossible)
            
            if answer is None: #cancel button
                return False

            if answer == False:
                try:
                    log('delete backup: %s' % (str(self.tabname+'.sqbkp')))
                    os.remove(self.tabname+'.sqbkp')
                except:
                    log('delete backup faileld, passing')
                    # whatever...
                    pass
            
            if answer == True:
                self.saveFile()

        try: 
            if self.conn is not None:
                db.close_connection(self.conn)
        except dbException as e:
            log('close() db exception: '+ str(e))
            super().close()
            return True
        except Exception as e:
            log('close() exception: '+ str(e))
            super().close()
            return True
        

        super().close()
        
        return True
            
    def disconnectDB(self):
        try: 
            if self.conn is not None:
                db.close_connection(self.conn)
                self.conn = None
                self.log('\nDisconnected')
                
        except dbException as e:
            log('close() db exception: '+ str(e))
            self.log('close() db exception: '+ str(e), True)
            self.conn = None # ?
            return
        except Exception as e:
            log('close() exception: '+ str(e))
            self.log('close() exception: '+ str(e), True)
            self.conn = None # ?
            return
        
    def connectDB(self):
        try: 
            if self.conn is not None:
                db.close_connection(self.conn)
                self.conn = None

            self.conn = db.create_connection(self.config)                
            self.log('\nConnected')
            
        except dbException as e:
            log('close() db exception: '+ str(e))
            self.log('close() db exception: '+ str(e), True)
            return
        except Exception as e:
            log('close() exception: '+ str(e))
            self.log('close() exception: '+ str(e), True)
            return

    
    def reconnect(self):

        print('reconnect')

        try: 
            conn = db.create_connection(self.config)
        except Exception as e:
            raise e
        
        if conn is None:
            self.log('[i] Failed to reconnect, dont know what to do next')
            raise Exception('Failed to reconnect, dont know what to do next...')
        else:
            self.log('re-connected')
            self.conn = conn
            
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
            
            
            #model = result.model()
            #model.removeRows(0, 10000)

            result.clear()

            del(result.cols)
            del(result.rows)
            
            if result.LOBs and not result.detached:
                result.detach()
            
            result.destroy()
            #result.deleteLater()
            
            del(result)
            del self.results[i]
            
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
        except Exception as e:
            log('[!] unexpected exception, disable the connection')
            log('[!] %s' % str(e))
            
            self.conn = None
                        
    def log(self, text, error = False):
        #self.logArea.setPlainText(self.logArea.toPlainText() + '\n' + text)
        
        if error:
            self.logArea.appendHtml('<font color = "red">%s</font>' % text);
        else:
            self.logArea.appendPlainText(text)
        
    def dummyResultTable2(self, n):
        row0 = []
    
        cols = [
            ['Name',11],
            ['Integer',3],
            ['Decimal',5]
        ]

        
        rows = []
        for i in range(n):
            row = ['name ' + str(i), i, i/312]
            rows.append(row)
        
        result = self.newResult(self.conn)
        
        result.rows = rows
        result.cols = cols
        
        result.populate()
    
    def dummyResultTable(self):
    
        row0 = []
    
        cols = [
            ['Name',11],
            ['LOB String',26],
            ['Integer',3],
            ['Decimal',5],
            ['Timestamp',16],
        ]
        
        rows = [
                ['name 1','select * from dummy fake blob 1', 1024, 1/12500, datetime.datetime.now()],
                ['name 2','select * from \r\n dummy blob 2', 22254, 2/3, datetime.datetime.now()],
                ['name 3','select 1/16 from dummy blob 3', 654654, 1/16, datetime.datetime.now()],
                ['name 4','''select 10000 from dummy blob 3 
                
                and too many 
                characters''', 654654, 10000, datetime.datetime.now()]
            ]
        
        result = self.newResult(self.conn)
        result._parent = self
        
        result.rows = rows
        result.cols = cols
        
        result.populate()
    
    def executeSelection(self):
    
        txt = ''
        statements = []
        F9 = True
        
        self.delayBackup()
        
        def isItCreate(s):
            '''
                if in create procedure now?
            '''
            
            if re.match('^\s*create\s+procedure\W.*', s, re.IGNORECASE) or \
                re.match('^\s*do\s+begin\W.*', s, re.IGNORECASE):
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
            
            #print('exec: [%s]' % str)
            
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

        cursorPos = None

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

        # print('from to: ', scanFrom, scanTo)
        
        # startDelta = 0
        # clearDelta = False
        
        for i in range(scanFrom, scanTo):
            c = txt[i]
            
            '''
            if clearDelta:
                startDelta = 0
                clearDelta = False
            '''

            #print('['+c+']')
            if not insideString and c == ';':
                #print(i)
                if not insideProc:
                    str = ''
                    stop = i
                    # clearDelta = True
                    continue
                else:
                    if isItEnd(str[-10:]):
                        insideProc = False
                        str = ''
                        stop = i
                        # clearDelta = True
                        continue
            
            if str == '':
                #happens when semicolon detected.
                # print('str = \'\'', 'startDelta: ', startDelta)
                if c in (' ', '\n', '\t'):
                    # warning: insideString logic skipped here (as it is defined below this line
                    # skip leading whitespaces
                    # print(start, stop, cursorPos, i)
                    # startDelta += 1
                    continue
                else:
                    #if F9 and (start <= cursorPos < stop):
                    #reeeeeallly not sure!
                    if F9 and (start <= cursorPos <= stop) and (start < stop):
                        print('start <= cursorPos <= stop:', start, cursorPos, stop)
                        selectSingle(start, stop)
                        break
                    else:
                        if not F9:
                            statementDetected(start, stop)
                        
                    start = i
                    str = str + c
            else:
                str = str + c
                #print(str)

            if not insideString and c == '\'':
                insideString = True
                continue
                
            if insideString and c == '\'':
                insideString = False
                continue
                
            if not insideProc and isItCreate(str[:64]):
                insideProc = True


        '''
        print('F9?', F9)
        print('cursorPos', cursorPos)
        # print('startDelta', startDelta)
        print('scanFrom, scanTo', scanFrom, scanTo)
        print('start, stop', start, stop)
        print('str:', str)
        '''
        
        if stop == 0:
            # no semicolon met
            stop = scanTo
        
        #if F9 and (start <= cursorPos < stop):
        #print so not sure abous this change
        if F9 and (start <= cursorPos <= stop) and (start < stop):
            print('m1')
            selectSingle(start, stop)
        elif F9 and (start > stop and start <= cursorPos): # no semicolon in the end
            print('m2')
            selectSingle(start, scanTo)
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
            
        elif F9 and (start > stop and start <= cursorPos): # no semicolon in the end
            #print('-> [%s] ' % txt[start:scanTo])

            result = self.newResult(self.conn)
            self.executeStatement(txt[start:scanTo], result)

        else:
            for st in statements:
                #print('--> [%s]' % st)
                
                result = self.newResult(self.conn)
                self.executeStatement(st, result)
                
                #self.update()
                self.repaint()

        return
    
    def connectionLost(self, err_str = ''):
        '''
            very synchronous call, it holds controll until connection status resolved
        '''
        
        print('Connection Lost...')
        
        msgBox = QMessageBox()
        msgBox.setWindowTitle('Connection lost')
        msgBox.setText('Connection failed, reconnect?')
        msgBox.setStandardButtons(QMessageBox.Yes| QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        iconPath = resourcePath('ico\\favicon.ico')
        msgBox.setWindowIcon(QIcon(iconPath))
        msgBox.setIcon(QMessageBox.Warning)

        reply = None
        
        while reply != QMessageBox.No and self.conn is None:
            reply = msgBox.exec_()
            if reply == QMessageBox.Yes:
                try:
                    self.log('Reconnecting to %s:%s...' % (self.config['host'], str(self.config['port'])))
                    self.reconnect()
                    self.log('Connection restored')
                except Exception as e:
                    log('Reconnect failed: %s' % e)
                    self.log('Reconnect failed: %s' % str(e))

        if reply == QMessageBox.Yes:
            return True
        else:
            return False
            
    def executeStatement(self, sql, result):
        '''
            executes the string without any analysis
            result filled
        '''
        
        self.renewKeepAlive()
        
        if cfg('loglevel', 3) > 3:
            log('console execute: [%s]' % (sql))
        
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
                
            m = re.search(r'^\s*select\s+top\s+(\d+)', sql, re.I)
            
            if m:
                explicitLimit = True
                resultSizeLimit = int(m.group(1))
            else:
                explicitLimit = False
                resultSizeLimit = cfg('resultSize', 1000)
                
            txtSub = txtSub.replace('\n', ' ')
            txtSub = txtSub.replace('\t', ' ')
            
            self.log('\nExecute: ' + txtSub + suffix)
            self.logArea.repaint()
            
            result.rows, result.cols, dbCursor = db.execute_query_desc(self.conn, sql, [], resultSizeLimit)
            
            rows = result.rows
            cols = result.cols
            
            t1 = time.time()

            #logText = 'Query execution time: %s s' % (str(round(t1-t0, 3)))


            logText = 'Query execution time: %s' % utils.formatTime(t1-t0)
            
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
                    
            if result.LOBs == False and not explicitLimit and resultSize == resultSizeLimit:
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
            
            if e.type == dbException.CONN:
                log('connection lost, should we close it?')

                try: 
                    db.close_connection(self.conn)
                except dbException as e:
                    log('[?] ' + str(e))
                except:
                    log('[!] ' + str(e))
                    
                self.conn = None
                
                self.connectionLost()
            return

        result.populate()
            
        return

    '''
    def consKeyPressHandler(self, event):
        
        # modifiers = QApplication.keyboardModifiers()
        
        if event.key() == Qt.Key_F8 or  event.key() == Qt.Key_F9:
            self.delayBackup()
            executeSelection()

        else:
            #have to clear each time in case of input right behind the braket
            if self.braketsHighlighted:
                self.clearBraketsHighlight()
                
            # print explisit call of the normal processing? this looks real weird
            # shouldnt it be just super().keyPressEvent(event) instead?
            # may be if I inherited QPlainTextEdit...
            QPlainTextEdit.keyPressEvent(self.cons, event)
    '''
        
    def initUI(self):
        '''
            main sqlConsole UI 
        '''
        vbar = QVBoxLayout()
        hbar = QHBoxLayout()
        
        #self.cons = QPlainTextEdit()
        self.cons = console()
        
        self.cons._parent = self
        
        self.cons.executionTriggered.connect(self.executeSelection)
        
        self.cons.openFileSignal.connect(self.openFile)
        self.cons.goingToCrash.connect(self.delayBackup)
        
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