from flask import Flask, request, jsonify
import joblib
import numpy as np
import os

app = Flask(__name__)

# 🔹 Model yükleniyor
BASE_DIR = os.path.dirname(os.path.abspath("C:\\Users\\ACER\\Desktop\\gb_model3_final.pkl"))

# 🔹 Modelin tam yolu
MODEL_PATH = os.path.join(BASE_DIR, "gb_model_final.pkl")

# 🔹 Modeli yükle
model = joblib.load(MODEL_PATH)

@app.route("/")
def home():
    return "ML Tahmin Servisi Çalışıyor"

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()

        # Django'dan gelen input
        features = data["features"]

        # NumPy formatına çevir
        features = np.array(features).reshape(1, -1)

        # Tahmin
        prediction = model.predict(features)[0]

        return jsonify({
            "success": True,
            "tahmin": float(prediction)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

if __name__ == "__main__":
    app.run(host="192.168.1.102", port=5000, debug=True)
