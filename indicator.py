from PyQt5.QtWidgets import QWidget, QToolTip
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen
from PyQt5.QtCore import QSize, Qt, QPoint
from PyQt5.QtCore import pyqtSignal, QTimer

from datetime import datetime
import time
import utils

class indicator(QWidget):

    styles = {
        'idle': '#CCC',
        'sync': '#44F',
        'running': ('#8F8', '#4A4'),
        'error': ('#CCC', '#F00'),
        'render': '#FFF',
        'disconnected': '#888',
        #'disconnected': '#FCC',
        'alert': '#FAC',
        'autorefresh': '#cfc',
        'detach': ('#CCC', '#444'),
        #'detach': '#EEC',
    }


    iClicked = pyqtSignal()
    #iHover = pyqtSignal() 2022-07-03
    
    # iToggle = pyqtSignal(['QString'])
    
    def __init__(self, parent = None):
        self.active = False
        
        self.bkpStatus = 'idle'
        self.status = 'idle'
        
        self.runtime = None         # str to be displayed, not a number/timer/whatever
        self.t0 = None              # link to parent tab statement start time (charts or console)
        self.nextAutorefresh = None # link to parent next autorefresh time
        self.runtimeTimer = None

        super().__init__(parent)
        
        self.setMinimumSize(QSize(15, 15))
        
        #self.setMouseTracking(True)
        
    def leaveEvent(self, event):
        #self.iToggle.emit('off')
        self.updateRuntime('off')
    
    def enterEvent(self, event):
        # self.iToggle.emit('on')
        self.updateRuntime('on')
        
    def updateRuntime_depr(self):
        if self.runtime is not None:
            QToolTip.showText(self.mapToGlobal(QPoint(5, 5)), str(self.runtime), self)
        else:
            QToolTip.showText(self.mapToGlobal(QPoint(5, 5)), None, self)

    def updateRuntimeTT(self):
        '''
            Updates the indicator tooltip
        '''
        if self.runtime is not None:
            QToolTip.showText(self.mapToGlobal(QPoint(5, 5)), str(self.runtime), self)
        else:
            QToolTip.showText(self.mapToGlobal(QPoint(5, 5)), None, self)

    def updateRuntime(self, mode=None):
        '''
            manages the indicator hint and calculates it's value
            new implementation, moved from sqlConsole to Indicator class

            mode = 'on': enable the hint, emmited by indicator on mouse hover
                'off': emmited by indicator on exit
                'stop': triggered manually on stop of sql execution.
        '''
        t0 = self.t0
        t1 = time.time()

        if mode == 'on':
            if t0 is not None: # normal hint for running console
                if self.runtimeTimer == None:
                    self.runtimeTimer = QTimer(self)
                    self.runtimeTimer.timeout.connect(self.updateRuntime)
                    self.runtimeTimer.start(1000)
            elif self.status == 'autorefresh': # autorefresh backward counter
                if self.runtimeTimer == None:
                    self.runtimeTimer = QTimer(self)
                    self.runtimeTimer.timeout.connect(self.updateRuntime)
                    self.runtimeTimer.start(1000)

        elif mode == 'off' or mode == 'stop':
            if mode == 'stop' and self.status == 'autorefresh':
                pass
            else:
                if self.runtimeTimer is not None:
                    self.runtime = None
                    self.runtimeTimer.stop()
                    self.runtimeTimer = None

                    self.updateRuntimeTT()

                    return

        if mode == 'off' or mode == 'stop':
            self.runtime = None
            self.updateRuntimeTT()
            return

        if t0 is not None:
            self.runtime = utils.formatTimeShort(t1-t0)
        elif self.status == 'autorefresh': # autorefresh backward counter
            if self.nextAutorefresh is None:
                return
            delta = self.nextAutorefresh - datetime.now()
            deltaSec = round(delta.seconds + delta.microseconds/1000000)
            self.runtime = 'Run in: ' + utils.formatTimeShort(deltaSec)
        else:
            self.runtime = None

        self.updateRuntimeTT()

    def mousePressEvent(self, event):
        self.iClicked.emit()
        
    def paintEvent(self, QPaintEvent):

        qp = QPainter()
        super().paintEvent(QPaintEvent)
        qp.begin(self)
        
        s = self.size()
        h, w = s.height(), s.width()

        '''
        if self.active:
            qp.setBrush(QBrush(QColor('#8C8'), Qt.SolidPattern))
        '''

        if self.status in self.styles:
        
            st = self.styles[self.status]
            
            if isinstance(st, tuple):
                brush = st[0]
                frame = st[1]
            else:
                brush = st
                frame = '#888'
        
            color = QColor(brush)
            qp.setBrush(QBrush(color, Qt.SolidPattern))
            qp.setPen(QColor(frame))
        else:
            # unknown status
            qp.setBrush(QBrush(QColor('#F00'), Qt.SolidPattern))
            qp.setPen(QColor('#A00'))
        
        '''
        if self.status == 'disconnected was' or self.status == 'error':
            qp.setPen(QColor('#F00'))
        else:
            qp.setPen(QColor('#888'))
        '''
            
        qp.drawRect(int((h - 10 )/2), int((w - 10 )/2), 10, 10)
        
        qp.end()
