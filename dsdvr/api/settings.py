from django.conf import settings


GUIDE_METHOD = 'manual'
GUIDE_SD_USERNAME = None
GUIDE_SD_PASSWORD = None


if 'siteprefs' in settings.INSTALLED_APPS:
    from siteprefs.toolbox import preferences

    with preferences() as prefs:
        prefs(
            prefs.group('Guide settings',
                        (GUIDE_METHOD, GUIDE_SD_USERNAME, GUIDE_SD_PASSWORD),
                        static=False),
        )
