from PyQt5.QtWidgets import QWidget, QToolTip

from PyQt5.QtGui import QPainter, QColor, QBrush, QPen

from PyQt5.QtCore import QSize, Qt, QPoint

from PyQt5.QtCore import pyqtSignal

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
    
    iToggle = pyqtSignal(['QString'])
    
    def __init__(self, parent = None):
        self.active = False
        
        self.bkpStatus = 'idle'
        self.status = 'idle'
        
        self.runtime = None         # str to be displayed, not a number/timer/whatever
        super().__init__(parent)
        
        self.setMinimumSize(QSize(15, 15))
        
        #self.setMouseTracking(True)
        
    def leaveEvent(self, event):
        self.iToggle.emit('off')
    
    def enterEvent(self, event):
        self.iToggle.emit('on')
        
    def updateRuntime(self):
        if self.runtime is not None:
            QToolTip.showText(self.mapToGlobal(QPoint(5, 5)), str(self.runtime), self)
        else:
            QToolTip.showText(self.mapToGlobal(QPoint(5, 5)), None, self)

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