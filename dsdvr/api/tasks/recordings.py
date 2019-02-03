import logging
import threading
import subprocess
import signal

import psutil

from django.utils import timezone
from django.db.transaction import atomic

from api.models import Recording, Library, Show
from api.tasks import BaseTask

from main import util


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class RecordingControl(object):
    def __init__(self, recording):
        self.recording = recording

    @atomic
    def _start_recording(self):
        # TODO: Setup wizard or similar must make user configure a library for
        # recordings... Perhaps we use a sane default? Can't think of one...
        # In any case, the first Library may not be the right one.
        library = Library.objects.first()

        if library is None:
            raise RuntimeError('No library for recordings')

        show, created = Show.objects.get_or_create(
            library=library, program=self.recording.program)

        if created:
            show.generate_path()

        recording_path = util.get_next_recording(show.path)

        command = [
            'ffmpeg', '-loglevel', 'fatal', '-i',
            self.recording.program.channel.stream, '-c:v', 'copy', '-pix_fmt',
            'yuv420p', '-c:a', 'aac', '-profile:a', 'aac_low', '-f', 'mpegts',
            recording_path,
        ]

        LOGGER.info('Spawning: "%s"', " ".join(command))
        process = subprocess.Popen(command)
        self.recording.update(
            show=show, status=Recording.STATUS_RECORDING, pid=process.pid)

        return process

    def _get_process(self):
        '''
        Retrives a psutil.Process instance for recording.pid. Sets
        recording.pid to None if it is invalid.
        '''
        if self.recording.pid is None:
            return

        try:
            process = psutil.Process(self.recording.pid)

            if process.status() == psutil.STATUS_ZOMBIE:
                process.wait()
                self.recording.update(pid=None)
                return

            elif not process.is_running():
                self.recording.update(pid=None)
                return

            else:
                return process

        except psutil.NoSuchProcess:
            self.recording.update(pid=None)
            pass

    def _finalize_recording(self):
        '''
        Do any post-processing necessary.

        For interrupted recordings, new files are created. Here we concatenate
        all the files together into the Show's path. This works because we use
        mpegts as a container.
        '''
        # TODO: Here is where we would skip commercials etc.
        path = self.recording.show.path
        file_names = util.get_recordings(path)
        util.combine_recordings(path, file_names[1:])

    def _stop_recording(self, process=None):
        process = self._get_process()

        if process is not None:
            process.send_signal(signal.SIGINT)
            process.wait()

        self.recording.update(pid=None, status=Recording.STATUS_DONE)

        self._finalize_recording()

    def _check_recording(self):
        process = self._get_process()

        if process is None:
            return self._start_recording()

    def control(self):
        now = timezone.now()

        if self.recording.is_airing(now):
            try:
                self._check_recording()

            except Exception as e:
                LOGGER.exception(e)
                self.recording.update(status=Recording.STATUS_ERROR)

        elif self.recording.is_over(now):
            self._stop_recording()


class TaskRecordingManager(BaseTask):
    lock = threading.Lock()

    def _run(self):
        if not self.lock.acquire(False):
            LOGGER.debug('Recording manager lock acquisition failed')
            return

        try:
            queryset = Recording.objects.exclude(status=Recording.STATUS_DONE)

            LOGGER.info(
                'Recording manager started, %i active recordings',
                len(queryset))

            for recording in queryset:
                RecordingControl(recording).control()

        finally:
            self.lock.release()
