from PyQt5.QtWidgets import QApplication, QMessageBox;
from PyQt5.QtGui import QPainter, QIcon

import sys
import hslWindow

from PyQt5 import QtCore

from utils import log

import utils
from utils import resourcePath
from _constants import build_date, version

import traceback

'''
    TODO
    
    - log console (log all exceptions through signals)
    - file import dialog
    - hosts/tenants pane
    - config screen
        - favorite connections
        - smart checks (show ooms, show expst)
    - statistics server charts
    - memory allocators chart
    
'''

class ExceptionHandler(QtCore.QObject):

    errorSignal = QtCore.pyqtSignal()

    def __init__(self):
        super(ExceptionHandler, self).__init__()

    def handler(self, exctype, value, tb):
        log('[!] fatal exeption\n')
        #details = '%s: %s\n' % (str(exctype), str(value))
        details = '%s.%s: %s\n\n' % (exctype.__module__ , exctype.__qualname__  , str(value))
        #???

        #self.errorSignal.emit()
        #sys._excepthook(exctype, value, traceback)
        

        for s in traceback.format_tb(tb):
            details += s.replace('\\n', '\n')

        log(details, nots = True)

        msgBox = QMessageBox()
        msgBox.setWindowTitle('Fatal error')
        msgBox.setText('Unhandled exception occured. Check the log file for details.')
        msgBox.setIcon(QMessageBox.Critical)
        msgBox.setDetailedText(details)
        iconPath = resourcePath('ico\\favicon.ico')
        msgBox.setWindowIcon(QIcon(iconPath))
        msgBox.exec_()
        
        sys.exit(0)

if __name__ == '__main__':
    
    exceptionHandler = ExceptionHandler()
    #sys._excepthook = sys.excepthook
    sys.excepthook = exceptionHandler.handler

    utils.loadConfig()
    
    log('Starting %s build %s' % (version, build_date))
    
    app = QApplication(sys.argv)
    ex = hslWindow.hslWindow()
    
    sys.exit(app.exec_())
    app.exec_()