import os.path

from collections import OrderedDict

from django.utils import timezone
from django.db.transaction import atomic

from rest_framework import serializers

from api.models import Episode, Show, Recording, Program, Channel, Library
from api.tasks import STATUS_NAMES
from api.tasks.recordings import RecordingControl


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
        fields = ('id', 'title', 'start', 'stop', 'length', 'icon',
                  'previously_shown', 'channel', 'episode', 'category',
                  'rating')
        read_only_fields = ('title', 'start', 'stop', 'length', 'icon',
                            'previously_shown', 'channel', 'episode',
                            'category', 'rating')

    channel = serializers.StringRelatedField(read_only=True)
    episode = serializers.StringRelatedField(read_only=True)
    category = serializers.SlugRelatedField(
        read_only=True, slug_field='name')
    rating = serializers.SlugRelatedField(
        read_only=True, slug_field='name')


class ShowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Show
        fields = '__all__'
        read_only_fields = ('id',)

    program = ProgramRelatedField(read_only=True)
    library = serializers.SlugRelatedField(read_only=True, slug_field='name')


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
        fields = ('id', 'recording', 'episode', 'rating', 'category', 'title',
                  'start', 'stop', 'length', 'icon', 'previously_shown')

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


class LibrarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = '__all__'
        read_only_fields = ('id',)

    type = DisplayChoiceField(choices=list(Library.TYPE_NAMES.items()))

    def validate(self, data):
        if not os.path.isdir(data['path']):
            raise serializers.ValidationError(
                '%s is not a directory' % data['path'])
        return data


class ShowRelatedField(serializers.ModelSerializer):
    class Meta:
        model = Show
        fields = ('id', 'program', 'library')

    program = serializers.SlugRelatedField(read_only=True, slug_field='title')
    library = serializers.SlugRelatedField(read_only=True, slug_field='name')


class StreamSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    show = ShowRelatedField()
    url = serializers.URLField(read_only=True)
    path = serializers.CharField(read_only=True)

    def to_internal_value(self, data):
        ret = OrderedDict()

        try:
            ret['show'] = Show.objects.get(pk=data['show.id'])

        except Show.DoesNotExist:
            raise serializers.ValidationError(
                'Invalid show.id: %s' % data['show.id'])

        return ret

    def create(self, validated_data):
        from api.views.streams import Stream
        return Stream(validated_data['show'])


class GuideUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
