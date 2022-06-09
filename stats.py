import os

def fileStats(fname):
    rows = 0
    nerows = 0
    size = os.path.getsize(fname)

    with open(fname, encoding="utf8") as f:
        for l in f:
            if len(l.strip()) > 0:
                nerows +=1 
            rows +=1 
         
    return {'rows': rows, 'nerows': nerows, 'size': size}

def stats():
    files = os.listdir('.')
    
    files = [f for f in files if f[-3:] == '.py']
    
    i = 0
    
    trows = 0
    tnerows = 0
    tsize = 0
    
    for f in files:
        s = fileStats(f)
        
        rows = s['rows']
        nerows = s['nerows']
        size = s['size']
        
        trows += rows
        tnerows += nerows
        tsize += size
        
    print(f'Rows: {trows}, non-empty: {tnerows}, size: {tsize}')
        
if __name__ == '__main__':
    stats()
    