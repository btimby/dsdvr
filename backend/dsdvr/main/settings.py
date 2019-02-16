import os

from django.conf import settings


GUIDE_METHOD = 'manual'
GUIDE_SD_USERNAME = None
GUIDE_SD_PASSWORD = None
OMDB_API_KEY = os.environ.get('DSDVR_OMDB_API_KEY', None)
STORAGE_MEDIA = os.environ.get('DSDVR_STORAGE_MEDIA',
                               '/home/btimby/Code/dsdvr/media')
STORAGE_TEMP = os.environ.get('DSDVR_STORAGE_TEMP',
                              '/var/tmp/dsdvr')


if 'siteprefs' in settings.INSTALLED_APPS:
    from siteprefs.toolbox import preferences, patch_locals

    with preferences() as prefs:
        prefs(
            prefs.group('Guide Settings',
                        (GUIDE_METHOD, GUIDE_SD_USERNAME, GUIDE_SD_PASSWORD),
                        static=False),
            prefs.group('OMDB API Settings', (OMDB_API_KEY, ), static=True),
            prefs.group('Storage Settings',
                        (OMDB_API_KEY, ),
                        static=True),
        )
