from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem, QApplication

from PyQt5.QtCore import Qt

import time

import db

import utils

from utils import dbException

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
    
    def __init__(self, config):
        super().__init__()
        self.initUI()
        
        try: 
            self.conn = db.create_connection(config)
        except dbException as e:
            raise e
            
    def csvRow(self, table, r):
        
        values = []
        
        for i in range(table.columnCount()):
            values.append(table.item(r, i).text())
            
        return ';'.join(values)


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
            
            for r in range(len(rows)):
            
                if r == 1:
                    self.result.resizeColumnsToContents();
                    
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
        
    def initUI(self):
        vbar = QVBoxLayout()
        hbar = QHBoxLayout()
        
        self.cons = QPlainTextEdit()
        self.result = QTableWidget()
        self.result.setWordWrap(False)
        self.result.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: lightgray }")
        #self.result = QPlainTextEdit()
        #splitOne = QSplitter(Qt.Horizontal)
        spliter = QSplitter(Qt.Vertical)
        self.log = QPlainTextEdit()
        
        self.cons.keyPressEvent = self.consKeyPressHandler
        
        self.result.keyPressEvent = self.resultKeyPressHandler
        
        self.cons.setPlainText('select * from m_load_history_info')
        
        spliter.addWidget(self.cons)
        spliter.addWidget(self.result)
        spliter.addWidget(self.log)
        
        spliter.setSizes([300, 200, 10])
        
        vbar.addWidget(spliter)
        
        self.setLayout(vbar)
        pass
        #console = QPlainTextEdit()