'''
Ephemeral tasks.

Threads that perform functions within the django process. They report their
status vi an API.

Tasks are started by other API endpoints to handle any work that cannot be
completed during an HTTP request / response cycle (long running operations).

They are ephemeral as they are not stored anywhere, the are spawned and then
can be monitored or cancelled. However if the django process restarts, all
threads stop and all the tasks are forgotten.
'''

import logging
import threading
import uuid

from datetime import datetime, timedelta

from django.utils import timezone
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse

from main.schedule import TASK_QUEUE


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())

# Data store.
# TODO: locking?
TASKS = {}

STATUS_NONE = None
STATUS_QUEUED = 1
STATUS_RUNNING = 2
STATUS_DONE = 0
STATUS_ERROR = 3
STATUS_TERMINATING = 4
STATUS_TERMINATED = 5

STATUS_NAMES = {
    STATUS_NONE: 'none',
    STATUS_QUEUED: 'queued',
    STATUS_RUNNING: 'running',
    STATUS_DONE: 'done',
    STATUS_ERROR: 'error',
    STATUS_TERMINATING: 'terminating',
    STATUS_TERMINATED: 'terminated',
}


class TaskTerminationException(BaseException):
    '''
    Raised by BaseTask._check_exit() to signal Task cancellation.
    '''
    pass


# TODO: move to main.
class BaseTask(object):
    '''
    To implement a new Task, you must subclass this one and implement _run().

    Refer to the docs of _run() for more details.
    '''

    def __init__(self, args=None, kwargs=None, id=None):
        self.id = id or uuid.uuid4()
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.done = 0
        self.total = 0
        self.created = timezone.now()
        self.modified = None
        self.thread = None
        self.status = STATUS_NONE
        self.summary = ''
        self.percent = 0
        self.elapsed = 0
        self.remaining = 0
        self.exit = threading.Event()
        # Create a subclass-wide lock to lock all tasks of the same type.
        self.__class__.lock = threading.Lock()

    def enqueue(self, background=False):
        TASK_QUEUE.put(self)

        self.status = STATUS_QUEUED
        self._set_progress(0, 1, 'Awaiting execution.')

        if not background:
            TASKS[str(self.id)] = self

        return redirect(reverse('tasks-detail', kwargs={'pk': str(self.id)}))

    start = enqueue

    def stop(self):
        '''
        Signal the Task thread to exit.
        '''
        self.status = STATUS_TERMINATING
        self.exit.set()

    def _check_exit(self):
        '''
        Raises TaskTerminationException if Task has been signalled to exit.
        '''
        if self.exit.is_set():
            LOGGER.info('Attempting to terminate task thread')
            raise TaskTerminationException('Terminate thread')

    def _estimate(self):
        '''
        Calculate runtime stats. Useful for progress notification.
        '''
        percent = elapsed = remaining = 0

        if self.total:
            percent = int(self.done / self.total * 100)

        if self.created:
            # If the task has been started, calculate how many seconds it has
            # been running.
            elapsed = (timezone.now() - self.created).total_seconds()

            # Then use the percentage of completion to determine how much more
            # runtime remains.
            if percent:
                # If percentage of completion is 0, then estimate the remaining
                # runtime by rounding percent up to 1%.
                at_least_one = max(percent, 1)
                remaining = elapsed / at_least_one * (100 - at_least_one)

        self.percent = percent
        self.elapsed = elapsed
        self.remaining = remaining

    def _set_progress(self, done, total, summary=None):
        '''
        To be called by _run() implementation periodically to provide progress
        notification.
        '''
        self.done = done
        self.total = total
        self.modified = timezone.now()

        # Only update summary if one is provided. Thus a task can provide an
        # initial summary that will remain during its run.
        if summary is not None:
            self.summary = summary

        # Calculate some stats.
        self._estimate()

        # Check if this task has been cancelled and exit if so.
        self._check_exit()

    def run(self):
        '''
        Entry point for Task thread.
        '''
        if not self.lock.acquire(False):
            LOGGER.debug('Metadata fetch lock acquisition failed')
            return

        try:
            self.status = STATUS_RUNNING
            try:
                self._run(*self.args, **self.kwargs)
                self.status = STATUS_DONE

            except TaskTerminationException:
                LOGGER.info('Task thread terminated.')
                self.status = STATUS_TERMINATED

            except Exception as e:
                LOGGER.debug('Error in task', exc_info=True)
                self.status = STATUS_ERROR
                self.summary = str(e)

        finally:
            self.lock.release()

    def _run(self, *args, **kwargs):
        '''
        To be overridden - It should do it's work and periodically update
        progress by calling _set_progress(). Also, it should call _check_exit()
        more frequently if possible.

        NOTE: _set_progress() calls _check_exit(). _check_exit() will raise
        TaskTerminationException if the Task has been signalled to exit. You
        are free to handle this exception as long as you re-raise it after any
        necessary cleanup or other actions.
        '''
        pass


class TaskCleanup(BaseTask):
    '''
    Clean up stale Tasks. Should be scheduled in settings.py.
    '''

    def _run(self):
        LOGGER.info('Task cleanup...')
        self._set_progress(0, 1, 'Purging stale Tasks...')
        for task in list(TASKS.values()):
            if task.status in (STATUS_NONE, STATUS_DONE, STATUS_ERROR,
                               STATUS_TERMINATED):

                # Leave tasks that have activity within the last 5 minutes
                # alone.
                last_activity = task.modified or task.created
                if last_activity >= timezone.now() - timedelta(minutes=5):
                    continue

                LOGGER.debug('Purging stale task id: %s', task.id)
                TASKS.pop(str(task.id))
        self._set_progress(1, 1, 'Purged stale Tasks.')
