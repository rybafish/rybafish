from PyQt5.QtWidgets import (QWidget, QPushButton, QDialog, QDialogButtonBox,
                             QHBoxLayout, QVBoxLayout, QApplication, QLineEdit, QLabel, QTableWidget,
                             QTableWidgetItem)

from PyQt5.QtGui import QIcon, QDesktopServices

from PyQt5.QtCore import Qt, QUrl

from utils import resourcePath
from utils import log, cfg
from utils import secondsToTime, timeToSeconds

class tzDialog(QDialog):

    def __init__(self, hwnd, ndp):
        super().__init__(hwnd)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint);

        self.ndp = ndp
        self.initUI()
        self.fillTable()
        
        
    def fillTable(self):
        self.tzTab.setRowCount(len(self.ndp))

        # populate table
        # each line directly linked to dataprovider with the same index
        # so on submit they can me linked back and updated with new TZ
        for i in range(len(self.ndp)):
            dp = self.ndp[i]
            prop = dp.dbProperties
            dpName = prop.get('dbi', '')
            dpName += ': ' + str(prop.get('tenant', ''))

            tzd = secondsToTime(prop.get('timeZoneDelta', 0))
            tss = secondsToTime(prop.get('timestampShift', 0))

            self.tzTab.setItem(i, 0, QTableWidgetItem(dpName))

            tzdItem = QTableWidgetItem(tzd)
            tzdItem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            tssItem = QTableWidgetItem(tss)
            tssItem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tzTab.setItem(i, 1, tzdItem)
            self.tzTab.setItem(i, 2, tssItem)

        self.tzTab.resizeColumnsToContents()

    def accept(self):
        '''processes the updated time zones'''
        for i in range(len(self.ndp)):
            prop = None
            dp = self.ndp[i]

            prop = dp.dbProperties
            oldTZD = prop.get('timeZoneDelta', 0)
            oldTSS = prop.get('timestampShift', 0)

            newTZD = self.tzTab.item(i, 1).text()
            newTSS = self.tzTab.item(i, 2).text()

            try:
                if newTZD.strip() == '':
                    newTZD = 0
                else:
                    newTZD = int(newTZD)
            except ValueError:
                newTZD = timeToSeconds(newTZD)
                if newTZD is None:
                    log(f'[W] incorrect time zone delta value: {newTZD}, row: {i}', 2)

            try:
                if newTSS.strip() == '':
                    newTSS = 0
                else:
                    newTSS = int(newTSS)
            except ValueError:
                newTSS = timeToSeconds(newTSS)
                if newTSS is None:
                    log(f'[W] incorrect timestamp shift value: {newTSS}, row: {i}', 2)

            if newTZD is None:
                log(f'[W] dp[{i}] {oldTZD} --> no change', 4)
            else:
                prop['timeZoneDelta'] = newTZD
                log(f'dp[{i}] {oldTZD} --> {newTZD}', 4)

            if newTSS is None:
                log(f'[W] dp[{i}] {oldTSS} --> no change', 4)
            else:
                prop['timestampShift'] = newTSS
                log(f'dp[{i}] {oldTSS} --> {newTSS}', 4)

        super().accept()

    def rybafishDotNet(self, link):
        QDesktopServices.openUrl(QUrl(link))

    def initUI(self):

        iconPath = resourcePath('ico', 'favicon.png')


        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel |
            QDialogButtonBox.Ok,
            Qt.Horizontal,
            self)


        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        vbox = QVBoxLayout()

        self.tzTab = QTableWidget()
        self.tzTab.setColumnCount(3)
        self.tzTab.setHorizontalHeaderLabels(['Data Provider', 'Time Zone Delta', 'Timestamps Shift'])

        vbox.addWidget(self.tzTab)

        vbox.addWidget(QLabel('Timestamps Shift: number of seconds to be added to compensate incorrect timestamps.'))
        vbox.addWidget(QLabel('Time Zone Delta: difference between local and dataprovider timezones.'))

        helpLabel = QLabel('\nStill not clear, need to check <a href="https://www.rybafish.net/timezones.html">help</a> page.')
        helpLabel.linkActivated.connect(self.rybafishDotNet)

        vbox.addWidget(helpLabel)

        vbox.addWidget(self.buttons)

        self.setLayout(vbox)
        
        self.setWindowIcon(QIcon(iconPath))
        
        self.setWindowTitle('Adjust data provider time zones')
        self.resize(500, 300)

if __name__ == '__main__':
    pass
