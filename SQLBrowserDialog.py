import sys

from PyQt5.QtWidgets import (QPushButton, QDialog, 
    QHBoxLayout, QVBoxLayout, QApplication, QLabel, QTreeView, QStyle)
    
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem

import os, time

from PyQt5.QtCore import Qt

from PyQt5.QtCore import pyqtSignal

from utils import resourcePath
from utils import log, cfg

from profiler import profiler
    
class SQLBrowser(QTreeView):

    def buildModel(self, folder=''):
    
        nodes = {}
        
        def processFolder(path, folder=''):
            target = os.path.join(path, folder)
            
            if folder == '':
                nodes[target] = parentItem
            else:
                if os.path.isdir(target):
                    item = QStandardItem(folder)
                    item.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
                    item.setEditable(False)
                    nodes[target] = item
                    nodes[path].appendRow(item)
                else:
                    nodes[target] = folder + ' (file)'
                    item1 = QStandardItem(folder)
                    item1.setEditable(False)
                    item1.setData(target, role=Qt.UserRole + 1)
                    item2 = QStandardItem(str(os.path.getsize(target)))
                    item2.setEditable(False)
                    
                    ftime = os.path.getmtime(target)
                    ftime = time.ctime(ftime)
                    
                    item3 = QStandardItem(str(ftime))
                    item3.setEditable(False)
                    nodes[path].appendRow([item1, item2, item3])
                    return
        
            folders = os.listdir(target)
            
            for f in folders:
                processFolder(target, f)

        #self.model = QStandardItemModel()
        
        self.model.clear()
        parentItem = self.model.invisibleRootItem()
        
        self.model.setHorizontalHeaderLabels(['sql', 'size', 'date'])
        processFolder(folder)
        
        self.setModel(self.model)

        self.setColumnWidth(0, 350)
        self.setColumnWidth(1, 50)
        self.setColumnWidth(2, 150)
        
    def __init__(self, folder=cfg('sqlFolder', 'scripts')):
        super().__init__()
        
        self.model = QStandardItemModel()
        self.buildModel(folder)
        

class SQLBrowserDialog(QDialog):

    inst = None
    
    def __init__(self, parent = None):

        super(SQLBrowserDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        self.mode = None
        
        self.initUI()

        #self.linesList.setFocus()
        
    @staticmethod
    def getFile(parent):
        if SQLBrowserDialog.inst is None:
            sqld = SQLBrowserDialog(parent)
            SQLBrowserDialog.inst = sqld
        else:
            sqld = SQLBrowserDialog.inst
    
        result = sqld.exec_()
        
        indexes = sqld.tree.selectionModel().selectedIndexes()
        
        file = None
        
        if len(indexes):
            idx = indexes[0]
            file = idx.data(role=Qt.UserRole + 1)
        
        if result == QDialog.Accepted:
            return (sqld.mode, file)
        else:
            return (None, None)


    def insertText(self):
        self.mode = 'insert'
        self.accept()

    def newCons(self):
        self.mode = 'open'
        self.accept()
    
    def editFile(self):
        self.mode = 'edit'
        self.accept()
        
    def reloadModel(self):
        self.tree.buildModel(folder=cfg('sqlFolder', 'scripts'))
        #self.tree.setModel(model)

        self.repaint()

    def initUI(self):

        iconPath = resourcePath('ico\\favicon.ico')
        
        self.tree = SQLBrowser()
        
        self.vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        
        insertBtn = QPushButton('Insert SQL')
        insertBtn.clicked.connect(self.insertText)
        
        newconsBtn = QPushButton('Open in new console')
        newconsBtn.clicked.connect(self.newCons)

        editBtn = QPushButton('Open for edit')
        editBtn.clicked.connect(self.editFile)
        
        cancelBtn = QPushButton('Cancel')
        cancelBtn.clicked.connect(self.reject)
        
        reloadBtn = QPushButton('Reload')
        reloadBtn.clicked.connect(self.reloadModel)
        
        hbox.addWidget(insertBtn)
        hbox.addWidget(newconsBtn)
        hbox.addWidget(editBtn)
        hbox.addWidget(reloadBtn)
        hbox.addWidget(cancelBtn)
        
        self.vbox.addWidget(self.tree)
        self.vbox.addLayout(hbox)

        self.setLayout(self.vbox)
        
        self.resize(600, 300)
        
        self.setWindowTitle('SQL Browser')

if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    ab = SQLBrowserDialog()
    
    sys.exit(ab.exec_())