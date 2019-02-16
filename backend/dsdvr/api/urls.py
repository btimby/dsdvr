from django.urls import path

from rest_framework_simplejwt import views as simplejwt
from rest_framework.routers import DefaultRouter

from api.views.tasks import TaskViewSet
from api.views.tuners import TunerViewSet
from api.views.tuners import TunerScanView
from api.views.recordings import RecordingViewSet
from api.views.guide import GuideViewSet
from api.views.guide import GuideUploadViewSet
from api.views.streams import StreamViewSet
from api.views.streams import playlist, segment
from api.views.shows import ShowViewSet
from api.views.channels import ChannelViewSet
from api.views.devices import DeviceViewSet
from api.views.people import PersonViewSet
from api.views.ratings import RatingViewSet
from api.views.categories import CategoryViewSet
from api.views.movies import MovieViewSet
from api.views.programs import ProgramViewSet
from api.views.media import MediaViewSet, MediaStreamViewSet, poster, frame0
from api.views.series import SeriesViewSet
from api.views.me import MeView


router = DefaultRouter()
router.register('tasks', TaskViewSet, base_name='tasks')
router.register('tuners', TunerViewSet, base_name='tuners')
router.register('recordings', RecordingViewSet, base_name='recordings')
router.register('guide', GuideViewSet, base_name='guide')
router.register('streams', StreamViewSet, base_name='streams')
router.register('shows', ShowViewSet, base_name='shows')
router.register('movies', MovieViewSet, base_name='movies')
router.register('channels', ChannelViewSet, base_name='channels')
router.register('devices', DeviceViewSet, base_name='devices')
router.register('people', PersonViewSet, base_name='people')
router.register('ratings', RatingViewSet, base_name='ratings')
router.register('categories', CategoryViewSet, base_name='categories')
router.register('programs', ProgramViewSet, base_name='programs')
router.register('media', MediaViewSet, base_name='media')
router.register('series', SeriesViewSet, base_name='series')


urlpatterns = [
    # Custom url patterns here...
    path('streams/<uuid:pk>/hls/stream.m3u8', playlist,
         name='streams-playlist'),
    # NOTE: slug is import here. It prevents path traversal chars, yet allows
    # the chars we expect to see as segment file names.
    path('streams/<uuid:pk>/hls/<slug:name>.ts', segment,
         name='streams-segment'),

    # Standalone viewset that allows file upload and starts the import task.
    path('guide/upload/', GuideUploadViewSet.as_view({'post': 'create'})),

    # Standalone view that allows scanning a tuner for new channels.
    path('tuners/<uuid:pk>/scan/', TunerScanView.as_view()),

    # Standalone view that manages media streams.
    path('media/<uuid:pk>/stream/', MediaStreamViewSet.as_view({
        'get': 'retrieve',
        'patch': 'partial_update',
        'post': 'create',
        'delete': 'destroy',
    })),

    path('media/<uuid:pk>/poster.jpg', poster, name='media-poster'),
    path('media/<uuid:pk>/frame0.jpg', frame0, name='media-frame0'),

    # Authentication
    path(
        'token/', simplejwt.TokenObtainPairView.as_view(),
        name='token_obtain_pair'),
    path(
        'token/refresh/', simplejwt.TokenRefreshView.as_view(),
        name='token_refresh'),

    path('me/', MeView.as_view(), name='me'),

] + router.urls
