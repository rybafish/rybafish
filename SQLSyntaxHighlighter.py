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
        
        keywords = ['select', 'from', 'order\s+by', 'group\s+by', 'where', 'inner', 'left', 'right', 
                    'outer', 'join', 'as', 'on', 'with', 'distinct', 'create', 'drop', 'procedure', 'table', 'truncate', 'function',
                    'where', 'asc', 'desc', 'case', 'when', 'else', 'and', 'or', 'like', 'round', 'count', 'sum', 'min', 'max', 'avg',
                    'update', 'delete', 'insert', 'into', 'call', 'commit', 'rollback', 'alter', 'view', 
                    'do', 'begin', 'end', 'then', 'if', 'in', 'not', 'between', 'having',  'union\s+all', 'union', 'except']

        rules = []

        #check multi line comments
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

        # if the whole block is a comment - just skip the rest rules
        if len(comments) == 1:
            c = comments[0]
            if c[0] == 0 and c[1] == len(text):
                return
        
        for kw in keywords:
            rules.append(['\\b'+kw+'\\b', fmKeyword, False])

        # literals
        rules.append(['\'.*?\'', fmLiteral, False])
        rules.append(['".+?"', fmLiteral, False])

        # one line comment
        rules.append(['--.+', fmComment, True])
        
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
