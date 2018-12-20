#!.env/bin/python
# -*- coding: utf8 -*-

from __future__ import unicode_literals

import cv2
import sys
import os

from conf import Conf
import log
from lib.DeepFaceLab.mainscripts.Extractor import ExtractSubprocessor
from lib.DeepFaceLab.facelib.LandmarksProcessor import landmarks_68_pt
from tools.analyzer.dflAnnotator import MTDFLAnnotator, DLIBDFLAnnotator

COLORS = [
    (0, 255, 0),
    (0, 0, 255),
    (255, 0, 0),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (0, 0, 0),
    (255, 255, 255)
]

log.init(3, False, filename="experiment.log", colored=False)

def debugrect(data, result):
    filename, faces = result
    if len(faces) <= 0:
        return
    image = cv2.imread(filename)

    if image is None:
        print("Couldn't find: %s" % (filename))
        return

    for fidx, face in enumerate(faces):
        (x, y, x2, y2, confidence) = face
        cv2.rectangle(image, (x, y), (x2, y2), COLORS[fidx % len(COLORS)], 1)

        cv2.imshow("Rect found", image)
        cv2.waitKey(0)

def debugface(data, result):
    filename, faces = result
    title = 'No Face' if len(faces) <= 0 else ('%d faces found' % len(faces))

    image = cv2.imread(filename)
    if image is None:
        print("Couldn't find: %s" % (filename))
        return

    for fidx, (face, landmarks) in enumerate(faces):
        (x, y, x2, y2, confidence) = face
        cv2.rectangle(image, (x, y), (x2, y2), COLORS[fidx % len(COLORS)], 1)

        for (x, y) in landmarks:
            cv2.circle(image, (x, y), 1, COLORS[fidx % len(COLORS)], 1)

        cv2.imshow(title, image)
        cv2.waitKey(0)

def debugfaceserialized(frame, data):
    faces = data['faces']
    title = 'No Face' if len(faces) <= 0 else ('%d faces found' % len(faces))
    filename = data['path']

    image = cv2.imread(filename)
    if image is None:
        print("Couldn't find: %s" % (filename))
        return

    for fidx, face in enumerate(data['faces']):
        x = face['boundaries'][0]['x']
        y = face['boundaries'][0]['y']
        x2 = face['boundaries'][1]['x']
        y2 = face['boundaries'][1]['y']
        cv2.rectangle(image, (x, y), (x2, y2), COLORS[fidx % len(COLORS)], 1)

        for landmark in face['landmarks']:
            x = landmark['x']
            y = landmark['y']

            cv2.circle(image, (x, y), 1, COLORS[fidx % len(COLORS)], 1)

        cv2.imshow(title, image)
        cv2.waitKey(0)

def run():
    # Get user supplied values
    imgs = [
        # "D:\\faces\\abba.png",
        # "D:\\faces\\little_mixx.jpg",
        # "D:\\faces\\sat.jpg",
        # "D:\\faces\\test01.png",
        # "D:\\faces\\test02.png",
        # "D:\\faces\\test03.png",
        # "D:\\faces\\test04.png",
        # "D:\\faces\\test05.png",
        # "D:\\faces\\test06.png",
        # "D:\\faces\\test001.jpg",
        # "D:\\faces\\test002.jpg",
        # "D:\\faces\\test003.jpg",
        # "D:\\faces\\test1.png",
        # "D:\\faces\\test2.png",
        # "D:\\faces\\test3.png",
        # "D:\\faces\\test4.png",
        # "D:\\faces\\test5.png",
        # "D:\\faces\\test6.png",
        # "D:\\faces\\test7.png",
        # "D:\\faces\\test8.png",
        # "D:\\faces\\test9.png",
        # "D:\\faces\\test10.png",
        # "D:\\faces\\test11.png",
        # "D:\\faces\\test12.png",
        "D:\\faces\\minivid0331.png",
        "D:\\faces\\minivid0332.png",
        "D:\\faces\\minivid0333.png",
        "D:\\faces\\minivid0334.png"
    ]
    dirs = [
        # "D:\\faces\\datasets\\dormer",
        # "D:\\faces\\datasets\\somegirl",
        # "D:\\faces\\datasets\\sasha",
        # "D:\\faces\\datasets\\face-rec.org"
    ]

    SKIP_FACTOR = 10

    count = 0
    for dirname in dirs:
        for dirpath, dirnames, filenames in os.walk(dirname):
            for filename in filenames:
                if filename[-3:] in ['png', 'jpg']:
                    count += 1
                    if SKIP_FACTOR > 0 and count % SKIP_FACTOR != 0:
                        continue
                    filepath = os.path.join(dirpath, filename)
                    imgs.append(filepath)

    print("Will process %d images." % len(imgs))

    annotator = DLIBDFLAnnotator(imgPaths=imgs, progress=debugfaceserialized)

    for ann in annotator():
        debugfaceserialized(0, ann)

    # Detect faces in the image
    # input_path_image_paths = imgs
    # extracted_rects = ExtractSubprocessor(
    #     input_data=[(x,) for x in input_path_image_paths],
    #     type='rects', image_size=25, face_type=face_type,
    #     debug=True, multi_gpu=True, manual=False, detector=detector,
    #     callback=None).process()
    # faces = ExtractSubprocessor(
    #     extracted_rects, type='landmarks', image_size=25,
    #     face_type=face_type, debug=True, multi_gpu=True, manual=False,
    #     callback=debugface).process()
