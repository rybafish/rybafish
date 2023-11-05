# experimental highlighting for resultset module
# Oct, 2023

import os
from utils import cfg, log, deb
from yaml import safe_load, YAMLError

hll = {}                        # highlight list, key = column name
                                # value - dict of highlights: key / desc

def loadSingleYaml(column, filename):
    '''load a single file with highlights

    return ??
    '''
    try:
        log(f'loading {filename}', 4)
        f = open(filename, 'r')
        highlights = safe_load(f)
        f.close()
    except Exception as e:
        log(e)
        return None

    if not column in hll:
        hll[column] = {}

    hll[column].update(highlights)

def loadFolder(column, folder):
    '''scan for yaml files in folder and load them'''

    log(f'loading {folder}...')
    files = os.listdir(folder)

    for f in files:
        fname = os.path.join(folder, f)
        if os.path.isfile(fname) and f.endswith('.yaml'):
            loadSingleYaml(column, fname)

def loadHighlights():
    '''browse through highlight directory and compose highlighting structure

    returns nothing'''

    hll.clear()

    if not cfg('experimental'):
        return

    folder = cfg('highlightFolder', 'highlight')

    if not os.path.isdir(folder):
        log(f'folder {folder} is not a valid folder or does not exist, no highlighting possible', 2)

    files = os.listdir(folder)

    for f in files:
        path = os.path.join(folder, f)
        if os.path.isdir(path):
            loadFolder(f.lower(), path)


def dumpHighlights():
    '''dump to log of existing highlights'''
    log('Report loaded highlights:')
    for k in hll.keys():
        v = hll[k]
        log(f'{k} highlighting')
        for hl in v.keys():
            log(f'{hl} -- {v[hl]}', 4)


if __name__ == '__main__':
    loadHighlights()
    dumpHighlights()
