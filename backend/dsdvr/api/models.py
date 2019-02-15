import os
import shutil
import uuid
import signal
import logging

from os.path import join as pathjoin
from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone

from ua_parser import user_agent_parser


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


def flatten(d):
    flat = {}
    for key, value in d.items():
        if hasattr(value, 'items'):
            for subkey, value in flatten(value).items():
                flat['%s_%s' % (key, subkey)] = value
        
        else:
            flat[key] = value
    return flat


class DirectoryPathField(models.CharField):
    def __init__(self, max_length=256, **kwargs):
        super().__init__(max_length=max_length, **kwargs)


class FilePathField(models.CharField):
    def __init__(self, max_length=256, **kwargs):
        super().__init__(max_length=max_length, **kwargs)


class UpdateMixin(object):
    def update(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)
        self.save(update_fields=list(kwargs.keys()))


class CreatedModifiedModel(models.Model):
    class Meta:
        abstract = True

    created = models.DateTimeField(editable=False)
    modified = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if self.created is None:
            self.created = timezone.now()
        self.modified = timezone.now()
        return super(CreatedModifiedModel, self).save(*args, **kwargs)


class DefaultTypeQuerySet(models.query.QuerySet):
    def __init__(self, *args, **kwargs):
        self.default_type = kwargs.pop('default_type', None)
        super().__init__(*args, **kwargs)

    def _extract_model_params(self, defaults, **kwargs):
        lookup, params = super()._extract_model_params(defaults, **kwargs)
        if self.default_type is not None:
            params.setdefault('type', self.default_type)
        return lookup, params


class DefaultTypeManager(models.Manager):
    DEFAULT_TYPE = None

    def get_queryset(self):
        return DefaultTypeQuerySet(
            model=self.model, using=self._db, hints=self._hints,
            default_type=self.DEFAULT_TYPE)


class Setting(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=256)
    value = models.CharField(max_length=256)


class DeviceQuerySet(models.query.QuerySet):
    def get_or_create(self, *args, **kwargs):
        user_agent = kwargs.get('user_agent', None)

        if user_agent:
            # TODO: populate other fields from user_agent
            defaults = kwargs.setdefault('defaults', {})
            flat = flatten(user_agent_parser.Parse(user_agent))
            flat.pop('string', None)
            defaults.update(flat)

        return super().get_or_create(*args, **kwargs)


class DeviceManager(models.Manager):
    def get_queryset(self):
        return DeviceQuerySet(
            model=self.model, using=self._db, hints=self._hints)


class Device(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_agent = models.TextField(unique=True)
    last_ip_address = models.GenericIPAddressField(null=True)
    device_brand = models.CharField(max_length=32, null=True)
    device_family = models.CharField(max_length=32, null=True)
    device_model = models.CharField(max_length=32, null=True)
    os_family = models.CharField(max_length=32, null=True)
    os_major = models.CharField(max_length=32, null=True)
    os_minor = models.CharField(max_length=32, null=True)
    os_patch = models.CharField(max_length=32, null=True)
    os_patch_minor = models.CharField(max_length=32, null=True)
    user_agent_family = models.CharField(max_length=32, null=True)
    user_agent_major = models.CharField(max_length=32, null=True)
    user_agent_minor = models.CharField(max_length=32, null=True)
    user_agent_patch = models.CharField(max_length=32, null=True)

    objects = DeviceManager()


class Tuner(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=32, unique=True)
    ipaddr = models.GenericIPAddressField()
    model = models.CharField(max_length=48)
    tuner_count = models.SmallIntegerField()


class Channel(UpdateMixin, CreatedModifiedModel):
    class Meta:
        unique_together = (
            ('tuner', 'number'),
        )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tuner = models.ForeignKey(
        Tuner, on_delete=models.CASCADE, related_name='channels')
    number = models.CharField(max_length=8)
    name = models.CharField(max_length=8)
    stream = models.CharField(max_length=256, null=True)
    poster = models.URLField(max_length=256, null=True)
    hd = models.BooleanField(default=False)

    def __str__(self):
        return '%s (%s)' % (self.name, self.number)

    def __repr__(self):
        return 'Channel: %s' % str(self)


class Library(UpdateMixin, CreatedModifiedModel):
    TYPE_MOVIES = 0
    TYPE_SHOWS = 1
    TYPE_MUSIC = 2

    TYPE_NAMES = {
        TYPE_MOVIES: 'movies',
        TYPE_SHOWS: 'shows',
        TYPE_MUSIC: 'music',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    type = models.SmallIntegerField(choices=list(TYPE_NAMES.items()))
    name = models.CharField(max_length=32, unique=True)
    path = DirectoryPathField(unique=True)


class Series(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=128, unique=True)


class Episode(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    series = models.ForeignKey(
        Series, on_delete=models.CASCADE, related_name='episodes')
    season = models.IntegerField()
    episode_system = models.CharField(max_length=32)
    episode = models.CharField(max_length=32)


class Category(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=128)


class Rating(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=16)


class Actor(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=16)


class ProgramManager(models.Manager):
    def get_upcoming(self):
        start_time = timezone.now()
        window = timedelta(hours=2)

        queryset = self.filter(
            Q(start__lte=start_time + window) & Q(stop__gte=start_time))
        queryset = queryset.order_by('channel__number', 'start')

        return queryset

    def get_playing(self):
        now = timezone.now()

        queryset = self.filter(
            Q(start__lte=now) & Q(stop__gte=now))
        queryset = queryset.order_by('channel__number', 'start')

        return queryset


class Program(UpdateMixin, CreatedModifiedModel):
    class Meta:
        unique_together = (
            ('channel', 'start'),
            ('channel', 'stop'),
        )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name='programs')
    episode = models.ForeignKey(
        Episode, on_delete=models.CASCADE, null=True, related_name='programs')
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, null=True, related_name='programs')
    rating = models.ForeignKey(Rating, on_delete=models.CASCADE, null=True)
    actors = models.ManyToManyField(Actor)
    title = models.CharField(max_length=256)
    subtitle = models.CharField(max_length=256)
    desc = models.TextField()
    start = models.DateTimeField()
    stop = models.DateTimeField()
    duration = models.IntegerField()
    poster = models.URLField(max_length=256, null=True)
    previously_shown = models.BooleanField(default=True)

    def __str__(self):
        return '%s @%s %s' % (self.channel, self.start, self.title,)

    def __repr__(self):
        return 'Show: %s' % str(self)

    objects = ProgramManager()


class Media(UpdateMixin, CreatedModifiedModel):
    TYPE_MOVIE = 0
    TYPE_MUSIC = 1
    TYPE_SHOW = 2

    TYPE_NAMES = {
        TYPE_MOVIE: 'Movie',
        TYPE_MUSIC: 'Music',
        TYPE_SHOW: 'Show',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    type = models.SmallIntegerField(choices=list(TYPE_NAMES.items()))
    library = models.ForeignKey(
        Library, on_delete=models.CASCADE, related_name='media')
    path = FilePathField(max_length=256)
    title = models.CharField(max_length=256)
    subtitle = models.CharField(max_length=256)
    desc = models.TextField()
    poster = models.URLField(max_length=256, null=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, null=True,
        related_name='%(class)ss')
    rating = models.ForeignKey(Rating, on_delete=models.CASCADE, null=True)
    has_metadata = models.BooleanField(default=False)
    duration = models.DecimalField(null=True, max_digits=12, decimal_places=6)
    size = models.IntegerField(null=True)
    format = models.CharField(null=True, max_length=32)
    audio_enc = models.CharField(null=True, max_length=32)
    play_count = models.IntegerField(default=0)

    def ensure_path(self):
        '''
        Generate a unique path for this show. Used by DVR, shows not recorded
        by DVR will have a path to the existing video file.
        '''
        # TODO: We need to follow a human readable naming scheme, but currently
        # there is not enough data to do so. Thus use the UUID.
        self.path = pathjoin(self.library.path, str(self.id))
        os.makedirs(self.path, exist_ok=True)
        self.save(update_fields=['path'])


class ShowManager(DefaultTypeManager):
    DEFAULT_TYPE = Media.TYPE_SHOW

    def get_or_create_from_program(self, program, **kwargs):
        defaults = kwargs.copy()
        defaults.update({
            'title': program.title,
            'subtitle': program.subtitle,
            'desc': program.desc,
            'duration': program.duration,
            'poster': program.poster,
            'category': program.category,
            'rating': program.rating,
        })
        show, created = self.get_or_create(program=program, defaults=defaults)
        show.update(**defaults)
        show.ensure_path()
        return show, created


class Show(Media):
    program = models.OneToOneField(
        Program, on_delete=models.SET_NULL, null=True, related_name='shows')
    episode = models.ForeignKey(
        Episode, on_delete=models.CASCADE, null=True, related_name='shows')
    width = models.SmallIntegerField(null=True)
    height = models.SmallIntegerField(null=True)
    video_enc = models.CharField(null=True, max_length=32)

    def __str__(self):
        return self.program.title

    def __repr__(self):
        return 'Show: %s' % str(self)

    objects = ShowManager()


class Stream(UpdateMixin, CreatedModifiedModel):
    TYPE_HLS = 0
    TYPE_RAW = 1

    TYPE_NAMES = {
        TYPE_HLS: 'hls',
        TYPE_RAW: 'raw',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    media = models.OneToOneField(
        Media, on_delete=models.CASCADE, related_name='stream')
    type = models.SmallIntegerField(choices=list(TYPE_NAMES.items()))
    path = DirectoryPathField(null=True)
    pid = models.IntegerField(null=True)
    cursor = models.DecimalField(max_digits=12, decimal_places=6, default=0.0)

    def delete(self, *args, **kwargs):
        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGINT)

            except ProcessLookupError as e:
                LOGGER.warning(e, exc_info=True)

        if self.path is not None:
            shutil.rmtree(self.path, ignore_errors=True)

        return super().delete(*args, **kwargs)


class Recording(UpdateMixin, CreatedModifiedModel):
    STATUS_NONE = 0
    STATUS_RECORDING = 1
    STATUS_ERROR = 2
    STATUS_DONE = 3

    STATUS_NAMES = {
        STATUS_NONE: 'none',
        STATUS_RECORDING: 'recording',
        STATUS_ERROR: 'error',
        STATUS_DONE: 'done',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    start = models.DateTimeField()
    stop = models.DateTimeField()
    program = models.OneToOneField(
        Program, on_delete=models.CASCADE, related_name='recording')
    show = models.OneToOneField(
        Show, null=True, on_delete=models.CASCADE, related_name='recording')
    status = models.SmallIntegerField(
        choices=STATUS_NAMES.items(), default=STATUS_NONE)
    pid = models.IntegerField(null=True)

    def is_now(self, now=None):
        if now is None:
            now = timezone.now()
        return self.start <= now and self.stop >= now

    def is_future(self, now=None):
        if now is None:
            now = timezone.now()
        return now < self.start

    def is_past(self, now=None):
        if now is None:
            now = timezone.now()
        return now >= self.stop

    def delete(self, *args, **kwargs):
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGINT)

            except ProcessLookupError as e:
                LOGGER.warning(e, exc_info=True)

        return super().delete(*args, **kwargs)


class Artist(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=256)
    poster = models.URLField(max_length=256, null=True)


class Album(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=256)
    poster = models.URLField(max_length=256, null=True)


class MusicManager(DefaultTypeManager):
    DEFAULT_TYPE = Media.TYPE_MUSIC


class Music(Media):
    artist = models.ForeignKey(
        Artist, on_delete=models.CASCADE, related_name='songs')
    album = models.ForeignKey(
        Album, on_delete=models.CASCADE, related_name='songs')

    objects = MusicManager()


class MovieManager(DefaultTypeManager):
    DEFAULT_TYPE = Media.TYPE_MOVIE


class Movie(Media):
    width = models.SmallIntegerField(null=True)
    height = models.SmallIntegerField(null=True)
    video_enc = models.CharField(null=True, max_length=32)

    objects = MovieManager()
