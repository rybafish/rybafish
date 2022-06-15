from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor

import re

from profiler import profiler

class SQLSyntaxHighlighter(QSyntaxHighlighter):

    keywords = ['select', 'from', 'order\s+by', 'group\s+by', 'where', 'inner', 'left', 'right', 
                'outer', 'join', 'as', 'on', 'with', 'distinct', 'create', 'drop', 'procedure', 'table', 'truncate', 'function',
                'where', 'asc', 'desc', 'case', 'when', 'else', 'and', 'or', 'like', 'round', 'count', 'sum', 'min', 'max', 'avg',
                'update', 'delete', 'insert', 'into', 'call', 'commit', 'rollback', 'alter', 'view', 
                'do', 'begin', 'end', 'then', 'if', 'in', 'not', 'between', 'having',  'union\s+all', 'union', 'except']
                
    def __init__(self, prnt):
        super().__init__(prnt)
        
        self.rules = []

        fmKeyword = QTextCharFormat()
        fmKeyword.setFontWeight(QFont.Bold)
        fmKeyword.setForeground(QColor('#808'))

        self.fmComment = QTextCharFormat()
        self.fmComment.setForeground(QColor('#080'))

        fmLiteral = QTextCharFormat()
        fmLiteral.setForeground(QColor('#00F'))

        for kw in SQLSyntaxHighlighter.keywords:
            self.rules.append((re.compile('\\b'+kw+'\\b', re.I), fmKeyword, False))

        # literals
        self.rules.append((re.compile(r'\'.*?\''), fmLiteral, False))
        self.rules.append((re.compile(r'".+?"'), fmLiteral, False))

        # one line comment
        self.rules.append((re.compile(r'--.+'), self.fmComment, True))
        
    @profiler
    def highlightBlock(self, text):

        comments = []

        def inComment(i):
            '''
                checks if position i is inside a block comment
            '''
            for c in comments:
                if c[0] <= i <= c[1]:
                    return True

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
               
           self.setFormat(startIndex, commentLength, self.fmComment)
           
           comments.append((startIndex, startIndex+commentLength))

           startIndex = text.find('/*', startIndex + commentLength)

        # if the whole block is a comment - just skip the rest rules
        if len(comments) == 1:
            c = comments[0]
            if c[0] == 0 and c[1] == len(text):
                return

        for (reg, fmt, stop) in self.rules:
            #(reg, format, stop) = (r[0], r[1], r[2])

            ml = reg.finditer(text)
            
            i = 0
            for m in ml:
                i += 1
                
                if not inComment(m.start(0)):
                    self.setFormat(m.start(0), len(m.group(0)), fmt)

            if i > 0 and stop:
                # do not apply other rules
                # for example in case of single line comments
                break
