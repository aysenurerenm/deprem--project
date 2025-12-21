from django.apps import AppConfig

# tahmin_app/apps.py
import joblib
import os
from django.apps import AppConfig
class StaticConfig(AppConfig):
    name = 'tahmin_app'
    # Modeli burada bir kez yüklüyoruz
    model_yolu = os.path.join(os.path.dirname(__file__), 'gb_model_final.pkl')
    model = joblib.load(model_yolu)