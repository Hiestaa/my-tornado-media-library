# -*- coding: utf8 -*-

from __future__ import unicode_literals

import json
import os
import logging
import threading

from tornado.web import RequestHandler, HTTPError

from conf import Conf


class ServerActionHandler(RequestHandler):
    """
    Handle actions such as killing the server or restarting the server (if possible)
    """
    def initialize(self, onKill=None):
        self.onKill = onKill

    def kill(self):
        """
        Route: GET /api/server/kill
        Kill the server after having sent the exit page to the server.
        notification to the client.
        """
        self.render('exit.html', currentPage='admin')
        # self.finish()
        if self.onKill is not None:
            self.onKill()
        exit()  # raises "SystemExit: None?"

    def get(self, action):
        actions = {
            'kill': self.kill
        }
        if action in actions:
            actions[action]()
        raise HTTPError(404, "Not Found")