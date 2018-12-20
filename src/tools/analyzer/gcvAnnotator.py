# -*- coding: utf8 -*-

from __future__ import unicode_literals

import io
from enum import Enum

from tools.analyzer.baseAnnotator import BaseAnnotator

# Imports the Google Cloud client library
from google.cloud import vision
from google.cloud.vision import types
from google.cloud.vision.feature import Feature, FeatureTypes
from google.cloud.vision.face import LandmarkTypes


class Serializer(object):
    """Serialize a Google Cloud Vision Response to JSON-cp,[aton;e """
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

    @staticmethod
    def boundsToJSON(bounds):
        return [
            {'x': vertex.x, 'y': vertex.y}
            for vertex in bounds.vertices
        ]

    @staticmethod
    def locationsToJSON(locations):
        return [
            {'latitude': loc.latitude, 'longitude': loc.longitude}
            for loc in locations
        ]

    @staticmethod
    def entityToJSON(entity):
        return {
            # 'bounds': Serializer.boundsToJSON(entity.bounds),AnnotateImageRequest
            'description': entity.description,
            # 'location': Serializer.locationsToJSON(entity.locations),
            'mid': entity.mid,
            'score': entity.score
        }

    @staticmethod
    def faceToJSON(face):
        return {
            'anger_likelihood': Serializer.Likelihood(face.anger_likelihood).name.lower(),
            'joy_likelihood': Serializer.Likelihood(face.joy_likelihood).name.lower(),
            'sorry_likelihood': Serializer.Likelihood(face.sorrow_likelihood).name.lower(),
            'surprise_likelihood': Serializer.Likelihood(face.surprise_likelihood).name.lower(),
            'roll_angle': face.roll_angle,
            'pan_angle': face.pan_angle,
            'tilt_angle': face.tilt_angle,
            'bounding_poly': Serializer.boundsToJSON(face.bounding_poly),
            'detection_confidence': face.detection_confidence,
            'fd_bounding_poly': Serializer.boundsToJSON(face.fd_bounding_poly),
            'headwear_likelihood': Serializer.Likelihood(face.headwear_likelihood).name.lower(),
            'blurred_likelihood': Serializer.Likelihood(face.blurred_likelihood).name.lower(),
            'under_exposed_likelihood': Serializer.Likelihood(face.under_exposed_likelihood).name.lower(),
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

    @staticmethod
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

    @staticmethod
    def cropToJSON(crop_hint):
        return {
            'bounding_poly': Serializer.boundsToJSON(crop_hint.bounding_poly),
            'confidence': crop_hint.confidence,
            'importance_fraction': crop_hint.importance_fraction
        }

    @staticmethod
    def imagePropertiesToJSON(properties):
        return {
            'dominant_colors': [
                {'score': color.score, 'pixel_fraction': color.pixel_fraction, 'color': {
                    'red': color.color.red,
                    'green': color.color.green,
                    'blue': color.color.blue
                }} for color in properties.dominant_colors.colors
            ]
        }

    @staticmethod
    def responseToJSON(response):
        """
        Convert the GCV response into a JSON-serializable object.
        """
        return {
            'version': vision.__version__,
            'labels': map(Serializer.entityToJSON, response.label_annotations),
            'faces': map(Serializer.faceToJSON, response.face_annotations),
            'crop': map(Serializer.cropToJSON, response.crop_hints_annotation.crop_hints),
            'web': Serializer.webToJSON(response.web_detection),
            'properties': Serializer.imagePropertiesToJSON(response.image_properties_annotation)
        }

class GCVAnnotator(BaseAnnotator):
    """
    Use Google Cloud Vision to submit image annotation for a large batch of images
    Save a cache of the result of the analysis on disk, so that we never submit
    a request for the same image twice.
    """
    def __init__(self, imgPaths, progress):
        super(GCVAnnotator, self).__init__('gcv', 2, imgPaths, progress)

        self.client = vision.ImageAnnotatorClient()


    # override
    def _annotateBatch(self, batch):
        requests = []
        for imagePath in batch:
            # Loads the image into memory
            with io.open(imagePath, 'rb') as image_file:
                content = image_file.read()

                image = types.Image(content=content)

            # https://googlecloudplatform.github.io/google-cloud-python/latest/vision/gapic/v1/types.html#google.cloud.vision_v1.types.AnnotateImageRequest
            request = types.AnnotateImageRequest(image=image, features=[
                types.Feature(type=FeatureTypes.FACE_DETECTION, max_results=3),  # Run face detection.
                # types.Feature(type=FeatureTypes.LANDMARK_DETECTION),  # Run landmark detection.
                # types.Feature(type=FeatureTypes.LOGO_DETECTION),  # Run logo detection.
                types.Feature(type=FeatureTypes.LABEL_DETECTION, max_results=10),  # Run label detection.
                # types.Feature(type=FeatureTypes.TEXT_DETECTION),  # Run OCR.
                # types.Feature(type=FeatureTypes.DOCUMENT_TEXT_DETECTION),  # Run dense text document OCR. Takes precedence when both DOCUMENT_TEXT_DETECTION and TEXT_DETECTION are present.
                # types.Feature(type=FeatureTypes.SAFE_SEARCH_DETECTION),  # Run computer vision models to compute image safe-search properties.
                types.Feature(type=FeatureTypes.IMAGE_PROPERTIES),  # Compute a set of image properties, such as the image's dominant colors.
                types.Feature(type=FeatureTypes.CROP_HINTS, max_results=5),  # Run crop hints.
                types.Feature(type=FeatureTypes.WEB_DETECTION, max_results=10),  # Run web detection.
            ])

            requests.append(request)

        response = self.client.batch_annotate_images(requests=requests)
        return [
            Serializer.responseToJSON(
                response.responses[resultCache[imagePath]['index']])
            for imagePath in batch
        ]
