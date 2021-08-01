from PyQt5.QtWidgets import (QWidget, QToolTip, QFrame,
    QPushButton, QApplication, QMainWindow, QAction, qApp, QPlainTextEdit, QVBoxLayout, QSplitter, QHBoxLayout)

from PyQt5.QtGui import QFont, QIcon, QPainter, QBrush, QColor, QPen, QFontMetrics, QTextCursor

from PyQt5.QtCore import Qt, QSize

from utils import cfg

class QPlainTextEditLN(QWidget):
    class PlainTextEdit(QPlainTextEdit):
        def __init__(self, parent = None):
            super().__init__(parent)
            
            #font = QFont ('Consolas')
            #self.setFont(font)

        '''
        def contextMenuEvent (self, event):
            print('bebebe')
            #super().contextMenuEvent(event)
        '''
        
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

            self.font = self.edit.font()
            
            fontSize = cfg('console-fontSize', 10)
            
            self.font.setPointSize(fontSize)
            
            self.fm = QFontMetrics(self.font)
            
            self.fontHeight = self.fm.height()
            self.fontWidth = self.fm.width('0')
            
            self.adjustWidth(1)

        def adjustWidth(self, lines):

            newWidth = len(str(lines))

            if newWidth < self.minWidth:
                self.width = self.minWidth
            else:
                self.width = newWidth
                
            self.baseWidth = self.width*self.fontWidth
                
            self.setFixedWidth(self.width*self.fontWidth)
            
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
            
            #margin = 3
            
            #fln = self.edit.verticalScrollBar().value()
            
            qp.setFont(self.font)
            
            block = self.edit.firstVisibleBlock()
            i = block.blockNumber()
            
            while block.isValid():
                i += 1

                ln = str(i)
                
                offset = self.baseWidth - self.fm.width(ln)
                y = self.edit.blockBoundingGeometry(block).translated(self.edit.contentOffset()).top()
                
                y += + self.fontHeight - 1
                
                # check if on the screen yet
                if y >= QPaintEvent.rect().top():
                    qp.drawText(offset, y, ln)
                    
                # check if out of the screen already
                if y >= QPaintEvent.rect().bottom():
                    break
                
                block = block.next()
            
            qp.end()
            
            self.locked  = False

    def __init__(self, parent):
        super().__init__(parent)
        
        #self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)

        self.edit = self.PlainTextEdit(self)
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

        self.setFont = self.edit.setFont
        self.setStyleSheet = self.edit.setStyleSheet
        
        self.edit.contextMenuEvent = self.contextMenuEvent # not sure why this works but it does.
        
        self.insertFromMimeData = self.edit.insertFromMimeData
        
        self.setFocus = self.edit.setFocus
        
        self.firstVisibleBlock = self.edit.firstVisibleBlock
        
        #self.keyPressEvent = self.edit.keyPressEvent
        
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
  