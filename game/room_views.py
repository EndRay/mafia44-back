import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from game import game_logic
from game.exceptions import (
    RoomAlreadyExistsException,
    RoomNotFoundException,
    UserNotCreatorException,
    UserAlreadyInRoomException,
    UserNotFoundException,
    CreatorCannotLeaveRoomException,
    RoomFullException,
    GameAlreadyStartedException
)
from game.game_logic import init_game
from game.models import Room, Player, User
from game.view_utils import smart_view, require_user_in_room, require_room_exists


def _user_data(user: User):
    return {"id": user.id, "username": user.username}


def _room_data(room: Room):
    return {
        "id": room.id,
        "name": room.name,
        "creator": _user_data(room.creator),
        "is_game_started": room.get_game() is not None,
        "players": [_user_data(player.user) for player in room.players.all()]
    }


@require_GET
def get_rooms_list(request):
    rooms = Room.objects.all()
    rooms_data = [_room_data(room) for room in rooms]
    return JsonResponse({"rooms": rooms_data}, status=200)


@require_POST
@csrf_protect
@smart_view
def create_room(request):
    data = json.loads(request.body or "{}")
    room_name = data.get('room_name')
    if Room.objects.filter(name=room_name).exists():
        raise RoomAlreadyExistsException
    room = Room.objects.create(name=room_name, creator=request.user)
    Player.objects.create(user=request.user, room=room)
    room.save()
    return JsonResponse(_room_data(room), status=201)


@require_POST
@csrf_protect
@smart_view
def delete_room(request):
    data = json.loads(request.body or "{}")
    room_id = data.get('room_id')
    if not Room.objects.filter(id=room_id).exists():
        raise RoomNotFoundException
    room = Room.objects.get(id=room_id)
    if room.creator != request.user:
        raise UserNotCreatorException
    room.delete()
    return HttpResponse(status=200)


@require_POST
@csrf_protect
@smart_view
def join_room(request):
    data = json.loads(request.body or "{}")
    room_id = data.get('room_id')
    if not Room.objects.filter(id=room_id).exists():
        raise RoomNotFoundException
    room = Room.objects.get(id=room_id)
    if room.players.filter(user=request.user).exists():
        raise UserAlreadyInRoomException
    if room.players.count() >= game_logic.PLAYERS:
        raise RoomFullException
    Player.objects.create(user=request.user, room=room)
    return HttpResponse(status=201)


@require_POST
@csrf_protect
@smart_view
def leave_room(request):
    data = json.loads(request.body or "{}")
    room_id = data.get('room_id')
    if not Room.objects.filter(id=room_id).exists():
        raise RoomNotFoundException
    room = Room.objects.get(id=room_id)
    if not room.players.filter(user=request.user).exists():
        raise UserNotFoundException
    if room.creator == request.user:
        raise CreatorCannotLeaveRoomException
    player = Player.objects.get(user=request.user, room=room)
    player.delete()
    return HttpResponse(status=200)


@require_POST
@csrf_protect
@smart_view
@require_room_exists
@require_user_in_room
def start_game(request):
    data = json.loads(request.body or "{}")
    room_id = data.get('room_id')
    room = Room.objects.get(id=room_id)
    if room.creator != request.user:
        raise UserNotCreatorException
    if room.get_game() is not None:
        raise GameAlreadyStartedException
    init_game(room)
    return HttpResponse(status=200)
