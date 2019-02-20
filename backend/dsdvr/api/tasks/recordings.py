import os
import logging
import threading
import subprocess
import multiprocessing
import time
import signal
import select

from datetime import timedelta

from os.path import join as pathjoin
from os.path import dirname

import psutil
import daemon

from django.utils import timezone
from django.db.transaction import atomic

from api.models import Recording, Media
from api.tasks import BaseTask, metadata


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


def _tail(command, path):
    log_file = open(
        pathjoin(dirname(path), 'ffmpeg.stderr'), 'ab')
    log_file.write(b'\n%s\n\n' % (' '.join(command).encode('utf8')))
    log_file.flush()

    process = subprocess.Popen(
        command, stderr=log_file, stdout=subprocess.PIPE, shell=False)

    written = 0
    with open(path, 'ab') as output:
        while process.poll() is None:
            input_readable = \
                select.select([process.stdout], [], [], 1.0)[0]

            if input_readable:
                data = process.stdout.read(1024 ** 2 * 3)
                if data:
                    written += len(data)
                    output.write(data)

    LOGGER.info(
        'Recording process exited with: %i after writing %i bytes',
        process.poll(), written)


def _daemonize(command, pid_file, path):
    with daemon.DaemonContext(pidfile=pid_file, detach_process=True):
        _tail(command, path)


class RecordingControl(object):
    def __init__(self, recording):
        self.recording = recording

    @atomic(immediate=True)
    def _start_recording(self):
        from api.views.streams import Pidfile

        # TODO: Setup wizard or similar must make user configure a library for
        # recordings... Perhaps we use a sane default? Can't think of one...
        # In any case, the first Library may not be the right one.
        media, _ = Media.objects.get_or_create_from_program(
            self.recording.program)

        # Just to be safe, this is our working dir...
        os.makedirs(dirname(media.abs_path), exist_ok=True)

        command = [
            'ffmpeg', '-loglevel', 'error', '-y', '-i',
            self.recording.program.channel.stream, '-c:v', 'copy', '-pix_fmt',
            'yuv420p', '-c:a', 'aac', '-profile:a', 'aac_low', '-f', 'mpegts',
            'pipe:1',
        ]

        frame0_path = media.frame0_path
        command.extend([
            '-vframes', '1', '-f', 'image2', frame0_path
        ])

        LOGGER.info('Spawning: "%s"', " ".join(command))

        pid_file = Pidfile(pathjoin(dirname(media.abs_path), 'ffmpeg.pid'))
        t_rec = multiprocessing.Process(
            target=_daemonize, args=(command, pid_file, media.abs_path))
        t_rec.daemon = False
        t_rec.start()

        pid = pid_file.poll()
        LOGGER.debug('Recording daemon on pid: %i', pid)
        self.recording.update(
            media=media, status=Recording.STATUS_RECORDING, pid=pid)

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
        try:
            metadata.ffprobe(self.recording.media.subtype())

        except Exception as e:
            LOGGER.exception(e)

    def _stop_recording(self, process=None):
        process = self._get_process()

        if process is not None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=10)

            except subprocess.TimeoutExpired as e:
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
    def _run(self, purge=False):
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

        queryset = Recording.objects.exclude(status=Recording.STATUS_DONE)

        LOGGER.debug(
            'Controlling %i active recording(s)', len(queryset))

        for recording in queryset:
            RecordingControl(recording).control()
