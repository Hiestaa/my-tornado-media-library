# -*- coding: utf8 -*-

from __future__ import unicode_literals

import logging
from threading import Thread, Event
import time
import os
import subprocess
from tqdm import tqdm
import re
import signal
import shutil

from conf import Conf
from tools.workspace import Workspace
from tools.utils import extends


class MinividGeneratorMonitor(Thread):
    """
    Monitors every second on a separate thread the progression
    of the generation of the minivideo
    Whenever a new frame is created, call the given `callback` given
    the basename of the last file generated and the total number of frames
    generated so far.
    """
    def __init__(self, callback, path, duration, generator):
        super(MinividGeneratorMonitor, self).__init__()
        self._callback = callback
        self._path = path
        self._stop_event = Event()
        self._workspace = Workspace()
        self._duration = duration
        self._generator = generator
        self._lastProgressDesc = None

    def stop(self):
        self._stop_event.set()

    def _stopped(self):
        return self._stop_event.is_set()

    @staticmethod
    def getMinividFileList(minividFolder):
        try:
            return [
                file for file in os.listdir(minividFolder)
                if file.endswith('.png') and file.startswith(MinividGenerator.MINIVID_PREFIX)
            ]
        except FileNotFoundError:
            return []

    @staticmethod
    def computeExpectedNbFrames(duration):
        framerate = Conf['data']['ffmpeg']['minividFrameRate']
        nb, unit = map(int, framerate.split('/'))
        return duration * nb / unit

    def getCurrentProgressDesc(self):
        """
        Retuns the current progress descriptor
        This will block the thread until data is read from the generator output.
        This will return None until something relevant is decoded from the output, then
        it will always return either:
        * updated progress descriptor
        * last valid progress descriptor
        """
        line = self._generator.readOutput()
        search = re.search(
            'frame=\s*(?P<frame>\d*).*fps=\s*(?P<fps>\d*).*time=\s*(?P<time>\d\d:\d\d:\d\d.\d\d).*speed=\s*(?P<speed>\d*)',
            line or '')
        if search is None:
            return self._lastProgressDesc

        self._lastProgressDesc = search.groupdict()
        return self._lastProgressDesc

    def run(self):
        logging.info("Monitor started (path=%s)", self._path)
        lastGeneratedFrame = None
        nbFrames = 0
        maxFrames = MinividGeneratorMonitor.computeExpectedNbFrames(self._duration)
        progress = tqdm(total=maxFrames, desc="[t=00:00:00.00, f=0", postfix="s=?x (? fps)")
        nbFramesLastDiskUsageCheck = 0
        while not self._stopped() and nbFrames < maxFrames:
            time.sleep(0.01)
            minividFrames = MinividGeneratorMonitor.getMinividFileList(self._path)
            if len(minividFrames) == nbFrames:
                continue

            nbFrames = len(minividFrames)
            lastGeneratedFrame = sorted(minividFrames)[-1]

            logging.debug("Monitor notifies [nbFrames=%d, lastGeneratedFrame=%s]" % (
                nbFrames, lastGeneratedFrame))
            self._callback(
                nbFrames=nbFrames,
                lastGeneratedFrame=lastGeneratedFrame)

            # note: this is blocking
            progress.n = nbFrames
            progress.update(0)
            desc = self.getCurrentProgressDesc()
            if desc is not None:
                progress.set_description("[t=%(time)s, f=%(frame)s" % (desc))
                progress.set_postfix_str(
                    "s=%(speed)sx (%(fps)s fps)" % (desc))

            if nbFrames > nbFramesLastDiskUsageCheck + 100:
                nbFramesLastDiskUsageCheck = nbFrames
                self._workspace.verifyDiskUsage()

        progress.close()

        if self._stopped():
            logging.info("Monitor interrupted.")


class MinividGenerator(object):
    """
    Uses FFMPEG to extract frames from the video
    """
    MINIVID_PREFIX = 'minivid'

    def __init__(self, videoPath, snapshotsFolder, videoDuration):
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
        self._workspace = Workspace()
        self._minividFolder = MinividGenerator.buildMinividFolderPath(self._workspace, self._snapshotsFolder)
        self._popen = None
        self._stop_event = Event()
        self._videoDuration = videoDuration

        logging.info("> %s", self._getCommand())

    @staticmethod
    def buildMinividFolderPath(workspace, snapshotsFolder):
        _ssw = Conf['data']['ffmpeg']['minividDimension'][0]
        _ssh = Conf['data']['ffmpeg']['minividDimension'][1]
        _frameRate = Conf['data']['ffmpeg']['minividFrameRate']

        snapshotsFolderName = os.path.basename(snapshotsFolder)
        if len(snapshotsFolderName) == 0:
            snapshotsFolderName = os.path.basename(snapshotsFolder[:-1])

        return workspace.getPath(
            'minivids',
            snapshotsFolderName,
            'minivid_%dx%d_%s' % (_ssw, _ssh, _frameRate.replace('/', '-')))

    @staticmethod
    def getMinividFPS(minvidFolder):
        rep = minvidFolder.split('_')[-1]
        rep = rep.split('-')
        return float(rep[0]) / float(rep[1])

    @staticmethod
    def cleanup(folder):
        nb = 0
        try:
            nb = len(os.listdir(folder))
        except FileNotFoundError:
            return  # nothing to clean up

        logging.info("Cleaning up %d analysis temporary files.", nb)
        for file in os.listdir(folder):
            file_path = os.path.join(folder, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(e)

    def readOutput(self):
        if self._popen is None:
            return None
        chunk = self._popen.stdout.readline()
        return chunk

    def _getCommand(self):
        spec = {
            'ffmpegpath': Conf['data']['ffmpeg']['exePath'],
            'videoPath': self._videoPath,
            'ssw': self._ssw,  # width
            'ssh': self._ssh,  # height
            'minividFolder': self._minividFolder,
            'frameRate': self._frameRate,
            'prefix': self.MINIVID_PREFIX,
        }
        command = '{ffmpegpath} -i "{videoPath}" -f image2 -vf fps={frameRate} -s {ssw}x{ssh} "{minividFolder}\\{prefix}%04d.png"'
        command = command.format(**spec)
        return command

    # may be called from a different thread
    def stop(self):
        self._stop_event.set()
        if self._popen is not None:
            # try :allthethings:!
            try:
                self._popen.terminate()
                os.killpg(os.getpgid(self._popen.pid), signal.SIGTERM)
            except:
                pass

    def _stopped(self):
        return self._stop_event.is_set()

    def __call__(self):
        """
        This will use ffmpeg to create a extract frames from the video.
        Returns the path in which the frames have been extracted
        """
        logging.info("Generating mini-video")

        return_code = 0
        nbCreatedSnapshots = 0
        expectedNbFrames = MinividGeneratorMonitor.computeExpectedNbFrames(self._videoDuration)
        # actual generation
        try:
            if not os.path.exists(self._minividFolder):
                os.makedirs(self._minividFolder)
            nbCreatedSnapshots = len(os.listdir(self._minividFolder))
            if nbCreatedSnapshots < expectedNbFrames:
                self._popen = subprocess.Popen(
                    self._getCommand(), stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                    universal_newlines=True)
                if self._stopped():
                    raise Exception('Interrupted before starting!')
                return_code = self._popen.wait()
                nbCreatedSnapshots = len(os.listdir(self._minividFolder))
            else:
                logging.info("Minivid found with all %d frames - generation not needed.",
                             nbCreatedSnapshots)
        except Exception as e:
            logging.warning("Unable to generate minivid:")
            logging.exception(e)
            return_code = 1

        if self._stopped():
            return self._minividFolder

        if not os.path.exists(self._minividFolder) or nbCreatedSnapshots == 0 or return_code != 0:
            raise Exception("Unable to generaete minivid (nbCreatedSnapshots=%d, return_code=%d)" % (
                nbCreatedSnapshots, return_code))
        return self._minividFolder
