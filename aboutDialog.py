import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel)


from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from PyQt5.QtGui import QPixmap, QIcon

from PyQt5.QtCore import Qt, QUrl

from utils import resourcePath
from yaml import safe_load, YAMLError

from utils import log

from _constants import build_date, version

class About(QDialog):

    def __init__(self):
    
        #QtGui.QDialog(None, QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint)
        #super().__init__(None, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        super().__init__()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.initUI()
        
        
    def gotResponse(self, QNetworkReply):
        print('check for http 200 here')
        #print(QNetworkReply.rawHeaderList())
        #print(QNetworkReply.rawHeader(b'Location'))
        
        try: 
            response = QNetworkReply.readAll()
            response = str(response, 'utf-8')
            ver = safe_load(response)
        except Exception as e:
            log('[e] http/yaml error: %s' % str(e))
            self.updatesLabel.setText('error')
            return
        
        if 'version' in ver and 'date' in ver:
            verStr = 'Last published version is %s, from %s.' % (ver['version'], ver['date'])
            self.updatesLabel.setText(verStr)
        
        
    def checkUpdates(self):
        #self.updatesLabel.setText('Not implemented yet, please check <a href="http://rybafish.net">http://rybafish.net</a> for updates')
        
        manager = QNetworkAccessManager(self)
        
        manager.finished[QNetworkReply].connect(self.gotResponse)
        manager.get(QNetworkRequest(QUrl('http://www.rybafish.net/version')))
        
        self.updatesLabel.setText('requesting...')
        
    def initUI(self):

        iconPath = resourcePath('ico\\favicon.ico')
        imgPath  = resourcePath('ico\\logo.png')
        
        checkButton = QPushButton("Check for updates")
        
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok,
            Qt.Horizontal,
            self)

        self.buttons.accepted.connect(self.accept)

        img = QLabel()
        img.setPixmap(QPixmap(imgPath))
        
        self.updatesLabel = QLabel()
        #self.updatesLabel.setText('To report bugs or check for updates please visit <a href="http://rybafish.net">http://rybafish.net</a>.')

        self.infoLabel = QLabel()
        self.infoLabel.setText('''To report bugs or check for updates please visit <a href="http://rybafish.net">http://rybafish.net</a>.''')
        
        txt = QLabel('''Ryba Fish Charts.

Version %s, Build %s.
''' % (version, build_date))

        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        vbox2 = QVBoxLayout()
        
        vbox2.addStretch(1)
        vbox2.addWidget(txt)
        vbox2.addWidget(checkButton)
        vbox2.addWidget(self.updatesLabel)
        vbox2.addWidget(QLabel())
        vbox2.addWidget(self.infoLabel)
        vbox2.addStretch(1)
        
        hbox.addWidget(img)
        hbox.addLayout(vbox2)
        vbox.addLayout(hbox)

        vbox.addWidget(self.buttons)
        checkButton.clicked.connect(self.checkUpdates)
        checkButton.resize(150, 150)
        
        self.setLayout(vbox)
        
        self.setWindowIcon(QIcon(iconPath))
        
        #self.setGeometry(300, 300, 300, 150)
        self.setWindowTitle('About')
        #self.show()
        
        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    ab = About()
    ab.exec_()
    sys.exit(app.exec_())