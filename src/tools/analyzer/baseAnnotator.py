# -*- coding: utf8 -*-

from __future__ import unicode_literals

from collections import deque
import logging
import time
import os
import subprocess
import json
import math
from datetime import datetime
from tqdm import tqdm
import re

from conf import Conf
from tools.utils import extends
from tools.analyzer.minivid import MinividGenerator
from server import model

BASE_PATH = Conf['data']['videos']['rootFolder']

def extract_image_num(string):
    match = re.search('%s(\d+)' % MinividGenerator.MINIVID_PREFIX, string)
    return int(match[1])

class BaseAnnotator(object):
    supportReportingProgress = False
    """
    A generic annotator providing an interface to be extended in the sub-class
    as well as utility methods such as caching and batching.
    This doesn't perform any analysis on its own.
    """
    def __init__(self, name, batchSize, imgPaths, progress):
        super(BaseAnnotator, self).__init__()
        self.imgPaths = list(sorted(set(imgPaths), key=extract_image_num))  # don't query the same image twice
        self.BATCH_SIZE = batchSize
        self.name = name
        self.frameNumber = 0
        self.progress = progress
        self.resultCache = {}
        self.lastProgressCall = time.time()
        self._stopped = False

    # overridable
    def stop(self):
        self._stopped = True
        return

    def _checkCache(self, imagePath):
        """
        Check existence of cached google cloud vision result for the given image
        Raises `ValueError` or `IOError` if the no cache data can be found
        Returns the result (note: already serialized) otherwise
        """
        cachePath = imagePath.replace('.png', "_%s_raw.json" % self.name)
        cachePath = cachePath.replace('.jpg', "_%s_raw.json" % self.name)
        with open(cachePath, 'r') as cacheFile:
            cacheData = json.load(cacheFile)
            if len(cacheData) == 0:
                raise ValueError("Empty cache")
            return cacheData

    def _cache(self, imagePath, serializedData, frameNumber):
        """
        Dump the serialized result into a json file sepecific to the given image.
        """
        cachePath = imagePath.replace('.png', "_%s_raw.json" % self.name)
        cachePath = cachePath.replace('.jpg', "_%s_raw.json" % self.name)
        try:
            with open(cachePath, 'w') as cacheFile:
                json.dump(serializedData, cacheFile)
        except Exception as e:
            logging.error("Unable to dump %s result on disk." % self.name)
            pass

        # if we don't support reporting the progress in real time,
        # we haven't reported about any of the non-cached result of this batch.
        # Do it now as we're caching these. We're not at risk double reporting,
        # but we might not garantee the order of the frame is gonna be preserved.
        if not self.supportReportingProgress:
            self.progress(frameNumber, serializedData)

        return serializedData

    def _extendAnnotation(self, annotation, imagePath, duration):
        if 'name' in annotation or 'path' in annotation:
            return annotation  # already extended (might come from cache)
        return dict(
            analyzeTs=time.time(),
            analyzeDate=datetime.utcnow().isoformat(),
            analyzeDuration=duration,
            path=imagePath.replace(BASE_PATH, ''),
            name=os.path.basename(imagePath),
            **annotation)

    # overridable
    def _annotateBatch(self, batch):
        """
        Returns a list of JSON-compatible dict annotations in the
        same order as the provided batch of images.
        Some properties such as the path, name, analyze date and duration will be automatically added.
        """
        raise NotImplementedError()

    def _progress(self, imagePath, data):
        """
        Called when processing a specific image
        The `imagePath` is expected to exist in the `resultCache` with a frame number.
        """
        cacheData = self.resultCache[imagePath]
        duration = time.time() - self.lastProgressCall
        self.lastProgressCall = time.time()
        self.progress(cacheData['frame'], self._extendAnnotation(data, imagePath, duration))

    def nextBatch(self):
        """
        Process the next batch of images.
        Submit up to `BATCH_SIZE` images for annotation
        Returns a list of serialized results
        """
        start_batch = time.time()

        # list of image paths annotated (not cached) in this batch
        currentBatch = []
        # list of all images processed in this batch (cached and annotated)
        fullBatch = []
        # {<imagePath>: {'data': <cached data, if available>, 'index': <response index, otherwise>, 'frame': <frame number>}}
        self.resultCache = {}

        while len(self.imgPaths) > 0 and len(currentBatch) < self.BATCH_SIZE:
            imagePath = self.imgPaths.pop(0)
            fullBatch.append(imagePath)
            # check cache existence
            try:
                data = self._checkCache(imagePath)
                self.resultCache[imagePath] = {'data': data, 'frame': self.frameNumber}
                self._progress(imagePath, data)
            except (IOError, ValueError):
                #  cache doesn't exist
                self.resultCache[imagePath] = {'index': len(currentBatch), 'frame': self.frameNumber}
                currentBatch.append(imagePath)

            self.frameNumber += 1

        annotations = []
        if len(currentBatch) > 0:
            logging.debug("Submitting %d annotations...", len(currentBatch))
            self.lastProgressCall = time.time()
            annotations = self._annotateBatch(currentBatch)
            duration = time.time() - start_batch
            logging.debug("Received %d responses (duration: %.3fs)",
                          len(annotations), duration)

        if self._stopped:
            return []

        if len(annotations) < len(currentBatch):  # can't happen if current batch is empty ;)
            raise Exception('Missed %d annotation responses in current batch. Aborting.' % (len(currentBatch) - len(annotations)))

        return [
            self.resultCache[imagePath]['data']
            if 'data' in self.resultCache[imagePath] else
            self._cache(imagePath, self._extendAnnotation(
                annotations[self.resultCache[imagePath]['index']],
                imagePath, duration), self.resultCache[imagePath]['frame'])
            for imagePath in fullBatch
        ]

    def __call__(self):
        """
        Process the full batch of images in multiple batch requests.
        yield annotations for each image in the batch, serialized as a
        JSON-compatible object to which some additional information have been added
        (file name, full file path, generation date / time and duration)
        """
        results = {}
        batchNb = 0
        nbImages = len(self.imgPaths)
        nbBatches = math.ceil(nbImages / self.BATCH_SIZE)
        progress = tqdm(total=nbBatches, desc="[Batches")
        self.frameNumber = 0
        while len(self.imgPaths) > 0:
            if self._stopped:
                break
            batchNb += 1
            progress.update()
            try:
                for v in self.nextBatch():
                    if self._stopped:
                        break
                    yield v
            except Exception as e:
                logging.error("Error during batch #%d. Skipping.", batchNb)
                logging.exception(e)
                if batchNb > nbImages:
                    logging.error(
                        "Processed more batches than images - something must be wrong here.")
                    break

        progress.close()

        if self._stopped:
            logging.info("Minivid Annotator interrupted.")

