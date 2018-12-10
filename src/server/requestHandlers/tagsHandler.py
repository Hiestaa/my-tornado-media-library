# -*- coding: utf8 -*-

from __future__ import unicode_literals

import os
import re
import random
import json
import time

from tornado.web import RequestHandler, HTTPError

from server import model, memory
from conf import Conf


class TagsHandler(RequestHandler):
    """Handle requests related to the tags"""
    def create(self):
        """
        Route: POST /api/tag/create
        Create a new tag. Requires the parameters `name` and `value` to be set.
        The parameter `relation` can be set to use this tag to suggest related videos
        The parameter `autotag` can be set to enable automatic tagging of imported albums and videos
        """
        name = self.get_argument('name').lower()
        value = self.get_argument('value').lower()
        relation = self.get_argument('relation', default=False)
        autotag = self.get_argument('autotag', default='')
        home = self.get_argument('home', default=False)
        if relation == 'false':
            relation = False
        elif relation == 'true':
            relation = True
        if home == 'false':
            home = False
        elif home == 'true':
            home = True

        _id = model.getService('tag').insert(
            name, value, _id=None, relation=relation,
            autotag=autotag, home=home)
        inserted = model.getService('tag').getById(_id)
        inserted['name'] = inserted['name'].title()
        inserted['value'] = inserted['value'].title()
        self.write(json.dumps(inserted))

    def delete(self):
        """
        Route: POST /api/tag/delete
        Delete a tag. Requires the parameter `tagId` to be set.
        """
        tagId = self.get_argument('tagId')
        model.getService('tag').deleteById(tagId)
        model.getService('video').removeTag(tagId)
        model.getService('album').removeTag(tagId)

        self.write('{"success": true}')

    def __count_usage(self, tags):
        """
        Count the number of videos that holds each tags.
        The result will be added to each tag as a field named 'usage'.
        """
        for tag in tags:
            _, count = model.getService('video').find({
                'tags': [{'$value': tag['_id']}]
            }, returnCount=True)
            tag['usage'] = count
            _, count = model.getService('album').find({
                'tags': [tag['_id']]
            }, returnCount=True)
            tag['usage'] += count

    def get(self):
        """
        Route: POST /api/tag/get
        Get all avilable tags, or a single tag given by id
        if the parameter `tagId` is provided.
        For each tag returned, the number of related videos will be attached
        **ONLY IF** the parameter 'usage' is set to True.
        """
        tagId = self.get_argument('id', default=None)
        usage = self.get_argument('usage', default=False)
        if usage =='false':
            usage = False
        if tagId is None:
            tagsG = model.getService('tag').getAll(returnList=False, orderBy={'name': 1, 'value': 1})
            tags = []
            for tag in tagsG:
                tag['name'] = tag['name'].title()
                tag['value'] = tag['value'].title()
                tags.append(tag)
            if usage:
                self.__count_usage(tags)
            self.write(json.dumps(tags))
        else:
            tag = model.getService('tag').getById(tagId)
            tag['name'] = tag['name'].title()
            tag['value'] = tag['value'].title()
            if usage:
                self.__count_usage([tag])
            self.write(json.dumps(tag))

    def edit(self):
        """
        Route: POST /api/tag/edit
        Edit a property of a tag. Require the parameters `property`,
        `value` and `tagId` to be set.
        Writes back the edited tag.
        """
        field = self.get_argument('property')
        value = self.get_argument('value').lower()
        tagId = self.get_argument('tagId').lower()
        usage = self.get_argument('usage', default=False)
        if usage =='false':
            usage = False

        if field == 'relation' or field == 'home':
            if value == 'false':
                value = False
            elif value == 'true':
                value = True

        model.getService('tag').set(tagId, field, value)
        res = model.getService('tag').getById(tagId)
        res['name'] = res['name'].title()
        res['value'] = res['value'].title()
        if usage:
            self.__count_usage([res])
        self.write(json.dumps(res))

    def post(self, resource):
        resources = {
            'edit': self.edit,
            'get': self.get,
            'delete': self.delete,
            'create': self.create
        }
        if resource in resources:
            return resources[resource]()
        raise HTTPError(404, 'Not Found')
