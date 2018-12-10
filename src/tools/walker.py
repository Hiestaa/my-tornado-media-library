# -*- coding: utf8 -*-

from __future__ import unicode_literals

import os
import subprocess
import time
import logging
from threading import Thread, Event
import re

import cv2
from PIL import Image

from tools.utils import extends
from server import model
from conf import Conf


FFMPEG_CMDS = {
    'generateSnapshots': '{ffmpegpath} -i "{videoPath}" -f image2 -vf fps=fps={frameRate} -s {ssw}x{ssh} "{snapFolder}\\thumb%03d.png"',
    'extractDuration': '{ffprobe} -i "{videoPath}" -show_entries format=duration -v quiet -of csv="p=0"',
    'extractFps': '{ffprobe} -i "{videoPath}" -v 0 -of csv=p=0 -select_streams 0 -show_entries stream=r_frame_rate',
    'extractDimensions': '{ffprobe} -i "{videoPath}" -v 0 -of csv=p=0 -select_streams 0 -show_entries stream=width,height'
}

class Walker(Thread):
    """
    This object is dedicated to walk through all the files
    an perform some action on them
    """
    def __init__(self, progress=None, progressCb=None, async=True):
        """
        Initialize a new walker that will recursively erun through
        the files of the data folders and perform actions on it.
        If `async` is set to True (default), the walker tasks
        will be performed on a separate thread
        The progress dict will be populated with 4 fields:
            `file`: the name of the current file being processed
            `step`: the processing step currently applied to this file
            `dones`: number of files processed
            `fileList`: list of files that have been processed. Each file is represented by an object with the fields:
                `fileName`, `success` and `error` (error message if success is false)
            `duration`: times spent on the process
            `finished`: False unless the whole walking process is finished.
            `interrupted`: False unless the walking process has been interrupted.
            `errorred`: False unless an error happened somewhere along the walking process
        The progress dict will be passed in to `progressCb` after each update.
        """
        super(Walker, self).__init__()
        logging.info("Initializing %s walker"
                     % ('new asynchroneous' if async else 'new'))
        self._progress = progress or {}
        self._progressCb = progressCb
        self._async = async
        self._start_t = time.time()
        self._tags = []
        self._stop_event = Event()

    def start(self):
        if self._async:
            logging.info("Starting walker process asynchroneously")
            super(Walker, self).start()
        else:
            logging.info("Starting walker process")
            self.run()

    def stop(self):
        self._stop_event.set()

    def resubscribe(self, progressCb):
        self._progressCb = progressCb

    def _stopped(self):
        return self._stop_event.is_set()

    def _send_progress(self):
        if self._progressCb:
            self._progressCb(self._progress)

    def run(self):
        try:
            self._run()
        except Exception as e:
            logging.error("An error occurred during the walking process")
            logging.exception(e)
            self._progress = self._progress or {}
            self._progress['errorred'] = True
            self._send_progress()

    def run(self):
        # reinit progress informations
        self._start_t = time.time()
        self._progress = extends(
            self._progress or {}, file='', step='Initializing', dones=0,
            duration=0.0, finished=False, interrupted=False, errorred=False, fileList=[])
        self._progress['fileList'] = []
        self._progress['file'] = ''
        self._progress['step'] = 'Initializing'
        self._progress['dones'] = 0
        self._progress['duration'] = 0
        self._progress['finished'] = False
        self._progress['interrupted'] = False
        self._send_progress()

        self._tags = model.getService('tag').getAutoTags()
        self.walk(
            Conf['data']['videos']['rootFolder'],
            [(self.__vid_exists, 'Checking existence'),
             (self.__generate_snapshots, 'Generating snapshots'),
             (self.__extract_vid_infos, 'Extracting informations'),
             (self.__save_vid, 'Saving video in database'),
             (self.__autotag_vid, 'Auto-tagging video'),
             # self.__generate_minivid,
             (self.__update_video_progress, 'Updating progress')],
            Conf['data']['videos']['allowedTypes']
        )
        self.walk(
            Conf['data']['albums']['rootFolder'],
            [(self.__find_album, 'Looking for related album'),
             (self.__picture_exists, 'Checking existence'),
             (self.__update_album_infos, 'Retrieving image informations'),
             (self.__save_album, 'Saving or updating album in database'),
             (self.__autotag_album, 'Auto-tagging album'),
             (self.__update_album_progress, 'Updating progress')],
            Conf['data']['albums']['allowedTypes']
        )

        self._progress['duration'] = time.time() - self._start_t
        self._progress['finished'] = True
        self._send_progress()

    def __find_album(self, imgPath, data):
        """
        Find the album related to this picture.
        Create an 'album' entry the data dict containing the
        name of this album.
        """
        album = os.path.basename(os.path.abspath(os.path.join(imgPath, os.pardir)))
        logging.debug("Album of img: %s is %s" % (os.path.basename(imgPath), album))
        return extends(data, album=album)

    def __picture_exists(self, imgPath, data):
        """
        Check if the album already holds the current image.
        Create a 'picture_exist' and an 'album_exist' entry
        in the data dict.
        Will also create the album_id entry containing the id of the
        album document if it does exist.
        """
        logging.debug("Checking existence of the image.")
        logging.debug(">> data: %s" % str(data))
        self._progress['file'] = data['album']
        found = model.getService('album').getByRealName(data['album'])
        if found is None:
            data = extends(data, album_exist=False, picture_exist=False, album_id=None)
        elif os.path.basename(imgPath) in found['pictures']:
            data = extends(data, album_exist=True, picture_exist=True, album_id=found['_id'])
        else:
            data = extends(data, album_exist=True, picture_exist=False, album_id=found['_id'])
        return data

    def __update_album_infos(self, imgPath, data):
        """
        Open the image to check the resolution, set of update the
        average resolution of the album as well as the picsNumber.
        If the picture does not exist yet, create the fields
        'picsNumber', 'averageWidth' and 'averageHeight' in the data dict.
        """
        logging.debug("Setting or Updating album infos")
        logging.debug(">> data: %s" % str(data))
        if data['album_exist'] and data['picture_exist']:
            return data

        try:
            f = Image.open(imgPath)
            w, h = f.size
        except:
            return extends(data, error="Unable to open image %s" % os.path.basename(imgPath))

        if data['album_exist']:
            found = model.getService('album').getByRealName(data['album'])
            avgW = float(found['averageWidth'])
            avgH = float(found['averageWidth'])
            nb = found['picsNumber']
            data = extends(
                data,
                averageWidth=((avgW * nb + w) / (nb + 1)),
                averageHeight=((avgH * nb + h) / (nb + 1)))
        else:
            data = extends(
                data,
                averageWidth=w,
                averageHeight=h)

        return data

    def __save_album(self, imgPath, data):
        """
        Insert or update the document matching the album of the current picture
        in the album collection.
        FIXME: do we manage subfolders ?
        """
        logging.debug("Updating albums collection.")
        logging.debug(">> data: %s" % str(data))
        if data['album_exist'] and data['picture_exist']:
            return data
        if 'error' in data and data['error']:
            return data

        if data['album_exist']:
            model.getService('album').set(
                _id=data['album_id'], field='averageWidth', value=data['averageWidth'])
            model.getService('album').set(
                _id=data['album_id'], field='averageHeight', value=data['averageHeight'])
            model.getService('album').addPicture(data['album_id'], os.path.basename(imgPath))
        else:
            _id = model.getService('album').insert(
                album=data['album'], fullPath=os.path.dirname(imgPath), pictures=[os.path.basename(imgPath)],
                averageWidth=data['averageWidth'], averageHeight=data['averageHeight'])
            data = extends(data, inserted_id=_id)

        return data

    def __autotag_album(self, imgPath, data):
        logging.debug("Auto-tagging album")
        logging.debug(">> data: %s" % str(data))
        # do only tag if the album did not exist yet
        if data['album_exist'] or not data['inserted_id']:
            return data

        tagged = [];
        for tag in self._tags:
            if re.search(tag['autotag'], imgPath, flags=re.I):
                logging.debug(
                    "ImgPath: %s matches autotag: %s for tag: %s - %s"
                    % (imgPath, tag['autotag'], tag['name'], tag['value']))
                tagged.append(tag)
                model.getService('album').addTag(data['inserted_id'], tag['_id'])
            else:
                logging.debug(
                    "ImgPath: %s does NOT match autotag: %s"
                    % (imgPath, tag['autotag']))

        if len(tagged) > 0:
            data['msg'] = 'Tagged as: ' + ', '.join(
                    map(lambda t: t['name'].title() + ' - ' + t['value'].title(), tagged))

        return extends(data, tagged=tagged)

    def __update_album_progress(self, imgPath, data):
        logging.debug("Updating progress.")
        # if the album already existed, ignore it
        if not data['album_exist']:
            self._progress['dones'] += 1
            if 'error' in data and data['error']:
                fileObj = {'fileName': data['album'], 'success': False, 'error': data['error']}
            elif 'msg' in data and data['msg']:
                fileObj = {'fileName': data['album'], 'success': True, 'error': data['msg']}
            else:
                fileObj = {'fileName': data['album'], 'success': True, 'error': None}
            if 'inserted_id' in data:
                fileObj['link'] = '/slideshow/albumId=' + data['inserted_id']
                fileObj['id'] = data['inserted_id']
                fileObj['snapshot'] = '/download/album/' + data['inserted_id'] + '/0'
            self._progress['fileList'].append(fileObj)
        return data

    def __vid_exists(self, videoPath, data):
        """
        check that the video exist, create the field
        'exist' in the data dict and set it to True or False
        """
        logging.debug("Checking existence of the video")
        logging.debug(">> data: %s" % str(data))
        videoPath = videoPath.replace('/', os.path.sep)
        videoPath = videoPath.replace('\\', os.path.sep)
        found = model.getService('video').getByPath(videoPath)
        if found is not None:
            logging.debug("Video does alread exist!")
            data = extends(data, exists=True)
        else:
            logging.debug("Video does not exist!")
            data = extends(data, exists=False)
        return data

    def __generate_snapshots(self, videoPath, data):
        """
        This will use ffmpeg to create a snapshot of the video.
        """
        # do not rerun the snapshot creation process if data already exists
        if data['exists']:
            return data
        logging.debug("Generating snapshots of video")
        logging.debug(">> Data: %s" % str(data))
        spec = {
            'ffmpegpath': Conf['data']['ffmpeg']['exePath'],
            'videoPath': videoPath,
            'ssw': Conf['data']['ffmpeg']['snapshotDimensions'][0],  # width
            'ssh': Conf['data']['ffmpeg']['snapshotDimensions'][1],  # height
            'snapFolder': '.'.join(videoPath.split('.')[:-1]),  # same except trailing extension
            'frameRate': Conf['data']['ffmpeg']['frameRate']
        }
        return_code = 0
        # actual generation
        try:
            if not os.path.exists(spec['snapFolder']):
                os.mkdir(spec['snapFolder'])
            nbCreatedSnapshots = len(os.listdir(spec['snapFolder']))
            if nbCreatedSnapshots == 0:
                command = FFMPEG_CMDS['generateSnapshots'].format(**spec)
                logging.info("> %s", command)
                return_code = subprocess.call(command, shell=True)
                nbCreatedSnapshots = len(os.listdir(spec['snapFolder']))
            else:
                data = extends(data, msg="Snapshots found, generation not needed.")
        except Exception as e:
            logging.warning("Unable to generate snapshots: %s." % repr(e).encode())
            return_code = 1

        # verifications
        if not os.path.exists(spec['snapFolder']) or nbCreatedSnapshots == 0:
            return extends(data, snapshotsError=True)

        if return_code == 0:
            snapFolder = spec['snapFolder'][len(Conf['data']['videos']['rootFolder']):]

            return extends(data, snapshotsFolder=spec['snapFolder'], snapshotsError=False)
        else:
            return extends(data, snapshotsError=True)

    def __ffmpeg_get_duration(self, videoPath):
        command = FFMPEG_CMDS['extractDuration'].format(**{
            'ffprobe': Conf['data']['ffmpeg']['probePath'],
            'videoPath': videoPath
        })
        logging.info("> %s" % command)
        res = subprocess.Popen(command, stdout=subprocess.PIPE).communicate()[0].strip()
        logging.info("[OUT]: %s" % res)
        return float(res)

    def __ffmpeg_get_fps(self, videoPath):
        command = FFMPEG_CMDS['extractFps'].format(**{
            'ffprobe': Conf['data']['ffmpeg']['probePath'],
            'videoPath': videoPath
        })
        logging.info("> %s" % command)
        res = subprocess.Popen(command, stdout=subprocess.PIPE).communicate()[0].strip()
        logging.info("[OUT]: %s" % res)
        res = res.split(b'/')
        if res == '0/0':
            return 24  # assumes 24
        return (float(res[0]) or 24) / (float(res[1]) or 1)

    def __ffmpeg_get_dimensions(self, videoPath):
        command = FFMPEG_CMDS['extractDimensions'].format(**{
            'ffprobe': Conf['data']['ffmpeg']['probePath'],
            'videoPath': videoPath
        })
        logging.info("> %s" % command)
        res = subprocess.Popen(command, stdout=subprocess.PIPE).communicate()[0].strip()
        logging.info("[OUT]: %s" % res)
        res = res.split(b',')
        if len(res) == 0 or len(res) == 1:
            return 1920, 1080
        return int(res[0]), int(res[1])

    def __extract_vid_infos(self, videoPath, data):
        def error(data, msg):
            logging.warning(msg)
            return extends(data, cvError=True, cvErrorMessage=msg)
        if data['exists'] or data['snapshotsError']:
            return data
        logging.debug("Extracting informations from video")
        logging.debug(">> Data: %s" % str(data))

        try:
            fps = self.__ffmpeg_get_fps(videoPath)
            duration = self.__ffmpeg_get_duration(videoPath)
            length = duration * fps
            w, h = self.__ffmpeg_get_dimensions(videoPath)
        except Exception as e:
            logging.exception(e)
            return error(data, "Unable to extract video details")

        if length == 0:
            return error(data, "Unable to find video duration")
        if w == 0:
            return error(data, "Unable to find video width")
        if h == 0:
            return error(data, "Unable to find video height")
        if fps == 0:
            return error(data, "Unable to find video fps")

        return extends(
            data, videoDuration=duration, videoResolution=(w, h),
            videoFPS=fps, cvError=False, fileSize=os.path.getsize(videoPath))

    def __save_vid(self, videoPath, data):
        # ignore videos that resulted in a snapshot error or that were already existing
        # also ignore if an error occured while opening the video using openCV
        # unless the insertOnCVError configuration value is set to True
        if data['exists'] or data['snapshotsError'] or (
                data['cvError'] and not Conf['data']['videos']['insertOnCVError']):
            return extends(data, inserted=False)
        logging.debug("Saving video")
        logging.debug(">> Data: %s" % str(data))
        _id = model.getService('video').insert(
            filename=videoPath.split(os.path.sep)[-1],
            path=videoPath, fileSize=data['fileSize'],
            description='', snapshotsFolder=data['snapshotsFolder'],
            display=0, seen=0, favorite=0,
            duration=data['videoDuration'], resolution=data['videoResolution'],
            fps=data['videoFPS'], tags=[],
            nbSnapshots=len([
                name for name in os.listdir(data['snapshotsFolder'])
                if os.path.isfile(os.path.join(
                    data['snapshotsFolder'], name))])
        )
        return extends(data, inserted=True, inserted_id=_id)

    def __autotag_vid(self, videoPath, data):
        logging.debug("Auto-tagging video")
        logging.debug(">> data: %s" % str(data))
        # do only tag if the album did not exist yet
        if data['exists'] or not data['inserted']:
            return data

        tagged = [];
        for tag in self._tags:
            if re.search(tag['autotag'], videoPath, flags=re.I):
                logging.debug(
                    "VideoPath: %s matches autotag: %s for tag: %s - %s"
                    % (videoPath, tag['autotag'], tag['name'], tag['value']))
                tagged.append(tag)
                model.getService('video').addTag(data['inserted_id'], tag['_id'])
            else:
                logging.debug(
                    "videoPath: %s does NOT match autotag: %s"
                    % (videoPath, tag['autotag']))

        if len(tagged) > 0:
            data['msg'] = 'Tagged as: ' + ', '.join(
                    map(lambda t: t['name'].title() + ' - ' + t['value'].title(), tagged))

        return extends(data, tagged=tagged)

    def __update_video_progress(self, videoPath, data):
        logging.debug("Updating progress.")
        # if the video already existed, ignore it
        if not data['exists']:
            self._progress['dones'] += 1
            if data['snapshotsError']:
                fileObj = {'fileName': os.path.basename(videoPath), 'success': False, 'error': 'Snapshot creation failure.'}
            elif data['cvError']:
                fileObj = {'fileName': os.path.basename(videoPath), 'success': False, 'error': 'OpenCV failure: %s' % data['cvErrorMessage']}
            elif not data['inserted']:
                fileObj = {'fileName': os.path.basename(videoPath), 'success': False, 'error': 'Unable to insert video in database.'}
            elif 'msg' in data and data['msg']:
                fileObj = {'fileName': os.path.basename(videoPath), 'success': True, 'error': data['msg']}
            else:
                fileObj = {'fileName': os.path.basename(videoPath), 'success': True, 'error': None}
            if 'inserted_id' in data:
                fileObj['link'] = '/videoplayer/videoId=' + data['inserted_id']
                fileObj['id'] = data['inserted_id']
                fileObj['snapshot'] = '/download/snapshot/' + data['inserted_id'] + '/1'
            self._progress['fileList'].append(fileObj)
        return data

    def _interrupt(self):
        """
        Called on the walker thread when the process is actually interrupting
        (as soon as possible after the stop flag is set)
        Set the interrupted progress status and log the info.
        """
        self._progress['interrupted'] = True
        self._progress['finished'] = True
        logging.info("Walker thread interrupted.")


    def walk(self, root, steps, types=None):
        """
        This will call the given steps on any file contained in the given
        folder or its subfolders, each step should be a (callback, description) tuple.
        types can be specified to call the callback only of the files with
        one of the given extensions. This is expected to be a list of strings.
        The prototype of the steps is expected to be:
        `function (videoPath, data)` where `videoPath` is the path of the
        current video, and data is the data returned by the previous callback
        for this video (or an empty dict for the first one.)
        """
        logging.info("Starting walking process from folder: %s" % root)

        if self._stopped():
            return self._interrupt()

        for dirpath, dirnames, filenames in os.walk(root):
            dirpath = dirpath.replace('\\', os.path.sep)
            dirpath = dirpath.replace('/', os.path.sep)
            for f in filenames:
                if types is None or f.split('.')[-1] in types:
                    filepath = os.path.join(dirpath, f)
                    logging.info("Processing: %s" % filepath)
                    self._progress['file'] = f
                    res = {}
                    for cb, description in steps:
                        self._progress['duration'] = time.time() - self._start_t
                        self._progress['step'] = description
                        if self._stopped():
                            return self._interrupt()
                        try:
                            self._send_progress()
                            res = cb(filepath, res)
                        except Exception as e:

                            logging.error("Error occurred during step %s", str(cb))
                            logging.error(repr(e))
                            logging.exception(e)

                            self._progress['fileList'].append({
                                'fileName': f,
                                'success': False,
                                'error': "Error while executing step %s: %s" % (str(cb), repr(e))
                            })
                            self._send_progress()
                            break
