import os
import logging
import time

from datetime import timedelta
from functools import wraps
from os.path import getsize
from os.path import join as pathjoin

import psutil
from psutil import NoSuchProcess, ZombieProcess, AccessDenied

from rest_framework import serializers, views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from django.contrib.auth import get_user_model

from api.models import Recording, Stream
from api.views.tasks import TASKS
from api.serializers import (
    TaskSerializer, RecordingSerializer, StreamSerializer
)

from main import settings


User = get_user_model()


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class throttle(object):
    """
    Decorator that prevents a function from being called more than once every
    time period.
    To create a function that cannot be called more than once a minute:
        @throttle(minutes=1)
        def my_fun():
            pass
    """
    def __init__(self, seconds=0, minutes=0, hours=0):
        self.throttle_secs = timedelta(
            seconds=seconds, minutes=minutes, hours=hours
        ).seconds
        self.cache = {}

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            now = time.time()
            cache_key = (tuple(map(str, sorted(args))),
                         tuple(map(str, sorted(kwargs.items()))))
            last_call, last_result = \
                self.cache.get(cache_key, (0, None))

            if now - last_call > self.throttle_secs:
                last_result = fn(*args, **kwargs)
                self.cache[cache_key] = (now, last_result)

            return last_result

        return wrapper


@throttle(minutes=5)
def get_directory_stats(path):
    size, count = 0, 0
    for root, _, files in os.walk(path):
        count += len(files)
        for f in files:
            size += getsize(pathjoin(root, f))

    stats = {
        'usage': size,
        'count': count,
    }
    return stats


@throttle(seconds=90)
def get_process_stats(pids):
    stats = {
        'uptime': 0,
        'count': len(pids),
        'cpu_percent': 0,
        'cpu_times': {'user': 0, 'system': 0},
        'mem_percent': 0.0,
        'mem_usage': 0,
    }
    for i, pid in enumerate(pids):
        try:
            process = psutil.Process(pid)

            with process.oneshot():
                if i == 0:
                    # First item is main process pid, get uptime for that.
                    stats['uptime'] = \
                        round(time.time() - process.create_time(), 2)

                stats['cpu_percent'] += process.cpu_percent()
                stats['mem_percent'] += round(process.memory_percent(), 2)
                stats['mem_usage'] += process.memory_info().rss

                user, system = process.cpu_times()[:2]
                stats['cpu_times']['user'] += user
                stats['cpu_times']['system'] += system

        except (NoSuchProcess, ZombieProcess, AccessDenied) as e:
            LOGGER.warning(e, exc_info=True)
            continue

    return stats


@throttle(seconds=30)
def get_system_stats():
    pids = [os.getpid()]
    pids.extend(
        Recording.objects.filter(
            pid__isnull=False).values_list('pid', flat=True)
    )
    pids.extend(
        Stream.objects.filter(pid__isnull=False).values_list('pid', flat=True)
    )
    stats = {
        'media': get_directory_stats(settings.STORAGE_MEDIA),
        'temp': get_directory_stats(settings.STORAGE_TEMP),
        'processes': get_process_stats(pids),
    }
    return stats


class StatusSerializer(serializers.Serializer):
    users = serializers.IntegerField()
    configured = serializers.BooleanField()
    system = serializers.SerializerMethodField()
    tasks = serializers.SerializerMethodField()
    recordings = serializers.SerializerMethodField()
    streams = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Some fields are only for authenticated users pop them...
        if not self.context['request'].user.is_authenticated:
            self.fields.pop('tasks')
            self.fields.pop('recordings')
            self.fields.pop('streams')
            pass

    def get_system(self, obj):
        return get_system_stats()

    def get_tasks(self, obj):
        return TaskSerializer(TASKS, many=True).data

    def get_recordings(self, obj):
        return RecordingSerializer(Recording.objects.all(), many=True).data

    def get_streams(self, obj):
        return StreamSerializer(Stream.objects.all(), many=True).data


class StatusView(views.APIView):
    '''
    There is a lot going on in this endpoint.

    We return system metrics that the UI needs. Some metrics are expensive to
    calculate, so a throttle decorator is used to cache results and only re-
    execute the function at a specific interval (regardless of the polling
    interval). Also, some metrics are sensitive and are only returned to an
    authenticated user (although this endpoint is open).
    '''

    permission_classes = (AllowAny,)

    def get(self, request):
        status = {
            'users': User.objects.all().count(),
            # For now, True, later check configuration for required keys.
            'configured': True,
        }
        serializer = StatusSerializer(status, context={'request': request})
        return Response(serializer.data)
