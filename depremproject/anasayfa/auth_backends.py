from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from .models import Kullanici

class EmailOrTCBackend(BaseBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):

        # username → email veya TC olabilir
        try:
            user = Kullanici.objects.get(email=username)
        except Kullanici.DoesNotExist:
            try:
                user = Kullanici.objects.get(TC=username)
            except Kullanici.DoesNotExist:
                return None

        # Şifre eşleşiyor mu?
        # Eğer şifre hash değilse: direct kontrol
        if user.Sifre == password:
            return user
        
        # Eğer hash kullanıyorsan:
        # if check_password(password, user.Sifre):
        #     return user
        
        return None

    def get_user(self, user_id):
        try:
            return Kullanici.objects.get(pk=user_id)
        except Kullanici.DoesNotExist:
            return None
