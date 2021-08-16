from yaml import safe_load, YAMLError, parser

import os

from utils import log

columns = []
menu = {}
sqls = {}

def loadSQLs():

    columns.clear()
    menu.clear()
    sqls.clear()
    
    folder = 'ContextSQLs'

    if not os.path.isdir(folder):
        log('no context sqls folder exist (%s), skipping' % folder)
        return

    dir = os.listdir(folder)
    
    path = os.path.join(folder)
    
    for fl in dir:
    
        yamlFile = fl
        
        sqlFile = None
        
        if os.path.isdir(os.path.join(folder, fl)):
            # skip folders so far
            continue
        
        if yamlFile[-5:].lower() == '.yaml':
        
            log('loading %s...' % yamlFile, 4)

            try: 
                f = open(os.path.join(path, yamlFile), 'r')
        
                sqlFile = safe_load(f)
            except Exception as e:
                log('Error loading custom SQL file %s: %s' %(os.path.join(path, yamlFile), str(e)), 1)
                
        if sqlFile:
        
            columnList = sqlFile['column']

            # convert column to a list
            if isinstance(columnList, list):
                pass
            else:
                columnList = [columnList]
                
                
            # convert sqls to a list
            sqlList = []
            
            if isinstance(sqlFile['sql'], list):
                for sql in sqlFile['sql']:
                    sqlList.append(sql.strip().rstrip(';'))
            else:
                sqlList.append(sqlFile['sql'].strip().rstrip(';'))
            
            
            
            
            for c in columnList:

                columns.append(c)

                if c not in menu:
                    menu[c] = []

                menu[c].append(sqlFile['name'])
            
                sqls[c + '.' + sqlFile['name']] = sqlList
