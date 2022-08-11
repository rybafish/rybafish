import os
import sys
import re

stats = {}
filess = {}

debug = False

def parsePair(pair):

    s = pair.strip()
    
    q = s[0]
    
    if q != "'":
        print('cannot find the first quote, stop', pair)
        sys.exit(1)
        
    keyStop = s[1:].find(q)
    
    if keyStop < 0:
        print('cannot find second quote, stop', pair)
        sys.exit(1)
    
    setting = s[1:keyStop+1]
    #print('setting: ', setting)
    
    rest = s[keyStop+1+1:]
    rest = rest.strip()

    if rest:
        if rest[0] != ',':
            print('Cannot find coma:', rest)
            sys.exit(1)
            
        rest = rest[1:].strip()
        
        #print('rest: ', rest)

    return (setting, rest)

def fileStats(fname):

    # if cfg('test1', nope) or cfg('hz', Nopetoo)

    with open(fname, encoding="utf8") as f:
        for l in f:
            #m = re.findall('cfg\(\'(\w+)\')', l)
            #m = re.findall(r"cfg\('\w'(,\s?.+)?\)", l)
            
            if l.strip() == 'def cfg(param, default = None):':
                #function definition, not usage
                continue
            
            m = re.findall(r'cfg\((.+?)\)', l)
            
            if len(m):
                if debug:
                    print('--', l.strip(), '--')
                    
            for i in m:
                if debug:
                    print(f'   ---> {i}')
                v = parsePair(i)
                
                if debug:
                    print(f'{v[0]} --> {v[1]}')
                
                if v[1]:
                    kv = f'{v[0]}: {v[1]}'
                else:
                    kv = f'{v[0]}'
                
                if kv in stats:
                    stats[kv] += 1
                else:
                    stats[kv] = 1
                    
                if kv in filess:
                    if fname not in filess[kv]:
                        filess[kv].append(fname)
                else:
                    filess[kv] = [fname]
                
         
    return None

def calcStats():
    files = os.listdir('.')
    
    files = [f for f in files if f[-3:] == '.py']
    
    for f in files:
        if f == 'config_settings.py':
            continue

        if debug:
            print(f'check {f}')

        s = fileStats(f)
        
    st = sorted(stats)
    
    maxLen = len(max(st, key=lambda x: len(x)))+1
        
    for k in st:
        flist = ', '.join(filess[k])
        print(f'{k:{maxLen}} - {stats[k]:3}, {flist}')

                
if __name__ == '__main__':
    calcStats()
    