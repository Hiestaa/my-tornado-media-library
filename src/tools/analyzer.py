# -*- coding: utf8 -*-

from __future__ import unicode_literals

from collections import deque
import logging
from threading import Thread
from enum import Enum
import time
import os
import subprocess
import io
import json
from datetime import datetime

from conf import Conf
from tools.utils import extends
from server import model


BASE_PATH = Conf['data']['videos']['rootFolder']

class Serializer(object):
    """Serialize a Google Cloud Vision Response to JSON-cp,[aton;e """
    class Likelihood(Enum):
        """
        A bucketized representation of likelihood, which is intended to give clients
        highly stable results across model upgrades.

        Attributes:
          UNKNOWN (int): Unknown likelihood.
          VERY_UNLIKELY (int): It is very unlikely that the image belongs to the specified vertical.
          UNLIKELY (int): It is unlikely that the image belongs to the specified vertical.
          POSSIBLE (int): It is possible that the image belongs to the specified vertical.
          LIKELY (int): It is likely that the image belongs to the specified vertical.
          VERY_LIKELY (int): It is very likely that the image belongs to the specified vertical.
        """
        UNKNOWN = 0
        VERY_UNLIKELY = 1
        UNLIKELY = 2
        POSSIBLE = 3
        LIKELY = 4
        VERY_LIKELY = 5

    @staticmethod
    def boundsToJSON(bounds):
        return [
            {'x': vertex.x, 'y': vertex.y}
            for vertex in bounds.vertices
        ]

    @staticmethod
    def locationsToJSON(locations):
        return [
            {'latitude': loc.latitude, 'longitude': loc.longitude}
            for loc in locations
        ]

    @staticmethod
    def entityToJSON(entity):
        return {
            # 'bounds': Serializer.boundsToJSON(entity.bounds),AnnotateImageRequest
            'description': entity.description,
            # 'location': Serializer.locationsToJSON(entity.locations),
            'mid': entity.mid,
            'score': entity.score
        }

    @staticmethod
    def faceToJSON(face):
        return {
            'anger_likelihood': Serializer.Likelihood(face.anger_likelihood).name.lower(),
            'joy_likelihood': Serializer.Likelihood(face.joy_likelihood).name.lower(),
            'sorry_likelihood': Serializer.Likelihood(face.sorrow_likelihood).name.lower(),
            'surprise_likelihood': Serializer.Likelihood(face.surprise_likelihood).name.lower(),
            'roll_angle': face.roll_angle,
            'pan_angle': face.pan_angle,
            'tilt_angle': face.tilt_angle,
            'bounding_poly': Serializer.boundsToJSON(face.bounding_poly),
            'detection_confidence': face.detection_confidence,
            'fd_bounding_poly': Serializer.boundsToJSON(face.fd_bounding_poly),
            'headwear_likelihood': Serializer.Likelihood(face.headwear_likelihood).name.lower(),
            'blurred_likelihood': Serializer.Likelihood(face.blurred_likelihood).name.lower(),
            'under_exposed_likelihood': Serializer.Likelihood(face.under_exposed_likelihood).name.lower(),
            'landmarks': [
                {
                    'type': LandmarkTypes(landmark.type).name.lower(),
                    'position': {
                        'x': landmark.position.x,
                        'y': landmark.position.y,
                        'z': landmark.position.z
                    }
                }
                for landmark in face.landmarks
            ],
            'landmarking_confidence': face.landmarking_confidence
        }

    @staticmethod
    def webToJSON(web):
        return {
            'web_entities': [
                {
                    'entity_id': ent.entity_id,
                    'score': ent.score,
                    'description': ent.description
                } for ent in web.web_entities
            ],
            'full_matching_images': [
                {
                    'url': image.url,
                    # 'score': image.score
                } for image in web.full_matching_images
            ],
            'partial_matching_images': [
                {
                    'url': image.url,
                    # 'score': image.score
                } for image in web.partial_matching_images
            ],
            'pages_with_matching_images': [
                {
                    'url': page.url,
                    # 'score': page.score
                } for page in web.pages_with_matching_images
            ]
        }

    @staticmethod
    def cropToJSON(crop_hint):
        return {
            'bounding_poly': Serializer.boundsToJSON(crop_hint.bounding_poly),
            'confidence': crop_hint.confidence,
            'importance_fraction': crop_hint.importance_fraction
        }

    @staticmethod
    def imagePropertiesToJSON(properties):
        return {
            'dominant_colors': [
                {'score': color.score, 'pixel_fraction': color.pixel_fraction, 'color': {
                    'red': color.color.red,
                    'green': color.color.green,
                    'blue': color.color.blue
                }} for color in properties.dominant_colors.colors
            ]
        }

    @staticmethod
    def responseToJSON(response, imagePath, duration=-1):
        """
        Convert the GCV response into a JSON-serializable object.
        Also add some metadata to the result, such as the current time and date,
        file path and analyze duration (if provided)
        """
        return {
            'version': vision.__version__,
            'analyzeTs': time.time(),
            'analyzeDate': datetime.utcnow().isoformat(),
            'analyzeDuration': duration,
            'path': imagePath.replace(BASE_PATH, ''),
            'name': os.path.basename(imagePath),
            'labels': map(Serializer.entityToJSON, response.label_annotations),
            'face': map(Serializer.faceToJSON, response.face_annotations),
            'crop': map(Serializer.cropToJSON, response.crop_hints_annotation.crop_hints),
            'web': Serializer.webToJSON(response.web_detection),
            'properties': Serializer.imagePropertiesToJSON(response.image_properties_annotation)
        }

class LargeBatchImageAnnotator(object):
    """
    Use Google Cloud Vision to submit image annotation for a large batch of images
    Save a cache of the result of the analysis on disk, so that we never submit
    a request for the same image twice.
    """
    BATCH_SIZE = 2
    def __init__(self, imgPaths):
        super(LargeBatchImageAnnotator, self).__init__()
        self.imgPaths = list(sorted(set(imgPaths)))  # don't query the same image twice

        self.client = vision.ImageAnnotatorClient()

    def _checkCache(self, imagePath):
        """
        Check existence of cached google cloud vision result for the given image
        Raises `ValueError` or `IOError` if the no cache data can be found
        Returns the result (note: already serialized) otherwise
        """
        cachePath = imagePath.replace('.png', '_gcv_raw.json')
        cachePath = cachePath.replace('.jpg', '_gcv_raw.json')
        with open(cachePath, 'r') as cacheFile:
            cacheData = json.load(cacheFile)
            if len(cacheData) == 0:
                raise ValueError("Empty cache")
            return cacheData

    def _cache(self, imagePath, serializedData):
        """
        Dump the serialized result into a json file sepecific to the given image.
        """
        cachePath = imagePath.replace('.png', '_gcv_raw.json')
        cachePath = cachePath.replace('.jpg', '_gcv_raw.json')
        try:
            with open(cachePath, 'w') as cacheFile:
                json.dump(serializedData, cacheFile)
        except Exception as e:
            logging.error("Unable to dump GCV result on disk.")
            pass

        return serializedData


    def nextBatch(self):
        """
        Process the next batch of images.
        Submit up to `BATCH_SIZE` images to google cloud vision for processing
        Returns a list of serialized results
        """
        start_batch = time.time()

        # list of requests submitted to GCV
        requests = []
        # list of image paths processed in this batch
        currentBatch = []
        # {<imagePath>: {'data': <cached data, if available>, 'index': <response index, otherwise>}}
        resultCache = {}

        while len(self.imgPaths) > 0 and len(requests) < self.BATCH_SIZE:
            imagePath = self.imgPaths.pop(0)
            currentBatch.append(imagePath)

            # check cache existence
            try:
                resultCache[imagePath] = {'data': self._checkCache(imagePath)}
                continue
            except (IOError, ValueError):
                pass

            # Loads the image into memory
            with io.open(imagePath, 'rb') as image_file:
                content = image_file.read()

                image = types.Image(content=content)

            # https://googlecloudplatform.github.io/google-cloud-python/latest/vision/gapic/v1/types.html#google.cloud.vision_v1.types.AnnotateImageRequest
            request = types.AnnotateImageRequest(image=image, features=[
                types.Feature(type=FeatureTypes.FACE_DETECTION, max_results=3),  # Run face detection.
                # types.Feature(type=FeatureTypes.LANDMARK_DETECTION),  # Run landmark detection.
                # types.Feature(type=FeatureTypes.LOGO_DETECTION),  # Run logo detection.
                types.Feature(type=FeatureTypes.LABEL_DETECTION, max_results=10),  # Run label detection.
                # types.Feature(type=FeatureTypes.TEXT_DETECTION),  # Run OCR.
                # types.Feature(type=FeatureTypes.DOCUMENT_TEXT_DETECTION),  # Run dense text document OCR. Takes precedence when both DOCUMENT_TEXT_DETECTION and TEXT_DETECTION are present.
                # types.Feature(type=FeatureTypes.SAFE_SEARCH_DETECTION),  # Run computer vision models to compute image safe-search properties.
                types.Feature(type=FeatureTypes.IMAGE_PROPERTIES),  # Compute a set of image properties, such as the image's dominant colors.
                types.Feature(type=FeatureTypes.CROP_HINTS, max_results=5),  # Run crop hints.
                types.Feature(type=FeatureTypes.WEB_DETECTION, max_results=10),  # Run web detection.
            ])

            resultCache[imagePath] = {'index': len(requests)}
            requests.append(request)

        logging.info("Submitting %d GCV requests...", len(requests))
        response = self.client.batch_annotate_images(requests=requests)
        duration = time.time() - start_batch
        logging.info("Received %d GCV responses (duration: %.3fs)",
                     len(response.responses), duration)

        return [
            resultCache[imagePath]['data']
            if 'data' in resultCache[imagePath] else
            self._cache(imagePath, Serializer.responseToJSON(
                response.responses[resultCache[imagePath]['index']],
                imagePath, duration / self.BATCH_SIZE))
            for imagePath in currentBatch
        ]

    def __call__(self):
        """
        Process the full batch of images in multiple batch requests.
        yield google cloud vision answer for each image in the batch, serialized as a
        JSON-compatible object to which some additional information have been added
        (file name, full file path, generation date / time and duration)
        """
        results = {}
        nbBatch = 0
        nbImages = len(self.imgPaths)
        while len(self.imgPaths) > 0:
            nbBatch += 1
            logging.info("Preparing batch #%d", nbBatch)
            try:
                for v in self.nextBatch():
                    yield v
            except Exception as e:
                logging.error("Error during batch #%d. Skipping.", nbBatch)
                logging.exception(e)
                if nbBatch > nbImages:
                    logging.error(
                        "Processed more batches than images - something must be wrong here.")
                    return


class MinividGeneratorMonitor(Thread):
    """
    Monitors every second on a separate thread the progression
    of the generation of the minivideo
    Whenever a new frame is created, call the given `callback` given
    the basename of the last file generated and the total number of frames
    generated so far.
    """
    def __init__(self, callback, path):
        super(MinividGeneratorMonitor, self).__init__()
        self._callback = callback
        self._path = path
        self._stop = False

    def stop(self):
        self._stop = True

    @staticmethod
    def getMinividFileList(minividFolder):
        return [
            file for file in os.listdir(minividFolder)
            if file.endswith('.png') and file.startswith(MinividGenerator.MINIVID_PREFIX)
        ]

    def run(self):
        logging.info("Monitor started (path=%s)", self._path)
        lastGeneratedFrame = None
        nbFrames = 0
        while not self._stop:
            time.sleep(0.1)
            minividFrames = MinividGeneratorMonitor.getMinividFileList(self._path)
            if len(minividFrames) == nbFrames:
                continue

            nbFrames = len(minividFrames)
            lastGeneratedFrame = sorted(minividFrames)[-1]

            logging.info("Monitor notifies [nbFrames=%d, lastGeneratedFrame=%s]" % (
                nbFrames, lastGeneratedFrame))
            self._callback(
                nbFrames=nbFrames,
                lastGeneratedFrame=lastGeneratedFrame)

        logging.info("Monitor interrupted")


class MinividGenerator(object):
    """
    Uses FFMPEG to extract frames from the video
    """
    MINIVID_PREFIX = 'minivid'

    def __init__(self, videoPath, snapshotsFolder):
        """
        Initialize the minivid generator for the given video
        Parameters:
        * `videoPath`: path to the video from which to extract frames
        * `snapshotsFolder`: path to the folder that contains snapshots,
            a `minivid_<w>_<h>_<skip>` folder will be created in there where the frames will be saved
        """
        super(MinividGenerator, self).__init__()
        videoPath = videoPath.replace('/', os.path.sep)
        videoPath = videoPath.replace('\\', os.path.sep)
        self._videoPath = videoPath
        self._snapshotsFolder = snapshotsFolder
        self._ssw = Conf['data']['ffmpeg']['minividDimension'][0]
        self._ssh = Conf['data']['ffmpeg']['minividDimension'][1]
        self._frameRate = Conf['data']['ffmpeg']['minividFrameRate']
        self._minividFolder = MinividGenerator.buildMinividFolderPath(self._snapshotsFolder)

    @staticmethod
    def buildMinividFolderPath(snapshotsFolder):
        _ssw = Conf['data']['ffmpeg']['minividDimension'][0]
        _ssh = Conf['data']['ffmpeg']['minividDimension'][1]
        _frameRate = Conf['data']['ffmpeg']['minividFrameRate']

        return os.path.join(
            snapshotsFolder,
            'minivid_%dx%d_%s' % (_ssw, _ssh, _frameRate.replace('/', '-')))

    @staticmethod
    def getMinividFPS(minvidFolder):
        rep = minvidFolder.split('_')[-1]
        rep = rep.split('-')
        return float(rep[0]) / float(rep[1])

    def __call__(self):
        """
        This will use ffmpeg to create a extract frames from the video.
        Returns the path in which the frames have been extracted
        """
        logging.info("Generating mini-video")
        spec = {
            'ffmpegpath': Conf['data']['ffmpeg']['exePath'],
            'videoPath': self._videoPath,
            'ssw': self._ssw,  # width
            'ssh': self._ssh,  # height
            'minividFolder': self._minividFolder,
            'frameRate': self._frameRate,
            'prefix': self.MINIVID_PREFIX,
        }
        command = '{ffmpegpath} -i "{videoPath}" -f image2 -vf fps=fps={frameRate} -s {ssw}x{ssh} "{minividFolder}\\{prefix}%04d.png"'

        return_code = 0
        # actual generation
        try:
            if not os.path.exists(spec['minividFolder']):
                os.mkdir(spec['minividFolder'])
            nbCreatedSnapshots = len(os.listdir(spec['minividFolder']))
            if nbCreatedSnapshots == 0:
                command = command.format(**spec)
                logging.info("> %s", command)
                return_code = subprocess.call(command, shell=True)
                nbCreatedSnapshots = len(os.listdir(spec['minividFolder']))
            else:
                data = extends(data, msg="Minivid found, generation not needed.")
        except Exception as e:
            logging.warning("Unable to generate minivid: %s." % repr(e).encode())
            return_code = 1

        if not os.path.exists(spec['minividFolder']) or nbCreatedSnapshots == 0 or return_code != 0:
            raise Exception("Unable to generaete minivid (nbCreatedSnapshots=%d, return_code=%d" % (
                nbCreatedSnapshots, return_code))
        return self._minividFolder

class MinividAnalyzer(object):
    """
    Use a `LargeBatchImageAnnotator` instance to annotate each frame of the minivid
    that is expected to be generated already
    """
    def __init__(self, minividFolder):
        super(MinividAnalyzer, self).__init__()
        self._minividFolder = minividFolder
        self._images = [os.path.join(self._minividFolder, img)
                        for img in os.listdir(self._minividFolder)
                        if img.endswith('.png')]

    def __len__(self):
        return len(self._images)

    def __call__(self):
        """
        Successively yield GCV results for each image found in the minivid folder
        Only *.png files will be processed (minivid generator is expected to generate png files)
        Call `len(analyzer)` to get the number of items expected to be generated in advance.
        """
        annotate = LargeBatchImageAnnotator(self._images)
        for result in annotate():
            yield result

class AnalysisPostProcessor(object):
    """
    Performs the post-processing of google cloud vision analysis results
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
            width = float(abs(faceDatum['bounding_poly'][2]['x'] - faceDatum['bounding_poly'][0]['x']))
            height = float(abs(faceDatum['bounding_poly'][2]['y'] - faceDatum['bounding_poly'][0]['y']))
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
        """
        processed = dict(**context[frameI])
        return extends(
            processed,
            contextStart=contextStart, contextStartFile=context[0]['name'],
            contextEnd=contextEnd, contextEndFile=context[-1]['name'],
            postProcessorVersion__=AnalysisPostProcessor.__version__,
            faceRatio=self._computeFaceRatio(context[frameI]['face']))

    def __call__(self):
        context = deque([], maxlen=(
            self._contextLen * 2))
        preprocessedFrame = -1
        for i, res in enumerate(self._results):
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
    def __init__(self, results):
        super(AnalysisAggregator, self).__init__()
        self._results = results

    def __call__(self):
        return {
            '__version__': AnalysisAggregator.__version__,
            'averageFaceRatio': sum(
                itm['faceRatio'] for itm in self._results
                if itm['faceRatio'] != 0) / len(self._results),
            'faceTime': sum(
                1.0 if len(itm['face']) > 0 else 0.0
                for itm in self._results),
            'faceTimeProp': sum(
                1.0 if len(itm['face']) > 0 else 0.0
                for itm in self._results) / len(self._results) * 100
        }


class GCVAnalyzer(Thread):
    """
    Object dedicated to the analysis of the content of the video using google cloud vision api.
    The intend is to extract all frames from the video (or half / third of them),
    pass them to google cloud vision for analysis, post-process the analysis in the context of
    other adjacent frames and finally aggregate the results to provide relevant video analysis results.
    During the execution, the `progress` parameter will be updated with information to report
    progression to the client.
    """
    def __init__(self, videoId, videoPath, snapshotsFolder,
                 progressCb=None, async=True, force=False):
        """
        Initialize an analyzer for the given video and snapshots folder
        (both given relative to the base video directory defined in the config file).
        If the snapshot folder doesn't exist it will be created.
        If `async` is set to True (default), the analyzer tasks will be performed on a separate thread
        The results of each intermediary step (minivid generation, analysis, post-processing and aggregation)
        are cached on disk, meaning that once they are retrieved / computed they will be reused as needed to
        avoid unecessary requests and computations. Use `force=true` to ignore cached data and force
        re-generation / computations.
        If `progressCb` is given, it is expected to be a callback to be called whenever the
        the analysis progresses. Each progress call will pass a dict as parameter that will hold the
        fields listed below.
        Beware that the call will happen on the child thread.
        Use e.g. tornado's IOLoop to schedule a callback on the main thread.
        * `file`: the name of the current file being processed
        * `step`: the processing step currently applied to this file
        * `duration`: times spent on the process
        * `finished`: False unless the whole analyze process is finished.
        * `nb_frames`: number of frames extracted from this video
        * `generation_complete`: False unless all frames have been extracted from this video
        * `frame_number`: frame currently being generated/analyzed/processed.
            Note: during the generation there might not be a progress call for every single
            generated image. One should rely on `nb_frames` to know the number of frames generated so far.
        * `data_type` type of data being sent - either:
            * 'init': the data will contain nothing, used to indicate the first progress call of the process
            * 'frame': the data will contain nothing (use `nb_frames`)
            * 'annotation_raw': the data will contain a raw annotation for the current frame,
                where the annotation is a full GCV response serialized to a JSON compatible format
                (see: `Serializer` above). There will be one annotation for each extracted frame of the video
            * 'annotation': data will contain updated annotation from post-processing algorithm in context.
                Each frame is analyzed by google independently from the rest of the video,
                but we can be smart about the results knowing the context in which they were extracted.
                For instance, a face detected in a single frame but not in the previous or following one
                is likely to be a mistake, while a face detected in 100 frames in a raw that stays more
                or less the same size and position is much more likely to be a real one.
                Similarily, if no face is detected in a frame but a face is detected in all
                50 previous frames and all 50 following frames it is likely that the face is actually
                there but was missed by google cloud engine.
            * `aggregation`: data will contain a dict describing the result of the aggregation of all annotated frames.
                This includes the time face ratio, pixel face ratio, time eye ratio, number of pictured humans,
                mapping of tags / web entities to the number time google actually mentionned it, etc..
        * `data`: actual data being sent
        """
        super(GCVAnalyzer, self).__init__()
        logging.info("Initializing new %s analyzer"
                     % ('asynchroneous' if async else ''))
        self._async = async
        self._start_t = time.time()

        self._videoPath = '%s%s' % (BASE_PATH, videoPath)
        self._videoId = videoId
        self._snapshotsFolder = '%s%s' % (BASE_PATH, snapshotsFolder)
        self._progress = {}
        self._progressCb = progressCb
        self._force = force

        if not os.path.exists(self._snapshotsFolder):
            os.mkdir(self._snapshotsFolder)

    def start(self):
        if self._async:
            logging.info("Starting analyzer process asynchroneously")
            super(GCVAnalyzer, self).start()
        else:
            logging.info("Starting analyzer process")
            self.run()

    def run(self):
        # Imports the Google Cloud client library
        from google.cloud import vision
        from google.cloud.vision import types
        from google.cloud.vision.feature import Feature, FeatureTypes
        from google.cloud.vision.face import LandmarkTypes

        self.initProgress(
            file=self._videoPath.replace(BASE_PATH, ''),
            step='Initializing',
            finished=False,
            nb_frames=0,
            generation_complete=False)

        minividFolder = self._generateMinivid()
        self.progress(
            'frame',
            None,
            generation_complete=True,
            nb_frames=len(MinividGeneratorMonitor.getMinividFileList(minividFolder)))
        results = self._analyzeMinivid(minividFolder)
        ppResults = self._postProcessAnalyzis(results, minividFolder)
        aggregate = self._aggregateAnalyzis(ppResults, minividFolder)

        self.progress(
            dataType='aggregation',
            data=aggregate,
            file=self._videoPath,
            step='Analyze complete',
            finished=True)

        return aggregate

    def initProgress(self, **kwargs):
        """
        Initialize the progress dict with information that should be added to each progress call.
        """
        self._progress = extends(kwargs, **self._progress)
        if self._progressCb:
            self._progressCb(self._videoId, extends(
                {}, data_type='init', data=None, **self._progress))


    def progress(self, dataType, data, **kwargs):
        """
        `data` and `dataType` are just passed along in the progress call
        all additional keyword arguments will be retained and passed with each subsequent call
        """
        self._progress['duration'] = time.time() - self._start_t
        self._progress = extends(kwargs, **self._progress)
        if self._progressCb:
            self._progressCb(self._videoId, extends(
                {}, data_type=dataType, data=data, **self._progress))

    def _minividGenerationProgress(self, nbFrames, lastGeneratedFrame):
        self.progress(dataType='frame', data=None,
                      frame_number=lastGeneratedFrame, nb_frames=nbFrames)

    def _generateMinivid(self):
        logging.info("Generating minivid for video: %s" % self._videoPath)
        minividFolder = MinividGenerator.buildMinividFolderPath(self._snapshotsFolder)
        if not self._force and os.path.isdir(minividFolder) and len(os.listdir(minividFolder)) > 0:
            logging.info(
                "Minivid folder exists and is not empty - generation skipped (set force=true): %s",
                 minividFolder)
            return minividFolder

        generator = MinividGenerator(self._videoPath, self._snapshotsFolder)
        monitor = MinividGeneratorMonitor(path=minividFolder, callback=self._minividGenerationProgress)
        monitor.start()
        minividFolder = generator()
        monitor.stop()
        monitor.join()
        return minividFolder

    def _pushAllAnalysisProgress(self, dataType, allData, stepTitle):
        """
        Push analysis progress calls for the cached data retrieved from hard drive.
        """
        for i, res in enumerate(allData):
            self.progress(dataType=dataType, data=res, frame_number=i,
                          stepTitle=stepTitle % (i),
                          file=res['name'])

    def _analyzeMinivid(self, minividFolder):
        logging.info("Performing analysis from minivid in folder: %s" % minividFolder)
        jsonDump = os.path.join(minividFolder, 'analysis_gcv_raw.json')
        if not self._force and os.path.exists(jsonDump):
            try:
                with open(jsonDump, 'r') as f:
                    results = json.load(f)
                    if len(results) > 0:
                        logging.info(
                            "GCV raw results found - analysis skipped (set force=true): %s",
                            jsonDump)
                        self._pushAllAnalysisProgress(
                            'annotation_raw', results, 'Minivid analysis, frame #%d')
                        return results
            except:
                pass
        analyzer = MinividAnalyzer(minividFolder)
        # breaking the generator chain here - holding all results in memory shouldn't be an issue
        # also we need the full list to dump it on disk before passing to the post-processing step
        results = []
        for i, res in enumerate(analyzer()):
            results.append(res)
            self.progress(dataType='annotation_raw', data=res, frame_number=i,
                          step='Minivid analysis, frame #%d' % (len(results)),
                          file=res['name'])

        with open(jsonDump, 'w') as f:
            json.dump(results, f)

        return results

    def _postProcessAnalyzis(self, results, minividFolder):
        logging.info("Performing post-processing from analysis of %d frames" % len(results))
        jsonDump = os.path.join(minividFolder, 'analysis_gcv_pp.json')
        if not self._force and os.path.exists(jsonDump):
            try:
                with open(jsonDump, 'r') as f:
                    results = json.load(f)
                    if len(results) > 0:
                        logging.info(
                            "GCV post-processed results found - analysis skipped (set force=true): %s",
                            jsonDump)
                        self._pushAllAnalysisProgress(
                            'annotation', results, 'Minivid analysis post-processing, frame #%d')
                        return results
            except:
                pass
        processor = AnalysisPostProcessor(results)
        ppResults = []
        # breaking the generator chain here - holding all results in memory shouldn't be an issue
        # also we need the full list to dump it on disk before passing to the post-processing step

        for i, res in enumerate(processor()):
            ppResults.append(res)
            self.progress(
                dataType='annotation', data=res, frame_number=i,
                step='Minivid analysis post-processing, frame #%d' % (len(ppResults)),
                file=res['name'])

        with open(jsonDump, 'w') as f:
            json.dump(ppResults, f)
        return ppResults

    def _aggregateAnalyzis(self, results, minividFolder):
        logging.info("Performing aggregation from analysis of %d frames" % len(results))
        jsonDump = os.path.join(minividFolder, 'analysis_gcv_aggreg.json')
        if not self._force and os.path.exists(jsonDump):
            try:
                with open(jsonDump, 'r') as f:
                    results = json.load(f)
                    if len(results.items()) > 0:
                        logging.info(
                            "GCV post-processed results found - analysis skipped (set force=true): %s",
                            jsonDump)
                        return results
            except:
                pass
        aggregator = AnalysisAggregator(results)
        aggregResults = aggregator()
        with open(jsonDump, 'w') as f:
            json.dump(aggregResults, f)
        return aggregResults
