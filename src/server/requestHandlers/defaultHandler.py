# -*- coding: utf8 -*-

from __future__ import unicode_literals

from tornado.web import RequestHandler, HTTPError

import random
import logging

from conf import Conf


class DefaultHandler(RequestHandler):
    """
    Handle every request that has no request handler.
    This could display a proper 404 Error template.
    For now, it only raises a 404 Http error.
    """
    def get(self, request):
        if request == 'login':
            raise Exception('/login route should not be hit. \
Try to login using main app login page.')
        logging.error("Unable to find item: %s" % request)
        raise HTTPError(404)
