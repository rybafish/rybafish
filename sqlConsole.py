from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem, QApplication, QAbstractItemView

from PyQt5.QtGui import QTextCursor, QColor

from PyQt5.QtCore import Qt

import time

import db

import utils

from utils import dbException, log

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
    
    config = None
    
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
            
    def csvRow(self, table, r):
        
        values = []
        
        for i in range(table.columnCount()):
            values.append(table.item(r, i).text())
            
        return ';'.join(values)


    def consSelection(self):
        return
        cursor = self.cons.textCursor()
        
        selected = cursor.selectedText()
        
        if len(selected) >0 :
            print('processSelection: [%s]' % selected)
        
        # https://stackoverflow.com/questions/27716625/qtextedit-change-font-of-individual-paragraph-block
        # https://stackoverflow.com/questions/1849558/how-do-i-use-qtextblock
        # cursor.setPosition(0)
                
        cursor = QTextCursor(self.cons.document())

        cursor.setPosition(0,QTextCursor.MoveAnchor);
        cursor.setPosition(6,QTextCursor.KeepAnchor);
        
        format = cursor.charFormat()
        
        format.setBackground(QColor('#0E0'));
        cursor.setCharFormat(format);
                
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
                        csv = self.result.item(c.row(), c.column()).text()
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
            
            try:
                t0 = time.time()
                rows, cols = db.execute_query_desc(self.conn, txt, [])
                
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
            
            print('[headers]')
            for c in cols:
                row0.append(c[0])
                print(c)
               
            self.headers = row0.copy()
               
            self.result.setColumnCount(len(row0))
            self.result.setRowCount(0)
            self.result.setHorizontalHeaderLabels(row0)
            self.result.resizeColumnsToContents();
            
            self.result.setRowCount(len(rows))
            
            adjRow = 5 if len(rows) >=5 else len(rows)
            
            print (adjRow)
            
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
            
            '''
            # csv approach
            
            res = ';'.join(row0) + '\n'
            
            for row in rows:
                rowI = []
                for val in row:
                    rowI.append(str(val))
                    
                res += ';'.join(rowI) + '\n'
                
            self.result.setPlainText(res)
            '''
            
        else:
            QPlainTextEdit.keyPressEvent(self.cons, event)
            self.consSelection()
        
    def initUI(self):
        vbar = QVBoxLayout()
        hbar = QHBoxLayout()
        
        #self.cons = QPlainTextEdit()
        self.cons = QPlainTextEdit()
        self.result = QTableWidget()
        self.result.setWordWrap(False)
        self.result.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: lightgray }")
        #self.result = QPlainTextEdit()
        #splitOne = QSplitter(Qt.Horizontal)
        spliter = QSplitter(Qt.Vertical)
        self.log = QPlainTextEdit()
        
        self.cons.keyPressEvent = self.consKeyPressHandler
        self.cons.selectionChanged = self.consSelection #does not work
        
        self.result.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
                
        self.cons.setPlainText('select * from m_load_history_info')
        
        spliter.addWidget(self.cons)
        spliter.addWidget(self.result)
        spliter.addWidget(self.log)
        
        spliter.setSizes([300, 200, 10])
        
        vbar.addWidget(spliter)
        
        self.setLayout(vbar)
        pass
        #console = QPlainTextEdit()