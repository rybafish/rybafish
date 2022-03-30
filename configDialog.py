import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox,
    QHBoxLayout, QVBoxLayout, QApplication, QGridLayout, QFormLayout, QLineEdit, QLabel, QCheckBox, QComboBox)
    
from PyQt5.QtGui import QPixmap, QIcon

from PyQt5.QtCore import Qt

from utils import resourcePath

from utils import log, cfg

from dbi import dbidict

class Config(QDialog):

    config = {}
    
    def __init__(self, conf, parent = None):
        #super().__init__(parent)
        
        super(Config, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        self.initUI()
        
        print('config', conf)
        
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

    def initUI(self):

        #form = QFormLayout()
        form = QGridLayout()
        
        self.driverCB = QComboBox()
        self.driverCB.addItem('HANA DB')
        self.driverCB.addItem('ABAP Proxy')

        
        iconPath = resourcePath('ico\\favicon.png')
        
        self.hostportEdit = QLineEdit()
        
        self.hostportEdit.setFixedWidth(192)
        
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

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)


        dbiHBox = QHBoxLayout()
        
        dbiHBox.addWidget(QLabel('Connection type:'))
        dbiHBox.addWidget(self.driverCB)
        
        
        vbox = QVBoxLayout()
        #vbox.addWidget(checkButton)
        #vbox.addWidget()
        
        if cfg('DBI', False):
            vbox.addLayout(dbiHBox)
        
        vbox.addLayout(form)
        #vbox.addStretch(1)
        # vbox.addLayout(hbox)
        
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