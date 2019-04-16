# -*- coding: utf8 -*-

from __future__ import unicode_literals

### Initialize the logging system
import logging
import os

from logging.handlers import RotatingFileHandler
import logging

from conf import Conf
from config import termColors
from threading import Lock

import tqdm

class TqdmLoggingHandler (logging.StreamHandler):
    def __init__ (self, level = logging.NOTSET):
        super (self.__class__, self).__init__ (level)

    def emit (self, record):
        try:
            msg = self.format (record)
            tqdm.tqdm.write (msg)
            self.flush ()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

class ColorFormatter(logging.Formatter):

    def __init__(self, *args, **kwargs):
        # can't do super(...) here because Formatter is an old school class
        logging.Formatter.__init__(self, *args, **kwargs)
        self.DEFAULT_COLOR = termColors.IWhite
        self.COLORS = {
            logging.DEBUG: termColors.White,
            logging.INFO: termColors.Green,
            logging.WARNING: termColors.BYellow,
            logging.ERROR: termColors.Red,
            logging.CRITICAL: termColors.BIRed
        }

    def format(self, record):
        color = self.COLORS[record.levelno] if record.levelno in self.COLORS \
            else self.DEFAULT_COLOR
        record.msg = color + record.msg + termColors.Color_Off
        message = logging.Formatter.format(self, record)
        return message\
            .replace(
                record.levelname,
                '%s%s%s'
                % (termColors.Purple, record.levelname, termColors.Color_Off))\
            .replace(
                record.filename,
                '%s%s%s'
                % (termColors.Cyan, record.filename, termColors.Color_Off))


class LockedRotatingFileHandler(RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super(LockedRotatingFileHandler, self).__init__(*args, **kwargs)
        self._lock = Lock()

    def doRollOver(self):
        # doesn't work - file is still in use by the user process, even if locked
        with self._lock:
            super(LockedRotatingFileHandler, self).doRollOver()


def init(verbose=0, quiet=False, filename='activity.log', colored=True):
    """
    Initialize the logger
    * verbose (int) specify the verbosity level of the standart output
      0 (default) ~ ERROR, 1 ~ WARN & WARNING, 2 ~ INFO, 3 ~ DEBUG
    * quiet (boolean) allow to remove all message whatever is the verbosity lvl
    """
    if not os.path.exists('log'):
        os.mkdir('log')

    with open("log/" + filename, 'w'):
        pass
    with open("log/errors.log", 'w'):
        pass

    logger = logging.getLogger()
    logger.propagate = False
    logger.setLevel(min([Conf['log']['fileLevel'],
                         verbose]))

    formatter = logging.Formatter(
        '%(asctime)s :: %(levelname)s :: ' +
        '%(filename)s:%(funcName)s[%(lineno)d] :: %(message)s')
    file_handler = LockedRotatingFileHandler("log/" + filename, 'w', 10000000, 10)
    file_handler.setLevel(Conf['log']['fileLevel'])
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    formatter = logging.Formatter(
        '%(asctime)s :: %(levelname)s :: ' +
        '%(filename)s:%(funcName)s[%(lineno)d] :: %(message)s')
    file_handler = LockedRotatingFileHandler("log/errors.log", 'w', 10000000, 10)
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if not quiet:
        Formatter = ColorFormatter if colored else logging.Formatter
        formatter = Formatter(
            '%(levelname)s :: %(filename)s :: %(message)s')
        stream_handler = TqdmLoggingHandler()
        if verbose is 0:
            stream_handler.setLevel(logging.ERROR)
        elif verbose is 1:
            stream_handler.setLevel(logging.WARNING)
        elif verbose is 2:
            stream_handler.setLevel(logging.INFO)
        else:
            stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logging.info("=" * 80)
    logging.info('Logging system started: verbose=%d, quiet=%s' %
                 (verbose, str(quiet)))
