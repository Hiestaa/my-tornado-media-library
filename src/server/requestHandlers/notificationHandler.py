# -*- coding: utf8 -*-

from __future__ import unicode_literals

import logging
import json

from tornado.web import RequestHandler, HTTPError

from server import model, memory
from conf import Conf
from tools.utils import timeFormat

class NotificationHandler(RequestHandler):
    """
    Handle requests related to the notification from the client to the server
    """
    def addFilter(self):
        """
        Route: PUT /api/notify/filter
        Notify the server that the client added a new tag.
        The following parameters are required:
        * type: the type ('video', 'tag', or 'photo') of the filter
        * name: a name for this filter
        * value: a value for this filter
        * filteruid: a unique identifier for this filter, used for remove notification
        """
        filterType = self.get_argument('type')
        name = self.get_argument('name')
        value = self.get_argument('value')
        filteruid = self.get_argument('uid')

        val = memory.getVal('current-filter-%s' % filterType)
        if val is None:
            val = {}
            memory.setVal('current-filter-%s' % filterType, {})

        val[filteruid] = {'type': filterType, 'name': name, 'value': value}

        self.write(json.dumps({}))

    def setData(self):
        """
        Route PUT /api/notify/data
        Save some data in memory
        The following parameters are required:
        * name
        * value
        """
        name = self.get_argument('name')
        value = self.get_argument('value')

        logging.info("Setting %s to %s" % (name, value))

        try:
            value = json.loads(value)
        except:
            pass


        data = memory.getVal('user-data')
        if data is None:
            data = {}
            memory.setVal('user-data', data)

        data[name] = value

        self.write(json.dumps({}))

    def getData(self):
        """
        Route GET /api/notify/data
        Retrieve some saved data
        * name
        """
        name = self.get_argument('name')

        data = memory.getVal('user-data')

        logging.info("Getting %s (%s)" % (name, data))

        if data is not None and name in data:
            self.write(json.dumps({'result': data[name]}))
        else:
            self.write(json.dumps({'result': None}))

    def getStoredFilter(self):
        """
        Route: GET /api/notify/filter
        Get the stored filters as an object {
            <type>: {
                <uid>: {<type>, <name>, <value>}
            }
        }
        Requires the `type` parameter to be set
        """
        res = {}
        for filterType in ['tag', 'video', 'photo']:
            val = memory.getVal('current-filter-%s' % filterType)

            if val is None:
                val = {}
                memory.setVal('current-filter-%s' % filterType, {})

            res[filterType] = val
        self.write(json.dumps(res))

    def deleteStoredFilter(self):
        """
        Route: DELETE /api/notify/filter
        Delete a filter, giving its `filteruid`
        """
        filterType = self.get_argument('type')
        filteruid = self.get_argument('uid')

        val = memory.getVal('current-filter-%s' % filterType)
        if val is None:
            val = {}
            memory.setVal('current-filter-%s' % filterType, {})

        if filteruid in val:
            del val[filteruid]

        self.write(json.dumps({}))

    def put(self, resource):
        """
        This will handle the PUT requests to the /api/notify/* route
        """
        avail_resources = {
            'filter': self.addFilter,
            'data': self.setData
        }
        if resource in avail_resources:
            return avail_resources[resource]()
        raise HTTPError(404, "Not Found: %s" % resource)


    def get(self, resource):
        """
        This will handle the GET requests to the /api/notify/* route
        """
        avail_resources = {
            'filter': self.getStoredFilter,
            'data': self.getData
        }
        if resource in avail_resources:
            return avail_resources[resource]()
        raise HTTPError(404, "Not Found: %s" % resource)


    def delete(self, resource):
        """
        """
        avail_resources = {
            'filter': self.deleteStoredFilter
        }
        if resource in avail_resources:
            return avail_resources[resource]()
        raise HTTPError(404, "Not Found: %s" % resource)

