# -*- coding: utf8 -*-

from __future__ import unicode_literals

import json
import logging

from tornado.websocket import WebSocketHandler
from tornado.ioloop import IOLoop

from server import memory
from tools.walker import Walker
from tools.utils import timeFormat, dateFormat
from server.requestHandlers.dbUpdateHandler import MEMKEY as STATUSMEMKEY

MEMKEY = 'db-updater'

class DbUpdateSocketHandler(WebSocketHandler):

    def callback(self, progress):
        # executed on the `GCVAnalyzer` thread, does nothing but scheduling a callback
        # to be executed on the main thread by the IOLoop whenever possible
        # would we be able to push data on the existing socket from the separate thread directly?
        IOLoop.instance().add_callback(lambda: self.on_progress(progress))

    def start(self, **kwargs):

        updater = memory.getVal(MEMKEY)
        if updater:
            logging.warn("An update is already running")
            updater.resubscribe(self.callback)
        else:
            updater = Walker(progressCb=self.callback, async=True)
            updater.start()
            memory.setVal(MEMKEY, updater)

    def stop(self, **kwargs):
        updater = memory.getVal(MEMKEY)
        updater.stop()
        updater.join()

    def on_progress(self, status):
        # save the progress status in memory so the db update status handler can access it when refreshing the page
        memory.setVal(STATUSMEMKEY, status)
        if status.get('finished', False) or status.get('interrupted', False) or status.get('errorred', False):
            memory.setVal(MEMKEY, None)

        dump = {}
        dump['status'] = dict(status)
        dump['status']['duration'] = timeFormat(float(status.get('duration', 0)))
        dump['status']['file']
        dump = json.dumps(dump)
        try:
            self.write_message(dump)
        except Exception as e:
            logging.exception(e)
            # the socket is probably stale, stop receiving update
            # until a new connection comes in
            updater = memory.getVal(MEMKEY)
            if updater is not None:
                updater.resubscribe(None)

    def open(self):
        updater = memory.getVal(MEMKEY)
        if updater:
            logging.info("An update is running, subscribing to status updates")
            updater.resubscribe(self.callback)

    def on_message(self, message):
        try:
            message = json.loads(message)
            {
                'start': self.start,
                'stop': self.stop
            }[message['action']](**message)
        except Exception as e:
            logging.error("Error while executig action for message %s", message)
            logging.exception(e)
            self.on_progress({"errorred": True})

    def on_close(self):
        # the socket is stale, stop receiving update
        # until a new connection comes in
        updater = memory.getVal(MEMKEY)
        if updater is not None:
            updater.resubscribe(None)
