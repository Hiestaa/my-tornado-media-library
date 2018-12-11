# -*- coding: utf8 -*-
from __future__ import unicode_literals

from pprint import pformat
import logging
import time
from bson.objectid import ObjectId
from pymongo import DESCENDING, ASCENDING
from bson.son import SON

from server.services.baseService import Service
from conf import Conf
from tools.utils import extends, dateFormat

"""
Schema:
    * _id:string id of the video
    * filename:string actual name of the file as saved on drive
    * path:string path to the video, not including the defined videos root
    * name:string display name for this video
    * description:string some text, thoughts or notes about this video
    * display:int number of times this video has been shown to the client
    * seen:int number of times this video has been downloaded, played or marked as 'seen' by the user
    * favorite:int number of times this video has been marked as favorite
    * toWatch:boolean True if the video has recently been marked as 'to watch'. Set to false each time
                      the video is marked as 'seen'
    * tags:array<_id>: list of tags attached to this video
    * snapshotsFolder:string folder where to find the images thumbXXX.png that allow
                             a snapshot visualization of the video.
                             WARNING: The path does not include  the video root prefix.
    * nbSnapshots:int number of snapshots for this video
    * thumbnail:string index of the snapshot that should be used as thumbnail.
                       if not set, a random snapshot will be used instead.
                       This thumbnail is expected to be found in the snapshot folder of the video
    * duration:int duration of the video in seconds
    * fileSize:int size of the video file, in bytes
    * width: width of the video
    * height: height of the video
    * fps:int number of frames per seconds for this video
    * creation:float timestamp of the creation of the video
    * lastTagged:float timestamp of the last time this video has been tagged
    * tagHistory:array<float> timestamps of the times this video has been tagged
    * lastDisplay:float timestamp of the last time this video has been displayed
    * displayHistory:array<float> timestamps of the times this video has been displayed
    * lastSeen:float timestamp of the last time this video has been downloaded or
                     marked as 'seen' by the user.
    * seenHistory:array<float> timestamps of the times this video has been seen
    * lastFavorite:float timestamp of the last time this video has been marked favorite
    * favoriteHistory:array<float> list of timestamp recording the times the video is marked as 'favorite'
    * lastToWatch:float timestamp of the last time this video has been marked as 'to see'
    * toWatchHistory:array<float> list of timestamp recording the times a video is marked as 'to see'
    * analysis:dict automated video frames analysis results if performed. Structure:
                    `{gcv: {raw: [<gcv response for each frame],
                            pp: [<gcv response post-processed],
                            aggreg: {<aggregation of all frames' analyzis into a single object}}}`
"""


class VideoService(Service):
    """
    Provides helper functions related to the videos collection
    of the database.
    """
    def __init__(self, db):
        super(VideoService, self).__init__(db, 'videos')
        self._collection.ensure_index(
            [('path', DESCENDING)],
            name="video_path_uq_idx", unique=True)

    def schema(self):
        return {
            'filename': True,
            'path': True,
            'name': True,
            'description': True,
            'display': True,
            'seen': True,
            'favorite': True,
            'toWatch': True,
            'tags': True,
            'snapshotsFolder': True,
            'nbSnapshots': True,
            'thumbnail': True,
            'duration': True,
            'fileSize': True,
            'width': True,
            'height': True,
            'fps': True,
            'creation': True,
            'taggedHistory': False,
            'lastTagged': True,
            'displayHistory': False,
            'lastDisplay': True,
            'seenHistory': False,
            'lastSeen': True,
            'favoriteHistory': False,
            'lastFavorite': True,
            'toWatchHistory': False,
            'lastToWatch': True,
            'analysis': False
        }

    def insert(self, filename, path, name=None, description='',
               snapshotsFolder=None, display=0, seen=0, favorite=0, toWatch=False,
               duration=0, resolution=(0, 0), fps=0, creation=None,
               lastDisplay=0, lastSeen=0, lastFavorite=0, lastToWatch=0,
               thumbnail=None, tags=None, _id=None, nbSnapshots=0, fileSize=0,
               lastTagged=0, taggedHistory=None, displayHistory=None, seenHistory=None,
               favoriteHistory=None, toWatchHistory=None):
        """
        Insert a new document and returns its id
        """
        logging.debug("Saving new video: %s" % filename)
        if name is None:
            name = filename
        if snapshotsFolder is None:
            snapshotsFolder = '.'.join(path.split('.')[:-1])
        if Conf['data']['videos']['rootFolder'] in path:
            path = path[len(Conf['data']['videos']['rootFolder']):]
        if Conf['data']['videos']['rootFolder'] in snapshotsFolder:
            snapshotsFolder = snapshotsFolder[len(Conf['data']['videos']['rootFolder']):]
        post = self.schema()
        post['filename'] = filename
        post['path'] = path
        post['name'] = name
        post['description'] = description
        post['display'] = display
        post['seen'] = seen
        post['favorite'] = favorite
        post['tags'] = tags or []
        post['duration'] = duration
        post['width'] = resolution[0]
        post['height'] = resolution[1]
        post['fps'] = fps
        post['creation'] = creation or time.time()
        post['lastDisplay'] = lastDisplay
        post['lastSeen'] = lastSeen
        post['lastFavorite'] = lastFavorite
        post['lastToWatch'] = lastToWatch
        post['lastTagged'] = lastTagged
        post['taggedHistory'] = taggedHistory or []
        post['displayHistory'] = displayHistory or []
        post['seenHistory'] = seenHistory or []
        post['favoriteHistory'] = favoriteHistory or []
        post['toWatchHistory'] = toWatchHistory or []
        post['toWatch'] = toWatch
        post['snapshotsFolder'] = snapshotsFolder
        post['nbSnapshots'] = nbSnapshots
        post['thumbnail'] = thumbnail
        post['fileSize'] = fileSize
        post['analysis'] = {}
        if _id is not None:
            post['_id'] = ObjectId(_id)
        _id = self._collection.insert(self.validate(post))
        return str(_id)

    def increment(self, _id, field, val=1):
        """
        If _id is a list, it will be used as a list of video ids
        """
        logging.debug("Incrementing field: %s" % field)
        select = {}
        if isinstance(_id, list):
            select['_id'] = {'$in': [ObjectId(i) for i in _id]}
        else:
            select = {'_id': ObjectId(_id)}
        corresp_ts_record = {
            'seen': 'lastSeen',
            'display': 'lastDisplay',
            'favorite': 'lastFavorite',
            'toWatch': 'lastToWatch'
        }
        corresp_history_record = {
            'seen': 'seenHistory',
            'display': 'displayHistory',
            'favorite': 'favoriteHistory',
            'toWatch': 'toWatchHistory'
        }
        update = {
            '$inc': self.validate({field: val}, strict=False)
        }
        t = time.time()
        if field in corresp_ts_record:
            update['$set'] = {corresp_ts_record[field]: t}
        if field in corresp_history_record:
            update['$push'] = {corresp_history_record[field]: t}
        if field == 'seen':
            update['$set'] = update.get('$set', {})
            update['$set']['toWatch'] = False

        self._collection.update(select, update, multi=True)

    def set(self, _id, field, value):
        print('videoService.set(', _id, field, value)
        if field == 'thumbnail' and not isinstance(value, int):
            logging.error("Video %s's thumbnail has been set to a non-integer value!" % (value))

        # seen, display and favorite are set via increment
        # when they are set via `set`, this is a user-corrected value
        # and we do not wish to save the change in history
        corresp_ts_record = {
            'toWatch': 'lastToWatch'
        }
        corresp_history_record = {
            'toWatch': 'toWatchHistory'
        }

        t = time.time()
        update = {}
        if field in corresp_ts_record:
            update['$set'] = {corresp_ts_record[field]: t}
        if field in corresp_history_record:
            update['$push'] = {corresp_history_record[field]: t}

        super(VideoService, self).set(_id, field, value, update)

    def addTag(self, _id, tagId):
        logging.debug("Pushing tag %s to video %s" % (tagId, _id))
        q = {'_id': ObjectId(_id)}
        t = time.time()
        self._collection.update(q, {
            '$addToSet': {'tags': tagId},
            '$set': {'lastTagged': t},
            '$push': {'taggedHistory': t}
        })

    def removeTag(self, tagId, videoId=None):
        if videoId is not None:
            self._collection.update(
                {'_id': ObjectId(videoId)},
                {'$pull': {'tags': tagId}})
        else:
            self._collection.update(
                {'tags': {'$in': [tagId]}},
                {'$pull': {'tags': tagId}},
                multi=True)

    def getByPath(self, path):
        if Conf['data']['videos']['rootFolder'] in path:
            path = path[len(Conf['data']['videos']['rootFolder']):]
        return self._collection.find_one({'path': path})

    def find(self, criteria, page=0, item_per_page=0, generator=True, returnCount=False, analyzed_only=False):
        """
        Retrieve videos from database, given the defined criteria.
        If more than a defined number of items per page exist, the page
        parameter can be specified to ask for the nth group of videos.
        Criteria is expected to be an dict with the following structure: {
            'type': <'any'|'all'>
            'video': [  # filters related to the video itself.
                {'$comparator': <'='|'<'|'>'>, $negated: True|False, <field>:<value>}, ...
            ]
            'tags': [   # tag filtering
                {$negated: True|False, $value: <tag_id>}, ...
            ],
            sort: [[field, 1 | -1]]
        }
        The 'type' field allow to ask for all specified criteria to be present, or
        to ask for any of the specified criteria to be present.
        The 'video' list contains filters related to the fields of the video object,
        and the 'tags' list contains filters related to the tags attached to the video.
        The 'video' filters are dicts where keys are video property names, and value
        is the expected value. The special '$comparator' key can be used if the value
        is an integer.
        The 'tags' filters are simple tag ids
        The 'sort' field is an array with the structure [field, order]. Default is `['creation': -1]`
        The generator parameter allow to ask for a generator or a fully generated list.
        It count is set to true, the returned item is in a tuple along with the total number of
        items matching this criteria.
        If analyzed_only is set to true, only analyzer videos will be returned.
        """
        logging.debug("Building mongo criteria from criteria: %s" % pformat(criteria))

        # apply default values to the criteria
        criteria = extends(criteria, type='any', video=[], tags=[], sort=[])
        if len(criteria['sort']) == 0 or criteria['sort'][0][0] != 'lastSeen':
            criteria['sort'].append(['lastSeen', ASCENDING])

        mongo_criteria = []
        # video filter
        for filtre in criteria['video']:
            mongo_filtre = {}
            # default comparator is '='
            if not '$comparator' in filtre:
                filtre['$comparator'] = '='
            if not '$negated' in filtre:
                filtre['$negated'] = False
            # populare the mongoDB filter with given criteria filters
            for key, val in filtre.items():
                # ignore '$comparator' key
                if key == '$comparator' or key == '$negated':
                    continue
                # 'name' key will be a regexp, where spaces are any number of characters
                if key == 'name':
                    mongo_filtre[key] = {'$regex': '.*' + '.*'.join(val.split(' ')) + '.*', '$options': 'is'}
                    if filtre['$negated']:
                        mongo_filtre[key] = {'$not': mongo_filtre[key]}
                    continue

                # convert our comparator to mongoDB comparison system
                if filtre['$comparator'] == '>':
                    mongo_filtre[key] = {'$gte': val}
                elif filtre['$comparator'] == '<':
                    mongo_filtre[key] = {'$lte': val}
                elif filtre['$negated']:  # and neither '<' nor '>'
                    mongo_filtre[key] = {'$ne': val}
                else:
                    mongo_filtre[key] = val

                if filtre['$negated'] and (filtre['$comparator'] == '>' or filtre['$comparator'] == '<'):
                    mongo_filtre[key] = {'$not': mongo_filtre[key]}

            # add the mongo filter to the mongo criteria
            mongo_criteria.append(mongo_filtre)

        # populate mongodb criteria with tags filters
        # if criteria['type'] == 'all' and len(criteria['tags']) > 0:
        #     mongo_criteria.append({'tags': {'$all': criteria['tags']}})
        # elif criteria['type'] == 'any' and len(criteria['tags']) > 0:
        for filtre in criteria['tags']:
            tagId = filtre['$value']
            if filtre.get('$negated', False):
                mongo_criteria.append({'tags': {'$ne': tagId}})
            else:
                mongo_criteria.append({'tags': tagId})

        # avoid error when noting is specified
        if len(mongo_criteria) == 0:
            mongo_criteria = {}
        # 'all' will AND all the filters, 'any' will 'OR' all the filters
        elif criteria['type'] == 'all':
            mongo_criteria = {'$and': mongo_criteria}
        elif criteria['type'] == 'any':
            mongo_criteria = {'$or': mongo_criteria}
        else:
            logging.error("Unrecognized criteria type: %s" % criteria['type'])

        logging.debug("Performing search criteria: \n%s" % pformat(mongo_criteria))
        mongo_criteria['$comment'] = "Built from: %s" % pformat(criteria)

        foundId = False
        for sort in criteria['sort']:
            sort[1] = int(sort[1])
            if sort[0] == '_id':
                foundId = True

        if not foundId:
            criteria['sort'].append(['_id', -1])

        aggreg = [
            {'$match': mongo_criteria}
        ]
        if analyzed_only:
            aggreg.append({'$match': {'analysis.faceTime': {'$gt': 0}}})

        aggreg.append({
            # note here: all the fields have to be specified...
            '$project':extends(
                {field: True for field, val in self.schema().items()},
                nbTags={'$size': '$tags'},
                faceRatio='$analysis.averageFaceRatio',
                faceTime='$analysis.faceTime',
                faceTimeProp='$analysis.faceTimeProp',
                # todo: devide by the number of days since the last time the video has been seen
                popularity={'$add': [
                    {'$divide': ['$display', 10]},
                    {'$multiply': ['$favorite', 3]},
                    '$seen'
                ]}
            )
        })
        aggreg.append({
            '$sort': SON(criteria['sort'])
        })

        if page > 0:
            aggreg.append({'$skip': page * item_per_page})
        if item_per_page > 0:
            aggreg.append({'$limit': item_per_page})
        cursor = self._collection.aggregate(aggreg, cursor={})

        # manage the generator parameter
        if generator:
            ret = cursor
        else:
            ret = [itm for itm in cursor]

        # manage the `returnCount` parameter
        if returnCount:
            count = self._collection.aggregate([
                {'$match': mongo_criteria},
                {'$group': {'_id': None, 'count': {'$sum': 1}}}
            ])
            try:
                count = next(count)['count']
            except StopIteration:
                count = 0
            return ret, count
        return ret
