import os.path

from django.shortcuts import get_object_or_404

from rest_framework import serializers, viewsets, views
from rest_framework.response import Response
from rest_framework.decorators import detail_route

from api.models import Library
from api.serializers import LibrarySerializer, MediaSerializer


class LibraryViewSet(viewsets.ModelViewSet):
    '''
    Library ViewSet.

    Send contents query string argument to see shows in the library(s).
    '''
    serializer_class = LibrarySerializer
    queryset = Library.objects.all()

    @detail_route()
    def media(self, request, pk):
        library = get_object_or_404(Library, pk=pk)
        serializer = serializers.ListSerializer(
            library.media, child=MediaSerializer())
        return Response(serializer.data)
