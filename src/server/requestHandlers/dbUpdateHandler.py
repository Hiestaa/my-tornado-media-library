# -*- coding: utf8 -*-

from __future__ import unicode_literals

import json
import os
import logging
import random

from tornado.web import RequestHandler, HTTPError

from conf import Conf
from server import memory


MEMKEY = 'db-update-status'


class DbUpdateHandler(RequestHandler):
    """
    Handle the database update status requests
    THe actual update process is dealt with by the db update socket handler
    """

    def _getDbUpdateStatus(self):
        status = memory.getVal(MEMKEY)
        if status is None or len(status) == 0:
            status = {
                'file': '',
                'step': 'none',
                'dones': 0,
                'fileList': [],
                'duration': 0.0,
                'finished': True,
            }

        return status

    def get(self):
        """
        Retrieve and display the status of the update of the database
        Route: /action/db/
        """
        status = self._getDbUpdateStatus()

        self.render('dbUpdateStatus.html', status=status, currentPage='admin')

