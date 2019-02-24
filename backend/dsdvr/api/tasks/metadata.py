import re
import logging
import threading

import ffmpeg
from ffmpeg._run import Error as FfmpegError

from django.db.transaction import atomic

from constance import config

from api.tasks import BaseTask
from api.models import (
    Media, Series, Category, Rating, Episode, Person, MediaActor,
)


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())
_OMDB = None
RE_DIGITS = re.compile(r'[^0-9]')


def _omdb_client():
    import omdb

    global _OMDB

    if _OMDB is None:
        LOGGER.debug('Making client with API key: %s', config.OMDB_API_KEY)
        _OMDB = omdb.OMDBClient(apikey=config.OMDB_API_KEY)

    return _OMDB


@atomic
def ffprobe(media):
    LOGGER.info('Getting metadata from file...')
    try:
        metadata = {}
        try:
            info = ffmpeg.probe(media.abs_path)

        except FfmpegError as e:
            LOGGER.warning(e.stderr, exc_info=True)
            return metadata

        format = info['format']

        video_enc = audio_enc = width = height = None
        for stream in info['streams']:
            if stream['codec_type'] == 'video':
                video_enc = stream['codec_name']
                width = stream['width']
                height = stream['height']

            elif stream['codec_type'] == 'audio':
                audio_enc = stream['codec_name']

        metadata.update({
            'duration': float(format['duration']),
            'size': int(format['size']),
            'format': format['format_name'],
            'width': width,
            'height': height,
            'audio_enc': audio_enc,
            'video_enc': video_enc,
        })

        media.update(**metadata)
        return metadata

    except Exception as e:
        LOGGER.exception(e)


@atomic
def omdb(media):
    LOGGER.info('Fetching medata from OMDB...')
    info = _omdb_client().get(title=media.title)
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
        series, _ = Series.objects.get_or_create(title=metadata['title'])
        series.update(**metadata)

        # Guide data _may_ provide these at some point...
        nseason = nepisode = None
        episode, _ = Episode.objects.get_or_create(
            show=media.subtype(), series=series)
        episode.update(season=nseason, episode=nepisode)

        media.categories.add(*categories)
        for person in actors:
            MediaActor.objects.get_or_create(media=media, person=person)
        series.categories.add(*categories)
        for person in actors:
            MediaActor.objects.get_or_create(media=series, person=person)

        # The OMDB poster is typically of higher quality...
        media.update(poster=metadata['poster'])

    else:
        media.update(**metadata)
        media.categories.add(*categories)

        for person in actors:
            MediaActor.objects.get_or_create(media=media, person=person)

    return metadata


class TaskMetadataFetch(BaseTask):
    '''
    Fetch metadata for a media item.
    '''

    def _run(self, media):
        ffprobe(media)
        omdb(media)
