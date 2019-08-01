from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem

from PyQt5.QtCore import Qt

class sqlConsole(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        vbar = QVBoxLayout()
        hbar = QHBoxLayout()
        
        cons = QPlainTextEdit()
        table = QTableWidget()
        #splitOne = QSplitter(Qt.Horizontal)
        spliter = QSplitter(Qt.Vertical)
        logArea = QPlainTextEdit()
        
        spliter.addWidget(cons)
        spliter.addWidget(table)
        spliter.addWidget(logArea)
        
        spliter.setSizes([300, 200, 10])
        
        vbar.addWidget(spliter)
        
        self.setLayout(vbar)
        pass
        #console = QPlainTextEdit()