from PyQt5.QtWidgets import (QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidgetItem,
                             QTabWidget, QApplication, QMenu, QFileDialog, QMessageBox, QInputDialog, QLabel,
                             QToolBar, QAction, QStyle, QCheckBox, QToolButton)

from PyQt5.QtGui import QTextCursor, QColor, QFont, QFontMetricsF, QIcon
from PyQt5.QtGui import QTextCharFormat, QBrush, QDesktopServices

from PyQt5.QtCore import QTimer, QPoint

from PyQt5.QtCore import Qt, QSize

from PyQt5.QtCore import QObject, QThread

# crazy sound alert imports
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import QUrl
#from PyQt5.QtCore import WindowState

import time, sys

#import shiboken2
#import sip

from dbi import dbi

import utils
from QPlainTextEditLN import QPlainTextEditLN
from QResultSet import QResultSet

from utils import cfg
from utils import dbException, log
from utils import resourcePath
from utils import normalize_header

import re

import searchDialog
from autocompleteDialog import autocompleteDialog 

from SQLSyntaxHighlighter import SQLSyntaxHighlighter

import datetime
import os
import traceback

#import gc

from sqlparse import format

import customSQLs

from PyQt5.QtCore import pyqtSignal

from profiler import profiler

reExpPlan = re.compile('explain\s+plan\s+for\s+sql\s+plan\s+cache\s+entry\s+(\d+)\s*$', re.I)

class sqlWorker(QObject):
    finished = pyqtSignal()

    def __init__(self, cons):
        super().__init__()
        
        self.psid = None
        
        self.cons = cons
        self.args = []
    
    @profiler
    def executeStatement(self):
    
        #print('0 --> main thread method')
        log(f'[thread] iteslf, child: {int(QThread.currentThreadId())}', 5)
        
        if not self.args:
            log('[!] sqlWorker with no args?')
            self.finished.emit()
            return
            
        sql, result, refreshMode = self.args

        if cfg('dev'): #mapping
            with profiler('map sql'):
                hm = cfg('maphost')
                if hm:
                    sql = sql.replace("'"+hm[1]+"'", "'"+hm[0]+"'")
                pm = cfg('mapport')
                if pm:
                    sql = sql.replace(' = '+pm[1], ' = '+pm[0])
                    sql = sql.replace('='+pm[1], '='+pm[0])

        cons = self.cons # cons - sqlConsole class itself, not just a console...

        cons.wrkException = None
        
        if cons.conn is None:
            #cons.log('Error: No connection')
            cons.wrkException = 'no db connection'
            self.finished.emit()
            return
            
        if self.dbi is None:
            cons.wrkException = 'no dbi instance, please report this error'
            self.finished.emit()
            return

        if self.dbi.name == 'HDB':
            # hdb specific megic here 
            if len(sql) >= 2**17 and cons.conn.large_sql != True:
                log('reconnecting to handle large SQL')
                #print('replace by a pyhdb.constant? pyhdb.protocol.constants.MAX_MESSAGE_SIZE')
                
                self.dbi.largeSql = True
                
                try: 
                    cons.conn = self.dbi.console_connection(cons.config)

                    '''
                    rows = self.dbi.execute_query(cons.conn, "select connection_id from m_connections where own = 'TRUE'", [])
                    
                    if len(rows):
                        self.cons.connection_id = rows[0][0]
                        log('connection open, id: %s' % self.cons.connection_id)
                    '''
                    
                    self.cons.connection_id = self.dbi.get_connection_id(cons.conn)
                        
                except dbException as e:
                    err = str(e)
                    #
                    # cons.log('DB Exception:' + err, True)
                    
                    cons.wrkException = 'DB Exception: ' + err
                    
                    cons.connect = None
                    self.finished.emit()
                    return
                    
                except Exception as e:
                    log(f'[W] Generic exception during executeStatement.connect, thread {int(QThread.currentThreadId())}, {type(e)}, {e}', 1)

                    cwd = os.getcwd()
                    
                    # It has to start with "Thread exception" otherwise logging will be broken in exception processing
                    
                    details = f'Thread exception {type(e)}: {e}\n--\n'

                    (_, _, tb) = sys.exc_info()

                    for s in traceback.format_tb(tb):
                        details += '>>' + s.replace('__n', '_n').replace(cwd, '..')

                    log(details)
                    
                    cons.wrkException = details
                    cons.connect = None
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
            
            m = re.search('^sleep\s?\(\s*(\d+)\s*\)$', txtSub)
            
            if m is not None:
                time.sleep(int(m.group(1)))
                self.rows_list = None
                self.cols_list = None
                dbCursor = None
                psid = None
                self.resultset_id_list = None
            else:
                self.rows_list, self.cols_list, dbCursor, psid = self.dbi.execute_query_desc(cons.conn, sql, [], resultSizeLimit)
            
                if dbCursor:
                    self.resultset_id_list = dbCursor._resultset_id_list
                else:
                    self.resultset_id_list = None
            
            result.explicitLimit = explicitLimit
            result.resultSizeLimit = resultSizeLimit          
            
            #no special treatment for the first resultset anymore
            #result.rows, result.cols = self.rows_list[0], self.cols_list[0]
            #_resultset_id = dbCursor._resultset_id_list[0]
            #print('sql finished')

            self.dbCursor = dbCursor
            self.psid = psid
            
        except dbException as e:
            err = str(e)
            
            # fixme 
            # cons.log('DB Exception:' + err, True)
            
            cons.wrkException = 'DB Exception: ' + err
            
            if e.type == dbException.CONN:
                # fixme 
                log('connection lost, should we close it?')

                try: 
                    self.dbi.close_connection(cons.conn)
                except dbException as e:
                    log('[?] ' + str(e))
                except:
                    log('[!] ' + str(e))
                    
                cons.conn = None
                cons.connection_id = None
                
                log('connectionLost() used to be here, but now no UI possible from the thread')
                #cons.connectionLost()
        
        except Exception as e:
            log(f'[W] Generic exception during executeStatement, thread {int(QThread.currentThreadId())}, {type(e)}, {e}', 1)

            cwd = os.getcwd()
            
            # It has to start with "Thread exception" otherwise logging will be broken in exception processing
            
            details = f'Thread exception {type(e)}: {e}\n--\n'
            #trace = traceback.StackSummary.format()
            #trace = traceback.format_exc().splitlines()
            (_, _, tb) = sys.exc_info()

            for s in traceback.format_tb(tb):
                details += '>>' + s.replace('__n', '_n').replace(cwd, '..')

            log(details)
            cons.wrkException = details
            
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
            
        #print('checking ', fname)
        
        if not os.path.isfile(fname+'.sqbkp'):
            return fname
            
        i += 1


class console(QPlainTextEditLN):
#class console(QPlainTextEdit):
    
    executionTriggered = pyqtSignal(['QString'])
    
    log = pyqtSignal(['QString'])
    
    closeSignal = pyqtSignal()
    goingToCrash = pyqtSignal()
    
    openFileSignal = pyqtSignal()
    saveFileSignal = pyqtSignal()
    
    connectSignal = pyqtSignal()
    disconnectSignal = pyqtSignal()
    abortSignal = pyqtSignal()
    
    explainSignal = pyqtSignal(['QString'])
    
    autocompleteSignal = pyqtSignal()

    def insertTextS(self, str):
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        cursor.insertText(str)
        
        self.setFocus()

    def __init__(self, parent):
        self.lock = False
        
        self.haveHighlighrs = False #have words highlighted
        self.bracketsHighlighted = False

        self.highlightedWords = [] # list of (start, stop) tuples of highlighed words
        
        
        self.modifiedLayouts = [] # backup of the original layouts: tuples (position, layout, additionalFormats)
                                  # position - block position (start of the paragraph)
                                  # layout - hz
                                  # af - list of modifications as a result of syntax highlighting, for example
        
        '''
        self.modifiedLayouts = {}
        
        self.modifiedLayouts['br'] = [] #Brackets only this one used as work around 
        self.modifiedLayouts['w'] = [] #words
        '''
        
        self.manualSelection = False
        self.manualSelectionPos = []
        self.manualStylesRB = [] # rollback styles

        self.lastSearch = ''    #for searchDialog
        
        super().__init__(parent)

        fontSize = utils.cfg('console-fontSize', 10)
        
        try: 
            font = QFont ('Consolas', fontSize)
        except:
            log('[W] :wQFont(Consolas)')
            font = QFont ()
            font.setPointSize(fontSize)
            
        self.setFont(font)
        # self.lineNumbers.updateFontMetrix()

        #self.setStyleSheet('{selection-background-color: #48F; selection-color: #fff;}')
        self.setStyleSheet('selection-background-color: #48F')

        self.setTabStopDistance(QFontMetricsF(font).width(' ') * 4)
        
        self.cursorPositionChanged.connect(self.cursorPositionChangedSignal) # why not just overload?
        self.selectionChanged.connect(self.consSelection)
        
        self.rehighlightSig.connect(self.rehighlight)

    def rehighlight(self):
        #need to force re-highlight manually because of #476

        cursor = self.textCursor()
        block = self.document().findBlockByLineNumber(cursor.blockNumber())
        
        log('rehighlight...', 5)
        self.SQLSyntax.rehighlightBlock(block)  # enforce highlighting 


    '''
    def insertFromMimeData(self, src):
        
            # for some reason ctrl+v does not trigger highliqter
            # so do it manually
        
        a = super().insertFromMimeData(src)
        print('insertFromMimeData(src)')
        
        cursor = self.textCursor()
        block = self.document().findBlockByLineNumber(cursor.blockNumber())
        
        self.SQLSyntax.rehighlightBlock(block)  # enforce highlighting 
        
        return a
        
    '''

    '''
    def _cl earHighlighting(self):
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
    '''
      
    #def newLayout(self, type, position, lo, af):
    def newLayout(self, position, lo, af):
        
        #for l in self.modifiedLayouts[type]:
        for l in self.modifiedLayouts:
            if l[0] == position:
                #this layout already in the list
                return
            
        #self.modifiedLayouts[type].append([position, lo, af])
        #log('add layout: %s' % str(lo), 5)
        self.modifiedLayouts.append([position, lo, af])
            
    @profiler
    def highlight(self):
        '''
            highlights word in document based on self.highlightedWords[]
        '''
    
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
                #self.newLayout('br', blkStCurrent, lo, af)
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
        
        #print('okay, search...', str)
        
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
        
    @profiler
    def consSelection(self):
        #512 
        if self.manualSelection:
            self.clearManualSelection()

        if cfg('noWordHighlighting'):
            return
    
        if self.lock:
            return
            
        cursor = self.textCursor()
        selected = cursor.selectedText()

        #if True or self.haveHighlighrs:
        if self.haveHighlighrs:
            # we ignore highlighted brackets here
            #log('consSelection clear highlighting', 5)
            self.clearHighlighting()

        #txtline = self.document().findBlockByLineNumber(cursor.blockNumber()) one of the longest annoing bugs, someday I will give it a name
        txtline = self.document().findBlockByNumber(cursor.blockNumber())
        line = txtline.text()
        
        if re.match('\w+$', selected):
            if re.search('\\b%s\\b' % selected, line):
                self.searchWord(selected)

        return
        
    def explainPlan(self):
    
        cursor = self.textCursor()
    
        if cursor.selection().isEmpty():
            self.log.emit('You need to select the statement manually first')
            return

        st = cursor.selection().toPlainText()
        
        st = st.strip().rstrip(';')
        
        self.explainSignal.emit(st)
    
    @profiler
    def formatSelection(self):
        cursor = self.textCursor()

        if cursor.selection().isEmpty():
            self.log.emit('Select the statement manually first')
            return
            
        txt = cursor.selection().toPlainText()
        
        trailingLN = False
        
        if txt[-1:] == '\n':
            trailingLN = True
        
        txt = format(txt, reindent=True, indent_width=4)
        
        if trailingLN:
           txt += '\n' 
           
        cursor.insertText(txt)
        
        
    def contextMenuEvent(self, event):
       
        cmenu = QMenu(self)
        
        menuExec = cmenu.addAction('Execute statement/selection\tF8')
        menuExecNP = cmenu.addAction('Execute without parsing\tAlt+F8')
        menuExecLR = cmenu.addAction('Execute but leave the results\tCtrl+F9')
        cmenu.addSeparator()
        menuOpenFile = cmenu.addAction('Open File in this console')
        menuSaveFile = cmenu.addAction('Save File\tCtrl+S')
        cmenu.addSeparator()
        menuDisconnect = cmenu.addAction('Disconnect from the DB')
        menuConnect = cmenu.addAction('(re)connecto to the DB')
        menuAbort = cmenu.addAction('Generate cancel session sql')
        menuClose = cmenu.addAction('Close console\tCtrl+W')

        cmenu.addSeparator()
        explainPlan = cmenu.addAction('Explain Plan\tCtrl+Shift+X')
        sqlFormat = cmenu.addAction('Format SQL\tCtrl+Shift+O')
            
        if cfg('dev'):
            cmenu.addSeparator()
            menuTest = cmenu.addAction('Test menu')
            createDummyTable = cmenu.addAction('Generate test result')
            createClearResults = cmenu.addAction('Clear results')
            generateCrash = cmenu.addAction('Crash now!')

        action = cmenu.exec_(self.mapToGlobal(event.pos()))

        if cfg('dev'):
            if action == createDummyTable:
                self._parent.closeResults()
                self._parent.dummyResultTable2(200 * 1000)

            if action == generateCrash:
                log('Im going to crash!!')
                log('Im going to crash: %i' % (1/0))
                
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
        elif action == menuAbort:
            self.abortSignal.emit()
        elif action == menuConnect:
            self.connectSignal.emit()
        elif action == menuOpenFile:
            self.openFileSignal.emit()
        elif action == menuSaveFile:
            self.saveFileSignal.emit()
        elif action == menuClose:
            self.closeSignal.emit()
        elif cfg('dev') and action == menuTest:
            cursor = self.textCursor()
            cursor.removeSelectedText()
            cursor.insertText('123')
            self.setTextCursor(cursor)
            
        if action == sqlFormat:
            self.formatSelection()
        
        if action == explainPlan:
            self.explainPlan()
            
    @profiler
    def findString(self, str = None):
    
        if str is None:
            if self.lastSearch  is None:
                return
                
            str = self.lastSearch 
        else:
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
        
    # the stuff moved to QPlainTextEditLN because I am stupid and lazy.
    
    '''
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
    '''
    
    '''
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
    '''
    
    def keyPressEvent (self, event):
    
        #print('console keypress')
        
        modifiers = QApplication.keyboardModifiers()

        if event.key() == Qt.Key_F8 or  event.key() == Qt.Key_F9:

            if modifiers & Qt.AltModifier:
                self.executionTriggered.emit('no parsing')
            elif modifiers & Qt.ControlModifier:
                self.executionTriggered.emit('leave results')
            else:
                self.executionTriggered.emit('normal')
            
            '''
            
            all this moved to QPlainTextEdit
            
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
            '''
        elif modifiers == Qt.ControlModifier and event.key() == Qt.Key_F:
                search = searchDialog.searchDialog(self.lastSearch)
                
                search.findSignal.connect(self.findString)
                
                search.exec_()
        elif event.key() == Qt.Key_F3:
            self.findString()
        elif event.key() == Qt.Key_O and (modifiers == Qt.ControlModifier | Qt.ShiftModifier):
            self.formatSelection()
        elif event.key() == Qt.Key_X and (modifiers == Qt.ControlModifier | Qt.ShiftModifier):
            self.explainPlan()
            
        elif modifiers == Qt.ControlModifier and event.key() == Qt.Key_Space:
            self.autocompleteSignal.emit()

        else:
            #have to clear each time in case of input right behind the braket
            #elif event.key() not in (Qt.Key_Shift, Qt.Key_Control):
            '''
            if self.haveHighlighrs:
                self.clearHighlighting('br')
            if self.bracketsHighlighted:
                self.clearHighlighting('br')
            '''
            if self.bracketsHighlighted:
                #log('keypress clear highlighting', 5)
                self.clearHighlighting()
                
            #print('console: super')
            super().keyPressEvent(event)
            
            #if modifiers == Qt.ControlModifier and event.key() == Qt.Key_V:
                #print('QSyntaxHighlighter::rehighlightBlock')
            '''
                cursor = self.textCursor()
                block = self.document().findBlockByLineNumber(cursor.blockNumber())
        
                self.SQLSyntax.rehighlightBlock(block)  # enforce highlighting 
            '''

    #def clearHighlighting(self, type):
    @profiler
    def clearHighlighting(self):
        #log('modifiedLayouts count: %i' % len(self.modifiedLayouts), 5)
        #return
        #log('clearHighlighting', 5)
        if self.bracketsHighlighted or self.haveHighlighrs and not self.lock:
            
            #for lol in self.modifiedLayouts[type]:
            
            #log('modifiedLayouts count: %i' % len(self.modifiedLayouts), 5)
            for lol in self.modifiedLayouts:
            
                lo = lol[1]
                af = lol[2]

                #log('mod: %s' % str(lo), 5)
                #log('lines: %s' % lo.lineCount(), 5)
                lo.setAdditionalFormats(af)
                #log('clear went ok', 5)
                
            #self.modifiedLayouts[type].clear()
            self.viewport().repaint()

        self.modifiedLayouts.clear()
            
        self.bracketsHighlighted = False # <<<< this is not true in case of #382
                                         # <<<< we came here just to clear words
                                         # somehow need to manage this explicitly
                                         
        self.haveHighlighrs = False

        '''
        if type == 'br':
            self.bracketsHighlighted = False
        elif type == 'br':
            self.haveHighlighrs = False
        '''

    @profiler
    def clearManualSelection(self):
        #print('clear manualSelectionPos...', self.manualSelectionPos)
        
        start = self.manualSelectionPos[0]
        stop = self.manualSelectionPos[1]
        
        cursor = QTextCursor(self.document())
        
        #print('clear manualSelectionPos... 1')
        for (block, lo, af) in self.manualStylesRB:
            #print(' '*10, block, block.blockNumber(), lo, af)
            if block.isValid():
                lo.setAdditionalFormats(af)
            else:
                log('[W] block highlighting anti-crash skip...', 4)
            #print(' '*10,'(clear)')
            
        #print('clear manualSelectionPos... 2')
            
        self.manualStylesRB.clear()
        
        #print('clear manualSelectionPos... 3')

        self.manualSelection = False
        self.manualSelectionPos = []
        
        #print('clear manualSelectionPos... 4')
        
        self.viewport().repaint()
        #print('clear manualSelectionPos... done')
        

    @profiler
    def cursorPositionChangedSignal(self):
        #log('cursorPositionChangedSignal', 5)
    
        t0 = time.time()
        
        #print('cursorPositionChangedSignal', self.lock)
    
        if self.manualSelection:
            self.clearManualSelection()
    
        if cfg('noBracketsHighlighting'):
            return
    
        self.checkBrackets()
        
        t1 = time.time()
        
        #log('cursorPositionChangedSignal: %s ms' % (str(round(t1-t0, 3))), 5)
        
    @profiler
    def highlightBrackets(self, block, pos1, pos2, mode):
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
            
            #self.newLayout('br', txtblk1.position(), lo1, af)
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
            
            #self.newLayout('br', txtblk2.position(), lo2, af2) zhere??
            self.newLayout(txtblk1.position(), lo1, af1)
            self.newLayout(txtblk2.position(), lo2, af2)
        
        self.viewport().repaint()
        
    @profiler
    def checkBrackets(self):
    
        if self.bracketsHighlighted:
            #log('checkBrackets clear', 5)
            self.clearHighlighting()
            #self.clearHighlighting('br')
            #self.clearHighlighting('w')
    
        cursor = self.textCursor()
        pos = cursor.position()

        text = self.toPlainText()

        textSize = len(text)
        
        def scanPairBracket(pos, shift):
        
            bracket = text[pos]
        
            depth = 0
        
            if bracket == ')':
                pair = '('
            elif bracket == '(':
                pair = ')'
            elif bracket == '[':
                pair = ']'
            elif bracket == ']':
                pair = '['
            else:
                return -1
            
            i = pos + shift
            
            if bracket in (')', ']'):
                # skan forward
                stop = 0
                step = -1
            else:
                stop = textSize-1
                step = 1
                
            
            while i != stop:
                i += step
                ch = text[i]
                
                if ch == bracket:
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
                pb = scanPairBracket(bPos, shift)
            else:
                bPos = pos
                shift = 0
                pb = scanPairBracket(bPos, shift)

            if pb >= 0:
                self.bracketsHighlighted = True
                self.highlightBrackets(self.document(), bPos, pb, True)
        
class logArea(QPlainTextEdit):

    tabSwitchSignal = pyqtSignal(int)

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
    def keyPressEvent (self, event):
        #log keypress
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.AltModifier and Qt.Key_0 < event.key() <= Qt.Key_9:
            self.tabSwitchSignal.emit(event.key() - Qt.Key_1)
        else:
            super().keyPressEvent(event)
              
        
class sqlConsole(QWidget):

    nameChanged = pyqtSignal(['QString'])
    statusMessage = pyqtSignal(['QString', bool])
    selfRaise = pyqtSignal(object)
    alertSignal = pyqtSignal()
    
    sqlBrowserSignal = pyqtSignal()
    
    tabSwitchSignal = pyqtSignal(int)
    fontUpdateSignal = pyqtSignal(['QString'])
    
    #gc.set_debug(gc.gc.DEBUG_LEAK)

    def __init__(self, window, config, tabname=None, dpid=None):
    
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
        self.dbi = None
        self.timer = None           # keep alive timer
        self.rows = []
        
        self.splitterSizes = None
        
        self.fileName = None
        self.unsavedChanges = False
        
        self.backup = None
    
        self.results = [] #list of resultsets
        self.resultTabs = None # tabs widget
        
        self.noBackup = False
        
        self.connection_id = None
        
        # self.runtimeTimer = None
        
        self.toolbar = None

        # self.psid = None # prepared statement_id for drop_statement -- moved to the resultset!
        
        self.timerAutorefresh = None
        # self.nextAutorefresh = None     # datetime of next planned autorefresh >> moved to ind.
        
        self.defaultTimer = [60]        # list used to trick static value for all tabs in this console.
                                        # wouldn't it be clearer to have this value as console attribue, ha?
                                        # plust refresh timer itself, insead of self.timerSet,  - also a result set attribue
                                        # should be rather on console (especially considering toolbar)
                                        
        self.timerSet = [False]
        
        self.lockRefreshTB = False      # lock the toolbar button due to change from resultset context menu
        
        self.abapCopyFlag = [False]     # to be shared with child results instances
        
        self.resultsLeft = False        # when True - warning will be displayed before closing results
        self.LOBs = False               # True if one of console results has LOBs. Reset with detach

        self.secondary = None           # Str describing the DP on secondary DP, used for warning
        self.prod = None                # True for production connections

        self.dpid = dpid

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
        
        #self.cons.selectionChanged.connect(self.selectionChangedS)
        
        self.cons.updateRequest.connect(self.updateRequestS)
        
        self.cons.connectSignal.connect(self.connectDB)
        self.cons.disconnectSignal.connect(self.disconnectDB)
        self.cons.abortSignal.connect(self.cancelSession)
        self.cons.autocompleteSignal.connect(self.autocompleteHint)
        
        self.cons.tabSwitchSignal.connect(self.tabSwitchSignal)
        
        self.logArea.tabSwitchSignal.connect(self.tabSwitchSignal)
        
        self.cons.explainSignal.connect(self.explainPlan)

        if config is None:
            self.consoleStatus()
            return
        
        try:
            # get (existing or create) db interface instance
            dbimpl = dbi(config['dbi'])         # this is a class name
            self.dbi = dbimpl.dbinterface       # and this is interface instance now
            
            self.sqlWorker.dbi = self.dbi       # again, instance

            log('starting console connection')
            self.conn = self.dbi.console_connection(config)
            self.config = config

            self.connection_id = self.dbi.get_connection_id(self.conn)
            #log('connection open, id: %s' % self.connection_id)
            '''
            moved to DBI implementation
            
            rows = self.dbi.execute_query(self.conn, "select connection_id from m_connections where own = 'TRUE'", [])
            
            if len(rows):
                self.connection_id = rows[0][0]
                
                log('connection open, id: %s' % self.connection_id)
            '''
            
        except dbException as e:
            log('[!] failed!')
            raise e
            return
            
        self.consoleStatus()

        # print(self.conn.session_id) it's not where clear how to get the connection_id
        # 

        if cfg('keepalive-cons'):
            keepalive = int(cfg('keepalive-cons'))
            self.enableKeepAlive(self, keepalive)

    '''
    def selectionChangedS(self):
        if self.cons.manualSelection:
            self.cons.clearManualSelection()
    '''
        
    def updateRequestS(self, rect):
        '''
            okay all this logic below is a workaround for #382
            
            somehow the brackets highlighting disappears by itself on any text change
            
            therefore we can just clear the list and set the flags (flags?) off
        '''
        
        if self.cons.lock:
            return
            
        if rect.width() > 11:
            # width == 10 means just cursor blinking with any (!) font size
            if self.cons.bracketsHighlighted:
                #log('updateRequestS FAKE clear highlighting', 5)
                #self.cons.clearHighlighting()

                self.cons.modifiedLayouts.clear()
                    
                self.cons.bracketsHighlighted = False
                self.cons.haveHighlighrs = False

        
    def textChangedS(self):
    
        if self.cons.lock:
            return
            
        if not cfg('noWordHighlighting'):
            if not self.cons.lock:
                if self.cons.haveHighlighrs:
                    #log('textChangedS, clear highlighting', 5)
                    self.cons.clearHighlighting()
        '''
        this does not work because textChanged is called on background change...
        this can be resolved by a lock, but...
        it is called after the change, so the issue persists
        
        if self.cons.manualSelection:

            self.cons.lock = True
            
            start = self.cons.manualSelectionPos[0]
            stop = self.cons.manualSelectionPos[1]
            
            cursor = QTextCursor(self.cons.document())
            cursor.joinPreviousEditBlock()

            format = cursor.charFormat()
            format.setBackground(QColor('white'))
        
            cursor.setPosition(start,QTextCursor.MoveAnchor)
            cursor.setPosition(stop,QTextCursor.KeepAnchor)
            
            cursor.setCharFormat(format)
            
            cursor.endEditBlock() 
            self.cons.manualSelection = False
            
            self.cons.lock = False
        '''
        
        '''
        # 2021-05-29
        print('textChangedS')
        if self.cons.bracketsHighlighted:
            log('textChangedS clear highlighting', 5)
            self.cons.clearHighlighting()
        '''

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
    @profiler
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
            bkpFile = os.path.abspath(bkpFile)
            
            self.backup = bkpFile
            
            bkpPath = os.path.join(path, 'bkp')
            
            if not os.path.isdir(bkpPath):
                os.mkdir(bkpPath)
            
        filename = self.backup
        
        fnsecure = utils.securePath(filename)
    
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
    
        #print('sql tab keypress')
   
        modifiers = QApplication.keyboardModifiers()

        if event.key() == Qt.Key_F12:
        
            backTo = self.spliter.sizes()

            if self.splitterSizes is None:
                #self.splitterSizes = [4000, 200, 100]
                self.splitterSizes = [200, 800, 100]
                
            self.spliter.setSizes(self.splitterSizes)
            
            self.splitterSizes = backTo

        #elif event.key() == Qt.Key_F11:
            #self.manualSelect(4, 8)
            
                
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

        fnsecure = utils.securePath(filename, True)
        bkpsecure = utils.securePath(backup)
        
        log('openFile: %s, %s' % (fnsecure, bkpsecure))

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
            log ('Error: ' + str(e), 1, True)
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
    
    def close(self, cancelPossible=True, abandoneExecution=False):
    
        #log(f'close call: {self.tabname=}, {cancelPossible=}')
        
        if self.unsavedChanges and cancelPossible:
            answer = utils.yesNoDialog('Unsaved changes', 'There are unsaved changes in "%s" tab, do yo want to save?' % self.tabname, cancelPossible, parent=self)
            
            if answer is None: #cancel button
                return False

            if answer == False:
                try:
                    #log('delete backup: %s' % (str(self.tabname+'.sqbkp')))
                    #os.remove(self.tabname+'.sqbkp')
                    log('delete backup: %s' % (utils.securePath(self.backup)))
                    os.remove(self.backup)
                except:
                    log('delete backup 2 faileld, passing')
                    # whatever...
                    pass
            
            if answer == True:
                self.saveFile()
                
        self.closeResults(abandoneExecution)
        
        try: 
            self.stopKeepAlive()

            if self.sqlRunning and abandoneExecution:
                log('Something is running in tab \'%s\', abandoning without connection close()...' % self.tabname.rstrip(' *'), 3)
            
            if self.conn is not None and abandoneExecution == False:
                log('close the connection...', 5)
                self.indicator.status = 'sync'
                self.indicator.repaint()
                self.dbi.close_connection(self.conn)
                self.conn = None
                self.dbi = None
                
        except dbException as e:
            log('close() db exception: '+ str(e))
            super().close()
            self.dbi = None
            return True
            
        except Exception as e:
            log('close() exception: '+ str(e))
            super().close()
            self.dbi = None
            return True
        
        if self.indicator.runtimeTimer is not None:
            log('runtimeTimer --> off', 5)
            self.indicator.runtimeTimer.stop()
            self.indicator.runtimeTimer = None
        super().close()
                
        return True
            
    def explainPlan(self, st):
        sqls = []
        
        st_name = 'rf'
        
        sqls.append("explain plan set statement_name = '%s' for %s" % (st_name, st))
        sqls.append("select * from explain_plan_table where statement_name = '%s'" % (st_name))
        sqls.append("delete from sys.explain_plan_table where statement_name = '%s'" % (st_name))
            
        self.stQueue = sqls.copy()
        self.launchStatementQueue()
        
    def autocompleteHint(self):
            
            if self.conn is None:
                self.log('The console is not connected to the DB', True)
                return
                
            if self.sqlRunning:
                self.log('Autocomplete is blocked while the sql is still running...')
                return

            if not hasattr(self.dbi, 'getAutoComplete'):
                self.log('Autocomplete is not implemented for this DBI.')
                return

            cursor = self.cons.textCursor()
            pos = cursor.position()
            linePos = cursor.positionInBlock();
            lineFrom = self.cons.document().findBlock(pos)
            
            line = lineFrom.text()

            j = i = 0
            # check for the space
            for i in range(linePos-1, 0, -1):
                if line[i] == ' ':
                    break
            else:
                #start of the line reached
                i = -1
                
            # check for the dot
            for j in range(linePos-1, i+1, -1):
                if line[j] == '.':
                    break
            else:
                j = -1
                
            if j > i:
                schema = line[i+1:j]
                
                if schema.islower() and schema[0] != '"' and schema[-1] != '"':
                    schema = schema.upper()
                    
                term = line[j+1:linePos].lower() + '%'
                
            else:
                schema = 'PUBLIC'
                term = line[i+1:linePos].lower() + '%'
                    
            if linePos - i <= 2:
                #string is too short for autocomplete search
                return
                 
            if j == -1:
                stPos = lineFrom.position() + i + 1
            else:
                stPos = lineFrom.position() + j + 1

            endPos = lineFrom.position() + linePos

            log('get autocomplete input (%s)... ' % (term), 3)
            
            if j != -1:
                self.statusMessage.emit('Autocomplete request: %s.%s...' % (schema, term), False)
            else:
                self.statusMessage.emit('Autocomplete request: %s...' % (term), False)
            
            self.indicator.status = 'sync'
            self.indicator.repaint()
            
            t0 = time.time()

            try:
                sql, params = self.dbi.getAutoComplete(schema, term)
                rows = self.dbi.execute_query(self.conn, sql, params)

            except dbException as e:
                err = str(e)
                
                self.statusMessage.emit('db error: %s' % err, False)

                self.indicator.status = 'error'
                self.indicator.repaint()
                return

            t1 = time.time()

            self.indicator.status = 'idle'
            self.indicator.repaint()
            
            n = len(rows)
            
            log('ok, %i rows: %s ms' % (n, str(round(t1-t0, 3))), 3, True)
            
            if n == 0:
                self.statusMessage.emit('No suggestions found', False)
                return
                
            self.statusMessage.emit('', False)

            if n > 1:
                lines = []
                for r in rows:
                    lines.append('%s (%s)' % (r[0], r[1]))
                    
                line, ok = autocompleteDialog.getLine(self, lines)
            else:
                #single suggestion, let's fake "OK":
                ok = True
                line = rows[0][0]
                
            line = line.split(' (')[0]

            if ok:
                cursor.clearSelection()
                cursor.setPosition(stPos, QTextCursor.MoveAnchor)
                cursor.setPosition(endPos, QTextCursor.KeepAnchor)
            
                cursor.insertText(normalize_header(line))
                
    def cancelSession(self):
        if self.connection_id:
            self.log(f"\nNOTE: the SQL needs to be executed manually from the other SQL console:\nalter system cancel session '{str(self.connection_id)}'")
        else:
            self.log('\nConsole seems to be disconnected')
        
    def disconnectDB(self):

        try: 
        
            self.stopResults()
        
            if self.conn is not None:
                self.dbi.close_connection(self.conn)
                self.dbi = None
                
                self.stopKeepAlive()
                
                self.conn = None
                self.connection_id = None

                self.prod = None
                self.secondary = None

                self.indicator.status = 'disconnected'
                self.indicator.repaint()
                self.log('\nDisconnected')
                
        except dbException as e:
            log('close() db exception: '+ str(e))
            self.log('close() db exception: '+ str(e), True)
            
            self.stopKeepAlive()
            self.conn = None # ?
            self.connection_id = None
            self.dbi = None
            return
        except Exception as e:
            log('close() exception: '+ str(e))
            self.log('close() exception: '+ str(e), True)
            
            self.stopKeepAlive()
            self.conn = None # ?
            self.connection_id = None
            self.dbi = None
            return
        
    def connectDB(self):
    
        if self.config is None:
            self.log('No connection, connect RybaFish to the DB first.')
            return
    
        try: 
            log('connectDB, indicator sync?', 4)
            self.indicator.status = 'sync'
            self.indicator.repaint()

            if self.conn is not None:
                self.dbi.close_connection(self.conn)
                
                self.stopKeepAlive()
                self.conn = None
                self.connection_id = None
                self.log('\nDisconnected')

            self.sqlRunning = False
            self.stQueue.clear()

            if self.dbi == None:
                dbimpl = dbi(self.config['dbi'])
                self.dbi = dbimpl.dbinterface
                
                self.sqlWorker.dbi = self.dbi
                
            self.conn = self.dbi.console_connection(self.config)

            self.consoleStatus()
            '''
            rows = self.dbi.execute_query(self.conn, "select connection_id  from m_connections where own = 'TRUE'", [])
            
            if len(rows):
                self.connection_id = rows[0][0]
                
                log('connection open, id: %s' % self.connection_id)
            '''
            self.connection_id = self.dbi.get_connection_id(self.conn)

            if cfg('keepalive-cons') and self.timer is None:
                keepalive = int(cfg('keepalive-cons'))
                self.enableKeepAlive(self, keepalive)
            
        except dbException as e:
            log('close() db exception: '+ str(e))
            self.log('close() db exception: '+ str(e), True)
        except Exception as e:
            log('close() exception: '+ str(e))
            self.log('close() exception: '+ str(e), True)


        log('connectDB, indicator idle?', 4)
        self.indicator.status = 'idle'
        self.indicator.repaint()
        
        self.log('Connected.')

    
    def reconnect(self):
            
        if self.dbi is None:
            log('Reconnection canceled as there is no DBI instance', 3)
            return
            
        try:
        
            conn = self.dbi.console_connection(self.config)

            '''
            rows = self.dbi.execute_query(conn, "select connection_id  from m_connections where own = 'TRUE'", [])
            
            if len(rows):
                self.connection_id = rows[0][0]
                
                log('connection open, id: %s' % self.connection_id)
            '''
            self.connection_id = self.dbi.get_connection_id(conn)

        except Exception as e:
            raise e
        
        if conn is None:
            self.log('[i] Failed to reconnect, dont know what to do next')
            raise Exception('Failed to reconnect, dont know what to do next...')
        else:
            self.log('re-connected')
            self.conn = conn

    def autorefreshRun(self):
        log('autorefresh...', 4)
        
        self.timerAutorefresh.stop()

        self.refresh(0)
        
        interval = self.timerAutorefresh.interval()/1000
        self.indicator.nextAutorefresh = datetime.datetime.now() + datetime.timedelta(seconds=interval)
        # self.indicator.nextAutorefresh = self.nextAutorefresh
        self.timerAutorefresh.start()
    
    def setupAutorefresh(self, interval, suppressLog = False):
        if interval == 0:
            log('Stopping the autorefresh: %s' % self.tabname.rstrip(' *'))
            
            if suppressLog == False:
                self.log('--> Stopping the autorefresh')

            if self.indicator.status in ('autorefresh', 'alert'):
                self.indicator.status = 'idle'
                self.indicator.bkpStatus = 'idle'
                self.indicator.repaint()
            
            if self.timerAutorefresh is not None:
                self.timerAutorefresh.stop()
                self.timerAutorefresh = None
                
            self.lockRefreshTB = True
            self.tbRefresh.setChecked(False)
            self.lockRefreshTB = False
            
            self.timerSet[0] = False
            
            return
         
        
        if self.resultTabs.count() == 0:
            self.log('Execute some SQL first, autorefresh related to result set.')
            return
            
        if self.resultTabs.count() != 1:
            self.log('Autorefresh only possible for single resultset output.', True)
            return
        
        self.lockRefreshTB = True
        self.tbRefresh.setChecked(True)
        self.lockRefreshTB = False
        
        self.indicator.status = 'autorefresh'
        self.indicator.repaint()

        self.log('\n--> Scheduling autorefresh, logging will be supressed. Autorefresh will stop on manual query execution or context menu -> stop autorefresh')
        log('Scheduling autorefresh %i (%s)' % (interval, self.tabname.rstrip(' *')))
            
        if self.timerAutorefresh is None:
            self.timerAutorefresh = QTimer(self)
            self.timerAutorefresh.timeout.connect(self.autorefreshRun)
            self.indicator.nextAutorefresh = datetime.datetime.now() + datetime.timedelta(seconds=interval)
            # self.indicator.nextAutorefresh = self.nextAutorefresh
            self.timerAutorefresh.start(1000 * interval)
        else:
            log('[W] autorefresh timer is already running, ignoring the new one...', 2)
            self.log('Autorefresh is already running? Ignoring the new one...', True)
            
        self.timerSet[0] = True
            
    def resultDetached(self):
        if self.LOBs:
            self.LOBs = False
        # self.indicator.status = 'idle'
        # this should fix #787

        if self.timerAutorefresh:
            self.indicator.status = 'autorefresh'
        else:
            self.indicator.status = 'idle'

        self.indicator.repaint()
        
    def alertProcessing(self, fileName, volume=-1, manual=False):
    
        if fileName == '' or fileName is None:
            fileName = cfg('alertSound', 'default')
        else:
            pass
            
        #print('filename:', fileName)
            
        if fileName.find('.') == -1:
            fileName += '.wav'
            
        #print('filename:', fileName)
            
        if '/' in fileName or '\\' in fileName:
            #must be a path to some file...
            pass
        else:
            #try open normal file first
            #fileName = 'snd\\' + fileName
            fileNamePath = os.path.join('snd', fileName)
            
            if os.path.isfile(fileNamePath):
                log(f'seems there is a file in the rybafish snd folder: {fileNamePath}', 4)
            else:
                #okay, take it from the build then...
                fileNamePath = resourcePath('snd', fileName)
                
            fileName = fileNamePath
                
        #print('filename:', fileName)

        #log('Sound file name: %s' % fileName, 4)
        
        if not os.path.isfile(fileName):
            log(f'warning: sound file does not exist: {fileName} will use default.wav', 2)
            fileName = os.path.join('snd', 'default.wav')
            
            if not os.path.isfile(fileName):
                fileName = resourcePath('snd', 'default.wav')
    
        if self.timerAutorefresh and not manual:
            log('console [%s], alert...' % self.tabname.rstrip(' *'), 3)
            ts = datetime.datetime.now().strftime('%H:%M:%S') + ' '
            self.logArea.appendHtml(ts + '<font color = "#c6c">Alert triggered</font>.');
            
            
        if volume < 0:
            volume = cfg('alertVolume', 80)
            
        try:
            volume = int(volume)
        except ValueError:
            volume = 80
            
        volume /= 100
        
        if not manual:
            self.indicator.status = 'alert'

        log(f'sound file: {fileName}', 5)
        
        self.sound = QSoundEffect()
        soundFile = QUrl.fromLocalFile(fileName)
        self.sound.setSource(soundFile)
        self.sound.setVolume(volume)
            
        self.sound.play()
        
        if cfg('alertAutoPopup', True):
            if not self.isActiveWindow():
                self.selfRaise.emit(self)
            
            self.alertSignal.emit()
    
    def newResult(self, conn, st):
        
        result = QResultSet(conn)
        result.dbi = self.dbi
        
        result.statement = st
        
        result.defaultTimer = self.defaultTimer     #cross-link the lists from sql console to result
        result.timerSet = self.timerSet
        
        result.abapCopyFlag = self.abapCopyFlag     # same for ABAP-copy
        
        result._connection = conn
        
        result.log = self.log
        
        result.insertText.connect(self.cons.insertTextS)
        result.executeSQL.connect(self.surprizeSQL)
        result.alertSignal.connect(self.alertProcessing)
        result.detachSignal.connect(self.resultDetached)
        result.triggerAutorefresh.connect(self.setupAutorefresh)
        result.fontUpdateSignal.connect(self.fontResultUpdated)
        result.closeRequestSignal.connect(self.close)
        
        if len(self.results) > 0:
            rName = 'Results ' + str(len(self.results)+1)
        else:
            rName = 'Results'
        
        self.results.append(result)
        self.resultTabs.addTab(result, rName)
        
        #self.resultTabs.setCurrentIndex(len(self.results) - 1)
        self.resultTabs.setCurrentIndex(self.resultTabs.count() - 1)
        
        return result
        
    def stopResults(self):
    
        if self.results:
            log('Stopping all the results, %s...' % (self.tabname.rstrip(' *')), 4)
        
        for result in self.results:

            # stop autorefresh if any
            if self.timerAutorefresh is not None:
                log('Stopping autorefresh as it was enabled')
                result.log('--> Stopping the autorefresh...', True)
                self.timerAutorefresh.stop()
                self.timerAutorefresh = None
                
                self.tbRefresh.setChecked(False)

            if result.LOBs and not result.detached:
                if result.detachTimer is not None:
                    log('Stopping the detach timer as we are disconnecting...')
                    result.detachTimer.stop()
                    result.detachTimer = None
                    
                result.detach()

            if self.conn is not None:
                try:
                    self.indicator.status = 'sync'
                    self.indicator.repaint()
                    self.dbi.drop_statement(self.conn, result.psid)
                    self.indicator.status = 'idle'
                    self.indicator.repaint()
                except Exception as e:
                    log('[E] exeption during console close/drop statement: %s' % str(e), 2)
                    self.indicator.status = 'error'
                    self.indicator.repaint()
    
    def closeResults(self, abandon=False):
        '''
            closes all results tabs, detaches resultsets if any LOBs
        '''
        
        #log(f'closeResults() {self.tabname.rstrip(" *")}', 5)
        
        if abandon == True:
            cname = self.tabname.rstrip(' *')
            log(f'Ignore closing the results due to abandon=True ({cname})')
        else:
            self.stopResults()
        
        for i in range(len(self.results) - 1, -1, -1):
            
            self.resultTabs.removeTab(i)

            result = self.results[i]
            
            #log(f'[w] Result rows reference count: {sys.getrefcount(result.rows)}', 4)
            #log(f'[w] Result reference count: {sys.getrefcount(result)}', 4)
            
            #model = result.model()
            #model.removeRows(0, 10000)

            result.clear()

            del(result.cols)
            del(result.rows)
            #result.cols.clear()
            #result.rows.clear()
            
            #same code in refresh()
            
            #result.destroy()
            #result.deleteLater()
            
            del(result)
            del self.results[i]
            
        self.results.clear()
            
    def enableKeepAlive(self, window, keepalive):
    
        if not self.dbi.options.get('keepalive'):
            log('Keep-alives not supported by this DBI')
            return
    
        log('Setting up console keep-alive requests: %i seconds' % (keepalive))
        self.timerkeepalive = keepalive
        self.timer = QTimer(window)
        self.timer.timeout.connect(self.keepAlive)
        self.timer.start(1000 * keepalive)
        
    def stopKeepAlive(self):
    
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
            
            cname = self.tabname.rstrip(' *')
            log('keep-alives stopped (%s)' % cname)
    
    def renewKeepAlive(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer.start(1000 * self.timerkeepalive)

    def keepAlive(self):
    
        if self.conn is None:
            return

        if self.dbi is None:
            return
            
        if self.sqlRunning:
            log('SQL still running, skip keep-alive') # #362
            self.timer.stop()
            self.timer.start(1000 * self.timerkeepalive)
            return

        try:
            cname = self.tabname.rstrip(' *')
            log('console keep-alive (%s)... ' % (cname), 3, False, True)
            
            log('keepAlive, indicator sync', 4)
            self.indicator.status = 'sync'
            self.indicator.repaint()
            
            t0 = time.time()
            self.dbi.execute_query(self.conn, 'select * from dummy', [])
            t1 = time.time()

            #self.indicator.status = 'idle'
            
            if self.timerAutorefresh:
                self.indicator.status = 'autorefresh'
            else:
                self.indicator.status = 'idle'
            
            self.indicator.repaint()
            
            log('ok: %s ms' % (str(round(t1-t0, 3))), 3, True)
        except dbException as e:
            log('Trigger autoreconnect...')
            self.log('Connection lost, trigger autoreconnect...')
            try:
                conn = self.dbi.console_connection(self.config)
                if conn is not None:
                    self.conn = conn
                    log('Connection restored automatically')
                    self.indicator.status = 'idle'

                    '''
                    rows = self.dbi.execute_query(self.conn, "select connection_id  from m_connections where own = 'TRUE'", [])
                    
                    if len(rows):
                        self.connection_id = rows[0][0]
                        
                        log('connection open, id: %s' % self.connection_id)
                    '''
                    self.connection_id = self.dbi.get_connection_id(self.conn)
                        
                else:
                    log('Some connection issue, give up')
                    self.log('Some connection issue, give up', 1, True)
                    self.stopKeepAlive()
                    self.conn = None
                    self.connection_id = None
            except:
                log('Connection lost, give up')

                self.indicator.status = 'disconnected'
                self.indicator.repaint()
                self.log('Connection lost, give up', True)
                # print disable the timer?
                self.stopKeepAlive()
                self.conn = None
                self.connection_id = None
                
                if self.timerAutorefresh is not None:
                    self.log('--> Stopping the autorefresh on keep-alive fail...', True)
                    self.setupAutorefresh(0, suppressLog=True)
                
                    if cfg('alertDisconnected'):
                        self.alertProcessing(cfg('alertDisconnected'), manual=True)
                
        except Exception as e:
            log('[!] unexpected exception, disable the connection')
            log('[!] %s' % str(e))
            self.log('[!] unexpected exception, disable the connection', True)

            self.stopKeepAlive()

            self.conn = None
            self.connection_id = None
            self.indicator.status = 'disconnected'
            self.indicator.repaint()
            
                        
    def log(self, text, error=False, pre=False):
        if error:
            if pre:
                text = f'<pre>{text}</pre>'
            else:
                text = utils.escapeHtml(text)
                text = text.replace('\n', '\n<br />')
                
            self.logArea.appendHtml(f'<font color = "red">{text}</font>');
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
            
        result.alerted = False

        self.executeStatement(result.statement, result, True)
        
    def executeSelection(self, mode):
    
        if self.config is None:
            self.log('No connection, connect RybaFish to the DB first.')
            return
            
        if self.resultsLeft and mode != 'leave results' and len(self.results) >= 1:
            answer = utils.yesNoDialog('Warning',
                'You were saving some results, are you sure you want to abandon those now?', 
                parent=self
            )
            
            if answer == False:
                self.log('Execution cancelled')
                return
                
            self.resultsLeft = False
            
        if mode == 'leave results':
            self.resultsLeft = True
            
        if self.conn is None:
            self.log('The console is disconnected...')
            
            #answer = utils.yesNoDialog('Connect to db', 'The console is not connected to the DB. Connect as "%s@%s:%s"?' % (self.config['user'], self.config['host'], str(self.config['port'])))
            answer = utils.yesNoDialog('Connect to db', 'The console is not connected to the DB. Connect now?', parent = self)
            
            if not answer:
                return 
                
            self.connectDB()
    
        if self.timerAutorefresh:
            self.setupAutorefresh(0)
            
        
        # reset block numbering, #672
        self.cons.lineNumbers.fromLine = None
        
        if mode == 'normal':
            self.executeSelectionParse()
        elif mode == 'no parsing':
            self.executeSelectionNP(False)
        elif mode == 'leave results':
            self.executeSelectionNP(True)
            
    def surprizeSQL(self, key, value):
        
        sqls = []
        
        for st in customSQLs.sqls[key]:
            sqls.append(st.replace('$value', value))
            
        if len(sqls) == 0:
            self.log('No sql defined', 2)
        
        if len(sqls) == 1:
            self.executeSelectionNP(True, sqls[0])
        else:
            self.stQueue = sqls.copy()
            self.launchStatementQueue()
        
    def executeSelectionNP(self, leaveResults, sql = None):
    
        cursor = self.cons.textCursor()
    
        if cursor.selection().isEmpty() and sql is None:
            self.log('You need to select statement manually for this option')
            return

        if leaveResults == False:
            self.closeResults()

        if sql == None:
            statement = cursor.selection().toPlainText()
        else:
            statement = sql
        
        result = self.newResult(self.conn, statement)
        self.executeStatement(statement, result)
        
    def manualSelect(self, start, stop, color):
        
        #print('manualSelect %i - %i (%s)' % (start, stop, color))
        
        updateMode = False
        
        if self.cons.manualSelection:
            # make sure we add additional formattin INSIDE existing one
            
            updateMode = True
            
            if start < self.cons.manualSelectionPos[0] or stop > self.cons.manualSelectionPos[1]:
                log('[W] Attemt to change formatting (%i:%i) outside already existing one (%i:%i)!' % \
                    (start, stop, self.cons.manualSelectionPos[0], self.cons.manualSelectionPos[1]), 2)
            
                return
            

        '''
        # modern (incorrect) style from here:

        cursor = QTextCursor(self.cons.document())

        cursor.joinPreviousEditBlock()

        format = cursor.charFormat()
        format.setBackground(QColor('#ADF'))

        cursor.setPosition(start,QTextCursor.MoveAnchor)
        cursor.setPosition(stop,QTextCursor.KeepAnchor)
        
        cursor.setCharFormat(format)
        
        cursor.endEditBlock() 
        
        #to here
        '''
        
       # old (good) style from here:
        
        '''
        not sure why it was so complex, 
        simplified during #478
        
        and reverted because issues with removing the highlighted background ...
        
        low level approach is better as it does not go into the undo/redo history, #482, #485
        but in this case also the exception highlighting must be low-level
        '''
        
        
        charFmt = QTextCharFormat()
        charFmt.setBackground(QColor(color))

        block = tbStart = self.cons.document().findBlock(start)
        tbEnd = self.cons.document().findBlock(stop)
        
        fromTB = block.blockNumber()
        toTB = tbEnd.blockNumber()
        
        #print('from tb, to:', fromTB, toTB)
        
        curTB = fromTB

        while curTB <= toTB and block.isValid():
        
            #print('block, pos:', curTB, block.position())
            
            if block == tbStart:
                delta = start - block.position()
            else:
                delta = 0

            if block == tbEnd:
                lenght = stop - block.position() - delta
            else:
                lenght = block.length()
            
            lo = block.layout()
            
            r = lo.FormatRange()
            
            r.start = delta
            r.length = lenght
            
            r.format = charFmt
            
            af = lo.additionalFormats()
            
            if not updateMode:
                self.cons.manualStylesRB.append((block, lo, af))

            lo.setAdditionalFormats(af + [r])
            
            block = block.next()
            curTB = block.blockNumber()

        #cursor.endEditBlock()

        if self.cons.manualSelection == False:
            #only enable it if not set yet
            #we also never narrow down the manualSelectionPos start/stop (it is checked in procedure start)
            self.cons.manualSelection = True
            self.cons.manualSelectionPos  = [start, stop]

        #print('manualSelectionPos[] = ', self.cons.manualSelectionPos)
        
        #print('manualSelectionPos', self.cons.manualSelectionPos)
            
        self.cons.viewport().repaint()
            
    @profiler
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
            #print('selectSingle', start, stop)
            
            self.manualSelect(start, stop, '#adf')
            
            #cursor = QTextCursor(self.cons.document())

            #cursor.setPosition(start,QTextCursor.MoveAnchor)
            #cursor.setPosition(stop,QTextCursor.KeepAnchor)
            
            #self.cons.setTextCursor(cursor)
        
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
                
        #print('ran from: ', cursorPos)
        
        str = ''
        
        i = 0
        start = stop = 0
        
        leadingComment = False
        insideString = False
        insideProc = False
        
        # main per character loop:

        # print('from to: ', scanFrom, scanTo)
        
        # startDelta = 0
        # clearDelta = False
        
        ### print('from, to', scanFrom, scanTo)
        
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
                    ### print("str = '' #1")
                    str = ''
                    
                    #if stop < start: # this is to resolve #486
                    if stop < start or (start == 0 and stop == 0): # this is to resolve # 486, 2 
                        stop = i
                    # clearDelta = True
                    continue
                else:
                    if isItEnd(str[-10:]):
                        insideProc = False
                        ### print("str = '' #2")
                        str = ''
                        stop = i
                        # clearDelta = True
                        continue
            
            if str == '':
                #happens when semicolon detected.
                # print('str = \'\'', 'startDelta: ', startDelta)
                if c in (' ', '\n', '\t') and not leadingComment:
                    # warning: insideString logic skipped here (as it is defined below this line
                    # skip leading whitespaces
                    # print(start, stop, cursorPos, i)
                    # startDelta += 1
                    continue
                elif not leadingComment and c == '-' and i < scanTo and txt[i] == '-':
                    leadingComment = True
                elif leadingComment:
                    ### print(c, i, start, stop)
                    if c == '\n':
                        leadingComment = False
                    else:
                        continue
                else:
                    #if F9 and (start <= cursorPos < stop):
                    #reeeeeallly not sure!
                    if F9 and (start <= cursorPos <= stop) and (start < stop):
                        #print('start <= cursorPos <= stop:', start, cursorPos, stop)
                        #print('warning! selectSingle used to be here, but removed 05.02.2021')
                        #selectSingle(start, stop)
                        ### print('stop detected')
                        break
                    else:
                        if not F9:
                            statementDetected(start, stop)
                        
                    start = i
                    str = str + c
                    ### print(i, 'sTr:', str, start, stop)
            else:
                str = str + c
                ### print(i, 'str:', str, start, stop)

            if not insideString and c == '\'':
                insideString = True
                continue
                
            if insideString and c == '\'':
                insideString = False
                continue
                
            if not insideProc and isItCreate(str[:64]):
                insideProc = True
                
        ### print('[just stop]')

        
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
        disconnectAlert = None
        
        tname = self.tabname.rstrip(' *')
        
        log(f'Connection Lost ({tname})...')

        if self.timerAutorefresh is not None and cfg('alertDisconnected'):      # Need to do this before stopResults as it resets timerAutorefresh
            log('disconnectAlert = True', 5)
            disconnectAlert = True
        else:
            log(f'disconnectAlert = None, because timer: {self.timerAutorefresh}, config alertDisconnected={cfg("alertDisconnected")}', 5)
        
        self.stopResults()
        
        
        msgBox = QMessageBox(self)
        msgBox.setWindowTitle(f'Console connection lost ({tname})')
        msgBox.setText('Connection failed, reconnect?')
        msgBox.setStandardButtons(QMessageBox.Yes| QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        iconPath = resourcePath('ico', 'favicon.png')
        msgBox.setWindowIcon(QIcon(iconPath))
        msgBox.setIcon(QMessageBox.Warning)

        if disconnectAlert:
            log('play the disconnect sound...', 4)
            self.alertProcessing(cfg('alertDisconnected'), manual=True)
            
        reply = None
        
        while reply != QMessageBox.No and self.conn is None:
            log('connectionLost, indicator sync')
            self.indicator.status = 'sync'
            self.indicator.repaint()
            
            reply = msgBox.exec_()
            if reply == QMessageBox.Yes:
                try:
                    self.log('Reconnecting to %s:%s...' % (self.config['host'], str(self.config['port'])))
                    self.reconnect()
                    #self.log('Connection restored <<')
                    self.logArea.appendHtml('Connection restored. <font color = "blue">You need to restart SQL manually</font>.');
                    
                    self.indicator.status = 'idle'
                    self.indicator.repaint()
                    
                    if cfg('keepalive-cons') and self.timer is None:
                        keepalive = int(cfg('keepalive-cons'))
                        self.enableKeepAlive(self, keepalive)
                    else:
                        self.renewKeepAlive() 
                        
                except Exception as e:
                    self.indicator.status = 'disconnected'
                    self.indicator.repaint()
                    
                    log('Reconnect failed: %s' % e)
                    self.log('Reconnect failed: %s' % str(e))

        if reply == QMessageBox.Yes:
            return True
        else:
            self.indicator.status = 'disconnected'
            return False
            
    def sqlFinished(self):
        '''
            post-process the sql results
            also handle exceptions
        '''
        #print('2 --> sql finished')

        log(f'[thread] finished, parent: {int(QThread.currentThreadId())}', 5)
        self.thread.quit()
        self.sqlRunning = False
        
        self.indicator.status = 'render'
        self.indicator.repaint()
        
        log('(%s) psid to save --> %s' % (self.tabname.rstrip(' *'), utils.hextostr(self.sqlWorker.psid)), 4)
        
        if self.dbi is None:
            log('dbi is None during sqlFinished. Likely due to close() call executed before, aborting processing', 2)
            return
        
        if self.wrkException is not None:
            pre = self.wrkException[:16] == 'Thread exception'
            self.log(self.wrkException, True, pre)
            
            #self.thread.quit()
            #self.sqlRunning = False

            if self.conn is not None and self.dbi is not None:
                self.indicator.status = 'error'
                
                if cfg('blockLineNumbers', True) and self.cons.manualSelection:
                    pos = self.cons.manualSelectionPos
                    doc = self.cons.document()
                    
                    #print('selection: ', pos)
                    startBlk = doc.findBlock(pos[0])
                    stopBlk = doc.findBlock(pos[1])
                    
                    if startBlk and stopBlk:
                        fromLine = startBlk.blockNumber() + 1
                        toLine = stopBlk.blockNumber() + 1
                    
                        #print('selection lines:', fromLine, toLine)
                        
                        #self.cons.lineNumbers.fromLine = fromLine   #674
                        #self.cons.lineNumbers.toLine = toLine
                        
                        #self.cons.lineNumbers.repaint()
                        
                        # exception text example: sql syntax error: incorrect syntax near "...": line 2 col 4 (at pos 13)
                        # at pos NNN - absolute number
                        
                        linePos = self.wrkException.find(': line ')
                        posPos = self.wrkException.find(' pos ')
                        
                        print(linePos, posPos)
                        
                        if linePos > 0 or posPos > 0:

                            self.cons.lineNumbers.fromLine = fromLine   #674 moved inside if
                            self.cons.lineNumbers.toLine = toLine
                            
                            self.cons.lineNumbers.repaint()
                            
                            linePos += 7
                            posPos += 5
                            
                            linePosEnd = self.wrkException.find(' ', linePos)
                            posPosEnd = self.wrkException.find(')', posPos)
                            
                            errLine = None
                            errPos = None
                            
                            if linePosEnd > 0:
                                errLine = self.wrkException[linePos:linePosEnd]
                                
                                try:
                                    errLine = int(errLine)
                                except ValueError:
                                    log('[w] ValueError exception: [%s]' % (errLine))
                                    errLine = None
                                    
                            if linePosEnd > 0:
                                errPos = self.wrkException[posPos:posPosEnd]
                                try:
                                    errPos = int(errPos)
                                except ValueError:
                                    log('[w] ValueError exception: [%s]' % (errPos))
                                    errPos = None
                                    

                            if errLine or errPos:
                            
                                cursor = QTextCursor(doc)
                                #cursor.joinPreviousEditBlock()

                                if errLine and toLine > fromLine:
                                    doc = self.cons.document()
                                    
                                    blk = doc.findBlockByNumber(fromLine - 1 + errLine - 1)
                                    
                                    start = blk.position()
                                    stop = start + blk.length() - 1
                                    
                                    if stop > pos[1]:
                                        stop = pos[1]
                                    
                                    #print('error highlight:', start, stop)

                                    '''
                                    format = cursor.charFormat()
                                    format.setBackground(QColor('#FCC'))
                                
                                    cursor.setPosition(start,QTextCursor.MoveAnchor)
                                    cursor.setPosition(stop,QTextCursor.KeepAnchor)
                                    
                                    cursor.setCharFormat(format)
                                    '''
                                    
                                    self.manualSelect(start, stop, '#fcc')
                                    
                                if errPos:
                                    
                                    start = self.cons.manualSelectionPos[0] + errPos - 1
                                    
                                    '''
                                    format = cursor.charFormat()
                                    format.setBackground(QColor('#F66'))
                                
                                    cursor.setPosition(start,QTextCursor.MoveAnchor)
                                    cursor.setPosition(start + 1,QTextCursor.KeepAnchor)
                                    
                                    cursor.setCharFormat(format)
                                    '''
                                    self.manualSelect(start, start+1, '#f66')

                                #cursor.endEditBlock()
                
            else:
                self.indicator.status = 'disconnected'
                
                log('console connection lost %s, %s' % (str(self.conn), str(self.dbi)))
                
                self.connectionLost()
                #answer = utils.yesNoDialog('Connectioni lost', 'Connection to the server lost, reconnect?' cancelPossible)
                #if answer == True:


            t0 = self.t0
            t1 = time.time()
            
            #there is no dbCursor at this point, so no server time for you...
            logText = 'Query was running for... %s' % utils.formatTime(t1-t0)
            
            self.t0 = None
            self.indicator.t0 = None

            self.log(logText)

            self.indicator.runtime = None
            self.indicator.updateRuntime('stop')

            self.indicator.repaint()
            
            if self.stQueue:
                self.log('Queue processing stopped due to this exception.', True)
                self.stQueue.clear()

            return
        
        sql, result, refreshMode = self.sqlWorker.args
        
        dbCursor = self.sqlWorker.dbCursor
        
        if dbCursor is not None:
            result._connection = dbCursor.connection
        
        #self.psid = self.sqlWorker.psid
        #log('psid saved: %s' % utils.hextostr(self.psid))
        
        if dbCursor is not None:
            log('Number of resultsets: %i' % len(dbCursor.description_list), 3)

        t0 = self.t0
        t1 = time.time()
        
        self.t0 = None
        self.indicator.t0 = None

        sptStr = ''
        if dbCursor is not None and hasattr(dbCursor, 'servertime'):
            spt = dbCursor.servertime
            sptStr = ' (' + utils.formatTimeus(spt) + ')'

        # logText = 'Query execution time: %s' % utils.formatTime(t1-t0)
        timeStr = utils.formatTime(t1-t0, skipSeconds = True)
        logText = f'Query execution time: {timeStr}{sptStr}'

        rows_list = self.sqlWorker.rows_list
        cols_list = self.sqlWorker.cols_list
        resultset_id_list = self.sqlWorker.resultset_id_list
        
        #if rows_list is None or cols_list is None:
        if not cols_list:
            # that was not exception, but
            # it was a DDL or something else without a result set so we just stop
            
            if dbCursor is not None:
                logText += ', ' + utils.numberToStr(dbCursor.rowcount) + ' rows affected'
            
            result.clear()
            
            # now destroy the tab, #453
            # should we also remove the result from self.results? Do we know which one?
            # self.results.remove(result) ?
            
            i = self.resultTabs.count()
            log ('no resultset, so kill the tab #%i...' % i, 4)
            
            self.resultTabs.removeTab(i-1)
            
            #return 2021-08-01
            
            numberOfResults = 0
            
        else:
            numberOfResults = len(cols_list)
        
        for i in range(numberOfResults):
            
            #print('result:', i)
            
            if i > 0:
                result = self.newResult(self.conn, result.statement)
                
            result.rows = rows_list[i]
            result.cols = cols_list[i]

            #log(f'sqlFinished rowlist reference count: {sys.getrefcount(result.rows)}', 4)
            
            result.psid = self.sqlWorker.psid
            log('psid saved: %s' % utils.hextostr(result.psid), 4)
            
            #hana hardcode...
            if result.cols and result.cols[0][2] == 'SCALAR':
                result._resultset_id = None
            else:
                if resultset_id_list is not None:
                    result._resultset_id = resultset_id_list[i]
                else:
                    result._resultset_id = None
                
            rows = rows_list[i]
        
            resultSize = len(rows_list[i])

            # copied from statementExecute (same code still there!)
            result.detached = False
            
            if result.cols is not None:
                for c in result.cols:
                    if self.dbi.ifLOBType(c[1]):
                        result.LOBs = True
                        break
                        
                        
            if result.LOBs == False and (not result.explicitLimit and resultSize == result.resultSizeLimit):
                log('detaching due to possible SUSPENDED because of unfinished fetch')
                result.detach()
                        

            if result.LOBs:
                self.LOBs = True
                result.triggerDetachTimer(self)

            lobs = ', +LOBs' if result.LOBs else ''

            logText += '\n' + str(len(rows)) + ' rows fetched' + lobs
            if resultSize == cfg('resultSize', 1000): logText += ', note: this is the resultSize limit'

            result.populate(refreshMode)
            
            if result.highlightColumn:
                result.highlightRefresh()

        if not self.timerAutorefresh:
            self.log(logText)

        if numberOfResults:
            log('clearing lists (cols, rows): %i, %i' % (len(cols_list), len(rows_list)), 4)
            
            for i in range(len(cols_list)):
                #log('rows %i:%i' % (i, len(rows_list[0])))
                del rows_list[0]
                #log('cols %i:%i' % (i, len(cols_list[0])))
                del cols_list[0]
            
        if self.indicator.status != 'alert':
            '''
            if self.indicator.bkpStatus == 'autorefresh':
                self.indicator.status = self.indicator.bkpStatus
            else:
            '''
            if self.timerAutorefresh:
                self.indicator.status = 'autorefresh'
            elif result.LOBs:
                self.indicator.status = 'detach'
            else:
                if self.LOBs:
                    self.indicator.status = 'detach'
                else:
                    self.indicator.status = 'idle'
            
        self.indicator.runtime = None
        self.indicator.updateRuntime('stop')
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
        
        m = reExpPlan.search(sql)
        
        if m is not None:

            plan_id = m.group(1)
        
            if len(self.stQueue) > 0:
                self.log('explain plan not possible in queue, please run by itesf', True)
                return

            i = self.resultTabs.count()
            log ('Normal statement execution flow aborted, so kill the tab #%i' % i, 4)
            
            self.resultTabs.removeTab(i-1)

            sqls = []
            
            sqls.append("explain plan set statement_name = 'st$%s' for sql plan cache entry %s" % (plan_id, plan_id))
            sqls.append("select * from explain_plan_table where statement_name = 'st$%s'" % (plan_id))
            sqls.append("delete from explain_plan_table where statement_name = 'st$%s'" % (plan_id))
            sqls.append("commit")
                
            self.stQueue = sqls.copy()
            self.launchStatementQueue()
        
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
        
        if not self.timerAutorefresh:
            self.log('\nExecute: ' + txtSub + suffix)

        ##########################
        ### trigger the thread ###
        ##########################
        
        self.sqlWorker.args = [sql, result, refreshMode]
        
        self.t0 = time.time()
        self.indicator.t0 = self.t0
        self.sqlRunning = True
        
        self.indicator.bkpStatus = self.indicator.status
        self.indicator.status = 'running'
        self.indicator.repaint()
        
        #print('--> self.thread.start()')
        self.thread.start()
        log(f'[thread] started, parent: {int(QThread.currentThreadId())}', 5)
            
        return
        
    def resultTabsKey (self, event):

        modifiers = QApplication.keyboardModifiers()

        if not ((modifiers & Qt.ControlModifier) or (modifiers & Qt.AltModifier)):
            if event.key() == Qt.Key_F8 or event.key() == Qt.Key_F9 or event.key() == Qt.Key_F5:
            
                i = self.resultTabs.currentIndex()
                log('refresh %i' % i)
                self.refresh(i) # we refresh by index here...
                return
                
        super().keyPressEvent(event)

    '''
    @profiler
    def updateRuntime_DEPRICATED(self, mode = None):
        ''
            manages the indicator hint and calculates it's value
        
            mode = 'on': enable the hint, emmited by indicator on mouse hover
                'off': emmited by indicator on exit
                'stop': triggered manually on stop of sql execution.
        ''
        t0 = self.t0
        t1 = time.time()
                
        if mode == 'on':
            if t0 is not None: # normal hint for running console
                if self.runtimeTimer == None: 
                    self.runtimeTimer = QTimer(self)
                    self.runtimeTimer.timeout.connect(self.updateRuntime)
                    self.runtimeTimer.start(1000)
            elif self.indicator.status == 'autorefresh': # autorefresh backward counter
                if self.runtimeTimer == None:
                    self.runtimeTimer = QTimer(self)
                    self.runtimeTimer.timeout.connect(self.updateRuntime)
                    self.runtimeTimer.start(1000)
                
        elif mode == 'off' or mode == 'stop':
            if mode == 'stop' and self.indicator.status == 'autorefresh':
                pass
            else:
                if self.runtimeTimer is not None:
                    self.indicator.runtime = None
                    self.runtimeTimer.stop()
                    self.runtimeTimer = None  

                    self.indicator.updateRuntimeTT()
                    
                    return
                
        if mode == 'off' or mode == 'stop':
            self.indicator.runtime = None
            self.indicator.updateRuntimeTT()
            return
            
        if t0 is not None:
            self.indicator.runtime = utils.formatTimeShort(t1-t0)
        elif self.indicator.status == 'autorefresh': # autorefresh backward counter
            delta = self.nextAutorefresh - datetime.datetime.now()
            deltaSec = round(delta.seconds + delta.microseconds/1000000)
            self.indicator.runtime = 'Run in: ' + utils.formatTimeShort(deltaSec)
        else:
            self.indicator.runtime = None
            
        self.indicator.updateRuntimeTT()
                

    '''

    def reportRuntime(self):
            self.selfRaise.emit(self)
    
    
    def toolbarExecuteNormal(self):
        self.executeSelection('normal')

    def toolbarExecuteSelection(self):
        self.cons.executionTriggered.emit('no parse')
    
    def toolbarExecuteLeaveResults(self):
        self.cons.executionTriggered.emit('leave results')
        
    def toolbarFormat(self):
        self.cons.formatSelection()

    def toolbarBrowser(self):
        self.sqlBrowserSignal.emit()
    
    def toolbarConnect(self):
        self.connectDB()

    def toolbarDisconnect(self):
        self.disconnectDB()
        
    def toolbarAbort(self):
        self.cancelSession()
        
    def toolbarRefresh(self, state):
    
        if self.lockRefreshTB:
            return
        
        if state:
            id = QInputDialog

            value, ok = id.getInt(self, 'Refresh interval', 'Input the refresh interval in seconds                          ', self.defaultTimer[0], 0, 3600, 5)
            
            if ok:
                self.setupAutorefresh(value)
                self.defaultTimer[0] = value
                
                if self.timerSet[0] == False: # bounce back
                    self.lockRefreshTB = True
                    self.tbRefresh.setChecked(False)
                    self.lockRefreshTB = False
                
            else:
                self.tbRefresh.setChecked(False)

        else:
            self.setupAutorefresh(0)
        
        return False
        
    def toolbarABAP(self, state):
        self.abapCopyFlag[0] = state
        
    def toolbarHelp(self):
        QDesktopServices.openUrl(QUrl('https://www.rybafish.net/sqlconsole'))

        
        
    def toolbarEnable(self):
        if self.toolbar is None:
            self.toolbar = QToolBar('SQL', self)
            
            #tbExecuteNormal = QAction('[F8]', self)
            tbExecuteNormal = QAction(QIcon(resourcePath('ico', 'F8_icon.png')), 'Execute statement [F8]', self)
            tbExecuteNormal.triggered.connect(self.toolbarExecuteNormal)
            self.toolbar.addAction(tbExecuteNormal)

            tbExecuteSelection = QAction(QIcon(resourcePath('ico', 'F8alt_icon.png')), 'Execute selection without parsing [Alt+F8]', self)
            tbExecuteSelection.triggered.connect(self.toolbarExecuteSelection)
            self.toolbar.addAction(tbExecuteSelection)

            tbExecuteLeaveResult = QAction(QIcon(resourcePath('ico', 'F8ctrl_icon.png')), 'Execute opening a new result set tab [Ctrl+F8]', self)
            tbExecuteLeaveResult.triggered.connect(self.toolbarExecuteLeaveResults)
            self.toolbar.addAction(tbExecuteLeaveResult)
            
            tbFormat = QAction(QIcon(resourcePath('ico', 'format.png')), 'Beautify code [Ctrl+Shift+O]', self)
            tbFormat.triggered.connect(self.toolbarFormat)
            self.toolbar.addAction(tbFormat)

            tbBrowser = QAction(QIcon(resourcePath('ico', 'sqlbrowser.png')), 'SQL Browser [F11]', self)
            tbBrowser.triggered.connect(self.toolbarBrowser)
            self.toolbar.addAction(tbBrowser)

            # connect/discinnect
            self.toolbar.addSeparator()
            
            tbConnect = QAction(QIcon(resourcePath('ico', 'connect.png')), '(re)Connect', self)
            tbConnect.triggered.connect(self.toolbarConnect)
            # tbConnect.setEnabled(False)
            self.toolbar.addAction(tbConnect)

            tbDisconnect = QAction(QIcon(resourcePath('ico', 'disconnect.png')), 'Disconnect', self)
            tbDisconnect.triggered.connect(self.toolbarDisconnect)
            self.toolbar.addAction(tbDisconnect)

            tbAbort = QAction(QIcon(resourcePath('ico', 'abort.png')), 'Generate cancel session SQL', self)
            tbAbort.triggered.connect(self.toolbarAbort)
            self.toolbar.addAction(tbAbort)
            
            self.toolbar.addSeparator()
            
            
            self.tbRefresh = QToolButton()
            self.tbRefresh.setIcon(QIcon(resourcePath('ico', 'refresh.png')))
            self.tbRefresh.setToolTip('Schedule automatic refresh for the result set')
            self.tbRefresh.setCheckable(True)
            self.tbRefresh.toggled.connect(self.toolbarRefresh)
            self.toolbar.addWidget(self.tbRefresh)
            
            self.toolbar.addSeparator()
            
            self.ABAPCopy = QToolButton()
            self.ABAPCopy.setIcon(QIcon(resourcePath('ico', 'abapcopy.png')))
            self.ABAPCopy.setToolTip('Use ABAP-style (markdown) result copy by default.')
            self.ABAPCopy.setCheckable(True)
            self.ABAPCopy.toggled.connect(self.toolbarABAP)
            self.toolbar.addWidget(self.ABAPCopy)
            
            tbHelp = QAction(QIcon(resourcePath('ico', 'help.png')), 'SQL Console Help', self)
            tbHelp.triggered.connect(self.toolbarHelp)
            self.toolbar.addAction(tbHelp)

            self.vbar.insertWidget(0, self.toolbar)

            #self.setTabOrder(self.cons, self.toolbar)
            #self.toolbar.setFocusPolicy(Qt.NoFocus)
            #self.cons.setFocus()
            #self.toolbar.clearFocus()
            #self.toolbar.setFocusProxy(self.cons)
        else:
            self.toolbar.show()

    def toolbarDisable(self):
        if self.toolbar:
            self.toolbar.hide()


    def consoleStatus(self):

        if self.config:
            log('console config exists', 5)
        else:
            self.warnLabel.setText('')
            self.warnLabel.setVisible(False)
            log('No config in console status, exit', 4)
            return

        if self.config.get('secondary'):
            log('Secondary console usage detected', 2)
            self.secondary = True

        if self.config.get('usage') == 'PRODUCTION':
            log('PROD console usage detected', 2)
            self.prod = True

        self.warnChange()

    def warnChange(self):
        '''changes the label above the console text'''

        txt = ''

        if self.secondary:
            dbi = self.config.get('dbi', '')
            txt = f'Secondary connection: {dbi}'

            if self.dpid:
                txt += f', {self.dpid}'
        if self.prod:
            if self.secondary:
                txt += ' <b>[PROD]</b>'
            else:
                txt += '[PROD]'

        if txt:
            txt = f'<font color="blue">{txt}</font>'
            self.warnLabel.setText(txt)
            self.warnLabel.setVisible(True)
        else:
            self.warnLabel.setText('')
            self.warnLabel.setVisible(False)

        log(f'warn change: {txt}', 5)


    def fontUpdated(self):
        self.fontUpdateSignal.emit('console')

    def fontResultUpdated(self):
        self.fontUpdateSignal.emit('resultSet')

    def resultFontUpdate(self):
        fontSize = cfg('result-fontSize')
        for r in self.results:
            r.zoomFont(mode='=', toSize=fontSize)

    def initUI(self):
        '''
            main sqlConsole UI 
        '''
        self.vbar = QVBoxLayout()
        hbar = QHBoxLayout()
        
        #self.cons = QPlainTextEdit()
        self.cons = console(self)
        
        self.cons._parent = self
        
        self.cons.executionTriggered.connect(self.executeSelection)
        self.cons.log.connect(self.log)
        
        self.cons.openFileSignal.connect(self.openFile)
        self.cons.goingToCrash.connect(self.delayBackup)
        self.cons.fontUpdateSignal.connect(self.fontUpdated)
        
        self.resultTabs = QTabWidget()
        
        self.resultTabs.keyPressEvent = self.resultTabsKey
                
        self.spliter = QSplitter(Qt.Vertical)
        #self.logArea = QPlainTextEdit()
        self.logArea = logArea()
        
        self.warnLabel = QLabel('')

        self.spliter.addWidget(self.cons)
        self.spliter.addWidget(self.resultTabs)
        self.spliter.addWidget(self.logArea)
        
        self.spliter.setSizes([300, 200, 10])
        
        if cfg('sqlConsoleToolbar', True):
            self.toolbarEnable()
                    
        self.vbar.addWidget(self.warnLabel)

        self.vbar.addWidget(self.spliter)
        
        self.setLayout(self.vbar)
        
        # self.SQLSyntax = SQLSyntaxHighlighter(self.cons.document())
        self.cons.SQLSyntax = SQLSyntaxHighlighter(self.cons.document())
        #console = QPlainTextEdit()
        
        self.cons.setFocus()
