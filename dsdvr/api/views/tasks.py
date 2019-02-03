'''
Ephemeral tasks.

Threads that perform functions within the django process. They report their
status vi an API.

Tasks are started by other API endpoints to handle any work that cannot be
completed during an HTTP request / response cycle (long running operations).

They are ephemeral as they are not stored anywhere, the are spawned and then
can be monitored or cancelled. However if the django process restarts, all
threads stop and all the tasks are forgotten.
'''

import logging


from django.http import Http404
from django.shortcuts import redirect

from rest_framework import viewsets, status
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.decorators import action

from api.views import (
    ObjectListMixin, ObjectRetrieveMixin,
    ObjectDestroyMixin
)
from api.tasks import TASKS
from api.serializers import TaskSerializer


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class TaskViewSet(ObjectListMixin, ObjectRetrieveMixin, ObjectDestroyMixin,
                  viewsets.ViewSet):
    '''
    API for ephemeral Tasks.
    '''

    serializer_class = TaskSerializer
    object_manager = TASKS

    @action(methods=['post'], detail=False)
    def cleanup(self, request):
        return TaskCleanup().start()
