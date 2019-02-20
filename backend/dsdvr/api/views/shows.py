import logging

from rest_framework import serializers, viewsets

from api.models import Show
from api.serializers import ShowSerializer


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class ShowViewSet(viewsets.ModelViewSet):
    serializer_class = ShowSerializer
    queryset = Show.objects.all()
