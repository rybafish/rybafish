import sys, os
from datetime import datetime

import locale
from decimal import Decimal

from yaml import safe_load, dump, YAMLError #pip install pyyaml



logmode = 'file'
config = {}

class dbException(Exception):
    pass
    
def numberToStr(num):
    '''
    num = str(num)
    l = len(num)
    
    s = ''
    
    while len(num) > 0:
        s = num[-3:] + chr(160) + s
        
        num = num[:-3]
        
    return(s[:-1])
    '''
    if cfg('locale'):
        locale.setlocale(locale.LC_ALL, cfg('locale'))
    else:
        locale.setlocale(locale.LC_ALL, '')
    
    #s = locale.format("%f", num, grouping=True)
    s = '{0:n}'.format(num)
    
    return s
    
    
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
    
def cfg(param):
    if param in config:
        return config[param]
    else:
        return None
        
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
        