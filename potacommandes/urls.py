"""potacommandes URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
import commandes.views

urlpatterns = [
    path('', commandes.views.next_deliveries, name='next_deliveries'),
    path('delivery/<int:id>/order', commandes.views.new_cart, name='new_cart'),
    path('delivery/<int:id>/baskets',
                commandes.views.prepare_baskets,
                name='prepare_baskets'),
    path('order/<int:id>', commandes.views.cart, name='cart'),
    path('deliveries', commandes.views.needed_quantities, name='needed_quantities'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
]
