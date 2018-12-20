# -*- coding: utf8 -*-

from __future__ import unicode_literals
import logging

from lib.DeepFaceLab.mainscripts.Extractor import ExtractSubprocessor
from lib.DeepFaceLab.facelib.LandmarksProcessor import landmarks_68_pt

from tools.analyzer.baseAnnotator import BaseAnnotator

BATCH_SIZE = 2000

class DFLAnnotator(BaseAnnotator):
    supportReportingProgress = True

    """
    Use Google Cloud Vision to submit image annotation for a large batch of images
    Save a cache of the result of the analysis on disk, so that we never submit
    a request for the same image twice.
    """
    def __init__(self, name, imgPaths, progress, detector):
        super(DFLAnnotator, self).__init__(name, BATCH_SIZE, imgPaths, progress)

        self.progress = progress
        self.detector = detector
        self._stopped = False
        self._currentExtractor = None

    # override
    def stop(self):
        super(DFLAnnotator, self).stop()
        self._stopped = True
        if self._currentExtractor is not None:
            self._currentExtractor.interrupt()

    def _callbackWithLandmarks(self, data, result):
        filename, faces = result
        self._progress(filename, self.serializeWithLandmarks(faces))

    def serializeWithLandmarks(self, faces):
        return {
            'faces': [{
                'boundaries': [{'x': x, 'y': y}, {'x': x2, 'y': y2}],
                'landmarks': [
                    {'x': lx, 'y': ly} for lx, ly in landmarks
                ],
                # it'd be nice to have a way to get a proper confidence value!
                'detection_confidence': confidence
            } for (x, y, x2, y2, confidence), landmarks in faces],
        }

    def _callbackRect(self, data, result):
        filename, faces = result
        self._progress(filename, self.serializeRect(faces))

    def serializeRect(self, faces):
        return {
            'faces': [{
                'boundaries': [{'x': x, 'y': y}, {'x': x2, 'y': y2}],
                'landmarks': [],
                # it'd be nice to have a way to get a proper confidence value!
                'detection_confidence': confidence
            } for (x, y, x2, y2, confidence) in faces],
        }


    # override
    def _annotateBatch(self, batch):
        if self._stopped:
            return []

        # logging.info("Performing 1st pass...")
        self._currentExtractor = ExtractSubprocessor(
            input_data=[(x,) for x in batch],
            type='rects', image_size=250, face_type='full_face',
            debug=True, multi_gpu=True, manual=False, detector=self.detector,
            callback=self._callbackRect)
        extracted_rects = self._currentExtractor.process()

        if self._stopped:
            return []

        # logging.info("Performing 2nd pass...")
        self._currentExtractor = ExtractSubprocessor(
            extracted_rects, type='landmarks', image_size=250,
            face_type='full_face', debug=True, multi_gpu=True, manual=False,
            callback=self._callbackWithLandmarks)
        result = self._currentExtractor.process()

        if self._stopped:
            return []

        return [
            self.serializeWithLandmarks(faces)
            for filename, faces in result
        ]

class MTDFLAnnotator(DFLAnnotator):
    def __init__(self, imgPaths, progress):
        super(MTDFLAnnotator, self).__init__('dfl-mt', imgPaths, progress, 'mt')

class DLIBDFLAnnotator(DFLAnnotator):
    def __init__(self, imgPaths, progress):
        super(DLIBDFLAnnotator, self).__init__('dfl-dlib', imgPaths, progress, 'dlib')
