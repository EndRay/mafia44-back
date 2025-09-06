import json
import threading

from django.http import JsonResponse

from game.exceptions import GameException, RoomNotFoundException, GameNotStartedException, UserNotInRoomException
from game.models import Room

_registry_lock = threading.Lock()
_room_locks = {}  # {room_id: threading.RLock()}


def _get_room_lock(room_id):
    with _registry_lock:
        lock = _room_locks.get(room_id)
        if lock is None:
            lock = threading.RLock()
            _room_locks[room_id] = lock
        return lock


def smart_view(view):
    def new_view(*args, **kwargs):
        data = json.loads(args[0].body or "{}")
        room_lock = None
        if "room_id" in data:
            room_lock = _get_room_lock(data["room_id"])
            room_lock.acquire()
        try:
            return view(*args, **kwargs)
        except GameException as e:
            return JsonResponse({"detail": e.details}, status=e.code)
        finally:
            if room_lock:
                room_lock.release()

    return new_view


def require_room_exists(func):
    def wrapper(request, *args, **kwargs):
        room_id = json.loads(request.body or "{}").get("room_id") or request.GET.get("room_id")
        if not room_id:
            print(f"room_id: {room_id}")
            return JsonResponse({"detail": "room_id is required"}, status=400)
        if not Room.objects.filter(id=room_id).exists():
            raise RoomNotFoundException
        return func(request, *args, **kwargs)

    return wrapper


def require_game_started(func):
    def wrapper(request, *args, **kwargs):
        room_id = json.loads(request.body or "{}").get("room_id") or request.GET.get("room_id")
        room = Room.objects.get(id=room_id)
        if not room.get_game():
            raise GameNotStartedException
        return func(request, *args, **kwargs)

    return wrapper


def require_user_in_room(func):
    def wrapper(request, *args, **kwargs):
        room_id = json.loads(request.body or "{}").get("room_id") or request.GET.get("room_id")
        room = Room.objects.get(id=room_id)
        if request.user not in [player.user for player in room.players.all()]:
            raise UserNotInRoomException
        return func(request, *args, **kwargs)

    return wrapper
