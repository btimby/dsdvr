import os
import re
import logging
import threading
import mimetypes

from os.path import join as pathjoin
from os.path import basename

import ffmpeg
import pylast
import omdb

from ffmpeg._run import Error as FfmpegError

from django.db.transaction import atomic

from api.tasks import BaseTask
from api.models import (
    Library, Media, Movie, Music, Show, Artist, Album, Category, Rating, Actor,
    Episode, Series,
)


TAG_RE = re.compile(r'<[^>]+>')
EPISODE_RE = re.compile(r'[sS](\d+)[eE](\d+)')

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())

LASTFM = {
    'app': '********',
    'key': '********',
    'secret': '********',
    'username': '********',
    'password': '********',
}

# Send on querystring:
# http://www.omdbapi.com/?i=tt3896198&apikey=a9e4d8e2
OMDB = {
    'key': '********',
}

_LASTFM = None
_OMDB = None


def _strip_html(text):
    return TAG_RE.sub('', text)


def _get_lastfm_client():
    global _LASTFM
    if _LASTFM is None:
        _LASTFM = pylast.LastFMNetwork(
            api_key=LASTFM['key'], api_secret=LASTFM['secret'],
            username=LASTFM['username'],
            password_hash=pylast.md5(LASTFM['password']))
    return _LASTFM


def _get_omdb_client():
    global _OMDB
    if _OMDB is None:
        _OMDB = omdb.OMDBClient(apikey=OMDB['key'])
    return _OMDB


def _get_media_type(path):
    mime, _ = mimetypes.guess_type(path)

    LOGGER.debug('Mime type of %s: %s', path, mime)

    if mime is not None:
        type_name = mime.partition('/')[0]
        return Media.TYPE_MOVIE if type_name == 'video' else Media.TYPE_MUSIC


def _ffprobe_video(path, metadata):
    try:
        info = ffmpeg.probe(path)
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

    except FfmpegError as e:
        LOGGER.error(e.stderr)

    except Exception as e:
        LOGGER.exception(e)


def _omdb_video(path, metadata):
    # TODO: try to determine type, show or movie...

    title = basename(path)
    m = EPISODE_RE.search(title)

    season = episode = None
    if m:
        metadata['type'] = Media.TYPE_SHOW

        title = title[:m.start()]
        season, episode = map(int, m.groups())
        video = _get_omdb_client().get(
            title=title, season=season, episode=episode)

    else:
        LOGGER.error('Unparsable name: %s', title)
        metadata['type'] = Media.TYPE_MOVIE

        video = _get_omdb_client().get(title=title)

    metadata['title'] = title
    metadata['subtitle'] = video['title']
    metadata['poster'] = video['poster']
    metadata['rating'] = video['rated']
    metadata['actors'] = video['actors'].split(', ')
    metadata['desc'] = video['plot']
    metadata['season'] = video['season']
    metadata['episode'] = video['episode']
    metadata['year'] = video['year']
    metadata['category'] = video['genre']


def _ffprobe_audio(path, metadata):
    try:
        info = ffmpeg.probe(path)
    
        format = info['format']
        stream = info['streams'][0]
        tags = format['tags']

        metadata.update({
            'duration': float(format['duration']),
            'size': int(format['size']),
            'format': format['format_name'],
            'audio_enc': stream['codec_name'],

            'category': tags['genre'],
            'artist': {
                'name': tags['artist'],
            },

            'album': {
                'title': tags['album'],
                'year': int(tags['date']),
                'track': int(tags['track'])
            },
        })

    except FfmpegError as e:
        LOGGER.error(e.stderr)

    except Exception as e:
        LOGGER.exception(e)


def _lastfm_audio(path, metadata):
    # Set type to music.
    metadata['type'] = Media.TYPE_MUSIC

    # Get album from last fm...
    try:
        album = _get_lastfm_client().get_album(
            metadata['artist']['name'], metadata['album']['title'])
    except KeyError:
        return

    # Grab cover art.
    try:
        metadata['poster'] = metadata['album']['poster'] = \
            album.get_cover_image()
        metadata['artist']['poster'] = album.artist.get_cover_image()
        metadata['artist']['desc'] = \
            _strip_html(album.artist.get_wiki_summary())
        metadata['album']['desc'] = _strip_html(album.get_wiki_summary())

    except pylast.WSError:
        return


class TaskLibraryScan(BaseTask):
    lock = threading.Lock()

    def _get_metadata(self, path):
        metadata = {
            'type': _get_media_type(path),
        }

        if metadata['type'] == Media.TYPE_MOVIE:
            _ffprobe_video(path, metadata)
            _omdb_video(path, metadata)

        elif metadata['type'] == Media.TYPE_MUSIC:
            _ffprobe_audio(path, metadata)
            _lastfm_audio(path, metadata)

        else:
            raise ValueError('Invalid media type: %s' % metadata['type'])

        return metadata

    @atomic
    def _create_media(self, library, path, metadata):
        if metadata['type'] in (Media.TYPE_SHOW, Media.TYPE_MOVIE):
            actors = []

            if 'category' in metadata:
                metadata['category'], _ = Category.objects.get_or_create(
                    name=metadata.pop('category'))

            if 'rating' in metadata:
                metadata['rating'], _ = Rating.objects.get_or_create(
                    name=metadata.pop('rating'))

            if 'actors' in metadata:
                for name in metadata.pop('actors'):
                    actor, _ = Actor.objects.get_or_create(name=name)
                    actors.append(actor)

            if 'episode' in metadata:
                series, _ = Series.objects.get_or_create(name=metadata['title'])
                metadata['episode'], _ = Episode.objects.get_or_create(
                    series=series, season=metadata.pop('season'),
                    episode=metadata.pop('episode'))

            if metadata['type'] == Media.TYPE_SHOW:
                video = Show.objects.create(
                    library=library, path=path, **metadata)

            else:
                video = Movie.objects.create(
                    library=library, path=path, **metadata)

            if actors:
                video.actors.add(*actors)

            return video

        elif metadata['type'] == Media.TYPE_MUSIC:
            artist_metadata = metadata.pop('artist')
            album_metadata = metadata.pop('album')
            metadata['track'] = album_metadata.pop('track')

            artist, _ = Artist.objects.get_or_create(
                name=artist_metadata.pop('name'), defaults=artist_metadata)
            album, _ = Album.objects.get_or_create(
                artist=artist,
                title=album_metadata.pop('title'),
                defaults=album_metadata,
            )
            category, _ = Category.objects.get_or_create(
                name=metadata.pop('category'))

            return Music.objects.create(
                library=library, path=path, artist=artist, album=album,
                category=category, **metadata)

        else:
            raise ValueError('Invalid media type: %s' % metadata['type'])

    def _scan_library(self, library):
        LOGGER.info('Scanning media library: %s', library.abs_path)
        # Recursively create a list of all FILES in the library.
        new, stale = set(), set()
        for (root, _, files) in os.walk(library.abs_path):
            new.update([pathjoin(root, file) for file in files])

        # Now loop over media and remove paths that we already know about.
        # Any media paths that don't exist, we record here (so we can purge
        # the DB)
        for media in library.media.all():
            try:
                new.remove(media.abs_path)

            except KeyError:
                stale.add(media.abs_path)

        LOGGER.debug(
            'Found %i new files and %i stale media', len(new), len(stale))

        for path in new:
            try:
                metadata = self._get_metadata(path)

            except ValueError as e:
                LOGGER.warning(e, exc_info=True)
                continue

            # TODO: create model...
            LOGGER.debug('Metadata for path: %s: %s', path, metadata)

            self._create_media(library, path, metadata)

    def _run(self, library=None):
        if not self.lock.acquire(False):
            LOGGER.debug('Library scan lock acquisition failed')
            return

        try:
            queryset = Library.objects.all() if library is None \
                       else Library.objects.filter(pk=library.pk)

            for library in queryset:
                self._scan_library(library)

        finally:
            self.lock.release()
