import os
import sys
import django
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from kneed import KneeLocator

# ===============================
# DJANGO SETUP
# ===============================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'depremproject.settings')
django.setup()

# Modelleri içeri aktar
from anasayfa.models import Depo, ToplanmaAlanlari, Kullanici

print("Django ve modeller başarıyla yüklendi.")

# ===============================
# 1. VERİLERİ ÇEKME
# ===============================
# Veritabanından toplanma alanlarını çekiyoruz
konum_verileri = ToplanmaAlanlari.objects.values('enlem', 'boylam', 'mahalleAdı', 'alan')
df = pd.DataFrame(list(konum_verileri))

if df.empty:
    print("Hata: Veritabanında kümeleme yapılacak toplanma alanı bulunamadı.")
    sys.exit()

# Kümeleme için sadece koordinatları alıyoruz
X = df[['enlem', 'boylam']].values

# ===============================
# 2. DİNAMİK KÜME SAYISI (ELBOW METHOD)
# ===============================
wcss = []
k_range = range(1, min(len(X), 11)) # Veri azsa hata almamak için min kontrolü

for k in k_range:
    kmeans = KMeans(n_clusters=k, init='k-means++', random_state=42)
    kmeans.fit(X)
    wcss.append(kmeans.inertia_)

# Dirsek noktasını tespit etme
kn = KneeLocator(k_range, wcss, curve='convex', direction='decreasing')
ideal_k = kn.knee if kn.knee else 3

print(f"Dinamik olarak belirlenen ideal küme sayısı: {ideal_k}")

# ===============================
# 3. K-MEANS VE GREEDY DEPO SEÇİMİ
# ===============================
kmeans_final = KMeans(n_clusters=ideal_k, init='k-means++', random_state=42)
df['cluster'] = kmeans_final.fit_predict(X)

# Sorumlu kullanıcıyı çek (ID: 3)
try:
    hedef_kullanici = Kullanici.objects.get(kullaniciID=3)
except Kullanici.DoesNotExist:
    print("Hata: 3 ID'li kullanıcı bulunamadı!")
    hedef_kullanici = None

depo_objeleri = []
if hedef_kullanici:
    for i in range(ideal_k):
        # Bu kümeye ait noktaları filtrele
        cluster_data = df[df['cluster'] == i]
        center = kmeans_final.cluster_centers_[i]
        
        # Merkeze en yakın gerçek toplanma alanını bul (Greedy)
        distances = np.linalg.norm(cluster_data[['enlem', 'boylam']].values - center, axis=1)
        best_row = cluster_data.iloc[distances.argmin()]
        
        # Depo objesini listeye ekle
        depo_objeleri.append(
            Depo(
                enlem=float(best_row['enlem']),
                boylam=float(best_row['boylam']),
                Ad=best_row['mahalleAdı'],
                depoKapasite=int(best_row['alan']),
                kullaniciID=hedef_kullanici,
                kapasiteoran=0.0
            )
        )

    # ===============================
    # 4. VERİTABANI GÜNCELLEME (DEPO)
    # ===============================
    Depo.objects.all().delete() # Eski depoları temizle
    Depo.objects.bulk_create(depo_objeleri)
    print(f"Başarıyla {len(depo_objeleri)} yeni depo kaydedildi.")

    # ===============================
    # 5. TOPLANMA ALANLARINA DEPO ATAMASI
    # ===============================
    # Kaydedilen depoları tekrar çekerek ID'lerini alıyoruz
    kaydedilen_depolar = list(Depo.objects.filter(kullaniciID=hedef_kullanici).order_by('-depoID')[:ideal_k])[::-1]
    cluster_to_depo_map = {i: kaydedilen_depolar[i] for i in range(ideal_k)}

    all_toplanma = ToplanmaAlanlari.objects.all()
    updated_alanlar = []

    for alan in all_toplanma:
        # DataFrame üzerinden bu alanın hangi cluster'da olduğunu bul
        match = df[(df['enlem'] == alan.enlem) & (df['boylam'] == alan.boylam)]
        if not match.empty:
            cluster_id = match['cluster'].values[0]
            alan.depoID = cluster_to_depo_map[cluster_id]
            updated_alanlar.append(alan)

    # Toplanma alanlarını toplu güncelle
    if updated_alanlar:
        ToplanmaAlanlari.objects.bulk_update(updated_alanlar, ['depoID'])
        print(f"{len(updated_alanlar)} toplanma alanı ilgili depolara bağlandı.")

# ===============================
# 6. GÖRSELLEŞTİRME (OPSİYONEL)
# ===============================
plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.plot(k_range, wcss, 'bx-')
plt.title('Elbow Method')

plt.subplot(1, 2, 2)
plt.scatter(df['enlem'], df['boylam'], c=df['cluster'], cmap='viridis', alpha=0.5)
for depo in depo_objeleri:
    plt.scatter(depo.enlem, depo.boylam, s=200, c='red', marker='X')
plt.title(f'K-Means Kümeleme (k={ideal_k})')
plt.show()