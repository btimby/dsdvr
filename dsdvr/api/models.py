import os
import uuid

from os.path import join as pathjoin
from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone


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


class CreatedUpdatedModel(models.Model):
    class Meta:
        abstract = True

    created = models.DateTimeField(editable=False)
    modified = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if self.created is None:
            self.created = timezone.now()
        self.modified = timezone.now()
        return super(CreatedUpdatedModel, self).save(*args, **kwargs)


class Setting(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=256)
    value = models.CharField(max_length=256)


class Tuner(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=32, unique=True)
    ipaddr = models.GenericIPAddressField()
    model = models.CharField(max_length=48)
    tuner_count = models.SmallIntegerField()


class Channel(UpdateMixin, CreatedUpdatedModel):
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
    icon = models.URLField(max_length=256, null=True)
    high_definition = models.BooleanField(default=False)

    def __str__(self):
        return '%s (%s)' % (self.name, self.number)

    def __repr__(self):
        return 'Channel: %s' % str(self)


class Library(UpdateMixin, CreatedUpdatedModel):
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


class Series(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=128, unique=True)


class Episode(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    series = models.ForeignKey(
        Series, on_delete=models.CASCADE, related_name='episodes')
    season = models.IntegerField()
    episode_system = models.CharField(max_length=32)
    episode = models.CharField(max_length=32)


class Category(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=128)


class Rating(UpdateMixin, CreatedUpdatedModel):
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


class Program(UpdateMixin, CreatedUpdatedModel):
    class Meta:
        unique_together = (
            ('channel', 'start'),
            ('channel', 'stop'),
        )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name='shows')
    episode = models.ForeignKey(
        Episode, on_delete=models.CASCADE, null=True, related_name='copies')
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, null=True, related_name='shows')
    rating = models.ForeignKey(Rating, on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=256)
    start = models.DateTimeField()
    stop = models.DateTimeField()
    length = models.IntegerField()
    icon = models.URLField(max_length=256, null=True)
    previously_shown = models.BooleanField(default=True)

    def __str__(self):
        return '%s @%s %s' % (self.channel, self.start, self.title,)

    def __repr__(self):
        return 'Show: %s' % str(self)

    objects = ProgramManager()


class Show(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    program = models.OneToOneField(
        Program, on_delete=models.SET_NULL, null=True,
        related_name='airings', unique=True)
    library = models.ForeignKey(
        Library, on_delete=models.CASCADE, related_name='shows')
    path = FilePathField(max_length=256)

    def __str__(self):
        return self.program.title

    def __repr__(self):
        return 'Show: %s' % str(self)

    def generate_path(self):
        '''
        Generate a unique path for this show. Used by DVR, shows not recorded
        by DVR will have a path to the existing video file.
        '''
        self.path = pathjoin(self.library.path, str(self.id))
        os.makedirs(self.path, exist_ok=True)
        self.save(update_fields=['path'])


class ShowMeta(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    show = models.OneToOneField(
        Show, on_delete=models.CASCADE, related_name='meta')


class Stream(UpdateMixin, CreatedUpdatedModel):
    TYPE_HLS = 0

    TYPE_NAMES = {
        TYPE_HLS: 'hls'
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    show = models.OneToOneField(
        Show, on_delete=models.CASCADE, related_name='stream')
    type = models.IntegerField(choices=list(TYPE_NAMES.items()))


class Recording(UpdateMixin, CreatedUpdatedModel):
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

    def is_airing(self, now=None):
        if now is None:
            now = timezone.now()
        return self.start <= now and self.stop >= now

    def is_upcoming(self, now=None):
        if now is None:
            now = timezone.now()
        return now < self.start

    def is_over(self, now=None):
        if now is None:
            now = timezone.now()
        return now >= self.stop


class Artist(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=256)
    icon = models.URLField(max_length=256, null=True)


class Album(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=256)
    icon = models.URLField(max_length=256, null=True)


class Music(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    artist = models.ForeignKey(
        Artist, on_delete=models.CASCADE, related_name='songs')
    album = models.ForeignKey(
        Album, on_delete=models.CASCADE, related_name='songs')
    path = models.FileField()
    library = models.ForeignKey(
        Library, on_delete=models.CASCADE, null=True, related_name='music')


class MusicMeta(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    music = models.OneToOneField(
        Music, on_delete=models.CASCADE, related_name='meta')


class Movie(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=256)
    path = models.FileField()
    library = models.ForeignKey(
        Library, on_delete=models.CASCADE, null=True, related_name='movies')


class MovieMeta(UpdateMixin, CreatedUpdatedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    movie = models.OneToOneField(
        Movie, on_delete=models.CASCADE, related_name='meta')
