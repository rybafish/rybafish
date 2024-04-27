import re
import os.path

from PyQt5.QtWidgets import (QPushButton, QDialog, QLineEdit, QGridLayout,
                             QHBoxLayout, QVBoxLayout, QApplication, QLabel)

from PyQt5.QtCore import Qt

from PyQt5.QtGui import QIcon, QFont

import utils
from utils import cfg, deb

class pwdDialog(QDialog):

    height = None
    width = None

    def __init__(self, parent, user, pwd, title='Change password'):

        super(pwdDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        
        self.user = user
        self.pwd = pwd
        self.title = title

        self.initUI()
        
    def resizeEvent (self, event):
        # save the window size before layout dump in hslwindow
        pwdDialog.width = self.size().width()
        pwdDialog.height = self.size().height()
    

    def pwdShowHide(self):
        if self.pwdEdit.echoMode() == QLineEdit.Password:
            self.pwdEdit.setEchoMode(QLineEdit.Normal)
            self.pwdShow.setText('hide')
        else:
            self.pwdShow.setText('show')
            self.pwdEdit.setEchoMode(QLineEdit.Password)

    def initUI(self):

        iconPath = utils.resourcePath('ico', 'favicon.png')

        vbox = QVBoxLayout()
        btns = QHBoxLayout()
        form = QGridLayout()

        okBtn = QPushButton('Ok')
        okBtn.clicked.connect(self.accept)
        cancelBtn = QPushButton('Cancel')
        cancelBtn.clicked.connect(self.reject)

        self.userEdit = QLineEdit()
        self.userEdit.setEnabled(False)
        self.userEdit.setText(self.user)

        self.message = QLabel('')

        self.pwdEdit = QLineEdit()
        self.pwdEdit.setEchoMode(QLineEdit.Password)
        self.pwdEdit.setText(self.pwd)
        self.pwdEdit.setText(self.pwd)

        self.pwdShow = QPushButton('show')
        self.pwdShow.clicked.connect(self.pwdShowHide)

        form.addWidget(QLabel('User'), 1, 1)
        form.addWidget(self.userEdit, 1, 2)

        form.addWidget(QLabel('Passwd'), 2, 1)
        form.addWidget(self.pwdEdit, 2, 2)
        form.addWidget(self.pwdShow, 2, 3)

        btns.addWidget(okBtn)
        btns.addWidget(cancelBtn)
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
    dialog = pwdDialog(None, 'user', 'pwd')
    
    dialog.exec_()
