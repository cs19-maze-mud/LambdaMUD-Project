from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict
from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework.decorators import api_view
from pusher import Pusher
from decouple import config
from .models import *
import json
import sys

# instantiate pusher
pusher = Pusher(
    app_id=config('PUSHER_APP_ID'),
    key=config('PUSHER_KEY'),
    secret=config('PUSHER_SECRET'),
    cluster=config('PUSHER_CLUSTER'),
    ssl=True,
)


@csrf_exempt
@api_view(['GET'])
def initialize(request):
    player = request.user.player
    player_id = player.user.id
    game = player.game()

    if game is not None:
        game.in_progress = True
        game.save()
    else:
        return JsonResponse({'message': 'Game has ended please join a new lobby'}, safe=True)

    current_room = player.room()
    rooms_list = game.all_rooms()
    uuids = current_room.player_UUIDs(player_id)

    response_object = {
        'user': {
            'uuid': player.uuid,
            'username': player.user.username,
        },
        'game': {
            'id': game.id,
            'in_progress': game.in_progress,
            'uuids': uuids,
            'usernames': current_room.player_usernames(player_id),
            'num_players': len(uuids) + 1
        },
        'current_room': {
            'title': current_room.title,
            'description': current_room.description,
            'visited': current_room.visited,
            'end': current_room.end,
            'players': current_room.player_usernames(player_id),
            'loc': current_room.id,
            'n': current_room.n,
            's': current_room.s,
            'e': current_room.e,
            'w': current_room.w,
        },
        'maze': rooms_list
    }

    for p_uuid in uuids:
        pusher.trigger(
            f'p-channel-{p_uuid}', u'broadcast', {'message': f'game starting', 'init': 'Game initializing'})

    return JsonResponse(response_object, safe=True)


@csrf_exempt
@api_view(['GET'])
def joinlobby(request):

    no_preference = False
    try:
        columns_given = request.query_params.get('columns')
        columns = int(columns_given)
        if columns > 10:
            columns = 10
        elif columns < 2:
            columns = 2
    except:
        columns = 5
        no_preference = True

    user = request.user
    player = user.player
    player_id = player.user.id
    uuid = player.uuid
    existing_game = player.game()

    if existing_game is not None:
        current_room = player.room()
        rooms_list = existing_game.all_rooms()

        return JsonResponse({
        'user': {
            'uuid': player.uuid,
            'username': player.user.username,
        },
        'game': {
            'id': existing_game.id,
            'in_progress': existing_game.in_progress,
            'uuids': current_room.player_UUIDs(player_id),
            'usernames': current_room.player_usernames(player_id),
            'num_players': existing_game.num_players()
        },
        'current_room': {
            'title': current_room.title,
            'description': current_room.description,
            'visited': current_room.visited,
            'end': current_room.end,
            'players': current_room.player_usernames(player_id),
            'loc': current_room.id,
            'n': current_room.n,
            's': current_room.s,
            'e': current_room.e,
            'w': current_room.w,
        },
        'maze': rooms_list
    }, safe=True)

    if no_preference and Game.objects.filter(in_progress=False):
        new_game = Game.objects.get(in_progress=False)
    elif Game.objects.filter(in_progress=False, map_columns=columns):
        # Todo: If player already joined the lobby will this break??
        # It only calls player.initialize(new_game.id, new_game.min_room_id) so maybe not???
        new_game = Game.objects.get(in_progress=False)
    else:
        new_game = Game(map_columns=columns, in_progress=False)
        new_game.generate_rooms()
        new_game.generate_maze()
        new_game.generate_ending()

    for p_uuid in new_game.get_games_UUIDs(uuid):
        pusher.trigger(f'p-channel-{p_uuid}', u'broadcast',
                       {'message': f'{player.user.username} has entered the lobby', 'joining': 'joining lobby'})
    player.initialize(new_game.id, new_game.min_room_id)
    player.save()
    current_room = player.room()
    rooms_list = new_game.all_rooms()

    return JsonResponse({
        'user': {
            'uuid': player.uuid,
            'username': player.user.username,
        },
        'game': {
            'id': new_game.id,
            'in_progress': new_game.in_progress,
            'uuids': current_room.player_UUIDs(player_id),
            'usernames': current_room.player_usernames(player_id),
            'num_players': new_game.num_players()
        },
        'current_room': {
            'title': current_room.title,
            'description': current_room.description,
            'visited': current_room.visited,
            'end': current_room.end,
            'players': current_room.player_usernames(player_id),
            'loc': current_room.id,
            'n': current_room.n,
            's': current_room.s,
            'e': current_room.e,
            'w': current_room.w,
        },
        'maze': rooms_list
    }, safe=True)


@csrf_exempt
@api_view(['POST'])
def move(request):
    dirs = {'n': 'north', 's': 'south', 'e': 'east', 'w': 'west'}
    direction = json.loads(request.body)['direction'].lower()

    if direction not in dirs.keys():
        return JsonResponse({
            'in_progress': True,
            'error': True,
            'message': 'Invalid Direction'}, safe=True)
    else:
        player = request.user.player
        room = player.room()
        if room:
            next_room_id = model_to_dict(room).get(direction, -1)
        else:
            return JsonResponse({
                'in_progress': False,
                'error': True,
                'message': 'The game has already ended! Someone found the end of the maze!!'
            }, safe=True)

    reverse_dirs = {'n': 'south', 's': 'north', 'e': 'west', 'w': 'east'}
    player_id = player.user.id
    player_uuid = player.uuid
    current_game = player.game()

    if current_game and current_game.in_progress and next_room_id != -1:
        next_room = Room.objects.get(id=next_room_id)
        player.moves += 1

        if next_room.end:
            player_uuid = player.uuid
            for p_uuid in current_game.get_games_UUIDs(player_uuid):
                pusher.trigger(f'p-channel-{p_uuid}', u'broadcast',
                               {'message': f'{player.user.username} has completed the maze', 'ending': 'maze completed'})
            min_room_id = current_game.min_room_id
            max_room_id = min_room_id+current_game.num_rooms()-1
            current_game.reset_players()
            Room.objects.filter(id__gte=min_room_id,
                                id__lte=max_room_id).delete()
            Game.objects.filter(id=current_game.id).delete()

            return JsonResponse({
                'in_progress': False,
                'error': False,
                'message': 'Congratulations! You found the end of the maze!!'}, safe=True)
        else:
            player.current_room = next_room_id
            player.save()
            next_room.visited = True
            next_room.save()
            players = next_room.player_usernames(player_id)
            current_player_UUIDs = room.player_UUIDs(player_id)
            next_player_UUIDs = next_room.player_UUIDs(player_id)
            for p_uuid in current_player_UUIDs:
                pusher.trigger(f'p-channel-{p_uuid}', u'broadcast', {
                               'message': f'{player.user.username} has walked {dirs[direction]}.'})
            for p_uuid in next_player_UUIDs:
                pusher.trigger(f'p-channel-{p_uuid}', u'broadcast', {
                               'message': f'{player.user.username} has entered from the {reverse_dirs[direction]}.'})
            return JsonResponse({
                'name': player.user.username,
                'title': next_room.title,
                'description': next_room.description,
                'players': players,
                'num_players': current_game.num_players(),
                'loc': next_room.id,
                'n': next_room.n,
                's': next_room.s,
                'e': next_room.e,
                'w': next_room.w,
                'moves': player.moves,
                'in_progress': True,
                'error': False}, safe=True)
    elif current_game == None:
        return JsonResponse({
            'in_progress': False,
            'error': True,
            'message': 'The game has already ended! Someone found their way to the end of the maze!!'
        }, safe=True)
    elif not current_game.in_progress:
        return JsonResponse({
            'in_progress': False,
            'error': True,
            'message': 'Game has not started yet'
        }, safe=True)
    else:
        players = room.player_usernames(player_id)
        return JsonResponse({
            'in_progress': True,
            'name': player.user.username,
            'title': room.title,
            'description': room.description,
            'players': players,
            'num_players': current_game.num_players(),
            'loc': room.id,
            'n': room.n,
            's': room.s,
            'e': room.e,
            'w': room.w,
            'error': True,
            'message': 'You cannot move that way.'
        }, safe=True)


@csrf_exempt
@api_view(['POST'])
def say(request):
    player = request.user.player
    player_id = player.user.id
    player_uuid = player.uuid
    data = json.loads(request.body)
    message = data['message']
    room = player.room()
    player_UUIDs = room.player_UUIDs(player_id)
    print("UUIDS: ", player_UUIDs)
    for p_uuid in player_UUIDs:
        pusher.trigger(f'p-channel-{p_uuid}', u'broadcast',
                       {'message': f'{player.user.username}: {message}'})

    players = room.player_usernames(player_uuid)
    return JsonResponse({'message': message}, safe=True)


@csrf_exempt
@api_view(['POST'])
def shout(request):
    player = request.user.player
    player_uuid = player.uuid
    data = json.loads(request.body)
    message = data['message']
    game = player.game()
    for p_uuid in game.get_games_UUIDs(player_uuid):
        pusher.trigger(f'p-channel-{p_uuid}', u'broadcast',
                       {'message': f'{player.user.username}: {message}'})
    return JsonResponse({'message_to_channel': message}, safe=True)


@csrf_exempt
@api_view(['GET'])
def end(request):
    player = request.user.player
    current_game = player.game()
    if current_game and current_game.num_players() == 1:
        min_room_id = current_game.min_room_id
        max_room_id = min_room_id+current_game.num_rooms()-1
        current_game.reset_players()
        Room.objects.filter(id__gte=min_room_id, id__lte=max_room_id).delete()
        Game.objects.filter(id=current_game.id).delete()
        return JsonResponse({
            'in_progress': False,
            'error': False,
            'message': 'Game quit!'}, safe=True)
    elif current_game and current_game.num_players() > 1:
        return JsonResponse({
            'in_progress': True,
            'error': True,
            'message': 'There are other players in this game, so you can not end it!'
        }, safe=True)
    else:
        return JsonResponse({
            'in_progress': False,
            'error': True,
            'message': 'The game has already ended! Someone found the end of the maze!!'
        }, safe=True)


@csrf_exempt
@api_view(['GET'])
def get_maze(request):
    player = request.user.player
    current_game = player.game()
    if current_game:
        return JsonResponse({'error': False, 'maze': current_game.all_rooms()})
    else:
        return JsonResponse({'error': True, 'message': 'You are not in a game'})
