"""
Fix all albums data (it was a very poor idea to store pictures and starred as two separate lists)
"""

import log
import time
import os
import logging

from tqdm import tqdm

from tools.utils import timeFormat
from server import model
from tools.analyzer import Analyzer

def genAlbums():
    c = 0
    albums = model.getService('album').getAll()
    progress = tqdm(total=len(albums), desc='[Analyzing album: ')
    for a in albums:
        c += 1
        progress.set_description('[Analyzing album %s' % os.path.basename(a['fullPath']))
        progress.update()
        yield a
    logging.info("Processed %d albums." % c)

def main():
    log.init(2, False, filename="fixAlbums.log", colored=False)
    for album in genAlbums():
        if album['_id'] in ['random', 'starred']:
            model.getService('album')._collection.remove({'fullPath': album['_id']})
            continue

        data = []
        for idx, pic in enumerate(album['pictures']):
            obj = {
                'filename': pic,
                'display': 0,
                'starred': idx in album['starred'],
                'faces': []
            }
            data.append(obj)
        model.getService('album').set(album['_id'], 'picturesDetails', data)

if __name__ == '__main__':
    main()
