# -*- coding: utf8 -*-

from __future__ import unicode_literals

import json
import logging

from tornado.websocket import WebSocketHandler
from tornado.ioloop import IOLoop

from tools.compiler import VideoCompiler
from server import memory

class CompileSocketHandler(WebSocketHandler):
    """
    Handles connections to the `wss://*/subscribe/video/analyze
    Note: named for consistency as this file is highly specific for now.
    If ever extending the features using websockets on the video page
    (where this socket is used notably), if should be made more generic
    as we can only have a small number of simulateous websockets on the same page.
    """

    def start(self, filters, options, **kwargs):
        """
        Action: start
        Parameters: filters, options
        Start the video compilation process
        """
        def callback(result):
            # executed on the `VideoCompiler` thread, does nothing but scheduling a callback
            # to be executed on the main thread by the IOLoop whenever possible
            # would we be able to push data on the existing socket from the separate thread directly?
            IOLoop.instance().add_callback(lambda: self.on_progress(result))

        existing_worker = memory.getVal('video-compiler')
        if existing_worker is not None and existing_worker.isAlive():
            raise Exception("A compilation is still in progress.")

        logging.info("Starting analysis of videos compilation process")
        compiler = VideoCompiler(
            filters, options,
            progressCb=callback)
        compiler.start()
        memory.setVal('video-compiler', compiler)

    def on_progress(self, data):
        self.write_message(json.dumps(data))

    def open(self):
        pass

    def on_message(self, message):
        try:
            message = json.loads(message)
            {
                'start': self.start
            }[message['action']](**message)
        except Exception as e:
            logging.error("Error while executig action %s", message.get('action', '???'))
            logging.exception(e)
            self.on_progress({'error': repr(e)})

    def on_close(self):
        pass
