#!.env/bin/python
# -*- coding: utf8 -*-

from __future__ import unicode_literals

# Imports the Google Cloud client library
# from google.cloud import vision
# from google.cloud.vision import types
# from google.cloud.vision.feature import Feature, FeatureTypes
# from google.cloud.vision.face import LandmarkTypes

import io
import os
import sys
import json
import time
from enum import Enum

# from tools.analyzer import Serializer

def run():
	start_t = time.time()

	# Get user supplied values
	cascPath = "config\\cascades\\haarcascade_frontalface_default.xml"
	# up to 16 images per request
	imgs = [
		# "D:\\faces\\abba.png",
		# "D:\\faces\\little_mixx.jpg",
		# "D:\\faces\\sat.jpg",
		# "D:\\faces\\test01.png",
		# "D:\\faces\\test02.png",
		# "D:\\faces\\test03.png",
		"D:\\faces\\test04.png",
		# "D:\\faces\\test05.png",
		# "D:\\faces\\test06.png",
		# # "D:\\faces\\test001.jpg",
		# # "D:\\faces\\test002.jpg",
		# # "D:\\faces\\test003.jpg",
		"D:\\faces\\test1.png",
		"D:\\faces\\test2.png",
		"D:\\faces\\test3.png",
		"D:\\faces\\test4.png",
		"D:\\faces\\test5.png",
		"D:\\faces\\test6.png",
		"D:\\faces\\test7.png",
		"D:\\faces\\test8.png",
		"D:\\faces\\test9.png",
		"D:\\faces\\test10.png",
		"D:\\faces\\test11.png",
		"D:\\faces\\test12.png",
		"D:\\faces\\test13.png",
		"D:\\faces\\test14.png"
	]

	# for dirpath, dirnames, filenames in os.walk('D:\\faces\\datasets'):
	# 	for filename in filenames:
	# 		filepath = os.path.join(dirpath, filename)
	# 		imgs.append(filepath)
	# for dirpath, dirnames, filenames in os.walk('.\\data\\viceArc\\Videos'):
	# 	for filename in filenames:
	# 		if filename[-3:] in ['png', 'jpg']:
	# 			filepath = os.path.join(dirpath, filename)
	# 			imgs.append(filepath)


	print("Will process %d images." % len(imgs))
	requests = []
	for imagePath in imgs:
		print("Processing: %s" % imagePath)

		# Instantiates a client
		client = vision.ImageAnnotatorClient()

		# jsonPath = imagePath.replace('.png', '.json')
		# jsonPath = jsonPath.replace('.jpg', '.json')

		# if os.path.exists(jsonPath):
		# 	print("Metadata already gathered - skipping")
		# 	continue

		# Loads the image into memory
		with io.open(imagePath, 'rb') as image_file:
		    content = image_file.read()

		image = types.Image(content=content)

		# https://googlecloudplatform.github.io/google-cloud-python/latest/vision/gapic/v1/types.html#google.cloud.vision_v1.types.AnnotateImageRequest
		request = types.AnnotateImageRequest(image=image, features=[
			types.Feature(type=FeatureTypes.FACE_DETECTION, max_results=3),  # (int): Run face detection.
			# types.Feature(type=FeatureTypes.LANDMARK_DETECTION),  # (int): Run landmark detection.
			# types.Feature(type=FeatureTypes.LOGO_DETECTION),  # (int): Run logo detection.
			types.Feature(type=FeatureTypes.LABEL_DETECTION, max_results=10),  # (int): Run label detection.
			# types.Feature(type=FeatureTypes.TEXT_DETECTION),  # (int): Run OCR.
			# types.Feature(type=FeatureTypes.DOCUMENT_TEXT_DETECTION),  # (int): Run dense text document OCR. Takes precedence when both DOCUMENT_TEXT_DETECTION and TEXT_DETECTION are present.
			# types.Feature(type=FeatureTypes.SAFE_SEARCH_DETECTION),  # (int): Run computer vision models to compute image safe-search properties.
			# types.Feature(type=FeatureTypes.IMAGE_PROPERTIES),  # (int): Compute a set of image properties, such as the image's dominant colors.
			types.Feature(type=FeatureTypes.CROP_HINTS, max_results=5),  # (int): Run crop hints.
			types.Feature(type=FeatureTypes.WEB_DETECTION, max_results=10),  # (int): Run web detection.
		])

		requests.append(request)

	print("Submitting %d requests" % len(requests))
	# Performs label detection on the image file
	response = client.batch_annotate_images(requests=requests)
	jsonPath = 'D:\\faces\\batchResult.json'

	result = []

	for idx, resp in enumerate(response.responses):
		result.append(Serializer.responseToJSON(resp, imgs[idx]))

	print("Writing: %s" % jsonPath)
	with open(jsonPath, 'w') as f:
		f.write(json.dumps(result))

	print("Job finished in %.3fs" % (time.time() - start_t))
