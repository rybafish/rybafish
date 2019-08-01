from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QScrollArea

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QGridLayout

from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt

import sys

from utils import log

lst = ['1', '2', '3', '4', '5', '6', '7', '8']

class myWidget(QWidget):
    def paintEvent(self, QPaintEvent):
        qp = QPainter()
        
        size = self.size()
        
        log('%i x %i' % (size.width(), size.height()))
        
        super().paintEvent(QPaintEvent)
        
        #f=open('21231','r')
        qp.begin(self)
        #
        
        
        qp.setPen(QColor('#AAF'))
        
        qp.setPen(Qt.blue)

        qp.drawLine(0, 0, size.width(), size.height())
        qp.drawLine(size.width(), 0, 0,  size.height())
        
        qp.end()
        
        #log(self.parentWidget.size().height());
        
class MyApp(QWidget):
    def __init__(self):
        super(MyApp, self).__init__()
        window_width = 1200
        window_height = 600
        #self.setFixedSize(window_width, window_height)
        self.initUI()
        
    def resizeEvent(self, event):
        log('%i x %i  -> %i x %i (%i)' % (self.width(), self.height(), self.scrollarea.width(), self.scrollarea.height(), self.scrollarea.horizontalScrollBar().height()))
        self.widget.resize(2000, self.scrollarea.height()-(self.scrollarea.horizontalScrollBar().height() + 2))
        super().resizeEvent(event)
        
    def createLayout_Container(self):
        self.scrollarea = QScrollArea(self)
        #self.scrollarea.setFixedWidth(250)
        #self.scrollarea.setFixedHeight(320)
        self.scrollarea.setWidgetResizable(False)

        self.widget = myWidget()
        
        #widget.resize(20000, self.scrollarea.height()-19);
        
        self.scrollarea.setWidget(self.widget)
        self.layout_SArea = QVBoxLayout(self.widget)

    def initUI(self):
        self.createLayout_Container()
        self.layout_All = QVBoxLayout(self)
        self.layout_All.addWidget(self.scrollarea)
        self.show()
        #log(self.scrollarea.height())
        #log(self.scrollarea.horizontalScrollBar().height())
        
        log('init: %i x %i  -> %i x %i (%i)' % (self.width(), self.height(), self.scrollarea.width(), self.scrollarea.height(), self.scrollarea.horizontalScrollBar().height()))
        self.widget.resize(2000, self.scrollarea.height()-(self.scrollarea.horizontalScrollBar().height() + 2))
        self.widget.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    sys.exit(app.exec_())