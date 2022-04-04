import sys, os, time
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QIcon

from datetime import datetime

import os

import locale

from decimal import Decimal

from yaml import safe_load, dump, YAMLError #pip install pyyaml

from binascii import hexlify

logmode = 'file'
config = {}

timers = []

localeCfg = None

def pwdunhash(pwdhsh):
    pwd = pwdhsh[5:]
    print('------', pwd)
    return pwd
    
def pwdtohash(pwd):
    pwdhsh = 'hash!' + pwd
    return pwdhsh

def hextostr(value):
    if value:
        value_str = hexlify(bytearray(value)).decode('ascii')
    else:
        value_str = 'None'
        
    return(value_str)


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
        
    return s

class cfgManager():

    configs = {}
    
    def __init__(self, ):
        from cryptography.fernet import Fernet
        
        script = sys.argv[0]
        path, file = os.path.split(script)
        
        self.fname = os.path.join(path, 'connections.yaml')
        
        self.fernet = Fernet(b'aRPhXqZj9KyaC6l8V7mtcW7TvpyQRmdCHPue6MjQHRE=')
        
        cfs = None

        self.configs = {}

        try: 
            f = open(self.fname, 'r')
            cfs = safe_load(f)
            
        except:
            log('no configs, using defaults')
            return
            
        if not cfs:
            return

        for n in cfs:
                
            confEntry = cfs[n]
            
            if 'pwd' in confEntry:
                pwd = confEntry['pwd']
                pwd = self.fernet.decrypt(pwd).decode()
                confEntry['pwd'] = pwd
                
            self.configs[n] = confEntry
        
    def updateConf(self, confEntry):
        
        
        #if confEntry['name'] in self.configs:
        #    self.configs.remove()
        
        name = confEntry.pop('name')
        
        self.configs[name] = confEntry
        
        self.dump()
        
    
    def removeConf(self, entryName):
        if entryName in self.configs:
            del self.configs[entryName]
            
        self.dump()
        
    def dump(self):

        #ds = self.configs.copy()
        
        ds = {}
        for n in self.configs:
            confEntry = self.configs[n].copy()
            if 'pwd' in confEntry:
                pwd = confEntry['pwd']
                pwd = self.fernet.encrypt(pwd.encode())
        
                confEntry['pwd'] = pwd
                
                
            if confEntry.get('dbi') == 'S2J':
                if 'pwd' in confEntry:
                    del confEntry['pwd']
                
                if 'user' in confEntry:
                    del confEntry['user']
                    
            ds[n] = confEntry

        try: 
            f = open(self.fname, 'w')
            
            dump(ds, f, default_flow_style=None, sort_keys=False)
            f.close()
        except Exception as e:
            log('layout dump issue:' + str(e))

class Layout():
    
    lo = {}
    
    def __init__ (self, mode = False):

        if mode == False:
            return

        script = sys.argv[0]
        path, file = os.path.split(script)
        
        fname = os.path.join(path, 'layout.yaml')

        try: 
            f = open(fname, 'r')
            self.lo = safe_load(f)
        except:
            log('no layout, using defaults')
            
            self.lo['pos'] = None
            self.lo['size'] = [1400, 800]
            
    def __getitem__(self, name):
        if name in self.lo:
            return self.lo[name]
        else:
            return None

    def __setitem__(self, name, value):
        self.lo[name] = value
        
    def dump(self):
        try: 
            f = open('layout.yaml', 'w')
            dump(self.lo, f, default_flow_style=None, sort_keys=False)
            f.close()
        except:
            log('layout dump issue')
            
            return False
        

class dbException(Exception):

    CONN = 1
    SQL = 2

    def __init__ (self, message, type = None):
        self.type = type
        super().__init__(message, type)

class customKPIException(Exception):

    def __init__ (self, message, type = None):
        self.type = type
        super().__init__(message, type)
    
def timestampToStr(ts, trimZeroes = True):

    if trimZeroes:
        if ts.microsecond:
            s = ts.strftime('%Y-%m-%d %H:%M:%S.%f').rstrip('0')
        else:
            s = ts.strftime('%Y-%m-%d %H:%M:%S')
    else:
        s = ts.strftime('%Y-%m-%d %H:%M:%S.%f')
        
    return s

def numberToStr(num, d = 0, fix = True):

    global localeCfg

    if localeCfg is None:
        localeCfg = cfg('locale', '')
        if localeCfg != '':
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
        
        localeCfg = cfg('locale', '')
                
        if localeCfg != '':
            try:
                print (4, localeCfg)
                locale.setlocale(locale.LC_ALL, localeCfg)
            except Exception as e:
                localeCfg = ''
                log('[!] '+ str(e))
                
    locale.setlocale(locale.LC_ALL, localeCfg)
        
    dp = locale.localeconv()['decimal_point']
    
    if num is None:
        return '?'

    #fmt = '%g'
    
    fmt = '%f'
    s = locale.format(fmt, num, grouping = grp)

    # trim ziroes for f:
    
    s = s.rstrip('0').rstrip(dp)
    
    return s

def formatTimeShort(t):
    (ti, ms) = divmod(t, 1)
    
    if ti < 60:
        
        s = str(round(t)) + ' sec'
        
    elif ti < 3600:
        format = '%M:%S'
            
        s = time.strftime(format, time.gmtime(ti))
    else:
        format = '%H:%M:%S'
        s = time.strftime(format, time.gmtime(ti))
    
    return s

def formatTime(t, skipSeconds = False, skipMs = False):
    
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

        msStr = '.%s' % ms if not skipMs else ''
            
        s = time.strftime(format, time.gmtime(ti)) + msStr
    else:
        format = '%H:%M:%S'
        msStr = '.%s' % ms if not skipMs else ''
        s = time.strftime(format, time.gmtime(ti)) + msStr
    
    if not skipSeconds:
        s += '   (' + str(round(t, 3)) + ')'
    
    return s

def yesNoDialog(title, message, cancel = False, ignore = False, parent = None):

    if parent:
        msgBox = QMessageBox(parent)
    else:
        msgBox = QMessageBox()
        
    msgBox.setWindowTitle(title)
    msgBox.setText(message)

    if cancel == True:
        buttons = QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
    elif ignore:
        buttons = QMessageBox.Yes | QMessageBox.No | QMessageBox.Ignore
    else:
        buttons = QMessageBox.Yes | QMessageBox.No
        
    msgBox.setStandardButtons(buttons)
    msgBox.setDefaultButton(QMessageBox.Yes)
    iconPath = resourcePath('ico\\favicon.png')
    msgBox.setWindowIcon(QIcon(iconPath))
    msgBox.setIcon(QMessageBox.Warning)
    
    reply = msgBox.exec_()
    
    #for some reason sometimes code CONTINUES to run after this

    if reply == QMessageBox.Yes:
        return True
    elif reply == QMessageBox.Ignore:
        return 'ignore'
    elif reply == QMessageBox.No:
        return False
        
    return None

def msgDialog(title, message):
    msgBox = QMessageBox()
    msgBox.setWindowTitle(title)
    msgBox.setText(message)

    buttons = QMessageBox.Ok
        
    msgBox.setStandardButtons(buttons)
    iconPath = resourcePath('ico\\favicon.png')
    
    msgBox.setWindowIcon(QIcon(iconPath))
    msgBox.setIcon(QMessageBox.Warning)
    
    reply = msgBox.exec_()
    
    return
        

def GB(bytes, scale = 'GB'):
    '''
        returns same number but in GB (/=1023^3)
    '''
    
    if bytes is None:
        return None
    
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
    
    script = sys.argv[0]
    path, file = os.path.split(script)
    
    cfgFile = os.path.join(path, 'config.yaml')

    config.clear()

    try: 
        f = open(cfgFile, 'r')
        config = safe_load(f)
        
        if 'raduga' not in config:
            log('raduga list of colors is not defined in config, so using a pre-defined list...', 2)
            config['raduga'] = ['#20b2aa', '#32cd32', '#7f007f', '#ff0000', '#ff8c00', '#7fff00', '#00fa9a', '#8a2be2']
    except:
        log('no config file? <-')
        config = {}
        
        return False
        
    return True
    
def cfgSet(param, value):
    global config

    config[param] = value

def cfg(param, default = None):

    global config

    if param in config:
        return config[param]
    else:
        return default
        
def log(s, loglevel = 3, nots = False, nonl = False):
    '''
        log the stuff one way or another...
    '''
    
    if cfg('loglevel', 3) < loglevel:
        return

    if not nots:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' '
    else:
        ts = ''
    
    if cfg('logmode') == 'screen' or cfg('logmode') == 'duplicate':
        print('[l]', s)
        
    if nonl:
        nl = ''
    else:
        nl = '\n'
    
    if cfg('logmode') != 'screen':
        f = open('.log', 'a')
        f.seek(os.SEEK_END, 0)
        try:
            f.write(ts + str(s) + nl)
        #except builtins.UnicodeEncodeError:   builtins unknown smth.
        #    f.write(ts + str(s.encode()) + nl)

        except Exception as e:
            f.write(ts + str(e) + nl)
        
        f.close()
        
def normalize_header(header):
    if header.isupper() and (header[0].isalpha() or header[0] == '_'):
        if cfg('lowercase-columns', False):
            h = header.lower()
        else:
            h = header
    else:
        h = '"%s"' % (header)
        
    return h
        
def securePath(filename, backslash = False):

    if filename is None:
        return None
    # apparently filename is with normal slashes, but getcwd with backslashes on windows, :facepalm:
    cwd = os.getcwd()
    
    if backslash:
        cwd = cwd.replace('\\','/') 
    
    #remove potentially private info from the trace
    fnsecure = filename.replace(cwd, '..')
    
    return fnsecure