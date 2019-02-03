
from django.urls import path
from django.views.generic.base import TemplateView

from main.views import player


urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html')),
    path('player/', player),
]
