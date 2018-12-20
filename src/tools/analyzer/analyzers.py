# -*- coding: utf8 -*-

from __future__ import unicode_literals

from collections import deque
import logging
import os
import traceback
import time

from conf import Conf
from tools.utils import extends
from server import model
from tqdm import tqdm


# try:
#     from tools.analyzer.gcvAnnotator import GCVAnnotator
# except Exception as e:
#     print("ERROR: Unable to load Google Cloud Vision Annotator. Annotator 'gcv' will be unavailable.")
#     traceback.print_exc()
from tools.analyzer.unavailableAnnotator import UnavailableAnnotator as GCVAnnotator

try:
    from tools.analyzer.dflAnnotator import MTDFLAnnotator
    from tools.analyzer.dflAnnotator import DLIBDFLAnnotator
except Exception as e:
    print("ERROR: Unable to load Deep Face Lab Annotator. Annotator 'dfl' will be unavailable.")
    traceback.print_exc()
    from tools.analyzer.unavailableAnnotator import UnavailableAnnotator as MTDFLAnnotator
    DLIBDFLAnnotator = MTDFLAnnotator


Annotators = {
    'dfl-mt': MTDFLAnnotator,
    'dfl-dlib': DLIBDFLAnnotator,
    'gcv': GCVAnnotator
}

class MinividAnalyzer(object):
    """
    Use a `BatchImageAnnotator` instance to annotate each frame of the minivid
    that is expected to be generated already
    """
    def __init__(self, minividFolder, annotator, progress):
        super(MinividAnalyzer, self).__init__()
        self._minividFolder = minividFolder
        self._images = [os.path.join(self._minividFolder, img)
                        for img in os.listdir(self._minividFolder)
                        if img.endswith('.png')]
        self.annotator = annotator
        self.annotatorInstance = None
        self.progress = progress

    def stop(self):
        self.annotatorInstance.stop()

    def __len__(self):
        return len(self._images)

    def __call__(self):
        """
        Analyze the minivid using the provided annotator
        Progress will be reported either as the annotator is running (for real time progress on batches)
        or, if it doesn't support real-time progress reporting, at the end of each batch.
        Note that due to caching, real time progress might not be provided in the exact order of the frames
        """
        BatchImageAnnotator = Annotators[self.annotator] if self.annotator in Annotators else DFLAnnotator
        """
        Successively yield GCV results for each image found in the minivid folder
        Only *.png files will be processed (minivid generator is expected to generate png files)
        Call `len(analyzer)` to get the number of items expected to be generated in advance.
        """
        self.annotatorInstance = BatchImageAnnotator(self._images, self.progress)
        for result in self.annotatorInstance():
            yield result

class AnalysisPostProcessor(object):
    """
    Performs the post-processing of the analysis results
    in the context of frames extracted from a video
    """
    __version__ = '0.0.1'
    def __init__(self, results):
        """
        Build the post-processor to process the given results.
        * `results` is expected to be an iterator of GCV image analysis results
        * `contextLen` is the size of the context - or how many frames of context
            before AND after the currently analyzed frame to take into account during
            the post-processing operations
        """
        super(AnalysisPostProcessor, self).__init__()
        self._results = results
        self._contextLen = Conf['data']['ffmpeg']['minividPostProcContext']

    def _computeFaceRatio(self, faceData):
        """
        Compute the 'face ratio', that the the ratio the detected face takes in the image.
        This is the average of the ratio face width / image witdh and height
        """
        total = 0
        for i, faceDatum in enumerate(faceData):
            width = float(abs(faceDatum['boundaries'][1]['x'] - faceDatum['boundaries'][0]['x']))
            height = float(abs(faceDatum['boundaries'][1]['y'] - faceDatum['boundaries'][0]['y']))
            totalWidth = float(Conf['data']['ffmpeg']['minividDimension'][0])
            totalHeight = float(Conf['data']['ffmpeg']['minividDimension'][1])
            total += (width / totalWidth + height / totalHeight) / 2 * (1 + i / 5)
        return total

    def _postProcessor(self, context, frameI, contextStart, contextEnd):
        """
        Perform post-processing of results for frame `frameI` (int) in the given `context` where:
        * `context` is a list of frame analysis results and should contain up to `contextLen * 2` items
        * `frameI` is the index of the frame result to post-process in the `context` array
        * `contextStart` is the frame index of the first frame of the context in the overall frames list
        * `contextEnd` is the frame index of the last frame of the context in the overall frames list
        This doesn't do much than providing some additional fields and computing the face ratio,
        in the future we should examine the previous and next frames and compute a confidence value, then discard
        the frames that have a low face detection confidence
        (which may or may not account for the detection confidence per frame)
        """
        processed = dict(**context[frameI])
        return extends(
            processed,
            contextStart=contextStart, contextStartFile=context[0]['name'],
            contextEnd=contextEnd, contextEndFile=context[-1]['name'],
            postProcessorVersion__=AnalysisPostProcessor.__version__,
            faceRatio=self._computeFaceRatio(context[frameI]['faces']))

    def __call__(self):
        context = deque([], maxlen=(
            self._contextLen * 2))
        preprocessedFrame = -1
        for i, res in enumerate(tqdm(self._results, desc='[Post-Processing')):
            context.append(res)
            if len(context) > self._contextLen:
                # in `context` index space:
                # 0 < ccontex len <= 10: no PP - building context
                # 10 < context len < 20: PP(i - 10) (i = 10: pp(0), i = 12: PP(2), i = 15: PP(5) )
                # i >= 20: 10 PP(10)
                preprocessedFrame = min(i - self._contextLen, self._contextLen - 1)
                yield self._postProcessor(
                    context,
                    preprocessedFrame,
                    i + 1 - len(context), i)

        # preprocess missing frame
        # if there is less frame than the size of the context, we'll not have started processing any - time to do so
        # otherwise there is going to be oone context length of results that have been skipped
        while preprocessedFrame + 1 < len(context):
            preprocessedFrame += 1
            yield self._postProcessor(
                context,
                preprocessedFrame,
                i + 1 - len(context), i)



class AnalysisAggregator(object):
    """
    Aggregates all frame analysis results into a single object with the following properties:
    * `__version__` version of the aggregator used to generate this aggretation
    * `averageFaceRatio`: average ratio between detected covering face surface and image size
    * `faceTime`: number of frames holding a face
    * `faceTimeProp`: proportion of frames holding a face
    * ...
    """
    __version__ = '0.0.1'
    def __init__(self, results, start_t):
        super(AnalysisAggregator, self).__init__()
        self._results = results
        self._start_t = start_t

    def __call__(self):
        if len(self._results) == 0:
            raise Exception('No result to aggregate!')
        return {
            '__version__': AnalysisAggregator.__version__,
            'averageFaceRatio': sum(
                itm['faceRatio'] for itm in self._results
                if itm['faceRatio'] != 0) / len(self._results) * 100,
            'faceTime': sum(
                1.0 if len(itm['faces']) > 0 else 0.0
                for itm in self._results),
            'faceTimeProp': sum(
                1.0 if len(itm['faces']) > 0 else 0.0
                for itm in self._results) / len(self._results) * 100,
            'duration': time.time() - self._start_t,
            'nbFrames': len(self._results)
        }
