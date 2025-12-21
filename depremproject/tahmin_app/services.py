import os
import joblib
from django.conf import settings

_MODEL = None

def get_model():
    global _MODEL
    if _MODEL is None:
        model_path = os.path.join(
            settings.BASE_DIR,
            'tahmin_app',
            'gb_model_final.pkl'
        )
        _MODEL = joblib.load(model_path)
    return _MODEL
