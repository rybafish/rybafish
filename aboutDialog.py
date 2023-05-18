import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel)


from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QSslCertificate

from PyQt5.QtGui import QPixmap, QIcon, QDesktopServices

from PyQt5.QtCore import Qt, QUrl

from utils import resourcePath
from yaml import safe_load, YAMLError

from urllib.parse import urlparse

from utils import log, cfg

from _constants import build_date, version, platform

class About(QDialog):

    def __init__(self, hwnd):
    
        #QtGui.QDialog(None, QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint)
        #super().__init__(None, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        super().__init__(hwnd)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.initUI()
        
        
    def gotResponse(self, QNetworkReply):
    
        def logChain(certs, loglevel):
            for i in range(len(certs)-1, -1, -1):
                l = certs[i]
                log('-', loglevel)
                log(f"    Issuer O: {l.issuerInfo(0)}, OU: {l.issuerInfo(3)}, DisplayName: {l.issuerDisplayName()}", loglevel)
                log(f"    Subject {l.subjectInfo(b'CN')} ({l.subjectInfo(b'O')}), SN: {l.serialNumber()}", loglevel)
                log(f"    Validity {l.effectiveDate().toString('yyyy-MM-dd HH:mm:ss')} - {l.expiryDate().toString('yyyy-MM-dd HH:mm:ss')}", loglevel)
    
        stopFlag = None
    
        er = QNetworkReply.error()
        
        if er != QNetworkReply.NoError:
            log('[E] Network error code: ' + str(er), 2)
            log('[E] Network error string: ' + QNetworkReply.errorString(), 2)
            self.updatesLabel.setText('Network error: ' + QNetworkReply.errorString())
            
            stopFlag = True
            #return stop flag instead

        if not cfg('ignoreSSLValidation', False)        :
            sslConf = QNetworkReply.sslConfiguration()
            
            sslConf.setCaCertificates([])
            certs = sslConf.peerCertificateChain()
            
            domain = urlparse(self.url).netloc
            sslErrorsList = QSslCertificate.verify(certs, domain)
            
            if cfg('loglevel', 3) >=4 or sslErrorsList:
                if sslErrorsList:
                    logChain(certs, 1)  # report chain in case of errors despite the configured loglevel
                else:
                    logChain(certs, 4)  
                
            if sslErrorsList:
                sslErrorsStr = ''                
                for e in sslErrorsList:
                    log(f'[E]: {e.error()}: {e.errorString()}', 1)
                    sslErrorsStr += '\n' + e.errorString()
                    
                log('[W] Aborting due to SSL issues', 2)
                
                if stopFlag is None or er == 6:
                    self.updatesLabel.setText('SSL error, check rybafish.log file for the details.' + '\n' + sslErrorsStr)
                    
                stopFlag = True
            else:
                log('No SSL errors detected.', 4)

        if stopFlag:
            return

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
        
        self.url = updateURL

        request = QNetworkRequest(QUrl(updateURL))
        request.setRawHeader(b'User-Agent', f'RybaFish {version}/{platform} @'.encode('utf-8'));
        manager.get(request)
        log(f'Requesting {updateURL}', 4)
        
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
