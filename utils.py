import sys, os
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QIcon

from datetime import datetime

import locale
from decimal import Decimal

from yaml import safe_load, dump, YAMLError #pip install pyyaml

logmode = 'file'
config = {}

class dbException(Exception):
    pass
    
def numberToStr(num, d = 0):
    if cfg('locale'):
        locale.setlocale(locale.LC_ALL, cfg('locale'))
    else:
        locale.setlocale(locale.LC_ALL, '')
    
    if num is None:
        return '?'
        
    fmt = '%.{0}f'.format(d)
    s = locale.format(fmt, num, grouping=True)
    
    return s
    

def yesNoDialog(title, message):
    msgBox = QMessageBox()
    msgBox.setWindowTitle(title)
    msgBox.setText(message)
    msgBox.setStandardButtons(QMessageBox.Yes| QMessageBox.No)
    msgBox.setDefaultButton(QMessageBox.Yes)
    iconPath = resourcePath('ico\\favicon.ico')
    msgBox.setWindowIcon(QIcon(iconPath))
    msgBox.setIcon(QMessageBox.Warning)
    
    reply = msgBox.exec_()
    
    #for some reason sometimes code CONTINUES to run after this

    if reply == QMessageBox.Yes:
        return True
        
    return False
        

def GB(bytes, scale = 'GB'):
    '''
        returns same number but in GB (/=1023^3)
    '''
    
    if scale == 'MB':
        mult = 1024*1024
    elif scale == 'GB':
        mult = 1024*1024*1024
    elif scale == 'TB':
        mult = 1024*1024*1024*1024
    
    return bytes/mult
    
def antiGB(gb, scale = 'GB'):
    '''
        returns same number but in bytes (*=1023^3)
    '''
    
    if scale == 'MB':
        mult = 1024*1024
    elif scale == 'GB':
        mult = 1024*1024*1024
    elif scale == 'TB':
        mult = 1024*1024*1024*1024
    
    return gb*mult
    
    
def strftime(time):

    #ms = time.strftime('%f')
    ms = round(time.timestamp() % 1 * 10)
    str = time.strftime('%Y-%m-%d %H:%M:%S')
    
    return '%s.%i' % (str, ms)
    
    
def resourcePath(file):
    '''
        resource path calculator
        for pyinstall
    '''

    try:
        base = sys._MEIPASS
    except:
        base = '.'

    return base + '\\' + file
    
def loadConfig():

    global config

    try: 
        f = open('config.yaml', 'r')
        config = safe_load(f)
    except:
        log('no config file? <-')
        config = {}
    
def cfg(param, default = None):
    if param in config:
        return config[param]
    else:
        return default
        
def log(s, nots = False, nonl = False):
    '''
        log the stuff one way or another...
    '''
    
    if not nots:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' '
    else:
        ts = ''
    
    if cfg('logmode') == 'screen' or cfg('logmode') == 'duplicate':
        print(s)
        
    if nonl:
        nl = ''
    else:
        nl = '\n'
        
    if cfg('logmode') != 'duplicate':
        f = open('.log', 'a')
        f.seek(os.SEEK_END, 0)
        f.write(ts + str(s) + nl)
        f.close()
        