# -*- coding: utf8 -*-
from __future__ import unicode_literals

from pprint import pformat
import logging

from bson.objectid import ObjectId

from server.services.baseService import Service

"""
Schema:
    * _id:string id of the tag
    * name:string name of the tag
    * value:mixed value of the tag, can be an integer or a string
    * relation:boolean, state whether related videos by this tag should be displayed on the 'related' section
    * autotag:string regexp to be used when importing a new picture.
                     If the regexp does match the name of the video or the album,
                     this tag will be automatically added to the video or the album.
    * home:boolean state whether videos and pictures related to this tag should be displayed on the home page
"""

class TagService(Service):
    """
    Provides helper functions related to the tags collection
    of the database.
    """
    def __init__(self, db):
        super(TagService, self).__init__(db, 'tags')

    def schema(self):
        return {
            'name': True,
            'value': True,
            'relation': True,
            'autotag': True,
            'home': True
        }

    def insert(self, name, value, _id=None, relation=False, autotag='', home=0):
        logging.debug("Saving new tag: %s - %s" % (name, value))
        post = self.schema()
        post['name'] = name
        post['value'] = value
        post['relation'] = True if relation else False
        post['autotag'] = autotag;
        post['home'] = home
        if _id is not None:
            if not isinstance(_id, ObjectId):
                _id = ObjectId(_id)
            post['_id'] = _id
        return self._collection.insert(self.validate(post))

    def populate(self, videos):
        """
        For each video, will populate the `tags_list` field with a list of
        tags object retrieved from the database, that match the tag ids found
        in the `tags` field of each video.
        """
        # collect all ids
        tags = []
        for video in videos:
            for x in range(len(video['tags'])):
                try:
                    tags.append(ObjectId(video['tags'][x]))
                except:
                    logging.error("TagId: %s (tag #%d) seems to not be a valid\
 objectId (video %s, id=%s)" % (video['tags'][x], x, video['filename'], video['_id']))
        # retrieve objects from the collection
        tags = self._collection.find({'_id': {'$in': tags}})
        # index by id
        tags = {tag['_id']: {
                'name': tag['name'].title(),
                'value': tag['value'].title(),
                '_id': tag['_id'],
                'relation': tag['relation']
            } for tag in tags}
        # make the replacement
        default = lambda _id: {'name': 'Undefined', 'value': 'Undefined', '_id': _id, 'relation': 'Undefined'}
        for video in videos:
            video['tags_list'] = [(tags[tid]) for tid in video['tags'] if tid in tags]

    def getAutoTags(self):
        """
        Returns all the tags that have an non-empty autotag field
        """
        cur = self._collection.find({'autotag': {'$ne': ''}})
        return [t for t in cur]

    def getHomeTags(self, returnList=False):
        """
        Returns all the tags that should be used to build the home page
        """
        cur = self._collection.find({'home': {'$ne': False}})
        if returnList:
            return [t for t in cur]
        return cur

    def getRelationTags(self, returnList=False):
        """
        Returns all the tags that should be used to build the home page
        """
        cur = self._collection.find({'relation': {'$ne': False}})
        if returnList:
            return [t for t in cur]
        return cur
