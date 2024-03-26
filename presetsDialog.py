from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPen, QColor

from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QLineEdit, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QComboBox

from yaml import safe_load, dump, YAMLError #pip install pyyaml
from utils import resourcePath, log, deb

presetFile = 'presets.yaml'
presets = None

class Presets():
    '''the class does presets persistence management'''

    presets = {}                # key here - name, content - dictionary
                                # in this dict: key - host, value - list of KPIs
                                # and what do we do with variables?..

    def __init__(self):
        self.load()

    def load(self):
        log(f'Loading presets: {presetFile}')

        try:
            f = open(presetFile, 'r')
            self.presets = safe_load(f)
        except Exception as ex:
            log(f'[e] Error reading yaml file: {ex}', 1)
            return

    def persist(self):
        '''persist caurrent presets into yaml'''

        print('[persist preset]')

        for name, preset in self.presets.items():
            print(f'name: {name}')
            for kpi in preset.keys():
                print(f'    {kpi} --> {preset[kpi]}')

        try:
            f = open(presetFile, 'w')

            dump(self.presets, f, default_flow_style=None, sort_keys=False)
            f.close()
        except Exception as e:
            log('[E] presets dump issue:' + str(e))

    def get(self, name):
        return self.presets.get(name)


    def add(self, name, preset):
        print('[add]')
        print(preset)
        self.presets[name] = preset

    def list(self, host=None):

        names = []
        for name, preset in self.presets.items():
            names.append(name)
            log(f'preset name: {name}', 5)
            for kpi in preset.keys():
                log(f'    {kpi} {preset[kpi]}', 5)

        return names

    def delete(self, name):
        log(f'Delete preset: {name}')

        if name:
            del self.presets[name]

class PresetsDialog(QDialog):

    width = None
    height = None
    x = None
    y = None

    def __init__(self, hwnd, preset=None):
        super().__init__(hwnd)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);

        self.preset = preset
        self.initUI(preset)

        if preset:
            self.fillPreset(self.preset)

    def doOk(self):

        if self.preset:
            name = self.nameEdit.text().strip()
            presets.add(name, self.preset)

        presets.persist()

        self.accept()


    def fillPreset(self, preset):

        rows = []

        if not preset:
            self.presetTab.setRowCount(0)
            return

        for host in preset.keys():
            hostvalue = host    # only put host on the first line
            for kpiVar in preset[host]:
                if type(kpiVar) == list and len(kpiVar) == 2:
                    rows.append((hostvalue, kpiVar[0], kpiVar[1]))
                else:
                    rows.append((hostvalue, kpiVar, ''))

                hostvalue = ''


        self.presetTab.setRowCount(len(rows))

        for i in range(len(rows)):
            host, kpi, vars = rows[i]
            item1 = QTableWidgetItem(host)

            item2 = QTableWidgetItem(kpi)
            item3 = QTableWidgetItem(vars)

            self.presetTab.setItem(i, 0, item1)
            self.presetTab.setItem(i, 1, item2)
            self.presetTab.setItem(i, 2, item3)

        self.presetTab.resizeColumnsToContents()

    def deletePreset(self):
        i = self.nameCB.currentIndex()
        presetName = self.nameCB.itemText(i)

        if presetName:
            presets.delete(presetName)
            self.nameCB.removeItem(i)

    def presetChanged(self, i):
        name = self.nameCB.itemText(i)
        log(f'preset change: {name}', 5)

        preset = presets.get(name)

        if preset:
            self.fillPreset(preset)
        else:
            self.presetTab.setRowCount(0)
            log(f'[w] unknown preset: {name}', 2)

    def initUI(self, preset):

        iconPath = resourcePath('ico', 'favicon.png')

        nameBox = QHBoxLayout()
        vbox = QVBoxLayout()
        ocBox = QHBoxLayout()

        nameBox.addWidget(QLabel('Preset'))
        if preset:          # creating a new one
            self.nameEdit = QLineEdit()
            nameBox.addWidget(self.nameEdit)
        else:                   # manage mode
            self.nameCB = QComboBox()

            names = presets.list()
            print('names')

            for n in names:
                self.nameCB.addItem(n)

            nameBox.addWidget(self.nameCB)

            self.nameCB.currentIndexChanged.connect(self.presetChanged)

        nameBox.addStretch(1)

        self.presetTab = QTableWidget()

        self.presetTab.setColumnCount(3)

        self.presetTab.setHorizontalHeaderLabels(['Host', 'KPI', 'Variables'])

        vbox.addLayout(nameBox)
        vbox.addWidget(self.presetTab)

        okButton = QPushButton('Save')
        cButton = QPushButton('Cancel')

        okButton.clicked.connect(self.doOk)
        cButton.clicked.connect(self.reject)

        if not preset:
            # manage presets mode
            delButton = QPushButton('Delete Preset')
            delButton.clicked.connect(self.deletePreset)
            self.presetChanged(0)
            ocBox.addStretch(1)
            ocBox.addWidget(delButton)
            ocBox.addWidget(okButton)

            vbox.addWidget(QLabel('You can actually only delete presets one by one with this dialog.'))
            vbox.addWidget(QLabel('Worst case - edit presets.yaml directly.'))
            vbox.addLayout(ocBox)
            ocBox.addWidget(cButton)

        else:
            # create preset mode
            ocBox.addStretch(1)
            ocBox.addWidget(okButton)
            ocBox.addWidget(cButton)

            vbox.addLayout(ocBox)

        self.setLayout(vbox)

        self.resize(500, 300)
        self.setWindowTitle('Presets')

        if self.width and self.height:
            self.resize(self.width, self.height)

        if self.x and self.y:
            self.move(self.x, self.y)
