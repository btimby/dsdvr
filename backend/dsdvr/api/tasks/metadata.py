import logging
import threading

from os.path import join as pathjoin

import ffmpeg

from api.tasks import BaseTask
from api.models import Movie, Music, Show


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class TaskMetadataManager(BaseTask):
    lock = threading.Lock()

    def _ffprobe_video(self, video):
        try:
            video_path = pathjoin(video.path, 'recording0.mpeg')
            info = ffmpeg.probe(video_path)
            format = info['format']

            video_enc = audio_enc = width = height = None
            for stream in info['streams']:
                if stream['codec_type'] == 'video':
                    video_enc = stream['codec_name']
                    width = stream['width']
                    height = stream['height']

                elif stream['codec_type'] == 'audio':
                    audio_enc = stream['codec_name']

            video.update(
                has_metadata=True, duration=float(format['duration']),
                size=int(format['size']), format=format['format_name'],
                width=width, height=height, audio_enc=audio_enc,
                video_enc=video_enc,
            )

        except Exception:
            LOGGER.exception()

    def _omdb_movie(self, music):
        pass

    def _omdb_show(self, music):
        pass

    def _ffprobe_music(self, music):
        pass

    def _lastfm_music(self, music):
        pass

    def _run(self):
        if not self.lock.acquire(False):
            LOGGER.debug('Metadata manager lock acquisition failed')
            return

        # NOTE: this task is responsible for gathering metadata for media
        # files.

        try:
            # For loop over movies
            queryset = Movie.objects.all()
            for movie in queryset:
                # Use ffprobe to gather file information.
                self._ffprobe_video(self, movie)

                # Use OMDB to gather additional information.
                self._omdb_movie(self, movie)

            queryset = Show.objects.all()
            for show in queryset:
                self._ffprobe_video(show)
                self._omdb_show(show)

            queryset = Music.objects.all()
            for music in queryset:
                self._ffprobe_music(music)
                self._lastfm_music(music)

        finally:
            self.lock.release()
