# -*- coding: utf8 -*-

from __future__ import unicode_literals
import logging
from threading import Thread
import random
import os
import subprocess
import time
import io
import json
import shutil
from datetime import datetime

from conf import Conf
from tools.utils import extends, getDuration
from tools.analyzer import MinividGenerator
from tools.workspace import Workspace
from server import model


BASE_PATH = Conf['data']['videos']['rootFolder']


class CompilerException(Exception):
    pass

def toHHMMSS(seconds):
    return '%02d:%02d:%02d' % (seconds / 3600, (seconds / 60) % 60, seconds % 60)

class SegmentCandidateGenerator(object):
    """
    Generates candidates of segments of the desired length among analyzed videos
    A segment is an object with the following properties:
    * `videoId`: id of the video the segment comes from
    * `videoPath`: path to the video the segment comes from
    * `startMinividFrame`: segment starting frame number in the minivid
    * `endMinividFrame`: segment ending frame number in the minivid
    * `startTime`: segment starting time, in seconds
    * `endTime`: segment ending time, in seconds
    * `startTimeS`: segment starting time, in `HH:MM:SS` format
    * `endTimeS`: segment ending time, in `HH:MM:SS` format
    * `label`: `{name: freq}` mapping of labels, where `freq` is the number of occurrences
               of each label in the frames of the segment
    * `nbPerformers`: estimation of the number of performers based on the maximum number of
                      faces detected in the same frame of the video
    * `frameProps`: list of properties for each frame in the segment:
        * `face`: `[{x, y, width, height}]` position and size of the faces, if detected
        * `labels`: `{name: confidence}` labels associated with this frame
    """
    MAX_GAP_BETWEEN_SEGMENTS_FACTOR = 0.5
    EXTENSION_TOLERANCE = 2.0
    def __init__(self, filters, minSegmentLength=5, maxSegmentLength=30, hardLimits=False, **kwargs):
        """
        Initialize the generators with the given filters. These should be a valid criteria
        to pass to `VideoService.find()`
        The following options can be provided as keyword arguments:
        * `minSegmentLength` to set a lower bound to the duration of the segment in seconds, default: 5
        * `maxSegmentLength` to set an upper bound to the duration of the segment in seconds, default: 30
        * `hardLimits`: by default limits are advices that can be exceeded for the sake
          of a better transition. Enable to never go out of bounds.
        """
        super(SegmentCandidateGenerator, self).__init__()
        logging.info("Initializing SegmentCandidateGenerator(minSegmentLength=%d, maxSegmentLength=%d, hardLimits=%s",
                     minSegmentLength, maxSegmentLength, str(hardLimits))
        self.filters = filters
        self.minSegmentLength = minSegmentLength
        self.maxSegmentLength = maxSegmentLength
        self.hardLimits = hardLimits
        self._workspace = Workspace()

    def _getAnalysisData(self, video):
        snapshotsFolder = '%s%s' % (BASE_PATH, video['snapshotsFolder'])
        minividFolder = MinividGenerator.buildMinividFolderPath(self._workspace, snapshotsFolder)
        # FIXME: grab the analysis data from the snapshot folder
        jsonPath = os.path.join(minividFolder, 'analysis_gcv_pp.json')

        try:
            with open(jsonPath, 'r') as f:
                return json.load(f)
        except:
            raise Exception("Unable to load pp analysis data from file: %s" % (jsonPath))

    def _getFrameDelay(self,  video):
        # FIXME: get frame delay from the video analysis aggregation duration and frame count
        snapshotsFolder = '%s%s' % (BASE_PATH, video['snapshotsFolder'])
        minividFolder = MinividGenerator.buildMinividFolderPath(self._workspace, snapshotsFolder)
        fps = MinividGenerator.getMinividFPS(minividFolder)
        fdelay = 1.0 / fps
        return fdelay

    def _segmentStartCriteria(self, annotation):
        # TODO: face -> faces and other gcv to dfl field conversion
        return len(annotation['face']) > 0

    def _segmentEndCriteria(self, annotation):
        return len(annotation['face']) == 0

    def _reachedMaxLength(self, start, end, fdelay):
        """
        Function called for each possible [start, currentFrame] segment until the segment
        end is reached. It returns wether the segment should be cut here, despite that we
        didn't detect a termination criteria for this statement.
        We consider the segment has reached the maximum length if:
        * segment has is at 95% of the upper bound duration and hard limit is set
        * 5% chance if segment has exceeded the lower bound
        * 10% chance if prev segment exceeded the upper bound (no hard limit)
        * the prev segment has reached / is 20% to EXTENSION_TOLERANCE * upper_boundhen:
        """
        if start is None or end is None:
            return False
        segmentLength = abs(end - start) * fdelay
        if segmentLength > 0.95 * self.maxSegmentLength and self.hardLimits:
            return True
        if segmentLength > self.minSegmentLength and random.random() > 0.95:
            return True
        if segmentLength > self.maxSegmentLength and random.random() > 0.90:
            return True
        if segmentLength > 0.95 * self.EXTENSION_TOLERANCE * self.maxSegmentLength:
            return True

        return False

    def _isTooShort(self, start, end, fdelay):
        segmentLength = abs(end - start) * fdelay
        if segmentLength < self.minSegmentLength and self.hardLimits:
            return True
        if segmentLength < float(self.minSegmentLength) / max([1, self.EXTENSION_TOLERANCE]):
            return True

        return False

    def _getMaxNbFaces(self, data):
        return max(len(ann['face']) for ann in data)

    def _generateCandidatesFrom(self, video, fdelay, data):
        segmentNb = 0
        segmentStart, segmentEnd = None, None
        isProcessingSegment = False
        for frameI, annotation in enumerate(data):
            # start a new segment
            if segmentStart is None and self._segmentStartCriteria(annotation):
                logging.debug("Segment #%d starts at frame #%d", segmentNb, frameI)
                segmentStart = frameI

            # end a segment
            if segmentStart is not None and segmentEnd is None and self._segmentEndCriteria(annotation):
                logging.debug("Segment #%d ends at frame #%d", segmentNb, frameI)
                segmentEnd = frameI

            if self._reachedMaxLength(segmentStart, frameI, fdelay):
                segment = (segmentStart, frameI)
                logging.debug("Generating candidate segment: [%d-%d]", *segment)
                segmentStart = None
                segmentEnd = None
                segmentNb += 1
                yield segment

            elif segmentEnd is not None:
                # segment finished - yield it.
                # It might be too small, but min-duration criteria will be checked after merge
                segment = (segmentStart, segmentEnd)
                logging.debug("Generating candidate segment: [%d-%d]", *segment)
                segmentStart = None
                segmentEnd = None
                segmentNb += 1
                yield segment

    def _shouldMerge(self, prev, cur, fdelay):
        # if any of the segment is smaller than the gap (a ratio of the gap actually), don't merge
        gapSizeRatio = self.MAX_GAP_BETWEEN_SEGMENTS_FACTOR * abs(cur[0] - prev[1])
        if (abs(prev[1] - prev[0]) < gapSizeRatio or
            abs(cur[1] - cur[0]) < gapSizeRatio):
            return False

        # if the result of the merge would produce a segment that is longer than the imposed limit, don't
        if ((self.hardLimits and fdelay * abs(cur[1] - prev[0]) > self.maxSegmentLength) or
            (not self.hardLimits and fdelay * abs(cur[1] - prev[0]) > self.maxSegmentLength * self.EXTENSION_TOLERANCE)):
            return False

        return True

    def _mergeAttempts(self, candidates, fdelay):
        """
        Attempt to merge candidates.
        Two segments will be merged into one if the gap between the two is smaller
        than a ratio of the length of the segment.
        `candidates` is a list of (start, end) tuples.
        """
        prev = None
        cur = None
        for (start, end) in candidates:
            if prev is None:
                prev = (start, end)
            elif cur is None:
                cur = (start, end)

            if prev is not None and cur is not None:
                if self._shouldMerge(prev, cur, fdelay):
                    logging.info(
                        "Merging segments: [%d-%d:%d-%d]",
                        prev[0], prev[1], cur[0], cur[1])
                    # merge segments and keep going, we might merge further more
                    prev = prev[0], cur[1]
                    cur = None
                else:
                    yield prev
                    prev = cur
                    cur = None

        yield prev

    def _computeLabels(self, data):
        res = {}
        for annotation in data:
            for label in annotation['labels']:
                res[label['description']] = res.get(label['description'], 0) + 1
        return res

    def _getFrameData(self, annotation):
        def faceData(face):
            x = face['bounding_poly'][0]['x']
            y = face['bounding_poly'][0]['y']
            x2 = face['bounding_poly'][3]['x']
            y2 = face['bounding_poly'][3]['y']

            return {
                'x': min([x, x2]),
                'y': min([y, y2]),
                'width': abs(x2 - x),
                'height': abs(y2 - y)
            }

        return {
            'face': map(faceData, annotation['face']),
            'labels': {
                label['description']: label['score']
                for label in annotation['labels']
            }
        }

    def _buildSegment(self, video, fdelay, data, start, end, nbPerformers):
        snapshotsFolder = '%s%s' % (BASE_PATH, video['snapshotsFolder'])
        minividFolder = MinividGenerator.buildMinividFolderPath(self._workspace, snapshotsFolder)
        fps = MinividGenerator.getMinividFPS(minividFolder)
        fdelay = 1.0 / fps

        return {
            'videoId': video['_id'],
            'videoPath': os.path.join(BASE_PATH, video['path']),
            'startMinividFrame': start,
            'endMinividFrame': end,
            'startTime': start * fdelay,
            'endTime': end * fdelay,
            'startTimeS': toHHMMSS(start * fdelay),
            'endTimeS': toHHMMSS(end * fdelay),
            'label': self._computeLabels(data[start:end]),
            'nbPerformers': nbPerformers,
            'frameProps': map(self._getFrameData, data[start:end])
        }

    def __call__(self):
        logging.info("Loading analyzed videos")
        videos = model.getService('video').find(self.filters, analyzed_only=True)
        for video in videos:
            try:
                fdelay = self._getFrameDelay(video)
                data = self._getAnalysisData(video)
                maxNbFaces = self._getMaxNbFaces(data)
                logging.info("Generating segments from video: %s", video['name'])
                segments = list(self._generateCandidatesFrom(video, fdelay, data))
                logging.info("Before merge: %d segments (video: %s)",
                             len(segments), video['name'])

                nbSegments = 0
                for segment in self._mergeAttempts(segments, fdelay):
                    if not self._isTooShort(segment[0], segment[1], fdelay):
                        nbSegments += 1
                        yield self._buildSegment(
                            video, fdelay, data, segment[0], segment[1], maxNbFaces)
                    else:
                        logging.debug("Discarding too short segment: [%d-%d]", *segment)

                logging.info("After merge: %d segments (video: %s)",
                             nbSegments, video['name'])
            except Exception as e:
                logging.error("Unable to generate candidates from video: %s", video['path'])
                logging.exception(e)


class SegmentsSelector(object):
    """
    Select segments based on the specified strategy in order to produce
    the final list of segments that will be assembled
    """
    def __init__(self, candidates, duration=600, strategy=None, reorder=None,
                 crossfadeDuration=10, **kwargs):
        super(SegmentsSelector, self).__init__()
        logging.info("Initializing SegmentsSelector(duration=%d, strategy=%s)",
                     duration, str(strategy))
        self.candidates = candidates
        self.duration = duration
        self.strategies = {
            'random': self.randomStrategy
        }
        self.strategy = strategy or 'random';
        self.strategyFn = self.strategies[strategy];
        self.reorder = reorder
        self.crossfadeDuration = crossfadeDuration

    def randomStrategy(self):
        """
        Most simple possible strategy: Select segments among candidates
        in a purely random fashion. The only two constraints are:
        * Don't pick twice in a raw a segment from the same video
        * Stop when the total duration reached the expected one.
        """
        candidates = list(self.candidates)
        totalDuration = 0
        lastVideo = None
        while totalDuration < self.duration:
            if lastVideo is None:
                pick = random.randint(0, len(candidates))
            else:
                picks = random.sample(range(len(candidates)), 10)
                if all(candidates[p]['videoId'] == lastVideo for p in picks):
                    continue  # attempt a new draw
                pick = next(p for p in picks if candidates[p]['videoId'] != lastVideo)

            candidate = candidates.pop(pick)
            newLength = candidate['endTime'] - candidate['startTime']
            oldTotalDuration = totalDuration
            totalDuration += newLength - self.crossfadeDuration
            if totalDuration < self.duration:
                yield candidate, totalDuration
            else:
                # if we're exceeding the total duration, we still might want to get it in
                # adding it will lower the gap between total duration and expected duration
                if abs(self.duration - totalDuration) < abs(self.duration - oldTotalDuration):
                    yield candidate, totalDuration
            lastVideo = candidate['videoId']

    def orderByDuration(self, desc, segments):
        return sorted(segments, key=lambda data: data[0]['endTime'] - data[0]['startTime'], reverse=desc)

    def orderByVideo(self, segments):
        return sorted(segments, key=lambda data: data[0]['videoId'])

    def __call__(self):
        logging.info("Selecting segments using strategy %s among %d candidates",
                     self.strategy, len(self.candidates))
        strategyFn = {
            'original': lambda: self.strategyFn(),
            'durationAsc': lambda: self.orderByDuration(False, self.strategyFn()),
            'durationDesc': lambda: self.orderByDuration(True, self.strategyFn()),
            'video': lambda: self.orderByVideo(self.strategyFn())
        }[self.reorder]

        for (segment, duration) in strategyFn():
            logging.debug("[%s] Selected segment [%s-%s] from video: %s",
                          toHHMMSS(duration),
                          segment['startTimeS'], segment['endTimeS'],
                          os.path.basename(segment['videoPath']))
            yield segment


class SegmentFilter(object):
    """
    Represents one list of filters to be applied to the given segment.
    The object stores information required to build the filter complex allowing the
    compilation of the video
    """
    def __init__(self,  filters, inputPad, outputPad, ftype='video'):
        super(SegmentFilter, self).__init__()
        self.filters = filters
        self.inputPad = inputPad
        self.outputPad = outputPad
        self.ftype = ftype

    def render(self):
        return "%s%s%s" % (self.inputPad, self.filters, self.outputPad)

    def renderPP(self):
        return "  %s\n    %s\n  %s ;" % (
            self.inputPad,
            ',\n    '.join(self.filters.split(',')),
            self.outputPad)

    @staticmethod
    def scaleIfNeeded(needed=False):
        if needed:
            return ['scale=height=1080:width=-1'];
        else:
            return []

    @staticmethod
    def introFadeIn(inputStream, inputAudio, segment, fadeDuration):
        """
        Build the filter that trims the video for this segment,
        applies a fade-in effect to the first few seconds of the segment,
        and concatenate the result.
        Parameters:
        * segment: descriptor of the segment that should be faded in
        * fadeDuration: duration of the fade-in, in seconds
        """
        d = fadeDuration
        s = segment['startTime']
        e = segment['startTime'] + d

        if e > segment['endTime']:
            e = segment['endTime']

        s2 = segment['startTime'] + d
        e2 = segment['endTime']

        if s2 > e2:
            s2 = e2

        if d > segment['endTime'] - segment['startTime']:
            d = segment['endTime'] - segment['startTime']

        return [
            # audio fade in
            SegmentFilter(
                ','.join([
                    'atrim=start=%d:end=%d' % (segment['startTime'], segment['endTime']),
                    'asetpts=PTS-STARTPTS',
                    'afade=t=in:st=0:d=%d' % (d)
                ]),
                inputAudio, '[audio0]', ftype='audio'),

            # fadein = trim + setpts + format + fade + fifo
            SegmentFilter(
                ','.join([
                    'scale=height=1080:width=-1',
                    'trim=start=%d:end=%d' % (s, e),
                    'setpts=PTS-STARTPTS',
                    'format=pix_fmts=yuva420p',
                    'fade=t=in:st=0:d=%d' % (d),
                    'fifo'
                ]),
                inputStream, '[fadeinv0]'),
            # trim the second part of the video (no fade whatsoever)
            SegmentFilter(
                ','.join([
                    'scale=height=1080:width=-1',
                    'trim=start=%d:end=%d' % (s2, e2),
                    'setpts=PTS-STARTPTS',
                    'format=pix_fmts=yuva420p'
                ]),
                inputStream, '[partv0]'),
            # concatenate the two
            SegmentFilter(
                ','.join([
                    'concat=n=2',
                    'setpts=PTS-STARTPTS'
                ]),
                '[fadeinv0][partv0]', '[v0]'),
        ]

    @staticmethod
    def crossfade(i1, i2, i1a, i2a, segment1Duration, segment2, crossfadeDuration, n):
        """
        Build the filter that trims the videos for the two segments,
        applies a fade-out effect to the end of the first - a fade-in to the beginning
        of the second, overlay the fade out and fade in, and concatenate the result
        Parameters:
        * i1: input pad to use for the first segment
        * i2: input pad to use for the second segment
        * i1a: input pad to use for the audio of the first segment
        * i2a: input pad to use for the audio of the second statement
        * segment1Duration: duration of the first segment, expected to start at ts=0
        * segment2: descriptor of the second segment (that should be faded out)
        * crossfadeDuration: duration of the crossfade
        * n: position of this crossfade (1 for first crossfade, n for nth)
        """
        d = crossfadeDuration
        sfo = segment1Duration - d
        efo = segment1Duration

        if sfo < 0:
            sfo = 0

        sfi = segment2['startTime']
        efi = segment2['startTime'] + d
        if efi > segment2['endTime']:
            efi = segment2['endTime']

        # if the fade-out and fade-in aren't the same duration, we might run into troubles
        if efo - sfo > efi - sfi:
            # the start of the fade-out will be pushed further, so that it has the same distance
            # from the end as the distance between the end and start of the fade-in
            sfo = efo - (efi - sfi)
        if efi - sfi > efo - sfo:
            # the end of the fade-in will be pushed back, so that it has the same distance
            # from the start as the distance between the end and start of the fade-out
            efi = sfi + (efo - sfo)

        return [
            # no need to rescale ever - this should be an input stream that is not a raw video input
            # # audio part of the first segment that will crossfaded
            SegmentFilter(','.join([
                'atrim=start=%d:end=%d' % (0, efo),
                'asetpts=PTS-STARTPTS'
            ]), i1a, '[crossfade%dax1]' % n, ftype='audio'),
            # alternative - fade out for a concat
            # SegmentFilter(','.join([
            #     'atrim=start=%d:end=%d' % (0, efo - d / 2),
            #     'asetpts=PTS-STARTPTS',
            #     'afade=t=out:st=%d:end=%d' % (efo - d / 2, efo)
            # ]), i1a, '[crossfade%dax1]' % n, ftype='audio'),
            # first part of the first segment will not be altered
            SegmentFilter(','.join([
                'trim=start=%d:end=%d' % (0, sfo),
                'setpts=PTS-STARTPTS'
            ]), i1, '[parto%dx1]' % n),
            # fade out = trim + setpts + format + fade + fifo
            SegmentFilter(','.join([
                'trim=start=%d:end=%d' % (sfo, efo),
                'setpts=PTS-STARTPTS',
                'format=pix_fmts=yuva420p',
                'fade=t=out:st=0:d=%d:alpha=1' % (d),
                'fifo'
            ]), i1, '[fadeouto%d]' % n),
            # fadein = trim + setpts + format + fade + fifo
            SegmentFilter(','.join([
                'scale=height=1080:width=-1',
                'trim=start=%d:end=%d' % (sfi, efi),
                'setpts=PTS-STARTPTS',
                'format=pix_fmts=yuva420p',
                'fade=t=in:st=0:d=%d:alpha=1' % (d),
                'fifo'
            ]), i2, '[fadeino%d]' % n),
            # # audio part of the second segment that will crossfaded
            SegmentFilter(','.join([
                'atrim=start=%d:end=%d' % (sfi, segment2['endTime']),
                'asetpts=PTS-STARTPTS'
            ]), i2a, '[crossfade%dax2]' % n, ftype='audio'),
            # alternative - fade in for concat
            # SegmentFilter(','.join([
            #     'atrim=start=%d:end=%d' % (sfi + d / 2, segment2['endTime']),
            #     'asetpts=PTS-STARTPTS',
            #     'fade=t=in:st=0:end=%d' % (d / 2)
            # ]), i2a, '[crossfade%dax2]' % n, ftype='audio'),
            # second part of the segment will not be altered
            SegmentFilter(','.join([
                'scale=height=1080:width=-1',
                'trim=start=%d:end=%d' % (efi, segment2['endTime']),
                'setpts=PTS-STARTPTS'
            ]), i2, '[parto%dx2]' % n),
            # overlay fadein and fadeout
            SegmentFilter(','.join([
                'overlay',
                'setpts=PTS-STARTPTS'
            ]), '[fadeouto%d][fadeino%d]' % (n, n), '[overlay%d]' % n),
            # concatenate the result
            SegmentFilter(','.join([
                'concat=n=3',
                'setpts=PTS-STARTPTS'
            ]), '[parto%dx1][overlay%d][parto%dx2]' % (n, n, n), '[v%d]' % n),
            # # audio crossfade
            SegmentFilter(', '.join([
                'acrossfade=d=%d' % (d),
                'asetpts=PTS-STARTPTS'
            ]), '[crossfade%dax1][crossfade%dax2]' % (n, n),
            '[a%d]' % (n), ftype='audio'),
            # alternative - audio concat
            # SegmentFilter(', '.join([
            #     'concat=n=2:a=1:v=0',
            #     'asetpts=PTS-STARTPTS'
            # ]), '[crossfade%dax1][crossfade%dax2]' % (n, n))

        ]

    @staticmethod
    def outroFadeOut(inputStream, inputAudio, totalDuration, fadeDuration, n):
        """
        Build the filter that trims the video for this segment,
        applies a fade-in effect to the first few seconds of the segment,
        and concatenate the result.
        Parameters:
        * inputStream: the input stream that will be faded out. Expected to start at ts=0
        * totalDuration: total duration of the input stream
        * fadeDuration: duration of the fade-out, in seconds
        * n: number of fade sections
        """
        d = fadeDuration
        s = 0
        e = totalDuration - d


        if e < s:
            e = s

        s2 = totalDuration - d
        e2 = totalDuration

        if s2 < 0:
            s2 = 0

        if d > totalDuration:
            d = totalDuration

        sa = totalDuration - d

        return [
            # audio
            SegmentFilter(
                ','.join([
                    # no need to trim audio here - we want to full audio content
                    # the output stream will have the same duration as the input stream
                    'afade=t=out:st=%d:d=%d' % (sa, d)
                ]), inputAudio, '[audio]', ftype='audio'),
            # trim the second part of the video (no fade whatsoever)
            SegmentFilter(
                ','.join([
                    'trim=start=%d:end=%d' % (s, e),
                    'setpts=PTS-STARTPTS',
                    'format=pix_fmts=yuva420p'
                ]),
                inputStream, '[partv%d]' % n),
            # fadeout = trim + setpts + format + fade + fifo
            SegmentFilter(
                ','.join([
                    'trim=start=%d:end=%d' % (s2, e2),
                    'setpts=PTS-STARTPTS',
                    'format=pix_fmts=yuva420p',
                    # start at 0, because we already reset the pts to 0 for this fragments
                    # and the whole fragment is going to be faded
                    'fade=t=out:st=0:d=%d' % (d),
                    'fifo'
                ]),
                inputStream, '[fadeoutv%d]' % n),
            # concatenate the two
            SegmentFilter(
                ','.join([
                    'concat=n=2',
                    'setpts=PTS-STARTPTS'
                ]),
                '[partv%d][fadeoutv%d]' % (n, n), '[output]')
        ]

    @staticmethod
    def lastFilter(filters, ftype):
        """ Returns the last filter of type `ftype` in the given list of filters """
        lastFilter = None
        for f in filters:
            if f.ftype == ftype:
                lastFilter = f
        if lastFilter is None:
            logging.warning("No filter of type %s in the given list of filters.", ftype)

        return lastFilter


class FFMPEGSegmentsMerger(object):
    """
    Merge the given segments into one video, applying cross-fade effect to make
    transitions between segments.
    """
    def __init__(self, segments, crossfadeDuration=10, fadeDuration=5, segmentLimit=-1,
                 progressCb=None, pp=True, **kwargs):
        """
        Initialize the merger on the given segments
        * segments: list of segments to compile to video from
        * crossfadeDuration: duration of the cross-fade transition
        * fadeDuration: Duration of the intro fade-in / outro fade-out
        * segmentLimit: for debugging purposes, set a limit to the number of segments
          that are going to be processed.
        * pp: pretty print the filter chains being built
        """
        super(FFMPEGSegmentsMerger, self).__init__()
        logging.info("Intializing FFMPEGSegmentsMerger(crossfadeDuration=%d, fadeDuration=%d, segmentLimit=%d)",
                     crossfadeDuration, fadeDuration, segmentLimit)
        self.crossfadeDuration = crossfadeDuration
        self.fadeDuration = fadeDuration
        self.limit = segmentLimit
        self.segments = segments if self.limit == -1 else segments[:self.limit]
        self.pp = pp
        self.folder = Conf['data']['ffmpeg']['compileFolder']
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

        i = 0
        self.filename = self._buildFileName(self.folder, i)
        while (os.path.exists(self.filename)):
            i += 1
            self.filename = self._buildFileName(self.folder, i)

    def _buildFileName(self, folder, i):
        return os.path.join(
           folder, 'compile.nbseg-%d-itm-%d.mp4' % (
               len(self.segments), i))

    def for2Segments(self):
        ffmpegpath = Conf['data']['ffmpeg']['exePath']
        s1 = self.segments[0]
        s2 = self.segments[1]
        d = self.crossfadeDuration
        ffmpegCmdParts = [
            '%(ffmpeg)s -i "%(v1)s" -i "%(v2)s" -an ' % dict(ffmpeg=ffmpegpath, v1=s1['videoPath'], v2=s2['videoPath']),  # disable audio for now #FIXME\
            '-filter_complex "', [
                '[0:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[v1]; ' % (s1['startTime'], s1['endTime'] - d),
                '[1:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[v2]; ' % (s2['startTime'] + d, s2['endTime']),
                '[0:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[fadeoutrawv1]; ' % (s1['endTime'] - d, s1['endTime']),
                '[1:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[fadeinrawv2]; ' % (s2['startTime'], s2['startTime'] + d),
                '[fadeoutrawv1]format=pix_fmts=yuva420p,fade=t=out:st=0:d=%d:alpha=1[fadeoutv1]; ' % (d),
                '[fadeinrawv2]format=pix_fmts=yuva420p,fade=t=in:st=0:d=%d:alpha=1[fadeinv2]; ' % (d),
                '[fadeoutv1]fifo[fadeoutv1fifo]; ',
                '[fadeinv2]fifo[fadeinv2fifo]; ',
                '[fadeoutv1fifo][fadeinv2fifo]overlay[crossfade]; ',
                '[v1][crossfade][v2]concat=n=3,format=yuv420p[output] '
            ], '" ',
            '-vcodec libx264 -map "[output]" D:\\out2.mp4'
        ]
        return ''.join([
            ''.join(cmdPart) for cmdPart in ffmpegCmdParts
        ])

    def for3Segments(self):
        ffmpegpath = Conf['data']['ffmpeg']['exePath']
        s1 = self.segments[0]
        s2 = self.segments[1]
        s3 = self.segments[2]
        d = self.crossfadeDuration
        ffmpegCmdParts = [
            '%(ffmpeg)s -i "%(v1)s" -i "%(v2)s" -i "%(v3)s" -an ' % dict(ffmpeg=ffmpegpath, v1=s1['videoPath'], v2=s2['videoPath'], v3=s3['videoPath']),  # disable audio for now #FIXME\
            '-filter_complex "', [
                # v1
                '[0:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[v1]; ' % (s1['startTime'], s1['endTime'] - d),
                '[0:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[fadeoutrawv1]; ' % (s1['endTime'] - d, s1['endTime']),
                '[fadeoutrawv1]format=pix_fmts=yuva420p,fade=t=out:st=0:d=%d:alpha=1[fadeoutv1]; ' % (d),
                '[fadeoutv1]fifo[fadeoutv1fifo]; ',

                # v2
                '[1:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[v2]; ' % (s2['startTime'] + d, s2['endTime'] - d),
                '[1:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[fadeinrawv2]; ' % (s2['startTime'], s2['startTime'] + d),
                '[fadeinrawv2]format=pix_fmts=yuva420p,fade=t=in:st=0:d=%d:alpha=1[fadeinv2]; ' % (d),
                '[fadeinv2]fifo[fadeinv2fifo]; ',

                '[1:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[fadeoutrawv2]; ' % (s2['endTime'] - d, s2['endTime']),
                '[fadeoutrawv2]format=pix_fmts=yuva420p,fade=t=out:st=0:d=%d:alpha=1[fadeoutv2]; ' % (d),
                '[fadeoutv2]fifo[fadeoutv2fifo]; ',

                # v3
                '[2:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[v3]; ' % (s3['startTime'] + d, s3['endTime']),
                '[2:v]trim=start=%d:end=%d,setpts=PTS-STARTPTS[fadeinrawv3]; ' % (s3['startTime'], s3['startTime'] + d),
                '[fadeinrawv3]format=pix_fmts=yuva420p,fade=t=in:st=0:d=%d:alpha=1[fadeinv3]; ' % (d),
                '[fadeinv3]fifo[fadeinv3fifo]; ',

                '[fadeoutv1fifo][fadeinv2fifo]overlay[crossfade1]; ',
                '[fadeoutv2fifo][fadeinv3fifo]overlay[crossfade2]; ',
                '[v1][crossfade1][v2][crossfade2][v3]concat=n=5,format=yuv420p[output] '
            ], '" ',
            '-vcodec libx264 -map "[output]" D:\\out4.mp4'
        ]
        return ''.join([
            ''.join(cmdPart) for cmdPart in ffmpegCmdParts
        ])

    def prettyprint(self, filters, comment):
        logging.info("# %s", comment)
        pp = '\n'.join(map(lambda f: f.renderPP(), filters))
        for line in pp.split('\n'):
            logging.info(line)

    def _inputLine(self, segments):
        """
        Buils the line of input, so that the same video isn't specified more than once
        Returns a mapping between video path and input pads in the form `[n:v]`
        """
        n = 0
        pathToInput = {}
        inputLine = []
        for segment in segments:
            if segment['videoPath'] not in pathToInput:
                inputLine.append('-i "%s"' % segment['videoPath'])
                pathToInput[segment['videoPath']] = {'video': '[%d:v]' % n, 'audio': '[%d:a]' % n}
                n += 1
        return ' '.join(inputLine), pathToInput

    def _assembleCommand(self, inputLine, filters, filename, compress=False):
        ffmpegpath = Conf['data']['ffmpeg']['exePath']
        lastAudioFilter = SegmentFilter.lastFilter(filters, 'audio')
        ffmpegCmdParts = [
            '%(ffmpeg)s -loglevel debug %(input)s -an ' % dict(ffmpeg=ffmpegpath, input=inputLine),
            '-filter_complex "%s" ' % ('; '.join(map(lambda f: f.render(), filters))),
            '-acodec aac -vcodec libx264 ',
            '-crf 18 ' if compress else '-crf 0 ',
            '-map "%(outputStream)s" ' % dict(
                outputStream=SegmentFilter.lastFilter(filters, 'video').outputPad),
            '-map "%(outputAudio)s" ' % dict(outputAudio=lastAudioFilter.outputPad)
            if lastAudioFilter is not None else '',
            '"%(outputFile)s"' % dict(outputFile=filename)
        ]
        return ''.join(ffmpegCmdParts)

    def _buildFilters(self, segments, pathToInput, fadeIn=True, fadeOut=True):
        """
        Build the list of filters that can be given to `ffmpegpath`
        to build a video from the given segments
        * segments: list of segments to build the video from
        * pathToInput: mapping between video path and input pad `[%d:v]`
        * fadeIn: whether to fade out the first segment. True by default.
        * fadeOut: whehter to fade out the last segment. True by default.
        """
        filters = []
        totalDuration = 0
        prevSegment = None
        for i, segment in enumerate(segments):
            tmpFilters = []
            inputVideo = pathToInput[segment['videoPath']]['video']
            inputAudio = pathToInput[segment['videoPath']]['audio']

            if fadeIn and i == 0:  # fade-in the first segment
                tmpFilters = SegmentFilter.introFadeIn(
                    inputVideo, inputAudio,
                    segment, self.fadeDuration)
                comment = 'Intro fade-in'
            elif i > 0:  # cross-fade all subsequent segments into the previous stream
                lastAudioFilter = SegmentFilter.lastFilter(filters, 'audio')
                tmpFilters = SegmentFilter.crossfade(
                    SegmentFilter.lastFilter(filters, 'video').outputPad if len(filters) > 0
                    else pathToInput[prevSegment['videoPath']]['video'],
                    inputVideo,
                    lastAudioFilter.outputPad if lastAudioFilter is not None
                    else pathToInput[prevSegment['videoPath']]['audio'],
                    inputAudio,
                    totalDuration,
                    segment,
                    self.crossfadeDuration, i)
                comment = 'Cross-fade segments #%d to #%d' % (i - 1, i)

            if self.pp and len(tmpFilters) > 0:
                self.prettyprint(tmpFilters, comment)

            filters += tmpFilters

            totalDuration += segment['endTime'] - segment['startTime']

            prevSegment = segment

        # fade-out the end of the final stream
        tmpFilters = []
        if fadeOut:
            lastAudioFilter = SegmentFilter.lastFilter(filters, 'audio')
            tmpFilters = SegmentFilter.outroFadeOut(
                SegmentFilter.lastFilter(filters, 'video').outputPad if len(filters) > 0
                else pathToInput[prevSegment['videoPath']]['video'],
                lastAudioFilter.outputPad if lastAudioFilter is not None
                else pathToInput[prevSegment['videoPath']]['audio'],
                totalDuration, self.fadeDuration, len(segments))
            if self.pp:
                self.prettyprint(tmpFilters, 'Outro fade-out')

        filters += tmpFilters

        return filters

    def _buildFFMPEGCommand(self, segments, filename, fadeIn=False, fadeOut=False, compress=False):
        inputLine, pathToInput = self._inputLine(segments)
        filters = self._buildFilters(
            segments, pathToInput, fadeIn=fadeIn, fadeOut=fadeOut)
        ffmpegCmd = self._assembleCommand(inputLine, filters, filename, compress)

        batFile = filename.replace('.mp4', '.bat')
        try:
            with open(batFile, 'w') as f:
                f.write(ffmpegCmd)
        except Exception as e:
            logging.error("Unable to write ffmpeg command in %s.", batFile)
            logging.exception(e)
        jsonfile = filename.replace('.mp4', '_segments.json')
        try:
            with open(jsonfile, 'w') as f:
                json.dump(segments, f)
        except Exception as e:
            logging.error("Unable to write segment details in %s.", jsonfile)
            logging.exception(e)

        return ffmpegCmd

    def _getTmpFileName(self, workdir, position):
        return os.path.join(
            workdir,
            os.path.basename(self.filename).replace('.mp4', '_tmp-%d.mp4' % position))

    def _executeCommand(self, ffmpegCmd, filename, segment, prevRes):
        logging.info('Executing: > %s' % ffmpegCmd)
        code = subprocess.call("%s" % ffmpegCmd, shell=True)
        logging.info("Command returned: %s" % str(code))
        if str(code) != '0':
            raise CompilerException("ffmpeg returned %s." % str(code))

        totalDuration = getDuration(filename)

        # return a 'fake' segment that will be passed down to further call to `_execMerge`
        return {
            'videoId': (
                segment['videoId'] if segment is not None else
                prevRes['videoId'] if prevRes is not None else None),
            'videoPath': filename,
            'startMinividFrame': 0,
            'endMinividFrame': 0,
            'startTime': 0,
            'endTime': totalDuration,
            'startTimeS': toHHMMSS(0),
            'endTimeS': toHHMMSS(totalDuration),
            'nbPerformers': (
                prevRes['nbPerformers'] if prevRes is not None and segment is None else
                segment['nbPerformers'] if prevRes is None and segment is not None else
                max([prevRes['nbPerformers'], segment['nbPerformers']])),
            'frameProps': (
                prevRes['frameProps'] if prevRes is not None and segment is None else
                segment['frameProps'] if segment is not None and prevRes is None else
                prevRes['frameProps'] + segment['frameProps'])
        }


    def _execMerge(self, filename, segment, position, prevRes):
        """
        Execute a ffmpeg command to merge the given segment with current on-going project.
        * workdir: directory in which temporary files can be written
        * segment: segment to merge
        * position: position of the segment in the list
        * prevRes: the result of the previous `_execMerge` operation, if there was.
                   it can be `None` for `position == 0`
        """
        if position == 0:
            segments = [segment]
        else:
            segments = [prevRes, segment]
        logging.info("Merging into temporary file: %s from %d segments." % (filename, len(segments)))

        ffmpegCmd = self._buildFFMPEGCommand(
            segments, filename, fadeIn=(position == 0))
        return self._executeCommand(ffmpegCmd, filename, segment, prevRes)

    def _execFadeOut(self, filename, prevRes):
        """
        Apply a fade-out effect to the video referenced in the `prevRes`, and write
        the output in the file referenced by `filename`
        """
        logging.info("Applying fade-out to temporary file: %s" % filename)
        ffmpegCmd = self._buildFFMPEGCommand([prevRes], filename, fadeOut=True, compress=True)
        return self._executeCommand(ffmpegCmd, filename, None, prevRes)

    def singleCommand(self):
        """
        Build one giant ffmpeg command that will do the whole job
        Seems to suffer from limitation of the size of the command line,
        and has a memory consumption issue
        """
        segments = self.segments

        ffmpegCmd = self._buildFFMPEGCommand(segments, filename, fadeIn=True, fadeOut=True)

        logging.info('Executing: > "%s"', ffmpegCmd)
        code = subprocess.call("%s" % ffmpegCmd, shell=True)
        logging.info("Command returned: %s" % str(code))

        yield {'filename': filename, 'segments': segments}

    def multiCommands(self):
        """
        Compile the video using multiple successive ffmpeg commands to avoid
        compiling more than two segments in one command.

        """
        logging.info("Compilation will happen in multiple commands.")
        try:
            workdir = os.path.join(self.folder, 'tmp')

            if os.path.exists(workdir):
                shutil.rmtree(workdir)
            time.sleep(1)
            os.makedirs(workdir)

            prevRes = None
            for i, segment in enumerate(self.segments):
                filename = self._getTmpFileName(workdir, i)
                prevRes = self._execMerge(filename, segment, i, prevRes)

                yield {'filename': filename, 'segments': self.segments[:i]}

            if prevRes is not None:
                filename = self._getTmpFileName(workdir, len(self.segments))
                prevRes = self._execFadeOut(filename, prevRes)
                yield {'filename': filename, 'segments': self.segments}
                shutil.copyfile(prevRes['videoPath'], self.filename)

            yield {'filename': filename, 'segments': self.segments}

        except Exception as e:
            logging.exception(e)
            logging.error(
                "An error occurred during the building process. Leaving tmp files intact.")


    def __call__(self):
        """
        Generates the final video from by compiling the given segments together.
        Each time a temporary file is created, yield a `{filename, segments}` object containing
            * the name of the compiled file
            * the list of segments that have been included in the compiled video.
        """
        for obj in self.multiCommands():
            yield obj

class VideoCompiler(Thread):
    """
    Object dedicated to the compilation of videos using a stochastic process.
    The idea is to extract segment from analyzed videos where segment boundaries are defined to
    be appearance or disappearance of a face in the video.
    The process is going to happen in three stages:
    * Process all videos matching defined filters that have ben analyzed,
      extract relevant segments (as described above) from there using ffmpeg
    * Select segments to assemble by creating one or several feature-space(s) of segments
      in which vector operations and distances can be computed.
      Use these feature spaces to find similar segments in respect to certain feature,
      and dissimilar in respect to other, attempting to have some kind of relationshit
      between the segments that follow each other (by face position, size, extracted tags, duration, ...)
    * Merge segments together using ffmpeg, applying effects such as cross fades, loops, acceleration and slow-downs, etc...
    During the execution, the `progress` parameter will be updated with information to report
    progression to the client.
    """
    def __init__(self, filters, options,
                 progressCb=None, async=True, force=False):
        """
        If `async` is set to True (default), the compilation tasks will be performed on a separate thread
        If `progressCb` is given, it is expected to be a callback to be called whenever the
        the analysis progresses. Each progress call will pass a dict as parameter that will hold the
        fields listed below.
        Beware that the call will happen on the child thread.
        Use e.g. tornado's IOLoop to schedule a callback on the main thread.
        Here is the structure of the progression dicts that will be sent to the client
        * `file`: the name of the current file being processed
        * `step`: the processing step currently applied to this file for display purposes
        * `duration`: time spent on the process
        * `data_type` type of data being sent - either:
            * 'init': the data will contain nothing, used to indicate the first progress call of the process
            * 'segment_candidate': a candidate segment has been nominated. It may not be selected in the final
              compiled video but it matches the criteria and defined options.
            * 'segment_select': a segment has been selected and is going to be included in the final video
            * 'segment_compiled': a segment has been compiled in the final video
            * 'result': the compilation process is finished. The data will contain a link to the compiled video.
        * `data`: actual data being sent as an object. The structure depends on the type.
        """
        super(VideoCompiler, self).__init__()
        logging.info("Initializing new %s compiler (options: %s)"
                     % ('asynchroneous' if async else '', str(options)))
        self._async = async
        self._start_t = time.time()

        self._filters = filters
        self._options = options

        self._progressCb = progressCb
        self._force = force

    def start(self):
        if self._async:
            logging.info("Starting compiler process asynchroneously")
            super(VideoCompiler, self).start()
        else:
            logging.info("Starting compiler process")
            self.run()

    def progress(self, file, step, dataType, data):
        if self._progressCb is not None:
            self._progressCb({
                'file': file,
                'step': step,
                'dataType': dataType,
                'data': data,
                'duration': time.time() - self._start_t
            })

    def generateSegmentCandidates(self):
        generator = SegmentCandidateGenerator(self._filters, **self._options)
        candidates = []
        for i, segment in enumerate(generator()):
            self.progress(
                file=os.path.basename(segment['videoPath']),
                step='Segment candidate #%d' % i,
                dataType='segment_candidate',
                data=segment)
            candidates.append(segment)
        return candidates

    def selectSegments(self, candidates):
        generator = SegmentsSelector(candidates, **self._options)
        selected = []
        for i, segment in enumerate(generator()):
            self.progress(
                file=os.path.basename(segment['videoPath']),
                step='Selected segment #%d' % i,
                dataType='segment_select',
                data=segment)
            selected.append(segment)
        return selected

    def compileSegments(self, selection):
        merger = FFMPEGSegmentsMerger(selection, **self._options)
        logging.info("Compiling final video: '%s'" % merger.filename)
        obj = None
        for i, obj in enumerate(merger()):
            self.progress(
                file=obj['filename'],
                step='Merged segment #%d' % i,
                dataType='segment_compiled',
                data=obj['segments'])
        return obj

    def run(self):
        self.progress(None, 'Initializing', 'init', {})
        candidates = self.generateSegmentCandidates()
        selection = self.selectSegments(candidates)
        result = self.compileSegments(selection)
        self.progress(None, 'Terminated successfully', 'result', result)