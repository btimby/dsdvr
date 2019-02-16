import logging
import tempfile
import shutil

from datetime import timedelta

from django.utils import timezone
from django.db.models import Q

from rest_framework import viewsets
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.decorators import action

from api.models import Channel
from api.serializers import GuideSerializer, GuideUploadSerializer
from api.tasks.guide import TaskGuideImport


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class GuideViewSet(viewsets.ModelViewSet):
    serializer_class = GuideSerializer
    queryset = Channel.objects.all()

    @action(methods=['post'], detail=False)
    def download(self, request):
        # TODO: we need to download this data from schedules direct or similar.
        # TODO: do this by created TaskGuideDownload that will chain to
        # TaskGuideImport
        return TaskGuideImport().start()


class GuideUploadViewSet(viewsets.ViewSet):
    parser_classes = (MultiPartParser, )
    serializer_class = GuideUploadSerializer

    def create(self, request):
        xmltv = request.FILES['file']

        with tempfile.NamedTemporaryFile(delete=False) as temp:
            shutil.copyfileobj(xmltv, temp)

        return TaskGuideImport(kwargs={'path_or_file': temp.name}).start()
