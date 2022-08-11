import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox, QPlainTextEdit,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel)

from PyQt5.QtGui import QIcon, QDesktopServices

from PyQt5.QtCore import Qt

from utils import resourcePath

from utils import log

from PyQt5.QtCore import pyqtSignal

class searchDialog(QDialog):

    findSignal = pyqtSignal(['QString'])
    
    def __init__(self, lastSearch = None):
    
        super().__init__()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.initUI(lastSearch)
        
    def search(self):
        
        str = self.str.text()
        
        self.findSignal.emit(str)
        
    def cancel(self):
        pass
        
    def initUI(self, lastSearch):

        iconPath = resourcePath('ico', 'favicon.png')

        self.setWindowIcon(QIcon(iconPath))
        
        self.str = QLineEdit(lastSearch)
        
        if lastSearch != '':
            self.str.selectAll()
        
        vbox = QHBoxLayout()
        
        searchBtn = QPushButton('Find')
        
        searchBtn.clicked.connect(self.search)
        
        #cancelBtn = QPushButton('Close')

        #vbox.addWidget(findLabel)
        vbox.addWidget(self.str)

        vbox.addStretch(1)
        
        vbox.addWidget(searchBtn)
        #vbox.addWidget(cancelBtn)
        
        self.setLayout(vbox)
        
        self.setWindowTitle('Find string...')
        #self.show()
        
        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    ab = About()
    ab.exec_()
    sys.exit(app.exec_())