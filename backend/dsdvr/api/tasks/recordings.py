import logging
import threading
import subprocess
import signal
import time

from datetime import timedelta

from os.path import join as pathjoin
from os.path import dirname

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
        library = Library.objects.order_by('created').first()

        if library is None:
            raise RuntimeError('No library for recordings')

        show, _ = Show.objects.get_or_create_from_program(
            self.recording.program, library=library)
        recording_path = util.get_next_recording(show.abs_path)

        command = [
            'ffmpeg', '-loglevel', 'error', '-n', '-i',
            self.recording.program.channel.stream, '-c:v', 'copy', '-pix_fmt',
            'yuv420p', '-c:a', 'aac', '-profile:a', 'aac_low', '-f', 'mpegts',
            recording_path,
        ]

        if recording_path.endswith('recording0.mpeg'):
            frame0_path = pathjoin(dirname(recording_path), 'frame0.jpg')
            command.extend([
                '-vframes', '1', '-f', 'image2', frame0_path
            ])

        log_file = open(
            pathjoin(dirname(recording_path), 'ffmpeg.stderr'), 'ab')
        log_file.write(b'\n%s\n\n' % (' '.join(command).encode('utf8')))
        log_file.flush()

        LOGGER.info('Spawning: "%s"', " ".join(command))
        process = subprocess.Popen(command, stderr=log_file, shell=False)
        self.recording.update(
            show=show, status=Recording.STATUS_RECORDING, pid=process.pid)

        # Let ffmpeg get started, then check if it died and report stderr.
        try:
            r = process.wait(2)
        
        except subprocess.TimeoutExpired:
            pass

        else:
            LOGGER.error(
                'ffmpeg died with error %i: %s', r,
                util.last_3_lines(process.stderr))

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
        util.combine_recordings(file_names[0], file_names[1:])

    def _stop_recording(self, process=None):
        process = self._get_process()

        if process is not None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=10)

            except subprocess.TimeoutException as e:
                # Process did not die after 10s, move forward, next task
                # iteration will retry.
                LOGGER.exception(e)

        self.recording.update(pid=None, status=Recording.STATUS_DONE)

        self._finalize_recording()

    def _check_recording(self):
        process = self._get_process()

        if process is None:
            return self._start_recording()

    def control(self):
        now = timezone.now()

        # Stop first to free up Tuners...
        if self.recording.is_past(now):
            self._stop_recording()

        # Then start new recordings...
        elif self.recording.is_now(now):
            try:
                self._check_recording()

            except Exception as e:
                LOGGER.exception(e)
                self.recording.update(status=Recording.STATUS_ERROR)


class TaskRecordingManager(BaseTask):
    lock = threading.Lock()

    def _run(self, purge=False):
        if not self.lock.acquire(False):
            LOGGER.debug('Recording manager lock acquisition failed')
            return

        if purge:
            try:
                expiration = timezone.now() - timedelta(hours=2)
                queryset = Recording.objects.filter(
                    status=Recording.STATUS_DONE, stop__lte=expiration)
                LOGGER.debug(
                    'Deleting %i recording(s) older than %s', len(queryset),
                    expiration)
                queryset.delete()

            except Exception as e:
                # This operation is not critical, but should be logged and
                # reported.
                LOGGER.exception(e)

        try:
            queryset = Recording.objects.exclude(status=Recording.STATUS_DONE)

            LOGGER.debug(
                'Controlling %i active recording(s)', len(queryset))

            for recording in queryset:
                RecordingControl(recording).control()

        finally:
            self.lock.release()
