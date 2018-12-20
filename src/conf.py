# -*- coding: utf8 -*-

from __future__ import unicode_literals

import logging
import os


Conf = {
    'state': 'DEBUG',
    'log': {
        'fileLevel': logging.WARNING
    },
    'data': {
        'mongoDB': {
            # allow to force starting mongoDB server if an instance is not listening on the
            # defined host:por.
            # See: `rootFolder` and `dataFolder` for configuration of the mongoDB server.
            'forceStart': True,
            # number of connection retries when forcing mongoDB server start up.
            'maxRetries': 10,
            'host': 'localhost',
            'port': 27017,
            # note: this will only be used if forceStart is True and
            # if a mongoDB server is NOT already listening on the
            # defined host and port
            'rootFolder': "%s\\_internal\\bin\\MongoDB\\bin\\" % os.getcwd(),  # trailing '\' is required
            'dataFolder': "%s\\data\\db" % os.getcwd(), #"%s\\data\\db\\" % os.getcwd(),
            'dbName': 'vice',
            'dumpFolder': "%s\\dumps\\" % os.getcwd(),
            'dumpDelay': 60 * 60 * 24  # a day
        },
        'ffmpeg': {
            'exePath': '%s\\_internal\\bin\\ffmpeg\\ffmpeg.exe' % os.getcwd(),
            'snapshotDimensions': (1280, 720),
            # per recommendation on https://cloud.google.com/vision/docs/supported-files
            'minividDimension': (800, 450),
            'minividFrameRate': '24/1',
            'minividPostProcContext': 10,
            'frameRate': '1/30',
            'probePath': '%s\\_internal\\bin\\ffmpeg\\ffprobe.exe' % os.getcwd(),
            'compileFolder': '%s\\workspace\\compilations' % os.getcwd()
        },
        'videos': {
            'insertOnCVError': False,
            'rootFolder': '%s\\data\\videos\\' % os.getcwd(),
            'allowedTypes': ['avi', 'mkv', 'flv', 'mpg', 'mp4', 'wmv', 'mov', 'm4v', 'm4a', '3gp'],
            'displayPerPage': 9,
        },
        'albums': {
            'rootFolder': '%s\\data\\photos\\' % os.getcwd(),
            'allowedTypes': ['png', 'jpg', 'jpeg']
        },
        # where temporary files are gonna be stored - to facilitate mass clean up
        'workspace': {
            'path': '%s\\workspace\\' % os.getcwd(),
            'usageWarning': 800,  # in GB
            'usageLimit': 1000   # in GB
        }
    },
    'server': {
        'port': 666,
        'assets': {
            'minifiedCleanups': [
                'src/http/assets/custom/css/',
                'src/http/assets/custom/js/'
            ],
            'minifyOnDebug': False
        },
        'playVideosVLC': True,
        'vlcPath': "%s\\_internal\\bin\\VLC\\vlc.exe" % os.getcwd(),
        'templatePath': 'src/http/templates/',
        'assetsPath': 'src/http/assets/'
    }
}
