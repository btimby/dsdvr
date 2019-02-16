from ua_parser import user_agent_parser

from django.utils import timezone
from django.db.transaction import atomic

from api.models import Device


def flatten(d):
    flat = {}
    for key, value in d.items():
        if hasattr(value, 'items'):
            for subkey, value in flatten(value).items():
                flat['%s_%s' % (key, subkey)] = value
        
        else:
            flat[key] = value
    return flat


class DeviceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', None)
        if user_agent is not None:
            flat = flatten(user_agent_parser.Parse(user_agent))
            defaults = {k: v for k, v in flat.items() if k != 'string'}

            with atomic(immediate=True):
                device, created = Device.objects.get_or_create(
                    user_agent=user_agent, defaults=defaults)

                if not created:
                    device.update(
                        last_ip_address=request.META.get('REMOTE_ADDR', None),
                        modified=timezone.now())  # Not sure this is necessary.

        return self.get_response(request)
