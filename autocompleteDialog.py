import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel, QListWidget)
    
from PyQt5.QtGui import QPixmap, QIcon

from PyQt5.QtCore import Qt

from PyQt5.QtCore import pyqtSignal

from utils import resourcePath

from utils import log, cfg

class QListWidgetMod(QListWidget):

    #filterUpdated = pyqtSignal(['QString'])
    filterUpdated = pyqtSignal()

    def __init__(self):
        self.filter = ''
        super().__init__()

    def keyPressEvent(self, event):
    
        k = event.text()

        if k.isalnum() or k == '_':
            self.filter += k
            self.filterUpdated.emit()
        elif event.key() == Qt.Key_Backspace:
            self.filter = self.filter[:-1]
            self.filterUpdated.emit()
        else:
            super().keyPressEvent(event)
        
        
    
class autocompleteDialog(QDialog):
    
    def __init__(self, parent, lines):
        
        
        self.linesAll = lines
        self.lines = lines.copy()
        
        self.filterLabel = None
        
        super(autocompleteDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        self.initUI()
        
        self.linesList.setFocus()
        
    @staticmethod
    def getLine(parent, lines):
    
        ac = autocompleteDialog(parent, lines)
        result = ac.exec_()
        
        if ac.linesList.currentItem():
            line = ac.linesList.currentItem().text()
        else:
            line = '??'
        
        return (line, result == QDialog.Accepted)

    def updateFilter(self):
        self.filterLabel.setText(self.linesList.filter)
        
        self.lines.clear()
        
        for l in self.linesAll:
            if l.lower().find(self.linesList.filter.lower()) >= 0:
                self.lines.append(l)
                
        self.updateList()
                
    def updateList(self):
        self.linesList.clear()
    
        for l in self.lines:
            self.linesList.addItem(l)
            
        self.linesList.setCurrentRow(0)
        self.linesList.update()
    
    def itemOk(self):
        self.accept()
        
    def initUI(self):

        iconPath = resourcePath('ico\\favicon.ico')
        
        self.linesList = QListWidgetMod()

        self.updateList()
            
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
        
        self.filterLabel = QLabel('Start typing to filter...')
        
        self.linesList.filterUpdated.connect(self.updateFilter)
        
        vbox.addWidget(self.filterLabel)
        
        vbox.addWidget(self.buttons)
        
        self.setWindowIcon(QIcon(iconPath))
        
        self.setLayout(vbox)
        
        self.resize(500, 300)
        
        self.setWindowTitle('Auto-complete options')
