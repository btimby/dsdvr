from django.shortcuts import render_to_response


def player(request):
    stream = request.GET.get('stream')
    return render_to_response('player.html', {'stream': stream})
