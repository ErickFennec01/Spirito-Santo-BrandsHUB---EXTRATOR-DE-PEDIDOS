# core/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('extrator_pedidos.urls')), # Adicione esta linha
]