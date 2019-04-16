# -*- coding: utf8 -*-

from __future__ import unicode_literals

from collections import deque
import logging
from threading import Thread, Event
from enum import Enum
import time
import os
import subprocess
import io
import json
from datetime import datetime
from tqdm import tqdm

from conf import Conf
from tools.utils import extends, timeFormat
from tools.workspace import Workspace

from tools.analyzer.analyzers import MinividAnalyzer, AnalysisPostProcessor, AnalysisAggregator
from tools.analyzer.minivid import MinividGeneratorMonitor, MinividGenerator

BASE_PATH = Conf['data']['videos']['rootFolder']

class Analyzer(Thread):
    """
    Object dedicated to the analysis of the content of the video using google cloud vision api.
    The intend is to extract all frames from the video (or half / third of them),
    pass them to google cloud vision for analysis, post-process the analysis in the context of
    other adjacent frames and finally aggregate the results to provide relevant video analysis results.
    During the execution, the `progress` parameter will be updated with information to report
    progression to the client.
    """
    __version__ = '0.1.0'
    def __init__(self, videoId, videoPath, snapshotsFolder,
                 progressCb=None, async=True, force=False,
                 annotator='dfl-mt', videoDuration=0, autoCleanup=False):
        """
        Initialize an analyzer for the given video and snapshots folder
        (both given relative to the base video directory defined in the config file).
        If the snapshot folder doesn't exist it will be created.
        If `autoCleanup` is enabled, the workspace will be automatically cleaned up from temporary analysis files
        If `async` is set to True (default), the analyzer tasks will be performed on a separate thread
        The results of each intermediary step (minivid generation, analysis, post-processing and aggregation)
        are cached on disk, meaning that once they are retrieved / computed they will be reused as needed to
        avoid unecessary requests and computations. Use `force=true` to ignore cached data and force
        re-generation / computations (doesn't apply to minivid generation as this likely won't change).
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
                where the annotation is a full annotation response serialized to a JSON compatible format
                (see: `Serializer` above). There will be one annotation for each extracted frame of the video
                Note that annotation_raw can happen many time for multiple stages of the analysis,
                and that data may only be provided partially
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
        super(Analyzer, self).__init__()
        logging.debug("Initializing new %s analyzer"
                     % ('asynchroneous' if async else ''))
        self._async = async
        self._start_t = time.time()
        self._completed = False

        self._videoPath = '%s%s' % (BASE_PATH, videoPath)
        self._videoId = videoId
        self._snapshotsFolder = '%s%s' % (BASE_PATH, snapshotsFolder)
        self._progress = {}
        self._progressCb = progressCb
        self._force = force
        self._annotator = annotator
        self._videoDuration = int(videoDuration)
        self._workspace = Workspace()
        self._stop_event = Event()
        self._minividFolder = MinividGenerator.buildMinividFolderPath(self._workspace, self._snapshotsFolder)
        self._minividGenerator = None
        self._analyzer = None
        self._autoCleanup = autoCleanup

        if not os.path.exists(self._snapshotsFolder):
            os.makedirs(self._snapshotsFolder)

    def resubscribe(self, progressCb):
        self._progressCb = progressCb

    def start(self):
        if self._async:
            logging.debug("Starting analyzer process asynchroneously")
            super(Analyzer, self).start()
        else:
            logging.debug("Starting analyzer process")
            self.run()

    def stop(self):
        self._stop_event.set()
        self._completed = True

    @staticmethod
    def cleanup(snapshotsFolder):
        MinividGenerator.cleanup(
            MinividGenerator.buildMinividFolderPath(
                Workspace(), '%s%s' % (BASE_PATH, snapshotsFolder)))

    def isComplete(self):
        return self._completed

    def _stopped(self):
        return self._stop_event.is_set()

    def run(self):
        progressBar = tqdm(total=5 if self._autoCleanup else 4, desc="[Analysis Step: Initializing")
        self.initProgress(
            file=self._videoPath.replace(BASE_PATH, ''),
            step='Initializing',
            finished=False,
            nb_frames=0,
            generation_complete=False)

        progressBar.set_description('[Analysis Step: Minivid Generation')
        progressBar.update()
        if self._stopped():
            return

        minividFolder = self._generateMinivid()
        self.progress(
            'frame',
            None,
            generation_complete=True,
            nb_frames=len(MinividGeneratorMonitor.getMinividFileList(minividFolder)))

        progressBar.set_description('[Analysis Step: Minivid Analysis')
        progressBar.update()
        if self._stopped():
            return

        results = self._analyzeMinivid(minividFolder)

        progressBar.set_description('[Analysis Step: Minivid Post-Processing')
        progressBar.update()
        if self._stopped():
            return

        ppResults = self._postProcessAnalyzis(results)

        progressBar.set_description('[Analysis Step: Analysis Aggregation')
        progressBar.update()
        if self._stopped():
            return

        aggregate = self._aggregateAnalyzis(ppResults)

        if self._autoCleanup:
            progressBar.set_description('[Analysis Step: Temporary Data Cleanup')
            progressBar.update()
            MinividGenerator.cleanup(minividFolder)

        progressBar.close()
        if self._stopped():
            return

        self.progress(
            dataType='aggregation',
            data=aggregate,
            file=self._videoPath,
            step='Analyze complete',
            finished=True)

        self._completed = True
        logging.info(
            "Analysis of video %s completed in %s!",
            self._videoPath.replace(BASE_PATH, ''),
            timeFormat(time.time() - self._start_t))

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
        if self._stopped():
            self._minividGenerator.stop()

        self.progress(dataType='frame', data=None, step="Minivid generation, frame #%d" % nbFrames,
                      frame_number=lastGeneratedFrame, nb_frames=nbFrames)

    def _shouldGenerateMinivid(self, minividFolder):
        jsonDump = self._rawAnalysisDump(minividFolder)
        return self._force or not os.path.exists(jsonDump)

    def _generateMinivid(self):
        logging.debug("Generating minivid for video: %s" % self._videoPath)
        minividFolder = self._minividFolder

        if not self._shouldGenerateMinivid(minividFolder):
            logging.info("Minivid generation skipped for video: %s - cache data found already", self._videoPath)
            return minividFolder

        expectedNbFrames = MinividGeneratorMonitor.computeExpectedNbFrames(self._videoDuration)
        try:
            foundNbFrames = len(os.listdir(minividFolder))
        except FileNotFoundError:
            foundNbFrames = 0

        if foundNbFrames >= expectedNbFrames:
            logging.info(
                "Minivid folder exists and contains all %d expected frames - generation skipped: %s",
                 expectedNbFrames, minividFolder)
            return minividFolder

        if foundNbFrames > 0:
            logging.info("Minivid found with %d of %d frames - cleanup needed.",
                         foundNbFrames, expectedNbFrames)
            MinividGenerator.cleanup(minividFolder)

        self._minividGenerator = MinividGenerator(
            self._videoPath, self._snapshotsFolder, self._videoDuration, silent=True)
        monitor = MinividGeneratorMonitor(
            path=minividFolder, callback=self._minividGenerationProgress,
            duration=self._videoDuration, generator=self._minividGenerator)
        monitor.start()
        minividFolder = self._minividGenerator()
        monitor.stop()
        try:
            # should terminate by itself once it reported having generated all the frames it expect
            monitor.join()
        except Exception as e:
            logging.warning(
                "Unable to wait for monitor thread to end. "
                "This won't interrupt the analysis process.")
            logging.exception(e)
            pass

        return minividFolder

    def _pushAllAnalysisProgress(self, dataType, allData, stepTitle):
        """
        Push analysis progress calls for the cached data retrieved from hard drive.
        """
        for i, res in enumerate(allData):
            self.progress(dataType=dataType, data=res, frame_number=i,
                          stepTitle=stepTitle % (i),
                          file=res['name'])

    def _analyzerProgress(self, frameNumber, data):
        if self._stopped():
            self._analyzer.stop()

        self.progress(dataType='annotation_raw', data=data, frame_number=frameNumber,
                      step='Minivid analysis, frame #%d' % (frameNumber),
                      file=data['name'])

    def _rawAnalysisDump(self, minividFolder):
        return os.path.join(self._snapshotsFolder, "%s-analysis_%s_raw.json" % (
            os.path.basename(minividFolder), self._annotator))

    def _analyzeMinivid(self, minividFolder):
        logging.info("Performing analysis from minivid in folder: %s" % minividFolder)
        jsonDump = self._rawAnalysisDump(minividFolder)
        # if os.path.exists(jsonDump):
        if not self._force and os.path.exists(jsonDump):
            try:
                with open(jsonDump, 'r') as f:
                    results = json.load(f)
                    if len(results) > 0:
                        logging.info(
                            "Raw annotation results found - analysis skipped (set force=true): %s",
                            jsonDump)
                        # self._pushAllAnalysisProgress(
                        #     'annotation_raw', results, 'Minivid analysis, frame #%d')
                        return results
            except:
                pass

        try:
            foundNbFrames = len(os.listdir(minividFolder))
        except FileNotFoundError:
            foundNbFrames = 0

        self._analyzer = MinividAnalyzer(minividFolder, annotator=self._annotator, progress=self._analyzerProgress)

        # breaking the generator chain here - holding all results in memory shouldn't be an issue
        # also we need the full list to dump it on disk before passing to the post-processing step
        results = []
        for i, res in enumerate(self._analyzer()):
            if self._stopped():
                self._analyzer.stop()
                return results  # don't save the cache if process was interrupted
            results.append(res)

        # don't dump if we don't have the full resultset!
        if len(results) > 0 and len(results) == foundNbFrames and not self._stopped():
            with open(jsonDump, 'w') as f:
                json.dump(results, f)

        return results

    def _postProcessAnalyzis(self, results):
        logging.info("Performing analysis post-processing of %d frames", len(results))
        jsonDump = os.path.join(self._snapshotsFolder, "%s-analysis_%s_pp.json" % (
            os.path.basename(self._minividFolder), self._annotator))
        if not self._force and os.path.exists(jsonDump):
            try:
                with open(jsonDump, 'r') as f:
                    results = json.load(f)
                    if len(results) > 0:
                        logging.info(
                            "Post-processed annotation results found - analysis skipped (set force=true): %s",
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
            if self._stopped():
                return ppResults  # don't save the cache if process was interrupted

            ppResults.append(res)
            self.progress(
                dataType='annotation', data=res, frame_number=i,
                step='Minivid analysis post-processing, frame #%d' % (len(ppResults)),
                file=res['name'])

        if len(ppResults) > 0 and len(ppResults) == len(results) and not self._stopped():
            with open(jsonDump, 'w') as f:
                json.dump(ppResults, f)
        return ppResults

    def _aggregateAnalyzis(self, results):
        logging.debug("Performing aggregation from analysis of %d frames" % len(results))
        jsonDump = os.path.join(self._snapshotsFolder, "%s-analysis_%s_aggreg.json" % (
            os.path.basename(self._minividFolder), self._annotator))
        if not self._force and os.path.exists(jsonDump):
            try:
                with open(jsonDump, 'r') as f:
                    results = json.load(f)
                    if len(results.items()) > 0:
                        logging.info(
                            "Aggregated annotation results found - analysis skipped (set force=true): %s",
                            jsonDump)
                        return results
            except:
                pass
        aggregator = AnalysisAggregator(results, self._start_t)
        aggregResults = aggregator(Analyzer.__version__)
        with open(jsonDump, 'w') as f:
            json.dump(aggregResults, f)
        return aggregResults
