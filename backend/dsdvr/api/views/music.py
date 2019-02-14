from rest_framework import serializers, viewsets

from api.models import Music
from api.serializers import MusicSerializer


class MusicViewSet(viewsets.ModelViewSet):
    serializer_class = MusicSerializer
    queryset = Music.objects.all()
