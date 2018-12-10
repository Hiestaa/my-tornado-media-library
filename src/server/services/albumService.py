# -*- coding: utf8 -*-
from __future__ import unicode_literals

from pprint import pformat
import logging
import time
import random
import os

from conf import Conf

from bson.objectid import ObjectId

from server.services.baseService import Service
from tools.utils import extends

"""
Schema:
    * _id:string id of the album
    * album:string name of the album as saved on disk
    * fullPath:string fullPath to the root folder of this album (all the pictures are
                      expected to be found in this folder) (with trailing /)
                      WARNING: the 'data.albums.rootFolder' prefix won't be included
    * pictures:array list of pictures in this album. Each picture is
                     represented as a string, name of the file of the picture
                     in the albun's folder
    * cover:int index of the picture to be used as cover for this album.
    * name:string display name for this album
    * display:int number of times this album has been shown to the client
    * picsNumber:int number of pictures in this album
    * creation:float timestamp of the creation of the album
    * lastDisplay:float timestamp of the last time this album has been displayed
    * lastStarred:float timestamp of the last time this album has been marked starred
    * averageWidth: average width of the pictures in this album
    * averageHeight: average height of the pictures in this album,
    * tags:list of tags attached to this album
    * starred: list of id of pictures that have been starred in this album.
"""


class AlbumService(Service):
    """
    Provides helper functions related to the Albumss collection
    of the database.
    """
    def __init__(self, db):
        super(AlbumService, self).__init__(db, 'albums')

    def schema(self):
        return {
            'album':True,
            'fullPath': True,
            'pictures':True,
            'cover':True,
            'name':True,
            'display':True,
            'starred':True,
            'picsNumber':True,
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

    def insert(self, album, fullPath, pictures, cover=0, name=None,
               display=0, picsNumber=None, creation=time.time(),
               lastDisplay=0, lastStarred=0, averageWidth=0, averageHeight=0,
               tags=[], starred=[], _id=None):
        """
        Insert a new document and returns its id
        """
        logging.debug("Saving new album: %s" % album)
        if name is None:
            name = album
        if picsNumber is None:
            picsNumber = len(pictures)
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
        post['pictures'] = pictures
        post['cover'] = cover
        post['name'] = name
        post['display'] = display
        post['starred'] = starred
        post['picsNumber'] = picsNumber
        post['creation'] = creation
        post['lastDisplay'] = lastDisplay
        post['lastStarred'] = lastStarred
        post['averageWidth'] = averageWidth
        post['averageHeight'] = averageHeight
        post['tags'] = tags
        post['starred'] = starred

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
        picPath = album['pictures'][pictureIdx]
        fullPath = os.path.dirname(picPath) + os.path.sep
        logging.debug("Picture belongs to album with fullPath: %s" % fullPath)
        # find album
        realAlbum = self.getByPath(fullPath)
        # find real picture index in the real album
        realPicIdx = realAlbum['pictures'].index(os.path.basename(picPath))
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
            {'$addToSet': {'starred': pictureIdx}})

    def removeStar(self, albumId, pictureIdx):
        if albumId == 'random' or albumId == 'starred':
            return self.removeStar(
                *self.__findBelongingAlbum(albumId, pictureIdx))
        logging.debug("Removing star from picture: %d" % (pictureIdx))
        self._collection.update(
            {'_id': ObjectId(albumId)},
            {'$pull': {'starred': pictureIdx}})

    def removePicture(self, albumId, pictureIdx):
        if albumId == 'random' or albumId == 'starred':
            # do not return, we will remove the picture from the 'random' or 'starred'
            # album AND from the belonging album
            self.removePicture(
                *self.__findBelongingAlbum(albumId, pictureIdx))

        album = self.getById(albumId, fields=['_id', 'name', 'pictures', 'cover', 'starred'], keepRealId=True)
        logging.debug('deleting picture %s from album %s' % (str(pictureIdx), album['_id']))

        for i, idx in enumerate(album['starred']):
            if idx == pictureIdx:
                del album['starred'][i]
            elif idx > pictureIdx:
                logging.debug("Album %s: picture %d becomes %d" % (album['name'], idx, idx - 1))
                album['starred'][i] -= 1
        if album['cover'] > pictureIdx:
            album['cover'] -= 1

        self._collection.update(
            # in case of 'random' or 'starred' album, the real album id
            # is different than the given parameter `albumId`
            {'_id': ObjectId(album['_id'])},
            {'$pull': {'pictures': album['pictures'][pictureIdx]},
             '$inc': {'picsNumber': -1},
             '$set': {
                'cover': album['cover'],
                'starred': album['starred']
            }})

    def addPicture(self, albumId, picture):
        if albumId == 'random' or albumId == 'starred':
            raise Exception("Add picture should not be called on %s album!" % albumId)
        self._collection.update({
                '_id': ObjectId(albumId)
            }, {
                '$push': { 'pictures': picture },
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

    def resetRandomAlbum(self):
        self._collection.remove({'fullPath': 'random'})
        album = self.createRandomAlbum()
        self._collection.insert(self.validate(album))

    def createRandomAlbum(self):
        start = time.time()
        albums = self.getAll(returnList=True)
        random.seed()
        random_album = {
            'album': 'Random',
            'fullPath': 'random',
            'pictures': [],  # add all pictures
            'cover': 0,
            'name': 'Random',
            'display': 0,  # sum of all albums display value
            'picsNumber': 0,  # sum of all picsNumber values
            'creation': 0,  # min of creation values
            'lastDisplay': 0,  # max of lastDisplay values
            'lastStarred': 0,  # max of lastStarred values
            'averageWidth': 0,  # average of all albums
            'averageHeight': 0,  # average of all albums
            'tags': [],  # no tags
            'starred': []  # starred feature should be disabled with random album
        }
        if len(albums) == 0:
            random_album['pictures'] = [os.path.join(*((Conf['server']['assetsPath'] + 'custom/img/question-mark.png').split('/')))]
            return random_album
        random_album['pictures'] = sum(
            ([album['fullPath'] + pic for pic in album['pictures']]
             for album in albums if album['fullPath'] != 'random' and album['fullPath'] != 'starred'),
            [])
        random.shuffle(random_album['pictures'])
        random_album['pictures'] = [os.path.join(*((Conf['server']['assetsPath'] + 'custom/img/question-mark.png').split('/')))] + random_album['pictures']
        random_album['display'] = sum((album['display'] for album in albums))
        random_album['picsNumber'] = len(random_album['pictures'])
        random_album['creation'] = time.time()
        random_album['lastDisplay'] = max((album['lastDisplay'] for album in albums))
        random_album['lastStarred'] = max((album['lastStarred'] for album in albums))
        random_album['averageWidth'] = sum((album['averageWidth'] for album in albums)) / len(albums)
        random_album['averageHeight'] = sum((album['averageHeight'] for album in albums)) / len(albums)
        # perf issue here? complexity: O(nb_pictures ^ 2)
        for album in albums:
            if album['fullPath'] == 'starred' or album['fullPath'] == 'random':
                continue
            for i, pic in enumerate(album['pictures']):
                if i in album['starred']:
                    random_album['starred'].append(random_album['pictures'].index(
                        album['fullPath'] + pic))
        logging.debug("Random album generated in %.3fs" % (time.time() - start))
        return random_album

    def resetStarredAlbum(self):
        self._collection.remove({'fullPath': 'starred'})
        album = self.createStarredAlbum()
        self._collection.insert(self.validate(album))

    def createStarredAlbum(self):
        logging.warning("Creating new starred album!")
        albums = self.getAll(returnList=True)
        random.seed()
        starred_album = {
            'album': 'Starred',
            'fullPath': 'starred',
            'pictures': [],  # add all pictures
            'cover': 0,
            'name': 'Starred',
            'display': 0,  # sum of all albums display value
            'picsNumber': 0,  # sum of all picsNumber values
            'creation': 0,  # min of creation values
            'lastDisplay': 0,  # max of lastDisplay values
            'lastStarred': 0,  # max of lastStarred values
            'averageWidth': 0,  # average of all albums
            'averageHeight': 0,  # average of all albums
            'tags': [],  # no tags
            'starred': []  # starred feature should be disabled with random album
        }
        if len(albums) == 0:
            starred_album['pictures'] = [os.path.join(*((Conf['server']['assetsPath'] + 'custom/img/star-red.png').split('/')))]
            return starred_album
        starred_album['pictures'] = sum(
            ([album['fullPath'] + pic for pic in
                (album['pictures'][starred] for starred in album['starred'] if starred < len(album['pictures']))]
             for album in albums if album['fullPath'] != 'random' and album['fullPath'] != 'starred'),
            [])
        random.shuffle(starred_album['pictures'])
        starred_album['pictures'] = [os.path.join(*((Conf['server']['assetsPath'] + 'custom/img/star-red.png').split('/')))] + starred_album['pictures']
        starred_album['display'] = sum((album['display'] for album in albums))
        starred_album['picsNumber'] = len(starred_album['pictures'])
        starred_album['creation'] = time.time()
        starred_album['lastDisplay'] = max((album['lastDisplay'] for album in albums))
        starred_album['lastStarred'] = max((album['lastStarred'] for album in albums))
        starred_album['averageWidth'] = sum((album['averageWidth'] for album in albums)) / len(albums)
        starred_album['averageHeight'] = sum((album['averageHeight'] for album in albums)) / len(albums)
        starred_album['starred'] = list(range(len(starred_album['pictures'])))  # everything is starred!
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
