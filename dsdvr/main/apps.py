import logging

from django.apps import AppConfig
from django.conf import settings

from . import schedule


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class MainConfig(AppConfig):
    name = 'main'

    def ready(self):
        schedule.setup(settings.CRON)
