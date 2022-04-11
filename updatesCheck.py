from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from PyQt5.QtWidgets import (QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QLabel)
    
from PyQt5.QtGui import QPixmap, QIcon, QDesktopServices

from yaml import safe_load, YAMLError
from utils import log
from utils import resourcePath
from _constants import build_date, version

from PyQt5.QtCore import Qt, QUrl

from datetime import datetime

from PyQt5.QtCore import QTimer

updTimer = None
wnd = None
versionCheck = None
afterCheck = None # callback function

def gotResponse(QNetworkReply):

    global afterCheck

    try:
        status = QNetworkReply.attribute(QNetworkRequest.HttpStatusCodeAttribute);
    except Exception as e:
        log('[e] http/yaml error: %s' % str(e))
        return

    if status != 200:
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
        return
    
    if ver is None:
        log('Some kind of version check error')
        return
        
    if 'version' in ver and 'date' in ver:
        verStr = 'Last published version is %s, build %s.' % (ver['version'], ver['date'])
        log(verStr)

    if 'versionBeta' in ver and 'dateBeta' in ver:
        verStrBeta = 'Last <i>beta</i> is %s, %s.' % (ver['versionBeta'], ver['dateBeta'])
        log(verStrBeta)
        
    #upd = updateDialog.Update(self)
    
    try:
        currentBuild = datetime.strptime(build_date, '%Y-%m-%d %H:%M:%S')
        currentBuild = currentBuild.strftime('%Y-%m-%d')
    except:
        log('[W] Cannot convert build_date to datetime: %s' % build_date, 2)
        currentBuild = ''
    
    try:
        buildDateDT = ver['date']
        buildDate = buildDateDT.strftime('%Y-%m-%d')
    except:
        buildDate = str(ver['date'])

    if versionCheck:
        if versionCheck < buildDate:
            log('Okay, there is a published build later than versionCheck: %s > %s' % (buildDate, versionCheck), 2)
        else:
            log('Skipping update dialog due to versionCheck value: %s, last build: %s' % (versionCheck, buildDate), 4)
            afterCheck('') # update the updateNextCheck date
            return
            
    else:
        if buildDate < currentBuild:
            log('There is no new version, current build %s, last published %s' % (currentBuild, buildDate), 4)
            
            afterCheck('') # update the updateNextCheck date
            return
        else:
            log('There is a build newer than current one: %s > %s' % (buildDate, currentBuild), 4)
    
    upd = updateInfo(wnd)
    
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
    global afterCheck
    global wnd
    global updTimer
    
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
    
    manager.finished[QNetworkReply].connect(gotResponse)
    manager.get(QNetworkRequest(QUrl('https://www.rybafish.net/versionTest')))
    

class updateInfo(QDialog):

    def __init__(self, hwnd = None):
    
        super().__init__(hwnd)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.status = ''
        
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
        
    def initUI(self):

        iconPath = resourcePath('ico\\favicon.png')
        imgPath  = resourcePath('ico\\logo.png')

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
        hButtons = QHBoxLayout()
        
        hbox.addWidget(img)
        hbox.addWidget(QLabel('Seems a new version is available, we will check and return with update.'))

        vbox.addLayout(hbox)
        hButtons.addStretch(1)
        hButtons.addWidget(okButton)
        hButtons.addWidget(ignoreButton)
        hButtons.addWidget(ignoreYearButton)
        vbox.addLayout(hButtons)
        
        self.setLayout(vbox)
        
        self.setWindowIcon(QIcon(iconPath))
        
        self.setWindowTitle('Version update')
