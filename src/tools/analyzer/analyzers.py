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
from tools.analyzer.baseAnnotator import checkCache

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

class AlbumAnalyzer(object):
    __version__ = '0.0.8'
    def __init__(self, imgPaths, annotator, progress=None):
        super(AlbumAnalyzer, self).__init__()
        self._imgPaths = imgPaths
        self.annotator = annotator
        self.annotatorInstance = None
        self.progress = progress

    def stop(self):
        self.annotatorInstance.stop()

    def __len__(self):
        return len(self._imgPaths)

    def __call__(self):
        """
        Analyze the minivid using the provided annotator
        Progress will be reported either as the annotator is running (for real time progress on batches)
        or, if it doesn't support real-time progress reporting, at the end of each batch.
        Note that due to caching, real time progress might not be provided in the exact order of the frames
        """
        BatchImageAnnotator = Annotators[self.annotator] if self.annotator in Annotators else DLIBDFLAnnotator
        """
        Successively yield GCV results for each image found in the minivid folder
        Only *.png files will be processed (minivid generator is expected to generate png files)
        Call `len(analyzer)` to get the number of items expected to be generated in advance.
        """
        self.annotatorInstance = BatchImageAnnotator(self._imgPaths, self.progress)
        for result in self.annotatorInstance():
            yield result

    @staticmethod
    def checkCache(filePath):
        annotator = Conf['data']['albums']['annotator']
        return checkCache(filePath, annotator)

class MinividAnalyzer(AlbumAnalyzer):
    """
    Use a `BatchImageAnnotator` instance to annotate each frame of the minivid
    that is expected to be generated already
    """
    def __init__(self, minividFolder, annotator, progress):
        imgPaths = [os.path.join(minividFolder, img)
                        for img in os.listdir(minividFolder)
                        if img.endswith('.png')]
        super(MinividAnalyzer, self).__init__(imgPaths, annotator, progress)

class AnalysisPostProcessor(object):
    """
    Performs the post-processing of the analysis results
    in the context of frames extracted from a video
    """
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
        self._faceUid = 0

    DISTANCE_RATIO = 50
    def _isValidCandidate(self, face, candidate, distance):
        faceWidth = abs(face['boundaries'][1]['x'] - face['boundaries'][0]['x'])
        faceHeight = abs(face['boundaries'][1]['y'] - face['boundaries'][0]['y'])
        dx = abs(face['boundaries'][0]['x'] - candidate['boundaries'][0]['x'])
        dx2 = abs(face['boundaries'][1]['x'] - candidate['boundaries'][1]['x'])
        dy = abs(face['boundaries'][0]['y'] - candidate['boundaries'][0]['y'])
        dy2 = abs(face['boundaries'][1]['y'] - candidate['boundaries'][1]['y'])

        return (
            dx * 100 / float(faceWidth) < self.DISTANCE_RATIO * distance and
            dx2 * 100 / float(faceWidth) < self.DISTANCE_RATIO * distance and
            dy * 100 / float(faceHeight) < self.DISTANCE_RATIO * distance and
            dy2 * 100 / float(faceHeight) < self.DISTANCE_RATIO * distance)

    # TODO: maybe, ignore giggling and flickering faces?
    def _identifyFaces(self, context, frameI, contextStart, contextEnd, previousFramePP):
        """
        Assign a unique id to faces found in `previousFramePP`.
        The id will be unique to a face accross a given frame, and will be re-used for subsequent
        frames if the face position doesn't move too abruptly from one frame to the other
        (based on a ratio speed / face size, since larger faces will likely more faster)
        This enables the smoothing step not to get confused when multiple frames appear and disappear on screen
        """
        currentFrameData = dict(**context[frameI])

        # if there is no face, nothing to do
        if len(currentFrameData['faces']) == 0:
            return currentFrameData

        # if self._uid is still 0, we might not be in the first frame but the first that has a face - all the same
        if previousFramePP is None or self._faceUid == 0:
            # first frame case - just assign a uid to each face
            for face in currentFrameData['faces']:
                face['id'] = self._faceUid
                self._faceUid += 1
            return currentFrameData

        # subsequent frames - look in tghe previous data which it is the most likely to be
        # if there ever has only been one, pick that one
        # don't do that: if the face is too far between two frames (e.g. transition between two plans)
        # we end up averaging the transition which result in faces in the middle of nowhere
        # if self._faceUid == 1 and len(currentFrameData['faces']) == 1:
        #     currentFrameData['faces'][0]['id'] = self._faceUid

        # if is a valid candidate, pick this one
        # otherwise, assign a new uid
        for face in currentFrameData['faces']:
            for candidate in previousFramePP['faces']:
                if self._isValidCandidate(face, candidate, 1):
                    face['id'] = candidate['id']
            if not 'id' in face:
                face['id'] = self._faceUid
                self._faceUid += 1

        return currentFrameData

    # FIXME (if possible): smoothing works kinda well when a single face is in the picture, but
    # when multiples are found it is really hard to avoid confusing a face with another.
    # For instance, say a frame has 2 faces, and the next one only has one, because the first one disappeared,
    # it is not trivial to get the smoothing algorithm to recognize that the first face disappeared,
    # and the second one stayed on screen.
    # We might be able to solve this by running a face-identification step, that will attempt to set
    # must likely id to face trying to minimize the distance between the face of the same id between two frames
    # Then, instead of averaging by face position (which, even sorted by coordinate, leads to a lot of confusion),
    # we would be able to average by face id.
    SMOOTH_CONTEXT_LEN = 2
    def _getSmoothedFaces(self, context, frameI, contextStart, contextEnd, previousFramePP):
        currentFrameData = dict(**context[frameI])
        if len(currentFrameData['faces']) == 0:
            return []

        faceDataById = {}  # deque of faces for each identified face

        # return false if need to stop the operation
        def addFaceToDataFromFrame(adder, contextPos):
            if not 'faces' in context[contextPos] or len(context[contextPos]['faces']) == 0:
                return False  # don't consider the whole context, stop when the face is not detected

            faces = context[contextPos]['faces']
            for face in faces:
                if face['id'] not in faceDataById:
                    faceDataById[face['id']] = deque()
                adder(faceDataById[face['id']], face)

            return True

        # TODO: use all context or a subset based on the timestep?
        adder = lambda data, face: data.append(face)
        for x in range(frameI, min(frameI + self.SMOOTH_CONTEXT_LEN, len(context))):
            if not addFaceToDataFromFrame(adder, x):
                break

        adder = lambda data, face: data.appendleft(face)
        for x in range(frameI, max(frameI - self.SMOOTH_CONTEXT_LEN, 0), -1):
            if not addFaceToDataFromFrame(adder, x):
                break

        smoothedFaces = {faceuid: {'boundaries': None, 'landmarks': []}
                         for faceuid in faceDataById}

        # loop over each face in the current frame data - we're gonna update its position to the
        # average of the position of the face with the same id in the other frames
        for face in currentFrameData['faces']:
            faceque = faceDataById[face['id']]
            faceavg = lambda getData: (sum(getData(face) for face in faceque) / len(faceque))
            x = faceavg(lambda face: face['boundaries'][0]['x'])
            y = faceavg(lambda face: face['boundaries'][0]['y'])
            x2 = faceavg(lambda face: face['boundaries'][1]['x'])
            y2 = faceavg(lambda face: face['boundaries'][1]['y'])
            face['boundaries'] = [{'x': x, 'y': y}, {'x': x2, 'y': y2}]

            haslandmarks = [face for face in faceque if len(face['landmarks']) > 0]
            landmarkavg = lambda getData: (sum(getData(face) for face in haslandmarks) / len(haslandmarks))
            if len(haslandmarks) == 0:
                continue

            for lk, landmark in enumerate(haslandmarks[0]['landmarks']):
                landmark['x'] = landmarkavg(lambda face: landmark['x'])
                landmark['y'] = landmarkavg(lambda face: landmark['y'])

        return currentFrameData

    FLICKERING_CONTEXT_LEN = 5
    def _markFlickeringFaces(self, context, frameI, contextStart, contextEnd, previousFramePP):
        """
        Returns the list of faces data found in `currentFrameData` marked with an additional `flickering` field
        The field will be True when the face is found flickering, which means it wasn't
        present in all frames of a window of up to `FLICKERING_CONTEXT_LEN` on both sides of
        the provided `frameI` in the given `context`.
        Note: if multiple faces are found in the picture, we'll not consider the faces that are further
        appart from each on in the context window than `distance * 5% * faceSize` in any dimension
        """
        def hasAtLeastOneCandidate(face, annotation, distance):
            for candidate in annotation['faces']:
                if self._isValidCandidate(face, candidate, distance):
                    return True
            return False
            # return any(isValidCandidate(face, candidate, distance)
            #            for candidate in annotation['faces'])

        currentFrameData = dict(**context[frameI])
        start = max(0, frameI - self.FLICKERING_CONTEXT_LEN)
        stop = min(len(context), frameI + self.FLICKERING_CONTEXT_LEN)

        for face in currentFrameData['faces']:
            flickeringLeft, flickeringRight = False, False

            for x in range(start, frameI):
                flickeringLeft = not hasAtLeastOneCandidate(face, context[x], abs(frameI - x) or 1)
                if flickeringLeft:
                    break

            for x in range(frameI + 1, stop):
                flickeringRight = not hasAtLeastOneCandidate(face, context[x], abs(frameI - x) or 1)
                if flickeringRight:
                    break

            if flickeringLeft and flickeringRight:
                face['flickering'] = True

        return currentFrameData

    GIGGLING_CONTEXT_LEN = 5
    GIGGLING_ALLOWANCE = 25
    def _markGigglingLandmarks(self, context, frameI, contextStart, contextEnd, previousFramePP):
        """
        Returns the list of face data found in `context[frameI]` marked with an additional `giggling` field
        The field will be True when the face is found giggling, that is the landmarks do not retain
        a stable position within the rect determined by this face accross multiple frames.
        Note: landmark position will be normalized in the corresponding face rect coordinate,
        which means there will be no need for identifying faces when multiple are found in
        a given picture. We'll just use all the faces found in the previous frames for the average,
        compare this average to the current position, and mark `giggling` if the difference
        exceeds a percentage of the face size (in any dimension)
        """
        currentFrameData = dict(**context[frameI])
        start = max(0, frameI - self.GIGGLING_CONTEXT_LEN)
        stop = min(len(context), frameI + self.GIGGLING_CONTEXT_LEN)
        context = list(context)[start:stop]

        def computeAverageLandmark(faces, lk, dim):
            # todo: we subtract the face coordinate to translate in the face rect coordinate
            # it'd be nice to also apply a ratio to account for changes in scaling
            return sum(face['landmarks'][lk][dim] - face['boundaries'][0][dim]
                       for face in faces) / len(faces)

        for face in currentFrameData['faces']:
            faces = [otherface for annotation in context for otherface in annotation['faces']
                     if otherface['id'] == face['id']]
            faceWidth = abs(face['boundaries'][1]['x'] - face['boundaries'][0]['x'])
            faceHeight = abs(face['boundaries'][1]['y'] - face['boundaries'][0]['y'])

            for lk, landmark in enumerate(face['landmarks']):
                meanX = computeAverageLandmark(faces, lk, 'x')
                meanY = computeAverageLandmark(faces, lk, 'y')
                x = landmark['x'] - face['boundaries'][0]['x']
                y = landmark['y'] - face['boundaries'][0]['y']
                dx = abs(meanX - x)
                dy = abs(meanY - y)
                xGiggling = dx * 100 / float(faceWidth)
                yGiggling = dy * 100 / float(faceHeight)

                landmark['xGiggling'] = xGiggling
                landmark['yGiggling'] = yGiggling
                if (xGiggling > self.GIGGLING_ALLOWANCE or
                    yGiggling > self.GIGGLING_ALLOWANCE):
                    landmark['giggling'] = True

        return currentFrameData

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

    def _finalize(self, context, frameI, contextStart, contextEnd, previousFramePP):
        currentFrameData = dict(**context[frameI])

        for face in currentFrameData['faces']:
            alteredConfidence = face['detection_confidence']
            if face.get('flickering'):
                alteredConfidence = 0.3 * alteredConfidence

            stableLandmarksProportion = 1.0 if len(face['landmarks']) == 0 else sum(
                0 if lm.get('giggling') else 1
                for lm in face['landmarks']) /\
                float(len(face['landmarks']))


            alteredConfidence = stableLandmarksProportion * alteredConfidence
            face['altered_detection_confidence'] = alteredConfidence

        return extends(
            currentFrameData,
            contextStart=contextStart, contextStartFile=context[0]['name'],
            contextEnd=contextEnd, contextEndFile=context[-1]['name'],
            faceRatio=self._computeFaceRatio(context[frameI]['faces']))


    def _framesWithContext(self, results, stageLabel):
        """
        WIP
        Returns an iterable that will iterate over the provided iterable,
        adding some context (previous and next frames) to each yielded item.
        Yields (context, itemIndex, contextStart, contextEnd) items where
        * `context` is the context around the item
        * `itemIndex` is the index of the current item in the provided context
        * `contextStart` is the position of the first item of the context in the provided iterable
        * `contextEnd` is the position of the last item of the context in the provided iterable
        """
        context = deque([], maxlen=(
            self._contextLen * 2))
        preprocessedFrame = -1
        prev = None
        for i, res in enumerate(tqdm(self._results, desc='[%s' % stageLabel)):
            context.append(res)
            if len(context) > self._contextLen:
                # in `context` index space:
                # 0 < ccontex len <= 10: no PP - building context
                # 10 < context len < 20: PP(i - 10) (i = 10: pp(0), i = 12: PP(2), i = 15: PP(5) )
                # i >= 20: 10 PP(10)
                preprocessedFrame = min(i - self._contextLen, self._contextLen - 1)
                yield (
                    context,
                    preprocessedFrame,
                    i + 1 - len(context), i)

        # preprocess missing frame
        # if there is less frame than the size of the context, we'll not have started processing any - time to do so
        # otherwise there is going to be oone context length of results that have been skipped
        while preprocessedFrame + 1 < len(context):
            preprocessedFrame += 1
            yield (
                context,
                preprocessedFrame,
                i + 1 - len(context), i)

    def __call__(self):
        processors = [
            ('Mark Flickering Faces', self._markFlickeringFaces),
            ('Identify Faces', self._identifyFaces),
            ('Mark Giggling Landmarks', self._markGigglingLandmarks),
            ('Smooth Face Positions', self._getSmoothedFaces),
            ('Finalization', self._finalize)
        ]

        frames = self._results
        processed = []
        prev = None
        for name, processor in tqdm(processors, desc='[Post-Processing'):
            for (context, frameI, contextStart, contextEnd) in self._framesWithContext(frames, name):
                prev = processor(context, frameI, contextStart, contextEnd, prev)
                processed.append(prev)

            frames = processed
            prev = None
            processed = []

        for item in frames:
            yield item


class AnalysisAggregator(object):
    """
    Aggregates all frame analysis results into a single object with the following properties:
    * `averageFaceRatio`: average ratio between detected covering face surface and image size
    * `faceTime`: number of frames holding a face
    * `faceTimeProp`: proportion of frames holding a face
    * ...
    """
    def __init__(self, results, start_t):
        super(AnalysisAggregator, self).__init__()
        self._results = results
        self._start_t = start_t

    def __call__(self, version):
        if len(self._results) == 0:
            raise Exception('No result to aggregate!')
        logging.info("Aggregating %d results..." % len(self._results))

        sums = [0, 0]
        for itm in tqdm(self._results, desc="[Aggregating results"):
            sums[0] += itm['faceRatio']
            sums[1] += 1.0 if len(itm['faces']) > 0 else 0.0

        return {
            '__version__': version,
            'averageFaceRatio': float(sums[0]) / len(self._results) * 100,
            'faceTime': sums[1],
            'faceTimeProp': float(sums[1]) / len(self._results) * 100,
            'duration': time.time() - self._start_t,
            'nbFrames': len(self._results)
        }
