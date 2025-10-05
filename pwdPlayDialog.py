import re
import os.path

from PyQt5.QtWidgets import (QComboBox, QPushButton, QDialog, QLineEdit, QGridLayout,
                             QHBoxLayout, QVBoxLayout, QApplication, QLabel, QGroupBox)

from PyQt5.QtCore import Qt, QUrl

from PyQt5.QtGui import QIcon, QFont, QDesktopServices

import utils
from utils import cfg, deb

from cfgManager import cfgManInst

import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken

class pwdPlayDialog(QDialog):

    height = None
    width = None

    def __init__(self, parent):

        super(pwdPlayDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.title = 'Password Encryptor/Decryptor'

        self.initUI()
        
    def resizeEvent (self, event):
        # save the window size before layout dump in hslwindow
        pwdPlayDialog.width = self.size().width()
        pwdPlayDialog.height = self.size().height()
    

    def rybafishDotNet(self, link):
        QDesktopServices.openUrl(QUrl(link))

    def generateDKey(self):
        self.message.setText('')
        mp = self.mpEdit.text()
        salt = self.saltEdit.text()

        deb(f'salt: {salt}, mp: {mp}')
        
        try:
            salt = bytes.fromhex(salt)
        except ValueError as e:
            self.message.setText('[!] Error: Salt is not a correct 32 bytes hexadecimal value.')
            return
            
        deb(f'salt: {salt}, mp: {mp}', '_pwd')
        
        if mp or salt:
            pwdenc = hashlib.pbkdf2_hmac('sha256', mp.encode(), salt, 100000, dklen=32)
            pwdenc = base64.urlsafe_b64encode(pwdenc).decode()
        else:
            deb('using default key', '_pwd')
            pwdenc = cfg('cryptKey', 'aRPhXqZj9KyaC6l8V7mtcW7TvpyQRmdCHPue6MjQHRE=')

        deb(f'encoded string: {pwdenc}', '_pwd')
        self.dkEdit.setText(pwdenc)

    def createFernet(self):
        key = self.dkEdit.text()
        key = key.encode()

        try:
            deb(f'creating fernet with key: {key}', '_pwd')
            fernet = Fernet(key)
        except ValueError as ex:
            self.message.setText(f'[!] error: {ex}')
            return

        return fernet
    
    def encodePwd(self):
        self.message.setText('')

        fernet = self.createFernet()

        if not fernet:
            return

        pwd = self.pwdEncodePlainEdit.text()
        
        pwdenc = fernet.encrypt(pwd.encode())
        pwdenc = pwdenc.decode()
                
        deb(f'encode: {pwdenc}', '_pwd')

        self.pwdEncodeEncEdit.setText(pwdenc)


    def decodePwd(self):
        self.message.setText('')

        fernet = self.createFernet()

        if not fernet:
            return
        
        pwdenc = self.pwdEdit.text()
        # pwdenc = self.fernet.encrypt(pwd.encode())

        try:
            deb(f'fernet.decrypt({pwdenc.encode()})')
            pwd = fernet.decrypt(pwdenc.encode()).decode()
        except InvalidToken:
            self.message.setText(f'[!] Decode error: invalid token (wrong incorrect derived key)')
            deb('[!] Decode error: Invalid token', '_pwd')
            return

        deb(f'decoded pwd: {pwd}', '_pwd')

        self.pwdDecEdit.setText(pwd)

    
    def confChange(self, i):
        name = self.confCB.currentText()

        if name == '':
            self.pwdEdit.setText('')
        else:
            c = cfgManInst.configs[name]
            self.pwdEdit.setText(c['pwd'].decode())

    def initUI(self):

        iconPath = utils.resourcePath('ico', 'favicon.png')

        btns = QHBoxLayout()
        formCommon = QGridLayout()
        formDecode = QGridLayout()
        formEncode = QGridLayout()
        vboxCommon = QVBoxLayout()
        vboxDecode = QVBoxLayout()
        vboxEncode = QVBoxLayout()

        self.message = QLabel('')

        vbox1 = QVBoxLayout()
        vboxMain = QVBoxLayout()

        okBtn = QPushButton('Ok')
        okBtn.clicked.connect(self.accept)
        cancelBtn = QPushButton('Cancel')
        cancelBtn.clicked.connect(self.reject)

        # self.info1 = QLabel('Label1')
        # self.info2 = QLabel('See more <a href="https://www.rybafish.net/masterPassword">details</a> on rybafish site.')
        # self.info2.linkActivated.connect(self.rybafishDotNet)

        # self.pwdEdit.setEchoMode(QLineEdit.Password)
        # self.pwdEdit.setText(self.pwd)

        # self.pwdShow = QPushButton('show')
        # self.pwdShow.clicked.connect(self.pwdShowHide)
        # self.pwdShow.setAutoDefault(False)

        # form.addWidget(QLabel('User'), 1, 1)
        # form.addWidget(self.userEdit, 1, 2)

        self.mpEdit = QLineEdit()
        self.mpEdit.setToolTip('Free style master password (pin) you use to encrypt credentials')
        formCommon.addWidget(QLabel('Master Password'), 1, 1)
        formCommon.addWidget(self.mpEdit, 1, 2)
        
        slt = cfgManInst.salt
        
        if slt:
            slt = slt.hex()

        self.saltEdit = QLineEdit(slt)

        self.saltEdit.setToolTip('32 bytes salt in hexadecimal form. Default value loaded from connections.yaml')
        
        formCommon.addWidget(QLabel('Salt'), 2, 1)
        formCommon.addWidget(self.saltEdit, 2, 2)

        dkeyLO = QHBoxLayout()
        dkeyBtn = QPushButton('Generate derived key')
        dkeyBtn.clicked.connect(self.generateDKey)
        
        dkeyLO.addStretch(1)
        dkeyLO.addWidget(dkeyBtn)
        formCommon.addLayout(dkeyLO, 3, 2)

        self.dkEdit = QLineEdit()
        self.dkEdit.setToolTip('Calculated using PBKDF2 with HMAC-SHA256 based on master pwd and salt')
        formCommon.addWidget(QLabel('Derived Key'), 4, 1)
        formCommon.addWidget(self.dkEdit, 4, 2)
        
        self.confCB = QComboBox()

        self.confCB.addItem('')
        
        for k in sorted(cfgManInst.configs):
            c = cfgManInst.configs.get(k)

            if c is not None and 'pwd' in c:
                self.confCB.addItem(k)
        
        self.confCB.currentIndexChanged.connect(self.confChange)
        formDecode.addWidget(self.confCB, 4, 1)
        
        self.pwdEdit = QLineEdit()
        formDecode.addWidget(QLabel('Encoded string (pwd)'), 5, 1)
        formDecode.addWidget(self.pwdEdit, 5, 2)

        decKeyLO = QHBoxLayout()
        decBtn = QPushButton('Decode')
        decBtn.clicked.connect(self.decodePwd)

        decKeyLO.addStretch(1)
        decKeyLO.addWidget(decBtn)
        formDecode.addLayout(decKeyLO, 6, 2)

        self.pwdDecEdit= QLineEdit()
        formDecode.addWidget(QLabel('Decoded password'), 7, 1)
        formDecode.addWidget(self.pwdDecEdit, 7, 2)

        self.pwdEncodePlainEdit= QLineEdit()
        formEncode.addWidget(QLabel('Decoded password'), 1, 1)
        formEncode.addWidget(self.pwdEncodePlainEdit, 1, 2)
        
        encKeyLO = QHBoxLayout()
        encBtn = QPushButton('Encode')
        encBtn.clicked.connect(self.encodePwd)

        encKeyLO.addStretch(1)
        encKeyLO.addWidget(encBtn)
        formEncode.addLayout(encKeyLO, 2, 2)
        
        self.pwdEncodeEncEdit= QLineEdit()
        formEncode.addWidget(QLabel('Encoded string'), 3, 1)
        formEncode.addWidget(self.pwdEncodeEncEdit, 3, 2)
        
        btns.addStretch(1)
        btns.addWidget(okBtn)
        btns.addWidget(cancelBtn)

        # vbox.addWidget(self.info1)
        # vbox.addWidget(self.info2)

        vboxCommon.addLayout(formCommon)
        vboxDecode.addLayout(formDecode)
        vboxEncode.addLayout(formEncode)

        commonGroup = QGroupBox()
        commonGroup.setTitle('Common Data')
        commonGroup.setLayout(vboxCommon)
        
        vboxMain.addWidget(commonGroup)
        
        decodeGroup = QGroupBox()
        decodeGroup.setTitle('Decoding')
        vboxDecode.addWidget(commonGroup)
        decodeGroup.setLayout(vboxDecode)
        vboxMain.addWidget(decodeGroup)
        
        encodeGroup = QGroupBox()
        encodeGroup.setTitle('Encoding')
        encodeGroup.setLayout(vboxEncode)
        vboxMain.addWidget(encodeGroup)
        vboxMain.addWidget(QLabel('Note: this dialog is 100% read only and it does not make any changes to connections.yaml'))
        vboxMain.addWidget(self.message)
        vboxMain.addLayout(btns)
        
        self.setLayout(vboxMain)
        
        self.resize(900, 300)
        
        if self.width and self.height:
            self.resize(self.width, self.height)

        self.setWindowIcon(QIcon(iconPath))

        self.setWindowTitle(self.title)

if __name__ == '__main__':
    
    app = QApplication([])
    dialog = pwdPlayDialog(None)
    
    dialog.exec_()
