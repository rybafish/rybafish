from PyQt5.QtWidgets import (QWidget, QToolTip, QFrame,
    QPushButton, QApplication, QMainWindow, QAction, qApp, QPlainTextEdit, QVBoxLayout, QSplitter, QHBoxLayout)

from PyQt5.QtGui import QFont, QIcon, QPainter, QBrush, QColor, QPen, QFontMetrics, QTextCursor

from PyQt5.QtCore import Qt, QSize

from PyQt5.QtCore import pyqtSignal

from utils import cfg, cfgSet

class QPlainTextEditLN(QWidget):

    fontUpdateSignal = pyqtSignal()
    tabSwitchSignal = pyqtSignal(int)

    class PlainTextEdit(QPlainTextEdit):
        
        rehighlightSig = pyqtSignal()
        tabSwitchSignal = pyqtSignal(int)
        
        def __init__(self, parent=None):
            super().__init__(parent)
        
        '''
        def focusInEvent(self, event):
            super().focusInEvent(event)
            print('---- >>>>>>>>>>>>>>>> got focus!')

        def focusOutEvent(self, event):
            super().focusOutEvent(event)
            print('---- <<<<<<<<<<<<<<<< lost focus :((')
        '''
        
        def insertFromMimeData(self, src):
            # need to force re-highlight manually because of #476
            # actually we only need to call it if there was a selection
            
            cursor = self.textCursor()
            
            rehighlight = not cursor.selection().isEmpty()
            
            a = super().insertFromMimeData(src)

            if rehighlight:
                self.rehighlightSig.emit()
            
            return a
            
        def duplicateLine (self):
            cursor = self.textCursor()
            
            if cursor.selection().isEmpty():
                #txtline = self.document().findBlockByLineNumber(cursor.blockNumber())
                txtline = self.document().findBlockByNumber(cursor.blockNumber())
                
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.MoveAnchor)
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
                if endPos+1 > len(self.document().toPlainText()):
                    return
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
                    #line = self.document().findBlockByLineNumber(i)
                    line = self.document().findBlockByNumber(i)
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
                
                #line = self.document().findBlockByLineNumber(stLine)
                line = self.document().findBlockByNumber(stLine)
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

                    #line = self.document().findBlockByLineNumber(i)
                    line = self.document().findBlockByNumber(i)
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
                
        def wheelEvent(self, event):
            modifiers = QApplication.keyboardModifiers()

            if modifiers & Qt.ControlModifier:
                # this is processed one level higher
                return None

            super().wheelEvent(event)


        def keyPressEvent (self, event):

            modifiers = QApplication.keyboardModifiers()
            
            if modifiers & Qt.ControlModifier and event.key() == Qt.Key_D:
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
            elif modifiers == Qt.AltModifier and Qt.Key_0 < event.key() <= Qt.Key_9:
                self.tabSwitchSignal.emit(event.key() - Qt.Key_1)
            else:
                super().keyPressEvent(event)


    class LineNumberArea(QWidget):
        def __init__(self, edit):

            #redraw lock
            self.locked = False
            
            super().__init__()
            

            self.lines = 0
            self.width = 0

            self.minWidth = 3

            self.setMinimumSize(QSize(100, 15))
            self.edit = edit

            self.updateFontMetrix()

            self.fromLine = None
            self.toLine = None

        def updateFontMetrix(self):
            font = self.font()
            self.fm = QFontMetrics(font)

            self.fontHeight = self.fm.height()
            self.fontWidth = self.fm.width('0')

            lines = self.edit.blockCount()
            self.adjustWidth(lines)

        def updateFont(self, fontSize=None):

            font = self.edit.font()

            self.setFont(font)
            self.updateFontMetrix()

            return

        def adjustWidth(self, lines):

            newWidth = len(str(lines))

            if newWidth < self.minWidth:
                self.width = self.minWidth
            else:
                self.width = newWidth
                
            self.baseWidth = self.width*self.fontWidth
                
            self.setFixedWidth(self.width*self.fontWidth)
            
            self.fromLine = None
            
            self.repaint()

        def paintEvent(self, QPaintEvent):
        
            if self.locked:
                return
                
            self.locked  = True

            self.lines = self.edit.document().blockCount()

            qp = QPainter()
            super().paintEvent(QPaintEvent)
            qp.begin(self)
            
            s = self.size()
            h, w = s.height(), s.width()

            qp.setPen(QColor('#888'))
            
            block = self.edit.firstVisibleBlock()
            i = block.blockNumber()

            if self.fromLine is not None:
                delta = self.fromLine - 1
            else:
                delta = 0

            
            while block.isValid():
                i += 1

                j = i - delta

                if j > 0:
                    ln = str(j)
                else:
                    ln = ''
                
                offset = self.baseWidth - self.fm.width(ln)
                y = int(self.edit.blockBoundingGeometry(block).translated(self.edit.contentOffset()).top())
                # font 46, height = 71, delta = -14
                # font 24, height = 37, delta = -7
                # font 10, height = 15, delta -2
                
                yfix = int((self.fontHeight - 5) / 5) # this formula is 100% incorrect but I give up
                # let me know if you know why Linenumbers Area font and plaintext font scale / render on a different place.

                y += self.fontHeight
                #y += self.fontHeight - 1
                
                # check if on the screen yet
                if y >= QPaintEvent.rect().top():
                    qp.drawText(offset, y - yfix, ln)
                    
                # check if out of the screen already
                if y >= QPaintEvent.rect().bottom():
                    break
                    
                if self.fromLine is not None and i >= self.toLine:
                    break
                
                block = block.next()
            
            qp.end()
            
            self.locked  = False
            
    def zoomFont(self, mode, tosize=None):
        '''Zoom the font of the .edit widget'''

        fnt = self.edit.font()
        size = fnt.pointSize()

        if mode == '+':
            size += 1

        if mode == '-' and size > 1:
            size -= 1

        if mode in ['+', '-']:
            fnt.setPointSizeF(size)
            self.edit.setFont(fnt)
            self.lineNumbers.updateFont(size)

            cfgSet('console-fontSize', size)
            self.fontUpdateSignal.emit()

        if mode == '=' and tosize:
            fnt.setPointSize(tosize)
            self.edit.setFont(fnt)
            self.lineNumbers.updateFont(size)

    def wheelEvent(self, event):
        '''Zoom the font of the .edit widget'''

        p = event.angleDelta()

        modifiers = QApplication.keyboardModifiers()

        if modifiers == Qt.ControlModifier:

            if p.y() >0:
                self.zoomFont(mode='+')
            if p.y() <0:
                self.zoomFont(mode='-')


    def setFont(self, font):
        self.edit.setFont(font)
        # self.lineNumbers.setFont(font)
        self.lineNumbers.updateFont()


    def __init__(self, parent=None):
        super().__init__(parent)
        
        #self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)

        self.edit = self.PlainTextEdit(self)
        
        self.setFocusProxy(self.edit)
        
        self.lineNumbers = self.LineNumberArea(self.edit)

        hbox = QHBoxLayout(self)

        hbox.addWidget(self.lineNumbers)
        hbox.addWidget(self.edit)
        
        self.edit.blockCountChanged.connect(self.lineNumbers.adjustWidth)
        self.edit.updateRequest.connect(self.redrawLines)
        
        self.setTabStopDistance = self.edit.setTabStopDistance
        self.cursorPositionChanged = self.edit.cursorPositionChanged
        self.selectionChanged = self.edit.selectionChanged

        self.document = self.edit.document
        self.textChanged = self.edit.textChanged

        self.updateRequest = self.edit.updateRequest
        self.setPlainText = self.edit.setPlainText

        self.textCursor = self.edit.textCursor
        self.setTextCursor = self.edit.setTextCursor
        self.toPlainText = self.edit.toPlainText
        self.viewport = self.edit.viewport

        self.setStyleSheet = self.edit.setStyleSheet
        
        self.edit.contextMenuEvent = self.contextMenuEvent # not sure why this works but it does.
        
        self.edit.tabSwitchSignal.connect(self.tabSwitchSignal)
        
        #self.insertFromMimeData = self.edit.insertFromMimeData
        
        self.setFocus = self.edit.setFocus
        
        self.firstVisibleBlock = self.edit.firstVisibleBlock
        
        #self.keyPressEvent = self.edit.keyPressEvent
        
        self.rehighlightSig = self.edit.rehighlightSig

        # required for csvImport
        self.setLineWrapMode = self.edit.setLineWrapMode
        self.horizontalScrollBar = self.edit.horizontalScrollBar
        self.verticalScrollBar = self.edit.verticalScrollBar
        
        self.locked = False
    
    def redrawLines(self, rect, dy):
        if rect.width() < 20:
            return
        
        if self.locked: #prevent refresh on top of refresh
            return 
            
        self.locked = True
        
        self.lineNumbers.repaint()
        
        self.locked = False

    def paintEventZZ(self, QPaintEvent):
        qp = QPainter()
        super().paintEvent(QPaintEvent)
        qp.begin(self)
        
        s = self.size()
        h, w = s.height(), s.width()

        
        #qp.setPen(QColor('#080'))
        #qp.drawRect(0, 0, w-2, h-2)
        
        qp.end()
