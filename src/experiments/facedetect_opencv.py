#!.env/bin/python
# -*- coding: utf8 -*-

from __future__ import unicode_literals

import cv2
import sys
import os

def run():
	# Get user supplied values
	cascPath = "config\\cascades\\haarcascade_frontalface_default.xml"
	imgs = [
		# "D:\\faces\\abba.png",
		# # "D:\\faces\\little_mixx.jpg",
		# # "D:\\faces\\sat.jpg",
		# "D:\\faces\\test01.png",
		# "D:\\faces\\test02.png",
		# "D:\\faces\\test03.png",
		# "D:\\faces\\test04.png",
		# "D:\\faces\\test05.png",
		# "D:\\faces\\test06.png",
		# # "D:\\faces\\test001.jpg",
		# # "D:\\faces\\test002.jpg",
		# # "D:\\faces\\test003.jpg",
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
		# "D:\\faces\\test12.png"
	]

	# for dirpath, dirnames, filenames in os.walk('D:\\faces\\datasets'):
	# 	for filename in filenames:
	# 		filepath = os.path.join(dirpath, filename)
	# 		imgs.append(filepath)
	for dirpath, dirnames, filenames in os.walk('D:\\faces\\galina'):
		for filename in filenames:
			if filename[-3:] in ['png', 'jpg']:
				filepath = os.path.join(dirpath, filename)
				imgs.append(filepath)

	# Create the haar cascade
	faceCascade = cv2.CascadeClassifier(cascPath)

	print("Will process %d images." % len(imgs))
	for imagePath in imgs:
		# Read the image
		image = cv2.imread(imagePath)
		if image is None:
			print("Couldn't find: %s" % (imagePath))
			continue

		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

		# Detect faces in the image
		faces = faceCascade.detectMultiScale(
		    gray,
		    scaleFactor=1.07,
		    minNeighbors=5,
		    minSize=(30, 30),
		    flags = cv2.cv.CV_HAAR_SCALE_IMAGE
		)

		print("%s: Found %d faces!" % (imagePath, len(faces)))

		if len(faces) > 0:
			# Draw a rectangle around the faces
			for (x, y, w, h) in faces:
			    cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)

			cv2.imshow("Faces found", image)
			cv2.waitKey(0)
		# else:w
			# cv2.imshow("No Face", image)
			# cv2.waitKey(0)

