import sys, os
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel, QCheckBox, QComboBox, QFrame, QGroupBox, QSplitter)
    
from PyQt5.QtGui import QPixmap, QIcon

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QProcess

from utils import resourcePath

from utils import log, deb, cfg
from cfgManager import cfgManInst

from dbi import dbidict

unsavedChanges = None

class Config(QDialog):

    # config = {}, face palm, 2023-08-12, face palm
    
    def setConf(self, conf):
        try:
            dbi = conf.get('dbi')

            if conf:
                if dbi == 'SLT':
                    hostport = conf['host']
                else:
                    hostport = conf['host'] + ':' + str(conf['port'])
                
                self.hostportEdit.setText(hostport)
                self.userEdit.setText(conf['user'])
                # self.pwdEdit.setText(conf['password'])
                
                decodedPwd = cfgManInst.decode(conf['password'])

                if decodedPwd:
                    self.pwdEdit.setText(decodedPwd)
                else:
                    if conf['password']:
                        self.reportError('Password cannot be decrypted, check Master Key')
                        self.pwdEdit.setText('')

                if 'ssl' in conf:
                    self.sslCB.setChecked(conf['ssl'])

                if dbi:
                    for i in range(self.driverCB.count()):
                        if dbidict[self.driverCB.itemText(i)] == dbi:
                            if dbi != 'HDB':
                                self.driverCB.setCurrentIndex(i)
                                break

                            if conf.get('auth') and self.driverCB.itemText(i) == 'HANA Cloud':
                                self.driverCB.setCurrentIndex(i)
                                break

                            if not conf.get('auth') and self.driverCB.itemText(i) == 'HANA DB':
                                self.driverCB.setCurrentIndex(i)
                                break

                if 'readonly' in conf:
                    self.readOnly.setChecked(conf['readonly'])
                else:
                    self.readOnly.setChecked(False)
                
            else:
                self.hostportEdit.setFocus()
        except Exception as e:
            log(f'[!] setConf exception: {e}', 2)

    
    def __init__(self, conf, parent = None):
        #super().__init__(parent)
        
        super(Config, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);

        self.auth = None
        self.prcPwdRequest = None
        
        # self.cfgManager = cfgManager(cfg('connectionsFile', None))
        self.initUI()
        
        self.conf = conf
        self.config = {}
        
        name = conf.get('setToName')
        
        if not name:
            name = conf.get('name')
        
        if name:
            self.setConfName(name)
            conf['name'] = name
            # change the config based on cfgManager

        if (conf and (conf.get('name') == name)) and not conf.get('setToName'):
            # old style configuration PLUS manually changed (saved for runtime only) config
            self.setConf(conf)
                
    def setConfName(self, name):
        '''
            set values from the configuration based on conf name
            conf name must exist in the list of connections and
            values are going to be implicitly filled by this index
        '''
        if not name:
            return False
            
        for i in range(self.confCB.count()):
            if name == self.confCB.itemText(i):
                self.confCB.setCurrentIndex(i)
                return True
                
        return False
    
    @staticmethod
    def getConfig(config, parent=None):
    
        cf = Config(config, parent)
        result = cf.exec_()
        
        hostport = cf.hostportEdit.text()
        
        dbi = dbidict[cf.driverCB.currentText()]

        # cf.config = {}

        if dbi == 'SLT':
            filename = hostport
            if os.path.exists(filename) or True: # check for the db existance switched off...
                cf.config['ok'] = True
                cf.config['port'] = ''
                cf.config['host'] = hostport
            else:
                log(f'File does not exist: {filename}', 2)
                cf.config['error'] = f'Cannot start the connection.\nFile does not exist: {filename}'
                cf.config['ok'] = False
        else:
            try:
            
                if dbi == 'SLT':
                    host = hostport
                    port = ''
                else:
                    host, port = hostport.split(':')
            
                port = int(port)

                cf.config['ok'] = True
                cf.config['host'] = host
                cf.config['port'] = port
                
            #ValueError
            except Exception as e:
                log(f'getConfig exception {type(e)}')
                log(f'getConfig exception {e}')
                cf.hostportEdit.setStyleSheet("color: red;")
                cf.config['ok'] = False
                cf.config['port'] = ''
                cf.config['host'] = hostport
                cf.config['error'] = f'Connection exception: {type(e)}\n{e}'

        cf.config['name'] = cf.confCB.currentText()
        cf.config['dbi'] = dbidict[cf.driverCB.currentText()]
        
        cf.config['user'] = cf.userEdit.text()
        cf.config['password'] = cfgManInst.encode(cf.pwdEdit.text().strip())
        
        cf.config['noreload'] = cf.noReload.isChecked()
        cf.config['ssl'] = cf.sslCB.isChecked()

        cf.config['auth'] = cf.auth
        
        if cf.config['dbi'] == 'SLT':
            cf.config['readonly'] = cf.readOnly.isChecked()
        
        return (cf.config, result == QDialog.Accepted)
        
    def driverChanged(self, index):
    
        drv = self.driverCB.currentText()
        
        self.auth = cfg('hanaAuth')

        if drv == 'ABAP Proxy' or drv == 'SQLite DB':
            self.userEdit.setDisabled(True)
            self.pwdEdit.setDisabled(True)
            self.sslCB.setDisabled(True)
        elif drv == 'HANA DB':
            self.userEdit.setEnabled(True)
            self.pwdEdit.setEnabled(True)
            self.sslCB.setEnabled(True)
        elif drv == 'HANA Cloud':
            self.userEdit.setEnabled(True)
            self.pwdEdit.setEnabled(True)
            self.sslCB.setEnabled(False)
            self.sslCB.setChecked(True)
            self.auth = 'pbkdf2'
            
        if drv == 'SQLite DB':
            self.readOnly.setEnabled(True)
            self.hostportLabel.setText('DB File:')
        else:
            self.hostportLabel.setText('hostname:port')
            self.readOnly.setEnabled(False)
            
        self.configurationChanged(self.confCB.currentText())

        self.update()

    def confChange(self, i):
    
        def parseHost(hostport):
            dbi = c.get('dbi')

            try:
                if dbi == 'SLT':
                    host = hostport
                    port = ''
                else:
                    host, port = hostport.split(':')
                    port = int(port)
                
                self.hostportEdit.setStyleSheet("color: black;")

            except:
                self.hostportEdit.setStyleSheet("color: red;")
                host = hostport
                port = None
                
            return host, port
        
        conf = {}
        
        name = self.confCB.currentText()
        
        if name != '':
            c = cfgManInst.configs[name]
            
            host, port = parseHost(c['hostport'])
            conf['dbi'] = c['dbi']
            conf['host'] = host
            conf['port'] = port
            conf['ssl'] = c.get('ssl')
            conf['auth'] = c.get('auth')
            
            if c.get('readonly'):
                conf['readonly'] = c.get('readonly')

            if 'user' in c:
                conf['user'] = c['user']
            else:
                conf['user'] = ''
                
            if 'pwd' in c:
                conf['password'] = c['pwd']
            else:
                conf['password'] = ''
                
            '''
            if 'ssl' in c:
                conf['ssl'] = c['ssl']
            else:
                pass
                #conf['ssl'] = 
            '''
            
        else:
            conf = self.conf
        
        self.reportError('')
        self.setConf(conf)
        self.setStatus('')
    
    def confSave(self):
        txt = self.confCB.currentText()
        
        global unsavedChanges
        
        if txt == '':
            self.setStatus('Please fill in the configuration name before saving.')
            return
        
        cfg = {}
        
        cfg['name'] = txt
        cfg['dbi'] = dbidict[self.driverCB.currentText()]
        cfg['user'] = self.userEdit.text()
        cfg['pwd'] = cfgManInst.encode(self.pwdEdit.text())
        cfg['hostport'] = self.hostportEdit.text()
        cfg['ssl'] = self.sslCB.isChecked()
        
        if cfg['dbi'] == 'SLT':
            cfg['readonly'] = self.readOnly.isChecked()
        
        if self.driverCB.currentText() == 'HANA Cloud':
            cfg['auth'] = self.auth
        else:
            cfg['auth'] = None

        items = []
        for i in range(self.confCB.count()):
            items.append(self.confCB.itemText(i))
            
        cfgManInst.updateConf(cfg)
        
        if txt not in items:
            self.confCB.addItem(txt)
            self.confCB.setCurrentIndex(self.confCB.count() - 1)
            self.setStatus('Configuration added.')
        else:
            self.setStatus('Configuration updated.')
            unsavedChanges = False

        self.reportError('')
                
    def reportError(self, txt):

        if txt:
            self.errorMessage.show()
            self.errorMessage.setStyleSheet("QLabel {color: blue;}");
            self.errorMessage.setText(txt)
        else:
            self.errorMessage.hide()
            self.errorMessage.setStyleSheet("QLabel {color: black;}");
            self.errorMessage.setText('')
    
    def confDel(self):
        name = self.confCB.currentText()
        i = self.confCB.currentIndex()
        self.confCB.removeItem(i)
        
        cfgManInst.removeConf(name)
        
        self.setStatus('Configuration removed.')
        
    def setStatus(self, txt):
        self.status.setText(txt)
        
    def checkForChanges(self, name):
        # returns True if there are changes
        
        conf = cfgManInst.configs.get(name)
        
        if conf:
            #print(conf)
            drv = dbidict[self.driverCB.currentText()]
            #print(conf.get('dbi'), drv)
            if (conf['hostport'] == self.hostportEdit.text()
                and conf.get('user') == self.userEdit.text()
                and conf.get('pwd') == self.pwdEdit.text()
                and conf.get('dbi') == drv
                and conf.get('ssl') == self.sslCB.isChecked()):
                return False
            else:
                #print('True')
                return True
        else:
            return False
        
    def configurationChanged(self, text):
    
        if self.checkForChanges(self.confCB.currentText()):
            self.setStatus('Note: there are unsaved configuration changes')
        else:
            self.setStatus('')

    def pwdShowHide(self):
        if self.pwdEdit.echoMode() == QLineEdit.Password:
            self.pwdEdit.setEchoMode(QLineEdit.Normal)
            self.pwdShow.setText('hide')
        else:
            self.pwdShow.setText('show')
            self.pwdEdit.setEchoMode(QLineEdit.Password)
        
    def processFinished(self):
        log(f'Process finished {self.prcPwdRequest=}')
        
    def processStdErr(self):
        log(f'Process err {self.prcPwdRequest=}')
        d = self.p.readAllStandardError()
        s = bytes(d).decode('utf8')
        log(s)

    def processStdOut(self):
        log(f'Process stdout, st={self.prcPwdRequest}')
        d = self.p.readAllStandardOutput()
        s = bytes(d).decode('utf8')
        log(s.strip())

        if s == 'Password:':
            deb('yep, trigger pwdRequest')
            self.prcPwdRequest = 'requested'
        else:
            deb('not pwd prompt...')

    def processReadReady(self):
        log(f'Process ready to read... {self.prcPwdRequest=}')

        if self.prcPwdRequest == 'requested':
            pwd = self.pwdEdit.text().strip()
            deb(f'pwd: {pwd}', comp='_pwd')
            self.p.write('test\n'.encode())
            self.prcPwdRequest = 'sent'
        else:
            deb('pwd not requested yet...')
        
    def processStateChange(self, state):
        states = {
            QProcess.NotRunning: 'Not running',
            QProcess.Starting: 'Starting',
            QProcess.Running: 'Running',
        }
        state_name = states.get(state)
        log(f'Process state -> {state_name}')
        
    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        
        if modifiers == Qt.ControlModifier and event.key() == Qt.Key_F12:
            import time

            log('Secret combo Ctrl+F12, call hdbuserstore', 2)
            log(r'    read more: https://www.pythonguis.com/tutorials/qprocess-external-programs/')

            self.prcPwdRequest = False
            self.p = QProcess()
            self.p.finished.connect(self.processFinished)
            self.p.readyReadStandardOutput.connect(self.processStdOut)
            self.p.readyReadStandardError.connect(self.processStdErr)
            self.p.stateChanged.connect(self.processStateChange)
            self.p.readyRead.connect(self.processReadReady)
            # hdbuserstore -i set <sid> <host>:<port> <username>
            
            confID = self.confCB.currentText()
            hostport = self.hostportEdit.text().strip()
            user = self.userEdit.text().strip()

            if cfg('dev'):
                self.p.start('hdbuserstore.bat', ['-i', 'set', 'test', hostport, user])
            else:
                params = ['-i', 'set', confID, hostport, user]
                log(f'hdbuserstore' + ' '.join(params), 2)
                self.p.start('hdbuserstore', params)
        else:
            super().keyPressEvent(event)
    

    def initUI(self):
    
        form = QGridLayout()
        
        self.driverCB = QComboBox()

        for drv in dbidict.keys():
            self.driverCB.addItem(drv)
        
        iconPath = resourcePath('ico', 'favicon.png')
        
        self.hostportEdit = QLineEdit()
        self.hostportEdit.textEdited.connect(self.configurationChanged)
        
        self.sslCB = QCheckBox('SSL');
        self.sslCB.stateChanged.connect(self.configurationChanged)
        
        #self.hostportEdit.setFixedWidth(192)
        
        self.userEdit = QLineEdit()
        self.pwdEdit = QLineEdit()
        self.userEdit.textEdited.connect(self.configurationChanged)
        self.pwdEdit.textEdited.connect(self.configurationChanged)
        
        self.pwdShow = QPushButton('show')
        self.pwdShow.clicked.connect(self.pwdShowHide)
        
        self.pwdEdit.setEchoMode(QLineEdit.Password)
        
        self.hostportLabel = QLabel('hostname:port')
        form.addWidget(self.hostportLabel, 1, 1)
        form.addWidget(QLabel('user'), 2, 1)
        form.addWidget(QLabel('pwd'), 3, 1)

        #hostport 
        #form.addWidget(self.hostportEdit, 1, 2)
        #form.addWidget(self.sslCB, 1, 3)
        hpLayout = QHBoxLayout()
        
        hpLayout.addWidget(self.hostportEdit)
        hpLayout.addWidget(self.sslCB)
        form.addLayout(hpLayout, 1, 2)
        
        form.addWidget(self.userEdit, 2, 2)
        
        pwdHBox = QHBoxLayout()
        pwdHBox.addWidget(self.pwdEdit)
        pwdHBox.addWidget(self.pwdShow)
        form.addLayout(pwdHBox, 3, 2)
        '''
        form.addWidget(self.pwdEdit, 3, 2)
        form.addWidget(self.pwdShow, 3, 3)
        '''
        
        checkButton = QPushButton("Check")
        
        self.noReload = QCheckBox('Skip initial KPIs load');
        self.readOnly = QCheckBox('Read-only connection (SQLite only)');
        self.readOnly.stateChanged.connect(self.configurationChanged)

        # save dialog
        self.confCB = QComboBox()
        
        #self.confCB.setFixedWidth(100)

        self.confCB.addItem('')
        
        for k in sorted(cfgManInst.configs):
            self.confCB.addItem(k)
        
        self.confCB.setEditable(True)
        self.confCB.currentIndexChanged.connect(self.confChange)
        
        self.save = QPushButton('Save')
        self.save.clicked.connect(self.confSave)
        
        self.delete = QPushButton('Delete')
        self.delete.clicked.connect(self.confDel)

        confHBox = QHBoxLayout()
        #confHBox.addWidget(QLabel('Configuration:'))
        
        #confSpltr = QSplitter(Qt.Horizontal)
        #confSpltr.addWidget(self.confCB)
        #confSpltr.addWidget(self.save)
        #confSpltr.addWidget(self.delete)
        #confSpltr.setSizes([200, 50])
        #confHBox.addWidget(confSpltr)

        confHBox.addWidget(self.confCB, 2)
        confHBox.addWidget(self.save, 1)
        confHBox.addWidget(self.delete, 1)

        # dbi stuff
        dbiHBox = QHBoxLayout()
        
        dbiHBox.addWidget(QLabel('Connection type:'))
        dbiHBox.addWidget(self.driverCB)
        
        self.driverCB.currentIndexChanged.connect(self.driverChanged)
        # ok/cancel buttons
        buttonsHBox = QHBoxLayout()
        btnConnect = QPushButton('Connect')
        btnCancel = QPushButton('Cancel')
        
        btnConnect.clicked.connect(self.accept)
        btnCancel.clicked.connect(self.reject)
        
        buttonsHBox.addStretch(1)
        buttonsHBox.addWidget(btnConnect)
        buttonsHBox.addWidget(btnCancel)
        
        self.errorMessage = QLabel()
        self.status = QLabel()

        # okay, Layout:
        vbox = QVBoxLayout()

        if True:
            confGroup = QGroupBox()
            confGroup.setTitle('Configuration')
            
            confGroup.setLayout(confHBox)
            
            vbox.addWidget(confGroup)
        
        if cfg('experimental', False):
            vbox.addLayout(dbiHBox) # driver type selection combo box
        
        vbox.addLayout(form) # main form
        
        if False:
            frm1 = QFrame()
            frm1.setFrameShape(QFrame.HLine)
            frm1.setFrameShadow(QFrame.Sunken)
            
            frm2 = QFrame()
            frm2.setFrameShape(QFrame.HLine)
            frm2.setFrameShadow(QFrame.Sunken)
            
            vbox.addWidget(frm1)
            vbox.addLayout(confHBox)
            vbox.addWidget(frm2)

        vbox.addWidget(self.noReload)

        if cfg('experimental'):
            vbox.addWidget(self.readOnly)

        vbox.addLayout(buttonsHBox)
        
        self.setWindowIcon(QIcon(iconPath))
        
        vbox.addWidget(self.errorMessage)
        vbox.addWidget(self.status)
        self.setLayout(vbox)
        
        btnConnect.setDefault(True)
        btnConnect.setFocus()
        
        #self.setFixedWidth(450)
        #self.setGeometry(300, 300, 300, 150)
        self.setWindowTitle('Connection details')
        #self.show()
        
        s = self.size()
        
        self.resize(450, s.height())
        
        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    cfg = Config()
    sys.exit(app.exec_())
