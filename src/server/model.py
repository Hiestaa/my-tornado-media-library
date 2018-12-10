# -*- coding: utf8 -*-

from __future__ import unicode_literals

import logging
import sys
import os
import json
import time
from datetime import datetime
from threading import Thread
import subprocess
from threading import Lock
from pymongo import MongoClient, database
from pymongo.errors import ConnectionFailure
from pymongo.son_manipulator import SONManipulator

from conf import Conf
from server.services.baseService import Service
from server.services.videoService import VideoService
from server.services.tagService import TagService
from server.services.albumService import AlbumService
from tools.utils import dateFormat, sizeFormat, getFolderSize

class ObjectIdManipulator(SONManipulator):
    def transform_outgoing(self, son, collection):
        if '_id' in son:
            son[u'_id'] = str(son[u'_id'])
        return son


class ModelException(Exception):
    pass


class MongoServerProcess(Thread):
    def __init__(self):
        super(MongoServerProcess, self).__init__()
        self.prog = None

    def run(self):
        try:
            FNULL = open(os.devnull, 'w')
            command = '"%smongod.exe" --dbpath "%s"' \
                % (Conf['data']['mongoDB']['rootFolder'],
                   Conf['data']['mongoDB']['dataFolder'])
            print ("Running command: ", command)
            self.prog = subprocess.Popen(
                command, stdout=FNULL, shell=True)
            logging.info("MongoDB Server PID: %d" % self.prog.pid)
        except KeyboardInterrupt:
            print("Exiting mongodb server thread.")
            self.prog = None

    def stop(self):
        if self.prog is not None:
            logging.info("Killing process PID: %d" % self.prog.pid)
            self.prog.kill()
            self.prog = None


### This class is the interface with the mongodb api.
class Model(object):
    """
    This class is the interface with the mongodb api.
    It is used to retrieve text to be used by the nlp algorithm from the loops
    collection and to cache items like account list, locations or
    generated reports
    It manages its own back-up system by creating DB dumps every week
    (or any configured delay)
    """
    def __init__(self):
        super(Model, self).__init__()
        self._server_process = None
        logging.info("Starting mongo client")
        # create connection
        try:
        	raise ConnectionFailure()
            # self._connection = MongoClient(
            #     host=Conf['data']['mongoDB']['host'],
            #     port=Conf['data']['mongoDB']['port'])
        except ConnectionFailure as e:
            logging.warning("Unable to connect to MongoDB server.")
            if Conf['data']['mongoDB']['forceStart']:
                logging.info("Forcing MongoDB Startup.")
                self._server_process = MongoServerProcess()
                self._server_process.start()
                success = False
                retry = 0
                while not success:
                    try:
                        self._connection = MongoClient(
                            host=Conf['data']['mongoDB']['host'],
                            port=Conf['data']['mongoDB']['port'])
                        logging.info("Connection succeed!")
                        success = True
                    except ConnectionFailure as e:
                        logging.warning("MongoDB Server connection failed on %s:%s"
                                        % (Conf['data']['mongoDB']['host'],
                                           Conf['data']['mongoDB']['port']))
                        logging.warning(repr(e))
                        retry += 1
                        if retry > 10:
                            raise ModelException("Max connection retries to MongoDB server (%d) exceeded."
                                                 % (10))
            else:
                raise ModelException("Exiting now. Set Conf['data']['mongoDB']['forceStart'] tu True \
to attempt to force to start a MongoDB server instance locally.")

        self._db = self._connection[Conf['data']['mongoDB']['dbName']]
        self._db.add_son_manipulator(ObjectIdManipulator())

        self._services = {
            'video':  VideoService(self._db),
            'tag': TagService(self._db),
            'album': AlbumService(self._db)
        }

        self.dumpDB(Conf['data']['mongoDB']['dumpFolder'])

    def dumpDB(self, dirPath):
        """
        Create a dump of the database for a future data restore in the given dirPath.
        A script `restore.bat` and `restore.sh` will be created to allow later restore of the data
        """
        if not os.path.exists(dirPath):
            os.mkdir(dirPath)
        statusFile = os.path.join(dirPath, 'status.json')
        if os.path.exists(statusFile):
            try:
                with open(statusFile, 'r') as f:
                    status = json.load(f)
            except Exception as e:
                status = None
        else:
            status = None
        if status is not None and time.time() - status['lastDump'] \
                < Conf['data']['mongoDB']['dumpDelay']:
            logging.info("Dumping database is not required: \
last dump performed on %s. Next dump will be done on %s."
% (status['dateForHumans'],
   dateFormat(status['lastDump'] + Conf['data']['mongoDB']['dumpDelay'])))
            return # do not perform the dump right now.
        dirPath = os.path.join(dirPath, datetime.fromtimestamp(
            int(time.time())).strftime('%Y-%m-%d_%H-%M-%S'))
        logging.info("Dumping data into folder: %s" % dirPath)
        try:
            os.mkdir(dirPath)
            subprocess_call = '"%smongodump.exe" --db %s --out %s'\
                % (Conf['data']['mongoDB']['rootFolder'],
                   Conf['data']['mongoDB']['dbName'],
                   dirPath)
            logging.debug("Calling: %s" % subprocess_call)
            subprocess.call(subprocess_call, shell=True)
            size = getFolderSize(dirPath)
            logging.info("Dump successfully done (%s)! \
You may want to restore these data later using:" % (sizeFormat(size)))
            restore_cmd = '"%smongorestore.exe" --db %s "%s"'\
                % (Conf['data']['mongoDB']['rootFolder'],
                   Conf['data']['mongoDB']['dbName'],
                   os.path.join(dirPath, Conf['data']['mongoDB']['dbName']))
            logging.info(restore_cmd)
            with open(os.path.join(dirPath, 'restore.bat'), 'w') as f:
                f.write(restore_cmd + '\n')
                f.write('pause\n')
            with open(os.path.join(dirPath, 'restore.sh'), 'w') as f:
                f.write(restore_cmd + '\n')
        except Exception as e:
            logging.error("Unable to perform the dump, an error occured.")
            logging.error(repr(e))
            logging.error("A new dump will be attempted upon next start-up.")
            return
        with open(statusFile, 'w') as sf:
            json.dump({
                'lastDump': time.time(),
                'dateForHumans': dateFormat(time.time()),
                'size': size,
                'sizeForHumans': sizeFormat(size),
                'folder': dirPath,
                'restoreCommand': restore_cmd}, sf)

    def getService(self, service):
        if service in self._services:
            return self._services[service]
        raise ModelException('The service %s does not exist' % service)

    def disconnect(self):
        if self._server_process is not None:
            logging.info("Waiting for MongoDB server process to stop...")
            self._server_process.stop()
            # self._server_process.terminate()
            self._server_process.join()
            logging.info("MongoDB server stopped.")


# this module is a singleton
# This object should not be accessed directly, use getInstance instead.
_instance = None
# will be used to lock the instance while initializing it.
_lock = Lock()

def getInstance():
    global _instance
    global _lock
    if _instance is None:
        with _lock:
            # re-test the _instance value, avoiding the case where another
            # thread did the initialization between the previous test and the
            # lock
            if _instance is None:
                _instance = Model()
    return _instance

def getService(service):
    return getInstance().getService(service)
