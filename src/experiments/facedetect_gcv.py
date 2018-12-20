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
from enum import Enum
import time


def run():
	start_t = time.time()


	# Get user supplied values
	cascPath = "config\\cascades\\haarcascade_frontalface_default.xml"
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


	class Likelihood(Enum):
	    """
	    A bucketized representation of likelihood, which is intended to give clients
	    highly stable results across model upgrades.

	    Attributes:
	      UNKNOWN (int): Unknown likelihood.
	      VERY_UNLIKELY (int): It is very unlikely that the image belongs to the specified vertical.
	      UNLIKELY (int): It is unlikely that the image belongs to the specified vertical.
	      POSSIBLE (int): It is possible that the image belongs to the specified vertical.
	      LIKELY (int): It is likely that the image belongs to the specified vertical.
	      VERY_LIKELY (int): It is very likely that the image belongs to the specified vertical.
	    """
	    UNKNOWN = 0
	    VERY_UNLIKELY = 1
	    UNLIKELY = 2
	    POSSIBLE = 3
	    LIKELY = 4
	    VERY_LIKELY = 5

	def boundsToJSON(bounds):
		return [
			{'x': vertex.x, 'y': vertex.y}
			for vertex in bounds.vertices
		]

	def locationsToJSON(locations):
		return [
			{'latitude': loc.latitude, 'longitude': loc.longitude}
			for loc in locations
		]

	def entityToJSON(entity):
		return {
			# 'bounds': boundsToJSON(entity.bounds),
			'description': entity.description,
			# 'location': locationsToJSON(entity.locations),
			'mid': entity.mid,
			'score': entity.score
		}

	def faceToJSON(face):
		return {
			'anger_likelihood': Likelihood(face.anger_likelihood).name.lower(),
			'joy_likelihood': Likelihood(face.joy_likelihood).name.lower(),
			'sorry_likelihood': Likelihood(face.sorrow_likelihood).name.lower(),
			'surprise_likelihood': Likelihood(face.surprise_likelihood).name.lower(),
			'roll_angle': face.roll_angle,
			'pan_angle': face.pan_angle,
			'tilt_angle': face.tilt_angle,
			'bounding_poly': boundsToJSON(face.bounding_poly),
			'detection_confidence': face.detection_confidence,
			'fd_bounding_poly': boundsToJSON(face.fd_bounding_poly),
			'headwear_likelihood': Likelihood(face.headwear_likelihood).name.lower(),
			'blurred_likelihood': Likelihood(face.blurred_likelihood).name.lower(),
			'under_exposed_likelihood': Likelihood(face.under_exposed_likelihood).name.lower(),
			'landmarks': [
				{
					'type': LandmarkTypes(landmark.type).name.lower(),
					'position': {
						'x': landmark.position.x,
						'y': landmark.position.y,
						'z': landmark.position.z
					}
				}
				for landmark in face.landmarks
			],
			'landmarking_confidence': face.landmarking_confidence
		}

	def webToJSON(web):
		return {
			'web_entities': [
				{
					'entity_id': ent.entity_id,
					'score': ent.score,
					'description': ent.description
				} for ent in web.web_entities
			],
			'full_matching_images': [
				{
					'url': image.url,
					# 'score': image.score
				} for image in web.full_matching_images
			],
			'partial_matching_images': [
				{
					'url': image.url,
					# 'score': image.score
				} for image in web.partial_matching_images
			],
			'pages_with_matching_images': [
				{
					'url': page.url,
					# 'score': page.score
				} for page in web.pages_with_matching_images
			]
		}

	def cropToJSON(crop_hint):
		return {
			'bounding_poly': boundsToJSON(crop_hint.bounding_poly),
			'confidence': crop_hint.confidence,
			'importance_fraction': crop_hint.importance_fraction
		}

	def responseToJSON(response):
		return {
			'labels': map(entityToJSON, response.label_annotations),
			'face': map(faceToJSON, response.face_annotations),
			'crop': map(cropToJSON, response.crop_hints_annotation.crop_hints),
			'web': webToJSON(response.web_detection)
		}

	print("Will process %d images." % len(imgs))
	for imagePath in imgs:
		print("Processing: %s" % imagePath)

		# Instantiates a client
		client = vision.ImageAnnotatorClient()

		jsonPath = imagePath.replace('.png', '.json')
		jsonPath = jsonPath.replace('.jpg', '.json')

		if os.path.exists(jsonPath):
			print("Metadata already gathered - skipping")
			continue

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

		# Performs label detection on the image file
		response = client.annotate_image(request=request)
		if response.error.code:
			print("Error processing %s." % imagePath, response.error.message)

		print("Writing: %s" % jsonPath)

		with open(jsonPath, 'w') as f:
			f.write(json.dumps(responseToJSON(response)))

	print("Job finished in %.3fs" % (time.time() - start_t))
