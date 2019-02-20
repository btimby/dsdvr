import logging
import errno

from os.path import join as pathjoin
from os.path import splitext

import requests
from requests.exceptions import RequestException

from rest_framework import viewsets

from django.http import FileResponse
from django.shortcuts import get_object_or_404

from api.models import Image
from api.serializers import ImageSerializer

from main import settings


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.NullHandler())


class ImageViewSet(viewsets.ModelViewSet):
    serializer_class = ImageSerializer
    queryset = Image.objects.all()


def image(request, pk):
    image = get_object_or_404(Image, pk=pk)
    _, ext = splitext(image.url)
    image_path = pathjoin(settings.STORAGE_TEMP, 'images', '%s%s' % (pk, ext))

    try:
        image_file = open(image_path, 'rb')

    except IOError as e:
        if e.errno != errno.ENOENT:
            raise

    else:
        return FileResponse(image_file)

    image_file = open(image_path, 'wb+')
    try:
        with requests.get(image.url) as r:
            for data in r.iter_content():
                image_file.write(data)
        image_file.seek(0)

    except RequestException:
        image_file.close()
        raise

    return FileResponse(image_file)
