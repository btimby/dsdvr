from django.urls import path

from rest_framework.routers import DefaultRouter

from api.views.tasks import TaskViewSet
from api.views.tuners import TunerViewSet
from api.views.tuners import TunerScanView
from api.views.recordings import RecordingViewSet
from api.views.guide import GuideViewSet
from api.views.guide import GuideUploadViewSet
from api.views.streams import StreamViewSet
from api.views.streams import playlist, segment
from api.views.libraries import LibraryViewSet
from api.views.shows import ShowViewSet
from api.views.channels import ChannelViewSet


router = DefaultRouter()
router.register('tasks', TaskViewSet, base_name='tasks')
router.register('tuners', TunerViewSet, base_name='tuners')
router.register('recordings', RecordingViewSet, base_name='recordings')
router.register('guide', GuideViewSet, base_name='guide')
router.register('streams', StreamViewSet, base_name='streams')
router.register('libraries', LibraryViewSet, base_name='libraries')
router.register('shows', ShowViewSet, base_name='shows')
router.register('channels', ChannelViewSet, base_name='channels')


urlpatterns = [
    # Custom url patterns here...
    path('streams/<uuid:id>/hls/stream.m3u8', playlist,
         name='streams-playlist'),
    path('streams/<uuid:id>/hls/<name>.ts', segment, name='streams-segment'),

    # Standalone viewset that allows file upload and starts the import task.
    path('guide/upload/', GuideUploadViewSet.as_view({'post': 'create'})),

    # Standalone view that allows scanning a tuner for new channels.
    path('tuners/<uuid:pk>/scan/', TunerScanView.as_view()),

] + router.urls
