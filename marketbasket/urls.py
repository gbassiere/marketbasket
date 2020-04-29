"""MarketBasket URL Configuration

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
from django.conf import settings
from django.conf.urls.static import static
import baskets.views

urlpatterns = [
    path('', baskets.views.merchant, name='merchant'),
    path('delivery/<int:id>/order', baskets.views.new_cart, name='new_cart'),
    path('delivery/<int:id>/baskets',
                baskets.views.prepare_baskets,
                name='prepare_baskets'),
    path('order/<int:id>/prepare',
                baskets.views.prepare_basket,
                name='prepare_basket'),
    path('order/<int:id>', baskets.views.cart, name='cart'),
    path('deliveries', baskets.views.needed_quantities, name='needed_quantities'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
]

if settings.DEBUG is True:
    urlpatterns += static(settings.MEDIA_URL,
                                document_root=settings.MEDIA_ROOT)
