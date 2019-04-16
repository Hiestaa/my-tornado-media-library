"""
Run the analyzer for all videos that haven't been analyzed yet.
Clean-up the
"""

import log
import time
import os
import logging

from tqdm import tqdm

from tools.utils import timeFormat
from server import model
from tools.analyzer import Analyzer

def genVids():
    c = 0
    videos = model.getService('video').getAll()
    progress = tqdm(total=len(videos), desc='[Analyzing video: ')
    for vid in videos:
        c += 1
        progress.set_description('[Analyzing video %s' % os.path.basename(vid['path']))
        progress.update()
        yield vid
    logging.info("Processed %d videos." % c)

def main():
    log.init(2, False, filename="bulkAnalyze.log", colored=False)
    for video in genVids():
        if ('analysis' in video and video['analysis'] is not None and
            '__version__' in video['analysis'] and
            video['analysis']['__version__'] == Analyzer.__version__):
            logging.info("Skipping video %s - analysis already completed for version %s.",
                         video['path'], Analyzer.__version__)
            continue

        start_t = time.time()
        analyzer = Analyzer(
            video['_id'], video['path'], video['snapshotsFolder'], async=False,
            force=False, annotator='dfl-dlib', videoDuration=video['duration'],
            autoCleanup=True)
        data = analyzer.run()
        logging.info("Analysis completed for video %s in %s.",
                     video['path'], timeFormat(time.time() - start_t))
        model.getService('video').set(video['_id'], 'analysis', data)


if __name__ == '__main__':
    main()
