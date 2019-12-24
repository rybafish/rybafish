import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox, QPlainTextEdit,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel)


from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from PyQt5.QtGui import QPixmap, QIcon, QDesktopServices

from PyQt5.QtCore import Qt, QUrl

from utils import resourcePath
from yaml import safe_load, YAMLError

from utils import log

from _constants import build_date, version

class lobDialog(QDialog):

    def __init__(self, lob):
    
        #QtGui.QDialog(None, QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint)
        #super().__init__(None, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        super().__init__()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.initUI(lob)
        
    def initUI(self, lob):

        iconPath = resourcePath('ico\\favicon.ico')
        
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok,
            Qt.Horizontal,
            self)

        self.buttons.accepted.connect(self.accept)
        
        vbox = QVBoxLayout()
        
        te = QPlainTextEdit()


        ls = len(lob)
        
        lobsize = 'Length: %i' % ls
        
        if ls == 65536:
            lobsize += ' <truncated?>'
            
        te.setPlainText(lob)
        
        vbox.addWidget(te)
        
        txt = QLabel(lobsize)
        
        vbox.addWidget(txt)
        vbox.addWidget(self.buttons)
        
        self.setLayout(vbox)
        
        self.setWindowIcon(QIcon(iconPath))

        
        self.setGeometry(300, 400, 700, 400)
        self.setWindowTitle('LOB value')
        #self.show()
        
        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    ab = About()
    ab.exec_()
    sys.exit(app.exec_())