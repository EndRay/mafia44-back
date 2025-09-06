import random

from django.contrib.auth.models import User
from django.utils import timezone

from game.exceptions import InvalidSelectedCardsException
from game.models import Game, GameState, CardType, GameStageRead, GameStage, Action, Room, CardShot

PLAYERS = 4
CARDS_IN_DISCARD = 3
CARDS_PER_PLAYER = 2

ROLE_TO_STAGE = {
    CardType.COPY.value: GameStage.COPY,
    CardType.THIEF.value: GameStage.THIEF,
    CardType.BROTHERS_1.value: GameStage.BROTHERS,
    CardType.BROTHERS_2.value: GameStage.BROTHERS,
    CardType.SEER.value: GameStage.SEER,
    CardType.BRAWLER.value: GameStage.BRAWLER,
    CardType.DRUNKARD.value: GameStage.DRUNKARD,
    CardType.WITCH.value: GameStage.WITCH,
    CardType.MILKMAN.value: GameStage.MILKMAN,
}

ROLE_COPY_TO_STAGE = {
    CardType.THIEF.value: GameStage.THIEF_COPY,
    CardType.BROTHERS_1.value: GameStage.BROTHERS,
    CardType.BROTHERS_2.value: GameStage.BROTHERS,
    CardType.SEER.value: GameStage.SEER_COPY,
    CardType.BRAWLER.value: GameStage.BRAWLER_COPY,
    CardType.DRUNKARD.value: GameStage.DRUNKARD_COPY,
    CardType.WITCH.value: GameStage.WITCH_COPY,
    CardType.MILKMAN.value: GameStage.MILKMAN_COPY,
}


def init_game(room: Room) -> Game:
    game = Game.objects.create(stage=GameStage.BEGINNING, room=room)

    cards = list(CardType)
    random.shuffle(cards)

    GameState.objects.create(
        game=game,
        cards=cards,
        stage=GameStage.BEGINNING
    )
    return game


def mark_read_by(game: Game, user: User):
    current_state = GameState.objects.get(game=game, stage=game.stage)
    GameStageRead.objects.get_or_create(user=user, state=current_state)


def is_action_required(game_state: GameState) -> bool:
    stage = game_state.stage
    copied_role = game_state.game.copied_role
    roles = game_state.game.roles
    if stage == GameStage.BEGINNING:
        return False
    if stage == GameStage.BROTHERS:
        return False
    if stage == GameStage.SHOOTING:
        return False
    if stage in ROLE_TO_STAGE.values():
        stage_to_role = {v.value: k for k, v in ROLE_TO_STAGE.items()}
        return stage_to_role[stage] in roles[:PLAYERS * CARDS_PER_PLAYER]
    if copied_role and copied_role in ROLE_COPY_TO_STAGE and stage == ROLE_COPY_TO_STAGE[copied_role]:
        return True
    return False


def check_advance_stage(game: Game) -> bool:
    if game.stage == GameStage.FINISHED:
        return False

    if game.stage == GameStage.SHOOTING:
        if CardShot.objects.filter(game=game).count() >= game.room.players.count():
            return True
        return False

    current_state = GameState.objects.get(game=game, stage=game.stage)

    if not GameState.objects.filter(game=game, stage=game.stage + 1).exists():
        return False

    current_state_readers = current_state.read_by.order_by('timestamp').all()
    if current_state_readers.count() < game.room.players.count():
        return False
    last_read_timestamp = current_state_readers.last().timestamp
    now = timezone.now()
    if (now - last_read_timestamp).total_seconds() < game.room.min_move_time:
        return False
    return True


def _apply_action(cards: list[CardType], action: Action):
    cards = cards.copy()
    if action.is_swap():
        cards[action.swap_card_a], cards[action.swap_card_b] = cards[action.swap_card_b], cards[action.swap_card_a]
    return cards


def try_create_next_state(game: Game) -> None:
    current_state = GameState.objects.get(game=game, stage=game.stage)
    if GameState.objects.filter(game=game, stage=game.stage + 1).exists():
        return
    if game.stage == GameStage.MILKMAN or (
            game.stage == GameStage.MILKMAN_COPY and game.copied_role == CardType.MILKMAN):
        milkman_index = game.roles.index(CardType.MILKMAN.value) \
            if game.stage == GameStage.MILKMAN else game.roles.index(CardType.COPY.value)
        if milkman_index < PLAYERS * CARDS_PER_PLAYER:
            Action.objects.create(
                cards_to_show=[milkman_index],
                swap_card_a=None,
                swap_card_b=None,
                game_state=current_state
            )
    if not is_action_required(current_state):
        GameState.objects.create(
            game=game,
            stage=game.stage + 1,
            cards=current_state.cards
        )
    if is_action_required(current_state) and current_state.get_action() is not None:
        if game.stage == GameStage.COPY:
            game.copied_role = current_state.cards[current_state.action.cards_to_show[0]]
            game.save()
        new_game_state = GameState.objects.create(
            game=game,
            stage=game.stage + 1,
            cards=_apply_action(current_state.cards, current_state.action)
        )


def advance_stage(game: Game) -> None:
    game.stage += 1
    game.save()
    try_create_next_state(game)


def get_accessible_stages(game: Game, player_id: int) -> list[GameStage]:
    player_roles = game.roles[player_id * CARDS_PER_PLAYER: (player_id + 1) * CARDS_PER_PLAYER]
    player_stages = [GameStage.BEGINNING] + [ROLE_TO_STAGE[role] for role in player_roles if role in ROLE_TO_STAGE]
    if CardType.COPY in player_roles and (copied_role := game.copied_role):
        if copied_role in ROLE_COPY_TO_STAGE:
            player_stages.append(ROLE_COPY_TO_STAGE[copied_role])
    player_stages.append(GameStage.SHOOTING)
    return player_stages


def check_action(game: Game, player_id: int, action: Action) -> bool:
    if game.stage not in get_accessible_stages(game, player_id):
        return False
    roles = game.roles

    if (action.swap_card_a is None) != (action.swap_card_b is None):
        return False
    if action.swap_card_a is not None and action.swap_card_a == action.swap_card_b:
        return False
    for idx in action.cards_to_show + action.swapped_cards:
        if not (0 <= idx < PLAYERS * CARDS_PER_PLAYER + CARDS_IN_DISCARD):
            return False

    def is_same_player_card(idx: int) -> bool:
        return player_id * CARDS_PER_PLAYER <= idx < (player_id + 1) * CARDS_PER_PLAYER

    def is_other_player_card(idx: int) -> bool:
        return 0 <= idx < PLAYERS * CARDS_PER_PLAYER and not is_same_player_card(idx)

    def is_player_card(idx: int) -> bool:
        return 0 <= idx < PLAYERS * CARDS_PER_PLAYER

    def is_discard_card(idx: int) -> bool:
        return not is_player_card(idx)

    match GameStage(game.stage):
        case GameStage.BEGINNING | GameStage.SHOOTING | GameStage.FINISHED:
            return False
        case GameStage.COPY:
            return (len(action.cards_to_show) == 1 and
                    roles[action.cards_to_show[0]] != CardType.COPY.value and
                    not action.is_swap())
        case GameStage.THIEF | GameStage.THIEF_COPY:
            card_self = CardType.THIEF.value if game.stage == GameStage.THIEF else CardType.COPY.value
            card_self_id = roles.index(card_self)
            return (len(action.cards_to_show) == 1 and
                    is_other_player_card(action.cards_to_show[0]) and
                    action.is_swap() and
                    action.cards_to_show[0] in action.swapped_cards and
                    card_self_id in action.swapped_cards)
        case GameStage.BROTHERS:
            return False
        case GameStage.SEER | GameStage.SEER_COPY:
            card_self = CardType.SEER.value if game.stage == GameStage.SEER else CardType.COPY.value
            return (((len(action.cards_to_show) == 1 and is_other_player_card(action.cards_to_show[0])) or
                     (len(action.cards_to_show) == 2 and
                      is_discard_card(action.cards_to_show[0]) and
                      is_discard_card(action.cards_to_show[1]))) and
                    card_self not in [roles[idx] for idx in action.cards_to_show] and
                    not action.is_swap())
        case GameStage.BRAWLER | GameStage.BRAWLER_COPY:
            return (len(action.cards_to_show) == 0 and
                    action.is_swap() and
                    all(is_other_player_card(idx) for idx in action.swapped_cards))
        case GameStage.DRUNKARD | GameStage.DRUNKARD_COPY:
            card_self = CardType.DRUNKARD.value if game.stage == GameStage.DRUNKARD else CardType.COPY.value
            return (len(action.cards_to_show) == 0 and
                    action.is_swap() and
                    any(is_discard_card(idx) for idx in action.swapped_cards) and
                    any(roles[idx] == card_self for idx in action.swapped_cards))
        case GameStage.WITCH | GameStage.WITCH_COPY:
            return (len(action.cards_to_show) == 0 and
                    action.is_swap() and
                    any(is_discard_card(idx) for idx in action.swapped_cards) and
                    any(is_other_player_card(idx) for idx in action.swapped_cards))
        case GameStage.MILKMAN | GameStage.MILKMAN_COPY:
            card_self = CardType.MILKMAN.value if game.stage == GameStage.MILKMAN else CardType.COPY.value
            return (len(action.cards_to_show) == 1 and
                    roles[action.cards_to_show[0]] == card_self and
                    not action.is_swap())


def selected_cards_to_action(game: Game, player_id: int, selected_cards: list[int]) -> Action:
    roles = game.roles
    match game.stage:
        case GameStage.BEGINNING | GameStage.SHOOTING | GameStage.FINISHED | GameStage.BROTHERS | GameStage.MILKMAN | GameStage.MILKMAN_COPY:
            raise InvalidSelectedCardsException
        case GameStage.COPY:
            action = Action(
                cards_to_show=selected_cards,
                swap_card_a=None,
                swap_card_b=None,
            )
        case GameStage.THIEF | GameStage.THIEF_COPY:
            card_self = CardType.THIEF.value if game.stage == GameStage.THIEF else CardType.COPY.value
            thief_idx = roles.index(card_self)
            action = Action(
                cards_to_show=selected_cards,
                swap_card_a=selected_cards[0],
                swap_card_b=thief_idx
            )
        case GameStage.SEER | GameStage.SEER_COPY:
            action = Action(
                cards_to_show=selected_cards,
                swap_card_a=None,
                swap_card_b=None,
            )
        case GameStage.BRAWLER | GameStage.BRAWLER_COPY | GameStage.WITCH | GameStage.WITCH_COPY:
            if len(selected_cards) != 2:
                raise InvalidSelectedCardsException
            action = Action(
                cards_to_show=[],
                swap_card_a=selected_cards[0],
                swap_card_b=selected_cards[1],
            )
        case GameStage.DRUNKARD | GameStage.DRUNKARD_COPY:
            if len(selected_cards) != 1:
                raise InvalidSelectedCardsException
            drunkard_idx = roles.index(
                CardType.DRUNKARD.value if game.stage == GameStage.DRUNKARD else CardType.COPY.value)
            action = Action(
                cards_to_show=[],
                swap_card_a=selected_cards[0],
                swap_card_b=drunkard_idx,
            )
        case _:
            raise ValueError("Unknown game stage")

    action.game_state = GameState.objects.get(game=game, stage=game.stage)
    if not check_action(game, player_id, action):
        raise InvalidSelectedCardsException
    return action


def can_shoot(game: Game, player_id: int, card_id: int) -> bool:
    if not (0 <= card_id < PLAYERS * CARDS_PER_PLAYER):
        return False
    if CardShot.objects.filter(game=game, shooter_id=player_id).exists():
        return False
    card_player_id = card_id // CARDS_PER_PLAYER
    if card_player_id == player_id:
        return False
    if game.stage != GameStage.SHOOTING:
        return False
    return True


def _shoot(game: Game, player_id: int, card_id: int) -> None:
    CardShot.objects.create(game=game, shooter_id=player_id, card_index=card_id)


def try_shoot(game: Game, player_id: int, card_id: int) -> None:
    if not can_shoot(game, player_id, card_id):
        raise InvalidSelectedCardsException
    _shoot(game, player_id, card_id)
