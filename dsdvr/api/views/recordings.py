import logging

from collections import OrderedDict

from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import serializers
from rest_framework import viewsets

from api.models import Recording, Show, Program
from api.tasks.recordings import RecordingControl
from api.serializers import RecordingSerializer, ProgramRelatedField


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class RecordingViewSet(viewsets.ModelViewSet):
    serializer_class = RecordingSerializer
    queryset = Recording.objects.all()

    def destroy(self, request, pk=None):
        recording = get_object_or_404(Recording, pk=pk)

        # NOTE: we let this raise so we don't delete a recording that may
        # reference a running process.
        RecordingControl(recording)._stop_recording()

        return super().destroy(request, pk=pk)
