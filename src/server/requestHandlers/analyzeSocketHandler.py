# -*- coding: utf8 -*-

from __future__ import unicode_literals

import json
import time
import logging

from tornado.websocket import WebSocketHandler
from tornado.ioloop import IOLoop

from conf import Conf
from tools.analyzer import Analyzer
from server import memory, model

MEMKEY = 'video-analyzer'

class AnalyzeSocketHandler(WebSocketHandler):
    """
    Handles connections to the `wss://*/subscribe/video/analyze
    Note: named for consistency as this file is highly specific for now.
    If ever extending the features using websockets on the video page
    (where this socket is used notably), if should be made more generic
    as we can only have a small number of simultaneous websockets on the same page.
    """
    def callback(self, videoId, result):
        # executed on the `Analyzer` thread, does nothing but scheduling a callback
        # to be executed on the main thread by the IOLoop whenever possible
        # would we be able to push data on the existing socket from the separate thread directly?
        IOLoop.instance().add_callback(lambda: self.on_analysis_progress(videoId, result))

    def start(self, videoId, force=False, **kwargs):
        """
        Action: analysis
        Parameters: videoId, force
        Begin the analyze the video by extracting every other frame and submitting
        them to google cloud vision. The process will be performed on a separate thread.
        The process is cached and won't be performed more than once, unless `force`
        is specified and set to `True`.
        """

        video = model.getService('video').getById(
            videoId, fields=['snapshotsFolder', 'path', 'analysis', 'name', 'duration'])

        existing_worker = memory.getVal(MEMKEY)
        if existing_worker is not None and existing_worker.isAlive():
            logging.warn("An analyze is still in progress for video: %s" % video['name'])
            existing_worker.resubscribe(self.callback)
            return

        logging.info("Starting analysis of video: %s", video['name'])
        analyzer = Analyzer(
            videoId, video['path'], video['snapshotsFolder'],
            progressCb=self.callback, force=force,
            annotator=Conf['data']['videos']['annotator'],
            videoDuration=video['duration'])
        analyzer.start()
        memory.setVal(MEMKEY, analyzer)

    def on_analysis_progress(self, videoId, data, skipped=False):
        if data.get('finished', False) and not skipped:
            model.getService('video').set(videoId, 'analysis', data['data'])

        try:
            self.write_message(json.dumps(data))
        except Exception as e:
            logging.exception(e)
            # the socket is probably stale, stop receiving update
            # until a new connection comes in
            analyzer = memory.getVal(MEMKEY)
            if analyzer is not None:
                analyzer.resubscribe(None)

    def stop(self, **kwargs):
        existing_worker = memory.getVal(MEMKEY)
        if existing_worker is not None:
            existing_worker.stop()
            memory.setVal(MEMKEY, None)

    def cleanup(self, videoId, **kwargs):
        existing_worker = memory.getVal(MEMKEY)
        video = model.getService('video').getById(
            videoId, fields=['snapshotsFolder'])

        if existing_worker is not None:
            existing_worker.stop()
            time.sleep(1)

        Analyzer.cleanup(video['snapshotsFolder'])

    def open(self):
        analyzer = memory.getVal(MEMKEY)
        if analyzer and not analyzer.isComplete():
            logging.info('An analysis is already running, subscribing to status updates')
            analyzer.resubscribe(self.callback)

    def on_message(self, message):
        try:
            message = json.loads(message)
            {
                'start': self.start,
                'stop': self.stop,
                'clean-up': self.cleanup
            }[message['action']](**message)
        except Exception as e:
            logging.error("Error while executing action for message %s", message)
            logging.exception(e)
            self.on_analysis_progress(None, {'error': repr(e)})

    def on_close(self):
        pass
