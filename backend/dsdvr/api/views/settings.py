from django.conf import settings

from rest_framework import viewsets
from rest_framework.serializers import ValidationError
from rest_framework.response import Response

from constance import config


class SettingViewSet(viewsets.ViewSet):
    def get_settings(self):
        return {
            key: options for key, options in
            getattr(settings, 'CONSTANCE_CONFIG', {}).items()
        }

    def create(self, request):
        settings = self.get_settings()
        for key in request.data:
            if key not in settings:
                raise ValidationError('Invalid setting name: %s' % key)
            setattr(config, key, request.data[key])
        return Response({
            key: getattr(config, key) for key in settings
        })

    def list(self, request):
        settings = self.get_settings()
        return Response({
            key: getattr(config, key) for key in settings
        })
