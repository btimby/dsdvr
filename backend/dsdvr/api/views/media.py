from rest_framework import serializers, viewsets

from api.models import Media
from api.serializers import MediaSerializer


class MediaViewSet(viewsets.ModelViewSet):
    serializer_class = MediaSerializer
    queryset = Media.objects.all()
