import logging

from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from rest_framework import views
from rest_framework.decorators import action

from api.models import Tuner
from api.serializers import TunerSerializer
from api.tasks.tuners import TaskTunerDiscover, TaskChannelScan


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class TunerViewSet(viewsets.ModelViewSet):
    serializer_class = TunerSerializer
    queryset = Tuner.objects.all()

    @action(methods=['post'], detail=False)
    def discover(self, request):
        return TaskTunerDiscover().start()


class ChannelScanView(views.APIView):
    def post(self, request, pk=None):
        tuner = get_object_or_404(Tuner, pk=pk)
        return TaskChannelScan(args=(tuner,)).start()
