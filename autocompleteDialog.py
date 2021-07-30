import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel, QListWidget)
    
from PyQt5.QtGui import QPixmap, QIcon

from PyQt5.QtCore import Qt

from utils import resourcePath

from utils import log, cfg

class autocompleteDialog(QDialog):
    
    def __init__(self, parent, lines):
        
        self.lines = lines
        
        super(autocompleteDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        self.initUI()
        
        self.linesList.setFocus()
        
    @staticmethod
    def getLine(parent, lines):
    
        ac = autocompleteDialog(parent, lines)
        result = ac.exec_()
        
        line = ac.linesList.currentItem().text()
        
        return (line, result == QDialog.Accepted)

    def itemOk(self):
        self.accept()
        
    def initUI(self):

        iconPath = resourcePath('ico\\favicon.ico')
        
        self.linesList = QListWidget()
        
        for l in self.lines:
            self.linesList.addItem(l)
            
        self.linesList.setCurrentRow(0)
        self.linesList.setFocus()
        
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        vbox = QVBoxLayout()
        
        vbox.addWidget(self.linesList)

        self.linesList.itemDoubleClicked.connect(self.itemOk)
        #vbox.addStretch(1)
        
        vbox.addWidget(self.buttons)
        
        self.setWindowIcon(QIcon(iconPath))
        
        self.setLayout(vbox)
        
        self.resize(500, 300)
        
        self.setWindowTitle('Auto-complete options')
