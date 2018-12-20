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
from threading import Thread
import subprocess

from tornado.web import RequestHandler, HTTPError

from server import model, memory
from conf import Conf
from tools.utils import timeFormat, sizeFormat, dateFormat


def populateMissingData(video):
        """
        Will populate the `snapshots` field of the given video dict
        with valid URLs.
        The `thumbnail` field will also be populated with the url of
        a thumbnail, selecting randomly one of the snapshots if necessary.
        """
        # compute base snapshot url for this video.
        snapshotsBaseURL = '/download/snapshot/'
        # ensure trailing slash
        if snapshotsBaseURL[-1] != '/':
            snapshotsBaseURL += '/'
        # add video id o complain to the route format defined in the server class
        snapshotsBaseURL += "%s/" % str(video['_id'])
        # for each file in the snapshots folder
        video['snapshots'] = {
            i: snapshotsBaseURL + str(i)
            for i in range(int(video['nbSnapshots']))
        }

        # The realThumbnail field contains the thumbnail set to None
        # even after having selected a snapshot randomly.
        # This is used in the player view to let the user select the
        # thumbnail among snapshts (or let the app select it randomly)
        video['realThumbnail'] = video['thumbnail']
        if video['thumbnail'] is None and len(video['snapshots']) > 0:
            video['thumbnail'] = random.randint(
                0, len(video['snapshots']) - 1);

        video['url'] = '/download/video/' + str(video['_id'])

        video['duration_str'] = timeFormat(video['duration'])
        video['fileSize_str'] = sizeFormat(video['fileSize'])
        for field in ['creation', 'lastDisplay', 'lastSeen', 'lastFavorite', 'lastTagged', 'lastToWatch']:
            video["%s_str" % field] = dateFormat(video.get(field, 0))

        for field in ['displayHistory', 'favoriteHistory', 'seenHistory', 'taggedHistory']:
            video["%s_str" % field] = []
            if field not in video:
                video[field] = []
            for item in video[field]:
                video["%s_str" % field].append(dateFormat(item))

        video['snapshotsFolder'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['snapshotsFolder'])
        video['path'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['path'])

        return video

class VidsHandler(RequestHandler):
    """Handle requests related to the videos"""
    def __populateMissingData(self, video):
        """
        Will populate the `snapshots` field of the given video dict
        with valid URLs.
        The `thumbnail` field will also be populated with the url of
        a thumbnail, selecting randomly one of the snapshots if necessary.
        """
        return populateMissingData(video)

    def openFolder(self):
        """
        Route: GET /api/video/folder
        Open the containing folder in windows explorer
        This require the parameter `videoId` to be defined.
        The function returns nothing.
        """
        vidId = self.get_argument('videoId')
        video = model.getService('video').getById(vidId, fields=['path'])

        video['path'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['path'])

        # increment 'seen' counter
        model.getService('video').increment(vidId, 'seen')

        subprocess.Popen(r'explorer /select,"%s"' % video['path'])

    def getRelated(self):
        """
        Route: GET /api/video/related
        Will randomly select N videos related to the given video.
        The more tags has each video in common with the given one,
        the more chance a they will have to be selected.
        Requires the `videoId` parameter to be defined
        `nbRelated` can be defined as well to set the (max) number of video
        should be returned. Default is five.
        """
        videoId = self.get_argument('videoId')
        nbRelated = int(self.get_argument('nbRelated', default=5))
        video = model.getService('video').getById(videoId)
        logging.debug("Getting %d videos related to: %s" % (nbRelated, pformat(video)))

        relationTags = {t['_id']: t for t in model.getService('tag').getRelationTags()}

        candidates = model.getService('video').find({
            'type': 'any',
            'video': [],
            'tags': [{'$value': t, '$negated': False} for t in video['tags'] if t in relationTags]
        }, generator=False)

        logging.debug("Found %d candidates! Selecting the most related ones." % len(candidates))
        # compute the score for each video
        for cid, vid in enumerate(candidates):
            # ignore current video (score stay at 0)
            if str(vid['_id']) == video['_id']:
                vid['relatedByScore'] = -1
                continue
            vid['relatedByScore'] = 0
            for tag in vid['tags']:
                if tag in video['tags'] and tag in relationTags:
                    vid['relatedByScore'] += 1

        # sort by descendant score
        candidates = sorted(candidates, key=lambda v: v['relatedByScore'], reverse=True)
        # select the top N, or all candidates except the last one, as this is the current video
        selected = range(min(nbRelated, len(candidates) - 1))

        # populate snapshots
        logging.debug("Populating snapshots of video: %s" % pformat(selected))
        selected = [self.__populateMissingData(
            candidates[x]) for x in selected if candidates[x]['_id'] != video['_id']]
        # get full tags involvet in the relation
        tags = {t['_id']: t for _, t in relationTags.items() if t['_id'] in video['tags']}

        # add a field to each video to display the relation with the input video
        # the intersection into the sets of tags attached to each video is the common tag ids
        for v in selected:
            v['relatedBy'] = [tags[tid] for tid in
                            set(video['tags']) & set(v['tags']) if tid in tags]

        # add tags to video
        model.getService('tag').populate(selected)

        self.write(json.dumps(selected, default=lambda obj: str(obj)))

    def getSingleVid(self):
        """
        Route: GET /api/video/display
        Will write back to the client a JSON object containing information
        related to a single video.
        This require the body parameter `videoId` defined.
        """
        videoId = self.get_argument('videoId')
        video = model.getService('video').getById(videoId)
        video = self.__populateMissingData(video)

        # update 'display' counter
        model.getService('video').increment(video['_id'], 'display')
        model.getService('tag').populate([video])

        self.write(json.dumps(video))

    def getByCrit(self):
        """
        Route: GET /api/video/filter
        This will use the given criteria and the requested page to
        retrieve X videos object and write them back to the client
        The number of videos can be configured by the
        Conf['data']['videos']['displayPerPage'] configuration value
        The criteria should follow the structure defined in the
        VideoService.find class method.
        This requires the parameter `criteria` to be defined.
        The `page` parameter can be defined as well, 0 will be used by default
        """
        try:
            criteria = json.loads(self.get_argument('criteria', default='{}'))
        except:
            logging.error("Unable to decode json object: %s" % self.get_argument('criteria', default='{}'))
            criteria = {}
        page = int(self.get_argument('page', default=0))
        perpage = Conf['data']['videos']['displayPerPage'];
        logging.debug("Getting page %d by crit: %s" % (page, str(criteria)))

        videos, count = model.getService('video').find(criteria, page, perpage, returnCount=True)
        videos = [self.__populateMissingData(vid) for vid in videos]

        # update 'display' counter
        model.getService('video').increment([v['_id'] for v in videos], 'display')

        model.getService('tag').populate(videos)

        self.write(json.dumps({
            'videos': videos,
            'page': page,
            'count': count
        }, default=lambda obj: str(obj)))

    def tag(self):
        """
        Route: POST /api/video/tag
        This will add or remove a tag to/from a video.
        This require the `tagId` and the `videoId` parameters to be defined
        To remove the tag instead of adding it, provide a `remove` parameter
        set to True.
        """
        tagId = self.get_argument('tagId')
        videoId = self.get_argument('videoId')
        remove = self.get_argument('remove', default=False)

        if remove:
            model.getService('video').removeTag(tagId, videoId=videoId)
        else:
            model.getService('video').addTag(videoId, tagId)

        self.write(json.dumps({"success": True}))

    def update(self):
        """
        Route: POST /api/video/update
        This will update one of the fields of the video object with the
        given value.
        This require the parameters `videoId`, `field` and `value` to be
        defined
        Note: to send a null/None value, send the string 'null' which will be
        converted to the None value.
        """
        videoId = self.get_argument('videoId')
        field = self.get_argument('field')
        value = self.get_argument('value')

        if value == 'null':
            value = None
        elif value == 'false':
            value = False
        elif value == 'true':
            value = True
        else:
            try:
                value = int(value)
            except:
                pass

        if field == 'thumbnail' and not isinstance(value, int):
            logging.error("Video %s's thumbnail has been set to a non-integer value!" % (value))

        model.getService('video').set(videoId, field, value)

        self.write(json.dumps({"success": True}))

    def increment(self):
        """
        Route: POST /api/video/increment
        This will increment one of the incrementable field of the video.
        WARNING: undefined behaviour if the requested field is not an integer.
        This requires the parametrs `videoId` and `field` to be defined
        """
        videoId = self.get_argument('videoId')
        field = self.get_argument('field')

        model.getService('video').increment(videoId, field)

        self.write(json.dumps({"success": True}))

    def toWatch(self):
        """
        Route: POST /api/video/towatch
        This will mark the given video as to be watched.
        Requires the parameter `videoId` to be defined.
        """
        model.getService('video').set(self.get_argument('videoId'), 'toWatch', True)

    def play(self):
        """
        Route: GET /api/video/play
        Use VLC to play the video
        This requires the parameter `videoId` to be defined.
        """
        def asyncPlay(videoPath):
            videoPath = videoPath.replace('/', os.path.sep)
            videoPath = videoPath.replace('\\', os.path.sep)
            if (Conf['server']['playVideosVLC']):
                subprocess.call(
                    '%s "%s"'
                    % (Conf['server']['vlcPath'], videoPath));
            else:
                try:
                    os.startfile(videoPath)
                except:
                    logging.error("Unable to open file: %s, \
try to enable the `playVideosVLC` option and fill in the VLC binary path to fix this issue."
% videoPath)

        # get the path for this video.
        videoId = self.get_argument('videoId')
        video = model.getService('video').getById(videoId, ['path', 'name'])
        video['path'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['path'])

        # check that the file exist
        try:
            with open(video['path'], 'r') as f:
                logging.debug("The video %s does exist!" % video['path']);
        except IOError:
            logging.error("The video: %s cannot be found." % video['path'])
            raise HTTPError(404, 'Not Found')
        # increment 'seen' counter
        model.getService('video').increment(videoId, 'seen')
        # perform asynchronous playing of the video
        Thread(target=asyncPlay, name="Player-%s" % video['name'], args=[video['path']]).start()
        self.write(json.dumps({'success': True}))

    def removeThumbnail(self):
        """
        Route: POST /api/video/thumbnail/remove
        Remove the given thumbnail of the video
        Requires the parameter `position` to be defined. An exception is raised if
        the given thumbnail does not exist. The parameter `videoId` must be defined as well.
        Writes back the video object to the client.
        `position` is in base 0
        """
        videoId = self.get_argument('videoId')
        pos = int(self.get_argument('position')) + 1  #base 0 to base1
        logging.info("Removing thumbnail: %d" % pos)
        video = model.getService('video').getById(videoId, fields=['snapshotsFolder', 'nbSnapshots', 'thumbnail'])
        video['snapshotsFolder'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['snapshotsFolder'])
        os.remove(os.path.join(video['snapshotsFolder'], 'thumb%03d.png' % (pos)))
        logging.info("Renaming each snapshot from %d to %d" % (pos + 1, video['nbSnapshots']))
        for x in range(pos + 1, video['nbSnapshots'] + 1):  #base 0 to base1
            oldName = os.path.join(video['snapshotsFolder'], 'thumb%03d.png' % x)
            newName = os.path.join(video['snapshotsFolder'], 'thumb%03d.png' % (x - 1))
            logging.info("Renaming from '" + oldName + '" to "' + newName + '"')
            os.rename(oldName, newName)
        model.getService('video').increment(videoId, 'nbSnapshots', -1)
        if video['thumbnail'] is not None and pos <= video['thumbnail']:
            model.getService('video').increment(videoId, 'thumbnail', -1)
        self.write(json.dumps(
            populateMissingData(
                model.getService('video').getById(videoId)),
            default=lambda obj: str(obj)))

    def regenerateThumbnail(self):
        """
        Route: POST /api/video/thumbnails/regenerate
        Regenerate the thumbnail.
        The generation will be performed on a separate thread.
        If a generation is already in progress, the request will raise an error
        (even for a different video, only one re-generation is allowed)
        To get the progress of the generation, checkout the `generationProgress` function.
        The parameter `videoId` is required, and the parameters `frameRate`, `width` and `height`
        can be defined.
        WARNING: `frameRate` is expected to have the format: 'X/Y' where X is the number of frame to generate
        and Y is a time period (e.g.: `"1/60"` generate 1 frame every 60s)
        """
        existing_worker = memory.getVal('thumbnail-generator')
        if existing_worker is not None and existing_worker.isAlive():
            video = model.getService('video').getById(existing_worker.name, fields=['name'])
            raise Exception("A generation is still in progress for video: %s" % video['name'])

        videoId = self.get_argument('videoId')
        video = model.getService('video').getById(videoId)
        video['path'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['path'])
        video['snapshotsFolder'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['snapshotsFolder'])

        data = {
            'frameRate': self.get_argument('frameRate', default=Conf['data']['ffmpeg']['frameRate']),
            'width': self.get_argument('width', default=Conf['data']['ffmpeg']['snapshotDimensions'][0]),
            'height': self.get_argument('height', default=Conf['data']['ffmpeg']['snapshotDimensions'][1]),
            'ffmpegPath': Conf['data']['ffmpeg']['exePath'],
            'videoPath': video['path'],
            'snapFolder': video['snapshotsFolder']
        }

        logging.info("Re-generating snapshots for video: %s" % video['name'])
        logging.info("FrameRate=%s, Width=%s, height: %s"
                     % (data['frameRate'], data['width'], data['height']))

        try:
            shutil.rmtree(video['snapshotsFolder'])
        except:
            logging.warning("Unable to remove thumbnails folder: %s. \
Attempting to generate thumbnails anyways..." % video['snapshotsFolder'])
        try:
            os.makedirs(video['snapshotsFolder'])
        except:
            logging.warning("Unable to create thumbnails folder: %s. \
Attempting to generate thumbnails anyways..." % video['snapshotsFolder'])

        model.getService('video').set(videoId, 'nbSnapshots', 0)
        video['nbSnapshots'] = 0

        def asyncThumbGen(data):
            logging.warning("Starting Thumbnail re-generation!")
            start_t = time.time()
            return_code = subprocess.call(
                '{ffmpegPath} -i "{videoPath}" -f image2 -vf fps=fps={frameRate} -s {width}x{height} "{snapFolder}\\thumb%03d.png"'.format(**data),
                shell= True)
            logging.warning("Thumbnails re-generation complete! Done in %.3fs." % (time.time() - start_t))
            try:
                thumbnails = os.listdir(video['snapshotsFolder'])
            except Exception as e:
                logging.warning("Couldn't read thumbnails in folder: %s" % (video['snapshotsFolder']))
                thumbnails = []
            model.getService('video').set(videoId, 'nbSnapshots', len(thumbnails))

        worker = Thread(target=asyncThumbGen, name=videoId, args=[data])
        worker.start()

        memory.setVal('thumbnail-generator', worker)

        self.write(json.dumps(populateMissingData(video)))

    def generationProgress(self):
        """
        Route: GET /api/video/thumbnails/generationProgress
        Get the progression of the generation of the thumbnail.
        If no generation is in progress for the given video, an error will be raised.
        Returns the video object, along with one field `generationFinished` set to True
        or false depending on the state.
        """
        worker = memory.getVal('thumbnail-generator')
        videoId = self.get_argument('videoId')
        if worker is None or worker.name != videoId:
            raise Exception("Generation hasn't been started yet.")

        video = model.getService('video').getById(videoId)
        video['snapshotsFolder'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['snapshotsFolder'])

        video['generationFinished'] = not worker.isAlive()
        thumbnails = os.listdir(video['snapshotsFolder'])
        model.getService('video').set(videoId, 'nbSnapshots', len(thumbnails))

        video['nbSnapshots'] = len(thumbnails)

        self.write(json.dumps(populateMissingData(video)))

    def migrate(self):
        # videos = model.getService('video').getAll()
        # toRemove = 'C:\\wamp\\www\\Vice\\webroot\\archives\\'
        # for vid in videos:
        #     logging.info("Migrating: %s" % vid['filename'])
        #     if vid['snapshotsFolder'].startswith(toRemove):
        #         model.getService('video').set(
        #             vid['_id'],
        #             'snapshotsFolder', vid['snapshotsFolder'][len(toRemove):])
        #     if vid['path'].startswith(toRemove):
        #         model.getService('video').set(
        #             vid['_id'],
        #             'path', vid['path'][len(toRemove):])
        self.write("KO")

    def get(self, resource):
        """
        This will handle the GET requests to the /api/video/* route
        """
        avail_resources = {
            'display': self.getSingleVid,
            'filter': self.getByCrit,
            'related': self.getRelated,
            'play': self.play,
            'thumbnails/generationProgress': self.generationProgress,
            'folder': self.openFolder,
            'migrate': self.migrate,
        }
        if resource in avail_resources:
            return avail_resources[resource]()
        raise HTTPError(404, "Not Found: %s" % resource)

    def post(self, resource):
        """
        This will handle the POST requests to the /api/video/* route
        """
        avail_resources = {
            'tag': self.tag,
            'update': self.update,
            'increment': self.increment,
            'thumbnails/regenerate': self.regenerateThumbnail,
            'thumbnails/remove': self.removeThumbnail
        }
        if resource in avail_resources:
            return avail_resources[resource]()
        raise HTTPError(404, "Not Found: %s" % resource)

    def delete(self, videoId):
        """
        Route: DELETE /api/video/<videoId>
        Remove any file related to the given video ID.
        This include the video itself, the snapshots of this video and the db record.
        """
        video = model.getService('video').getById(videoId)
        video['snapshotsFolder'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['snapshotsFolder'])
        video['path'] = '%s%s' % (
            Conf['data']['videos']['rootFolder'],
            video['path'])

        if video is None:
            raise HTTPError(404, "Not Found: %s" % videoId)

        try:
            shutil.rmtree(video['snapshotsFolder'])
        except:
            pass

        os.remove(video['path'])

        model.getService('video').deleteById(videoId)

        self.write(json.dumps({'success': True}))
