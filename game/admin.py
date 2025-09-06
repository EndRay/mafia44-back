from django.contrib import admin

from game.models import Room, Player, Game, GameState, GameStageRead, Action, CardShot

admin.site.register(Game)
admin.site.register(Room)
admin.site.register(Player)
admin.site.register(GameState)
admin.site.register(GameStageRead)
admin.site.register(Action)
admin.site.register(CardShot)