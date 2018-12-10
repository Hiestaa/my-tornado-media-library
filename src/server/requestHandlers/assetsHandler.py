# -*- coding: utf8 -*-

from __future__ import unicode_literals

from tornado.web import RequestHandler
from jsmin import jsmin
from cssmin import cssmin

import random
import logging
import os
import os.path
import io

from conf import Conf


def minifiedCleanUp():
    """
    WIll check the files in each folder of the cleanup list to remove
    minified js and css files.
    This is done each time the server is started.
    """
    _min_cleanup = Conf['server']['assets']['minifiedCleanups']

    for folder in _min_cleanup:
        logging.info("Cleaning minified files from folder: %s" % folder)
        try:
            for filename in os.listdir(folder):
                if filename.endswith(('.min.js', '.min.css')):
                    logging.debug("Removing minified file: %s" % filename)
                    os.remove(
                        (folder + filename) if folder.endswith('/')
                        else (folder + '/' + filename))
        except Exception as e:
            logging.error(
                "Unable to clean up minified files from folder %s: %s"
                % (folder, str(e)))


class AssetsHandler(RequestHandler):
    """Handle the requests of the assets items"""
    def __minify(self, filepath, extension):
        """
        Create the minified version of the given file path.
        filepath must be the entire path of the file from the root of the
        project, without its extension (eg: whatever/example.js should be
        given as 'whatever/example')
        extension must be the extension or the file without the '.'
        (eg: 'js' or 'css')
        This will create the filepath.min.extension minified version of the
        input file.
        Note: Unexpected results may occur if the extension is neither js nor
              css, or if the file does not contains js/css code.

        Returns the path of the minified file
        """
        logging.info("Minifying the file: %s.%s"
                     % ((filepath), extension))
        minifier = jsmin if extension == 'js' else cssmin
        if not os.path.isfile("%s.min.%s" % (filepath, extension)):
            with open("%s.min.%s" % (filepath, extension), 'w') \
                    as fw, open("%s.%s" % (filepath, extension)) as fr:
                fw.write(minifier(fr.read()))
        return "%s.min.%s" % (filepath, extension)

    def get(self, filename):
        """
        Will look at the Conf['server']['assetsPath']/filename folder to find the requested file
        and send it back to the client.

        If the project is not in debug state, if a requested asset is a
        javascript file (with .js extension) or a css file
        (with .css extension), it will send the corresponding filename.min.js
        or filename.min.css. If this file does not exist, it will create it.

        Note that (still not in DEBUG state), all the .min.js files found in
        the folders listed in the `AssetsHandler._min_cleanup` attributes will
        be deleted when the server restart (allowing recompile, and thus update
        of the minified version of the assets).

        Additionnal info: the module `jsmin` is used to minify js files and
        `cssmin` is used to minify css files.
        """
        # if the filename is a javacsript file (not a minified one) and the
        # corresponding minified file does not exist, create it.
        if filename.endswith('.js') and not filename.endswith('.min.js') \
                and (Conf['state'] != 'DEBUG' or
                     Conf['server']['assets']['minifyOnDebug']):
            filepath = self.__minify(Conf['server']['assetsPath'] + filename[:-3], 'js')
        # if the filename is a stylesheet (not a minified one) and the
        # corresponding minified file does not exist, create it.
        elif filename.endswith('.css') and not filename.endswith('.min.css') \
                and (Conf['state'] != 'DEBUG' or
                     Conf['server']['assets']['minifyOnDebug']):
            filepath = self.__minify(Conf['server']['assetsPath'] + filename[:-4], 'css')
        else:
            filepath = Conf['server']['assetsPath'] + filename

        if filepath.endswith('.png') or filepath.endswith('.gif') or filepath.endswith('.jpg'):
            try:
                with open(filepath, 'rb') as p:
                    buf = p.read()
                if filepath.endswith('.png'):
                    self.set_header('Content-type', 'image/png')
                if filepath.endswith('.gif'):
                    self.set_header('Content-type', 'image/gif')
                if filepath.endswith('.jpg'):
                    self.set_header('Content-type', 'image/jpeg')
                self.set_header('Content-length', len(buf))
                return self.write(buf)
            except IOError:
                logging.error("The snapshot: %s cannot be found." % filepath)
                raise HTTPError(404, 'Not Found')
        # now send the minified version of the requested file
        if filepath.endswith('.min.js'):
            logging.info("Sending Minified JS file: %s" % filepath)
            self.set_header("Content-Type", "application/js")
        elif filepath.endswith('.js'):
            logging.info("Sending NON-Minified JS file: %s" % filepath)
            self.set_header("Content-Type", "application/js")
        elif filepath.endswith('.min.css'):
            logging.info("Sending Minified CSS file: %s" % filepath)
            self.set_header("Content-Type", "text/css")
        elif filepath.endswith('.css'):
            logging.info("Sending NON-Minified CSS file: %s" % filepath)
            self.set_header("Content-Type", "text/css")
        elif filepath.endswith('.woff'):
            self.set_header('Vary', "Accept-Encoding")
            self.set_header('Accept-Ranges', "bytes")
            self.set_header('Content-Type', 'application/font-woff')
            self.set_header('Content-Length', "65452")
        elif filepath.endswith('.eot'):
            self.set_header('Content-Type', 'application/vnd.ms-fontobject')
        elif filepath.endswith('.ttf'):
            self.set_header('Content-Type', 'application/x-font-truetype')
        elif filepath.endswith('.svg'):
            self.set_header('Content-Type', 'image/svg+xml')
        elif filepath.endswith('.otf'):
            self.set_header('Content-Type', 'application/x-font-opentype')
        else:
            logging.info("Sending file: %s" % filepath)
        if filepath.endswith('.woff') or filepath.endswith('.eot') or \
                filepath.endswith('.ttf') or filepath.endswith('.svg') or \
                filepath.endswith('.otf'):
            with open(filepath, 'rb') as f:
                self.write(f.read())
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.write(f.read())
