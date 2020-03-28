from PyQt5.QtWidgets import QWidget

from PyQt5.QtGui import QPainter, QColor, QBrush, QPen

from PyQt5.QtCore import QSize, Qt

class indicator(QWidget):
    def __init__(self, parent = None):
        self.active = False
        super().__init__(parent)
        
        self.setMinimumSize(QSize(15, 15))

    def mousePressEvent(self, event):
        print('click-click')
        
    def paintEvent(self, QPaintEvent):

        qp = QPainter()
        super().paintEvent(QPaintEvent)
        qp.begin(self)
        
        s = self.size()
        h, w = s.height(), s.width()

        if self.active:
            qp.setBrush(QBrush(QColor('#8C8'), Qt.SolidPattern))
        
        qp.setPen(QColor('#888'))
        qp.drawRect((h - 10 )/2, (w - 10 )/2, 10, 10)
        
        qp.end()