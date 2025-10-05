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

    def __init__(self, parent, title='Enter master password', initial=False):

        self.never = None
        super(mpDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.title = title
        self.initial = initial

        self.initUI()
        
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
        
    def initUI(self):

        iconPath = utils.resourcePath('ico', 'favicon.png')

        vbox = QVBoxLayout()
        btns = QHBoxLayout()
        form = QGridLayout()

        okBtn = QPushButton('Ok')
        okBtn.clicked.connect(self.accept)
        cancelBtn = QPushButton('Cancel')
        cancelBtn.clicked.connect(self.reject)

        neverBtn = QPushButton('Don\'t set')
        neverBtn.clicked.connect(self.dontset)

        if self.initial:
            self.info1 = QLabel('You can define a master password for this installation. This password will be used to encrypt credentials.\nYou can also go "Don\'t set" and keep using RybaFish the old way.')
        else:
            self.info1 = QLabel('This RybaFish installation uses master passsword, please provide it.')

        self.info2 = QLabel('See more <a href="https://www.rybafish.net/masterPassword">details</a> on rybafish site.')
        self.info2.linkActivated.connect(self.rybafishDotNet)

        self.message = QLabel('')

        self.pwdEdit = QLineEdit()
        self.pwdEdit.setEchoMode(QLineEdit.Password)
        # self.pwdEdit.setText(self.pwd)

        self.pwdShow = QPushButton('show')
        self.pwdShow.clicked.connect(self.pwdShowHide)
        self.pwdShow.setAutoDefault(False)

        # form.addWidget(QLabel('User'), 1, 1)
        # form.addWidget(self.userEdit, 1, 2)

        form.addWidget(QLabel('Passwd'), 2, 1)
        form.addWidget(self.pwdEdit, 2, 2)
        form.addWidget(self.pwdShow, 2, 3)

        btns.addStretch(1)
        btns.addWidget(okBtn)
        btns.addWidget(cancelBtn)

        if self.initial:
            btns.addWidget(neverBtn)

        if self.initial or True:
            vbox.addWidget(self.info1)
            vbox.addWidget(self.info2)

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
