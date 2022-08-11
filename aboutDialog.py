import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel)


from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from PyQt5.QtGui import QPixmap, QIcon, QDesktopServices

from PyQt5.QtCore import Qt, QUrl

from utils import resourcePath
from yaml import safe_load, YAMLError

from utils import log, cfg

from _constants import build_date, version

class About(QDialog):

    def __init__(self, hwnd):
    
        #QtGui.QDialog(None, QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint)
        #super().__init__(None, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        super().__init__(hwnd)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.initUI()
        
        
    def gotResponse(self, QNetworkReply):

        try:
            status = QNetworkReply.attribute(QNetworkRequest.HttpStatusCodeAttribute);
        except Exception as e:
            log('[e] http/yaml error: %s' % str(e))
            self.updatesLabel.setText('Error')
            return

        if status != 200:
            self.updatesLabel.setText('Network error: ' + str(status))
            
            try:
                for h in (QNetworkReply.rawHeaderList()):
                    log('[w] %s: %s' % (str(h, 'utf-8'), str(QNetworkReply.rawHeader(h), 'utf-8')))
            except Exception as e:
                log('[e]: %s' % str(e))
                
            return
        
        try: 
            response = QNetworkReply.readAll()
            response = str(response, 'utf-8')
            ver = safe_load(response)
        except Exception as e:
            log('[e] http/yaml error: %s' % str(e))
            self.updatesLabel.setText('error')
            return
        
        if ver is None:
            self.updatesLabel.setText('<network error>')
            return
            
        if 'version' in ver and 'date' in ver:
            verStr = 'Last published version is %s, build %s.' % (ver['version'], ver['date'])
            self.updatesLabel.setText(verStr)

        if 'versionBeta' in ver and 'dateBeta' in ver:
            verStrBeta = 'Last <i>beta</i> is %s, %s.' % (ver['versionBeta'], ver['dateBeta'])
            self.updatesLabelBeta.setText(verStrBeta)
        
        
    def checkUpdates(self):
        manager = QNetworkAccessManager(self)
        
        manager.finished[QNetworkReply].connect(self.gotResponse)
        updateURL = cfg('updatesURL', 'https://files.rybafish.net/version')
        manager.get(QNetworkRequest(QUrl(updateURL)))
        
        self.updatesLabel.setText('requesting...')
        self.updatesLabelBeta.setText('')
        
    def rybafishDotNet(self, link):
        QDesktopServices.openUrl(QUrl(link))
        
    def initUI(self):

        iconPath = resourcePath('ico', 'favicon.png')
        imgPath  = resourcePath('ico', 'logo.png')
        
        checkButton = QPushButton("Check for updates")
        
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok,
            Qt.Horizontal,
            self)

        self.buttons.accepted.connect(self.accept)

        img = QLabel()
        img.setPixmap(QPixmap(imgPath))
        img.setToolTip('You are more than the sum of what you consume.')
        
        self.updatesLabel = QLabel()
        self.updatesLabelBeta = QLabel()
        
        #self.updatesLabel.setText('To report bugs or check for updates please visit <a href="https://www.rybafish.net">https://rybafish.net</a>.')

        self.infoLabel = QLabel()
        self.infoLabel.linkActivated.connect(self.rybafishDotNet)
        self.infoLabel.setText('''To report bugs or check for updates please visit <a href="https://www.rybafish.net">rybafish.net</a>.''')
        
        txt = QLabel('''Ryba Fish Charts.

Current version: %s, build %s.
''' % (version, build_date))

        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        vbox2 = QVBoxLayout()
        
        vbox2.addStretch(1)
        vbox2.addWidget(txt)
        vbox2.addWidget(checkButton)
        vbox2.addWidget(self.updatesLabel)
        vbox2.addWidget(self.updatesLabelBeta)
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