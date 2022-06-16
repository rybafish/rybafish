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

    filterUpdated = pyqtSignal()

    def flatStructure(self, files):
        '''checks if the folder seems to have "flat" structure'''
    
        total = 0
        underscore = 0
    
        for f in files:
            if f[0:5] == 'HANA_' and f[-4:] == '.txt':
                underscore += 1
                
            total += 1
            
        if total > 0 and underscore / total > 0.9:
            return True
        else:
            return False
        
    @profiler
    def parseFlat(self, parentItem, folder, files, filter=''):
        '''
            method deals with flat files structure based on inderscore as a separator
            and prefix as.. you know... prefix
            
            it also uses filter to hide/highlight staff
            
            again, very very very bad design, sorry.
            
            unfortunately, it works okay and the performance is good enough, so... not sure
            it it wirth refactoring, 2022-06-16, #500.
        '''
    
        maxDepth = 2
        prefix = 'HANA_'
    
        st = []
        nodesst = [parentItem]
        
        nodes = {}
        leaves = {}
    
        j = 0
        for f in files:
            if f[0:len(prefix)] != prefix:
                continue
                
            if filter and f.lower().find(filter) < 0:
                continue
                                
            f = f[len(prefix):]
                
            hier = f.split('_', maxDepth)
            #print(f, hier)
            
            for i in range(len(hier)-1):
                #print(i, hier[i])
                
                noSlice = False
                
                if i < len(st):
                    if hier[i] != st[i]:
                        noSlice = True
                        st = st[:i]
                        nodesst = nodesst[:i+1] # nodesst has parent node...
                        st.append(hier[i])
                        
                        #print('\t\tslice due to new parent', st)

                        item = QStandardItem(hier[i])
                        #item.setIcon(self.style().standardIcon(QStyle.SP_DirLinkIcon))
                        item.setEditable(False)

                        if len(filter) >=3 and hier[i].lower().find(filter) >= 0:
                            item.setFont(self.boldFont)
                        
                        nodesst[-1].appendRow(item)
                        nodesst.append(item)

                else:
                    st.append(hier[i])
                    
                    item = QStandardItem(hier[i])
                    #item.setIcon(self.style().standardIcon(QStyle.SP_DirLinkIcon))
                    item.setEditable(False)
                    
                    if len(filter) >=3 and hier[i].lower().find(filter) >= 0:
                        item.setFont(self.boldFont)
                    
                    nodesst[-1].appendRow(item)
                    nodesst.append(item)
                    
                    #print('\t\tone level deep', st)
                    
            if noSlice == False and i+1 < len(st):
                #print(f'\t\t[!] reslice... {len(st)}/{len(nodesst)}', st)
                st = st[:i+1]
                nodesst = nodesst[:i+1+1] # it also has parent item
                #print(f'\t\t[!] reslice... {len(st)}/{len(nodesst)}', st)

            '''
            initial population of leaves
            
            item = QStandardItem(hier[-1])
            item.setEditable(False)
            nodesst[-1].appendRow(item)
            '''
            
            filename = os.path.join(folder, prefix+f)
            leaves[f] = (hier[-1], nodesst[-1], filename)
            
            #print(f'\t\t{hier[-1]} goes to {st[-1]}')
            
            j += 1
            
            '''
            if j >= 10:
                break
            '''
        
        # populate leaves now:
        for file in leaves.keys():
            #print(f'{file} --> {leaves[file]}')
            f = leaves[file]
            item = QStandardItem(f[0])
            item.setEditable(False)
            
            if len(filter) >=3 and f[0].lower().find(filter) >= 0:
                item.setFont(self.boldFont)
            
            item.setData(f[2], role=Qt.UserRole + 1)
            f[1].appendRow(item)
       
    @profiler
    def buildModel(self, folder='', filter = ''):
    
        nodes = {}
        
        def processFolder(path, folder=''):
            '''
                recursive function to populate data model for treeview
                
                it also calls parseFlat to parse flat folder in case one detected
                
                it actually builds the model object based on a single root node parentNode
                which is created outside.

                long story short: very very bad design....
            '''
            target = os.path.join(path, folder)
            
            if folder == '':
                nodes[target] = parentItem
            
                if not os.path.isdir(target):

                    error = f'[ERROR] folder "{target}" does not exist. Check the folder and scriptsFolder setting.'
                    item1 = QStandardItem(error)
                    item1.setEditable(False)
                    
                    parentItem.appendRow(item1)
                    
                    return
            
            else:
                if os.path.isdir(target):
                    item = QStandardItem(folder)
                    item.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
                    item.setEditable(False)
                    nodes[target] = item
                    nodes[path].appendRow(item)
                else:
                    nodes[target] = folder + ' (file)'
                    
                    if filter and folder.lower().find(filter) < 0:
                        return

                    item1 = QStandardItem(folder)
                    item1.setEditable(False)

                    if len(filter) >=3 and folder.lower().find(filter) >= 0:
                        item1.setFont(self.boldFont)

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
            
            if self.flatStructure(folders):
                self.parseFlat(nodes[target], target, folders, filter=filter)
                
            else:
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
        
    def __init__(self, folder=cfg('scriptsFolder', 'scripts')):
        super().__init__()
        
        self.filter = ''
        
        self.model = QStandardItemModel()
        self.buildModel(folder)
        
        item = QStandardItem('dummy')
        
        self.boldFont = item.font()
        self.boldFont.setBold(True)

    def keyPressEvent(self, event):
    
        k = event.text()

        if k.isalnum() or k == '_':
            self.filter += k
            self.filterUpdated.emit()
        elif event.key() == Qt.Key_Backspace:
            self.filter = self.filter[:-1]
            self.filterUpdated.emit()
        else:
            super().keyPressEvent(event)
        

class SQLBrowserDialog(QDialog):

    inst = None
    
    def __init__(self, parent = None):

        super(SQLBrowserDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        self.mode = None

        self.initUI()
        self.tree.filter = ''

        #self.insertBtn.setFocus()
        
    def updateFilter(self):
        self.filterLabel.setText(self.tree.filter)
        
        self.tree.buildModel(folder=cfg('scriptsFolder', 'scripts'), filter=self.tree.filter)
        if len(self.tree.filter) >= 3:
            self.tree.expandAll()

    '''
    def keyPressEvent(self, event):
    
        k = event.text()
        
        if k.isalnum() or k == '_':
            self.filter += k
            self.updateFilter()
        elif event.key() == Qt.Key_Backspace:
            self.filter = self.filter[:-1]
            self.updateFilter()
        else:
            super().keyPressEvent(event)
    '''
        
        
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
    
    def itemSelected(self, item):
        # and the itec actually ignored because it is extracted in getFile()
        self.mode = 'insert'
        self.accept()
    
    def editFile(self):
        self.mode = 'edit'
        self.accept()
        
    def reloadModel(self):
        self.filter = ''
        self.updateFilter()
        self.tree.buildModel(folder=cfg('scriptsFolder', 'scripts'), filter=self.filter)
        self.repaint()

    def initUI(self):

        iconPath = resourcePath('ico\\favicon.ico')
        
        self.tree = SQLBrowser()
        
        self.tree.filterUpdated.connect(self.updateFilter)
        self.tree.doubleClicked.connect(self.itemSelected)
        
        self.vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        
        self.insertBtn = QPushButton('Insert SQL')
        self.insertBtn.clicked.connect(self.insertText)
        
        newconsBtn = QPushButton('Open in new console')
        newconsBtn.clicked.connect(self.newCons)

        editBtn = QPushButton('Open for edit')
        editBtn.clicked.connect(self.editFile)
        
        cancelBtn = QPushButton('Cancel')
        cancelBtn.clicked.connect(self.reject)
        
        reloadBtn = QPushButton('Reload')
        reloadBtn.clicked.connect(self.reloadModel)
        
        hbox.addWidget(self.insertBtn)
        hbox.addWidget(newconsBtn)
        hbox.addWidget(editBtn)
        hbox.addWidget(reloadBtn)
        hbox.addWidget(cancelBtn)
        
        self.filterLabel = QLabel('Start typing to filter...')
        
        self.vbox.addWidget(self.tree)
        self.vbox.addWidget(self.filterLabel)
        self.vbox.addLayout(hbox)

        self.setLayout(self.vbox)
        
        self.resize(600, 300)
        
        self.setWindowTitle('SQL Browser')

if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    ab = SQLBrowserDialog()
    
    ab.exec_()
    
    profiler.report()
    sys.exit()
    
    