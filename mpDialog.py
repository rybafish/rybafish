import re
import os.path

from PyQt5.QtWidgets import (QPushButton, QDialog, QLineEdit, QGridLayout,
                             QHBoxLayout, QVBoxLayout, QApplication, QLabel)

from PyQt5.QtCore import Qt, QUrl

from PyQt5.QtGui import QIcon, QFont, QDesktopServices

import utils
from utils import cfg, deb

class mpDialog(QDialog):

    height = None
    width = None

    def __init__(self, parent, title='Enter Master Key', mode=None, num=None):

        self.never = None
        super(mpDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.title = title
        self.num = num

        deb(f'mpDialog(mode={mode}, num={num})')
        self.initUI()
        self.setMode(mode)
        
    def resizeEvent (self, event):
        # save the window size before layout dump in hslwindow
        mpDialog.width = self.size().width()
        mpDialog.height = self.size().height()
    

    def pwdShowHide(self):
        if self.pwdEdit.echoMode() == QLineEdit.Password:
            self.pwdEdit.setEchoMode(QLineEdit.Normal)
            self.pwdShow.setText('hide')
        else:
            self.pwdShow.setText('show')
            self.pwdEdit.setEchoMode(QLineEdit.Password)

    def rybafishDotNet(self, link):
        QDesktopServices.openUrl(QUrl(link))

    def dontset(self):

        self.never = True
        self.reject()
        
    def setMode(self, mode):
        deb(f'setMode: {mode}')
        if mode == 'initial':
            self.info1.setText('You can define a master key for this installation. This key will be used to encrypt credentials.\nYou can as well go "Don\'t set" and keep using RybaFish the old way.')
            self.neverBtn.setVisible(True)
        elif mode == 'pwdrequest':
            self.info1.setText('This RybaFish installation uses master key, please provide it.')
            self.neverBtn.setVisible(False)
        elif mode == 'changepwd':
            # menu call to set up a new pwd
            self.info1.setText('Please define a NEW master key.')
            self.neverBtn.setVisible(False)

        if self.num and mode in ['initial', 'changepwd']:
            s = '' if self.num % 10 == 1 else 's'
            it = 'It' if self.num % 10 == 1 else 'Those'

            self.info2.setText(f"Note: this installation already has {self.num} configuration{s} with password. {it} will be re-coded (!). <span style='color: red;'>Highly recommended to create a backup before proceeding</span>.")
            self.info2.show()
        else:
            self.info2.hide()

    def initUI(self):
        iconPath = utils.resourcePath('ico', 'favicon.png')

        vbox = QVBoxLayout()
        btns = QHBoxLayout()
        form = QGridLayout()

        okBtn = QPushButton('Ok')
        okBtn.clicked.connect(self.accept)

        self.cancelBtn = QPushButton('Cancel')
        self.cancelBtn.clicked.connect(self.reject)

        self.neverBtn = QPushButton('Don\'t set')
        self.neverBtn.clicked.connect(self.dontset)

        self.info1 = QLabel()
        self.info2 = QLabel()

        # this one is more or less static
        self.info3 = QLabel('See <a href="https://www.rybafish.net/masterKey">details</a> on rybafish site.')
        self.info3.linkActivated.connect(self.rybafishDotNet)


        self.message = QLabel('')

        self.pwdEdit = QLineEdit()
        self.pwdEdit.setEchoMode(QLineEdit.Password)
        # self.pwdEdit.setText(self.pwd)

        self.pwdShow = QPushButton('show')
        self.pwdShow.clicked.connect(self.pwdShowHide)
        self.pwdShow.setAutoDefault(False)

        # form.addWidget(QLabel('User'), 1, 1)
        # form.addWidget(self.userEdit, 1, 2)

        form.addWidget(QLabel('Master Key'), 2, 1)
        form.addWidget(self.pwdEdit, 2, 2)
        form.addWidget(self.pwdShow, 2, 3)

        btns.addStretch(1)
        btns.addWidget(okBtn)
        btns.addWidget(self.cancelBtn)

        # if self.initial:
        btns.addWidget(self.neverBtn)

        vbox.addWidget(self.info1)
        vbox.addWidget(self.info2)
        vbox.addWidget(self.info3)

        vbox.addLayout(form)
        vbox.addWidget(self.message)
        vbox.addLayout(btns)

        self.setLayout(vbox)
        
        # self.resize(900, 600)
        
        if self.width and self.height:
            self.resize(self.width, self.height)

        self.setWindowIcon(QIcon(iconPath))

        self.setWindowTitle(self.title)

if __name__ == '__main__':
    
    app = QApplication([])
    dialog = mpDialog(None, initial=True)
    
    dialog.exec_()
