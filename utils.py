import sys, os, time
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QIcon

from datetime import datetime

import locale
from decimal import Decimal

from yaml import safe_load, dump, YAMLError #pip install pyyaml

logmode = 'file'
config = {}

timers = []

localeCfg = None

def timerStart():
    timers.clear()
    timers.append([time.time(), ''])
    
def timeLap(desc = None):

    if desc is None:
        desc = 't'+str(len(timers))

    timers.append([time.time(), desc])

def timePrint():

    s = []
    
    for i in range(1, len(timers)):
        s.append('%s:%s' % (timers[i][1], str(round(timers[i][0]-timers[i-1][0], 3))))

    print('timers: ', ', '.join(s))

class dbException(Exception):

    CONN = 1
    SQL = 2

    def __init__ (self, message, type = None):
        self.type = type
        super().__init__(message, type)
    
def numberToStr(num, d = 0, fix = True):

    global localeCfg

    if localeCfg is None:
        
        localeCfg = cfg('locale')
        
        try:
            locale.setlocale(locale.LC_ALL, localeCfg)
        except Exception as e:
            localeCfg = ''
            log('[!] '+ str(e))
    

    locale.setlocale(locale.LC_ALL, localeCfg)
    
    if num is None:
        return '?'
        
    fmt = '%.{0}f'.format(d)
        
    s = locale.format(fmt, num, grouping=True)
    
    return s

def numberToStrCSV(num, grp = True):

    global localeCfg

    if localeCfg is None:
        
        localeCfg = cfg('locale')
        
        try:
            locale.setlocale(locale.LC_ALL, localeCfg)
        except Exception as e:
            localeCfg = ''
            log('[!] '+ str(e))
    
    locale.setlocale(locale.LC_ALL, '')
        
    dp = locale.localeconv()['decimal_point']
    
    if num is None:
        return '?'

    #fmt = '%g'
    
    fmt = '%f'
    s = locale.format(fmt, num, grouping = grp)

    # trim ziroes for f:
    
    s = s.rstrip('0').rstrip(dp)
    
    return s

def formatTime(t):
    
    (ti, ms) = divmod(t, 1)
    
    ms = round(ms, 3)
    
    if ms == 1:
        ti += 1
        ms = '0'
    else:
        ms = str(int(ms*1000)).rstrip('0')
    
    if ti < 60:
        
        s = str(round(t, 3)) + ' s'
        
    elif ti < 3600:
        format = '%M:%S'
        msStr = '.%s' % ms
        s = time.strftime(format, time.gmtime(ti)) + msStr
    else:
        format = '%H:%M:%S'
        msStr = '.%s' % ms
        s = time.strftime(format, time.gmtime(ti)) + msStr
    
    s += '   (' + str(round(t, 3)) + ')'
    
    return s

def yesNoDialog(title, message, cancel = False):
    msgBox = QMessageBox()
    msgBox.setWindowTitle(title)
    msgBox.setText(message)

    if cancel == True:
        buttons = QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
    else:
        buttons = QMessageBox.Yes | QMessageBox.No
        
    msgBox.setStandardButtons(buttons)
    msgBox.setDefaultButton(QMessageBox.Yes)
    iconPath = resourcePath('ico\\favicon.ico')
    msgBox.setWindowIcon(QIcon(iconPath))
    msgBox.setIcon(QMessageBox.Warning)
    
    reply = msgBox.exec_()
    
    #for some reason sometimes code CONTINUES to run after this

    if reply == QMessageBox.Yes:
        return True
    elif reply == QMessageBox.No:
        return False
        
    return None
        

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
    
    config.clear()

    try: 
        f = open('config.yaml', 'r')
        config = safe_load(f)
    except:
        log('no config file? <-')
        config = {}
    
def cfg(param, default = None):

    global config

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
        
    if cfg('logmode') != 'screen':
        f = open('.log', 'a')
        f.seek(os.SEEK_END, 0)
        try:
            f.write(ts + s + nl)
        #except builtins.UnicodeEncodeError:   builtins unknown smth.
        #    f.write(ts + str(s.encode()) + nl)

        except Exception as e:
            f.write(ts + str(e) + nl)
        
        f.close()
        