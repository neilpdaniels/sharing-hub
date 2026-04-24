from django.urls import path, include
from . import views

app_name = 'transaction'
urlpatterns = [
    path('add_order/<int:product_id>/' , views.add_order, name='add_order'),
    path('edit_order/<int:order_id>/' , views.edit_order, name='edit_order'),
    path('expire_order/<int:order_id>/' , views.expire_order, name='expire_order'),
    path('hit_order/<int:order_id>/' , views.hit_order, name='hit_order'),
    path('get_fee/', views.get_fee, name='get_fee'),
    path('view_transaction/<str:transaction_reference>/' , views.view_transaction, name='view_transaction'),
    path('order_image_upload/', views.OrderImageUpload.as_view(), name='order_image_upload'),
    path('remove_order_image/' , views.remove_order_image, name='remove_order_image'),
    path('set_payment_state/', views.set_payment_state, name='set_payment_state'),
    path('set_product_state/', views.set_product_state, name='set_product_state'),
    path('set_transaction_state/', views.set_transaction_state, name='set_transaction_state'),
    path('raise_dispute/<str:transaction_reference>/', views.raise_dispute, name='raise_dispute'),
    path('transaction_add_message/', views.transaction_add_message, name='transaction_add_message'),
    path('transaction_message_image_upload/', views.TransactionMessageImageUpload.as_view(), name='transaction_message_image_upload'),
    path('transpact_refresh/', views.transpact_refresh, name='transpact_refresh'),

]   