import sys
import os
from PyQt5.QtCore import noshowbase
from yaml import safe_load, dump, YAMLError #pip install pyyaml
from utils import deb, log, cfg
import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken

# singleton in fact
class cfgManager():

    configs = {}
    path = None
    salt = None
    
    def encode(self, pwd):
        if not pwd:
            return None
        pwdenc = self.fernet.encrypt(pwd.encode())
        deb(f'pwd encode: {pwdenc}', '_pwd')
        return pwdenc
        # return cfgManager.fernet.encrypt(pwd.encode())

    def decode(self, pwd, silent=False):
        
        if not pwd:
            return None

        deb(f'pwd decode: {pwd}', '_pwd')

        pwddec = None
        try:
            pwddec = self.fernet.decrypt(pwd).decode()
        except InvalidToken :
            if not silent:
                deb(f'[W] decode error: Invalid token', '_pwd')
                log(f'[W] password hash decode error: Invalid token. Wrong master password?', 2)
            return None
            
        return pwddec

    def testFernet(self):

        ok = ''
        total = 0
        failed = 0
        
        for cName in self.configs:
            cfg = self.configs[cName]

            if 'pwd' in cfg:
                total += 1

                if self.decode(cfg['pwd']):
                    ok = 'ok'
                else:
                    failed += 1
                    ok = 'nope'

                deb(f'cfg: {cName} - with pwd: {ok}', '_pwd')
            else:
                deb(f'cfg: {cName} - no pwd', '_pwd')


        deb(f'total/failed: {total}/{failed}')
        return (total, failed)
            
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
        except Exception as ex:
            log(f'Error reading yaml file: {ex}', 2)
            return
            
        if not cfs:
            return

        for n in cfs:

            if n == '__salt__':
                slt = cfs[n]

                if slt == '':
                    deb(f'This connections.yaml is NOT salty: {slt}', '_pwd')
                    self.salt = ''
                else:
                    deb(f'This connections.yaml IS salty: {slt}', '_pwd')
                    self.salt = bytes.fromhex(slt)
                    self.masterPassword = True

                continue
                
            confEntry = cfs[n]

            '''
            if 'pwd' in confEntry:
                pwd = confEntry['pwd']
                pwd = self.fernet.decrypt(pwd).decode()
                confEntry['pwd'] = pwd
            '''
                
            self.configs[n] = confEntry

    def generateSalt(self, noSalt=False):

        deb('generateSalt()', '_pwd')
        if noSalt:
            deb('Salt --> []', '_pwd')
            self.salt = ''
            return False
        
        if self.salt:
            log(f'[!] This cfgManager already has salt: [{self.salt}], aborting', 1)
            log('[!] This might as well crash to save connections.yaml consistent', 1)
            return None
        
        self.salt = os.urandom(16)
        deb(f'Salt --> [{self.salt.hex()}]', '_pwd')

        return True
    
    def generateKey(self, mp):
        '''generates fernet key based on master password
        to be called just once per session
        '''
        key_bytes = hashlib.pbkdf2_hmac('sha256', mp.encode(), self.salt, 100000, dklen=32)
        self.cryptkey = base64.urlsafe_b64encode(key_bytes)
        deb(f'generateKey: ==> {self.salt}', '_pwd')
        deb(f'generateKey: ==> {mp.encode()}', '_pwd')
        deb(f'generateKey: ==> {self.cryptkey}', '_pwd')
        
    def createFernet(self):
        deb(f'createFernet: cryptkey: {self.cryptkey}', '_pwd')
        if self.cryptkey:
            self.fernet = Fernet(self.cryptkey)
            self.masterPassword = True
            deb(f'Manual fernet instance assigned, derivek key: {self.cryptkey}', '_pwd')
        else:
            log('[w] key is not generated, aborting', 2)
            # cfgManager.fernet = Fernet(b'aRPhXqZj9KyaC6l8V7mtcW7TvpyQRmdCHPue6MjQHRE=')
            k = cfg('cryptKey', 'aRPhXqZj9KyaC6l8V7mtcW7TvpyQRmdCHPue6MjQHRE=')
            k = k.encode()

            self.fernet = Fernet(k)
            self.masterPassword = False
            deb('Default fernet instance assigned', '_pwd')
            
    def __init__(self, fname=None):
        self.cryptkey = None
        self.masterPassword = None

        deb('[cfgManager] init', '_pwd')
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
        
        deb('dump connections...')
        ds = {}
        
        # we use a master massword for this connections.yaml
        if self.salt:
            ds['__salt__'] = self.salt.hex()

        if self.salt == '':
            ds['__salt__'] = ''

        for n in self.configs:

            if n == '__salt__':
                continue

            confEntry = self.configs[n].copy()
            deb(f'   {n}, {confEntry.get("pwd")}', '_pwd')
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

cfgManInst = cfgManager(cfg('connectionsFile', None))
