import logging
import os.path

from collections import OrderedDict

from django.utils import timezone
from django.db import models
from django.db.transaction import atomic
from django.urls import reverse, resolve, Resolver404

from rest_framework import serializers
from drf_queryfields import QueryFieldsMixin

from api.models import (
    Show, Recording, Program, Channel, Library, Tuner, Device, Rating,
    Category, Movie, Stream, Media, Series, Person, DeviceCursor
)
from api.tasks import STATUS_NAMES
from api.tasks.recordings import TaskRecordingManager


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class DisplayChoiceField(serializers.ChoiceField):

    def __init__(self, *args, **kwargs):
        choices = kwargs.get('choices')
        self._choices = OrderedDict(choices)
        super(DisplayChoiceField, self).__init__(*args, **kwargs)

    def to_representation(self, obj):
        """Used while retrieving value for the field."""
        return self._choices[obj]


class ProgramRelatedField(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ('id', 'title', 'start', 'stop', 'duration', 'poster',
                  'previously_shown', 'channel', 'season', 'episode',
                  'category', 'rating')
        read_only_fields = ('title', 'start', 'stop', 'duration', 'poster',
                            'previously_shown', 'channel', 'season', 'episode',
                            'category', 'rating')

    channel = serializers.StringRelatedField(read_only=True)
    category = serializers.SlugRelatedField(
        read_only=True, slug_field='name')
    rating = serializers.SlugRelatedField(
        read_only=True, slug_field='name')


class MediaRelatedField(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = ('id', 'type', 'library', 'path', 'title', 'duration',
                  'poster', 'category', 'rating')
        read_only_fields = ('type', 'library', 'path', 'title', 'duration',
                            'poster', 'category', 'rating')

    library = serializers.StringRelatedField(read_only=True)
    category = serializers.SlugRelatedField(
        read_only=True, slug_field='name')
    rating = serializers.SlugRelatedField(
        read_only=True, slug_field='name')


class ShowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Show
        fields = '__all__'
        read_only_fields = ('id', 'path')

    library = serializers.SlugRelatedField(read_only=True, slug_field='name')
    rating = serializers.SlugRelatedField(read_only=True, slug_field='name')
    category = serializers.SlugRelatedField(read_only=True, slug_field='name')
    type = DisplayChoiceField(
        choices=list(Show.TYPE_NAMES.items()), read_only=True)
    path = serializers.SerializerMethodField()

    def get_path(self, obj):
        return obj.abs_path


class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = '__all__'
        read_only_fields = ('id', 'path')

    library = serializers.SlugRelatedField(read_only=True, slug_field='name')
    rating = serializers.SlugRelatedField(read_only=True, slug_field='name')
    category = serializers.SlugRelatedField(read_only=True, slug_field='name')
    type = DisplayChoiceField(
        choices=list(Show.TYPE_NAMES.items()), read_only=True)
    path = serializers.SerializerMethodField()

    def get_path(self, obj):
        return obj.abs_path


class SeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Series
        fields = '__all__'
        read_only_fields = ('id', 'path')

    library = serializers.SlugRelatedField(read_only=True, slug_field='name')
    rating = serializers.SlugRelatedField(read_only=True, slug_field='name')
    category = serializers.SlugRelatedField(read_only=True, slug_field='name')
    type = DisplayChoiceField(
        choices=list(Show.TYPE_NAMES.items()), read_only=True)


class RecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recording
        fields = ('id', 'start', 'stop', 'status', 'show', 'program', 'pid')
        read_only_fields = ('id', 'status', 'pid')
        extra_kwargs = {
            'start': {'required': False},
            'stop': {'required': False},
        }

    show = ShowSerializer(read_only=True)
    status = DisplayChoiceField(
        choices=list(Recording.STATUS_NAMES.items()), read_only=True)
    program = ProgramRelatedField()

    def _validate_tuner(self, data):
        # Find out what is recording during this time slot.
        start, stop = data['start'], data['stop']
        q1 = models.Q(
            channels__programs__recording__start__gt=start,
            channels__programs__recording__start__lt=stop)
        q2 = models.Q(
            channels__programs__recording__stop__gt=start,
            channels__programs__recording__stop__lt=stop)
        tuners = Tuner.objects.filter(q1 | q2) \
            .values_list('id', 'tuner_count')

        if not tuners:
            return

        # Get the tuner id that will be used for the requested recording.
        tuner_id = data['program'].channel.tuner_id

        # Holds recording count for each tuner.    
        trecs = {
            # Account for the recording we are trying to create.
            tuner_id: 1,
        }

        for id, tcount in tuners:
            # Count recordings on the tuners.
            trec = trecs[id] = trecs.get(id, 0) + 1

            # If recordings exceed available tuners, fail validation.
            if trec > tcount:
                raise serializers.ValidationError(
                    'Cannot exceed tuner count. Tuner: %s has %i tuners, all '
                    'of them in use at the requested time.' % (id, tcount))

    def validate(self, data):
        # Define start and stop from show if not provided.
        if 'start' not in data:
            data['start'] = data['program'].start
        if 'stop' not in data:
            data['stop'] = data['program'].stop

        # Validate start and stop times.
        if data['start'] >= data['stop']:
            raise serializers.ValidationError('Start must occur before stop')
        if data['stop'] < timezone.now():
            raise serializers.ValidationError('Program has ended')

        self._validate_tuner(data)

        return data

    def to_internal_value(self, data):
        ret = OrderedDict()

        try:
            ret['program'] = Program.objects.get(pk=data['program.id'])

        except Program.DoesNotExist:
            raise serializers.ValidationError(
                'Invalid program.id: %s' % data['program.id'])

        return ret

    @atomic
    def create(self, validated_data):
        recording = super().create(validated_data)

        # Start this task to potentially start a recording right away.
        TaskRecordingManager().start()

        return recording


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = '__all__'
        read_only_fields = ('id', )

    recording = serializers.PrimaryKeyRelatedField(read_only=True)
    rating = serializers.SlugRelatedField(read_only=True, slug_field='name')
    category = serializers.SlugRelatedField(read_only=True, slug_field='name')


class GuideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = '__all__'

    programs = serializers.SerializerMethodField()

    def get_programs(self, obj):
        # TODO: add filtering.
        queryset = Program.objects.get_upcoming()
        queryset = queryset.filter(channel=obj)

        serializer = ProgramSerializer(instance=queryset, many=True)
        return serializer.data


class TaskSerializer(serializers.Serializer):
    '''
    Serializer for ephemeral tasks.
    '''

    id = serializers.UUIDField()
    name = serializers.SerializerMethodField()
    done = serializers.IntegerField()
    total = serializers.IntegerField()
    summary = serializers.CharField()
    created = serializers.DateTimeField()
    modified = serializers.DateTimeField()
    status = DisplayChoiceField(choices=list(STATUS_NAMES.items()))
    percent = serializers.IntegerField()
    elapsed = serializers.IntegerField()
    remaining = serializers.IntegerField()

    def get_name(self, obj):
        return obj.__class__.__name__


class MediaSerializer(serializers.ModelSerializer):
    '''
    Uses proper serializer for media type.
    '''
    class Meta:
        model = Media
        fields = '__all__'
        read_only_fields = ('id', 'path')

    serializer_classes = {
        Media.TYPE_SHOW: ('show', ShowSerializer),
        Media.TYPE_MOVIE: ('movie', MovieSerializer),
        Media.TYPE_SERIES: ('series', SeriesSerializer),
    }

    path = serializers.SerializerMethodField()

    def get_path(self, obj):
        return obj.abs_path

    def to_representation(self, data):
        attrname, serializer_class = self.serializer_classes[data.type]
        return serializer_class(getattr(data, attrname)).data


class LibrarySerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = '__all__'
        read_only_fields = ('id',)

    type = DisplayChoiceField(choices=list(Library.TYPE_NAMES.items()))
    media = serializers.ListSerializer(read_only=True, child=MediaSerializer())


class MediaRelatedField(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = ('id', 'library')

    library = serializers.SlugRelatedField(read_only=True, slug_field='name')


class GuideUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class TunerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tuner
        fields = '__all__'
        read_only_fields = ('id',)


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'
        read_only_fields = ('id',)


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = '__all__'
        read_only_fields = ('id',)


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = '__all__'
        read_only_fields = ('id',)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ('id',)


class CursorField(serializers.DecimalField):
    getter_name = 'get_cursor'
    setter_name = 'set_cursor'

    def __init__(self, method_name=None, **kwargs):
        kwargs['source'] = '*'
        super(CursorField, self).__init__(**kwargs)

    def to_representation(self, value):
        method = getattr(self.parent, 'get_cursor')
        value = method(value)
        return value

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return {'cursor': value}


class StreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stream
        fields = '__all__'
        read_only_fields = ('id', 'pid', 'path')

    type = DisplayChoiceField(
        choices=list(Stream.TYPE_NAMES.items()))
    url = serializers.SerializerMethodField()
    cursor = CursorField(max_digits=12, decimal_places=6, required=False)

    # NOTE: this seems a bit hacky, but the create() and update() overrides
    # Allow for a writable SerializerMethodField().
    def create(self, validated_data):
        cursor = validated_data.pop('cursor', None)
        obj = super().create(validated_data)
        self._set_devicecursor(obj, cursor)
        return obj

    def update(self, instance, validated_data):
        cursor = validated_data.pop('cursor', None)
        obj = super().update(instance, validated_data)
        self._set_devicecursor(obj, cursor)
        return obj

    def get_url(self, obj):
        url = reverse('streams-playlist', args=[obj.id])

        try:
            url = self.context['request'].build_absolute_uri(url)

        except KeyError:
            pass

        return url

    def get_cursor(self, obj):
        try:
            request = self.context['request']

        except KeyError as e:
            LOGGER.warning(e, exc_info=True)
            return

        try:
            dc = DeviceCursor.objects.get(stream=obj, device=request.device)
            return dc.cursor

        except DeviceCursor.DoesNotExist:
            return 0.0

    def _set_devicecursor(self, obj, cursor):
        if cursor is None:
            return

        try:
            request = self.context['request']

        except KeyError as e:
            LOGGER.warning(e, exc_info=True)
            return

        dc, _ = DeviceCursor.objects.get_or_create(
            stream=obj, device=request.device)
        dc.update(cursor=cursor)


class SeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Series
        fields = '__all__'
        read_only_fields = ('id',)
