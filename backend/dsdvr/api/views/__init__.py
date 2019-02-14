import logging

from collections import UserDict

from django.http import Http404
from django.db.transaction import atomic

from rest_framework import viewsets
from rest_framework import status
from rest_framework.response import Response


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class ObjectManager(UserDict):
    pass


class ObjectCreateMixin(object):
    @atomic
    def create(self, request):
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        obj = serializer.instance
        self.object_manager[str(obj.id)] = obj

        serializer = self.serializer_class(obj)
        return Response(serializer.data)


class ObjectRetrieveMixin(object):
    def retrieve(self, request, pk=None):
        try:
            obj = self.object_manager[pk]

        except KeyError:
            raise Http404()

        serializer = self.serializer_class(obj)
        return Response(serializer.data)


class ObjectListMixin(object):
    def list(self, request):
        serializer = self.serializer_class(
            self.object_manager.values(), many=True)
        return Response(serializer.data)


class ObjectDestroyMixin(object):
    def destroy(self, request, pk=None):
        try:
            obj = self.object_manager[pk]
            obj.stop()

        except KeyError:
            raise Http404()

        else:
            del self.object_manager[pk]

        return Response({}, status=status.HTTP_204_NO_CONTENT)


class ObjectManagerViewSet(ObjectCreateMixin, ObjectRetrieveMixin,
                           ObjectListMixin, ObjectDestroyMixin,
                           viewsets.ViewSet):
    object_manager = None
    serializer_class = None
