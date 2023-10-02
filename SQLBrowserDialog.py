import sys

from PyQt5.QtWidgets import (QPushButton, QDialog, 
    QHBoxLayout, QVBoxLayout, QApplication, QLabel, QTreeView, QStyle, QLineEdit, QStatusBar)
    
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem

import os, time

from PyQt5.QtCore import Qt, QObject, QThread

from PyQt5.QtCore import pyqtSignal, QRect, QItemSelectionModel

from utils import resourcePath
from utils import log, cfg, deb

from profiler import profiler


class descScanner(QObject):
    finished = pyqtSignal()
    
    def __init__(self, cons):
        super().__init__()
        
        self.flatStructure = None
        
    @profiler
    def updateDescriptions(self):

        for f in self.flatStructure:
            comment, offset = self.getComment(f[1], f[3])
            
            if comment:
                f[2] = comment
                f[4] = offset
                                
        self.finished.emit()

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
                                return l[2:].lstrip(), len(l)
                        
                        if mode == 2:
                            if l == '[DESCRIPTION]':
                                trigger = True
                                continue
                                
                            if trigger and l:
                                return l, None
                                                
                except StopIteration:
                    return None, None
                except Exception as e:
                    log(f'[E] {filename}:{e}', 2)
        except Exception as e:
            log(f'[E] {filename}:{e}', 2)
            
        return None, None
    

class SQLBrowser(QTreeView):

    filterUpdated = pyqtSignal()
    modelReady = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.expandedNodes = []
        
        self.folderIcon = self.style().standardIcon(QStyle.SP_DirIcon)
        self.filter = ''
        
        self.flatStructure = None
        
        item = QStandardItem('dummy')
        
        self.boldFont = item.font()
        self.boldFont.setBold(True)

        self.model = QStandardItemModel()

        self.thread = QThread()
        self.descWorker = descScanner(self)
        
        self.expanded.connect(self.nodeExpanded)
        self.collapsed.connect(self.nodeCollapsed)
        
        self.selectedPath = None        # input item (str) set in filter change/reload
        self.searchItem = None          # item detected during model build

        # one time thread init...
        self.descWorker.moveToThread(self.thread)
        self.descWorker.finished.connect(self.modelUpdated)
        self.thread.started.connect(self.descWorker.updateDescriptions)

    def nodeExpanded(self, index):
        self.expandedNodes.append(index.data(role=Qt.UserRole + 1))

    def nodeCollapsed(self, index):
        self.expandedNodes.remove(index.data(role=Qt.UserRole + 1))
    
    def resetStructure(self):
        self.flatStructure = None # need reload
        
    def modelUpdated(self):
        self.thread.quit()
        self.modelReady.emit()
        
    @profiler
    def updateModel(self):
        self.descWorker.flatStructure = self.flatStructure
        self.thread.start()
        
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
                
        deb(f'parseFlat, {folder=}', 'sqlbrowser')

        foldersAdded = []

        for (f, fpath, fdesc, fmode, offset) in files:

            if filter:
                if (
                    (f.lower().find(filter) < 0) 
                    and 
                    (fdesc is None or (fdesc is not None and fdesc.lower().find(filter) < 0))):

                    continue
                    
            #print('ok, something left:', f)
            
            deb(f'file: {f=}, {fpath=}', 'sqlbrowser')
            hier = f.split(os.sep)
            deb(f'hier: {hier}', 'sqlbrowser')
            
            for i in range(len(hier)-1):
                
                noSlice = False
                
                if hier[:i]:
                    parentPath = '\\'.join(hier[:i])
                else:
                    # avoid trailing slash
                    parentPath = ''
                
                #nodePath = folder + '\\' + '\\'.join(hier[:i+1])
                nodePath = '\\'.join(hier[:i+1])
                deb(f'{nodePath=}, {folder=}', 'sqlbrowser')

                if i < len(st):
                    if hier[i] != st[i]:
                        if len(folder) >= len(nodePath) or nodePath in foldersAdded:
                            deb(f'skip 1 {nodePath}', 'sqlbrowser')
                            continue
                        # this seem to be never reached after #879 fix``
                        deb(f'adding noSlice (never reached code?): {hier[i]=}, {parentPath=}, {nodePath=}', 'sqlbrowser')
                        noSlice = True
                        st = st[:i]
                        st.append(hier[i])
                                                
                        nodez.append((parentPath, nodePath, hier[i], None, None, None))

                else:
                    if len(folder) >= len(nodePath) or nodePath in foldersAdded:
                        deb(f'skip 2 {nodePath}', 'sqlbrowser')
                        continue

                    deb(f'adding folder {hier[i]=}, {parentPath=}, {nodePath=}', 'sqlbrowser')
                    st.append(hier[i])
                    foldersAdded.append(nodePath)
                    nodez.append((parentPath, nodePath, hier[i], None, None, None))

            if noSlice == False and i+1 < len(st):
                st = st[:i+1]

            if fpath is None:
                filename = f
            else:
                filename = fpath
            #print(f'filename: [{hier[-1]}], [{nodePath=}]]: {filename=}')
            leaves[f] = (hier[-1], nodePath, filename, fdesc, offset)
                        
        # populate leaves now:
        for file in leaves.keys():
            f = leaves[file]
            deb(f'add leaves, {file}, {f}', 'sqlbrowser')
            nodez.append((f[1], None, f[0], f[2], f[3], f[4]))

        return nodez

    @profiler
    def flatten(self, folder, files):
        '''translates flat folder to common flat structure with os.sep separators'''
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
            
            #desc = self.getComment(fold, mode=2)
            desc = None
                        
            filelist.append([fnew, fold, desc, 2, None])
        
        return filelist
            
    '''
    def updateComments(self):
        for f in self.flatStructure:
            comment = self.getComment(f[1], f[3])
            if comment is not None:
                f[2] = comment
    '''
        
    @profiler
    def flattenFolder(self, path):
        '''
            it actually builds semi-flat structure to be processed later
            each entry is ful path + file, which is essential for filtering
            
            filtering performed on this structure and actual tree model build on top
        '''
    
        flatlist = [] # [presented file name, actual name, description, comment extraction mode]
                      # presented file name - includes path that will be translated to hierarchy later (in buildModel)
                      # itmight differ from actual path based on maxdepth or specific "flat" folders tructure (flatten deals with that)
    
        for root, dirs, files in os.walk(path):
            if files:
                if self.flatFolder(files):
                    flat = self.flatten(root, files)
                    flatlist.extend(flat)
                else:
                    for f in files:
                        filename = os.path.join(root, f)
                        #desc = self.getComment(filename)
                        desc = None
                        flatlist.append([filename, filename, desc, 1, None])
                                           
        return flatlist

    @profiler
    def buildModel(self, folder='', filterStr = ''):
        '''
            builds the content of self.tree (QTreeView)
        
            if/when self.flatStructure is None - it builds it first
        '''
        #nodes = {}
        
        deb(f'build model call: {folder=}, {filterStr=}', 'sqlbrowser')
        needComments = False
        
        self.model.clear()

        #somehow this MUST be done after model.clear()
        #otherwise it resets self.flatStructure to None
        
        parentItem = self.model.invisibleRootItem()
        
        self.model.setHorizontalHeaderLabels(['File', 'Comment'])
        
        if self.flatStructure is None:
            needComments = True
            self.flatStructure = self.flattenFolder(folder)
            
        for f in self.flatStructure:
            deb(f'flatStr: {f}', 'sqlbrowser')

        filterLower = filterStr.lower()
            
        nodez = self.parseFlat(folder, self.flatStructure, filter=filterLower)

        for z in nodez:
            deb(f'nodez --> {[z[0], z[1], z[2]]}', 'sqlbrowser')
        
        parents = ['']              # stack of the parent nodes
        parentNodes = {}

        parentNodes[folder] = parentItem
        deb(f'nodes keys: {parentNodes.keys()}', 'sqlbrowser')
        
        i = 0
        rowsAdded = 0
        
        self.searchItem = None
        
        if len(nodez) == 0:
            if  filterLower:
                item1 = QStandardItem(f'no matches')
                item1.setEditable(False)
                
                item2 = None
            else:
                item1 = QStandardItem(f'[E] Nothing found in "{folder}" folder.')
                item1.setEditable(False)
                item2 = QStandardItem(f'Check the folder content and "scriptsFolder" setting value.')
                item2.setEditable(False)

            parentItem.appendRow([item1, item2])
        
        for i in range(len(nodez)):

            deb(f'i: {i}', 'sqlbrowser')

            (parent, mine, node, data, desc, offset) = nodez[i]

            deb(f'i: {i}, parent: {parent}', 'sqlbrowser')

            if parent == '':
                continue

            if parent == mine:
                continue
                
            #print(parent, mine, node)
            
            with profiler('SQLBrowser.pop'):
                while len(parent) < len(parents[-1]):
                    # one level back
                    parents.pop()

            # insert next leave
            
            #print(f'    {i:04} {node}')
            
            item = QStandardItem(node)
            item.setEditable(False)

            if filterLower and node.lower().find(filterLower) >= 0:
                item.setFont(self.boldFont)
                
            if data is None:                                #folder
                item.setIcon(self.folderIcon)
                
                item.setData(mine, role=Qt.UserRole + 1)    # required only to be able to reproduce expanded nodes
                item.setData(' - folder - ', role=Qt.UserRole + 2)    # required only to be able to reproduce expanded nodes

                if self.selectedPath == mine:
                    self.searchItem = item

                deb(f'parent: {parent}', 'sqlbrowser')
                deb(item, 'sqlbrowser')

                parentNodes[parent].appendRow(item)
                rowsAdded += 1
                parentNodes[mine] = item
                parents.append(mine)
                
                if mine in self.expandedNodes:
                    self.expand(item.index())
                
            else:
                item.setData(data, role=Qt.UserRole + 1)
                
                if self.selectedPath == data:
                    self.searchItem = item
                
                if desc:
                    itemDesc = QStandardItem(desc)
                    itemDesc.setEditable(False)
                    item.setData(offset and offset+1, role=Qt.UserRole + 2)

                    if filterLower and desc.lower().find(filterLower) >= 0:
                        itemDesc.setFont(self.boldFont)
                    
                    parentNodes[parent].appendRow([item, itemDesc])
                    rowsAdded += 1
                else:
                    parentNodes[parent].appendRow(item)
                    rowsAdded += 1
        
        self.setModel(self.model)
        
        self.setColumnWidth(0, 350)
        self.setColumnWidth(1, 200)
        #self.setColumnWidth(2, 150)
        
        
        #self.setSelection(QRect(0, 1, 3, 3), QItemSelectionModel.Select)
        #self.selectionModel().select()
        
        if self.searchItem is not None:
            pass
            #print(self.searchItem)
            #idx = self.model.index(self.searchItem, 0)
            #print(idx)
            #self.selectionModel().select(idx, QItemSelectionModel.Select  | QItemSelectionModel.Rows)
        
        if needComments:
            self.descWorker.flatStructure = self.flatStructure
            self.thread.start()

    def collapseNodes(self):
        self.expandedNodes.clear()

    def keyPressEvent(self, event):
        '''keypress on the QTreeView, actual model update to be handled by parent dialog'''
        k = event.text()

        if k.isalnum() or k == '_':
            self.filter += k
            self.filterUpdated.emit()
        elif event.key() == Qt.Key_Backspace:
            if len(self.filter) == 0:
                self.collapseAll()
                self.collapseNodes()
            else:
                self.filter = self.filter[:-1]
                
            self.filterUpdated.emit()
        else:
            super().keyPressEvent(event)
        

class QLineEditBS(QLineEdit):
    bsPressed = pyqtSignal()
    def __init__(self, parent = None):
        super().__init__(parent)
    
    def keyPressEvent (self, event):
        if event.key() == Qt.Key_Backspace:
            self.bsPressed.emit()

        super().keyPressEvent(event)
            
class SQLBrowserDialog(QDialog):

    inst = None
    layout = {}
    
    def __init__(self, parent = None):

        super(SQLBrowserDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);
        self.mode = None

        self.initUI()
        self.tree.filter = ''

        #self.insertBtn.setFocus()
        
    def restoreSelection(self):
    
        if self.tree.searchItem:
            idx = self.tree.searchItem.index()
            self.tree.scrollTo(idx)
            self.tree.selectionModel().select(idx, QItemSelectionModel.Select  | QItemSelectionModel.Rows)
        
    def filterChanged(self, s):
        '''bound to filter editbox textChanged signal'''
        self.tree.filter = s
        
        
        #self.tree.selectedPath = None
        
        model = self.tree.selectionModel()
        
        if model is not None:
            indexes = model.selectedIndexes()
            
            if len(indexes):
                idx = indexes[0]
                self.tree.selectedPath = idx.data(role=Qt.UserRole + 1)
        
        self.tree.buildModel(folder=cfg('scriptsFolder', 'scripts'), filterStr=self.tree.filter)
        if len(self.tree.filter) >= 3:
            self.tree.expandAll()
            
        self.restoreSelection()
    
    def updateFilter(self):
        '''triggered manual from keypress callback'''
        self.filterEdit.setText(self.tree.filter)
        
        # and it will trigger filterChanged itself
        return

    def bsPressed(self):
        if len(self.tree.filter) == 0:
            self.tree.collapseAll()
            self.tree.collapseNodes()
        
    def keyPressEvent(self, event):
        '''keypress anywhere on the dialog (QTreeView has very similar handler'''
    
        k = event.text()
        
        if k.isalnum() or k == '_':
            self.tree.filter += k
            self.updateFilter()
        elif event.key() == Qt.Key_Backspace:
            if len(self.tree.filter) == 0:
                self.tree.collapseNodes()
            else:
                self.tree.filter = self.tree.filter[:-1]
                
            self.updateFilter()
        else:
            super().keyPressEvent(event)
        
    @staticmethod
    def getFile(parent):
    
        posOffset = None # #663
    
        if SQLBrowserDialog.inst is None:
            sqld = SQLBrowserDialog(parent)
            SQLBrowserDialog.inst = sqld
        else:
            sqld = SQLBrowserDialog.inst
            

        sqld.restoreLayout()
        result = sqld.exec_()
        
        SQLBrowserDialog.layout['width'] = sqld.size().width()
        SQLBrowserDialog.layout['height'] = sqld.size().height()
        SQLBrowserDialog.layout['pos_x'] = sqld.pos().x()
        SQLBrowserDialog.layout['pos_y'] = sqld.pos().y()
        
        colwidth = []
        
        for i in range(2):
            colwidth.append(sqld.tree.columnWidth(i))
            
        SQLBrowserDialog.layout['col_width'] = colwidth
        
        if result == QDialog.Accepted:
            model = sqld.tree.selectionModel()
            
            if model is None:
                return (None, None, None)
                
            indexes = model.selectedIndexes()
            
            file = None
            
            if len(indexes):
                idx = indexes[0]
                file = idx.data(role=Qt.UserRole + 1)
                posOffset = idx.data(role=Qt.UserRole + 2)
                
            return (sqld.mode, file, posOffset)
        else:
            return (None, None, None)


    def insertText(self):
        self.mode = 'insert'
        self.accept()

    def newCons(self):
        self.mode = 'open'
        self.accept()
    
    def itemSelected(self, idx):
        # and the item actually ignored because it is extracted in getFile()
        if idx.data(role=Qt.UserRole + 2) == ' - folder - ':
            self.filterEdit.setText(idx.data())
            return
        
        self.mode = 'insert'
        self.accept()
        
    
    def editFile(self):
        self.mode = 'edit'
        self.accept()
        
        
    def reloadModel(self):
        #self.tree.filter = ''
        #self.updateFilter()
        
        self.tree.resetStructure() #meaning the flat structure
        
        pos = self.tree.verticalScrollBar().value()

        # get the selected item:
        model = self.tree.selectionModel()
        
        if model is not None:
            indexes = model.selectedIndexes()
            
            if len(indexes):
                idx = indexes[0]
                self.tree.selectedPath = idx.data(role=Qt.UserRole + 1)
                        
        self.tree.buildModel(folder=cfg('scriptsFolder', 'scripts'), filterStr=self.tree.filter)

        self.reloadBtn.setEnabled(False)
        self.sb.showMessage('Loading descriptions...')
        
        self.repaint()
        self.tree.verticalScrollBar().setValue(pos)
        
        self.tree.updateModel()
        
        self.restoreSelection()

    def modelReady(self):
        pos = self.tree.verticalScrollBar().value()
        
        self.tree.buildModel(folder=cfg('scriptsFolder', 'scripts'), filterStr=self.tree.filter)
        
        self.tree.repaint()
        self.tree.verticalScrollBar().setValue(pos)
        pos = self.tree.verticalScrollBar().value()
        
        self.restoreSelection()
        self.reloadBtn.setEnabled(True)
        self.sb.showMessage('Ready')
        
        
    def restoreLayout(wnd):
        if SQLBrowserDialog.layout:
            width = SQLBrowserDialog.layout.get('width', 600)
            height = SQLBrowserDialog.layout.get('height', 600)
            
            x = SQLBrowserDialog.layout.get('pos_x')
            y = SQLBrowserDialog.layout.get('pos_y')
            
            wnd.resize(width, height)
            wnd.move(x, y)

            i = 0
            for colwidth in SQLBrowserDialog.layout['col_width']:
                wnd.tree.setColumnWidth(i, colwidth)
                i += 1

        else:
            wnd.resize(600, 300)
    
        
    def initUI(self):

        iconPath = resourcePath('ico', 'favicon.ico')
        
        self.tree = SQLBrowser()
        
        self.tree.filterUpdated.connect(self.updateFilter)
        self.tree.doubleClicked.connect(self.itemSelected)
        
        self.tree.modelReady.connect(self.modelReady)
        
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
        
        self.reloadBtn = QPushButton('Reload')
        self.reloadBtn.clicked.connect(self.reloadModel)
        
        hbox.addWidget(self.insertBtn)
        hbox.addWidget(newconsBtn)
        hbox.addWidget(editBtn)
        hbox.addWidget(self.reloadBtn)
        hbox.addWidget(cancelBtn)
        
        self.filterl = QLabel('filter')
        self.filterEdit = QLineEditBS()
        self.filterEdit.textChanged.connect(self.filterChanged)
        self.filterEdit.bsPressed.connect(self.bsPressed)
        
        hboxfilter.addWidget(self.filterl, 0)
        hboxfilter.addWidget(self.filterEdit)
        hboxfilter.addStretch(10)
        
        self.vbox.addWidget(self.tree)
        self.vbox.addLayout(hboxfilter)
        self.vbox.addLayout(hbox)
        
        self.sb = QStatusBar()
        self.vbox.addWidget(self.sb)
        
        self.setLayout(self.vbox)
        
        
        self.tree.buildModel(folder=cfg('scriptsFolder', 'scripts'))
        self.sb.showMessage('Loading descriptions...')
                
        self.setWindowTitle('SQL Browser')
        

if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    ab = SQLBrowserDialog()
    
    ab.exec_()
    
    profiler.report()
    sys.exit()
