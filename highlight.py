# experimental highlighting for resultset module
# Oct, 2023

import os
from utils import cfg, log, deb
from yaml import safe_load, YAMLError
from PyQt5.QtGui import QColor, QBrush

hll = {}                        # highlight list, key = column name
                                # value - dict of highlights: key / desc

hlc = {}                        # hl colors, key = column
                                # value: dict key / color

def color(column):
    return hlc.get(column, '')

def loadSingleYaml(column, filename):
    '''load a single file with highlights

    return number of new entries
    '''

    c = 0
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


    if highlights.get('color'):
        color = highlights.pop('color')

        try:
            brush = QBrush(QColor(color))
            deb(f'brush created: {color}')
        except Exception as ex:
            brush = QBrush(QColor('blue'))
            log(f'[w] Cannot create color with "{color}": {ex}, using red', 1)
            deb(f'brush created: {color}')

        if not column in hlc:
            hlc[column] = {}

        for item in highlights:
            hlc[column][item] = brush

    c += len(highlights)
    hll[column].update(highlights)

    return c

def loadFolder(column, folder):
    '''scan for yaml files in folder and load them'''

    log(f'loading {folder}...')
    files = os.listdir(folder)

    c = 0
    for f in files:
        fname = os.path.join(folder, f)
        if os.path.isfile(fname) and f.endswith('.yaml'):
            c += loadSingleYaml(column, fname)

    return c

def loadHighlights():
    '''browse through highlight directory and compose highlighting structure

    returns number of entries added'''

    hll.clear()

    if not cfg('experimental'):
        return

    folder = cfg('highlightFolder', 'highlight')

    if not os.path.isdir(folder):
        log(f'folder {folder} is not a valid folder or does not exist, no highlighting possible', 2)
        return

    files = os.listdir(folder)

    c = 0
    for f in files:
        path = os.path.join(folder, f)
        if os.path.isdir(path):
            c += loadFolder(f.lower(), path)

    return c


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
