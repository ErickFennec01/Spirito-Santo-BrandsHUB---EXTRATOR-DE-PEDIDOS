# extrator_pedidos/urls.py
from django.urls import path
from .views import index, ProcessarPedido
urlpatterns = [
    path('', index, name='index'),
    path('processar_pedido/', ProcessarPedido.as_view(), name='processar_pedido'),
]