# -*- coding: utf8 -*-
from __future__ import unicode_literals

from pprint import pformat
import logging
import time
import random
import os
import json
from tqdm import tqdm

from pymongo import DESCENDING, ASCENDING
from bson.objectid import ObjectId

from conf import Conf
from server.services.baseService import Service
from tools.utils import extends, timeFormat
from tools.analyzer.analyzers import AlbumAnalyzer

"""
Schema:
    * _id:string id of the album
    * album:string name of the album as saved on disk
    * fullPath:string fullPath to the root folder of this album (all the pictures are
                      expected to be found in this folder) (with trailing /)
                      WARNING: the 'data.albums.rootFolder' prefix won't be included
    * picturesDetails:array list of pictures in this albums, where each picture is an object
                            with the shape {filename, display, starred, analyzerVersion, width, height}
    * cover:int index of the picture to be used as cover for this album.
    * name:string display name for this album
    * display:int number of times this album has been shown to the client
    * picsNumber:int number of pictures in this album
    * starredNumber:int number of starread pictures in this album
    * creation:float timestamp of the creation of the album
    * lastDisplay:float timestamp of the last time this album has been displayed
    * lastStarred:float timestamp of the last time this album has been marked starred
    * averageWidth: average width of the pictures in this album
    * averageHeight: average height of the pictures in this album,
    * tags:list of tags attached to this album
"""


class AlbumService(Service):
    """
    Provides helper functions related to the Albums collection
    of the database.
    """
    def __init__(self, db):
        super(AlbumService, self).__init__(db, 'albums')
        self._collection.ensure_index(
            [('creation', DESCENDING)], name="album_creation_idx")

    def schema(self):
        return {
            'album':True,
            'fullPath': True,
            'picturesDetails': True,
            'cover':True,
            'name':True,
            'display':True,
            'picsNumber':True,
            'starredNumber': True,
            'creation':True,
            'lastDisplay':True,
            'lastStarred':True,
            'averageWidth': True,
            'averageHeight': True,
            'tags': True
        }

    def getByRealName(self, realName):
        return self._collection.find_one({
            'album': realName
        })

    def insert(self, album, fullPath, picturesDetails, cover=0, name=None,
               display=0, picsNumber=None, creation=None,
               lastDisplay=0, lastStarred=0, averageWidth=0, averageHeight=0,
               tags=None, _id=None):
        """
        Insert a new document and returns its id
        """
        logging.debug("Saving new album: %s" % album)
        creation = creation or time.time()
        tags = tags or []

        if name is None:
            name = album
        if picsNumber is None:
            picsNumber = len(picturesDetails)
        # ensure proper folder separator
        toRemove = Conf['data']['albums']['rootFolder']
        if fullPath.startswith(toRemove):
            fullPath = fullPath[len(toRemove):]
        fullPath.replace('\\', os.path.sep)
        fullPath.replace('/', os.path.sep)

        if fullPath[-1] != os.path.sep:
            fullPath += os.path.sep
        post = self.schema()
        post['album'] = album
        post['fullPath'] = fullPath
        post['picturesDetails'] = picturesDetails
        post['cover'] = cover
        post['name'] = name
        post['display'] = display
        post['picsNumber'] = picsNumber
        post['starredNumber'] = 0
        post['creation'] = creation
        post['lastDisplay'] = lastDisplay
        post['lastStarred'] = lastStarred
        post['averageWidth'] = averageWidth
        post['averageHeight'] = averageHeight
        post['tags'] = tags

        if _id is not None:
            post['_id'] = ObjectId(_id)
        _id = self._collection.insert(self.validate(post))
        return str(_id)

    def addTag(self, _id, tagId):
        logging.debug("Pushing tag %s to album %s" % (tagId, _id))
        self._collection.update(
            {'_id': ObjectId(_id)},
            {'$addToSet': {'tags': tagId}})

    def removeTag(self, tagId, albumId=None):
        if albumId is not None:
            self._collection.update(
                {'_id': ObjectId(albumId)},
                {'$pull': {'tags': tagId}})
        else:
            self._collection.update(
                {'tags': {'$in': [tagId]}},
                {'$pull': {'tags': tagId}},
                multi=True)

    def getByPath(self, fullPath, fields=None):
        """
        Return an album specific to this path.
        fullPath is the path where the album is stored on hard-drive.
        fields is the list of fields to be returned (all by default)
        """
        if fields is None:
            return self._collection.find_one({'fullPath': fullPath})
        return self._collection.find_one({
            'fullPath': fullPath
        }, {
            field: 1 for field in fields
        })

    def __findBelongingAlbum(self, albumId, pictureIdx):
        """
        When a picture get starred or deleted from the 'random' or
        'starred' album, we need to find the right album it belongs to.
        To get it, use the path of the picture, as each album has a unique
        `fullPath`.
        Returns a tuple (realAlbumId, realPictureIdx)
        """
        if pictureIdx == 0:
            raise Exception("The picture nb %d does not belong to any album!" % pictureIdx)
        # get starred or random album document
        album = self.getById(albumId)
        # find fullPath
        picPath = album['picturesDetails'][pictureIdx]['filename']
        fullPath = os.path.dirname(picPath) + os.path.sep
        logging.debug("Picture belongs to album with fullPath: %s" % fullPath)
        # find album
        realAlbum = self.getByPath(fullPath)
        # find real picture index in the real album
        realPicIdx = None
        try:
            realPicIdx = next(idx for idx, pic in enumerate(realAlbum['picturesDetails'])
                              if pic['filename'] == os.path.basename(picPath))
        except StopIteration:
            logging.warning("Couldn't determine belonging album of picture: %s", picPath)
            pass

        logging.debug("Picture is number %d in album %s" % (realPicIdx, realAlbum['_id']))
        return realAlbum['_id'], realPicIdx

    def selectCover(self, albumId, pictureIdx):
        if albumId == 'random' or albumId == 'starred':
            album = self.getById(albumId, keepRealId=True)
            albumId = album['_id']
        logging.debug("New cover picture: %d" % pictureIdx)
        self._collection.update(
            {'_id': ObjectId(albumId)},
            {'$set': {'cover': pictureIdx}})

    def addStar(self, albumId, pictureIdx):
        if albumId == 'random' or albumId == 'starred':
            return self.addStar(
                *self.__findBelongingAlbum(albumId, pictureIdx))
        logging.debug("New starred picture: %d" % (pictureIdx))
        self._collection.update(
            {'_id': ObjectId(albumId)},
            {'$set': {'picturesDetails.%d.starred' % pictureIdx: True},
             '$inc': {'starredNumber': 1}})

    def removeStar(self, albumId, pictureIdx):
        if albumId == 'random' or albumId == 'starred':
            return self.removeStar(
                *self.__findBelongingAlbum(albumId, pictureIdx))
        logging.debug("Removing star from picture: %d" % (pictureIdx))
        self._collection.update(
            {'_id': ObjectId(albumId)},
            {'$set': {'picturesDetails.%d.starred' % pictureIdx: False},
             '$inc': {'starredNumber': -1}})

    def removePicture(self, albumId, pictureIdx):
        if albumId == 'random' or albumId == 'starred':
            # do not return, we will remove the picture from the 'random' or 'starred'
            # album AND from the belonging album
            self.removePicture(
                *self.__findBelongingAlbum(albumId, pictureIdx))

        album = self.getById(albumId, fields=['_id', 'name', 'picturesDetails', 'cover'], keepRealId=True)
        logging.debug('deleting picture %s from album %s' % (str(pictureIdx), album['_id']))

        if album['cover'] > pictureIdx:
            album['cover'] -= 1

        self._collection.update(
            # in case of 'random' or 'starred' album, the real album id
            # is different than the given parameter `albumId`
            {'_id': ObjectId(album['_id'])},
            {'$pull': {'picturesDetails': album['picturesDetails'][pictureIdx]},
             '$inc': {
                 'picsNumber': -1,
                 'starredNumber': -1
             },
             '$set': {
                'cover': album['cover']
            }})

    def addPicture(self, albumId, picture, width, height):
        if albumId == 'random' or albumId == 'starred':
            raise Exception("Add picture should not be called on %s album!" % albumId)
        self._collection.update({
                '_id': ObjectId(albumId)
            }, {
                '$push': { 'picturesDetails': {
                    'filename': picture,
                    'width': width,
                    'height': height,
                    'analyzerVersion': None,
                    'starred': False,
                    'display': 0
                } },
                '$inc': {'picsNumber': 1}
            })

    def getById(self, _id, keepRealId=False, *args, **kwargs):
        """
        Return a document specific to this id.
        If the _id is 'random123456random123456', a random album will be returned instead
        _id is the _id of the document
        fields is the list of fields to be returned (all by default)
        """
        if _id != 'random' and _id != 'starred':
            ret = super(AlbumService, self).getById(_id, *args, **kwargs)
            if ret is not None and 'fullPath' in ret and \
                    (ret['fullPath'] == 'random' or \
                     ret['fullPath'] == 'starred'):
                raise Exception("Album _id: %s is the %s album with the wrong id"
                                % (_id, ret['fullPath']))
            return ret
        album = self._collection.find_one({'fullPath': _id})
        if album is not None and not keepRealId:
            album['_id'] = _id
        if album is None:
            if _id == 'random':
                album = self.createRandomAlbum()
            elif _id == 'starred':
                album = self.createStarredAlbum()
            self._collection.insert(self.validate(album))
        if not keepRealId:
            album['_id'] = _id
        return album

    def getAll(self, *args, **kwargs):
        kwargs['returnList'] = True
        ret = super(AlbumService, self).getAll(*args, **kwargs)
        for i, alb in enumerate(ret):
            if 'fullPath' in alb and alb['fullPath'] == 'random':
                ret[i]['_id'] = 'random'
            if 'fullPath' in alb and alb['fullPath'] == 'starred':
                ret[i]['_id'] = 'starred'
        return ret

    def resetRandomAlbum(self, replace=False):
        album = self._collection.find_one({'fullPath': 'random'})
        if album is not None and not replace:
            return

        self._collection.remove({'fullPath': 'random'})
        album = self.createRandomAlbum()
        self._collection.insert(self.validate(album))

    def createRandomAlbum(self):
        logging.warning("Creating new random album!")
        start = time.time()
        albums = self.getAll(returnList=True)
        random.seed()
        random_album = {
            'album': 'Random',
            'fullPath': 'random',
            'picturesDetails': [],
            'cover': 0,
            'name': 'Random',
            'display': 0,  # sum of all albums display value
            'picsNumber': 0,  # sum of all picsNumber values
            'starredNumber': 0,  # sum of all starredNumber values
            'creation': 0,  # min of creation values
            'lastDisplay': 0,  # max of lastDisplay values
            'lastStarred': 0,  # max of lastStarred values
            'averageWidth': 0,  # average of all albums
            'averageHeight': 0,  # average of all albums
            'tags': [],  # no tags
        }
        if len(albums) == 0:
            random_album['picturesDetails'] = [{'filename': os.path.join(*((Conf['server']['assetsPath'] + 'custom/img/question-mark.png').split('/')))}]
            return random_album

        random_album['display'] = sum((album['display'] for album in albums))
        random_album['creation'] = time.time()
        random_album['lastDisplay'] = max((album['lastDisplay'] for album in albums))
        random_album['lastStarred'] = max((album['lastStarred'] for album in albums))
        random_album['averageWidth'] = sum((album['averageWidth'] for album in albums)) / len(albums)
        random_album['averageHeight'] = sum((album['averageHeight'] for album in albums)) / len(albums)

        random_album['picturesDetails'] = []
        for album in albums:
            if album['fullPath'] == 'starred' or album['fullPath'] == 'random':
                continue
            for pic in album['picturesDetails']:
                random_album['picturesDetails'].append({
                    'filename': album['fullPath'] + pic['filename'],
                    'starred': True,
                    'width': pic.get('width'),
                    'height': pic.get('height'),
                    'analyzerVersion': pic.get('analyzerVersion')
                })

        random_album['picsNumber'] = len(random_album['picturesDetails'])
        random_album['starredNumber'] = sum(1 if pic.get('starred', False) else 0 for pic in random_album['picturesDetails'])

        random.shuffle(random_album['picturesDetails'])
        random_album['picturesDetails'] = [
            {'filename': os.path.join(*((Conf['server']['assetsPath'] + 'custom/img/question-mark.png').split('/')))}
        ] + random_album['picturesDetails']
        logging.info("Random album generated in %s" % timeFormat(time.time() - start))
        return random_album

    def resetStarredAlbum(self, replace=False):
        album = self._collection.find_one({'fullPath': 'starred'})
        if album is not None and not replace:
            return

        self._collection.remove({'fullPath': 'starred'})

        album = self.createStarredAlbum()
        self._collection.insert(self.validate(album))

    def createStarredAlbum(self):
        logging.warning("Creating new starred album!")
        start = time.time()
        albums = self.getAll(returnList=True)
        random.seed()
        starred_album = {
            'album': 'Starred',
            'fullPath': 'starred',
            'picturesDetails': [],
            'cover': 0,
            'name': 'Starred',
            'display': 0,  # sum of all albums display value
            'picsNumber': 0,  # sum of all picsNumber values
            'starredNumber': 0,  # sum of all picsNumber values
            'creation': 0,  # min of creation values
            'lastDisplay': 0,  # max of lastDisplay values
            'lastStarred': 0,  # max of lastStarred values
            'averageWidth': 0,  # average of all albums
            'averageHeight': 0,  # average of all albums
            'tags': [],  # no tags
        }
        if len(albums) == 0:
            starred_album['picturesDetails'] = [{'filename': os.path.join(*((Conf['server']['assetsPath'] + 'custom/img/star-red.png').split('/')))}]
            return starred_album

        starred_album['display'] = sum((album['display'] for album in albums))
        starred_album['creation'] = time.time()
        starred_album['lastDisplay'] = max((album['lastDisplay'] for album in albums))
        starred_album['lastStarred'] = max((album['lastStarred'] for album in albums))
        starred_album['averageWidth'] = sum((album['averageWidth'] for album in albums)) / len(albums)
        starred_album['averageHeight'] = sum((album['averageHeight'] for album in albums)) / len(albums)

        for album in albums:
            if album['fullPath'] == 'starred' or album['fullPath'] == 'random':
                continue
            for pic in album['picturesDetails']:
                if pic.get('starred', False):
                    starred_album['picturesDetails'].append({
                        'filename': (album['fullPath'] + pic['filename']),
                        'starred': True,
                        'width': pic.get('width'),
                        'height': pic.get('height'),
                        'analyzerVersion': pic.get('analyzerVersion')
                    })

        random.shuffle(starred_album['picturesDetails'])

        starred_album['picturesDetails'] = [{
            'filename': os.path.join(*((Conf['server']['assetsPath'] + 'custom/img/star-red.png').split('/'))),
            'starred': True,
            'width': 0,
            'height': 0,
            'analyzerVersion': None
        }] + starred_album['picturesDetails']

        starred_album['picsNumber'] = len(starred_album['picturesDetails'])
        starred_album['starredNumber'] = len(starred_album['picturesDetails'])
        logging.info("Starred album generated in %s" % timeFormat(time.time() - start))

        return starred_album

    def find(self, criteria, page=0, item_per_page=0, generator=True, returnCount=False):
        """
        FIXME: make a common function with the video service god damn it!
        """
        logging.debug("Building mongo criteria from criteria: %s" % pformat(criteria))

        criteria = extends(criteria, type='any', album=[], tags=[])

        mongo_criteria = []
        for filtre in criteria['album']:
            mongo_filtre = {}
            if not '$comparator' in filtre:
                filtre['$comparator'] = '='
            for key, val in filtre.items():
                if key == '$comparator':
                    continue
                if key == 'name':
                    mongo_filtre[key] = {'$regex': '.*' + '.*'.join(val.split(' ')) + '.*', '$options': 'is'}
                    continue
                if filtre['$comparator'] == '>':
                    mongo_filtre[key] = {'$gte': val}
                elif filtre['$comparator'] == '<':
                    mongo_filtre[key] = {'$lte': val}
                else:
                    mongo_filtre[key] = val
            mongo_criteria.append(mongo_filtre)

        if criteria['type'] == 'all' and len(criteria['tags']) > 0:
            mongo_criteria.append({'tags': {'$all': criteria['tags']}})
        elif criteria['type'] == 'any' and len(criteria['tags']) > 0:
            for tagid in criteria['tags']:
                mongo_criteria.append({'tags': tagid})

        if len(mongo_criteria) == 0:
            mongo_criteria = {}
        elif criteria['type'] == 'all':
            mongo_criteria = {'$and': mongo_criteria}
        elif criteria['type'] == 'any':
            mongo_criteria = {'$or': mongo_criteria}
        else:
            logging.error("Unrecognized criteria type: %s" % criteria['type'])

        logging.debug("Performing search criteria: \n%s" % pformat(mongo_criteria))
        mongo_criteria['$comment'] = "Built from: %s" % pformat(criteria)

        cursor = self._collection.find(mongo_criteria)
        count = cursor.count()
        if page > 0:
            cursor.skip((page) * item_per_page)
        if item_per_page > 0:
            cursor.limit(item_per_page)

        if generator:
            ret = cursor
        else:
            ret = [itm for itm in cursor]
        if returnCount:
            return ret, count
        return ret

    def getUnanalyzedAlbums(self, version):
        """
        Returns the list of pictures that haven't been analyzed.
        Each picture will be a dict of the shape {albumId, pictureIdx, path}
        """
        albums = self.getAll(orderBy={'creation': -1})
        res = [
            {
                '_id': album['_id'],
                'name': album['name'],
                'picturesDetails': [
                    {
                        'albumId': album['_id'],
                        'pictureIdx': picIdx,
                        'path': album['fullPath'] + pic['filename'],
                        'filename': pic['filename'],
                        'version': pic.get('analyzerVersion'),
                        'albumName': album['name']
                    }
                    for picIdx, pic in enumerate(album['picturesDetails'])
                    if pic.get('analyzerVersion') != version
                ]
            }
            for album in albums if album['fullPath'] not in ['starred', 'random']
        ]
        return [album for album in res if len(album['picturesDetails']) > 0]


    # does not actuially save the face annotation as this account for too much data for storing in db
    def setPictureAnalysis(self, albumId, picIdx, version):
        self._collection.update(
            {'_id': ObjectId(albumId)},
            {'$set': {
                'picturesDetails.%d.analyzerVersion' % picIdx: version,
            }})

    def saveAlbumAnalysis(self, album, result):
        analysisPath = Conf['data']['albums']['rootFolder'] + album['fullPath'] + 'analysis.json'
        with open(analysisPath) as f:
            json.dump(result, f)

    # picture details are extended after being loaded with analysis information
    def extendAlbumWithFaces(self, album):
        albumFaces = None
        analysisPath = Conf['data']['albums']['rootFolder'] + album['fullPath'] + 'analysis.json'
        try:
            with open(analysisPath) as f:
                albumFaces = json.load(f)
                if len(albumFaces) != len(album['picturesDetails']):
                    albumFaces = None
        except:
            pass

        # speed up random album face retrieval
        allfaces = {}
        cachePath = Conf['data']['albums']['rootFolder'] + 'allfaces.json'
        if album['fullPath'] == 'random':
            try:
                with open(cachePath) as f:
                    allfaces = json.load(f)
            except:
                pass

        for idx, picture in enumerate(tqdm(album['picturesDetails'], desc="[Populating faces")):
            if picture['filename'] in allfaces:
                picture['faces'] = allfaces[picture['filename']]
            if albumFaces is not None:
                picture['faces'] = albumFaces[idx]['faces']
            else:
                picPath = Conf['data']['albums']['rootFolder'] + \
                    album['fullPath'] + picture['filename']
                # special case random and starred albums, the picture filename contains the album path
                if album['fullPath'] in ['starred', 'random']:
                    picPath = Conf['data']['albums']['rootFolder'] + \
                        picture['filename']
                try:
                    picture['faces'] = AlbumAnalyzer.checkCache(picPath)['faces']
                except Exception as e:
                    logging.warn("Unable to retrieve any face data for picture: %s",
                                 picPath)
                    picture['faces'] = {}

            if album['fullPath'] == 'random':
                allfaces[picture['filename']] = picture['faces']

        if album['fullPath'] == 'random':
            try:
                with open(cachePath) as f:
                    json.dump(allfaces, f)
            except:
                pass

        return album

    def setPictureDim(self, albumId, picIdx, width, height):
        self._collection.update(
            {'_id': ObjectId(albumId)},
            {'$set': {
                'picturesDetails.%d.width' % picIdx: width,
                'picturesDetails.%d.height' % picIdx: height,
            }})
