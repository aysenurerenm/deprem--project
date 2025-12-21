from django.urls import path
from .views import ev_tahmin

urlpatterns = [
    path('', ev_tahmin, name='ev_tahmin'),
]
