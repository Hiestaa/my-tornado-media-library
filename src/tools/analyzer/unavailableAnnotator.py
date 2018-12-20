
from tools.analyzer.baseAnnotator import BaseAnnotator


class UnavailableAnnotator(BaseAnnotator):

    def __init__(self, *args, **kwargs):
        raise Exception('The annotator you are trying to use is not available.')

    def _annotateBatch(self, *args, **kwargs):
        raise Exception('The annotator you are trying to use is not available.')
