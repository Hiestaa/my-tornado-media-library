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
            'rootFolder': ".\\_internal\\bin\\MongoDB\\bin\\",  # trailing '\' is required
            'dataFolder': ".\\data\\db", #"%s\\data\\db\\" % os.getcwd(),
            'dbName': 'vice',
            'dumpFolder': ".\\dumps\\",
            'dumpDelay': 60 * 60 * 24  # a day
        },
        'ffmpeg': {
            'exePath': '.\\_internal\\bin\\ffmpeg\\ffmpeg.exe',
            'snapshotDimensions': (640, 360),
            # per recommendation on https://cloud.google.com/vision/docs/supported-files
            'minividDimension': (800, 450),
            'minividFrameRate': '24/1',
            'minividPostProcContext': 10,
            'frameRate': '1/60',
            'probePath': '.\\_internal\\bin\\ffmpeg\\ffprobe.exe',
            'compileFolder': '.\\workspace\\compilations'
        },
        'videos': {
            'insertOnCVError': False,
            'rootFolder': '.\\data\\videos\\',
            'allowedTypes': ['avi', 'mkv', 'flv', 'mpg', 'mp4', 'wmv', 'mov', 'm4v', 'm4a', '3gp'],
            'displayPerPage': 9,
        },
        'albums': {
            'rootFolder': '.\\data\\photos\\',
            'allowedTypes': ['png', 'jpg', 'jpeg']
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
        'vlcPath': ".\\_internal\\bin\\VLC\\vlc.exe",
        'templatePath': 'src/http/templates/',
        'assetsPath': 'src/http/assets/'
    },
    'client': {
        'dbUpdateStatus': {
            'itemsOnPage': 20
        }
    }
}
