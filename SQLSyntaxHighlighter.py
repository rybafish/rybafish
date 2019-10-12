from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont
from PyQt5.QtCore import Qt, QRegExp, QRegularExpression

class SQLSyntaxHighlighter(QSyntaxHighlighter):

    def highlightBlock(self, text):
    
        kwFormat = QTextCharFormat()
        kwFormat.setFontWeight(QFont.Bold)
        kwFormat.setForeground(Qt.blue)

        rules = [
                [QRegularExpression('\\bselect\\b'),kwFormat],
                [QRegularExpression('\\border\s+by\\b'),kwFormat],
                [QRegularExpression('\\bgroup\s+by\\b'),kwFormat],
                [QRegularExpression('\\bfrom\\b'),kwFormat],
                ]
        
        for r in rules:
            (rule, format) = (r[0], r[1])
            mi = rule.globalMatch(text)
        
            while mi.hasNext():
                m = mi.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), kwFormat)