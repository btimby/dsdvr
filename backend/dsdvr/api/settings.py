import os

from django.conf import settings


GUIDE_METHOD = 'manual'
GUIDE_SD_USERNAME = None
GUIDE_SD_PASSWORD = None
OMDB_API_KEY = os.environ.get('OMDB_API_KEY', None)


if 'siteprefs' in settings.INSTALLED_APPS:
    from siteprefs.toolbox import preferences, patch_locals

    with preferences() as prefs:
        prefs(
            prefs.group('Guide settings',
                        (GUIDE_METHOD, GUIDE_SD_USERNAME, GUIDE_SD_PASSWORD),
                        static=False),
            prefs.group('OMDB API settings', (OMDB_API_KEY, ), static=True),
        )
