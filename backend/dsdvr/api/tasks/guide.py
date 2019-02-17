import logging
import pytz
import threading

import os.path

from xml.etree.cElementTree import iterparse
from datetime import datetime

from django.db.utils import IntegrityError
from django.db.transaction import atomic

from api.models import Channel, Rating, Category, Program, Person, ProgramActor
from api.tasks import BaseTask


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())

# TODO: we need to pull this down from a service like Schedules Direct...
XMLTV_PATH = '../data/xmltv.xml'
TIME_FORMAT0 = '%Y%m%d%H%M%S %z'
TIME_FORMAT1 = '%Y%m%d%H%M%S'


def _parse_time(timestamp):
    try:
        return datetime.strptime(timestamp, TIME_FORMAT0)

    except ValueError:
        # XMLTV documentation states that if TZ is missing, UTC is to be
        # presumed.
        dt = datetime.strptime(timestamp, TIME_FORMAT1)
        return dt.replace(tzinfo=pytz.UTC)


class TaskGuideImport(BaseTask):
    '''
    Imports XMLTV data from file at given path.

    Data is in the form:

    <tv>
        ...
        <channel id="I1948.49934.zap2it.com">
            <display-name>1948 FRMVDM</display-name>
            <display-name>1948</display-name>
            <display-name>FRMVDM</display-name>
            <icon src="https://zap2it.tmsimg.com/sources/generic/generic_sources_h3.png" />
        </channel>
        ...
        <programme start="20080715103000 -0600" stop="20080715113000 -0600" channel="I10759.labs.zap2it.com">
            <title lang="en">The Young and the Restless</title>
            <sub-title lang="en">Sabrina Offers Victoria a Truce</sub-title>
            <desc lang="en">Jeff thinks Kyon stole the face cream; Nikki asks Nick to give David a chance; Amber begs Adrian to go to Australia.</desc>
            <credits>
                <actor>Peter Bergman</actor>
                <actor>Eric Braeden</actor>
                <actor>Jeanne Cooper</actor>
                <actor>Melody Thomas Scott</actor>
            </credits>
            <date>20080715</date>
            <category lang="en">Soap</category>
            <category lang="en">Series</category>
            <episode-num system="dd_progid">EP00004422.1359</episode-num>
            <episode-num system="onscreen">8937</episode-num>
            <audio>
                <stereo>stereo</stereo>
            </audio>
            <subtitles type="teletext" />
            <rating system="VCHIP">
                <value>TV-14</value>
            </rating>
        </programme>
        ...
    </tv>
    '''

    lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.categories = {}
        self.ratings = {}

    @atomic(immediate=True)
    def _get_category(self, name):
        category = self.categories.get(name)
        if category is None:
            category, _ = Category.objects.get_or_create(name=name)
            # Cache
            self.categories[name] = category
        return category

    @atomic(immediate=True)
    def _get_rating(self, name):
        rating = self.ratings.get(name)
        if rating is None:
            rating, _ = Rating.objects.get_or_create(name=name)
            # Cache
            self.ratings[name] = rating
        return rating

    @atomic(immediate=True)
    def _get_person(self, name):
        actor = self.actors.get(name)
        if actor is None:
            person, _ = Person.objects.get_or_create(name=name)
            # Cache
            self.actors[name] = person
        return actor

    @atomic(immediate=True)
    def _get_channel(self, number=None, name=None, poster=None, id=None):
        try:
            channel = Channel.objects.get(
                number=number,
                name=name)

            channel.poster = poster
            channel.save()

            return channel

        except Channel.DoesNotExist:
            pass

    def _run(self, path_or_file=XMLTV_PATH):
        if not self.lock.acquire(False):
            LOGGER.debug('Metadata fetch lock acquisition failed')
            return

        try:
            LOGGER.info('Syncing guide data from XMLTV...')

            if isinstance(path_or_file, str):
                f = open(path_or_file, 'rb')
                size = os.fstat(f.fileno()).st_size

            else:
                f = path_or_file
                if hasattr(f, 'size'):
                    size = f.size

                else:
                    size = os.fstat(f.fileno()).st_size

            self._set_progress(0, size, 'Importing guide data...')

            try:
                # Load the XML and get a reference to the root element.
                parser = iterparse(f, events=('start', 'end'))
                parser = iter(parser)
                _, root = next(parser)
                LOGGER.debug('XML root element: %s', root.tag)

                channels, data = {}, {}
                for event, el in parser:
                    if event == 'start':
                        # LOGGER.debug('Start of XML element: %s', el.tag)
                        if el.tag == 'channel':
                            data['id'] = el.attrib['id']

                        if el.tag == 'programme':
                            data['start'] = _parse_time(el.attrib['start'])
                            data['stop'] = _parse_time(el.attrib['stop'])
                            # If the channel is not in our database, set to None,
                            # later we will skip saving programs with:
                            # channel == None.
                            data['channel'] = channels.get(el.attrib['channel'])
                        continue

                    # LOGGER.debug('End of XML element: %s', el.tag)

                    # There can be multiple elements. We want the one that contains
                    # both the number and name. That element can be split on space.
                    if el.tag == 'display-name':
                        parts = el.text.split(' ')
                        if len(parts) == 2:
                            data['number'], data['name'] = parts
                        continue

                    # Save Channel
                    elif el.tag == 'channel':
                        channels[data['id']] = self._get_channel(**data)

                    # shared fields.
                    elif el.tag == 'icon':
                        data['poster'] = el.attrib['src']
                        continue

                    # programme fields.
                    elif el.tag == 'title':
                        data['title'] = el.text
                        continue

                    elif el.tag == 'desc':
                        data['desc'] = el.text
                        continue

                    elif el.tag == 'sub-title':
                        data['desc'] = el.text
                        continue

                    elif el.tag == 'actor':
                        data.setdefault(
                            'actors', []).append(self.get_person(el.text))
                        continue

                    elif el.tag == 'length':
                        unit = el.attrib['units']

                        if unit == 'seconds':
                            data['duration'] = int(el.text)
                        elif unit == 'minutes':
                            data['duration'] = int(el.text) * 60
                        elif unit == 'hours':
                            data['duration'] = int(el.text) * 60 * 60
                        else:
                            LOGGER.warning(
                                'length unit: %s unrecognized', el.attrib['units'])
                        continue

                    elif el.tag == 'category':
                        data.setdefault(
                            'categories', []).append(self._get_category(el.text))
                        continue

                    elif el.tag == 'rating':
                        data['rating'] = self._get_rating(el[0].text)
                        continue

                    # Save Programme
                    elif el.tag == 'programme':
                        if data['channel'] is None:
                            continue

                        # Calculate program length if not provided.
                        if 'duration' not in data:
                            data['duration'] = int(
                                (data['stop'] - data['start']).total_seconds()
                            )

                        channel = data.pop('channel')
                        start = data.pop('start')
                        stop = data.pop('stop')
                        actors = data.pop('actors', None)
                        categories = data.pop('categories', None)

                        try:
                            with atomic(immediate=True):
                                program, _ = \
                                    Program.objects.update_or_create(
                                        channel=channel, start=start, stop=stop,
                                        defaults=data)

                                if actors is not None:
                                    for person in actors:
                                        ProgramActor.objects.get_or_create(
                                            program=program, person=person)

                                if categories:
                                    program.categories.add(*categories)


                        except IntegrityError as e:
                            LOGGER.exception(
                                'Schedule conflict: channel=%s, start=%s, stop=%s'
                                ', data=%s', channel, start, stop, data)
                            raise

                    else:
                        continue

                    data.clear()
                    root.clear()

                    self._set_progress(f.tell(), size)

                # One final progress notification...
                self._set_progress(f.tell(), size)

            finally:
                f.close()

        finally:
            self.lock.release()
