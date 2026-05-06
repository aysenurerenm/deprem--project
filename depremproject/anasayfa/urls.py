
from django.urls import path
from . import views
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *




urlpatterns = [
    
    path('', views.home, name='home'),
    path("en-yakin-toplanma/", views.en_yakin_toplanma, name="en_yakin_toplanma"),
    path('citizen_dashboard/', views.citizen_dashboard, name='citizen_dashboard'),
    path("guvende-ol/", views.guvende_ol, name="guvende_ol"),
    path("yardim-bekliyorum/", views.yardim_bekliyorum, name="yardim_bekliyorum"),
    path("yakin-ekle/", views.yakin_ekle, name="yakin_ekle"),
    path("yakin-durum-guncelle/", views.yakin_durum_guncelle, name="yakin_durum_guncelle"),
    path('driver-dashboard/', views.driver_dashboard, name='driver_dashboard'),
    path("surucu/tamamlandi/<int:ulasim_id>/",views.surucu_tamamlandi, name="surucu_tamamlandi"),
    path('areas/', views.area_officer_dashboard, name='area_officer_dashboard'),
     path('kisi/<int:kisi_id>/durum-guncelle/', views.kisi_durum_guncelle, name='kisi_durum_guncelle'),
    path('map_page/', views.map_page, name='map_page'),   
    path('warehouse/', views.warehouse_dashboard, name='warehouse_dashboard'),
    path("login/", views.login_view, name="login"),
    path('register/', views.register_view, name='register'),
    path('login/anasayfa/home.html', views.home, name='login_anasayfa'), #bu kısma giriş sonrası urller eklenecek
    path("logout/", views.logout_view, name="logout"),
    path("kullanici-ekle/", views.kullanici_ekle, name="kullanici_ekle"),
    path('ihtiyac_ekle/', views.ihtiyac_ekle, name='ihtiyac_ekle'),
    path('warehouse_dashboard/sevkiyat-takip/', views.depo_sevkiyat_takip, name="depo_sevkiyat_takip"),
    path('warehouse_dashboard/talep-yonetim/', views.talep_yonetim, name="talep-yonetim"),
    path('warehouse_dashboard/gecmis-sevkiyatlar/',views.gecmis_sevkiyatlar,name='gecmis_sevkiyatlar'
    ),


]
