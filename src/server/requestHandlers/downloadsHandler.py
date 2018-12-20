# -*- coding: utf8 -*-

from __future__ import unicode_literals

import os
import re
import random
import json
import time
from threading import Thread
import io
import logging
import subprocess

from tornado.web import RequestHandler, HTTPError, asynchronous
from server import model, memory
from tools.utils import sizeFormat
from tools.analyzer import MinividGenerator
from tools.workspace import Workspace
from conf import Conf


class DownloadsHandler(RequestHandler):
    """Handle requests related to the videos, snapshots, etc.."""
    def initialize(self, resType):
        """
        Initialize a download handler
        resType is the type of resource that should be server
        by this handler
        Accepted values are 'video' and 'snapshot'
        """
        self._resType = resType
        self._downloadFunctions = {
            'video': self.downloadVideo,
            'snapshot': self.downloadSnapshot,
            'album': self.downloadAlbum,
            'minivid': self.downloadMinivid
        }
        self.picMimeType = {
            'png': 'image/png',
            'gif': 'image/gif',
            'jpg': 'image/jpg',
            'jpeg': 'image/jpg'
        }
        self.videoMimeType = {
            'avi': 'video/avi',
            'divx': 'video/avi',
            'mpg': 'video/mpeg',
            'mpeg': 'video/mpeg',
            'mpg': 'video/mpeg',
            'mpeg': 'video/mpeg',
            'mp1': 'video/mpeg',
            'mp2': 'video/mpeg',
            'mp3': 'video/mpeg',
            'm1v': 'video/mpeg',
            'm1a': 'video/mpeg',
            'm2a': 'video/mpeg',
            'mpa': 'video/mpeg',
            'mpv': 'video/mpeg',
            'mp4': 'video/mp4',
            'm4a': 'video/mp4',
            'm4p': 'video/mp4',
            'm4b': 'video/mp4',
            'm4r': 'video/mp4',
            'm4v': 'video/mp4',
            'ogg': 'video/ogg',
            'ogv': 'video/ogg',
            'oga': 'video/ogg',
            'ogx': 'video/ogg',
            'ogm': 'video/ogg',
            'spx': 'video/ogg',
            'opus': 'video/ogg',
            '3gp': 'video/quicktime',
            'mov': 'video/quicktime',
            'webm': 'video/webm',
            'mkv': 'video/x-matroska',
            'mk3d': 'video/x-matroska',
            'mka': 'video/x-matroska',
            'mks': 'video/x-matroska',
            'wmv': 'video/x-ms-wmv',
            'flv': 'video/x-flv',
            'f4v': 'video/x-flv',
            'f4p': 'video/x-flv',
            'f4a': 'video/x-flv',
            'f4b': 'video/x-flv'
        }

        self._workspace = Workspace()

    def downloadAlbum(self, albumId, picNum):
        """
        Writes back to the client the picture number `picNum` of the album given by id.
        """
        picNumber = int(picNum)
        album = model.getService('album').getById(albumId)
        album['fullPath'] = '%s%s' % (
            Conf['data']['albums']['rootFolder'],
            album['fullPath'])
        if picNumber > len(album['pictures']):
            logging.error("Album has only %d pictures!" % len(album['pictures']))
            raise HTTPError(404, "Not Found")

        if albumId == 'random' or albumId == 'starred':
            if picNumber > 0:
                # the first picture is the icon, full exact path does not need to be reconstructed
                picPath = Conf['data']['albums']['rootFolder'] + album['pictures'][picNumber]  # path already included
            else:
                picPath = album['pictures'][picNumber]
        else:
            picPath = album['fullPath'] + album['pictures'][picNumber]

        try:
            with open(picPath, 'rb') as p:
                buf = p.read()
        except:
            logging.error("The picture: %s cannot be found." % picPath)
            raise HTTPError(404, 'Not Found')

        self.set_header('Content-Type', self.picMimeType[picPath.split('.')[-1].lower()])
        self.set_header('Content-Length', len(buf))
        self.write(buf)
        self.finish()

    def downloadSnapshot(self, videoId, ssNumber):
        """
        Write back to the client the snapshot number `ssnumber`
        of the video given by id
        """
        logging.debug("Downloading snapshot #%s on video %s" % (ssNumber, videoId))
        ssNumber = int(ssNumber) + 1  # base 1
        video = model.getService('video').getById(videoId)
        if video is None:
            raise HTTPError(404, 'Video Not Found: ' + videoId)
        video['snapshotsFolder'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['snapshotsFolder'])
        ssFolder = video['snapshotsFolder']
        # ensuretrailing slash
        if ssFolder[-1] != os.sep:
            ssFolder = ssFolder + os.sep
        # compute snapshot path
        if ssNumber < 10:
            snapshotPath = ssFolder + 'thumb00%d.png' % ssNumber
        elif ssNumber < 100:
            snapshotPath = ssFolder + 'thumb0%d.png' % ssNumber
        else:
            snapshotPath = ssFolder + 'thumb%d.png' % ssNumber

        try:
            with open(snapshotPath, 'rb') as p:
                buf = p.read()
        except:
            logging.error("The picture: %s cannot be found." % snapshotPath)
            raise HTTPError(404, 'Not Found')

        self.set_header('Content-Type', self.picMimeType['png'])
        self.set_header('Content-Length', len(buf))
        self.set_header('Cache-Control', 'no-cache, must-revalidate')
        self.write(buf)
        self.finish()

    def downloadMinivid(self, videoId, frameNumber):
        """
        Write back to the client the snapshot number `ssnumber`
        of the video given by id
        """
        logging.debug("Downloading minivid frame #%s on video %s" % (frameNumber, videoId))
        frameNumber = int(frameNumber) + 1  # base 1
        video = model.getService('video').getById(videoId)
        video['snapshotsFolder'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['snapshotsFolder'])
        ssFolder = MinividGenerator.buildMinividFolderPath(self._workspace, video['snapshotsFolder'])
        # ensure trailing slash
        if ssFolder[-1] != os.sep:
            ssFolder = ssFolder + os.sep
        # compute snapshot path
        if frameNumber < 10:
            snapshotPath = ssFolder + 'minivid000%d.png' % frameNumber
        elif frameNumber < 100:
            snapshotPath = ssFolder + 'minivid00%d.png' % frameNumber
        elif frameNumber < 1000:
            snapshotPath = ssFolder + 'minivid0%d.png' % frameNumber
        else:
            snapshotPath = ssFolder + 'minivid%d.png' % frameNumber

        try:
            with open(snapshotPath, 'rb') as p:
                buf = p.read()
        except:
            logging.error("The picture: %s cannot be found." % snapshotPath)
            raise HTTPError(404, 'Not Found')

        self.set_header('Content-Type', self.picMimeType['png'])
        self.set_header('Content-Length', len(buf))
        self.set_header('Cache-Control', 'no-cache, must-revalidate')
        self.write(buf)
        self.finish()

    def downloadVideo(self, videoId):
        logging.info("Will download video with id=%s" % videoId)
        # todo, add a better way to do this, in its dedicated function
        def asyncDownload(videoPath):
            videoPath = videoPath.replace('/', '\\')
            logging.info("Starting download of: %s" % videoPath)
            videoName = os.path.basename(videoPath)
            buf_size = 1024 * 1024
            self.set_header('Content-Type', self.videoMimeType[videoName.split('.')[-1].lower()])
            self.set_header('Content-Disposition', 'attachment; filename=' + videoName)
            self.set_header('Content-Length', os.path.getsize(videoPath))
            self.set_header('Expires', 0)
            self.set_header('Accept-Ranges', 'bytes')
            i = 0
            total_len = 0
            with open(videoPath, 'rb') as f:
                while True:
                    i += 1
                    data = f.read(buf_size)
                    if len(data) < buf_size:
                        logging.error("Read %s instead of %s" % (sizeFormat(len(data)), sizeFormat(buf_size)))
                    total_len += len(data)
                    logging.debug("Chunk: %d [%s]" % (i, sizeFormat(total_len)))
                    if not data:
                        data = f.read(buf_size)
                        if not data:
                            break
                    self.write(data)
                    self.flush()
            logging.debug("Total size should be %s" % (sizeFormat(total_len)))
            logging.debug("Size is expected to be: %s" % (sizeFormat(os.path.getsize(videoPath))))
            self.finish()
        # get the path for this video.
        video = model.getService('video').getById(videoId, ['path', 'name'])
        video['path'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['path'])
        # check that the file exist
        try:
            with open(video['path'], 'r') as f:
                logging.info("The video %s does exist!" % video['path']);
        except IOError:
            logging.error("The video: %s cannot be found." % video['path'])
            raise HTTPError(404, 'Not Found')
        # increment 'seen' counter
        model.getService('video').increment(videoId, 'seen')
        # perform asynchronous download
        Thread(target=asyncDownload, name="Downloader-%s" % video['name'], args=[video['path']]).start()

    @asynchronous
    def get(self, *resId):
        """
        Download a resource, route: /download/<resType>/<resId>
        This function is asynchronous to avoid that the request handler call
        the finish function while another thread is serving the download.
        """
        self._downloadFunctions[self._resType](*resId)

