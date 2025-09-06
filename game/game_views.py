import json

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_GET

from game.exceptions import UserNotInRoomException
from game.game_logic import mark_read_by, check_advance_stage, advance_stage, CARDS_PER_PLAYER, PLAYERS, \
    get_accessible_stages, selected_cards_to_action, try_create_next_state, try_shoot
from game.models import Room, GameStage, GameState, CardType, CardShot
from game.view_utils import smart_view, require_room_exists, require_game_started, require_user_in_room


@require_POST
@csrf_protect
@smart_view
@require_room_exists
@require_game_started
@require_user_in_room
def get_game_stage(request):
    room_id = json.loads(request.body).get("room_id")
    room = Room.objects.get(id=room_id)
    game = room.game

    try_create_next_state(game)
    if check_advance_stage(game):
        advance_stage(game)
    mark_read_by(game, request.user)

    return JsonResponse({"game_stage": game.stage}, status=200)


def _state_json(game_state: GameState, user: User):
    if game_state.stage == GameStage.BEGINNING:
        game = game_state.game
        player_id = game.room.players.get(user=user).position
        return {
            "cards_to_show": [
                role if player_id * CARDS_PER_PLAYER <= i < (player_id + 1) * CARDS_PER_PLAYER else None
                for i, role in enumerate(game.roles)
            ]
        }
    if game_state.stage == GameStage.BROTHERS:
        game = game_state.game
        players_to_show = []
        roles = game_state.game.roles
        for i in range(PLAYERS):
            player_roles = roles[i * CARDS_PER_PLAYER: (i + 1) * CARDS_PER_PLAYER]
            if CardType.BROTHERS_1.value in player_roles or \
                    CardType.BROTHERS_2.value in player_roles or \
                    CardType.COPY.value in player_roles and \
                    (game.copied_role == CardType.BROTHERS_1.value or game.copied_role == CardType.BROTHERS_2):
                players_to_show.append(i)
        return {
            "players_to_show": players_to_show
        }
    if game_state.stage == GameStage.SHOOTING:
        game = game_state.game
        result = [None] * PLAYERS
        for player_id in range(PLAYERS):
            card_shots = CardShot.objects.filter(game=game, shooter_id=player_id)
            if card_shots.exists():
                result[player_id] = card_shots.get().card_index
        return {
            "cards_shot": result
        }
    action = game_state.get_action()
    if not action:
        return None
    result = {"cards_to_show": [
        card if i in action.cards_to_show else None for i, card in enumerate(action.game_state.cards)
    ]}
    if action.is_swap():
        result["swap"] = [action.swap_card_a, action.swap_card_b]
    return result


def _make_brothers_indistinguishable(state_json):
    if state_json and "cards_to_show" in state_json:
        state_json = state_json.copy()
        cards_to_show = state_json["cards_to_show"]
        for i in range(len(cards_to_show)):
            if cards_to_show[i] == CardType.BROTHERS_1.value or cards_to_show[i] == CardType.BROTHERS_2.value:
                cards_to_show[i] = CardType.BROTHERS_1.value[:-2]  # brothers_1 -> brothers
    return state_json


@require_GET
@csrf_protect
@smart_view
@require_room_exists
@require_game_started
def get_history(request):
    room_id = request.GET.get("room_id")
    room = Room.objects.get(id=room_id)
    game = room.game

    if game.stage != GameStage.FINISHED:
        user = request.user
        if not room.players.filter(user=user).exists():
            raise UserNotInRoomException
        result = {}
        for stage in get_accessible_stages(game, game.room.players.get(user=user).position):
            result[stage] = _make_brothers_indistinguishable(_state_json(game.history.get(stage=stage), user)) \
                if stage <= game.stage else None
        return JsonResponse({
            "history": result
        }, status=200)
    else:
        result = {}
        for stage, state_id in game.history.all().order_by('stage').values_list('stage', 'id'):
            if stage >= GameStage.FINISHED:
                break
            state = GameState.objects.get(id=state_id)
            result[stage] = _state_json(state, room.players.get(user=request.user).user)
            if not state.get_action() or state.action.is_swap():
                if result[stage] is None:
                    result[stage] = {}
                result[stage]["cards_to_show"] = state.cards
            result[stage] = _make_brothers_indistinguishable(result[stage])
        result[GameStage.FINISHED] = _make_brothers_indistinguishable({
            "cards_to_show": game.history.get(stage=GameStage.FINISHED).cards
        })
        return JsonResponse({
            "history": result
        }, status=200)


@require_POST
@csrf_protect
@smart_view
@require_room_exists
@require_game_started
@require_user_in_room
def submit_action(request):
    room_id = json.loads(request.body).get("room_id")
    selected_cards = json.loads(request.body).get("selected_cards")
    room = Room.objects.get(id=room_id)
    game = room.game
    player_id = room.players.get(user=request.user).position
    action = selected_cards_to_action(game, player_id, selected_cards)
    action.save()
    try_create_next_state(game)
    return JsonResponse({"detail": "Action recorded"}, status=200)


@require_POST
@csrf_protect
@smart_view
@require_room_exists
@require_game_started
@require_user_in_room
def shoot_card(request):
    room_id = json.loads(request.body).get("room_id")
    card_position = json.loads(request.body).get("card_position")
    room = Room.objects.get(id=room_id)
    game = room.game
    player_id = room.players.get(user=request.user).position
    try_shoot(game, player_id, card_position)
    return JsonResponse({"detail": "Shot recorded"}, status=200)