import re
import logging
import threading

import ffmpeg
from ffmpeg._run import Error as FfmpegError

from django.db.transaction import atomic

from api.tasks import BaseTask
from api.settings import OMDB_API_KEY
from api.models import (
    Library, Media, Series, Category, Rating, Episode, Person, MediaActor,
)

from main import util


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())
_OMDB = None
RE_DIGITS = re.compile(r'[^0-9]')


def _omdb_client():
    import omdb

    global _OMDB

    if _OMDB is None:
        LOGGER.debug('Making client with API key: %s', OMDB_API_KEY)
        _OMDB = omdb.OMDBClient(apikey=OMDB_API_KEY)

    return _OMDB


@atomic
def ffprobe(media):
    try:
        for path in util.get_recordings(media.abs_path):
            try:
                info = ffmpeg.probe(path)

            except FfmpegError as e:
                LOGGER.warning(e.stderr, exc_info=True)
                continue

            format = info['format']

            video_enc = audio_enc = width = height = None
            for stream in info['streams']:
                if stream['codec_type'] == 'video':
                    video_enc = stream['codec_name']
                    width = stream['width']
                    height = stream['height']

                elif stream['codec_type'] == 'audio':
                    audio_enc = stream['codec_name']

            metadata = {
                'duration': float(format['duration']),
                'size': int(format['size']),
                'format': format['format_name'],
                'width': width,
                'height': height,
                'audio_enc': audio_enc,
                'video_enc': video_enc,
            }

            media.update(**metadata)
            return metadata

    except Exception as e:
        LOGGER.exception(e)


@atomic
def omdb(media):
    LOGGER.info('Fetching medata from OMDB...')
    info = _omdb_client().get(title=media.title)

    LOGGER.debug('Got: %s', info)
    metadata = {
        'title': info['title'],
        'subtitle': info['title'],
        'poster': info['poster'],
        'desc': info['plot'],
    }

    try:
        # I have seen invalid data in this field, ex: '2010-'
        metadata['year'] = int(RE_DIGITS.sub('', info['year']))

    except ValueError as e:
        LOGGER.warning(e, exc_info=True)

    metadata['rating'], _ = Rating.objects.get_or_create(name=info['rated'])

    categories, actors = [], []
    if 'genre' in info:
        for name in info['genre'].split(', '):
            cat, _ = Category.objects.get_or_create(name=name)
            categories.append(cat)

    if 'actors' in info:
        for name in info['actors'].split(', '):
            person, _ = Person.objects.get_or_create(name=name)
            actors.append(person)

    if info['type'] == 'series':
        series, _ = Series.objects.get_or_create(
            library=media.library, title=metadata['title'])
        series.update(**metadata)

        # Guide data _may_ provide these at some point...
        season = episode = None

        Episode.objects.create(
            show=media, series=series, season=season, episode=episode)

        media.categories.add(*categories)
        for person in actors:
            MediaActor.objects.get_or_create(media=media, person=person)
        series.categories.add(*categories)
        for person in actors:
            MediaActor.objects.get_or_create(media=series, person=person)

    else:
        media.update(**metadata)
        media.categories.add(*categories)

        for person in actors:
            MediaActor.objects.get_or_create(media=media, person=person)

    return metadata


class TaskMetadataFetch(BaseTask):
    '''
    Fetch metadata for a media item or library.
    '''

    lock = threading.Lock()

    def _get_metadata(self, media):
        ffprobe(media)
        omdb(media)

    def _run(self, obj):
        if not self.lock.acquire(False):
            LOGGER.debug('Metadata fetch lock acquisition failed')
            return

        try:
            if isinstance(obj, Library):
                queryset = Media.objects.filter(library=library)

            else:
                queryset = Media.objects.filter(pk=obj.pk)

            for media in queryset:
                self._get_metadata(media)

        finally:
            self.lock.release()
