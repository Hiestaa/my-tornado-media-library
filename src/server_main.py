#!.env/bin/python
# -*- coding: utf8 -*-

from __future__ import unicode_literals

import time
import json
import argparse
import logging
from threading import Thread

import tornado
from tornado.web import Application
from tornado.ioloop import IOLoop

from conf import Conf
from config.termColors import cPrint, ICyan
import log
from server.model import Model
from server.requestHandlers.assetsHandler import AssetsHandler, minifiedCleanUp
from server.requestHandlers.templatesHandler import TemplatesHandler
from server.requestHandlers.defaultHandler import DefaultHandler
from server.requestHandlers.vidsHandler import VidsHandler
from server.requestHandlers.albumsHandler import AlbumsHandler
from server.requestHandlers.tagsHandler import TagsHandler
from server.requestHandlers.downloadsHandler import DownloadsHandler
from server.requestHandlers.dbUpdateHandler import DbUpdateHandler
from server.requestHandlers.notificationHandler import NotificationHandler
from server.requestHandlers.serverActionHandler import ServerActionHandler
from server.requestHandlers.homeHandler import HomeHandler
from server.requestHandlers.analyzeSocketHandler import AnalyzeSocketHandler
from server.requestHandlers.dbUpdateSocketHandler import DbUpdateSocketHandler
from server.requestHandlers.compileSocketHandler import CompileSocketHandler

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the server for the web-ui report",
        prog="server.py")
    parser.add_argument('--verbose', '-v', action="count",
                        help="Set console logging verbosity level. Default \
displays only ERROR messages, -v enable WARNING messages, -vv enable INFO \
messages and -vvv enable DEBUG messages. Ignored if started using daemon.",
                        default=0)
    parser.add_argument('-q', '--quiet', action="store_true",
                        help="Remove ALL logging messages from the console.")
    return parser.parse_args()

def disable_downloader_logs(handler):
    if handler.__class__.__name__ in ['DownloadsHandler', 'AssetsHandler']:
        return

    if handler.get_status() < 400:
        log_method = logging.info
    elif handler.get_status() < 500:
        log_method = logging.warning
    else:
        log_method = logging.error
    request_time = 1000.0 * handler.request.request_time()
    log_method(
        "%d %s %.2fms",
        handler.get_status(),
        handler._request_summary(),
        request_time,
    )

class Server(Thread):
    """
    Create the server.
    """
    def __init__(self, ns, onReady=None, onKill=None):
        """
        Create the server. Call the 'run' function to start the server
        synchroneously, call the 'start' function to start the server
        on its own thread.
        * ns: configuration of the server (see: parse_args function)
        * onReady: callback to be called when the server is ready.
          WARNING: will be called on the server's thread just BEFORE starting
          event loop! The function should NOT be blocking or the server will
          never listen for requests!
        * onKill: callback to be called when the client ask for killing the server.
          This function will be called on the server's thread but can still perform
          some cleaning task or destroy a the HMI's window
        """
        super(Server, self).__init__()
        self._ns = ns
        self._onReady = onReady
        self._onKill = onKill

    def stop(self):
        ioloop = tornado.ioloop.IOLoop.instance()
        ioloop.add_callback(lambda x: x.stop(), ioloop)
        logging.info("Requested tornado server to stop.")

    def log(self, handler):
        import ipdb; ipdb.set_trace()
        request_time = 1000.0 * handler.request.request_time()
        logging.info(
            "%d %s %.2fms",
            handler.get_status(),
            handler._request_summary(),
            request_time,
        )

    """
    Run the server. This function will be called when the server's daemon
    start, but can also be called on the current process if server is not
    started as a daemon.
    """
    def run(self):
        # initialize log
        log.init(self._ns.verbose, self._ns.quiet, filename="server.log", colored=False)

        # create model, that hold services for database collection
        # and memory, a wrapper object over the manipulation of the shared
        # persistent memory between queries
        model = Model()

        # define server settings and server routes
        server_settings = {
            "cookie_secret": "101010",  # todo: generate a more secure token
            "template_path": Conf['server']['templatePath'],
            # allow to recompile templates on each request, enable autoreload
            # and some other useful features on debug. See:
            # http://www.tornadoweb.org/en/stable/guide/running.html#debug-mode
            # http://www.tornadoweb.org/en/stable/guide/running.html#debug-mode
            "debug": Conf['state'] == 'DEBUG',
            "log_function": disable_downloader_logs
        }
        server_routes = [
            (r"/action/db/update/?", DbUpdateHandler),
            (r"/action/db/display/?", DbUpdateHandler),
            (r"/action/server/([a-zA-Z0-9_.-]+)/?", ServerActionHandler,
                dict(onKill=self._onKill)),
            (r"/api/video/([a-zA-Z0-9_./-]+)/?", VidsHandler),
            (r"/api/album/([a-zA-Z0-9_.-]+)/?", AlbumsHandler),
            (r"/api/tag/([a-zA-Z0-9_.-]+)/?", TagsHandler),
            (r"/api/notify/([a-zA-Z0-9_.-]+)/?", NotificationHandler),
            (r"/api/home/([a-zA-Z0-9_.-]+)/?", HomeHandler),
            (r"/subscribe/db/update/?", DbUpdateSocketHandler),
            (r"/subscribe/video/analyze/?", AnalyzeSocketHandler),
            (r"/subscribe/video/compile/?", CompileSocketHandler),
            (r'/download/video/([a-zA-Z0-9]+)/?', DownloadsHandler, dict(resType='video')),
            (r'/download/snapshot/(.+)/(.+)/?', DownloadsHandler, dict(resType='snapshot')),
            (r'/download/minivid/(.+)/(.+)/?', DownloadsHandler, dict(resType='minivid')),
            (r'/download/album/(.+)/(.+)/?', DownloadsHandler, dict(resType='album')),
            (r"/assets/([a-zA-Z0-9_\/\.-]+)/?", AssetsHandler),
            (r"/([a-zA-Z0-9_/\.=-]*)/?", TemplatesHandler),
            (r"/(.+)/?", DefaultHandler)
        ]

        # start the server.
        logging.info("Server Starts - %s state - %s:%s"
                     % (Conf['state'], 'localhost', Conf['server']['port']))
        logging.debug("Debugging message enabled.")
        application = Application(server_routes, **server_settings)
        application.listen(Conf['server']['port'])
        logging.info("Connected to database: %s" % Conf['data']['mongoDB']['dbName'])

        # cleanup minified assets
        minifiedCleanUp()

        if self._onReady is not None:
            self._onReady()
        # start listening
        try:
            tornado.ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            logging.info("Stopping server...")

        model.disconnect()

if __name__ == '__main__':
    Server(parse_args()).run()
