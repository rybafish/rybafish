'''
    QTableWidget extention for result set table + csv preview table
'''
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QApplication, QMenu, QInputDialog, QStyledItemDelegate
from PyQt5.QtCore import pyqtSignal, Qt, QSize, QTimer
from PyQt5.QtGui import QFont, QFontMetricsF, QColor, QPixmap, QBrush

import utils
from utils import cfg, log, normalize_header, deb

import lobDialog, searchDialog
import customSQLs
import highlight

from profiler import profiler

class delegatedStyle(QStyledItemDelegate):

    def __init__(self, table, cols):
        super().__init__()
        self.cols = cols
        self.table = table

        if cfg('dataBarSelected', True):
            p = table.palette()
            self.selectedBrush = QBrush(p.color(p.Highlight))

    @profiler
    def paint(self, qp, style, idx):

        c = idx.column()
        # hlColor = QColor('#8de')
        hlColor = QColor('#8cf')


        manual = False

        if c in self.cols:
            dColor = hlColor    # actually to be used for bar itself

            d = idx.data(Qt.UserRole+1)

            if d is None:
                d = 0

            row = idx.row()
            col = idx.column()

            manual = False
            whiteBG = False

            if self.table:
                item = self.table.item(row, col)
                bg = item.background()

                if cfg('dataBarSelected', True):
                    if item.isSelected():
                        bg = self.selectedBrush

                cl = bg.color()
                (r, g, b) = (cl.red(), cl.green(), cl.blue()) # bg color

                if not(r == g == b == 0): # this seems to be a default table bg, don't know better way to check
                    manual = True

                if manual:
                    # f = item.font() # somehow it does not translated to items level
                    f = self.table.font()
                    alRight = False

                    if item.textAlignment() & Qt.AlignRight:
                        alRight = True

                    fm = QFontMetricsF(f)
                    fh = fm.height()

                    text = item.text()

                    if (r == g == b == 255):
                        whiteBG = True

            r = style.rect

            x = r.x()
            y = r.y()
            h = int(round(r.height() - 1))
            w = int(round(r.width() - 1))
            wd = int(round(r.width() - 1)*d)

            ident = 3           # horisontal text ident

            if manual:          # 100% manual render of the cell
                qp.setPen(bg.color())
                qp.setBrush(bg)
                qp.drawRect(x, y, w, h)

                if whiteBG:
                    dColor = hlColor
                else:
                    dColor = utils.colorMix(hlColor, bg.color())

            qp.setPen(utils.colorDarken(dColor, 0.8))
            qp.setBrush(dColor)
            qp.drawRect(x, y, wd, h)

            if manual:
                tw = fm.width(text)
                # print(f'rect {h}:{w}')
                # print(f'text width: {tw}')

                if tw + ident*2 > w+1: # if text does not fit...

                    i = len(text) - 1

                    # cut it until no characters left at all
                    while tw + ident*2 > w+1 and i >=0:
                        i -= 1
                        txt = text[:i] + '\u2026'
                        tw = fm.width(txt)

                    if i <= 0:
                        txt = ''

                else:
                    txt = text

                if alRight:
                    # offset = int(w - fm.width(text)) - 1 - 4
                    offset = int(w - fm.width(txt)) - 2
                else:
                    offset = 4

                # print(f'offset: {offset}, {txt=}')

                qp.setPen(QColor('#000')) # text color
                qp.drawText(x + offset, y + int(fh/2 + h/2)- 2, txt)

        if not manual:
            super().paint(qp, style, idx)


class QResultSet(QTableWidget):
    '''
        Implements the result set widget, basically QTableWidget with minor extensions
        Created to show the resultset (one result tab), destroyed when re-executed.

        Table never refilled. 
    '''
    
    alertSignal = pyqtSignal(['QString', int])
    insertText = pyqtSignal(['QString'])
    executeSQL = pyqtSignal(['QString', 'QString'])
    triggerAutorefresh = pyqtSignal([int])
    detachSignal = pyqtSignal()
    fontUpdateSignal = pyqtSignal()

    def __init__(self, conn):
    
        self._resultset_id = None    # filled manually right after execute_query

        self._connection = None      # this one populated in sqlFinished # 2021-07-16, #377
        
        self.statement = None        # statements string (for refresh)
        
        self.LOBs = False            # if the result contains LOBs
        self.detached = None         # supposed to be defined only if LOBs = True
        self.detachTimer = None      # results detach timer
        
        self.cols = [] # column descriptions
        self.rows = [] # actual data 
        
        self.headers = [] # column names
        
        self.psid = None # psid to drop on close
        
        # overriden in case of select top xxxx
        self.explicitLimit = False 
        self.resultSizeLimit = cfg('resultSize', 1000)
        
        self.timer = None
        self.timerDelay = None
        self.databar = None     # true when any databars added
        self.databarCols = []   # list of columns for databar
        
        #self.timerSet = None        # autorefresh menu switch flag
        
        self.alerted = None         # one time alarm signal flag
        
        super().__init__()
        
        verticalHeader = self.verticalHeader()
        verticalHeader.setSectionResizeMode(verticalHeader.Fixed)
        
        scale = 1

        fontSize = cfg('result-fontSize', 10)
        
        font = QFont ()
        font.setPointSize(fontSize)
        
        self.horizontalHeader().setFont(font);
        self.setFont(font)
        
        itemFont = QTableWidgetItem('').font()
        
        rowHeight = int(scale * QFontMetricsF(itemFont).height()) + 8
                
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
        
        self.highlightColumn = None     # column index to highlight
        self.highlightValue = None      # value to highlight, when None - changes will be highlighted

        self.highlightRows = []         # explicit rows to be highlighted nmw (alt+click, #974)
        
        self.abapCopyFlag = [False]

        self.cellClicked.connect(self.cellClickedSig)

        
    @profiler
    def checkHighlightClr(self, col, value):
        '''detect color for highlighter, returns brush'''

        column = self.headers[col].lower()
        hlc = highlight.hlc.get(column)

        if hlc:
            if value in hlc:
                return hlc[value]

        return QBrush(QColor('#dfe'))

    @profiler
    def checkHighlight(self, col, value):
        '''check for additional highlighters based on cell value'''

        column = self.headers[col].lower()
        hl = highlight.hll.get(column)

        if hl is not None:
            if value in hl:
                return hl[value]

    def databarEnable(self):
        if self.databar:
            return
        else:
            ds = delegatedStyle(self, self.databarCols)
            self.setItemDelegate(ds)
            self.databar = True

    def databarAdd(self, i):
        '''enable dynamic highlighting for the column

        i - column number

        '''

        if i not in self.databarCols:
            self.databarCols.append(i)

        if self.dataBarNormalize(i):
            self.databarEnable()

    def dataBarRenew(self):
        for i in self.databarCols:
            self.dataBarNormalize(i)


    def dataBarNormalize(self, c):
        '''normalize column values and save normilized to item.data'''

        rows = self.rowCount()

        if c >= len(self.cols):
            log('dataBarNormalize column does not exit', 5)
            return

        maxval = 0

        try:
            for i in range(rows):
                v = self.rows[i][c]

                if v is None:
                    continue

                if v > maxval:
                    maxval = v

        except TypeError as e:
            log(f'Column not valid for databar formatting: {e}', 2)
            return None

        if maxval == 0:
            return None

        for i in range(rows):
            v = self.rows[i][c]

            if v is None:
                d = None
            else:
                d = v/maxval

            self.item(i, c).setData(Qt.UserRole + 1, d)

        return True


    @profiler
    def highlightRefresh(self):
        '''
            highlight resultset based on RMC "highlight this value" or "highlight changes"

            initial execution is case 1

            same called on F8/F9 to re-highlight results (case 2)

            case 1 might be called on top of already highlighted resutset
            this is why white BG have to be mandatory re-set for the non-highlighted stuff

            _and_ this method cannot rely on any cells BG, because of this 'case 1' -> 'case 1' sequential call


            all the dataBar stuff to be called later as it relies on already defined BG color
        '''
        def combineBrush(noBg, brush, color):
            if noBg:
                return brush
            else:
                return QBrush(utils.colorMix(brush.color(), color))

        deb('HL refresh')
        rows = self.rowCount()
        cols = self.columnCount()
        
        col = self.highlightColumn
        value = self.highlightValue
        deb(f'do the highlight: column:{col}, value:{value}', comp='highlight')

        if col == -1 or rows == 0:
            return

        hl = False

        clr = QColor(cfg('highlightColor', '#def'))
        hlBrush = QBrush(clr)

        clr = QColor(int(clr.red()*0.9), int(clr.green()*0.9), int(clr.blue()*0.95))
        hlBrushLOB = QBrush(clr)
        
        # hl2Brush = QBrush(QColor('#dfe')) it now comes from checkHighlightClr

        wBrush = QBrush(QColor('#ffffff'))
        # wBrush = QBrush(Qt.NoBrush) - seems here real reset needed, to fix previous stuff on refresh
        wBrushLOB = QBrush(QColor('#f4f4f4'))
        
        if self.highlightColumn is not None:
            if value is None:
                val = self.item(0, col).text()
            else:
                val = value
            
        lobCols = []
        
        for i in range(len(self.cols)):
            if self.dbi.ifLOBType(self.cols[i][1]):
                lobCols.append(i)
            
        for i in range(rows):
            if self.highlightColumn is not None:
                if value is None:
                    if val != self.item(i, col).text():
                        hl = not hl
                else:
                    if val == self.item(i, col).text():
                        hl = True
                    else:
                        hl = False
            else:
                hl = False

            if i in self.highlightRows:
                hlExplicit = True
            else:
                hlExplicit = False

            for j in range(cols):
                deb(f'row: {i}, col: {j}', comp='highlight')
                bg = self.item(i, j).background()

                # okay I am lost now, what this can be not white?

                deb(f'check: column {j}, value: {self.item(i, j).text()}', comp='highlight')
                if self.checkHighlight(j, self.item(i, j).text()):
                    deb('some color...', comp='highlight')
                    # cl = hl2Brush.color()
                    cl = self.checkHighlightClr(j, self.item(i, j).text()).color()
                else:
                    deb('nope...', comp='highlight')
                    cl = QBrush(Qt.NoBrush).color()

                (r, g, b) = (cl.red(), cl.green(), cl.blue()) # bg color

                noBg = (r == g == b == 0) # true if the bg is default

                # the bG is not default normally in just a single case - cell is highlighted (based on value)

                if not noBg:
                    deb(f'>>> row: {i}, col:{j}: not a default bg', comp='highlight')
                else:
                    deb(f'row: {i}, col:{j} default white', comp='highlight')

                if hl or hlExplicit:          # the row is highlighted
                    if j in lobCols:
                        useBrush = combineBrush(noBg, hlBrushLOB, cl)
                    else:
                        useBrush = combineBrush(noBg, hlBrush, cl)
                    self.item(i, j).setBackground(useBrush)
                else:           # the row is not highlighted
                    if j in lobCols:
                        # self.item(i, j).setBackground(wBrushLOB)
                        useBrush = combineBrush(noBg, wBrushLOB, cl)
                    else:
                        # the row is not highlighted and not LOB... but there can be some BG still...
                        # but what is the point setting it to itself?
                        # the point setting white is clear - there might be a leftover from smth?
                        # self.item(i, j).setBackground(wBrush)
                        # useBrush = QBrush(cl)

                        # useBrush = QBrush(wBrush)
                        # useBrush = combineBrush(noBg, wBrush, cl)
                        if noBg:
                            useBrush = wBrush
                        else:
                            # useBrush = hl2Brush
                            useBrush = self.checkHighlightClr(j, self.item(i, j).text())

                    self.item(i, j).setBackground(useBrush)

                        # if self.checkHighlight(j, self.item(i, col).text()):
                        #     hl2 = True
                        # else:
                        #     hl2 = False
                        # if hl2 == False:
                        #     self.item(i, j).setBackground(wBrush)
                        # else:
                        #     self.item(i, j).setBackground(hl2Brush)

            if self.highlightColumn is not None:
                if value is None:
                    val = self.item(i, col).text()
    
    def contextMenuEvent(self, event):
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
        
        cmenu.addSeparator()
        
        refreshTimerStart = None
        refreshTimerStop = None
        
        i = self.currentColumn()
        
        cmenu.addSeparator()
    
        highlightColCh = cmenu.addAction('Highlight changes')
        highlightColVal = cmenu.addAction('Highlight this value')

        showDatabar = cmenu.addAction('Show data bar')
            
        cmenu.addSeparator()
        
        abapCopy = cmenu.addAction('Text formatted (markdown) copy')

        cmenu.addSeparator()
        
        if not self.timerSet[0]:
            refreshTimerStart = cmenu.addAction('Schedule automatic refresh for this result set')
        else:
            refreshTimerStop = cmenu.addAction('Stop autorefresh')
        
        if i >= 0 and self.headers[i] in customSQLs.columns:
            cmenu.addSeparator()

            for m in customSQLs.menu[self.headers[i]]:
                customSQL = cmenu.addAction(m)

        action = cmenu.exec_(self.mapToGlobal(event.pos()))
        
        if action == None:
            return

        '''
        if action == copyColumnName:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.cols[i][0])
        '''
        
        if action == highlightColCh:
            self.highlightColumn = i
            self.highlightValue = None
            self.highlightRefresh()

        if action == highlightColVal:
            self.highlightColumn = i
            self.highlightValue = self.item(self.currentRow(), i).text()
            self.highlightRefresh()
        
        if action == showDatabar:
            self.databarAdd(i)

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

                if cfg('dev'):  # mapping...
                    hm = cfg('maphost')
                    pm = cfg('mapport')
                    if hm and cname == 'HOST':
                        value = value.replace(hm[0], hm[1])
                    if pm and cname == 'PORT':
                        value = int(str(value).replace(pm[0], pm[1]))

                if self.dbi.ifNumericType(self.cols[c][1]):
                    values.append('%s = %s' % (normalize_header(cname), value))
                elif self.dbi.ifTSType(self.cols[c][1]):
                    values.append('%s = \'%s\'' % (normalize_header(cname), utils.timestampToStr(value)))
                else:
                    values.append('%s = \'%s\'' % (normalize_header(cname), str(value)))
                    
            filter = ' and '.join(values)

            self.insertText.emit(filter)
            
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

        if action == refreshTimerStart:
            '''
                triggers the auto-refresh timer
                
                the timer itself is to be processed by the parent SQLConsole object as it has 
                all the relevant accesses
                
                the feature is blocked when there are several resultset tabs
            '''

            id = QInputDialog

            value, ok = id.getInt(self, 'Refresh interval', 'Input the refresh interval in seconds                          ', self.defaultTimer[0], 0, 3600, 5)
            
            if ok:
                self.triggerAutorefresh.emit(value)
                self.defaultTimer[0] = value

        if action == refreshTimerStop:
            log('disabeling the timer...')
            self.triggerAutorefresh.emit(0)
            #self.timerSet[0] = False

        if action == abapCopy:
            self.copyCells(abapMode=True)
            
        if action is not None and i >= 0:
            
            key = self.headers[i] + '.' + action.text()
            
            if key in customSQLs.sqls:
                # custom sql menu item
            
                r = self.currentItem().row()
                c = self.currentItem().column()
                
                sm = self.selectionModel()

                if len(sm.selectedIndexes()) != 1:
                    self.log('Only single value supported for this action.', True)
                    return
                
                value = str(self.rows[r][c])
                
                #sql = customSQLs.sqls[key].replace('$value', value)
                
                self.executeSQL.emit(key, value)
                
                
        
    def detach(self):
        if self._resultset_id is None:
            # could be if the result did not have result: for example DDL or error statement
            # but it's strange we are detachung it...
            log('[!] attempted to detach resultset with no _resultset_id')
            return
            
        result_str = utils.hextostr(self._resultset_id)
        
        if self._connection is None:
            log('[!] resultset connection is None!')
            return
        
        if self.detached == False and self._resultset_id is not None:
            log('closing the resultset: %s' % (result_str))
            try:
                self.dbi.close_result(self._connection, self._resultset_id) 
                self.detached = True
            except Exception as e:
                log('[!] Exception: ' + str(e))
                
            self.detachSignal.emit()
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
        dtimer = cfg('detachTimeout', 300)
        
        log('Setting detach timer for %s %i sec' % (utils.hextostr(self._resultset_id), dtimer))
        self.detachTimer = QTimer(window)
        self.detachTimer.timeout.connect(self.detachCB)
        self.detachTimer.start(1000 * dtimer)
    
    def csvVal(self, v, t):
        '''escapes single value based on type'''
        
        if v is None:
            return cfg('nullStringCSV', '')
        elif self.dbi.ifBLOBType(t):
            return str(v.encode())
        else:
            if self.dbi.ifNumericType(t):
                return utils.numberToStrCSV(v, False)
            elif self.dbi.ifRAWType(t):
                return v.hex()
            elif self.dbi.ifTSType(t):
                return utils.timestampToStr(v)
            else:
                return str(v)
        
    
    def csvRow_deprecado(self, r):
        
        values = []
        
        # print varchar values to be quoted by "" to be excel friendly
        for i in range(self.columnCount()):
            #values.append(table.item(r, i).text())

            val = self.rows[r][i]
            vType = self.cols[i][1]
            
            values.append(self.csvVal(val, vType))
            
        return ';'.join(values)
        
    @profiler
    def copyCells(self, abapMode = False):
        '''
            copy cells or rows or columns implementation
        '''
        
        #print('copy cell(s)')
        
        def abapCopy():
        
            mdMode = cfg('copy-markdown', True)

            maxWidth = cfg('abap-length', 32)
            widths = []
            
            widths = [0]*len(colList)
            types = [0]*len(colList)
            
            deb(f'{widths=}')
            deb(f'len(colList) = {len(colList)}')
            deb(f'len(copypaste) = {len(copypaste)}')

            for l in copypaste:
                deb(l)

            for c in range(len(colList)):
            
                types[c] = self.cols[colList[c]][1]
            
                for r in range(len(copypaste)):
                
                    if widths[c] < len(copypaste[r][c]):
                        if len(copypaste[r][c]) >= maxWidth:
                            widths[c] = maxWidth
                            break
                        else:
                            widths[c] = len(copypaste[r][c])
                            

            '''
            tableWidth = 0
            
            for c in widths:
                tableWidth += c + 1
                
            tableWidth -= 1
            '''
            
            tableWidth = sum(widths) + len(widths) - 1

            topLine = '-' + '-'.rjust(tableWidth, '-') + '-'
            
            if mdMode:
                mdlLine = '|'

                for j in range(len(widths)):
                    if widths[j] > 1:
                        if self.dbi.ifNumericType(types[j]):
                            mdlLine += '-'*(widths[j]-1) + ':|'
                        else:
                            mdlLine += ':' + '-'*(widths[j]-1) + '|'
                    else:
                        log(f'column width <= 1? {widths[j]}, {j}', 2)
                        mdlLine += '-'*widths[j] + '|'

            else:
                mdlLine = '|' + '-'.rjust(tableWidth, '-') + '|'
                            
            csv = topLine + '\n'
            
            i = 0
            for r in copypaste:
                for c in range(len(colList)):
                    #val = r[c][:maxWidth]
                    
                    if len(r[c]) > maxWidth:
                        val = r[c][:maxWidth-1] + '…'
                    else:
                        val = r[c][:maxWidth]
                    
                    if self.dbi.ifNumericType(types[c]) and i > 0:
                        val = val.rjust(widths[c], ' ')
                    else:
                        val = val.ljust(widths[c], ' ')
                    
                    csv += '|' + val
                    
                csv += '|\n'

                if i == 0:
                    csv += mdlLine + '\n'
                    i += 1
                
            csv += topLine + '\n'
            
            return csv
        
    
        sm = self.selectionModel()
        
        colIndex = []
        colList = []
        
        for c in sm.selectedColumns():
            colIndex.append(c.column())
        
        rowIndex = []
        for r in sm.selectedRows():
            rowIndex.append(r.row())
            
        copypaste = []
        
        if len(rowIndex) >= 1000:
            # and len(colIndex) >= 5 ?
            # it is to expensive to check
            cellsSelection = False
        else:
            #this will be checked right away
            cellsSelection = True
        
        if (colIndex or rowIndex):
            # scan all selected cells to make sure this is pure column or row selection
        
            utils.timerStart()
        
            cellsSelection = False
            
            if len(sm.selectedIndexes()) == 1:
                #single cell selected, no need header for this
                cellsSelection = True
            else:
                for cl in sm.selectedIndexes():
                    r = cl.row()
                    c = cl.column()
                    
                    if (colIndex and c not in colIndex) or (rowIndex and r not in rowIndex):
                        # okay, something is not really inside the column (row), full stop and make regular copy
                    
                        cellsSelection = True
                        break
                    
            utils.timeLap()
            s = utils.timePrint()
            
            log('Selection model check: %s' % s[0], 5)
            
        if False and cellsSelection and abapMode:
            self.log('ABAP mode is only available when rows or columns are selected.', True)
        
        if not cellsSelection and rowIndex: 
            # process rows
            
            utils.timerStart()
            rowIndex.sort()
            
            cc = self.columnCount()
                
            hdrrow = []
            
            i = 0
            
            for h in self.headers:
            
                if len(self.headers) > 1 or abapMode:
                
                    if self.columnWidth(i) > 4:
                        hdrrow.append(h)
                        
                        colList.append(i) # important for abapCopy
                    
                i+=1
                    
            if hdrrow:
                copypaste.append(hdrrow)
    
            for r in rowIndex:
                values = []
                for c in range(cc):
                
                    if self.columnWidth(c) > 4:
                        values.append(self.csvVal(self.rows[r][c], self.cols[c][1]))
                    
                copypaste.append(values)
                
            if abapMode:
                csv = abapCopy()
            else:
                csv = ''
                for r in copypaste:
                    csv += ';'.join(r) + '\n'
            
            QApplication.clipboard().setText(csv)

            utils.timeLap()
            s = utils.timePrint()
            
            log('Clipboard formatting took: %s' % s[0], 5)
            QApplication.clipboard().setText(csv)

        elif not cellsSelection and colIndex: 
            # process columns
            colIndex.sort()
            
            hdrrow = []
            
            for c in colIndex:

                if self.columnWidth(c) > 4:
                    hdrrow.append(self.headers[c])
                    colList.append(c)

                
            if self.rowCount() > 1 or abapMode:
                copypaste.append(hdrrow)
                
            for r in range(self.rowCount()):
                values = []
                
                for c in colIndex:
                    if self.columnWidth(c) > 4:
                        values.append(self.csvVal(self.rows[r][c], self.cols[c][1]))
                
                copypaste.append(values)
            
            if abapMode:
                csv = abapCopy()
            else:
                csv = ''
                for r in copypaste:
                    csv += ';'.join(r) + '\n'
            
            QApplication.clipboard().setText(csv)
            
        else:
            # copy column
            #print('just copy')
            
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
            
            if abapMode:
                # check if the square area selected first
                
                if len(colIndex) > 0:
                    colList = colIndex[rowIndex[0]].copy()
                else:
                    colList = range(len(self.cols)) #fake 'all columns selected' list when the selection is empty
                
                abapNotPossible = False
                
                for ci in colIndex:
                    
                    if colList != colIndex[ci]:
                        abapNotPossible = True
                        break
                        
                if abapNotPossible:
                    self.log('ABAP-style copy is only possible for rectangular selections.', True)
                    return
                        
                values = []
                for c in colList:
                    if self.columnWidth(c) > 4:
                        values.append(self.headers[c])
                        
                copypaste.append(values)

                for r in rowIndex:
                    values = []

                    for c in colList:
                    
                        if self.columnWidth(c) > 4:
                            values.append(self.csvVal(self.rows[r][c], self.cols[c][1]))
                        
                    copypaste.append(values)
                    
                    
                csv = abapCopy()
                
                QApplication.clipboard().setText(csv)
                
                return
                
            
            rows = []

            cfgdev = cfg('dev')
            hm = cfg('maphost')
            pm = cfg('mapport')

            for r in rowIndex:
                colIndex[r].sort()

                values = []
                
                for c in colIndex[r]:
                
                    value = self.rows[r][c]
                    vType = self.cols[c][1]
                    
                    if value is None:
                        values.append(cfg('nullStringCSV', ''))
                    else:
                        if self.dbi.ifBLOBType(vType):
                            values.append(str(value.encode()))
                        else:
                            if self.dbi.ifNumericType(vType):
                                if cfgdev and pm and self.cols[c][0] == 'PORT': # mapping...
                                    value = int(str(value).replace(pm[0], pm[1]))
                                values.append(utils.numberToStrCSV(value, False))
                            elif self.dbi.ifRAWType(vType):
                                values.append(value.hex())
                            elif self.dbi.ifTSType(vType):
                                #values.append(value.isoformat(' ', timespec='milliseconds'))
                                values.append(utils.timestampToStr(value))
                            else:
                                if cfgdev and hm and self.cols[c][0] == 'HOST': # mapping...
                                    value = value.replace(hm[0], hm[1])
                                values.append(str(value))
                                
                rows.append( ';'.join(values))

            result = '\n'.join(rows)
            
            QApplication.clipboard().setText(result)
        

    def resultKeyPressHandler(self, event):
    
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.ControlModifier:
            if event.key() == Qt.Key_A:
                self.selectAll()
            
            if event.key() == Qt.Key_C or event.key() == Qt.Key_Insert:
                self.copyCells(abapMode=self.abapCopyFlag[0])

            if event.key() == Qt.Key_W:
                super().keyPressEvent(event)
        
        else:
            super().keyPressEvent(event)
            
    @profiler
    def populate(self, refreshMode=False):
        '''
            populates the result set based on
            self.rows, self.cols
        '''
    
        self.clear()
        
        self.highlightRows.clear()
        cols = self.cols
        rows = self.rows

        adhocDatabars = []
    
        row0 = []

        if cfg('experimental-formatting', True): # #990
            for i in range(len(cols)):
                cname = cols[i][0]
                if not refreshMode:
                    if cname[-3:] == '$db':
                        row0.append(cname[:-3])
                        deb(f'databar column detected: {cname}')
                        adhocDatabars.append(i)
                    else:
                        row0.append(cname)

        else:
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
        
        alert_str = cfg('alertTriggerOn')
        alert_simple = None
        
        if alert_str:
            if alert_str[0:1] == '{' and alert_str[-1:] == '}':
                alert_prefix = alert_str[:-1]
                alert_len = len(alert_str)
                alert_simple = False
            else:
                alert_simple = True
                alert_prefix = alert_str
                alert_len = len(alert_str)
        
        #fill the result table

        hm = cfg('maphost')
        pm = cfg('mapport')
        cfgdev = cfg('dev')

        for r in range(len(rows)):
            #log('populate result: %i' % r, 5)
            for c in range(len(row0)):
                
                val = rows[r][c]
                
                if val is None:
                    val = cfg('nullString', '?')
                    
                    item = QTableWidgetItem(val)
                elif self.dbi.ifNumericType(cols[c][1]):

                    if cfgdev and pm: # mapping stuff
                        with profiler('mapport'):
                            if row0[c] == 'PORT':
                                val = int(str(val).replace(pm[0], pm[1]))

                    if self.dbi.ifDecimalType(cols[c][1]):
                        val = utils.numberToStrCSV(val)
                    else:
                        val = utils.numberToStr(val)
                    
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif self.dbi.ifLOBType(cols[c][1]): #LOB
                    #val = val.read()
                    if self.dbi.ifBLOBType(cols[c][1]):
                        if val is None:
                            val = cfg('nullString', '?')
                        else:
                            val = str(val.encode())
                    else:
#                        val = str(val)
                        if val is None:
                            val = cfg('nullString', '?')
                        else:
                            val = str(val)
                            
                    item = QTableWidgetItem(val)
                    
                    if cfg('highlightLOBs', True):
                        item.setBackground(QBrush(QColor('#f4f4f4')))
                    
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop);

                elif self.dbi.ifRAWType(cols[c][1]): #VARBINARY
                    val = val.hex()
                    
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop);
                    
                elif self.dbi.ifVarcharType(cols[c][1]):

                    if cfgdev and hm: # mapping stuff
                        with profiler('maphost'):
                            if row0[c] == 'HOST':
                                val = val.replace(hm[0], hm[1])

                    item = QTableWidgetItem(val)
                    
                    if '\n' in val:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop);
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter);

                    hl = self.checkHighlight(c, val)
                        
                    if hl:
                        hlclr = self.checkHighlightClr(c, val)
                        item.setBackground(hlclr)
                        item.setToolTip(hl)

                    if alert_str:
                        #and val == cfg('alertTriggerOn'): # this is old, not flexible style
                        #'{alert}'
                        
                        with profiler('alertChecker'):
                        
                            #надо двинуть всё это барахло в отдельную функцию которая вернёт звук и громкость
                            #короче #696
                        
                            sound = None
                            
                            if alert_simple and val == alert_str:
                                sound = ''
                                volume = -1
                            elif val[:alert_len - 1] == alert_prefix:
                                # okay this looks like alert
                                
                                sound, volume = utils.parseAlertString(val)
                                
                            if sound is not None and not self.alerted:
                                self.alerted = True
                                
                                item.setBackground(QBrush(QColor('#FAC')))
                                
                                self.alertSignal.emit(sound, volume)

                
                elif self.dbi.ifTSType(cols[c][1]):
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

        for i in adhocDatabars:
            self.databarAdd(i)

        if self.databarCols:
            self.dataBarRenew()

                        
    def dblClick(self, i, j):
    
        if self.dbi.ifLOBType(self.cols[j][1]):
            if self.detached:
                self.log('warning: LOB resultset already detached', True)
                
                if self.dbi.ifBLOBType(self.cols[j][1]):
                    blob = str(self.rows[i][j].encode())
                else:
                    blob = str(self.rows[i][j])
            else:
                if self.rows[i][j] is not None:
                    try:
                        value = self.rows[i][j].read()
                    except Exception as e:
                        self.log('LOB read() error: %s' % str(e), True)
                        value = '<error1>'
                    
                    if self.dbi.ifBLOBType(self.cols[j][1]):
                        blob = str(value.decode("utf-8", errors="ignore"))
                    else:
                        blob = str(value)
                else:
                    blob = '<Null value>'

            if self.rows[i][j]:
                self.rows[i][j].seek(0) #rewind just in case
        else:
            blob = str(self.rows[i][j])

        lob = lobDialog.lobDialog(blob, self)
        
        lob.exec_()

        return False

    def zoomFont(self, mode, toSize=None):
        fnt = self.font()
        size = fnt.pointSizeF()

        if mode == '+':
            size += 1

        if mode == '-' and size > 1:
            size -= 1

        if mode in ['+', '-']:
            fnt.setPointSizeF(size)
            self.horizontalHeader().setFont(fnt);
            self.setFont(fnt)

            utils.cfgSet('result-fontSize', int(size))
            self.fontUpdateSignal.emit()

        if mode == '=':
            fnt.setPointSizeF(toSize)
            self.setFont(fnt)
            self.horizontalHeader().setFont(fnt);

    def cellClickedSig(self, row, column):
        modifiers = QApplication.keyboardModifiers()

        if modifiers == Qt.AltModifier:
            if row in self.highlightRows:
                self.highlightRows.remove(row)
            else:
                self.highlightRows.append(row)

        self.highlightRefresh()

    def wheelEvent (self, event):
    
        p = event.angleDelta()
        
        if p.y() < 0:
            mode = 1
        else:
            mode = -1
            
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.ShiftModifier:
            #x = 0 - self.pos().x() 
            x = self.horizontalScrollBar().value()
            
            step = self.horizontalScrollBar().singleStep() * 2 #pageStep()
            self.horizontalScrollBar().setValue(x + mode * step)
        elif modifiers == Qt.ControlModifier:
            p = event.angleDelta()

            if p.y() >0:
                self.zoomFont(mode='+')
            if p.y() <0:
                self.zoomFont(mode='-')
        else:
            super().wheelEvent(event)
