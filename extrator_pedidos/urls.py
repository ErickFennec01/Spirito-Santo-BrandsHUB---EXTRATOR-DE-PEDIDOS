from django.urls import path
from .views import index, ProcessarPedido, health_check # Adicione 'health_check' aqui

urlpatterns = [
    path('', index, name='index'),
    path('processar_pedido/', ProcessarPedido.as_view(), name='processar_pedido'),
    path('health/', health_check, name='health_check'), # Adicione esta linha
]
