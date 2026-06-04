from django.urls import path, include
from . import views

app_name='my_sharing_hub'
urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('earnings/', views.earnings, name='earnings'),
    path('my_details/', views.my_details, name='my_details'),
    path('open_orders/', views.open_orders, name='open_orders'),
    path('closed_orders/' , views.closed_orders, name='closed_orders'),
    path('copy_order_as_new/<int:order_id>/', views.copy_order_as_new, name='copy_order_as_new'),
    path('open_transactions/' , views.open_transactions, name='open_transactions'),
    path('mediation_transactions/' , views.mediation_transactions, name='mediation_transactions'),
    path('awaiting_feedback_transactions/' , views.awaiting_feedback_transactions, name='awaiting_feedback_transactions'),
    path('closed_transactions/' , views.closed_transactions, name='closed_transactions'),
    path('inbox/' , views.inbox, name='inbox'),
    path('notifications/' , views.notifications, name='notifications'),
    path('pending_actions/' , views.pending_actions, name='pending_actions'),
    path('messages_received/' , views.messages_received, name='messages_received'),
    path('messages_sent/' , views.messages_sent, name='messages_sent'),
    path('messages_mark_all_read/', views.mark_all_messages_read, name='messages_mark_all_read'),
    path('favourites/', views.favourites, name='favourites'),
    path('expand_message/' , views.expand_message, name='expand_message'),
    path('payment_methods/', views.payment_methods, name='payment_methods'),

]
