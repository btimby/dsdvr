from rest_framework import serializers, viewsets

from api.models import Show
from api.serializers import ShowSerializer


class ShowViewSet(viewsets.ModelViewSet):
    serializer_class = ShowSerializer
    queryset = Show.objects.all()
