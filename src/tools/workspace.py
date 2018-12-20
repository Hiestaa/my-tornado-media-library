# -*- coding: utf8 -*-

from __future__ import unicode_literals

import logging
import os

from conf import Conf
from tools import utils


class Workspace(object):
    def __init__(self):
        self._directory = Conf['data']['workspace']['path']
        try:
            os.stat(self._directory)
        except:
            os.makedirs(self._directory)

    def verifyDiskUsage(self):
        size = utils.getFolderSize(self._directory)
        warn = Conf['data']['workspace']['usageWarning'] * 1000 * 1000 * 1000
        limit = Conf['data']['workspace']['usageLimit'] * 1000 * 1000 * 1000
        if size > warn:
            logging.warn(
                "Workspace data usage warning: %.3f%% - %s used of %s allowed.",
                size * 100 / limit, utils.sizeFormat(size), utils.sizeFormat(limit))
        if size > limit:
            raise Exception(
                "Workspace data usage limit exceeded: %.3f%% - %s used of %s allowed.",
                size * 100 / limit, utils.sizeFormat(size), utils.sizeFormat(limit))

    def getPath(self, *kwargs):
        return os.path.join(self._directory, *kwargs)
