import os.path

from rest_framework import serializers, viewsets

from api.models import Library
from api.serializers import LibrarySerializer


class LibraryViewSet(viewsets.ModelViewSet):
    serializer_class = LibrarySerializer
    queryset = Library.objects.all()
