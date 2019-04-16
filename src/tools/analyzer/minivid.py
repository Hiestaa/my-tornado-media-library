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
from tools.utils import extends, timeFormat

DELAY = 0.5

class MinividGeneratorMonitor(Thread):
    """
    Monitors every second on a separate thread the progression
    of the generation of the minivideo
    Whenever a new frame is created, call the given `callback` given
    the basename of the last file generated and the total number of frames
    generated so far.
    """
    def __init__(self, callback, path, duration, generator, silent=False):
        super(MinividGeneratorMonitor, self).__init__()
        self._callback = callback
        self._path = path
        self._stop_event = Event()
        self._workspace = Workspace()
        self._duration = duration
        self._generator = generator
        self._lastProgressDesc = None
        self._silent = silent

    def stop(self):
        logging.info("Minivid Generation Complete. Interrupting Monitor.")
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
        if line is None:
            return self._lastProgressDesc

        search = re.search(
            'frame=\s*(?P<frame>\d*).*fps=\s*(?P<fps>\d*).*time=\s*(?P<time>\d\d:\d\d:\d\d.\d\d).*speed=\s*(?P<speed>\d*)',
            line or '')
        if search is None:
            return self._lastProgressDesc

        self._lastProgressDesc = search.groupdict()
        return self._lastProgressDesc

    def run(self):
        logging.debug("Monitor started (path=%s)", self._path)
        lastGeneratedFrame = None
        nbFrames = 0
        maxFrames = MinividGeneratorMonitor.computeExpectedNbFrames(self._duration)
        progress = None if self._silent else tqdm(total=maxFrames, desc="[t=00:00:00.00, f=0", postfix="s=?x (? fps)")
        nbFramesLastDiskUsageCheck = 0
        while not self._stopped() and nbFrames < maxFrames:
            newNbFrames = nbFrames
            time.sleep(DELAY)

            desc = self.getCurrentProgressDesc()

            if desc is not None and progress is not None:
                progress.set_description("[t=%(time)s, f=%(frame)s" % (desc))
                progress.set_postfix_str(
                    "s=%(speed)sx (%(fps)s fps)" % (desc))

            if desc is not None:
                newNbFrames = int(desc['frame'])

            if newNbFrames > nbFrames:
                nbFrames = newNbFrames
                logging.debug("Monitor notifies [nbFrames=%d, lastGeneratedFrame=%s]" % (
                    nbFrames, lastGeneratedFrame))
                self._callback(
                    nbFrames=nbFrames,
                    lastGeneratedFrame=lastGeneratedFrame)

            if progress is not None and nbFrames != progress.n:
                progress.n = nbFrames
                progress.update(0)

            if nbFrames > nbFramesLastDiskUsageCheck + 100:
                nbFramesLastDiskUsageCheck = nbFrames
                self._workspace.verifyDiskUsage()

        if progress is not None:
            progress.close()

        if self._stopped():
            logging.debug("Monitor interrupted.")


class MinividGenerator(object):
    """
    Uses FFMPEG to extract frames from the video
    """
    MINIVID_PREFIX = 'minivid'
    PROGRESS = 'progress.txt'

    def __init__(self, videoPath, snapshotsFolder, videoDuration, silent=False):
        """
        Initialize the minivid generator for the given video
        Parameters:
        * `videoPath`: path to the video from which to extract frames
        * `snapshotsFolder`: path to the folder that contains snapshots,
            a `minivid_<w>_<h>_<skip>` folder will be created in there where the frames will be saved
        * `videoDuration`: duration of the video, used to compute the expected number of extracted frames
        * `silent`: if displaying a progress bar, the process needs to be made silent, otherwise the
          outpout will mangle the progress bar display
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
        self._silent = silent
        self._progressPosition = 0

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
        for file in tqdm(os.listdir(folder), desc="[Cleaning up Minivid folder"):
            file_path = os.path.join(folder, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(e)

    def readOutput(self):
        path = os.path.join(self._minividFolder, MinividGenerator.PROGRESS)
        lines = []
        t = time.time()
        try:
            with open(path, 'r') as f:
                f.seek(self._progressPosition)
                for line in f:
                    lines.append(line)

                self._progressPosition = f.tell()
        except:
            pass

        if time.time() - t > DELAY:
            logging.warning("Reading progress output file took %s.",
                            timeFormat(time.time() - t))

        if len(lines) == 0:
            return None

        lastProgressMention = 0
        for i, l in enumerate(lines):
            if l.startswith('progress='):
                lastProgressMention = i

        relevantLines = []
        for x in range(lastProgressMention - 1, -1, -1):
            if lines[x].startswith('progress='):
                break
            relevantLines.insert(0, lines[x].replace('\n', ''))

        if len(relevantLines) == 0:
            return None

        return ', '.join(relevantLines)

    def _getCommand(self):
        progress = os.path.join(self._minividFolder, MinividGenerator.PROGRESS)
        spec = {
            'ffmpegpath': Conf['data']['ffmpeg']['exePath'],
            'videoPath': self._videoPath,
            'ssw': self._ssw,  # width
            'ssh': self._ssh,  # height
            'minividFolder': self._minividFolder,
            'verbosity': ('-hide_banner -loglevel panic -progress "%s"' % progress) if self._silent else '-hide_banner',
            'frameRate': self._frameRate,
            'prefix': self.MINIVID_PREFIX,
        }
        command = '{ffmpegpath} {verbosity} -i "{videoPath}" -f image2 -vf fps={frameRate} -s {ssw}x{ssh} "{minividFolder}\\{prefix}%04d.png"'
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

    def _makeMinividDir(self):
        if not os.path.exists(self._minividFolder):
            os.makedirs(self._minividFolder)

        with open(os.path.join(self._minividFolder, 'cleanup.bat'), 'w') as f:
            f.write('@ECHO OFF\n')
            f.write('ECHO Delete Folder: %CD%?\n')
            f.write('PAUSE\n')
            f.write('SET FOLDER=%CD%\n')
            f.write('CD /\n')
            f.write('DEL /F/Q/S "%FOLDER%" > NUL\n')
            f.write('RMDIR /Q/S "%FOLDER%"\n')
            f.write('EXIT\n')

    def __call__(self):
        """
        This will use ffmpeg to create a extract frames from the video.
        Returns the path in which the frames have been extracted
        """
        logging.info("Generating mini-video using command:")
        logging.info("> %s", self._getCommand())

        return_code = 0
        nbCreatedSnapshots = 0
        expectedNbFrames = MinividGeneratorMonitor.computeExpectedNbFrames(self._videoDuration)
        # actual generation
        try:
            self._makeMinividDir()
            nbCreatedSnapshots = len(os.listdir(self._minividFolder))
            if nbCreatedSnapshots < expectedNbFrames:
                stderr, stdout = (subprocess.STDOUT, subprocess.PIPE) if self._silent else (None, None)
                self._popen = subprocess.Popen(
                    self._getCommand(), stderr=stderr, stdout=stdout,
                    universal_newlines=True)
                if self._stopped():
                    raise Exception('Interrupted before starting!')
                return_code = self._popen.wait()
                nbCreatedSnapshots = len(os.listdir(self._minividFolder))
            else:
                logging.debug("Minivid found with all %d frames - generation not needed.",
                             nbCreatedSnapshots)
        except Exception as e:
            logging.warning("Unable to generate minivid:")
            logging.exception(e)
            with open('error.log', 'w') as f:
                f.write('Failed to generate minivid: %s' % (str(e)))
            return_code = 1

        if self._stopped():
            return self._minividFolder

        if not os.path.exists(self._minividFolder) or nbCreatedSnapshots == 0 or return_code != 0:
            raise Exception("Unable to generate minivid (nbCreatedSnapshots=%d, return_code=%d)" % (
                nbCreatedSnapshots, return_code))

        logging.info("Mini-video generation complete: %d frames." % nbCreatedSnapshots)

        return self._minividFolder
