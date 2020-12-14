from PyQt5.QtWidgets import (QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem,
        QTabWidget, QApplication, QAbstractItemView, QMenu, QFileDialog, QMessageBox)

from PyQt5.QtGui import QTextCursor, QColor, QFont, QFontMetricsF, QPixmap, QIcon
from PyQt5.QtGui import QTextCharFormat, QBrush, QPainter

from PyQt5.QtCore import QTimer, QPoint

from PyQt5.QtCore import Qt, QSize

from PyQt5.QtCore import QObject, QThread

import time, sys

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

class sqlWorker(QObject):
    finished = pyqtSignal()

    def __init__(self, cons):
        super().__init__()
        
        self.cons = cons
        self.args = []
    
    def executeStatement(self):
    
        #print('0 --> main thread method')
        
        if not self.args:
            log('[!] sqlWorker with no args?')
            self.finished.emit()
            return
            
        sql, result, refreshMode = self.args
        
        cons = self.cons # cons - sqlConsole class itself, not just a console...

        cons.wrkException = None
    
        if cfg('loglevel', 3) > 3:
            log('console execute: [%s]' % (sql))
        
        if len(sql) >= 2**17 and cons.conn.large_sql != True:
            log('reconnecting to hangle large SQL')
            #print('replace by a pyhdb.constant? pyhdb.protocol.constants.MAX_MESSAGE_SIZE')
            
            db.largeSql = True
            
            try: 
                cons.conn = db.console_connection(cons.config)
            except dbException as e:
                err = str(e)
                #
                # cons.log('DB Exception:' + err, True)
                
                cons.wrkException = 'DB Exception:' + err
                
                cons.connect = None
                self.finished.emit()
                return
                
        if cons.conn is None:
            #cons.log('Error: No connection')
            cons.wrkException = 'no db connection'
            self.finished.emit()
            return
            
        #execute the query
        
        try:
            # t0 = time.time()
            
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
            
            #print('start sql')
            result.rows, result.cols, dbCursor = db.execute_query_desc(cons.conn, sql, [], resultSizeLimit)
            #print('sql finished')
            
            self.dbCursor = dbCursor
            
        except dbException as e:
            err = str(e)
            
            # fixme 
            # cons.log('DB Exception:' + err, True)
            
            cons.wrkException = 'DB Exception:' + err
            
            if e.type == dbException.CONN:
                # fixme 
                log('connection lost, should we close it?')

                try: 
                    db.close_connection(cons.conn)
                except dbException as e:
                    log('[?] ' + str(e))
                except:
                    log('[!] ' + str(e))
                    
                cons.conn = None
                
                log('connectionLost() used to be here, but now no UI possible from the thread')
                #cons.connectionLost()
                
        if result.rows:
            resultSize = len(result.rows)
        else:
            resultSize = -1

        if cons.wrkException is None:
            result._resultset_id = dbCursor._resultset_id   #requred for detach (in case of detach)
            result.detached = False
            
            if dbCursor._resultset_id:
                result_str = binascii.hexlify(bytearray(dbCursor._resultset_id)).decode('ascii')
            else:
                result_str = 'None'
                
            log('saving the resultset id: %s' % result_str)

            if result.cols is not None:
                for c in result.cols:
                    if db.ifLOBType(c[1]):
                        result.LOBs = True
                        
                        break
                    
            if result.LOBs == False and (not explicitLimit and resultSize == resultSizeLimit):
                log('detaching due to possible SUSPENDED')
                result.detach()

        #print('1 <-- self.finished.emit()')
        self.finished.emit()
        #time.sleep(0.5)
        
        #print('4 <-- main thread method <-- ')

def generateTabName():

    '''
        not used actually 01.12.20
    '''
    
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
    
    executionTriggered = pyqtSignal(['QString'])
    
    closeSignal = pyqtSignal()
    goingToCrash = pyqtSignal()
    
    openFileSignal = pyqtSignal()
    saveFileSignal = pyqtSignal()
    
    connectSignal = pyqtSignal()
    disconnectSignal = pyqtSignal()
    
    def insertTextS(self, str):
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        cursor.insertText(str)
        
        self.setFocus()

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
        
    def insertFromMimeData(self, src):
        '''
            for some reason ctrl+v does not trigger highliqter
            so do it manually
        '''
        a = super().insertFromMimeData(src)
        
        cursor = self.textCursor()
        block = self.document().findBlockByLineNumber(cursor.blockNumber())
        
        self.SQLSyntax.rehighlightBlock(block)  # enforce highlighting 
        
        return a
        
        
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
      
    def newLayout(self, position, lo, af):
        
        for l in self.modifiedLayouts:
            if l[0] == position:
                #this layout already in the list
                return
            
        self.modifiedLayouts.append([position, lo, af])
            
    def highlight(self):
    
        blkStInit = None
        blkStCurrent = None
    
        charFmt = QTextCharFormat()
        charFmt.setBackground(QColor('#8F8'))

        for p in self.highlightedWords:
            txtblk = self.document().findBlock(p[0])
            
            blkStCurrent = txtblk.position()
    
            delta = p[0] - blkStCurrent
            
            lo = txtblk.layout()
            
            r = lo.FormatRange()
            
            r.start = delta
            r.length = p[1] - p[0]
            
            r.format = charFmt
            
            af = lo.additionalFormats()
            
            if blkStInit != blkStCurrent:
                #self.modifiedLayouts.append([blkStCurrent, lo, af])
                self.newLayout(blkStCurrent, lo, af)
                
                blkStInit = blkStCurrent

            lo.setAdditionalFormats(af + [r])

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
        
        self.highlightedWords = []
        
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
                    #self.highlight(self.document(), st, st+len(str))
                    self.highlightedWords.append([st, st+len(str)])
                
                st += len(str)
                    
        self.lock = False
        
        if self.highlightedWords:
            self.highlight()
            
            self.viewport().repaint()
            
        return
        
    def consSelection(self):
    
        if cfg('noWordHighlighting'):
            return
    
        if self.lock:
            return
            
        cursor = self.textCursor()
        selected = cursor.selectedText()
        
        if self.haveHighlighrs:
            self.clearHighlighting()

        txtline = self.document().findBlockByLineNumber(cursor.blockNumber())
        line = txtline.text()

        if re.match('\w+$', selected):
            if re.search('\\b%s\\b' % selected, line):
                self.searchWord(selected)

        return
        
    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)
        
        menuExec = cmenu.addAction('Execute selection\tF8')
        menuExecNP = cmenu.addAction('Execute without parsing')
        menuExecLR = cmenu.addAction('Execute but leave results')
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
                self._parent.dummyResultTable2(200 * 1000)

            if action == createClearResults:
                self._parent.closeResults()


        if action == menuExec:
            self.executionTriggered.emit('normal')
        if action == menuExecNP:
            self.executionTriggered.emit('no parsing')
        if action == menuExecLR:
            self.executionTriggered.emit('leave results')
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
            self.executionTriggered.emit('normal')

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
                self.clearHighlighting()
                
            # print explisit call of the normal processing? this looks real weird
            # shouldnt it be just super().keyPressEvent(event) instead?
            # may be if I inherited QPlainTextEdit...
            #QPlainTextEdit.keyPressEvent(self.cons, event)
            super().keyPressEvent(event)

    def clearHighlighting(self):
        if self.braketsHighlighted or self.haveHighlighrs:
            #pos = self.braketsHighlightedPos
            #self.highlightBraket(self.document(), pos[0], False)
            #self.highlightBraket(self.document(), pos[1], False)
            
            for lol in self.modifiedLayouts:
            
                lo = lol[1]
                af = lol[2]
                    
                #lo.clearAdditionalFormats()
                lo.setAdditionalFormats(af)
                
            self.modifiedLayouts.clear()
            
            self.viewport().repaint()
            
            self.braketsHighlighted = False
            self.haveHighlighrs = False

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
            
            #self.modifiedLayouts = [[lo1, af]]
            #self.modifiedLayouts.append([lo1, af])
            self.newLayout(txtblk1.position(), lo1, af)
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
            
            #self.modifiedLayouts = [[lo1, af1], [lo2, af2]]
            #self.modifiedLayouts.append([[lo1, af1], [lo2, af2]])
            #self.modifiedLayouts.append([lo1, af1])
            #self.modifiedLayouts.append([lo2, af2])
            self.newLayout(txtblk1.position(), lo1, af1)
            self.newLayout(txtblk2.position(), lo2, af2)
        
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
            self.clearHighlighting()
    
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
    
    insertText = pyqtSignal(['QString'])

    def __init__(self, conn):
    
        self._resultset_id = None    # filled manually right after execute_query

        self._connection = conn
        
        self.statement = None        # statements string (for refresh)
        
        self.LOBs = False            # if the result contains LOBs
        self.detached = None         # supposed to be defined only if LOBs = True
        self.detachTimer = None      # results detach timer
        
        self.cols = [] # column descriptions
        self.rows = [] # actual data 
        
        self.headers = [] # column names
        
        super().__init__()
        
        verticalHeader = self.verticalHeader()
        verticalHeader.setSectionResizeMode(verticalHeader.Fixed)
        
        scale = 1

        
        fontSize = utils.cfg('result-fontSize', 10)
        
        font = QFont ()
        font.setPointSize(fontSize)
        
        self.setFont(font)
        
        itemFont = QTableWidgetItem('').font()
        
        #rowHeight = scale * QFontMetricsF(itemFont).height() + 7 
        rowHeight = scale * QFontMetricsF(itemFont).height() + 8
        
        #rowHeight = 19
        
        verticalHeader.setDefaultSectionSize(rowHeight)
        
        self.setWordWrap(False)
        self.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: lightgray }")
        
        self.cellDoubleClicked.connect(self.dblClick) # LOB viewer

        self.keyPressEvent = self.resultKeyPressHandler
        
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        
        self.horizontalHeader().setMinimumSectionSize(0)

        # any style change resets everything to some defaults....
        # like selected color, etc. just gave up.

        #self.setStyleSheet('QTableWidget::item {padding: 2px; border: 1px}')
        #self.setStyleSheet('QTableWidget::item {margin: 3px; border: 1px}')
        
        #self.setStyleSheet('QTableWidget::item {padding: 2px; border: 1px; selection-background-color}')
        #self.setStyleSheet('QTableWidget::item:selected {padding: 2px; border: 1px; background-color: #08D}')
        
    def contextMenuEvent(self, event):
        def normalize_header(header):
            if header.isupper() and header[0].isalpha():
                if cfg('lowercase-columns', False):
                    h = header.lower()
                else:
                    h = header
            else:
                h = '"%s"' % (header)
                
            return h
            
        def prepareColumns():
            headers = []
            headers_norm = []
            
            sm = self.selectionModel()
            
            for c in sm.selectedIndexes():
                r, c = c.row(), c.column()

                cname = self.headers[c]
                
                if cname not in headers:
                    headers.append(cname)
                
                
            for h in headers:
                headers_norm.append(normalize_header(h))
                
            return headers_norm
            
       
        cmenu = QMenu(self)

        copyColumnName = cmenu.addAction('Copy Column Name(s)')
        copyTableScreen = cmenu.addAction('Take a Screenshot')
        
        cmenu.addSeparator()
        insertColumnName = cmenu.addAction('Insert Column Name(s)')
        copyFilter = cmenu.addAction('Generate Filter Condition')
        
        action = cmenu.exec_(self.mapToGlobal(event.pos()))

        i = self.currentColumn()

        '''
        if action == copyColumnName:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.cols[i][0])
        '''
        
        if action == insertColumnName:
            headers_norm = prepareColumns()
                
            names = ', '.join(headers_norm)
            
            self.insertText.emit(names)
            
        if action == copyColumnName:
            clipboard = QApplication.clipboard()
            
            headers_norm = prepareColumns()
                
            names = ', '.join(headers_norm)

            clipboard.setText(names)

        if action == copyFilter:
            sm = self.selectionModel()
            
            values = []
                        
            for c in sm.selectedIndexes():
                r, c = c.row(), c.column()

                value = self.rows[r][c]
                cname = self.headers[c]

                if db.ifNumericType(self.cols[c][1]):
                    values.append('%s = %s' % (normalize_header(cname), value))
                elif db.ifTSType(self.cols[c][1]):
                    values.append('%s = \'%s\'' % (normalize_header(cname), utils.timestampToStr(value)))
                else:
                    values.append('%s = \'%s\'' % (normalize_header(cname), str(value)))
                    
            filter = ' and '.join(values)

            self.insertText.emit(filter)
            
            #QApplication.clipboard().setText(filter)
            
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
            log('[!] attempted to detach resultset with no _resultset_id')
            return
            
        if self._resultset_id:
            result_str = binascii.hexlify(bytearray(self._resultset_id)).decode('ascii')
        else:
            result_str = 'None'
        
        if self._connection is None:
            return
        
        if self.detached == False and self._resultset_id is not None:
            log('closing the resultset: %s' % result_str)
            try:
                db.close_result(self._connection, self._resultset_id) 
                self.detached = True
            except Exception as e:
                log('[!] Exception: ' + str(e))
        else:
            log('[?] already detached?: %s' % result_str)

    def detachCB(self):
        log('detach timer triggered')
        
        if self.detachTimer is None:
            log('[?] why the timer is None?')
            return
            
        self.detachTimer.stop()
        self.detachTimer = None
        self.detach()
        
    def triggerDetachTimer(self, window):
        log('Setting detach timer')
        self.detachTimer = QTimer(window)
        self.detachTimer.timeout.connect(self.detachCB)
        self.detachTimer.start(1000 * 300)
    
    def csvRow(self, r):
        
        values = []
        
        # print varchar values to be quoted by "" to be excel friendly
        for i in range(self.columnCount()):
            #values.append(table.item(r, i).text())

            val = self.rows[r][i]
            vType = self.cols[i][1]

            if val is None:
                values.append(utils.cfg('nullStringCSV', ''))
            elif db.ifBLOBType(vType):
                values.append(str(val.encode()))
            else:
                if db.ifNumericType(vType):
                    values.append(utils.numberToStrCSV(val, False))
                elif db.ifRAWType(vType):
                    values.append(val.hex())
                elif db.ifTSType(vType):
                    #values.append(val.isoformat(' ', timespec='milliseconds'))
                    values.append(utils.timestampToStr(val))
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
                                values.append(utils.cfg('nullStringCSV', ''))
                            else:
                                if db.ifBLOBType(vType):
                                    values.append(str(value.encode()))
                                else:
                                    if db.ifNumericType(vType):
                                        values.append(utils.numberToStrCSV(value, False))
                                    elif db.ifRAWType(vType):
                                        values.append(value.hex())
                                    elif db.ifTSType(vType):
                                        #values.append(value.isoformat(' ', timespec='milliseconds'))
                                        values.append(utils.timestampToStr(value))
                                    else:
                                        values.append(str(value))
                                        
                        rows.append( ';'.join(values))

                    result = '\n'.join(rows)
                    
                    QApplication.clipboard().setText(result)
        
        else:
            super().keyPressEvent(event)
            
    def populate(self, refreshMode = False):
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
        
        
        if not refreshMode:
            self.resizeColumnsToContents()
        
        self.setRowCount(len(rows))
        
        adjRow = 10 if len(rows) >= 10 else len(rows)

        #return -- it leaks even before this point
        
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
#                        val = str(val)
                        if val is None:
                            val = utils.cfg('nullString', '?')
                        else:
                            val = str(val)
                            
                    item = QTableWidgetItem(val)
                    
                    if cfg('highlightLOBs'):
                        item.setBackground(QBrush(QColor('#f4f4f4')))
                    
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop);

                elif db.ifRAWType(cols[c][1]): #VARBINARY
                    val = val.hex()
                    
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop);
                    
                elif db.ifVarcharType(cols[c][1]):
                    item = QTableWidgetItem(val)
                    
                    if '\n' in val:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop);
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter);
                
                elif db.ifTSType(cols[c][1]):
                    #val = val.isoformat(' ', timespec='milliseconds') 
                    val = utils.timestampToStr(val)
                    item = QTableWidgetItem(val)
                else:
                    val = str(val)
                        
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter);
                    
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                
                
                self.setItem(r, c, item) # Y-Scale

            if r == adjRow - 1 and not refreshMode:
                self.resizeColumnsToContents();
                
                for i in range(len(row0)):
                    if self.columnWidth(i) >= 512:
                        self.setColumnWidth(i, 512)
                        
    def dblClick(self, i, j):
    
        if db.ifLOBType(self.cols[j][1]):
            if self.detached:
                self.log('warning: LOB resultset already detached', True)
                
                if db.ifBLOBType(self.cols[j][1]):
                    blob = str(self.rows[i][j].encode())
                else:
                    blob = str(self.rows[i][j])
            else:
                if self.rows[i][j] is not None:
                    
                    value = self.rows[i][j].read()
                    
                    if db.ifBLOBType(self.cols[j][1]):
                        blob = str(value.decode("utf-8", errors="ignore"))
                    else:
                        blob = str(value)
                else:
                    blob = '<Null value>'

            if self.rows[i][j]:
                self.rows[i][j].seek(0) #rewind just in case
        else:
            blob = str(self.rows[i][j])

        lob = lobDialog.lobDialog(blob)
        
        lob.exec_()

        return False
        
class logArea(QPlainTextEdit):
    def __init__(self):
        super().__init__()

    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)

        '''
        print delete this
        t1 = cmenu.addAction('test html')
        t2 = cmenu.addAction('test text')
        '''
        reset = cmenu.addAction('Clear log')
        
        # cmenu.addSeparator()

        action = cmenu.exec_(self.mapToGlobal(event.pos()))

        if action == reset:
            # will it restore the color?
            self.clear()
            
        '''
        if action == t1:
            self.appendHtml('<font color = "red">%s</font>' % 'red text');
            
        if action == t2:
            self.appendPlainText('random text')
        '''
              
        
class sqlConsole(QWidget):

    nameChanged = pyqtSignal(['QString'])
    selfRaise = pyqtSignal(object)

    def __init__(self, window, config, tabname = None):
    
        self.thread = QThread()             # main sql processing thread
        self.sqlWorker = sqlWorker(self)    # thread worker object (linked to console instance)
        self.sqlRunning = False             # thread is running flag
        
        self.wrkException = None            # thread exit exception
        self.indicator = None               # progress indicator widget, assigned OUTSIDE
        
        self.stQueue = []                   # list of statements to be executed
                                            # for the time being for one statement we do not build a queue, just directly run executeStatement
                                            
        self.t0 = None                      # set on statement start
        
        #todo:
        #self.t0 = None                      # set on queue start
        #self.t1 = None                      # set on statement start

        # one time thread init...
        self.sqlWorker.moveToThread(self.thread)
        self.sqlWorker.finished.connect(self.sqlFinished)
        #self.thread.finished.connect(self.sqlFinished)
        self.thread.started.connect(self.sqlWorker.executeStatement)
        
        #self.window = None # required for the timer
        
        self.conn = None
        self.config = None
        self.timer = None           # keep alive timer
        self.rows = []
        
        self.splitterSizes = None
        
        self.fileName = None
        self.unsavedChanges = False
        
        self.backup = None
    
        self.results = [] #list of resultsets
        self.resultTabs = None # tabs widget
        
        self.noBackup = False

        super().__init__()
        self.initUI()
        
        
        if tabname is not None:
            self.tabname = tabname
        else:
            self.tabname = '!ERROR!'
            
            '''
            # old logic (before layouts), 2020-12-02
            
            if os.path.isfile(tabname+'.sqbkp'):
                #looks we had a backup?
                self.openFile(tabname+'.sqbkp')
                
                self.unsavedChanges = True
            '''

        self.cons.textChanged.connect(self.textChangedS)
        
        if config is None:
            return
        
        try: 
            log('starting console connection')
            self.conn = db.console_connection(config)
            self.config = config
        except dbException as e:
            log('[!] failed!')
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

            '''
            sz = self.parentWidget().size()

            pos = self.mapToGlobal(self.pos())
            
            print(sz)
            print(pos.x(), pos.y())
            
            x = pos.x() + sz.width()/2
            y = pos.y() + sz.height()/2
            
            print(msgBox.size())
            
            #msgBox.move(x, y)
            '''
    
    def delayBackup(self):
        '''
            self.backup is a full path to a backup file
            
            if it's empty - it'll be generated as first step
            if the file already exists - the file will be owerritten
        '''
        
        if self.noBackup:
            return
    
        if self.unsavedChanges == False:
            return
    
        if not self.backup:
            if self.fileName is not None:
                path, file = os.path.split(self.fileName)
                
                file, ext = os.path.splitext(file)
            
                filename = file + '.sqbkp'
            else:
                filename = self.tabname + '.sqbkp'

            script = sys.argv[0]
            path, file = os.path.split(script)
            
            bkpFile = os.path.join(path, 'bkp', filename)
            
            self.backup = bkpFile
            
            bkpPath = os.path.join(path, 'bkp')
            
            if not os.path.isdir(bkpPath):
                os.mkdir(bkpPath)
            
        filename = self.backup
        fnsecure = filename
    
        #print(filename) # C:/home/dug/delme.sql.sqbkp
        #print(os.path.basename(filename)) #delme.sql.sqbkp

        # apparently filename is with normal slashes, but getcwd with backslashes on windows, :facepalm:
        cwd = os.getcwd()
        cwd = cwd.replace('\\','/') 
        
        #remove potentially private info from the trace
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

        if event.key() == Qt.Key_F12:
        
            backTo = self.spliter.sizes()

            if self.splitterSizes is None:
                self.splitterSizes = [4000, 200, 100]
                
            self.spliter.setSizes(self.splitterSizes)
            
            self.splitterSizes = backTo
                
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
                        self.backup = None
                    except:
                        log('delete backup faileld, passing')
                        # whatever...
                        pass

                self.log('File saved')
                
        except Exception as e:
            self.log ('Error: ' + str(e), True)
    
    def openFile(self, filename = None, backup = None):

        log('openFile: %s, %s' % (filename, backup))

        if filename is None and backup is None:
            fname = QFileDialog.getOpenFileName(self, 'Open file', '','*.sql')
            filename = fname[0]

        if filename == '':
            return

        self.fileName = filename
        self.backup = backup
        
        if filename is None:
            filename = backup

        if filename is not None and backup is not None:
            filename = backup           # we open backed up copy
            
        try:
            with open(filename, 'r') as f:
                data = f.read()
                f.close()
        except Exception as e:
            log ('Error: ' + str(e), True)
            self.log ('Error: opening %s / %s' % (self.fileName, self.backup), True)
            self.log ('Error: ' + str(e), True)
            
            return
            
        basename = os.path.basename(filename)
        self.tabname = basename.split('.')[0]
        
        ext = basename.split('.')[1]
        
        self.cons.setPlainText(data)

        self.unsavedChanges = False

        if filename is None:
            self.unsavedChanges = True

        if filename is not None and backup is not None:
            self.unsavedChanges = True

        if self.unsavedChanges:
            self.tabname += ' *'
            
        '''
        if ext == 'sqbkp':
            pass
        else:
            self.fileName = filename
            self.backup = backup
            
        '''

        self.nameChanged.emit(self.tabname)
        
        self.setFocus()
    
    def close(self, cancelPossible = True):
    
        log('closing sql console...')
        
        if self.unsavedChanges and cancelPossible is not None:
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
                
        self.closeResults()

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
            self.indicator.status = 'sync'
            self.indicator.repaint()

            if self.conn is not None:
                db.close_connection(self.conn)
                self.conn = None
                self.log('\nDisconnected')

            self.sqlRunning = False
            self.stQueue.clear()

            self.conn = db.console_connection(self.config)                
            self.log('Connected')
            
        except dbException as e:
            log('close() db exception: '+ str(e))
            self.log('close() db exception: '+ str(e), True)
        except Exception as e:
            log('close() exception: '+ str(e))
            self.log('close() exception: '+ str(e), True)


        self.indicator.status = 'idle'
        self.indicator.repaint()

    
    def reconnect(self):
            
        try: 
            conn = db.console_connection(self.config)
        except Exception as e:
            raise e
        
        if conn is None:
            self.log('[i] Failed to reconnect, dont know what to do next')
            raise Exception('Failed to reconnect, dont know what to do next...')
        else:
            self.log('re-connected')
            self.conn = conn
            
    def newResult(self, conn, st):
        
        result = resultSet(conn)
        result.statement = st
        
        result.log = self.log
        
        result.insertText.connect(self.cons.insertTextS)
        
        if len(self.results) > 0:
            rName = 'Results ' + str(len(self.results)+1)
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
        
        for i in range(len(self.results) - 1, -1, -1):
            
            self.resultTabs.removeTab(i)

            result = self.results[i]
            
            
            #model = result.model()
            #model.removeRows(0, 10000)

            result.clear()

            del(result.cols)
            del(result.rows)
            
            #same code in refresh()
            if result.LOBs and not result.detached:
                if result.detachTimer is not None:
                    log('stopping the detach timer in advance...')
                    result.detachTimer.stop()
                    result.detachTimer = None
                    
                result.detach()
            
            #result.destroy()
            #result.deleteLater()
            
            del(result)
            del self.results[i]
            
        self.results.clear()
            
    def enableKeepAlive(self, window, keepalive):
        log('Setting up DB keep-alive requests: %i seconds' % (keepalive))
        self.timerkeepalive = keepalive
        self.timer = QTimer(window)
        log('keep alive timer')
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
                conn = db.console_connection(self.config)
                if conn is not None:
                    self.conn = conn
                    log('Connection restored automatically')
                else:
                    log('Some connection issue, give up')
                    self.log('Some connection issue, give up', True)
                    self.conn = None
            except:
                log('Connection lost, give up')

                self.indicator.status = 'disconnected'
                self.indicator.repaint()
                self.log('Connection lost, give up', True)
                # print disable the timer?
                self.conn = None
        except Exception as e:
            log('[!] unexpected exception, disable the connection')
            log('[!] %s' % str(e))
            self.log('[!] unexpected exception, disable the connection', True)
            
            self.conn = None
            self.indicator.status = 'disconnected'
            self.indicator.repaint()
            
                        
    def log(self, text, error = False):
        if error:
            self.logArea.appendHtml('<font color = "red">%s</font>' % text);
        else:
            self.logArea.appendPlainText(text)
            
        self.logArea.verticalScrollBar().setValue(self.logArea.verticalScrollBar().maximum())
        
    def dummyResultTable2(self, n):
        row0 = []
    
        cols = [
            ['Name',11],
            ['Integer',3],
            ['Decimal',5],
            ['Str',11]
        ]

        
        rows = []
        for i in range(n):
            row = ['name ' + str(i), i, i/312, 'String String String String String String String String']
            rows.append(row)
        
        result = self.newResult(self.conn, 'select * from dummy')
        
        result.rows = rows
        result.cols = cols
        
        result.populate()

    
    def dummyResultTable(self):
    
        row0 = []
    
        cols = [
            ['Name', 11],
            ['STATEMENT_ID', 26],
            ['7CONNECTION_ID', 3],
            ['/USER_NAME', 5],
            ['dontknow', 61]     # 16 - old timestamp (millisec), 61 - longdate
        ]

        ''''
        ['LOB String',26],
        ['Integer',3],
        ['Decimal',5],
        ['Timestamp',16]
        '''
        
        dt1 = datetime.datetime.strptime('2001-01-10 11:23:07.123456', '%Y-%m-%d %H:%M:%S.%f')
        dt2 = datetime.datetime.strptime('2001-01-10 11:23:07.12300', '%Y-%m-%d %H:%M:%S.%f')
        dt3 = datetime.datetime.strptime('2001-01-10 11:23:07', '%Y-%m-%d %H:%M:%S')
        
        rows = [
                ['name 1','select * from dummy fake blob 1', 1024, 1/12500, dt1],
                ['name 2','select * from \r\n dummy blob 2', 22254, 2/3, dt2],
                ['name 3','select 1/16 from dummy blob 3', 654654, 1/16, dt3],
                ['name 4','''select 10000 from dummy blob 3 
                
                and too many 
                
                \n
                
                characters''', 654654, 10000, datetime.datetime.now()]
            ]
        
        result = self.newResult(self.conn, '<None>')
        result._parent = self
        
        result.rows = rows
        result.cols = cols
        
        result.populate()
    
    def refresh(self, idx):
        '''
            executed the attached statement without full table cleanup
            and header processing
        '''
        
        result = self.results[idx]
        
        #result.clear()

        # same code in close_results
        if result.LOBs and not result.detached:
            if result.detachTimer is not None:
                log('stopping the detach timer in advance...')
                result.detachTimer.stop()
                result.detachTimer = None
                
            result.detach()

        self.executeStatement(result.statement, result, True)
        
    def executeSelection(self, mode):
    
        if self.config is None:
            self.log('No connection')
            return
    
        if mode == 'normal':
            self.executeSelectionParse()
        elif mode == 'no parsing':
            self.executeSelectionNP(False)
        elif mode == 'leave results':
            self.executeSelectionNP(True)
            
    def executeSelectionNP(self, leaveResults):
    
        cursor = self.cons.textCursor()
    
        if cursor.selection().isEmpty():
            self.log('You need to select statement manually for this option')
            return

        if leaveResults == False:
            self.closeResults()

        statement = cursor.selection().toPlainText()
        
        result = self.newResult(self.conn, statement)
        self.executeStatement(statement, result)
        
    def executeSelectionParse(self):
    
        txt = ''
        statements = []
        F9 = True
        
        self.delayBackup()
        
        if self.sqlRunning:
            if len(self.stQueue) > 0:
                self.log('SQL still running, %i left in queue' % (len(self.stQueue)), True)
            else:
                self.log('SQL still running', True)
            
            return
        
        def isItCreate(s):
            '''
                if in create procedure now?
            '''
            
            if re.match('^\s*create\s+procedure\W.*', s, re.IGNORECASE) or \
                re.match('^\s*create\s+function\W.*', s, re.IGNORECASE) or \
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
                        #print('start <= cursorPos <= stop:', start, cursorPos, stop)
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
            selectSingle(start, stop)
        elif F9 and (start > stop and start <= cursorPos): # no semicolon in the end
            selectSingle(start, scanTo)
        else:
            if not F9:
                statementDetected(start, stop)
            
        self.closeResults()
        
        #if F9 and (start <= cursorPos < stop):
        #print so not sure abous this change
        if F9 and (start <= cursorPos <= stop):
            #print('-> [%s] ' % txt[start:stop])
            
            st = txt[start:stop]
            result = self.newResult(self.conn, st)
            self.executeStatement(st, result)
            
        elif F9 and (start > stop and start <= cursorPos): # no semicolon in the end
            #print('-> [%s] ' % txt[start:scanTo])
            st = txt[start:scanTo]

            result = self.newResult(self.conn, st)
            self.executeStatement(st, result)

        else:
            '''
            for st in statements:
                #print('--> [%s]' % st)
                
                result = self.newResult(self.conn, st)
                self.executeStatement(st, result)
                
                #self.update()
                self.repaint()
            '''
            
            if len(statements) > 1:
                self.stQueue = statements.copy()
                self.launchStatementQueue()
            elif len(statements) > 0:
                result = self.newResult(self.conn, statements[0])
                self.executeStatement(statements[0], result)
            else:
                #empty string selected
                pass
            

        return
        
    def launchStatementQueue(self):
        '''
            triggers statements queue execution using new cool QThreads
            list of statements is in self.statements
            
            each execution pops the statement from the list right after thread start!
        '''
        
        #print('0 launchStatementQueue')
        if self.stQueue:
            st = self.stQueue.pop(0)
            result = self.newResult(self.conn, st)
            self.executeStatement(st, result)
    
    def connectionLost(self, err_str = ''):
        '''
            very synchronous call, it holds controll until connection status resolved
        '''
        
        log('Connection Lost...')
        
        msgBox = QMessageBox(self)
        msgBox.setWindowTitle('Connection lost')
        msgBox.setText('Connection failed, reconnect?')
        msgBox.setStandardButtons(QMessageBox.Yes| QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        iconPath = resourcePath('ico\\favicon.ico')
        msgBox.setWindowIcon(QIcon(iconPath))
        msgBox.setIcon(QMessageBox.Warning)

        reply = None
        
        while reply != QMessageBox.No and self.conn is None:
            self.indicator.status = 'sync'
            self.indicator.repaint()
            
            reply = msgBox.exec_()
            if reply == QMessageBox.Yes:
                try:
                    self.log('Reconnecting to %s:%s...' % (self.config['host'], str(self.config['port'])))
                    self.reconnect()
                    self.log('Connection restored')
                    self.indicator.status = 'idle'
                    self.indicator.repaint()
                except Exception as e:
                    self.indicator.status = 'disconnected'
                    self.indicator.repaint()
                    
                    log('Reconnect failed: %s' % e)
                    self.log('Reconnect failed: %s' % str(e))

        if reply == QMessageBox.Yes:
            return True
        else:
            return False
            
    def sqlFinished(self):
        '''
            post-process the sql reaults
            also handle exceptions
        '''
        #print('2 --> sql finished')

        self.thread.quit()
        self.sqlRunning = False
        
        self.indicator.status = 'render'
        self.indicator.repaint()

        if self.wrkException is not None:
            self.log(self.wrkException, True)
            
            #self.thread.quit()
            #self.sqlRunning = False

            if self.conn is not None:
                self.indicator.status = 'error'
            else:
                self.indicator.status = 'disconnected'
                
                log('console connection lost')
                
                self.connectionLost()
                #answer = utils.yesNoDialog('Connectioni lost', 'Connection to the server lost, reconnect?' cancelPossible)
                #if answer == True:


            self.indicator.repaint()
            
            if self.stQueue:
                self.log('Queue processing stopped due to this exception.', True)
                self.stQueue.clear()
            return
        
        sql, result, refreshMode = self.sqlWorker.args
        
        dbCursor = self.sqlWorker.dbCursor
        
        rows = result.rows
        cols = result.cols

        t0 = self.t0
        t1 = time.time()
        
        self.t0 = None

        #logText = 'Query execution time: %s s' % (str(round(t1-t0, 3)))

        logText = 'Query execution time: %s' % utils.formatTime(t1-t0)

        if rows is None or cols is None:
            # it was a DDL or something else without a result set so we just stop
            
            #logText += ', ' + str(self.sqlWorker.rowcount) + ' rows affected'
            #logText += ', ' + str(dbCursor.rowcount) + ' rows affected'
            logText += ', ' + utils.numberToStr(dbCursor.rowcount) + ' rows affected'
            
            self.log(logText)
            
            result.clear()
            return

        resultSize = len(rows)

        if result.LOBs:
            result.triggerDetachTimer(self)

        lobs = ', +LOBs' if result.LOBs else ''

        logText += '\n' + str(len(rows)) + ' rows fetched' + lobs
        if resultSize == cfg('resultSize', 1000): logText += ', note: this is the resultSize limit'

        self.log(logText)

        result.populate(refreshMode)

        self.indicator.status = 'idle'
        self.indicator.repaint()
        
        # should rather be some kind of mutex here...
        
        if self.thread.isRunning():
            time.sleep(0.05)
            
        if self.thread.isRunning():
            log('[!!] self.thread.isRunning()!')
            time.sleep(0.1)

        if self.thread.isRunning():
            log('[!!!] self.thread.isRunning()!')
            time.sleep(0.2)
            
        self.launchStatementQueue()
        
        #print('3 <-- finished')
        
    def executeStatement(self, sql, result, refreshMode = False):
        '''
            triggers thread to execute the string without any analysis
            result populated in callback signal sqlFinished
        '''
        
        if self.sqlRunning:
            self.log('SQL still running...')
            return
        
        self.renewKeepAlive()
        
        suffix = ''
        
        if len(sql) > 128:
            txtSub = sql[:128]
            suffix = '...'
        else:
            txtSub = sql
            
        txtSub = txtSub.replace('\n', ' ')
        txtSub = txtSub.replace('\t', ' ')
        txtSub = txtSub.replace('    ', ' ')
        
        self.log('\nExecute: ' + txtSub + suffix)

        ##########################
        ### trigger the thread ###
        ##########################
        
        self.sqlWorker.args = [sql, result, refreshMode]
        
        self.t0 = time.time()
        self.sqlRunning = True
        
        self.indicator.status = 'running'
        self.indicator.repaint()
        
        #print('--> self.thread.start()')
        self.thread.start()
        #print('<-- self.thread.start()')
            
        return
        
    def resultTabsKey (self, event):
        super().keyPressEvent(event)

        modifiers = QApplication.keyboardModifiers()

        if not ((modifiers & Qt.ControlModifier) or (modifiers & Qt.AltModifier)):
            if event.key() == Qt.Key_F8 or event.key() == Qt.Key_F9 or event.key() == Qt.Key_F5:
                i = self.resultTabs.currentIndex()
                log('refresh %i' % i)
                self.refresh(i) # we refresh by index here...
                return
                
        super().keyPressEvent(event)
        
    def reportRuntime(self):
    
        self.selfRaise.emit(self)
    
        t0 = self.t0
        t1 = time.time()
        
        if t0 is not None:
            self.log('Current run time: %s' % utils.formatTime(t1-t0))
        else:
            self.log('Nothing is running')
    
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
        
        self.resultTabs.keyPressEvent = self.resultTabsKey
                
        self.spliter = QSplitter(Qt.Vertical)
        #self.logArea = QPlainTextEdit()
        self.logArea = logArea()
        
        self.spliter.addWidget(self.cons)
        self.spliter.addWidget(self.resultTabs)
        self.spliter.addWidget(self.logArea)
        
        self.spliter.setSizes([300, 200, 10])
        
        vbar.addWidget(self.spliter)
        
        self.setLayout(vbar)
        
        # self.SQLSyntax = SQLSyntaxHighlighter(self.cons.document())
        self.cons.SQLSyntax = SQLSyntaxHighlighter(self.cons.document())
        #console = QPlainTextEdit()
        
        self.cons.setFocus()