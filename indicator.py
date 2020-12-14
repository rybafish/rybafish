from PyQt5.QtWidgets import QWidget, QToolTip

from PyQt5.QtGui import QPainter, QColor, QBrush, QPen

from PyQt5.QtCore import QSize, Qt

from PyQt5.QtCore import pyqtSignal

class indicator(QWidget):

    styles = {
        'idle': '#CCC',
        'sync': '#44F',
        'running': '#8F8',
        'error': '#CCC',
        'render': '#FFF',
        'disconnected': '#FCC'
    }


    iClicked = pyqtSignal()
    
    def __init__(self, parent = None):
        self.active = False
        self.status = 'idle'
        super().__init__(parent)
        
        self.setMinimumSize(QSize(15, 15))

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
            color = QColor(self.styles[self.status])
            qp.setBrush(QBrush(color, Qt.SolidPattern))
        else:
            qp.setBrush(QBrush(QColor('#F00'), Qt.SolidPattern))
            #qp.setBrush(QBrush(QColor('#8C8'), Qt.SolidPattern))
        
        if self.status == 'disconnected' or self.status == 'error':
            qp.setPen(QColor('#F00'))
        else:
            qp.setPen(QColor('#888'))
            
        qp.drawRect((h - 10 )/2, (w - 10 )/2, 10, 10)
        
        qp.end()