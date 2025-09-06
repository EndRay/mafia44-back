from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

DEFAULT_MIN_MOVE_TIME = 5


class GameStage(models.IntegerChoices):
    BEGINNING = 0
    COPY = 1
    THIEF = 2
    THIEF_COPY = 3
    BROTHERS = 4
    SEER = 5
    SEER_COPY = 6
    BRAWLER = 7
    BRAWLER_COPY = 8
    DRUNKARD = 9
    DRUNKARD_COPY = 10
    WITCH = 11
    WITCH_COPY = 12
    MILKMAN = 13
    MILKMAN_COPY = 14
    SHOOTING = 15
    FINISHED = 16


class CardType(models.TextChoices):
    COPY = 'copy'
    THIEF = 'thief'
    BROTHERS_1 = 'brothers_1'
    BROTHERS_2 = 'brothers_2'
    SEER = 'seer'
    BRAWLER = 'brawler'
    DRUNKARD = 'drunkard'
    WITCH = 'witch'
    MILKMAN = 'milkman'
    MAFIA = 'mafia'
    SUICIDE = 'suicide'


class Room(models.Model):
    name = models.CharField(max_length=100)
    creator = models.ForeignKey(User, related_name='created_rooms', on_delete=models.CASCADE)
    min_move_time = models.IntegerField(default=DEFAULT_MIN_MOVE_TIME)

    def get_game(self):
        try:
            return self.game
        except Game.DoesNotExist:
            return None


class Game(models.Model):
    stage = models.IntegerField(choices=GameStage)
    copied_role = models.CharField(choices=CardType, null=True)
    room = models.OneToOneField(Room, related_name='game', on_delete=models.CASCADE)

    @property
    def roles(self):
        return self.history.get(stage=GameStage.BEGINNING).cards


class GameState(models.Model):
    game = models.ForeignKey(Game, related_name='history', on_delete=models.CASCADE)
    stage = models.IntegerField(choices=GameStage)
    timestamp = models.DateTimeField(default=timezone.now)
    cards = models.JSONField()  # [player 1 cards, player 2 cards, ..., discard]

    def get_action(self):
        try:
            return self.action
        except Action.DoesNotExist:
            return None


class GameStageRead(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    state = models.ForeignKey(GameState, related_name='read_by', on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'state'],
                name='unique_user_state_read'
            )
        ]


class Action(models.Model):
    game_state = models.OneToOneField(GameState, related_name='action', on_delete=models.CASCADE)
    cards_to_show = models.JSONField(blank=True)
    swap_card_a = models.IntegerField(null=True)
    swap_card_b = models.IntegerField(null=True)

    @property
    def swapped_cards(self):
        return [self.swap_card_a, self.swap_card_b] if self.is_swap() else []

    def is_swap(self):
        return self.swap_card_a is not None and self.swap_card_b is not None

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                        models.Q(swap_card_a__isnull=True, swap_card_b__isnull=True) |
                        models.Q(swap_card_a__isnull=False, swap_card_b__isnull=False)
                ),
                name="both_cards_null_or_not_null"
            ),
            models.CheckConstraint(
                check=~models.Q(swap_card_a=models.F('swap_card_b')),
                name="cards_to_swap_not_equal"
            )
        ]


class Player(models.Model):
    user = models.ForeignKey(User, related_name='players', on_delete=models.CASCADE)
    room = models.ForeignKey(Room, related_name='players', on_delete=models.CASCADE)
    join_timestamp = models.DateTimeField(default=timezone.now)

    @property
    def position(self):
        return self.room.players.filter(join_timestamp__lt=self.join_timestamp).count()
