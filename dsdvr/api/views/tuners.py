import logging

from django.shortcuts import get_object_or_404

from rest_framework import serializers
from rest_framework import viewsets
from rest_framework import views
from rest_framework.decorators import action

from api.models import Tuner
from api.tasks.tuners import TunerDiscoverTask, TunerScanTask


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class TunerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tuner
        fields = '__all__'
        read_only_fields = ('id',)


class TunerViewSet(viewsets.ModelViewSet):
    serializer_class = TunerSerializer
    queryset = Tuner.objects.all()

    @action(methods=['post'], detail=False)
    def discover(self, request):
        return TunerDiscoverTask().start()


class TunerScanView(views.APIView):
    def post(self, request, pk=None):
        tuner = get_object_or_404(Tuner, pk=pk)
        return TunerScanTask(args=(tuner,)).start()
