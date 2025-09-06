from django.urls import path

from game import room_views, auth_views, game_views

urlpatterns = [
    path('game_stage/', game_views.get_game_stage, name='game_stage'),
    path('game_history/', game_views.get_history, name='game_history'),
    path('submit_action/', game_views.submit_action, name='submit_action'),

    path('rooms/', room_views.get_rooms_list, name='rooms_list'),
    path('create_room/', room_views.create_room, name='create_room'),
    path('delete_room/', room_views.delete_room, name='delete_room'),
    path('join_room/', room_views.join_room, name='join_room'),
    path('leave_room/', room_views.leave_room, name='leave_room'),
    path('start_game/', room_views.start_game, name='start_game'),

    path("csrf/", auth_views.csrf),
    path("login/", auth_views.login_view),
    path("register/", auth_views.register_view),
    path("logout/", auth_views.logout_view),
    path("me/", auth_views.me_view),
]
