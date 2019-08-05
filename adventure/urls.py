from django.conf.urls import url
from . import api

urlpatterns = [
    url('join', api.joinlobby),
    url('init', api.initialize),
    url('move', api.move),
    url('say', api.say),
    url('shout', api.shout),
    url('end', api.end),
    url('get_maze', api.get_maze),
]