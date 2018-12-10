# -*- coding: utf8 -*-

from __future__ import unicode_literals

import os
import re
import random
import json
import time
import logging
import shutil
import random
from pprint import pformat

from tornado.web import RequestHandler, HTTPError

from server import model, memory
from conf import Conf
from tools.utils import timeFormat

class AlbumsHandler(RequestHandler):
    """Handle requests related to the videos"""

    def __populatePicturesURLs(self, album):
        """
        Will populate the `picturesURL` field of the given album dict with valid URLs.
        """
        picBaseURL = '/download/album/'
        # ensure trailing slash
        if picBaseURL[-1] != '/':
            picBaseURL += '/'
        #add album id to complain to the route format defined in the server class
        picBaseURL += "%s/" % str(album['_id'])
        # for each picture:
        album['picturesURL'] = [
            picBaseURL + str(i)
            for i in range(album['picsNumber'])]

        return album

    def display(self):
        """
        Route: GET /api/album/display
        Return the list of all albums of the database.
        If the parameter `albumId` is defined, only this album will be returned.
        """
        albumId = self.get_argument('albumId', default=None)

        if albumId is None:
            albums = model.getService('album').getAll(
                returnList=True, orderBy={'creation': -1})

            if not albums:
                return self.write(json.dumps([]))
            index, found = next(((i, x) for i, x in enumerate(albums) if x['fullPath'] == 'random'), (-1, False))
            if not found:
                albums.insert(0, model.getService('album').getById('random'))
            else:
                albums.pop(index)
                albums.insert(0, found)
            index, found = next(((i, x) for i, x in enumerate(albums) if x['fullPath'] == 'starred'), (-1, False))
            if not found:
                albums.insert(0, model.getService('album').getById('starred'))
            else:
                albums.pop(index)
                albums.insert(0, found)
            albums = [self.__populatePicturesURLs(a) for a in albums]
            self.write(json.dumps(albums))
        else:
            album = model.getService('album').getById(albumId)
            if album is None:
                raise HTTPError(404, 'Not Found')
            album = self.__populatePicturesURLs(album)
            self.write(json.dumps(album))

    def tag(self):
        """
        Route: POST /api/album/tag
        This will add or remove a tag to/from a album.
        This require the `tagId` and the `albumId` parameters to be defined
        To remove the tag instead of adding it, provide a `remove` parameter
        set to True.
        """
        tagId = self.get_argument('tagId')
        albumId = self.get_argument('albumId')
        remove = self.get_argument('remove', default=False)

        if remove:
            model.getService('album').removeTag(tagId, albumId=albumId)
        else:
            model.getService('album').addTag(albumId, tagId)

        self.write(json.dumps({"success": True}))

    def star(self):
        """
        Route: POST /api/album/star
        This will save the given picture as starred.
        This require the `albumId` and the `pictureIdx` to be defined.
        `pictureIdx` should be the index of the picture to star
        in the pictures array of the album.
        If `remove` is prodided and True, the picture will be unstarred instead.
        """
        pictureIdx = int(self.get_argument('pictureIdx'))
        albumId = self.get_argument('albumId')
        remove = self.get_argument('remove', default=False)
        logging.debug("PictureIDx=%d, albumId=%s, remove=%s" % (pictureIdx, albumId, str(remove)))

        if remove:
            model.getService('album').removeStar(albumId, pictureIdx)
        else:
            model.getService('album').addStar(albumId, pictureIdx)

        self.write(json.dumps({"success": True}))

    def cover(self):
        """
        Route: POST /api/album/cover
        This will select a new picture to be displayed as album cover
        This require the `albumId` and the `pictureIdx` to be defined.
        `pictureIdx` should be the index of the picture to select
        """
        pictureIdx = int(self.get_argument('pictureIdx'))
        albumId = self.get_argument('albumId')
        logging.debug("PictureIDx=%d, albumId=%s" % (pictureIdx, albumId))

        model.getService('album').selectCover(albumId, pictureIdx)

        self.write(json.dumps({"success": True}))

    def deletePic(self):
        """
        Route: DELETE /api/album/picture
        Remove a picture from an album.
        This will also permanentely delete the picture from the data folder.
        This requires the parameter 'pictureIdx' to be set.
        This also requires the parameter 'albumId' to be set.
        """
        albumId = self.get_argument('albumId')
        pictureIdx = int(self.get_argument('pictureIdx'))

        album = model.getService('album').getById(albumId)
        album['fullPath'] = '%s%s' % (
            Conf['data']['albums']['rootFolder'],
            album['fullPath'])
        logging.warning("Deleting picture %s from album %s" % (pictureIdx, album['name']))

        model.getService('album').removePicture(albumId, pictureIdx)

        try:
            if albumId != 'random' and albumId != 'starred':
                os.remove(album['fullPath'] + album['pictures'][pictureIdx])
            else:
                # the pictures array contains the fullpath
                # (the physical album does not exist)
                os.remove(album['pictures'][pictureIdx])
        except Exception as e:
            logging.error("Unable to remove picture %s from album %s."
                          % (album['name'], album['pictures'][pictureIdx]))
            raise

        self.write(json.dumps({'success': True}))

    def deleteAlbum(self):
        """
        Route: DELETE /api/album/album
        Remove the album from the database, as well as ALL the pictures is contains
        from the data folder.
        This requires the parameter 'album' to be defined.
        """
        albumId = self.get_argument('albumId')
        album = model.getService('album').getById(albumId)
        album['fullPath'] = '%s%s' % (
            Conf['data']['albums']['rootFolder'],
            album['fullPath'])
        logging.warning("Deleting album %s" % (album['name']))
        if albumId == 'starred' or albumId == 'random':
            raise Exception("Unable to delete the %s album!" % albumId)

        model.getService('album').deleteById(albumId)
        try:
            shutil.rmtree(album['fullPath'])
        except Exception as e:
            logging.error("Unable to remove album at location: %s" % album['fullPath'])
            raise

        self.write(json.dumps({'success': True}))

    def migrate(self):
        albums = model.getService('album').getAll()
        toRemove = 'Photos\\'
        for album in albums:
            logging.info("Migrating: %s" % album['name'])
            if album['fullPath'].startswith(toRemove):
                model.getService('album').set(
                    album['_id'],
                    'fullPath', album['fullPath'][len(toRemove):])
        self.write("OK")

    def get(self, resource):
        """
        This will handle the GET requests to the /api/album/* route
        """
        avail_resources = {
            'display': self.display,
            'migrate': self.migrate
        }
        if resource in avail_resources:
            return avail_resources[resource]()
        raise HTTPError(404, "Not Found: %s" % resource)

    def post(self, resource):
        """
        This will handle the post requests to the /api/album/* route
        """
        avail_resources = {
            'tag': self.tag,
            'star': self.star,
            'cover': self.cover
        }
        if resource in avail_resources:
            return avail_resources[resource]()
        raise HTTPError(404, "Not Found: %s" % resource)

    def delete(self, resource):
        """
        This will handle the DELETE requests to the /api/album/* route
        """
        avail_resources = {
            'album': self.deleteAlbum,
            'picture': self.deletePic
        }
        if resource in avail_resources:
            return avail_resources[resource]()
        raise HTTPError(404, "Not Found: %s" % resource)
