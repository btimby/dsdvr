import logging
import subprocess
import errno

from os.path import isfile
from os.path import dirname
from os.path import join as pathjoin

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.db.models import F
from django.contrib.staticfiles.templatetags.staticfiles import static

from rest_framework import viewsets
from rest_framework.response import Response

from main import util

from api.models import Media, Stream
from api.serializers import MediaSerializer, StreamSerializer
from api.views.streams import CreatingStreamSerializer


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


def make_frame0(media_path, frame0_path):
    file_names = util.get_recordings(media_path)
    for fn in file_names:
        command = [
            'ffmpeg', '-y', '-i', fn, '-vframes', '1', '-f', 'image2',
            frame0_path
        ]
        LOGGER.info('Spawning ffmpeg: %s', ' '.join(command))

        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

        except subprocess.CalledProcessError as e:
            LOGGER.warning(e.stderr, exc_info=True)
            continue

        else:
            break


class MediaViewSet(viewsets.ModelViewSet):
    serializer_class = MediaSerializer
    queryset = Media.objects.all()


class MediaStreamViewSet(viewsets.ModelViewSet):
    serializer_class = CreatingStreamSerializer
    queryset = Stream.objects.all()
    lookup_field = 'media__pk'
    lookup_url_kwarg = 'pk'

    def create(self, request, pk=None):
        media = get_object_or_404(Media, pk=pk)
        try:
            serializer = StreamSerializer(
                media.stream, context={'request': request})

        except Stream.DoesNotExist:

            data = {
                'media': pk,
                'type': request.data.get('type', 0)
            }
            serializer = CreatingStreamSerializer(
                data=data, context={'request': request})

            if serializer.is_valid():
                serializer.save()

        media.type_model().objects.filter(pk=media.id) \
            .update(play_count=F('play_count') + 1)

        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        request.data['media.id'] = pk
        return super().partial_update(request, pk=pk)


def poster(request, pk):
    # TODO: we may wish to cache these images. Could use a django disk cache
    # with a controlled path to use our "scratch" space. Could use a second
    # small memory cache as well. First cache to avoid hitting upstream too
    # much and second to avoid disk I/O.
    media = get_object_or_404(Media, pk=pk)
    poster_url = media.poster if media.poster else static('images/poster.jpg')
    return redirect(poster_url)


def frame0(request, pk):
    # TODO: we may with to cache these images in a memory cache.
    media = get_object_or_404(Media, pk=pk)
    frame0_path = pathjoin(dirname(media.abs_path), '%s.jpg' % pk)

    if not isfile(media.abs_path):
        raise Http404()

    if not isfile(frame0_path):
        make_frame0(media.abs_path, frame0_path)

    try:
        frame0_file = open(frame0_path, 'rb')

    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
        raise Http404()

    return FileResponse(frame0_file)
