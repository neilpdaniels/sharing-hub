from django.urls import path, include
from . import views

app_name='my_sharing_hub'
urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('open_orders/', views.open_orders, name='open_orders'),
    path('closed_orders/' , views.closed_orders, name='closed_orders'),
    path('open_transactions/' , views.open_transactions, name='open_transactions'),
    path('closed_transactions/' , views.closed_transactions, name='closed_transactions'),
    path('pending_actions/' , views.pending_actions, name='pending_actions'),
    path('messages_received/' , views.messages_received, name='messages_received'),
    path('messages_sent/' , views.messages_sent, name='messages_sent'),
    path('expand_message/' , views.expand_message, name='expand_message'),
    
]