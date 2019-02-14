from django.utils import timezone

from api.models import Device


class DeviceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', None)
        if user_agent is not None:
            device, created = Device.objects.get_or_create(user_agent=user_agent)

            if not created:
                device.update(
                    last_ip_address=request.META.get('REMOTE_ADDR', None),
                    modified=timezone.now())  # Not sure this is necessary...

        return self.get_response(request)
