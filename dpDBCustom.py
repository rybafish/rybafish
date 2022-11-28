from yaml import safe_load, YAMLError, parser

import os

from utils import log

from kpiDescriptions import createStyle, customSql, kpiGroup

# variables...
from kpiDescriptions import addVars, vrsStr, vrsStrDef, addVarsDef, addVarsRepl

from utils import Layout, cfg
from utils import customKPIException, vrsException

grouplist = {}

def scanKPIsN(hostKPIs, srvcKPIs, kpiStylesN):

    sqlFolder = cfg('customKPIsFolder', 'sql')
    
    if not os.path.isdir(sqlFolder):
        return

    dir = os.listdir(sqlFolder)
    
    grouplist['host'] = []
    grouplist['service'] = []
    
    for fl in dir:
        if os.path.isdir(os.path.join(sqlFolder,fl)):
            # process subfolders
            d2 = os.listdir(os.path.join(sqlFolder,fl))
            
            grpname = fl
            
            for yamlFile in d2:
                if yamlFile[-5:].lower() == '.yaml':
                    makeKPIsN(os.path.join(sqlFolder, fl), yamlFile, hostKPIs, srvcKPIs, kpiStylesN, grpname)
        else:
            # no subfolders
            yamlFile = fl

            #srvcKPIs.append('.Custom')
                        
            if yamlFile[-5:].lower() == '.yaml':
                makeKPIsN(os.path.join(sqlFolder), yamlFile, hostKPIs, srvcKPIs, kpiStylesN)
                

def makeKPIsN(path, file, hostKPIs, srvcKPIs, kpiStylesN, grpname = 'Custom'):
    
    log('loading custom kpis file: %s' % (os.path.join(path, file)))
    
    try: 
        f = open(os.path.join(path, file), 'r')
        
        for l in f:
            if l[0] == '\t':
                raise Exception('Please review custom KPIs documentation and YAML formatting rules.\nDo not use [TABS] to format YAML files, use spaces. Stopped loading custom KPIs.')
            
        f.seek(0, 0)
        
        kpiFile = safe_load(f)
    #except parser.ParserError as e:
    except Exception as e:
        log('Error loading custom KPI file %s: %s' %(os.path.join(path, file), str(e)), 1)
        
        raise customKPIException(str(e))
        
        
    srcIdx = file
    grpname = '.' + grpname

    vrs = {}
    
    log(f'-----> kpi file: {file}')
    
    if 'variables' in kpiFile:
    
        log('---- init dpDBCustom variables  ----')

        if 'variablesReplace' in kpiFile:
            log(f'-----> variablesReplace: {file}')
            repl = kpiFile['variablesReplace']
            
            if type(repl) == list and len(repl) == 2:
                repl = [str(x) for x in repl]
                log(f"Variables replace: '{repl[0]}' -> '{repl[1]}'")
                addVarsRepl(srcIdx, repl)
            else:
                log(f'Unexpected variablesReplace format: {repl!r}')
        else:
            log(f'-----> no variables repl: {kpiFile}')

        if srcIdx not in vrsStrDef:
            addVarsDef(srcIdx, kpiFile['variables'])
        
        log('----- addVars dpDBCustom start ----')
        #if srcIdx not in vrsStr:
        try:
            addVars(srcIdx, kpiFile['variables'], False)
        except Exception as e:
            log('[!] addVars processing error: %s: %s' % (str(type(e)), str(e)))
            raise vrsException('%s: %s' % (str(type(e)), str(e)))
            
        log('----- addVars dpDBCustom stop -----')

    kpis = kpiFile['kpis']
    
    customSql[srcIdx] = kpiFile['sql']
    
    for kpi in kpis:
        htype = kpi['type']

        csName = 'cs-' + kpi['name']
        
        if not grpname in grouplist[htype]:
            grouplist[htype].append(grpname)
            
            if htype == 'host': 
                hostKPIs.append(grpname)
            else:
                srvcKPIs.append(grpname)
        

        errorSuffix = ''
        
        while csName + errorSuffix in kpiStylesN[htype]:
            errorSuffix += '#'

        if htype == 'host': 
            hostKPIs.append(csName + errorSuffix)
        else:
            srvcKPIs.append(csName + errorSuffix)


        if errorSuffix != '':
            log('[W] custom KPI with this name already exists: %s, disabeling' % (csName))

            kpi['label'] = '[E] the KPI name must be unique! (label: %s, name: %s)' % (kpi['label'], kpi['name'])
            kpi['description'] = 'change the KPI name in YAML definition: ' + file
            
            
        style = createStyle(kpi, True, srcIdx)
        
        if style is not None:
            kpiStylesN[htype][csName + errorSuffix] = style
            
            if errorSuffix != '':
                style['disabled'] = True
