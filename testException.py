import sys, traceback

try:
    s = str(1/0)
except Exception as e:
    print(f'Exception {type(e)}: {e}')
    
    rows = traceback.format_exc().splitlines()
    
    print('---')
    print(traceback.format_exc())
    
    print('---')
    print('=====')
    
    (_, _, tb) = sys.exc_info()
    
    for l in traceback.format_tb(tb):
        print(f'>> [{l}]')
        
    print('=====')
    