import logging

from rest_framework import viewsets

from api.models import Channel
from api.serializers import ChannelSerializer


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class ChannelViewSet(viewsets.ModelViewSet):
    serializer_class = ChannelSerializer
    queryset = Channel.objects.all()
