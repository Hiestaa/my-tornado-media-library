#!/usr/bin/python

# -*- coding: utf8 -*-

from __future__ import unicode_literals

from tornado.web import RequestHandler, HTTPError, authenticated

import random
import logging
import os

from conf import Conf
from server import model

class TemplatesHandler(RequestHandler):
    """Handle the requests of the root page"""
    def get(self, filename=None):
        templateRoutes = {
            'home': 'base.html',
            'videos': 'videos.html',
            'albums': 'albums.html',
            'slideshow': 'slideshow.html',
            'tags': 'tags.html',
            'compiler': 'compiler.html',
            'videoplayer': 'player.html'
        }
        fullWidth = ['albums', 'slideshow', 'home']
        if filename is None or not filename:
            model.getService('album').resetStarredAlbum()
            self.render('home.html', currentPage='home.html', fullWidth=True)
        elif filename in templateRoutes:
            if filename == 'home':
                model.getService('album').resetStarredAlbum()
            self.render(templateRoutes[filename],
                        currentPage=filename,
                        debug=Conf['state'] == 'DEBUG',
                        fullWidth=filename in fullWidth)
        elif filename.split('/')[0] in templateRoutes:
            splitted = filename.split('/')
            filename, args = splitted[0], splitted[1:]
            kwtargs = {arg.split('=')[0]: arg.split('=')[1] for arg in args if len(arg.split('=')) > 1}
            if filename == 'slideshow' and kwtargs['albumId'] == 'random':
                model.getService('album').resetRandomAlbum()
            if filename == 'slideshow' and kwtargs['albumId'] == 'starred':
                model.getService('album').resetStarredAlbum()
            self.render(
                templateRoutes[filename],
                currentPage=filename, debug=Conf['state'] == 'DEBUG',
                fullWidth=filename in fullWidth,
                **kwtargs)
        else:
            logging.error("Unable to find item %s" % filename)
            raise HTTPError(404)
