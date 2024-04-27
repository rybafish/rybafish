'''
    random stuff used in random places
'''
import sys, os, time
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QIcon, QColor

from PyQt5.QtCore import QMutex

from datetime import datetime

import os

import locale

from decimal import Decimal

from yaml import safe_load, dump, YAMLError #pip install pyyaml

from binascii import hexlify
from profiler import profiler

import re

from io import StringIO
import csv

config = {}
statement_hints = None

global utils_alertReg
__alertReg__ = None

timers = []

#globals:
localeCfg = None
newNumbersFormatting = True
thousands_separator = ''
decimal_point = '.'
decimal_digits = 6

cfg_logmode = 'file'
cfg_loglevel = 3
cfg_logcomp = []
cfg_servertz = None

configStats = {}

@profiler
def setTZ(ts, s):
    '''set explicit tzinfo to datetime object'''

    if type(ts) != datetime:
        log(f'[w] setTZ not a datetime object: {ts}, type: {type(ts)}', 1)
        return ts

    import datetime as dt
    tz = dt.timezone(dt.timedelta(seconds=s))
    return ts.replace(tzinfo=tz)

def getTZ(s):
    import datetime as dt
    return dt.timezone(dt.timedelta(seconds=s))


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
    path = None
    
    def encode(pwd):
        if not pwd:
            return None
        return cfgManager.fernet.encrypt(pwd.encode())

    def decode(pwd):
        if not pwd:
            return None
        return cfgManager.fernet.decrypt(pwd).decode()

    def reload(self):

        cfs = None

        self.configs = {}

        try: 
            log(f'Opening connections file: {self.fname}', 3)
            
            f = open(self.fname, 'r')
        except:
            log('Cannot open the file, using defaults...', 2)
            
            return
        
        try:
            cfs = safe_load(f)
        except:
            log('Error reading yaml file', 2)
            return
            
        if not cfs:
            return

        for n in cfs:
                
            confEntry = cfs[n]

            '''
            if 'pwd' in confEntry:
                pwd = confEntry['pwd']
                pwd = self.fernet.decrypt(pwd).decode()
                confEntry['pwd'] = pwd
            '''
                
            self.configs[n] = confEntry

    def __init__(self, fname = None):
        from cryptography.fernet import Fernet
        cfgManager.fernet = Fernet(b'aRPhXqZj9KyaC6l8V7mtcW7TvpyQRmdCHPue6MjQHRE=')

        if fname is None:
            script = sys.argv[0]
            path, file = os.path.split(script)
        
            self.fname = os.path.join(path, 'connections.yaml')
            
        else:
            self.fname = fname
            
        self.reload()
        
    def updateConf(self, confEntry):
        name = confEntry.pop('name')
        self.configs[name] = confEntry
        self.dump()
    
    def removeConf(self, entryName):
        if entryName in self.configs:
            del self.configs[entryName]
            
        self.dump()
        
    def dump(self):
        
        ds = {}
        for n in self.configs:
            confEntry = self.configs[n].copy()
            # if 'pwd' in confEntry:
                # pwd = confEntry['pwd']
                # pwd = self.fernet.encrypt(pwd.encode())
                # confEntry['pwd'] = pwd
                
            if confEntry.get('dbi') == 'S2J':
                if 'pwd' in confEntry:
                    del confEntry['pwd']
                if 'user' in confEntry:
                    del confEntry['user']

            if confEntry.get('dbi') == 'SLT':
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

class Preset():
    '''KPIs preset class with it's own persistence but no dialog yet...'''
    pass


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
        
class csvException(Exception):
    pass

class vrsException(Exception):
    def __init__ (self, message):
        super().__init__(message)

class dbException(Exception):

    CONN = 1
    SQL = 2
    PWD = 3

    def __init__ (self, message, type=None, code=None):
        '''type - internal ryba type, code = pyhdb connection code'''
        self.code = code

        if code == 414:         # pasword reset error
            log('[i] pwd reset request detected, type -> PWD', 2)
            self.type = self.PWD
        else:
            self.type = type

        self.msg = message
        super().__init__(message, type)
        
    def __str__(self):
    
        message = self.msg
        
        if self.code is not None:
            message += ', code: ' + str(self.code)
    
        return message

class customKPIException(Exception):
    def __init__ (self, message):
        super().__init__(message)
    

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
    iconPath = resourcePath('ico', 'favicon.png')
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

def msgDialog(title, message, parent=None):
    msgBox = QMessageBox(parent)
    msgBox.setWindowTitle(title)
    msgBox.setText(message)

    buttons = QMessageBox.Ok
        
    msgBox.setStandardButtons(buttons)
    iconPath = resourcePath('ico', 'favicon.png')
    
    msgBox.setWindowIcon(QIcon(iconPath))
    msgBox.setIcon(QMessageBox.Warning)
    
    reply = msgBox.exec_()
    
    return
        

@profiler
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
    
@profiler
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
    
    
@profiler
def strftime(time):

    #ms = time.strftime('%f')
    ms = round(time.timestamp() % 1 * 10)
    str = time.strftime('%Y-%m-%d %H:%M:%S')
    
    return '%s.%i' % (str, ms)
    
    
def resourcePath(folder, file):
    '''
        resource path calculator
        for pyinstall
    '''

    try:
        base = sys._MEIPASS
    except:
        base = '.'

    #return base + '\\' + file
    return os.path.join(base, folder, file)
    
def fakeRaduga():
    global config
    config['raduga'] = ['#20b2aa', '#32cd32', '#7f007f', '#ff0000', '#ff8c00', '#7fff00', '#00fa9a', '#8a2be2']
    
def loadConfig(silent=False):

    global config
    global __alertReg__
    
    script = sys.argv[0]
    path, file = os.path.split(script)
    
    cfgFile = os.path.join(path, 'config.yaml')

    config.clear()

    try: 
        f = open(cfgFile, 'r')
        config = safe_load(f)
        f.close()
        
        if 'raduga' not in config:
            log('raduga list of colors is not defined in config, so using a pre-defined list...', 2)
            fakeRaduga()
            
    except:
        if not silent:
            log('no config file? <-')
            
        config = {}
        
        return False
        
    alertStr = cfg('alertTriggerOn')

    if alertStr and alertStr[0] == '{' and alertStr[-1:] == '}':
        __alertReg__ = re.compile(r'^{' + alertStr[1:-1] + r'(:[^!]*)?(!\d{1,3})?}$')
    else:
        __alertReg__ = None
        
    return True
    
def cfgSet(param, value):
    global config

    config[param] = value

def cfgPersist(param, value, layout):
    cfgSet(param, value)
    
    if 'settings' not in layout:
        layout['settings'] = {}
        
    layout['settings'][param] = value

@profiler
def cfg(param, default = None):

    global config
    global configStats

    if configStats:
        if param in configStats:
            configStats[param] += 1
        else:
            configStats[param] = 1
    
    if param in config:
        return config[param]
    else:
        return default
        
def configReportStats():

    global configStats
    
    if not configStats:
        return
    
    params = sorted(configStats.keys(), key=lambda x: configStats[x], reverse=True)
    
    maxLen = len(max(configStats.keys(), key=lambda x: len(x)))
    numLen = len(str(configStats[params[0]]))
        
    log('Config stats:')
    log('-'*(maxLen+4+numLen+1))
    
    c = 0
    for p in params:
        log(f'{p:{maxLen+4}} {configStats[p]}')
        c += configStats[p]
        
        if configStats[p] <= 5:
            break
        
    log('-')
    log(f'Total config calls: {c}')
    log('-'*(maxLen+4+numLen+1))
    
     
def getlog(prefix):
    '''
        returns logging function with provided prefix
    '''
    pref = None
    
    pref = prefix
    def logf(s, *args, **kwargs):
        s = '[%s] %s' % (pref, s)
        
        log(s, *args, **kwargs)
    
    return logf
    
class fakeMutex():
    def tryLock(self, timeout=0):
        pass
        
    def lock(self):
        pass
        
    def unlock(self):
        pass

loadConfig(silent=True) # try to silently init config...

if cfg('threadSafeLogging', False):
    mtx = QMutex()
else:
    mtx = fakeMutex()

@profiler
def loadHints():
    global statement_hints

    if statement_hints is None:
        statement_hints = cfg('knownStatements', [])

loadHints()

@profiler
def log(s, loglevel=3, nots=False, nonl=False, component=None,):
    '''
        log the stuff one way or another...

        comp - logging component to be checked if any
    '''
    
    if cfg_loglevel < loglevel and not component:
        return

    pfx = ''

    if component:
        if cfg_logcomp and (component in cfg_logcomp or '*' in cfg_logcomp):
            pfx = f'[{component}] '
        else:
            return

    if not nots:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' '
    else:
        ts = ''
    
    if cfg_logmode == 'screen' or cfg_logmode == 'duplicate':
        print('[l]', pfx, s)
        
    if nonl:
        nl = ''
    else:
        nl = '\n'
    
    if cfg_logmode != 'screen':
    
        with profiler('log mutex lock'):
            mtx.tryLock(200)
            
        f = open('rybafish.log', 'a')
        #f.seek(os.SEEK_END, 0)
    
        try:
            f.write(ts + pfx + str(s) + nl)

        except Exception as e:
            f.write(ts + str(e) + nl)
    
        f.close()
        
        mtx.unlock()

def deb(s, comp='deb'):
    log(s, 5, component=comp)

if cfg('threadSafeLogging', False):
    log('threadSafeLogging enabled')
    mtx = QMutex()
else:
    log('threadSafeLogging disabled')
    mtx = fakeMutex()
        
def sqlNameNorm(header):
    '''
        SQL object name normalization
        lowercased alphanum --> uppercase
        quoted ones --> same
        
        if the first character is not alpha or '_' --> quotes
    '''
    def norm_one(header):
        if header.isupper():
            return header
            
        if len(header) > 2 and header[0] == '"' and header[-1] == '"':
            return header
            
        if header[0].isalpha() or header[0] == '_':
            return header.upper()
            
        return header
        
    sp = header.split('.')
    
    if len(sp) > 2:
        return sp
        
    res = []
    
    for h in sp:
        res.append(norm_one(h))
        
    return '.'.join(res)

@profiler
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
    
@profiler
def safeBool(s):
    if type(s) == str:
        return False if s.lower().strip() == 'false' else True
    else:
        return s
    
@profiler
def safeInt(s, default = 0):
    
    try:
        i = int(s)
    except ValueError as e:
        log('error converting %s to integer: %s' % (s, str(e)), 2)
        return default
        
    return i
    

@profiler
def parseAlertString(value):
    '''parses alert string to extract filename and volume
    
        format: '{alert:soundFile!volume}'
        
        soundFile is uptional, could be just a filname or path
        volume - 2-digits, will be converted to integer
        
        alert - cfg('alertTriggerOn')
        if the string is not wrapped in {} - no any parsing will be executed, only sound file will be extracted
    '''
        
    if __alertReg__ is None:
        return None, None
    
    alertStr = cfg('alertTriggerOn')
    volume = cfg('alertVolume', 80)
    vol = None
    sound = ''
    
    if value[0] == '{' and value[-1:] == '}':
        #ml = re.search('^{alert(:[^!]*)?(!\d{1,3})?}$', value)
        ml = __alertReg__.search(value)
        
        if ml is None:
            return None, None
            
        for g in ml.groups():
            if g and g[0] == ':':
                sound = g[1:]

            if g and g[0] == '!':
                vol = g[1:]
            
        if vol is not None:
            volume = int(vol)
        
    else:
        if value == alertStr:
            sound = ''
        else:
            return None, None
            
    log(f'alert parsed: {sound}/{volume}', 5)
    
    return sound, volume 
    
@profiler
def initLocale():
    '''
        sets the locale based configuration
        
        sets thousands_separator and decimal_point globals
    '''
    
    global localeCfg
    global thousands_separator
    global decimal_point
    global decimal_digits
    global newNumbersFormatting

    localeCfg = cfg('locale', '')
    if localeCfg != '':
        log(f'Locale setting to: {localeCfg}')
        try:
            locale.setlocale(locale.LC_ALL, localeCfg)
        except Exception as e:
            localeCfg = ''
            log(f'[!] Locale error: {str(e)}, {localeCfg}', 2)
            log(f'[!] List of supported locales: {str(list(locale.locale_alias.keys()))}', 2)
                
    # just once now, 2022-10-03
        
    if localeCfg == '':
        locale.setlocale(locale.LC_ALL, localeCfg)
        
    newNumbersFormatting = cfg('newNumbersFormatting', True)
        
    thousands_separator = cfg('thousandsSeparator') or locale.localeconv()['thousands_sep']
    decimal_point = cfg('decimalPoint') or locale.localeconv()['decimal_point']
    decimal_digits = cfg('decimalDigits', 6)
    
    log(f'Locale thousands separator is: [{thousands_separator}], decimal point: [{decimal_point}]')
    
def initGlobalSettings():
    global configStats
    global cfg_logmode
    global cfg_loglevel
    global cfg_logcomp
    global cfg_servertz
    
    if cfg('dev'):
        configStats['dummy'] = 0
        
    cfg_logmode = cfg('logmode')
    cfg_loglevel = cfg('loglevel', 3)
    cfg_logcomp = cfg('log_components', [])
    cfg_servertz = cfg('serverTZ', True)

    if type(cfg_logcomp) != list:
        cfg_comp = []

    if cfg_logcomp:
        log(f'logging components list: {cfg_logcomp}', 2)
    
    initLocale()
    
initGlobalSettings()
    
def intToStr(x, grp = True):
    #only integers, only >= 0
    
    #separator = '\xa0'
    global thousands_separator
    
    if grp == False:
        return str(x)
    
    #print('int processing:', x)

    '''
    if type(x) is not int:
        raise TypeError(f'Not an integer: {x}, {type(x)}')
    '''

    if x < 1000:
        return str(x)
    else:
        x, r = divmod(x, 1000)
        #return intToStr(x) + '\xa0' + str(r)
        #x, r = divmod(x, 1000)
        #return intToStr(int(x/1000)) + '\xa0' + '%03d' % (x % 1000)    
        return f'{intToStr(x)}{thousands_separator}{r:03}'

def saneNumberToStr(x, grp=True, digits=None):

    global decimal_point
            
    #bkp = x
    
    if x < 0:
        x = -x
        sign = '-'
    else:
        sign = ''
    
    fr = x%1
    x = int(x)
    
    #print(f'{bkp} ==> sign:{sign} int: {x} dec: {fr}, {grp=}, {digits=}')
    
    if fr:
        if digits:
            frs = decimal_point + f'{fr:.{digits}f}'[2:]        # duplicated formula, but a bit different case
        elif digits == 0:
            frs = ''
        else:
            frs = decimal_point + f'{fr:.{decimal_digits}f}'.rstrip('0').rstrip(decimal_point)[2:]
    else:
        if digits:
            frs = decimal_point + f'{fr:.{digits}f}'[2:]        # duplicated formula, but a bit different case
        else:
            frs = ''
    
    #print(f'{bkp} --> int={intToStr(x, grp)}, dec:{frs}')
            
    return sign + intToStr(x, grp) + frs

@profiler
def numberToStrCSV(num, grp = True):
    '''
        formats numbers according to locale
            - thouthand groupping
            - decimal point
            - truncates zeroes in the end of the fractional
    '''
    
    global newNumbersFormatting
    
    if newNumbersFormatting:
        return saneNumberToStr(num, grp)

    global localeCfg
    global thousands_separator
    global decimal_point
    
    '''
    if localeCfg is None:
        
        localeCfg = cfg('locale', '')
                
        if localeCfg != '':
            try:
                locale.setlocale(locale.LC_ALL, localeCfg)
            except Exception as e:
                localeCfg = ''
                log('[!] '+ str(e))
                
        # just once now, 2022-10-03
        locale.setlocale(locale.LC_ALL, localeCfg)
    '''
    
    if localeCfg is None:
        initLocale()
        
    
    if num is None:
        return '?'

    #fmt = '%g'

    fmt = '%f'
    s = locale.format_string(fmt, num, grouping = grp)
    
    # trim zeroes for f, even integers have .000000 after %f formatting
    
    s = s.rstrip('0').rstrip(decimal_point)

    
    return s

@profiler
def numberToStr(num, d=0):
    '''
        in consoles it is used for integer type only
        for decimals numberToStrCSV used (for some reason)
        
        never used for copy
        
        this one is very straight-forward:
        when d is not zero - it will result in fixed number of digits after decimal point
        
        allways uses thouthands groupping
        mainly used for charts, not results render
    '''

    global newNumbersFormatting

    if newNumbersFormatting:
        return saneNumberToStr(num, grp=True, digits=d)
        
    global localeCfg
    global thousands_separator
    global decimal_point

    '''
    if localeCfg is None:
        localeCfg = cfg('locale', '')
        if localeCfg != '':
            log(f'Locale setting to: {localeCfg}')
            try:
                locale.setlocale(locale.LC_ALL, localeCfg)
            except Exception as e:
                localeCfg = ''
                log(f'[!] Locale error: {str(e)}, {localeCfg}', 2)
                log(f'[!] List of supported locales: {str(list(locale.locale_alias.keys()))}', 2)
                
        # just once now, 2022-10-03
        locale.setlocale(locale.LC_ALL, localeCfg)
        thousands_separator = locale.localeconv()['thousands_sep']
        decimal_point = locale.localeconv()['decimal_point']
        log(f'Locale thousands separator is: [{thousands_separator}], decimal point: [{decimal_point}]')
    '''
    if localeCfg is None:
        initLocale()
    
    if num is None:
        return '?'
        
    fmt = '%.{0}f'.format(d)
        
    s = locale.format_string(fmt, num, grouping=True)
    
    #print(f'{num} --> {s}')
    
    return s

@profiler
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

def formatTimeus(us):
    '''return formatted time in microsec'''
    if us is None:
        return ''

    s = numberToStr(us) + ' ' + chr(181) + 's'
    return s

@profiler
def formatTime(t, skipSeconds=False, skipMs=False):
    
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
        s = ''
        msStr = '.%s' % ms if not skipMs else ''
        if ti >= 3600*24:
            days, ti = divmod(ti, 3600*24)
            days = int(days)
            s = f'{days}D '

        s += time.strftime(format, time.gmtime(ti)) + msStr

    if not skipSeconds:
        s += '   (' + str(round(t, 3)) + ')'
    
    return s

@profiler
def timestampToStr(ts, trimZeroes = True):

    if trimZeroes:
        if ts.microsecond:
            s = ts.strftime('%Y-%m-%d %H:%M:%S.%f').rstrip('0')
        else:
            s = ts.strftime('%Y-%m-%d %H:%M:%S')
    else:
        s = ts.strftime('%Y-%m-%d %H:%M:%S.%f')
        
    return s

@profiler
def alignTypes(rows):
    '''
        scan through rows and detect types, perform conversion when required
        Main usage is SQLite output that can in fact return strings and integers in the same column
        and, by the way it is not aware of timestamps and has them as string.
        
        So the values in rows array are already in correct types but might be inconsistent.
        
        rows do not have header, data only
        
        if column values detected inconsistent - will be converted to detected type
        right in rows array (inplase)
        
        returns list of (type, length) tuples per column:
        
            1 - int
            2 - decimal
            3 - string
            4 - timestamp
        
        length defined only for str type columns (type 3)
    '''

    def check_timestamp(v):
        
        try:
            # v = datetime.fromisoformat(v)
            v = extended_fromisoformat(v)
            # log(f'is timestamp? {v} (yes)', 5)
        except ValueError:
            # log(f'is timestamp? {v} (NO)', 5)
            return False
            
        return True
        
    def detectType(t):
        # log(f'detectType: {str(t)[:8]}, {type(t)} {len(str(t))}', 6)
        
        if type(t) == int:
            return 'int'
            
        if type(t) == float:
            return 'decimal'

        if type(t) == str:
            if check_timestamp(t):
                return 'timestamp'
            else:
                return 'varchar'
            
        return ''
    
    if not rows:
        return None
        
    colNum = len(rows[0])
    columnTypes = []
    
    for idx in range(colNum):

        columnType = None
        maxLen = None
        needsConversion = False
        
        maxTempLen = 0
        i = 0
        jdeb = 0
        
        # log(f'column {idx}, {columnType=}', 6)
        for r in rows:
            v = r[idx]

            # log(f'row {jdeb}, value : {v}', 6)
            jdeb += 1
            
            if columnType != 'varchar':
                t = detectType(v)
                # cannot break as we also calculate maxlenth here below (maxTempLen)

            # log(f'1. {columnType=}, {t=}', 6)

            # if columnType == 'varchar' and t != 'varchar':
            #     needsConversion = True

            if columnType is None:
                columnType = t
                maxTempLen = 0
                continue
             
            # log specific column
            #if idx == 0:
            #    log(f'column 0, {v=}, {t=}, {needsConversion=}')

            #if columnType == 1 and (t == 2):
                # requires conversion from int to float, who cares.
            
            if columnType == 'int' and (t == 'varchar'):
                #downgrade to str
                needsConversion = True
                columnType = t
                
                log(f'column #{idx} downgraded to varchar because of row {i}, value = "{v}"', 5)
                log(f'row: {r}', 5)
                break
                
            if columnType == 'int' and v:
                maxTempLen = abs(v)

            # log(f'2. {columnType=}, {t=}', 6)

            if columnType == 'varchar' and (t == 'decimal' or t == 'int'):
                needsConversion = True
                break

            if columnType == 'varchar' and (type(v) == float or type(v) == int):
                needsConversion = True
                break

            if columnType == 'timestamp' and (t == 'varchar' or t == ''):
                needsConversion = True
                break

            if columnType == 'varchar' and v:
                maxTempLen = len(v)

            if columnType == '':
                break
        else:
            maxLen = maxTempLen

        # log(f'type detected: {columnType}, {needsConversion=}, {maxLen=}', 6)
                
        if needsConversion == True:
            maxLen = 0
            log(f'Need to convert column {idx} to str', 5)
            with profiler('SQLite column convertion'):
                for r in rows:
                    if type(r[idx]) != str:
                        # log(f'Convert: {r[idx]} ({type(r[idx])})', 5)
                        r[idx] = str(r[idx])
                    else:
                        pass
                        
                    strLen = len(r[idx])
                    
                    if strLen > maxLen:
                        maxLen = strLen 
                        
            columnType = 'varchar'
        
        if columnType == 'timestamp' and t == 'timestamp':
            # meaning the whole column was timestamp...
            for r in rows:
                # r[idx] = datetime.fromisoformat(r[idx])
                r[idx] = extended_fromisoformat(r[idx])
                
        columnTypes.append((columnType, maxLen))
                
    return columnTypes

@profiler
def detectConvert(rows):
    '''
        input - 2dim array of string values
        
        the method will try to
            1) detect integer, decimal, timestamp types
            2) convert the whole column to this type
            
        returned list of tuples: type, length
    '''
    
    pass

@profiler
def extended_fromisoformat(v):
    '''
        this is a bit extended version of the standard fromisoformat
        which also tries to parse values like 2022-12-04 19:56:34.12
        standard one will fail because it requres exactly 3 or 6 digits after dot
        
        current version only supports <6 digits after dot
    '''
    try:
        # return datetime.fromisoformat(v)
        return datetime.strptime(v, '%Y-%m-%d %H:%M:%S.%f')

    except ValueError:
        if v.find('.') == -1:
            v += '.000'

        else:
            decimals = v.split('.')[1]
            dec_len = len(decimals)

            if dec_len > 6:
                truncate = dec_len - 6
                v = v[:-truncate] # truncate everything after 6 digit


        return datetime.strptime(v, '%Y-%m-%d %H:%M:%S.%f')

        raise ValueError

        '''
        #old implementation

        if len(v) <3:
            raise ValueError
            
        if (v[-1].isnumeric() and v[-2] == '.'):
            return datetime.fromisoformat(v + '00')
        elif v[-1].isnumeric() and v[-2].isnumeric() and v[-3] == '.':
            return datetime.fromisoformat(v + '0')
            
        raise ValueError
        '''

def parseCSV(txt, delimiter=',', trim=False):
    '''
        it takes all the values = strings as input and tries to detect
        if the column might be an integer or a timestamp
        
        if all the values in the column are recognized specific type - the whole
        column will be converted to that type

        ! also builds self.types list
    
        Note: local rows but self.types here!
        
        Returns:
            cols - list of tuples: (name, type, length)
                types: strings 'int', 'timestamp', 'varchar'
            
            rows - regular list of lists, 2-dim array of values (converted to proper types
    '''

    '''
        this is almost 100% copy of def parseResponce(self, resp) with the following changes:

        it does not use self.types, just types variable
        it returns cols, rows (not just rows)
    '''

    def convert_types():
        '''
            performs conversion of rows array
            based on types list
            
            returns list of maxlen for varchars
        '''
        
        maxlenlist = []
        
        for c in range(len(types)):
            ml = 0
            
            for i in range(len(rows)):
                if types[c] == 'int':
                    rows[i][c] = int(rows[i][c])
                    if ml < abs(rows[i][c]):
                        ml = abs(rows[i][c])
                elif types[c] == 'timestamp':
                    #rows[i][c] = datetime.fromisoformat(rows[i][c])
                    rows[i][c] = extended_fromisoformat(rows[i][c])
                elif types[c] == 'varchar':
                    if ml < len(rows[i][c]):
                        ml = len(rows[i][c])
                else:
                    pass
                    
            if types[c] in ('varchar', 'int'):
                maxlenlist.append(ml)
            else:
                maxlenlist.append(None)
                
        return maxlenlist
    
    @profiler
    def check_integer(j):
        log(f'check column #{j} ({header[j]}) for int, {trim=}', 5)
        
        reInt = re.compile(r'^-?\d+$')
        
        for ii in range(len(rows)):
            if not reInt.match(rows[ii][j]):
                log(f'not a number: row: {ii}, col: {j}: "{rows[ii][j]}"', 5)
                log(f'not a number, row for the reference: {str(rows[ii])}', 5)
                return False
                
        return True
        
    def check_timestamp(j):
            
        log(f'check column {j} for timestamp, {trim=}', 5)
        
        for ii in range(len(rows)):
            try:
                v = extended_fromisoformat(rows[ii][j])
            except ValueError:
                log('not a timestamp: (%i, %i): %s' % (ii, j, rows[ii][j]), 5)
                return False
                
        return True
            
    f = StringIO(txt)
    reader = csv.reader(f, delimiter=delimiter)
    
    rows = []
    
    try:
        header = next(reader)
    except StopIteration:
        raise csvException('The input seems to be empty, nothing to process.')
    
    log('header:' + str(header), 5)
    
    numCols = len(header)
    
    i = 0 
    for row in reader:
        i+=1
        if len(row) != numCols:
            raise csvException(f'Unexpected number of values in row #{i}: {len(row)} != {numCols}')

        if trim:
            rows.append([x.strip() for x in row ])
        else:
            rows.append(row)

    types = ['']*numCols
    
    #detect types
    for i in range(numCols):
        if check_integer(i):
            types[i] = 'int'
        elif check_timestamp(i):
            types[i] = 'timestamp'
        else:
            types[i] = 'varchar'
    
    lenlist = convert_types()
    
    #log('types:' + str(types), 5)
    #log('lenlist:' + str(lenlist), 5)
    
    if len(rows) > 1:
        log('row sample:' + str(rows[1]), 5)
        
    # prepare cols list --> difference with dbi_st04 implementation
    
    cols = []
    for i in range(numCols):
        cols.append((header[i], types[i], lenlist[i]))
    
    for c in cols:
        l = f'({c[2]})' if c[2] is not None else ''
        log(f'{c[0]}, {c[1]}{l}', 5)
        
    return cols, rows

def escapeHtml(msg):
    return msg.replace('&', '&amp;').replace('>', '&gt;').replace('<', '&lt;').replace('\'','&#39;').replace('"','&#34;')

@profiler
def turboClean():
    # this one only calls size-based cleanup (mode 0)

    if cfg('doNotTurboClean', False):
        return

    logsize = None

    try:
        st1 = os.stat('rybafish.log')
        logSize = st1.st_size
    except FileNotFoundError:
        pass

    purgeLogs(mode=0, sizeKnown=logSize)

def purgeLogs(mode, sizeKnown=None):

    fname = 'rybafish.log'
    # this one was way too slow
    def seekLines_DEPR(num):
        lineSeek = {}
        seek = None
        i = 0

        try:
            with open(fname, 'r') as f:
                l = f.readline()
                while l:
                    lineSeek[i] = seek
                    seek = f.tell()
                    l = f.readline()
                    i += 1
        except:
            return None

        if i - num > 0:
            return lineSeek[i-num]
        else:
            return None

    def seekConfig_DEPR():      # 818
        seek = None
        try:
            with open(fname, 'r') as f:
                l = f.readline()
                while l:
                    if len(l) > 48 and l[20:48] == 'after connection dialog conn':
                        seek = f.tell()
                    l = f.readline()
        except:
            return None

        log('mode 13 turboclean detected...', 5)
        return seek

    def seekSize(size, size2):
        '''
            size - top limit for the log size
                    the same chunk size used to scan lines

            size2 - this is the size of the log after truncation
                    size2 supposed to be less then size itself
                    otherwise the seekSize will be executed each time
                    and we don't want that, right?


        '''
        def printLines(i):
            print(f'{i}, {lines1=}')
            print(f'{i}, {lines2=}')
            print(f'{i}, {lines3=}')


        assert size > size2, f'incorrect seekSize call, {size}<{size2}'

        seek = None
        fsize = 0

        try:
            with open(fname, 'r') as f:
                lines1 = f.readlines(size)
                lines2 = f.readlines(size)
                lines3 = f.readlines(size)

                while lines3:
                    lines1 = lines2
                    lines2 = lines3
                    lines3 = f.readlines(size)
                    if not lines3:
                        break

                fsize = f.tell()
        except:
            return None

        if fsize < size:
            return None

        if len(os.linesep) > 1: #compensate damn windows \r\n...
            eolSize = 1
        else:
            eolSize = 0

        lines = lines1 + lines2
        seekback = 0

        for i in range(len(lines)-1, -1, -1):
            l = lines[i]
            seekback += len(l) + eolSize
            if seekback > size2:
                break

        seek = fsize - seekback

        return seek

    seek = None

    if mode == 13:
        # seek = seekConfig() # 818
        if os.path.exists('.log'):
            os.remove('.log')
    else:
        s1 = cfg('logSizeMax', 10*1024**2)
        s2 = cfg('logSizeTarget', 1*1024**2)

        if type(s1) != int or type(s2) != int or (s1 != 0 and s1 <= s2):
            s1, s2 = 10*1024**2, 1*1024**2

        if s1 != 0 and sizeKnown is not None and sizeKnown >= s1: # also checks current log size
            log(f'turboclean check: {s1}/{s2}, size={sizeKnown}...', 5)
            seek = seekSize(s1, s2)

    if not seek:
        return

    log(f'turboclean seek({numberToStr(seek)})', 4)
    # scanning...
    lines = []
    with open(fname, 'r') as f:
        f.seek(seek)
        lines = f.readlines()

    # writing...
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(fname, 'w') as f:
        f.writelines([f'...truncated on {ts}...\n'])
        f.writelines(lines)
        log(f'turboclean written: ({numberToStr(f.tell())})', 4)

def secondsToTime(sec):
    '''converts seconds to hh:mm format
    if %60 != 0 - leaves as is, seconds, but returns str'''

    if sec < 0:
        sec = -sec
        sign = '-'
    else:
        sign = ''

    s = time.strftime('%H:%M:%S', time.gmtime(sec))
    return sign+s

def secondsToTZ(sec):
    if sec < 0:
        sec = -sec
        sign = '-'
    else:
        sign = '+'

    if sec %1800 == 0:
        s = time.strftime('%H:%M', time.gmtime(sec))
    else:
        s = secondsToTime(sec)

    return sign + s

def timeToSeconds(s):
    g = re.search(r'(-?)(\d\d?):(\d\d):(\d\d)', s)

    if not g:
        return None

    s = g[1]
    hh = int(g[2])
    mm = int(g[3])
    ss = int(g[4])

    sec = hh*3600 + mm*60 + ss

    if s:
        return -sec
    else:
        return sec

def colorMix(c1, c2):
    (r1, g1, b1) = (c1.red(), c1.green(), c1.blue())
    (r2, g2, b2) = (c2.red(), c2.green(), c2.blue())

    r = int((r1 + r2)/2)
    g = int((g1 + g2)/2)
    b = int((b1 + b2)/2)

    return QColor(r, g, b)

def colorDarken(c, d):
    (r, g, b) = (c.red(), c.green(), c.blue())

    r = int(r * d)
    g = int(g * d)
    b = int(b * d)

    return QColor(r, g, b)

def pwd_escape(value):
    ESCAPE_REGEX = re.compile(r'["]')
    ESCAPE_MAP = {'"': '""'}

    return "%s" % ESCAPE_REGEX.sub(
        lambda match: ESCAPE_MAP.get(match.group(0)),
        value
    )
