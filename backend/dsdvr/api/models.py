import os
import shutil
import uuid
import signal
import logging
import pathlib
import random
import string

from os.path import join as pathjoin
from os.path import isdir, isfile, relpath, dirname, splitext
from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

from constance import config


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


def _get_program_filename(program):
    '''
    Build a filesystem path for the given media item.
    '''
    title = program.title.replace(' ', '.')
    airtime = program.start.strftime('%m-%d-%Y-%H:%M')
    unique = ''.join(
        random.choices(string.ascii_letters + string.digits, k=6))
    return pathjoin(title, airtime, '%s-%s.mpeg' % (title, unique))


class BasePathField(models.CharField):
    def __init__(self, max_length=256, **kwargs):
        self.auto_create = kwargs.pop('auto_create', False)
        self.must_exist = kwargs.pop('must_exist', True)
        self.relative_to = kwargs.pop('relative_to', None)
        super().__init__(max_length=max_length, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.auto_create:
            kwargs['auto_create'] = self.auto_create
        if not self.must_exist:
            kwargs['must_exist'] = self.must_exist
        if self.relative_to is not None:
            kwargs['relative_to'] = self.relative_to
        return name, path, args, kwargs

    def _check_path(self, path):
        raise NotImplemented()

    def _create_path(self, path):
        raise NotImplemented()

    def pre_save(self, model_instance, add):
        path = getattr(model_instance, self.attname)
        abs_path = self.absolute(model_instance)

        # Ensure the path is relative.
        if self.relative_to is not None and path.startswith(self.relative_to):
            path = relpath(path, self.relative_to)

        if not self.null:
            if self.auto_create:
                self._create_path(abs_path)

            if self.must_exist:
                self._check_path(abs_path)

        return path

    def absolute(self, model_instance):
        path = getattr(model_instance, self.attname)

        if self.relative_to is not None:
            path = pathjoin(self.relative_to, path)

        return path


class DirectoryPathField(BasePathField):
    def _check_path(self, path):
        if not isdir(path):
            raise ValueError('Path: %s is not a directory')

    def _create_path(self, path):
        os.makedirs(path, exist_ok=True)


class FilePathField(BasePathField):
    def __init__(self, **kwargs):
        self.auto_create_parent = kwargs.pop('auto_create_parent', False)
        super().__init__(**kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.auto_create_parent:
            kwargs['auto_create_parent'] = self.auto_create_parent
        return name, path, args, kwargs

    def _check_path(self, path):
        if not isfile(path):
            raise ValueError('Path: %s is not a file')

    def _create_path(self, path):
        if self.auto_create_parent or self.auto_create:
            parent = dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)

        if self.auto_create:
            pathlib.Path(path).touch(exist_ok=True)

    def pre_save(self, model_instance, add):
        path = super().pre_save(model_instance, add)
        abs_path = self.absolute(model_instance)

        if self.auto_create_parent:
            self._create_path(abs_path)

        return path


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


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(email=self.normalize_email(email), name=name)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(
            email,
            name,
            password=password,
        )
        user.is_admin = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.EmailField(
        verbose_name='email address',
        max_length=255,
        unique=True,
    )
    name = models.CharField(max_length=255, verbose_name='name')
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = UserManager()

    @property
    def is_staff(self):
        return self.is_admin


class Image(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    url = models.URLField(unique=True)


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


class Tuner(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    device_id = models.IntegerField(unique=True)
    device_ip = models.GenericIPAddressField()
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
    callsign = models.CharField(max_length=32)
    stream = models.CharField(max_length=256, null=True)
    images = models.ManyToManyField(Image, related_name='channels')
    poster = models.ForeignKey(
        Image, null=True, on_delete=models.SET_NULL, related_name='channel_posters')
    hd = models.BooleanField(default=False)

    def __str__(self):
        return '%s (%s)' % (self.name, self.number)

    def __repr__(self):
        return 'Channel: %s' % str(self)


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=16)


class MediaActor(UpdateMixin, CreatedModifiedModel):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    media = models.ForeignKey('Media', on_delete=models.CASCADE)


class ProgramActor(UpdateMixin, CreatedModifiedModel):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    program = models.ForeignKey('Program', on_delete=models.CASCADE)


class Rating(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=16)


class Category(UpdateMixin, CreatedModifiedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=128)


class MediaManager(DefaultTypeManager):
    def get_or_create_from_program(self, program, **kwargs):
        defaults = kwargs.copy()
        defaults.update({
            'title': program.title,
            'subtitle': program.subtitle,
            'desc': program.desc,
            'duration': program.duration,
            'rating': program.rating,
            'poster': program.poster,
        })

        # Generate a path for this program. It will be relative to the media
        # path.
        if 'path' not in defaults:
            defaults['path'] = _get_program_filename(program)

        # If the program guide placed the program into "Movie" category, then
        # we want the appropriate media type.
        media_class = Show
        for cat in program.categories.all():
            if cat.name.lower() == 'movie':
                media_class = Movie
                break

        media, created = media_class.objects.get_or_create(
            program=program, defaults=defaults)

        if created:
            media.update(**defaults)

            for actor in program.actors.all():
                MediaActor.objects.get_or_create(
                    media=media, person=actor.person)

            media.images.add(*program.images.all())
            media.categories.add(*program.categories.all())

        return media, created


class Media(UpdateMixin, CreatedModifiedModel):
    TYPE_MOVIE = 0
    TYPE_SERIES = 1
    TYPE_SHOW = 2

    TYPE_NAMES = {
        TYPE_MOVIE: 'Movie',
        TYPE_SERIES: 'Series',
        TYPE_SHOW: 'Show',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    type = models.SmallIntegerField(choices=list(TYPE_NAMES.items()))
    title = models.CharField(max_length=256)
    subtitle = models.CharField(max_length=256)
    desc = models.TextField()
    images = models.ManyToManyField(Image, related_name='media')
    poster = models.ForeignKey(
        Image, null=True, on_delete=models.SET_NULL, related_name='media_posters')
    categories = models.ManyToManyField(Category, related_name='media')
    rating = models.ForeignKey(Rating, on_delete=models.CASCADE, null=True)
    year = models.SmallIntegerField(null=True)
    actors = models.ManyToManyField(Person, through='MediaActor')

    objects = MediaManager()

    def subtype_model(self):
        if self.type == Media.TYPE_MOVIE:
            return Movie

        elif self.type == Media.TYPE_SHOW:
            return Show

        elif self.type == Media.TYPE_SERIES:
            return Series

        else:
            raise ValueError(
                'Unsupported media type %s', Media.TYPE_NAMES[self.type])

    def subtype(self):
        if self.type == Media.TYPE_MOVIE:
            return self.movie

        elif self.type == Media.TYPE_SHOW:
            return self.show

        elif self.type == Media.TYPE_SERIES:
            return self.series

        else:
            raise ValueError(
                'Unsupported media type %s', Media.TYPE_NAMES[self.type])

    @cached_property
    def abs_path(self):
        return self.subtype().abs_path

    @cached_property
    def frame0_path(self):
        return '%s-frame0.jpg' % splitext(self.abs_path)[0]


class SeriesManager(DefaultTypeManager):
    DEFAULT_TYPE = Media.TYPE_SERIES


class Series(Media):
    objects = SeriesManager()

    def subtype(self):
        return self


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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    program_id = models.CharField(max_length=32, unique=True)
    season = models.PositiveSmallIntegerField(null=True)
    episode = models.PositiveSmallIntegerField(null=True)
    categories = models.ManyToManyField(Category, related_name='programs')
    actors = models.ManyToManyField(Person, through='ProgramActor')
    title = models.CharField(max_length=256)
    subtitle = models.CharField(null=True,max_length=256)
    desc = models.TextField(null=True)
    images = models.ManyToManyField(Image, related_name='programs')
    poster = models.ForeignKey(
        Image, null=True, on_delete=models.SET_NULL,
        related_name='program_posters')
    previously_shown = models.BooleanField(default=True)

    def __str__(self):
        return '%s @%s %s' % (self.channel, self.start, self.title,)

    def __repr__(self):
        return 'Show: %s' % str(self)

    objects = ProgramManager()


class Schedule(UpdateMixin, models.Model):
    class Meta:
        unique_together = (
            ('channel', 'start'),
            ('channel', 'stop'),
        )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name='programs')
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name='schedules')    
    rating = models.ForeignKey(Rating, on_delete=models.CASCADE, null=True)
    start = models.DateTimeField()
    stop = models.DateTimeField()
    duration = models.IntegerField()


class ShowManager(DefaultTypeManager):
    DEFAULT_TYPE = Media.TYPE_SHOW


class Episode(UpdateMixin, models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE)
    show = models.OneToOneField('Show', on_delete=models.CASCADE)
    season = models.PositiveSmallIntegerField(null=True)
    episode = models.PositiveSmallIntegerField(null=True)


class Show(Media):
    program = models.OneToOneField(
        Program, on_delete=models.SET_NULL, null=True, related_name='shows')
    series = models.ManyToManyField(Series, through=Episode)
    width = models.SmallIntegerField(null=True)
    height = models.SmallIntegerField(null=True)
    video_enc = models.CharField(null=True, max_length=32)
    size = models.IntegerField(null=True)
    audio_enc = models.CharField(null=True, max_length=32)
    duration = models.DecimalField(null=True, max_digits=12, decimal_places=6)
    format = models.CharField(null=True, max_length=32)
    play_count = models.IntegerField(default=0)
    path = FilePathField(
        max_length=256, must_exist=False, auto_create_parent=True,
        auto_create=False, relative_to=config.STORAGE_MEDIA)

    def __str__(self):
        return self.program.title

    def __repr__(self):
        return 'Show: %s' % str(self)

    @cached_property
    def abs_path(self):
        return self._meta.get_field('path').absolute(self)

    def subtype(self):
        return self

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

    def delete(self, *args, **kwargs):
        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGINT)

            except ProcessLookupError as e:
                LOGGER.warning(e, exc_info=True)

        if self.path is not None:
            shutil.rmtree(self.path, ignore_errors=True)

        return super().delete(*args, **kwargs)


class DeviceCursor(UpdateMixin, models.Model):
    class Meta:
        unique_together = [
            ('device', 'cursor'),
        ]

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name='devicecursor')
    stream = models.ForeignKey(
        Stream, on_delete=models.CASCADE, related_name='devicecursor')
    cursor = models.DecimalField(max_digits=12, decimal_places=6, default=0.0)


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
    media = models.OneToOneField(
        Media, null=True, on_delete=models.CASCADE, related_name='recording')
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


class MovieManager(DefaultTypeManager):
    DEFAULT_TYPE = Media.TYPE_MOVIE


class Movie(Media):
    program = models.OneToOneField(
        Program, on_delete=models.SET_NULL, null=True, related_name='movies')
    width = models.SmallIntegerField(null=True)
    height = models.SmallIntegerField(null=True)
    video_enc = models.CharField(null=True, max_length=32)
    size = models.IntegerField(null=True)
    audio_enc = models.CharField(null=True, max_length=32)
    duration = models.DecimalField(null=True, max_digits=12, decimal_places=6)
    format = models.CharField(null=True, max_length=32)
    play_count = models.IntegerField(default=0)
    path = FilePathField(
        max_length=256, must_exist=False, auto_create_parent=True,
        auto_create=False, relative_to=config.STORAGE_MEDIA)

    objects = MovieManager()

    @cached_property
    def abs_path(self):
        return self._meta.get_field('path').absolute(self)

    def subtype(self):
        return self
