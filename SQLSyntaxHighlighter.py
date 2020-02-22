from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor

import re
#from PyQt5.QtCore import Qt

class SQLSyntaxHighlighter(QSyntaxHighlighter):

    def highlightBlock(self, text):

        comments = []

        def inComment(i):
            '''
                checks if position i is inside a block comment
            '''
            for c in comments:
                if c[0] <= i <= c[1]:
                    return True
        
    
        fmKeyword = QTextCharFormat()
        fmKeyword.setFontWeight(QFont.Bold)
        fmKeyword.setForeground(QColor('#808'))

        fmComment = QTextCharFormat()
        fmComment.setForeground(QColor('#080'))

        fmLiteral = QTextCharFormat()
        fmLiteral.setForeground(QColor('#00F'))
        
        keywords = ['select', 'from', 'order', 'by', 'group', 'where', 'inner', 'left', 'right', 'join', 'as',
                    'where', 'asc', 'desc', 'case', 'when', 'else', 'and', 'or', 'like', 'round', 
                    'do', 'begin', 'end', 'then', 'if', 'between', 'having']

        rules = []
        
        startMLC = '/\\*'
        stopMLC = '/\\*'
        
        imc = 0 #in multi line comment?
        
        self.setCurrentBlockState(0)

        startIndex = 0
        
        if (self.previousBlockState() != 1):
            startIndex = text.find('/*')

        while startIndex >= 0:
           
           endIndex = text.find('*/', startIndex)
           
           if endIndex == -1:
               self.setCurrentBlockState(1)
               commentLength = len(text) - startIndex
           else:
               commentLength = endIndex - startIndex + 2
               
           self.setFormat(startIndex, commentLength, fmComment)
           
           comments.append((startIndex, startIndex+commentLength))

           startIndex = text.find('/*', startIndex + commentLength)
        
        for kw in keywords:
            rules.append(['\\b'+kw+'\\b', fmKeyword, False])

        # one line comment
        rules.append(['--.+', fmComment, True])
        
        # literals
        rules.append(['\'.+?\'', fmLiteral, False])
        rules.append(['".+?"', fmLiteral, False])
        
        for r in rules:
            (pattern, format, stop) = (r[0], r[1], r[2])

            ml = re.finditer(pattern, text, re.I )
            
            i = 0
            for m in ml:
                i += 1
                
                if not inComment(m.start(0)):
                    self.setFormat(m.start(0), len(m.group(0)), format)
                
            if i > 0 and stop:
                # do not apply other rules
                # for example in case of single line comments
                break
                

        '''
        # multiline comments
        # https://doc.qt.io/qtforpython/PySide2/QtGui/QSyntaxHighlighter.html
        
        commStart = 0
        
        if self.previousBlockState() != 1:
            mi = QRegularExpression('/\\*').globalMatch(text)
            if mi.hasNext():
                commStart = m.capturedStart()
                
        while commStart >= 0:
        '''