import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel, QCheckBox, QComboBox, QFrame)
    
from PyQt5.QtGui import QPixmap, QIcon

from PyQt5.QtCore import Qt

from utils import resourcePath

from utils import log, cfg, cfgManager

from dbi import dbidict

class Config(QDialog):

    config = {}
    
    def setConf(self, conf):
        try:
            if conf:
                hostport = conf['host'] + ':' + str(conf['port'])
                self.hostportEdit.setText(hostport)
                self.userEdit.setText(conf['user'])
                self.pwdEdit.setText(conf['password'])
                
                '''
                if conf.get('pwdhash'):
                    self.savePwd.setChecked(True)
                '''
                
                dbi = conf.get('dbi')
                
                if dbi:
                    for i in range(self.driverCB.count()):
                        if dbidict[self.driverCB.itemText(i)] == dbi:
                            self.driverCB.setCurrentIndex(i)
                
            else:
                self.hostportEdit.setFocus()
        except:
            pass
    
    
    def __init__(self, conf, parent = None):
        #super().__init__(parent)
        
        super(Config, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.cfgManager = cfgManager()
        self.initUI()
        
        self.conf = conf
        if conf:
            self.setConf(conf)
        
    @staticmethod
    def getConfig(config, parent = None):
    
        cf = Config(config, parent)
        result = cf.exec_()
        
        hostport = cf.hostportEdit.text()

        try:
            host, port = hostport.split(':')
        
            port = int(port)

            cf.config['ok'] = True
            cf.config['host'] = host
            cf.config['port'] = port
        except:
            cf.hostportEdit.setStyleSheet("color: red;")
            cf.config['ok'] = False
            cf.config['port'] = ''
            cf.config['host'] = hostport
        
        cf.config['dbi'] = dbidict[cf.driverCB.currentText()]
        
        cf.config['user'] = cf.userEdit.text()
        cf.config['password'] = cf.pwdEdit.text().strip()
        
        cf.config['noreload'] = cf.noReload.isChecked()
        # cf.config['savepwd'] = cf.savePwd.isChecked()
        
        return (cf.config, result == QDialog.Accepted)
        
    def driverChanged(self, index):
    
        drv = self.driverCB.currentText()
        
        if drv == 'ABAP Proxy':
            self.userEdit.setDisabled(True)
            self.pwdEdit.setDisabled(True)
            self.update()
        elif drv == 'HANA DB':
            self.userEdit.setEnabled(True)
            self.pwdEdit.setEnabled(True)

    def confChange(self, i):
    
        def parseHost(hostport):
        
            try:
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
            c = self.cfgManager.configs[name]
            
            host, port = parseHost(c['hostport'])
            conf['host'] = host
            conf['port'] = port
            conf['user'] = c['user']
            conf['password'] = c['pwd']
        else:
            conf = self.conf
        
        self.setConf(conf)
    
    def confSave(self):
        txt = self.confCB.currentText()
        
        cfg = {}
        
        cfg['name'] = txt
        cfg['dbi'] = self.driverCB.currentText()
        cfg['user'] = self.userEdit.text()
        cfg['pwd'] = self.pwdEdit.text()
        cfg['hostport'] = self.hostportEdit.text()
        
        items = []
        for i in range(self.confCB.count()):
            items.append(self.confCB.itemText(i))
            
        self.cfgManager.updateConf(cfg)
        
        self.confCB.addItem(txt)
        
        self.confCB.setCurrentIndex(self.confCB.count() - 1)
                
    def confDel(self):
        name = self.confCB.currentText()
        i = self.confCB.currentIndex()
        self.confCB.removeItem(i)
        
        self.cfgManager.removeConf(name)
        
    def initUI(self):

        #form = QFormLayout()
        form = QGridLayout()
        
        self.driverCB = QComboBox()
        self.driverCB.addItem('HANA DB')
        self.driverCB.addItem('ABAP Proxy')
        
        iconPath = resourcePath('ico\\favicon.png')
        
        self.hostportEdit = QLineEdit()
        
        #self.hostportEdit.setFixedWidth(192)
        
        self.userEdit = QLineEdit()
        self.pwdEdit = QLineEdit()
        
        self.pwdEdit.setEchoMode(QLineEdit.Password)
        
        form.addWidget(QLabel('hostname:port'), 1, 1)
        form.addWidget(QLabel('user'), 2, 1)
        form.addWidget(QLabel('pwd'), 3, 1)

        form.addWidget(self.hostportEdit, 1, 2)
        form.addWidget(self.userEdit, 2, 2)
        form.addWidget(self.pwdEdit, 3, 2)
        
        checkButton = QPushButton("Check")
        
        # self.savePwd = QCheckBox('Save the password into layout.aml');
        self.noReload = QCheckBox('Skip initial KPIs load');


        # save dialog
        self.confCB = QComboBox()
        
        self.confCB.setFixedWidth(100)

        self.confCB.addItem('')
        for k in self.cfgManager.configs:
            self.confCB.addItem(k)
        
        self.confCB.setEditable(True)
        self.confCB.currentIndexChanged.connect(self.confChange)
        
        self.save = QPushButton('Save')
        self.save.clicked.connect(self.confSave)
        
        self.delete = QPushButton('Delete')
        self.delete.clicked.connect(self.confDel)

        confHBox = QHBoxLayout()
        confHBox.addWidget(QLabel('Configuration:'))
        confHBox.addWidget(self.confCB)
        confHBox.addWidget(self.save)
        confHBox.addWidget(self.delete)

        # dbi stuff
        dbiHBox = QHBoxLayout()
        
        dbiHBox.addWidget(QLabel('Connection type:'))
        dbiHBox.addWidget(self.driverCB)
        
        self.driverCB.currentIndexChanged.connect(self.driverChanged)
        # ok/cancel buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)


        # okay, Layout:
        vbox = QVBoxLayout()
        
        if True:
            frm = QFrame()
            frm.setFrameShape(QFrame.HLine)
            frm.setFrameShadow(QFrame.Sunken)
            vbox.addLayout(confHBox)
            vbox.addWidget(frm)

        if cfg('DBI', False):
            vbox.addLayout(dbiHBox) # driver type
        
        vbox.addLayout(form) # main form
        
        # vbox.addWidget(self.savePwd)
        vbox.addWidget(self.noReload)
        vbox.addWidget(self.buttons)
        
        self.setWindowIcon(QIcon(iconPath))
        
        self.setLayout(vbox)
        
        #self.setGeometry(300, 300, 300, 150)
        self.setWindowTitle('Connection')
        #self.show()
        
        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    cfg = Config()
    sys.exit(app.exec_())