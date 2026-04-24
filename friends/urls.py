from django.urls import path
from . import views

app_name = 'friends'

urlpatterns = [
    path('',                                     views.my_friends,        name='my_friends'),
    path('add/',                                 views.add_friend,        name='add_friend'),
    path('add/user/<int:user_id>/',              views.add_friend_user,   name='add_friend_user'),
    path('add-to-my-list/user/<int:user_id>/',   views.add_to_my_list_user, name='add_to_my_list_user'),
    path('<int:friendship_id>/accept/',          views.accept_request,    name='accept_request'),
    path('<int:friendship_id>/reject/',          views.reject_request,    name='reject_request'),
    path('<int:friendship_id>/cancel/',          views.cancel_request,    name='cancel_request'),
    path('<int:friendship_id>/pause/',           views.pause_friendship,  name='pause_friendship'),
    path('<int:friendship_id>/unpause/',         views.unpause_friendship, name='unpause_friendship'),
    path('<int:friendship_id>/remove/',          views.remove_friend,     name='remove_friend'),
    path('<int:user_id>/block/',                 views.block_friend,      name='block_friend'),
    # Blocked users management
    path('blocked/',                             views.blocked_users,     name='blocked_users'),
    path('block/<int:user_id>/',                 views.block_user,        name='block_user'),
    path('unblock/<int:user_id>/',               views.unblock_user,      name='unblock_user'),
    # legacy redirects
    path('list/',                                views.friends_list,      name='friends_list'),
    path('requests/pending/',                    views.pending_requests,  name='pending_requests'),
    path('requests/sent/',                       views.sent_requests,     name='sent_requests'),
]
