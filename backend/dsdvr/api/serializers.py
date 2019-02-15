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
    Episode, Show, Recording, Program, Channel, Library, Tuner, Device, Actor,
    Rating, Category, Movie, Music, Stream, Media,
)
from api.tasks import STATUS_NAMES
from api.tasks.recordings import RecordingControl


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


class EpisodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Episode
        fields = '__all__'


class ProgramRelatedField(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ('id', 'title', 'start', 'stop', 'duration', 'poster',
                  'previously_shown', 'channel', 'episode', 'category',
                  'rating')
        read_only_fields = ('title', 'start', 'stop', 'duration', 'poster',
                            'previously_shown', 'channel', 'episode',
                            'category', 'rating')

    channel = serializers.StringRelatedField(read_only=True)
    episode = serializers.StringRelatedField(read_only=True)
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


class MusicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Music
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
        RecordingControl(recording).control()

        return recording


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = '__all__'
        read_only_fields = ('id', )

    recording = serializers.PrimaryKeyRelatedField(read_only=True)
    episode = EpisodeSerializer()
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
        Media.TYPE_SHOW: ShowSerializer,
        Media.TYPE_MOVIE: MovieSerializer,
        Media.TYPE_MUSIC: MusicSerializer,
    }

    def to_representation(self, data):
        return self.serializer_classes[data.type](data).data


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


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
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


class StreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stream
        fields = '__all__'
        read_only_fields = ('id', 'pid', 'path')
        extra_kwargs = {
            'resume_seconds': {'required': False},
        }

    type = DisplayChoiceField(
        choices=list(Stream.TYPE_NAMES.items()))
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        url = reverse('streams-playlist', args=[obj.id])

        try:
            url = self.context['request'].build_absolute_uri(url)

        except KeyError:
            pass

        return url
