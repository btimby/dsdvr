import logging

import requests

from xml.etree.cElementTree import iterparse

from libhdhomerun import (
    hdhomerun_discover_device_t, HDHOMERUN_DEVICE_TYPE_TUNER,
    HDHOMERUN_DEVICE_ID_WILDCARD,
)
from libhdhomerun import (
    hdhomerun_device_create, hdhomerun_device_destroy,
    hdhomerun_discover_destroy, hdhomerun_device_get_device_id,
    hdhomerun_device_get_device_ip, hdhomerun_device_get_model_str,
    hdhomerun_discover_find_devices_custom_v2,
)
from libhdhomerun.util import ip_to_str

from django.db.transaction import atomic

from api.models import Tuner, Channel
from api.tasks import BaseTask


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())

TUNERS_MAX = 64


class TunerScanException(Exception):
    pass


class TunerDiscoverTask(BaseTask):
    def _discover(self):
        # Create an array of structs.
        discovered = (hdhomerun_discover_device_t * TUNERS_MAX)()
        # Possibly fill that array.
        discovered_n = hdhomerun_discover_find_devices_custom_v2(
            0, HDHOMERUN_DEVICE_TYPE_TUNER,
            HDHOMERUN_DEVICE_ID_WILDCARD, discovered, TUNERS_MAX
        )

        tuners = []

        if discovered_n < 0:
            raise TunerScanException('Error discovering tuners')

        elif discovered_n == 0:
            LOGGER.warning('No tuners discovered')

        else:
            LOGGER.info('Found %i tuners', discovered_n)

            for i in range(discovered_n):
                device = hdhomerun_device_create(
                    discovered[i].device_id, discovered[i].ip_addr, 0, None)

                name = hdhomerun_device_get_device_id(device)
                ipaddr = ip_to_str(hdhomerun_device_get_device_ip(device))
                model = hdhomerun_device_get_model_str(device).decode('utf8')
                tuner_count = discovered[i].tuner_count

                hdhomerun_device_destroy(device)
                
                LOGGER.debug(
                    'Tuner found: name=%s, ip=%s, model=%s, tuners=%s', name,
                    ipaddr, model, tuner_count)

                try:
                    tuner = Tuner.objects.get(name=name)

                except Tuner.DoesNotExist:
                    tuner = Tuner.objects.create(
                        name=name, ipaddr=ipaddr, model=model,
                        tuner_count=tuner_count)

                tuners.append(tuner)

        return tuners

    def _import_lineup(self, tuner):
        '''
        Imports XML channel lineup from HDHomeRun tuner.
        '''
        # Stream XML from HDHomeRun:
        url = 'http://%s/lineup.xml' % tuner.ipaddr

        LOGGER.info('Syncing tuner channel lineup from %s', url)

        r = requests.get(url, stream=True)
        r.raw.decode_content = True

        # Load the XML and get a reference to the root element.
        parser = iterparse(r.raw, events=('start', 'end'))
        parser = iter(parser)
        _, root = next(parser)
        LOGGER.debug('XML root element: %s', root.tag)

        data = {}
        for event, el in parser:
            if event == 'start':
                continue

            if el.tag == 'GuideNumber':
                data['number'] = el.text
                continue

            elif el.tag == 'GuideName':
                data['name'] = el.text
                continue

            elif el.tag == 'URL':
                data['stream'] = el.text
                continue

            elif el.tag == 'HD':
                data['hd'] = el.text == '1'
                continue

            elif el.tag == 'Program':
                with atomic(immediate=True):
                    Channel.objects.update_or_create(
                        tuner=tuner, number=data['number'], name=data['name'],
                        defaults={
                            'stream': data['stream'],
                            'hd': data.get('hd', False),
                        })

            else:
                continue

            data.clear()
            root.clear()

    def _run(self):
        done, total = 0, 1
        LOGGER.info('Discovering tuners...')
        self._set_progress(done, total, 'Discovering tuners...')

        tuners = self._discover()
        total = len(tuners)

        for tuner in tuners:
            self._set_progress(done, total, 'Importing lineup...')
            self._import_lineup(tuner)
            done += 1

        self._set_progress(done, total, 'Discovered %i Tuners.' % done)


class TunerScanTask(BaseTask):
    def _run(self, tuner):
        self._set_progress(1, 1, 'Scan complete.')
