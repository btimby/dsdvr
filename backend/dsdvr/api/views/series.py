import logging

from rest_framework import viewsets

from api.models import Series
from api.serializers import SeriesSerializer


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class SeriesViewSet(viewsets.ModelViewSet):
    serializer_class = SeriesSerializer
    queryset = Series.objects.all()
