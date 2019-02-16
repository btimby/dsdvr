from rest_framework import views
from rest_framework.response import Response

from api.serializers import UserSerializer


class MeView(views.APIView):
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
