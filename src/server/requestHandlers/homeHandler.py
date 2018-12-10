# -*- coding: utf8 -*-

from __future__ import unicode_literals

import os
import re
import random
import json
import time
import logging

from tornado.web import RequestHandler, HTTPError

from server import model, memory
from server.requestHandlers.vidsHandler import populateMissingData
from conf import Conf


class HomeHandler(RequestHandler):
    """Handle requests related to the tags"""

    def __count_usage(self, tags):
        """
        Count the number of videos that holds each tags.
        The result will be added to each tag as a field named 'usage'.
        """
        # todo: optimize this function, make only 2 db call
        for tag in tags:
            _, count = model.getService('album').find({
                'tags': [tag['_id']]
            }, returnCount=True)
            tag['video_usage'] = count

    def __select_tags(self, n, tags):
        """
        Select randomly n tags among the one that have at least a video linked
        This function may return less than the given number of tags if there is not enough
        tags attached to at least an album and a video
        """
        logging.info("Selecting random tags")
        def build_stat_map(tags):
            max_val = 0
            for tag in tags:
                max_val += tag['video_usage']
                tag['cumulated_usage'] = max_val
            return max_val
        # select only the tags that have both video and album linked, then sort
        # by descendent usage count
        sorted_tags = sorted(
            (tag for tag in tags if tag['video_usage'] > 0),
            key=lambda tag: tag['video_usage'],
            reverse=True)
        # compute cumulated sum of number of uses of the tags
        max_val = build_stat_map(sorted_tags)
        result = []
        # now perform n times:
        # 1. select a random number between 0 and the maximum value
        # 2. check each tag successively in the filtered list.
        # 3. If the random value is lower than the tag usage, this is the one.
        #    If a tag is used 2x, another 4x, the second will be more likely to
        #    be selected.
        # 4. Pop the item from the list to avoid twice select, and lower the maximum
        #    value by the tag usage.
        for x in range(n):
            logging.debug("Pass: %d - max value: %d" % (x, max_val))
            val = random.randint(0, max_val - 1)
            logging.debug("Pass: %d - random value: %d" % (x, val))
            selected_tag = None
            selected_i = None
            for i, tag in enumerate(sorted_tags):
                if val < tag['cumulated_usage']:
                    selected_tag = tag
                    selected_i = i
                    break
            if tag is None or i is None:
                logging.error(
                    "Unable to pick a tag with max_val=%d in the list: %s"
                    % (max_val, str(sorted_tags)))
                break
            sorted_tags.pop(i)
            result.append(selected_tag)
            logging.debug("Pass: %d - selected tag with cumulated usage sum: %d"
                          % (x, selected_tag['cumulated_usage']))
            # rebuild stat map
            max_val = build_stat_map(sorted_tags)
            if len(sorted_tags) == 0:
                break
        return result

    def __select_vids(self, n, tag):
        """
        Select randomly n (or less) videos among the ones that belong to the given tag
        Less videos can be selected if there isn't enough videos for the given tag.
        """
        res = []
        vids = model.getService('video').find(criteria={
            'tags': [{'$value': tag['_id']}]
        })
        vids = [v for v in vids]
        if len(vids) <= n:
            return vids
        samples = sorted(random.sample(range(len(vids)), n))
        res = []
        for x in samples:
            res.append(vids[x])
        return res

    def display(self):
        """
        Route: GET /api/home/display
        Returns the list of videos to be displayed on the home page.
        The behavior of this function differs depending on what has been configured by the user.
        By default, it will select n tags among the most used ones. Then from each tag it will select
        randomly m videos, and returns the selected ones in an array.
        If some tags have the property 'home' set to True, only these tags will be used.
        """
        nb_vids = int(self.get_argument('nb_vids', default="1"))
        nb_tags = int(self.get_argument('nb_tags', default="5"))
        # get tags with the property home set to True
        tags = model.getService('tag').getHomeTags(returnList=True)
        if len(tags) == 0:
            # get all tags
            tags = model.getService('tag').getAll()
        selected = tags
        if len(selected) > 4:
            # count the usage of the tags
            self.__count_usage(tags)
            # select randomly 4 tags among the most used one
            selected = self.__select_tags(nb_tags, tags)
        # now for each tag in selected, select randomly 4 videos
        vids = []
        for tag in selected:
            vids += [populateMissingData(v) for v in self.__select_vids(nb_vids, tag)]

        model.getService('tag').populate(vids)

        self.write(json.dumps(vids, default=lambda obj: str(obj)))

    def get(self, resource):
        resources = {
            'display': self.display,
        }
        if resource in resources:
            return resources[resource]()
        raise HTTPError(404, 'Not Found')
