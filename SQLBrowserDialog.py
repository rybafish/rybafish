import sys

from PyQt5.QtWidgets import (QPushButton, QDialog, 
    QHBoxLayout, QVBoxLayout, QApplication, QLabel, QTreeView, QStyle, QLineEdit)
    
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem

import os, time

from PyQt5.QtCore import Qt

from PyQt5.QtCore import pyqtSignal

from utils import resourcePath
from utils import log, cfg

from profiler import profiler
    
class SQLBrowser(QTreeView):

    filterUpdated = pyqtSignal()

    def __init__(self, folder=cfg('scriptsFolder', 'scripts')):
        super().__init__()
        
        self.folderIcon = self.style().standardIcon(QStyle.SP_DirIcon)
        self.filter = ''
        
        self.flatStructure = None
        
        item = QStandardItem('dummy')
        
        self.boldFont = item.font()
        self.boldFont.setBold(True)

        self.model = QStandardItemModel()
        self.buildModel(folder)
        

    def flatFolder(self, files):
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
    def parseFlat(self, folder, files, filter=''):
        '''
            method deals with flat files structure based on os.sep
            
            returns nodez structure - ready to be used for populating tree
        '''
    
        st = []
        
        leaves = {}
        nodez = []
    
        j = 0
        for (f, fpath, fdesc) in files:
        
            if filter and f.lower().find(filter) < 0 and fdesc and fdesc.lower().find(filter) < 0:
                continue
                                
            hier = f.split(os.sep)
            
            for i in range(len(hier)-1):
                
                noSlice = False
                
                '''
                if hier[:i]:
                    parentPath = folder + '\\' + '\\'.join(hier[:i])
                else:
                    # avoid trailing slash
                    parentPath = folder
                '''

                if hier[:i]:
                    parentPath = '\\'.join(hier[:i])
                else:
                    # avoid trailing slash
                    parentPath = ''
                
                #nodePath = folder + '\\' + '\\'.join(hier[:i+1])
                nodePath = '\\'.join(hier[:i+1])
                
                if i < len(st):
                    if hier[i] != st[i]:
                        noSlice = True
                        st = st[:i]
                        st.append(hier[i])
                                                
                        nodez.append((parentPath, nodePath, hier[i], None, None))

                else:
                    st.append(hier[i])
                                        
                    nodez.append((parentPath, nodePath, hier[i], None, None))
                    
            if noSlice == False and i+1 < len(st):
                st = st[:i+1]

            if fpath is None:
                filename = f
            else:
                filename = fpath
            #print(f'filename: [{hier[-1]}], [{nodePath=}]]: {filename=}')
            leaves[f] = (hier[-1], nodePath, filename, fdesc)
                        
        # populate leaves now:
        for file in leaves.keys():
            f = leaves[file]
            nodez.append((f[1], None, f[0], f[2], f[3]))
            
        return nodez

    @profiler
    def flatten(self, folder, files):
        maxdepth = 2
        prefix = 'HANA_'
        sep = '_'
        
        filelist = []
        
        for f in files:

            if f[0:len(prefix)] != prefix:
                continue

            fmod = f[len(prefix):]
                
            hier = fmod.split(sep, maxdepth)
            
            fold = os.path.join(folder, f)
            
            fnew = os.sep.join(hier)
            fnew = os.path.join(folder, fnew)
            
            desc = self.getComment(fold, mode=2)
                        
            filelist.append((fnew, fold, desc))
        
        return filelist
           
    @profiler
    def getComment(self, filename, mode=1):
    
        trigger = False

        try:
            with open(filename) as f:
                try:
                    
                    for i in range(16):
                    
                        l = next(f)
                        l = l.strip()
                        
                        if mode == 1:
                            if l[0:2] == '--':
                                return l[2:].lstrip()
                        
                        if mode == 2:
                            if l == '[DESCRIPTION]':
                                trigger = True
                                continue
                                
                            if trigger and l:
                                return l
                                                
                except StopIteration:
                    return None
                except Exception as e:
                    log(f'[E] {filename}:{e}', 2)
        except Exception as e:
            log(f'[E] {filename}:{e}', 2)
            
    @profiler
    def flattenFolder(self, path):
        '''
            it actually builds semi-flat structure to be processed later
            each entry is ful path + file, which is essential for filtering
            
            filtering performed on this structure and actual tree model build on top
        '''
    
        flatlist = []
    
        for root, dirs, files in os.walk(path):
            if files:
                if self.flatFolder(files):
                    flat = self.flatten(root, files)
                    flatlist.extend(flat)
                else:
                    for f in files:
                        filename = os.path.join(root, f)
                        desc = self.getComment(filename)
                        flatlist.append((filename, None, desc))
                   
        return flatlist

    @profiler
    def buildModel(self, folder='', filter = ''):
    
        #nodes = {}

        self.model.clear()
        parentItem = self.model.invisibleRootItem()
        
        #self.model.setHorizontalHeaderLabels(['sql', 'size', 'date'])
        self.model.setHorizontalHeaderLabels(['File', 'Comment'])
        
        #xxx

        if self.flatStructure is None:
            self.flatStructure = self.flattenFolder(folder)
            
        nodez = self.parseFlat(folder, self.flatStructure, filter=filter)
        
        parents = ['']              # stack of the parent nodes
        parentNodes = {}

        parentNodes[folder] = parentItem
        
        i = 0
        
        for i in range(len(nodez)):

            (parent, mine, node, data, desc) = nodez[i]

            if parent == '':
                continue

            if parent == mine:
                continue
                
            #print(parent, mine, node)
            
            with profiler('pop'):
                while len(parent) < len(parents[-1]):
                    # one level back
                    parents.pop()

            # insert next leave
            
            item = QStandardItem(node)
            item.setEditable(False)

            if filter and node.lower().find(filter) >= 0:
                item.setFont(self.boldFont)
                
            if data is None:
                item.setIcon(self.folderIcon)

                parentNodes[parent].appendRow(item)
                parentNodes[mine] = item
                parents.append(mine)
            else:
                item.setData(data, role=Qt.UserRole + 1)
                
                if desc:
                    itemDesc = QStandardItem(desc)
                    itemDesc.setEditable(False)

                    if filter and desc.lower().find(filter) >= 0:
                        itemDesc.setFont(self.boldFont)
                    
                    parentNodes[parent].appendRow([item, itemDesc])
                else:
                
                    parentNodes[parent].appendRow(item)
        
        self.setModel(self.model)

        self.setColumnWidth(0, 350)
        self.setColumnWidth(1, 200)
        #self.setColumnWidth(2, 150)

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
        
    def filterChanged(self, s):
        self.tree.filter = s
        
        self.tree.buildModel(folder=cfg('scriptsFolder', 'scripts'), filter=self.tree.filter)
        if len(self.tree.filter) >= 3:
            self.tree.expandAll()
    
    def updateFilter(self):
        self.filterEdit.setText(self.tree.filter)
        
        self.tree.buildModel(folder=cfg('scriptsFolder', 'scripts'), filter=self.tree.filter)
        if len(self.tree.filter) >= 3:
            self.tree.expandAll()

    def keyPressEvent(self, event):
    
        k = event.text()
        
        if k.isalnum() or k == '_':
            self.tree.filter += k
            self.updateFilter()
        elif event.key() == Qt.Key_Backspace:
            self.tree.filter = self.tree.filter[:-1]
            self.updateFilter()
        else:
            super().keyPressEvent(event)
        
        
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
        self.tree.filter = ''
        self.updateFilter()
        
        self.tree.flatStructure = None # need reload
        self.tree.buildModel(folder=cfg('scriptsFolder', 'scripts'), filter=self.tree.filter)
        self.repaint()

    def initUI(self):

        iconPath = resourcePath('ico\\favicon.ico')
        
        self.tree = SQLBrowser()
        
        self.tree.filterUpdated.connect(self.updateFilter)
        self.tree.doubleClicked.connect(self.itemSelected)
        
        self.vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hboxfilter = QHBoxLayout()
        
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
        
        self.filterl = QLabel('filter')
        self.filterEdit = QLineEdit()
        self.filterEdit.textChanged.connect(self.filterChanged)
        
        hboxfilter.addWidget(self.filterl, 0)
        hboxfilter.addWidget(self.filterEdit)
        hboxfilter.addStretch(10)
        
        self.vbox.addWidget(self.tree)
        self.vbox.addLayout(hboxfilter)
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
    
    