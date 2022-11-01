from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QSslCertificate

from PyQt5.QtWidgets import (QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QLabel)
    
from PyQt5.QtGui import QPixmap, QIcon, QDesktopServices

from yaml import safe_load, YAMLError
from utils import log as ulog
from utils import resourcePath
from _constants import build_date, version, isbeta, platform

from PyQt5.QtCore import Qt, QUrl

from datetime import datetime

from PyQt5.QtCore import QTimer
from urllib.parse import urlparse

from utils import cfg

updTimer = None
wnd = None
versionCheck = None
afterCheck = None # callback function
global_domain = None

def log(s, p = 3):
    ulog('[UPD] ' + s, p)

def gotResponse(QNetworkReply):
    '''
        Network callback functions
        
        Parses the yaml response, triggers UI dialog when required.
    '''
    
    global afterCheck
    stopFlag = None
    
    er = QNetworkReply.error()
    
    if er != QNetworkReply.NoError:
        log('[E] Network error code: ' + str(er), 2)
        log('[E] Network error string: ' + QNetworkReply.errorString(), 2)
        afterCheck('')
        
        stopFlag = True # in order to elaborate the SSL status
        #return

    if not cfg('ignoreSSLValidation', False):
        sslConf = QNetworkReply.sslConfiguration()
        
        sslConf.setCaCertificates([])
        certs = sslConf.peerCertificateChain()
        
        domain = urlparse(global_domain).netloc
        sslErrorsList = QSslCertificate.verify(certs, domain)
        
        if sslErrorsList:
            ll = 1
        else:
            ll = 4

        if cfg('loglevel', 3) >=4 or sslErrorsList:
            for i in range(len(certs)-1, -1, -1):
                l = certs[i]
                log('-', ll)
                log(f"    Issuer O: {l.issuerInfo(0)}, OU: {l.issuerInfo(3)}, DisplayName: {l.issuerDisplayName()}", ll)
                log(f"    Subject {l.subjectInfo(b'CN')} ({l.subjectInfo(b'O')}), SN: {l.serialNumber()}", ll)
                log(f"    Validity {l.effectiveDate().toString('yyyy-MM-dd HH:mm:ss')} - {l.expiryDate().toString('yyyy-MM-dd HH:mm:ss')}", ll)
            
        if sslErrorsList:
            for e in sslErrorsList:
                log(f'[E]: {e.error()}: {e.errorString()}', 1)
                
            log('[E] Aborting due to SSL issues', 2)
            stopFlag = True
            
        else:
            log('No SSL errors detected.', 4)

    if stopFlag:
        return

    status = None
    
    try:
        status = QNetworkReply.attribute(QNetworkRequest.HttpStatusCodeAttribute);
        log('Got update response, status: %s' % str(status), 2)
    except Exception as e:
        log('[E] http/yaml error: %s' % str(e), 2)
        
        afterCheck('') # update the updateNextCheck date
        
        return
        
    if status != 200:
        try:
            for h in (QNetworkReply.rawHeaderList()):
                log('[w] %s: %s' % (str(h, 'utf-8'), str(QNetworkReply.rawHeader(h), 'utf-8')))
        except Exception as e:
            log('[e]: %s' % str(e))
            
        afterCheck('') # update the updateNextCheck date
        log('[E] Response, status is not 200, aborting', 2)
            
        return
    
    try: 
        response = QNetworkReply.readAll()
        response = str(response, 'utf-8')
        ver = safe_load(response)
    except Exception as e:
        log('[e] http/yaml error: %s' % str(e))
        return
    
    if ver is None:
        log('Some kind of version check error', 2)
        return
        
    '''
    if 'version' in ver and 'date' in ver:
        verStr = 'Last published version is %s, build %s.' % (ver['version'], ver['date'])
        log(verStr)

    if 'versionBeta' in ver and 'dateBeta' in ver:
        verStrBeta = 'Last <i>beta</i> is %s, %s.' % (ver['versionBeta'], ver['dateBeta'])
        log(verStrBeta)
    '''
        
    #upd = updateDialog.Update(self)
    
    try:
        currentBuild = datetime.strptime(build_date, '%Y-%m-%d %H:%M:%S')
        currentBuild = currentBuild.strftime('%Y-%m-%d')
    except:
        log('[W] Cannot convert build_date to datetime: %s' % build_date, 2)
        currentBuild = ''
    
    message = ''
    
    for (k) in ver:
        log('ver: %s = %s' % (k, str(ver[k])), 5)
    
    if cfg('updatesCheckBeta', isbeta) and ver.get('versionBeta'):
        log('There is a beta version available...')
        lastVersion = ver.get('versionBeta')
        lastBuild = ver.get('dateBeta')
        message = ver.get('messageBeta')
        linkMessage = 'To download this version and review last changes please visit <a href="https://www.rybafish.net/">rybafish.net</a>.'
        
    else:
        lastVersion = ver.get('version')
        lastBuild = ver.get('date')
        message = ver.get('message')
        linkMessage = 'To download last BETA version and review last changes visit <a href="https://www.rybafish.net/changelog">rybafish.net</a>.'
            
    try:
        buildDateDT = lastBuild
        buildDate = buildDateDT.strftime('%Y-%m-%d')
        
    except:
        buildDate = str(lastVersion)

    if versionCheck:
        if versionCheck < buildDate:
            log('Okay, there is a published build later than versionCheck: %s > %s' % (buildDate, versionCheck), 2)
        else:
            log('Skipping update dialog due to versionCheck value: %s, last build: %s' % (versionCheck, buildDate), 4)
            afterCheck('') # update the updateNextCheck date
            return
            
    else:
        if buildDate <= currentBuild:
            log('There is no new version, current build %s, last published %s' % (currentBuild, buildDate), 4)
            
            afterCheck('') # update the updateNextCheck date
            return
        else:
            log('There is a build newer than current one: %s > %s' % (buildDate, currentBuild), 4)
    
    upd = updateInfo(wnd, lastVersion, buildDate, message, linkMessage)
    
    upd.exec_()
    
    afterCheck(upd.status, buildDateDT)

'''    
def updateTimer():
    log('Okay, it\'s time now...')
    
    updTimer.stop()

    manager = QNetworkAccessManager(wnd)
    
    manager.finished[QNetworkReply].connect(gotResponse)
    manager.get(QNetworkRequest(QUrl('https://www.rybafish.net/version')))
    
    log('Last version check request sent...')
'''
    
    
def checkUpdates(prnt, afterCheckCB, nextCheck, versionCheckIn):
    '''
        Main function to be called from outside main thread.
        
        afterCheckCB - this is the call back function to be passed for results processing
        
        nextCheck - date of the next check
        versionCheckIn - version must be later than this value (if it was previously selected to ignore certain upgrade)
        two last parameters are datetime.
    '''
    global afterCheck
    global wnd
    global updTimer
    global global_domain
    
    global versionCheck
    
    wnd = prnt
    
    today = datetime.today().date().strftime('%Y-%m-%d')
    
    log('checkUpdates, nextCheck: %s, versionCheckIn: %s' % (str(nextCheck), str(versionCheckIn)), 5)
    
    if nextCheck:
        try:
            nextCheck = nextCheck.strftime('%Y-%m-%d')
        except:
            log('[W] cannot treat %s as date. Maybe check your layout.yaml?' % (str(nextCheck)), 2)
            nextCheck = str(nextCheck)
            
        if nextCheck < today:
            log('Okay, we need a version check due to nextCheck value (%s), triggering the request...' % str(nextCheck), 2)
        else:
            log('Skipping update check due to nextCheck value: %s' % str(nextCheck), 4)
            return
            
    if versionCheckIn:
        try:
            versionCheck = versionCheckIn.strftime('%Y-%m-%d')
        except:
            log('[W] cannot treat %s as date. Maybe check your layout.yaml?' % (str(versionCheckIn)), 2)
            versionCheck = str(versionCheckIn)
        
    # trigger the request...
            
    afterCheck = afterCheckCB
    
    #updTimer = QTimer(wnd)
    #updTimer.timeout.connect(updateTimer)
    #updTimer.start(1000 * 10)
    
    manager = QNetworkAccessManager(wnd)
    
    updateURL = cfg('updatesURL', 'https://files.rybafish.net/version')
    manager.finished[QNetworkReply].connect(gotResponse)
    
    global_domain = updateURL
    
    request = QNetworkRequest(QUrl(updateURL))
    request.setRawHeader(b'User-Agent', f'RybaFish {version}/{platform}'.encode('utf-8'));
        
    manager.get(request)
    
    log('Update check request sent (%s)...' % updateURL, 4)
    

class updateInfo(QDialog):

    def __init__(self, hwnd, lastVer, lastBuildDate, msg, linkMsg):
    
        super().__init__(hwnd)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.status = ''
        self.lastVer = lastVer
        self.lastBuildDate = lastBuildDate
        self.msg = msg
        self.linkMsg = linkMsg
        
        self.initUI()

    def ignoreVersion(self):
        self.status = 'ignoreVersion'
        self.close()
        
    def ignoreYear(self):
        self.status = 'ignoreYear'
        self.close()
        
    def acceptBtn(self):
        self.status = 'ignoreWeek'
        self.close()
        
    def rybafishDotNet(self, link):
        QDesktopServices.openUrl(QUrl(link))

    def initUI(self):

        iconPath = resourcePath('ico', 'favicon.png')
        imgPath  = resourcePath('ico', 'logo.png')

        okButton = QPushButton('Remind me next week')
        okButton.clicked.connect(self.acceptBtn)
        
        ignoreButton = QPushButton('Ignore this update')
        ignoreButton.clicked.connect(self.ignoreVersion)
        
        ignoreYearButton = QPushButton('Ignore updates for 1 year')
        ignoreYearButton.clicked.connect(self.ignoreYear)

        img = QLabel()
        img.setPixmap(QPixmap(imgPath))
        img.setToolTip('You are more than the sum of what you consume.')
        
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        msgBox = QVBoxLayout()
        hButtons = QHBoxLayout()
        
        
        try:
            currentBuild = datetime.strptime(build_date, '%Y-%m-%d %H:%M:%S')
            currentBuild = currentBuild.strftime('%Y-%m-%d')
        except:
            currentBuild = '???'

        verStr = 'Installed version: %s, %s<br/>Last avaible version: %s, %s.' % (version, currentBuild, self.lastVer, self.lastBuildDate)        

        if self.linkMsg:
            updateStr = self.linkMsg
        else:
            updateStr = 'To download last version and review last changes please visit rybafish.net.'

        log(updateStr)
        
        msgBox.addWidget(QLabel(verStr))
        
        msg = self.msg
        msgBox.addWidget(QLabel(msg))
        
        msgBox.addStretch(2)
        
        updateLabel = QLabel(updateStr)
        updateLabel.linkActivated.connect(self.rybafishDotNet)
        
        msgBox.addWidget(updateLabel)
        
        msgBox.addStretch(1)
        
        hbox.addWidget(img)
        hbox.addLayout(msgBox)
        

        vbox.addLayout(hbox)
        hButtons.addStretch(1)
        hButtons.addWidget(okButton)
        hButtons.addWidget(ignoreButton)
        hButtons.addWidget(ignoreYearButton)
        vbox.addLayout(hButtons)
        
        self.setLayout(vbox)
        
        self.setWindowIcon(QIcon(iconPath))
        
        self.setWindowTitle('Version update notification')
