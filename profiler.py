import sys, os, time
from yaml import safe_load
from datetime import datetime
from _constants import isbeta

# have to manually check the setting 
# in order to avoid cyclic imports
    
script = sys.argv[0]
path, file = os.path.split(script)
    

useProfiler = False

cfgFile = os.path.join(path, 'config.yaml')

config = {}

try: 
    f = open(cfgFile, 'r')
    config = safe_load(f)
    
    useProfiler = config.get('useProfiler', isbeta) # default is True in case of beta version
        
except:
    useProfiler = False
        
    s = 'cannot load config, profiler not to be used'
    
    print(s)
    
    f = open('.log', 'a')
    f.seek(os.SEEK_END, 0)
    
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' '

    f.write(ts + str(s) + '\n')
    
    f.close()        
    
# again, to avoid cyclic imports...
def log(s):
    '''
        log the stuff one way or another...
    '''
    
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' '

    if config.get('logmode') == 'screen' or config.get('logmode') == 'duplicate':
        print('[l]', s)
        
    if config.get('logmode') != 'screen':
        f = open('.log', 'a')
        f.seek(os.SEEK_END, 0)
        try:
            f.write(ts + str(s) + '\n')

        except Exception as e:
            f.write(ts + str(e) + '\n')
        
        f.close()    

def humanize(i):
    pf = ''
    if i >= 1000:
        i /= 1000
        pf = 'K'
    else:
        return str(i)
        
    if i >= 1000:
        i /= 1000
        pf = 'M'
    if i >= 1000:
        i /= 1000
        pf = 'B'
        
    return f'{i:.01f}{pf}'

class Profiler():

    timers = {}

    # context managet stuff
    names = []
    t0s = []
    
    def __enter__(self):
        self.t0s.append(time.perf_counter())
        return self
        
    def __exit__(self, exc_type, exc_value, exc_tb):
        name = self.names.pop()
        t = time.perf_counter() - self.t0s.pop()
        if name not in self.timers: self.timers[name] = [0, 0]

        self.timers[name][0] += 1
        self.timers[name][1] += t

    def __call__ (self, f):
        if type(f) == str:
            self.names.append(f)
            return self

        def ftime(*args, **kwargs):
            
            fname = f.__qualname__
            
            if fname not in self.timers: self.timers[fname] = [0, 0]
            
            t0 = time.perf_counter()
            res = f(*args, **kwargs)
            t1 = time.perf_counter()
            
            self.timers[fname][0] += 1
            self.timers[fname][1] += t1 - t0
            
            return res
        
        return ftime
        
    def report(self):

        nothing = 0
        
        timers = profiler.timers
                
        if '__doNothingProfile' in timers:
            calibrate = timers.pop('__doNothingProfile')
            nothing = calibrate[1]/calibrate[0]
        else:
            log('no calibration stats available')

        srt = sorted(timers.items(), key = lambda x: x[1][1], reverse=True)
        total = 0
        totalTime = 0
        
        if len (timers) == 0:
            return
            
        
        maxLen =  len(max(timers.keys(), key=lambda x: len(x))) + 1
        
        #syntax sugar coma:
        countLen =  len(humanize(timers[max(timers.keys(), key=lambda x: len(humanize(timers[x][0])))][0])) + 1

        repWidth = maxLen + countLen + 2 + 12 + 1 + 12 + 3 + 15 - 3
        repWidthD = (repWidth - 17) % 2
             
        log('-' * (int((repWidth - 17) / 2)) + ' profiler report ' + '-' * (repWidthD + int((repWidth - 17) / 2)))
        
        log(f'{"Function":{maxLen}} {"N":>{countLen}},{"Total, s":>12}{"AVG":>16}{"Profiler":>12}')
        
        for (k, v) in srt:
            count = v[0]
            #t = max(v[1] - nothing * count, 0)
            t = v[1]
            tp = v[1] + nothing * count
            total += count
            totalTime += t
            
            if count > 0:
                log(f'{k:{maxLen}} {humanize(count):>{countLen}},{tp:>12f}{t/count:>16g}{nothing*count:>12f}')
            else:
                log(f'{k:{maxLen}} {humanize(count):>{countLen}},{tp:>12f}{"n/a":>16}{nothing*count:>12f}')
            
        if nothing != 0:
            log('-')
            log(f'{"Total":{maxLen}} {humanize(total):>{countLen}},{totalTime:>12f} s.')
            log('Total duration normally exceeds sum of entries due to nested calls.')
            log(f'Profiler itself: {total*nothing:g} sec. Executions: {total}.')

        log('-' * repWidth)


if useProfiler:
    log('Init profiler')
    profiler = Profiler()
else:
    log('Dummy profiler')
    def profiler(f):
        return f

@profiler    
def __doNothingProfile():
    pass

def __doNothing():
    pass

def calibrate(n = 1000*1000):

    t0 = time.perf_counter()
    for i in range(n):
        __doNothing()
    
    t1 = time.perf_counter()

    for i in range(n):
        __doNothingProfile()
        
    t2 = time.perf_counter()
    
    noProfile = t1 - t0
    withProfile = t2 - t1
    
    overhead = withProfile - noProfile
    
    if hasattr(profiler, 'timers'):
        profiler.timers['__doNothingProfile'] = [n, overhead]
        log(f'calibration: {overhead=:.10f}, measured={profiler.timers["__doNothingProfile"][1]:.10f}')
