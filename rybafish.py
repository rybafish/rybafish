from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QPainter, QIcon

import sys

import os
from PyQt5.QtCore import Qt

import hslWindow

from PyQt5 import QtCore

from utils import log

import utils
from utils import resourcePath
from _constants import build_date, version

import traceback
import sqlConsole
import kpiDescriptions

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
    
        global ryba
        global rybaSplash
        
        if rybaSplash:
            try:
                import pyi_splash
                pyi_splash.close()
            except:
                pass
    
        cwd = os.getcwd()
        log('[!] fatal exception\n')
        
        #details = '%s: %s\n' % (str(exctype), str(value))
        details = '%s.%s: %s\n\n' % (exctype.__module__ , exctype.__qualname__  , str(value))
        #???

        #self.errorSignal.emit()
        #sys._excepthook(exctype, value, traceback)
        

        for s in traceback.format_tb(tb):
            details += '>>' + s.replace('\\n', '\n').replace(cwd, '..')

        log(details, nots = True)


        if ryba.tabs:
            for i in range(ryba.tabs.count() -1, 0, -1):

                w = ryba.tabs.widget(i)
                
                if isinstance(w, sqlConsole.sqlConsole):
                    w.delayBackup()

        try:
            if utils.cfg('saveLayout', True):
                ryba.dumpLayout()
        except Exception as e:
            log('[!] Exception during exception handler: %s' % str(e))
            details += '\n[!] Exception during exception handler:\n'
            details += str(e)

        msgBox = QMessageBox()
        msgBox.setWindowTitle('Fatal error')
        msgBox.setText('Unhandled exception occured. Check the log file for details.\n\nIf you want to report this issue, press "Show Details" and copy the call stack.')
        
        msgBox.setIcon(QMessageBox.Critical)
        msgBox.setDetailedText(details)
        iconPath = resourcePath('ico\\favicon.png')
        msgBox.setWindowIcon(QIcon(iconPath))
        msgBox.exec_()
        
        sys.exit(0)

if __name__ == '__main__':

    global ryba
    global rybaSplash
    
    #os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = '1'
    
    rybaSplash = True

    try:
        import pyi_splash
        pyi_splash.update_text('Starting...')
    except:
        pass

    exceptionHandler = ExceptionHandler()
    #sys._excepthook = sys.excepthook
    sys.excepthook = exceptionHandler.handler
    
    loadConfig = True
    
    while loadConfig:
    
        ok = utils.loadConfig()
                
        if not ok:
            try:
                import pyi_splash
                pyi_splash.close()
                rybaSplash = False
            except:
                pass
            loadConfig = utils.yesNoDialog('Config error', 'Cannot load/parse config.yaml\nTry again?')
        else:
            loadConfig = False
            
    if not loadConfig:
        utils.fakeRaduga()
            
    kpiDescriptions.generateRaduga()
    
    if utils.cfg('DPIAwareness', True):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        
    app = QApplication(sys.argv)

    log('Starting %s build %s' % (version, build_date))
    log('qt version: %s' %(QtCore.QT_VERSION_STR))

    ryba = hslWindow.hslWindow()

    try:
        import pyi_splash
        pyi_splash.close()
    except:
        pass
    
    loadConfig = True
    
    sys.exit(app.exec_())
    app.exec_()