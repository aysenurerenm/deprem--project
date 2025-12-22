from django.shortcuts import render
import requests

def ev_tahmin(request):
    sonuc = None
    hata = None

    if request.method == "POST":

        mahalle_secimi = request.POST.get("mahalle_secimi")

        # 🔹 Formdan gelen veriler
        input_data = {
            'Banyo Sayısı': float(request.POST.get('banyo_sayisi')),
            'Brüt Metrekare': float(request.POST.get('brut_metrekare')),
            'Binanın Yaşı Num': int(request.POST.get('bina_yasi')),
            'Binanın Kat Sayısı': int(request.POST.get('bina_kat_sayisi')),
            'Yayında Kalma Süresi': int(request.POST.get('yayin_suresi')),
            'Bulunduğu Kat Num': int(request.POST.get('bulundugu_kat')),
            'Toplam Oda Sayısı': int(request.POST.get('toplam_oda')),

            # 🔹 Encoded alanlar
            'Isitma Enc': int(request.POST.get('isitma_enc')),
            'Tipi Enc': int(request.POST.get('tipi_enc')),
            'Kullanım Enc': int(request.POST.get('kullanim_enc')),
            'Tapu_Kat İrtifakı': int(request.POST.get('tapu_irtifak')),

            # 🔹 Mahalle One-Hot
            'Mahalle_Kazımdirik Mahallesi': 1 if mahalle_secimi == 'kazimdirik' else 0,
            'Mahalle_Erzene Mahallesi': 1 if mahalle_secimi == 'erzene' else 0,
            'Mahalle_Yakaköy Mahallesi': 1 if mahalle_secimi == 'yakakoy' else 0,
            'Mahalle_Diğer': 1 if mahalle_secimi == 'diger' else 0,
        }

        # 🔹 Eğitimde kullanılan TAM sütun sırası
        sutun_sirasi = [
            'Banyo Sayısı',
            'Brüt Metrekare',
            'Binanın Yaşı Num',
            'Binanın Kat Sayısı',
            'Yayında Kalma Süresi',
            'Bulunduğu Kat Num',
            'Mahalle_Kazımdirik Mahallesi',
            'Toplam Oda Sayısı',
            'Isitma Enc',
            'Tipi Enc',
            'Mahalle_Diğer',
            'Mahalle_Erzene Mahallesi',
            'Tapu_Kat İrtifakı',
            'Kullanım Enc',
            'Mahalle_Yakaköy Mahallesi'
        ]

        # 🔹 Modele gidecek input
        model_input = [input_data[col] for col in sutun_sirasi]

        # 🔥 FLASK ML SERVİSİNE İSTEK
        try:
            response = requests.post(
                "http://192.168.1.102:5000/predict",
                json={"features": model_input},
                timeout=5
            )

            response_data = response.json()

            if response_data.get("success"):
                sonuc = response_data["tahmin"]
            else:
                hata = "Tahmin alınamadı."

        except Exception as e:
            hata = "ML servisine bağlanılamadı."

    return render(request, "tahmin_app/tahmin.html", {
        "sonuc": sonuc,
        "hata": hata
    })
