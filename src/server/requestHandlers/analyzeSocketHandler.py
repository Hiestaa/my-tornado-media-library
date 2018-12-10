# -*- coding: utf8 -*-

from __future__ import unicode_literals

import json
import logging

from tornado.websocket import WebSocketHandler
from tornado.ioloop import IOLoop

from tools.analyzer import GCVAnalyzer
from server import memory, model

class AnalyzeSocketHandler(WebSocketHandler):
    """
    Handles connections to the `wss://*/subscribe/video/analyze
    Note: named for consistency as this file is highly specific for now.
    If ever extending the features using websockets on the video page
    (where this socket is used notably), if should be made more generic
    as we can only have a small number of simulateous websockets on the same page.
    """

    def gcv(self, videoId, force=False, **kwargs):
        """
        Action: gcv
        Parameters: videoId, force
        Begin the analyze the video by extracting every other frame and submitting
        them to google cloud vision. The process will be performed on a separate thread.
        The process is cached and won't be performed more than once, unless `force`
        is specified and set to `True`.
        """
        def callback(videoId, result):
            # executed on the `GCVAnalyzer` thread, does nothing but scheduling a callback
            # to be executed on the main thread by the IOLoop whenever possible
            # would we be able to push data on the existing socket from the separate thread directly?
            IOLoop.instance().add_callback(lambda: self.on_gcv_progress(videoId, result))

        video = model.getService('video').getById(
            videoId, fields=['snapshotsFolder', 'path', 'analysis', 'name'])

        existing_worker = memory.getVal('video-analyzer-gcv')
        if existing_worker is not None and existing_worker.isAlive():
            raise Exception("An analyze is still in progress for video: %s" % video['name'])

        logging.info("Starting analysis of video: %s", video['name'])
        analyzer = GCVAnalyzer(
            videoId, video['path'], video['snapshotsFolder'],
            progressCb=callback, force=force)
        analyzer.start()
        memory.setVal('video-analyzer-gcv', analyzer)

    def on_gcv_progress(self, videoId, data, skipped=False):
        if data.get('finished', False) and not skipped:
            model.getService('video').set(videoId, 'analysis', data['data'])

        self.write_message(json.dumps(data))

    def open(self):
        pass

    def on_message(self, message):
        try:
            message = json.loads(message)
            {
                'gcv': self.gcv
            }[message['action']](**message)
        except Exception as e:
            logging.error("Error while executig action for message %s", message)
            logging.exception(e)
            self.on_gcv_progress(None, {'error': repr(e)})

    def on_close(self):
        pass
