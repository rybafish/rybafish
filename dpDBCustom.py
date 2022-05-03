from yaml import safe_load, YAMLError, parser

#move to descr ------->
# from PyQt5.QtGui import QPen, QColor 
# from PyQt5.QtCore import Qt
# <------- move to descr

import os

from utils import log

from kpiDescriptions import createStyle, customSql, kpiGroup

# variables...
from kpiDescriptions import addVars, vrsStr, vrsStrDef, addVarsDef

from utils import Layout
from utils import customKPIException

grouplist = {}

def scanKPIsN(hostKPIs, srvcKPIs, kpiStylesN):
    if not os.path.isdir('sql'):
        return

    dir = os.listdir('sql')
    
    grouplist['host'] = []
    grouplist['service'] = []
    
    for fl in dir:
        if os.path.isdir(os.path.join('sql',fl)):
            # process subfolders
            d2 = os.listdir(os.path.join('sql',fl))
            
            grpname = fl
            
            for yamlFile in d2:
                if yamlFile[-5:].lower() == '.yaml':
                    makeKPIsN(os.path.join('sql', fl), yamlFile, hostKPIs, srvcKPIs, kpiStylesN, grpname)
        else:
            # no subfolders
            yamlFile = fl

            #srvcKPIs.append('.Custom')
                        
            if yamlFile[-5:].lower() == '.yaml':
                makeKPIsN(os.path.join('sql'), yamlFile, hostKPIs, srvcKPIs, kpiStylesN)
                

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
    
    if 'variables' in kpiFile:
    
        if srcIdx not in vrsStrDef:
            addVarsDef(srcIdx, kpiFile['variables'])
        
        log('-----addVars dpDBCustom -----')
        #if srcIdx not in vrsStr:
        addVars(srcIdx, kpiFile['variables'], False)
        log('-----addVars dpDBCustom -----')
    
    kpis = kpiFile['kpis']
    
    customSql[srcIdx] = kpiFile['sql']
    
    for kpi in kpis:
        type = kpi['type']

        csName = 'cs-' + kpi['name']
        
        if not grpname in grouplist[type]:
            grouplist[type].append(grpname)
            
            if type == 'host': 
                hostKPIs.append(grpname)
            else:
                srvcKPIs.append(grpname)
        

        errorSuffix = ''
        
        while csName + errorSuffix in kpiStylesN[type]:
            errorSuffix += '#'

        if type == 'host': 
            hostKPIs.append(csName + errorSuffix)
        else:
            srvcKPIs.append(csName + errorSuffix)


        if errorSuffix != '':
            log('[W] custom KPI with this already exists: %s, disabeling' % (csName))

            kpi['label'] = '[E] the KPI name must be unique! (label: %s, name: %s)' % (kpi['label'], kpi['name'])
            kpi['description'] = 'change the KPI name in YAML definition: ' + file
            
            
        style = createStyle(kpi, True, srcIdx)
        
        if style is not None:
            kpiStylesN[type][csName + errorSuffix] = style
            
            if errorSuffix != '':
                style['disabled'] = True
