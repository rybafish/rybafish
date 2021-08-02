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
    
        print(fl)
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
        
            print(sqlFile)
        
            columns.append(sqlFile['column'])
            if sqlFile['column'] not in menu:
                menu[sqlFile['column']] = []

            menu[sqlFile['column']].append(sqlFile['name'])
            
            sqls[sqlFile['column'] + '.' + sqlFile['name']] = sqlFile['sql'].strip().rstrip(';')
