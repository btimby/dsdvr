import os
import time
import logging
import threading
import fcntl
import errno
import tempfile

from os.path import join as pathjoin

from datetime import datetime, timedelta

import psutil
from croniter import croniter

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())

SCHEDULE = {}
SCHEDULER = None
SCHEDULER_LOCK = 'dsdvr.lock'


class Cron(object):
    def __init__(self, crontab):
        self.crontab = crontab
        self._cron = croniter(crontab)
        self._next = self._cron.get_next(datetime)

    def is_due(self):
        curr_time = datetime.now()  # + timedelta(minutes=1)
        curr_time = curr_time.replace(second=0, microsecond=0)

        # Is this task due?
        if self._next > curr_time:
            return False

        self._next = self._cron.get_next(datetime)
        return True

    def is_every_minute(self):
        return self.crontab.replace(' ', '') == '*****'


def _is_parent_python():
    pprocess = psutil.Process().parent()
    return pprocess.name() == 'python'


def _start_scheduler():
    # Django runserver forks. We don't want our scheduler running in the parent
    # since it survives auto-restart. This is a temporary workaround...
    if not _is_parent_python():
        return

    lock_file = pathjoin(tempfile.gettempdir(), SCHEDULER_LOCK)
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        LOGGER.info('Scheduler lock obtained')

    except IOError as e:
        if e.errno != errno.EAGAIN:
            raise
        LOGGER.info('Scheduler lock held by another process')
        return

    LOGGER.info('Starting scheduler in pid %i', os.getpid())
    SCHEDULER = threading.Thread(target=_check_schedule)
    SCHEDULER.daemon = True
    SCHEDULER.start()


def _check_schedule():
    '''
    Runs each minute in order to execute any due Tasks.
    '''
    first = True

    def _inner():
        for cron, task_class in SCHEDULE.items():
            # On the first iteration, run anything that runs every minute. This
            # allows such tasks to run "at startup".
            if first and cron.is_every_minute():
                LOGGER.info('Running startup task...')

            elif not cron.is_due():
                continue

            LOGGER.info('Running task %s', task_class)
            task_class = import_string(task_class)
            task_class().start(background=True)

    while True:
        try:
            _inner()

        except Exception as e:
            LOGGER.exception(e)

        first = False
        time.sleep(60)


def setup(config):
    '''
    Accept a list of crontab tuples consisting of:

        (cron_schedule, module_name.Class)

    and schedule them to run.
    '''
    for crontab, task_class in config:
        try:
            cron = Cron(crontab)

        except ValueError:
            raise ImproperlyConfigured(
                '"%s" is an invalid cron schedule' % crontab)

        try:
            # Store the class string, defer import...
            SCHEDULE[cron] = task_class

        except ImportError as e:
            raise ImproperlyConfigured(
                '"%s" is an invalid module_name.Class. %s' % (task_class, e))

    _start_scheduler()
