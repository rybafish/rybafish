from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem

from PyQt5.QtCore import Qt

import time

import db
from utils import dbException

class sqlConsole(QWidget):
    conn = None
    
    def __init__(self, config):
        super().__init__()
        self.initUI()
        
        try: 
            self.conn = db.create_connection(config)
        except dbException as e:
            raise e
            
    def keyPressHandler(self, event):
        
        if event.key() == Qt.Key_F8:
            txt = self.cons.toPlainText()
            
            try:
                t0 = time.time()
                rows, cols = db.execute_query_desc(self.conn, txt, [])
                t1 = time.time()
                
                logText = 'Query execution time: %s s\n' % (str(round(t1-t0, 3)))
                logText += str(len(rows)) + ' rows fetched'
                self.log.setPlainText(logText)
            except dbException as e:
                err = str(e)
                self.log.setPlainText('DB Exception:' + err)
                return

            row0 = []
            for c in cols:
                row0.append(c[0])
                
            res = ';'.join(row0) + '\n'
            
            for row in rows:
                rowI = []
                for val in row:
                    rowI.append(str(val))
                    
                res += ';'.join(rowI) + '\n'
                
            self.result.setPlainText(res)
            
        else:
            QPlainTextEdit.keyPressEvent(self.cons, event)
        
    def initUI(self):
        vbar = QVBoxLayout()
        hbar = QHBoxLayout()
        
        self.cons = QPlainTextEdit()
        #self.result = QTableWidget()
        self.result = QPlainTextEdit()
        #splitOne = QSplitter(Qt.Horizontal)
        spliter = QSplitter(Qt.Vertical)
        self.log = QPlainTextEdit()
        
        self.cons.keyPressEvent = self.keyPressHandler
        
        self.cons.setPlainText('select * from m_load_history_info')
        
        spliter.addWidget(self.cons)
        spliter.addWidget(self.result)
        spliter.addWidget(self.log)
        
        spliter.setSizes([300, 200, 10])
        
        vbar.addWidget(spliter)
        
        self.setLayout(vbar)
        pass
        #console = QPlainTextEdit()