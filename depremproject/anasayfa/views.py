
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth import login
from .models import Kullanici,Rol
from django.contrib.auth.hashers import make_password

from django.contrib.auth.hashers import check_password
from django.db import connection
from django.contrib.auth.decorators import login_required
from anasayfa.models import AlanIhtiyacListesi
from .models import Urunler,Arac,YardimUlasimDetay,Depo,ToplanmaAlanlari,YardimUlasim,KullaniciYakinView,ViewAlanYetkilileri,SevkiyattaYukler,Ihtiyac,DepoYetkilisiView,VwTamamlananYardimUlasimlari,TamamlananIhtiyaclar
import re
from django.db import transaction
from datetime import date
import requests
from django.shortcuts import render
from math import radians, cos, sin, asin, sqrt
from django.http import JsonResponse


def home(request):
    url = "https://api.orhanaydogdu.com.tr/deprem/kandilli/live"
    earthquakes = []

    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            raw = resp.json().get("result", [])

            for q in raw[:10]:
                coords = q.get("geojson", {}).get("coordinates", [None, None])

                earthquakes.append({
                    "tarih": q.get("date_time"),
                    "yer": q.get("title"),
                    "mag": q.get("mag"),
                    "derinlik": q.get("depth"),
                    "lat": coords[1],   # latitude
                    "lon": coords[0],   # longitude
                })
    except Exception as e:
        print("Deprem API Hatası:", e)

    return render(request, "anasayfa/home.html", {
        "earthquakes": earthquakes
    })


# ----------------------- HESAPLAMA -----------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # metre
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)

    a = (
        sin(dLat/2)**2 +
        cos(radians(lat1)) * cos(radians(lat2)) *
        sin(dLon/2)**2
    )
    c = 2 * asin(sqrt(a))
    return R * c



# ----------------------- EN YAKIN TOPLANMA ALANI -----------------------
def en_yakin_toplanma(request):
    try:
        user_lat = float(request.GET.get("lat"))
        user_lon = float(request.GET.get("lon"))
    except:
        return JsonResponse({"error": "Konum alınamadı."}, status=400)

    en_yakin = None
    en_uzaklik = 999999999

    for alan in ToplanmaAlanlari.objects.all():
        mesafe = haversine(user_lat, user_lon, alan.enlem, alan.boylam)
        if mesafe < en_uzaklik:
            en_uzaklik = mesafe
            en_yakin = alan

    # ---> MODAL İÇİN JSON DÖNDÜRÜYORUZ <---
    return JsonResponse({
        "Ad": en_yakin.Ad,
        "mesafe": round(en_uzaklik, 2),
        "enlem": en_yakin.enlem,
        "boylam": en_yakin.boylam
    })

    

def map_page(request):
    alanlar = ToplanmaAlanlari.objects.all()

    return render(request, "anasayfa/map.html", {
        "alanlar": alanlar,
    })




from django.contrib import messages
from .models import Kullanici # Modellerinizin olduğu yerden Kullanici'yi içe aktarın
from django.contrib.auth.hashers import check_password # check_password fonksiyonunu dahil edin

from django.contrib.auth import login
from django.conf import settings
def login_view(request):
    if request.method != "POST":
        return render(request, "anasayfa/login.html")

    identifier = request.POST.get("username")
    password = request.POST.get("password")
    selected_role = request.POST.get("user_type")
    next_url = request.POST.get('next') or request.GET.get('next')

    ROLE_MAP = {
        "citizen": 1,
        "area_officer": 2,
        "warehouse_officer": 3,
        "driver": 4
    }
    try:
        user = Kullanici.objects.filter(email=identifier).first()
        if user is None:
            if identifier.isdigit():
                user = Kullanici.objects.filter(TC=identifier).first()

        if user is None:
        # ❌ Context dictionary ile hata mesajı (ViewBag/ViewData mantığı)
            return render(request, "anasayfa/login.html", {
            "error": "Email veya TC ile kayıtlı kullanıcı bulunamadı."
        })
        if not check_password(password, user.Sifre):
                return render(request, "anasayfa/login.html", {
                    "error": "Şifre hatalı."
                })
        
                # --- Rol Doğrulama ---
        selected_role_id = ROLE_MAP.get(selected_role)

        if user.rolID_id != selected_role_id:
            messages.error(request, "Seçtiğiniz rol bu hesaba ait değil! Lütfen doğru kullanıcı tipini seçin.")
            return render(request, "anasayfa/login.html")

        # --- Session Kaydı (Model değil sadece integer veya string sakla!) ---
        request.session["kullaniciID"] = user.kullaniciID
        request.session["ad"] = user.Ad
        request.session["rolID"] = user.rolID_id  # <-- ÖNEMLİ DÜZELTME
        request.session["alanID"] = user.alanID_id

        # next varsa önce oraya git
        if next_url:
            return redirect(next_url)

        # rol bazlı yönlendirme
        if user.rolID_id == 1:
            return redirect("citizen_dashboard")
        elif user.rolID_id == 2:
            return redirect("area_officer_dashboard")
        elif user.rolID_id == 3:
            return redirect("warehouse_dashboard")
        elif user.rolID_id == 4:
            return redirect("driver_dashboard")

        return redirect("home")

    except Exception as e:
        print("Login Error:", e)
        return render(request, "anasayfa/login.html", {
            "error": f"Hata: {e}"
    })



def register_view(request):
    roller = Rol.objects.all()

    if request.method == 'POST':
        ad = request.POST.get('ad')
        soyad = request.POST.get('soyad')
        tc_kimlik = request.POST.get('tc_kimlik')
        email = request.POST.get('email')
        telefon = request.POST.get('telefon_bilgisi')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        cinsiyet = request.POST.get('cinsiyet') == 'True'
        yas = request.POST.get('yas')
        rolID = request.POST.get('rolID')

        # Şifre kontrolü
        if password != password2:
            return render(request, 'anasayfa/register.html', {
                'error': 'Şifreler eşleşmiyor!',
                'roller': roller
            })

        hashed_password = make_password(password)

        try:
            secilen_rol = Rol.objects.get(rolID=rolID)
            
            yeni_kullanici = Kullanici(
                Ad=ad,
                Soyad=soyad,
                TC=tc_kimlik,
                email=email,
                telefon=telefon,
                Sifre=hashed_password,
                cinsiyet=cinsiyet,
                yas=yas,
                rolID=secilen_rol,
                alanID=None,            # EKLEDİM
                yakinID=None,           # EKLEDİM
                kullaniciDurum=None
            )

            yeni_kullanici.full_clean()
            yeni_kullanici.save()

            print("Kayıt başarılı!")

            return redirect('login')

        except Exception as e:
            return render(request, 'anasayfa/register.html', {
                'error': f"Hata: {e}",
                'roller': roller
            })

    return render(request, 'anasayfa/register.html', {'roller': roller})

def logout_view(request):
    storage = messages.get_messages(request)
    for _ in storage:
        pass
    # Sadece oturumu tamamen temizliyoruz
    request.session.flush()
    return redirect("login")
 
from functools import wraps
def user_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if "kullaniciID" not in request.session:
            return redirect("login")
        return view_func(request, *args, **kwargs)
    return wrapper

def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            rol_id = request.session.get("rolID")

            if not rol_id:
                return redirect("login")

            if rol_id not in allowed_roles:
                messages.error(request, "Bu sayfaya erişim yetkiniz yok.")
                return redirect("home")

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


from django.shortcuts import render, redirect
from django.db import connection
from math import radians, sin, cos, atan2, sqrt

@user_required
@role_required([1]) 
def citizen_dashboard(request):
    kullanici_id = request.session.get("kullaniciID")
    if not kullanici_id:
        return redirect("login")

    # --- 1) Kullanıcı bilgileri ---
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT "Ad", "Soyad", "kullaniciDurum", "enlem", "boylam"
            FROM "Kullanici"
            WHERE "kullaniciID" = %s
        """, [kullanici_id])
        row = cursor.fetchone()

    ad, soyad, durum, kullanici_lat, kullanici_lon = row

    alanlar = []
    en_yakin = None
    yetkililer = []

    # --- 2) Kullanıcı konumu varsa toplanma alanlarını getir ---
    if kullanici_lat is not None and kullanici_lon is not None:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT "alanID", "Ad", "enlem", "boylam"
                FROM "ToplanmaAlanları"
            """)
            alanlar = cursor.fetchall()

        # Mesafe hesaplama fonksiyonu
        def mesafe(lat1, lon1, lat2, lon2):
            R = 6371
            d_lat = radians(lat2 - lat1)
            d_lon = radians(lon2 - lon1)
            a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            return R * c

        # En yakın toplanma alanını bul
        min_mesafe = 999999
        for alanID, alanAd, lat, lon in alanlar:
            m = mesafe(kullanici_lat, kullanici_lon, lat, lon)
            if m < min_mesafe:
                min_mesafe = m
                en_yakin = {
                    "alanID": alanID,
                    "ad": alanAd,
                    "mesafe": round(m, 2),
                    "sure": round(m * 12, 1)  # 1 km ≈ 12 dk yürüyüş
                }

    # --- 3) En yakın alan bulunduysa o alanın yetkililerini getir ---
    if en_yakin is not None:
        yetkililer = ViewAlanYetkilileri.objects.filter(alanID=en_yakin["alanID"])

    # --- 4) Kullanıcının yakınları ---
    yakinlar = KullaniciYakinView.objects.filter(kullanici_id=kullanici_id)

    return render(request, "anasayfa/citizen_dashboard.html", {
        "kullanici": {
            "ad": ad,
            "soyad": soyad,
            "durum": durum
        },
        "en_yakin": en_yakin,
        "yakinlar": yakinlar,
        "yetkililer": yetkililer
    })


# ----------------------------
# DURUM GÜNCELLEME FONKSİYONLARI
# ----------------------------

def guvende_ol(request):
    kullanici_id = request.session.get("kullaniciID")
    if not kullanici_id:
        return redirect("login")

    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE "Kullanici"
            SET "kullaniciDurum" = 'Güvende'
            WHERE "kullaniciID" = %s
        """, [kullanici_id])

    return redirect("citizen_dashboard")


def yardim_bekliyorum(request):
    kullanici_id = request.session.get("kullaniciID")
    if not kullanici_id:
        return redirect("login")

    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE "Kullanici"
            SET "kullaniciDurum" = 'Yardım Bekliyor'
            WHERE "kullaniciID" = %s
        """, [kullanici_id])

    return redirect("citizen_dashboard")



# --- DURUMU YARDIM BEKLİYOR YAP ---
def yardim_bekliyorum(request):
    kullanici_id = request.session.get("kullaniciID")
    if not kullanici_id:
        return redirect("login")

    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE "Kullanici"
            SET "kullaniciDurum" = 'Yardım Bekliyor'
            WHERE "kullaniciID" = %s
        """, [kullanici_id])

    return redirect("citizen_dashboard")

def yakin_ekle(request):
    if request.method == "POST":
        kullanici_id = request.session.get("kullaniciID")
        tc = request.POST.get("yakinTC")

        if not tc:
            messages.error(request, "TC giriniz")
            return redirect("citizen_dashboard")

        with connection.cursor() as cursor:
            cursor.execute("""SELECT sp_yakin_ekle_tc(%s, %s)""", [kullanici_id, tc])
            sonuc = cursor.fetchone()[0]

        messages.info(request, sonuc)
        return redirect("citizen_dashboard")
def yakin_durum_guncelle(request):
    if request.method == "POST":
        yakin_id = request.POST.get("yakinID")
        yeni_durum = request.POST.get("durum")

        # Güncelleme
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE "Kullanici"
                SET "kullaniciDurum" = %s
                WHERE "kullaniciID" = %s
            """, [yeni_durum, yakin_id])

        messages.success(request, "Yakının durumu güncellendi.")
        return redirect("citizen_dashboard")

# ============================================================
# ➡️ ALAN SORUMLUSU DASHBOARD
@user_required
@role_required([2])
def area_officer_dashboard(request):
    current_kullanici_id = request.session.get("kullaniciID")
    if not current_kullanici_id:
        return render(request, 'hata.html', {'mesaj': 'Oturum bilgisi eksik.'})

    try:
        kullanici = Kullanici.objects.get(kullaniciID=current_kullanici_id)
        current_alan_id = kullanici.alanID_id
        request.session["alanID"] = current_alan_id

        if current_alan_id is None:
            return render(request, 'anasayfa/areaofficer.html', {
                'ihtiyaclar': [],
                'urunler': [],
                'tamamlanan_ihtiyaclar': [],
                'hata': 'Bu kullanıcının atanmış bir toplanma alanı yok.'
            })

    except Kullanici.DoesNotExist:
        return render(request, 'hata.html', {'mesaj': 'Kullanıcı bulunamadı.'})

    # -------------------------
    # 📌 İHTİYAÇ LİSTESİ
    # -------------------------
    ihtiyac_qs = AlanIhtiyacListesi.objects.filter(alanID=current_alan_id).exclude(durum="Tamamlandı")
    ihtiyaclar_listesi = [{
        "urun": item.urunAd,
        "miktar": item.miktar,
        "durum": item.durum,
    } for item in ihtiyac_qs]

    tamamlanan_ihtiyaclar_qs = TamamlananIhtiyaclar.objects.filter(alanID=current_alan_id)
    tamamlanan_ihtiyaclar_listesi = [{
        "urun": i.urunAd,
        "miktar": i.yukMiktar,
        "durum": i.durum,
    } for i in tamamlanan_ihtiyaclar_qs]

    # -------------------------
    # 📌 TOPLAM KİŞİ
    # -------------------------
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM fn_vatandas_by_alan(%s)", [current_alan_id])
        toplam_kisi_row = cursor.fetchone()
        toplam_kisi = toplam_kisi_row[0] if toplam_kisi_row else 0

    # -------------------------
    # 📌 KAPASİTE ve DOLULUK ORANI
    # -------------------------
    with connection.cursor() as cursor:
        cursor.execute('SELECT kapasite FROM "ToplanmaAlanları" WHERE "alanID" = %s', [current_alan_id])
        kapasite_row = cursor.fetchone()

    kapasite = kapasite_row[0] if kapasite_row else 0
    doluluk_orani = round((toplam_kisi / kapasite) * 100, 2) if kapasite > 0 else 0

    # -------------------------
    # 📌 İHTİYAÇ DURUMLARI
    # -------------------------
    bekleyen_ihtiyac = ihtiyac_qs.filter(durum="beklemede").count()
    tamamlanan_ihtiyac = tamamlanan_ihtiyaclar_qs.filter(durum="Tamamlandı").count()

    urunler = Urunler.objects.all()

    # -------------------------
    # 📌 ALANIN TÜM VATANDAŞLARI
    # -------------------------
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM fn_vatandas_by_alan(%s) ORDER BY ad, soyad", [current_alan_id])
        columns = [col[0] for col in cursor.description]
        data = cursor.fetchall()
    tum_vatandas = [dict(zip(columns, row)) for row in data]

    # -------------------------
    # Template render
    # -------------------------
    return render(request, "anasayfa/areaofficer.html", {
        'ihtiyaclar': ihtiyaclar_listesi,
        'urunler': urunler,
        'toplam_kisi': toplam_kisi,
        'kapasite': kapasite,
        'doluluk_orani': doluluk_orani,
        'bekleyen_ihtiyac': bekleyen_ihtiyac,
        'tamamlanan_ihtiyac': tamamlanan_ihtiyac,
        'tum_vatandas': tum_vatandas,  # yeni eklendi
        'tamamlanan_ihtiyaclar': tamamlanan_ihtiyaclar_listesi,
    })


@user_required
@role_required([2])
def kisi_durum_guncelle(request, kisi_id):
    if request.method == "POST":
        yeni_durum = request.POST.get("durum")
        alan_id = request.session.get("alanID")

        if not yeni_durum or alan_id is None:
            messages.error(request, "Durum veya AlanID eksik!")
            return redirect("area_officer_dashboard")

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # Alan yetkilisinin kendi alanındaki kullanıcıyı güncellemesi
                    cursor.execute(
                        'UPDATE "Kullanici" SET "kullaniciDurum" = %s WHERE "kullaniciID" = %s AND "alanID" = %s;',
                        [yeni_durum, kisi_id, alan_id]
                    )
            messages.success(request, f"Kullanıcı durumu başarıyla güncellendi.")
        except Exception as e:
            messages.error(request, f"Durum güncellenemedi: {e}")

    return redirect("area_officer_dashboard")
# ➕ KULLANICI EKLEME
# ============================================================
@user_required
@role_required([2])
def kullanici_ekle(request):
    if request.method == "POST":
        try:
            tc = int(request.POST.get("tc"))
            telefon = int(request.POST.get("telefon"))
            ad = request.POST.get("ad")
            soyad = request.POST.get("soyad")
            yas = int(request.POST.get("yas"))
            cinsiyet = request.POST.get("cinsiyet") == '1'
            alan_id = request.session.get("alanID")

            if alan_id is None:
                messages.error(request, "AlanID bulunamadı!")
                return redirect("area_officer_dashboard")

            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        'SELECT "sp_kullanici_ekle"(%s::BIGINT, %s::BIGINT, %s::TEXT, %s::TEXT, %s::SMALLINT, %s::BOOLEAN, %s::INT);',
                        [tc, telefon, ad, soyad, yas, cinsiyet, alan_id]
                    )
                    sonuc = cursor.fetchone()[0]

            match = re.search(r'ID\s*=\s*(\d+)', sonuc)
            if not match:
                messages.error(request, f"Kullanıcı eklendi fakat ID döndürülmedi → {sonuc}")
                return redirect("area_officer_dashboard")

            new_id = match.group(1)
            messages.success(request, f"Kullanıcı başarıyla eklendi. ID: {new_id}")

        except Exception as e:
            messages.error(request, f"Kayıt başarısız: {e}")

        return redirect("area_officer_dashboard")

    return redirect("area_officer_dashboard")



# ============================================================
# ➕ İHTİYAÇ EKLEME
# ============================================================
def ihtiyac_ekle(request):
    if request.method == "POST":
        try:
            alan_id = request.session.get("alanID")
            urun_id = int(request.POST.get("urunID"))
            miktar = int(request.POST.get("miktar"))

            with connection.cursor() as cursor:
                cursor.execute(
                    "CALL sp_ihtiyac_ekle_procedure(%s, %s, %s)",
                    [alan_id, urun_id, miktar]
                )

        except Exception as e:
            messages.error(request, f"Hata: {e}")

    return redirect("area_officer_dashboard")




# ======================DEPO YETKİLİSİ

from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages

@user_required
@role_required([3])
def warehouse_dashboard(request):
    # 1) Giriş yapan kullanıcının ID'sini sessiondan al
    kullanici_id = request.session.get("kullaniciID")

    if not kullanici_id:
        return redirect("login")

    # 2) Kullanıcının deposunu çek
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT "depoID", "depoKapasite"
            FROM "Depo"
            WHERE "kullaniciID" = %s
            LIMIT 1
        """, [kullanici_id])
        depo = cursor.fetchone()

    if not depo:
        return render(request, "anasayfa/warehouse.html", {
            "hata": "Bu kullanıcıya atanmış depo bulunamadı."
        })

    depo_id = depo[0]
    depoKapasite = depo[1]

    # 3) Ürün listesini çek
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT "urunID", "urunAd", "urunHacim"
            FROM "urunler"
        """)
        urunler = cursor.fetchall()

    # Ürünleri dict formatına çevir
    urunler_list = [
        {"urunID": u[0], "urunAd": u[1], "urunHacim": u[2]} for u in urunler
    ]

    mesaj = None
    hata = None

    # 4) ÜRÜN EKLEME POST GELİRSE
    if request.method == "POST":
        urun_id = request.POST.get("urun_id")
        miktar = request.POST.get("miktar")

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT depo_urun_ekle(%s, %s, %s)
                """, [depo_id, urun_id, miktar])

                sonuc = cursor.fetchone()[0]

            # Hata mı başarı mı ayırıyoruz
            if "HATA" in sonuc or "AŞIM" in sonuc:
                hata = sonuc
            else:
                mesaj = sonuc

        except Exception as e:
            hata = f"Hata oluştu: {str(e)}"

    # 5) Depodaki ürünleri çek
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT u."urunAd",
                   du."urunMiktar",
                   u."urunHacim",
                   (du."urunMiktar" * u."urunHacim") AS toplam_hacim
            FROM "depo_urun" du
            JOIN "urunler" u ON u."urunID" = du."urunID"
            WHERE du."depoID" = %s
        """, [depo_id])

        depo_urunler_raw = cursor.fetchall()

    depo_urunler = [
        {
            "urunAd": u[0],
            "urunMiktar": u[1],
            "urunHacim": u[2],
            "toplam_hacim": u[3],
        }
        for u in depo_urunler_raw
    ]

    return render(request, "anasayfa/warehouse.html", {
        "depo_id": depo_id,
        "depoKapasite": depoKapasite,
        "urunler": urunler_list,
        "depo_urunler": depo_urunler,
        "mesaj": mesaj,
        "hata": hata,
    })
@user_required
@role_required([3])
def talep_yonetim(request):
    mesaj = None
    hata = None

    kullanici_id = request.session.get("kullaniciID")
    if not kullanici_id:
        return redirect("login")

    # 🔹 Kullanıcının deposunu al
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT "depoID"
            FROM "Depo"
            WHERE "kullaniciID" = %s
            LIMIT 1
        """, [kullanici_id])
        depo = cursor.fetchone()

    if not depo:
        hata = "Bu kullanıcıya ait depo bulunamadı."
        depo_id = None
    else:
        depo_id = depo[0]

    # ======================================================
    # ONAY + YÜK + ULAŞIM (TRANSACTION)
    if request.method == "POST" and "onayla" in request.POST and depo_id:

        ihtiyac_id = request.POST.get("ihtiyac_id")

        try:
            # 🔒 TRANSACTION BAŞLIYOR
            with transaction.atomic():

                with connection.cursor() as cursor:

                    # 1️⃣ İhtiyaç durumunu güncelle
                    cursor.execute('CALL sp_ihtiyac_onayla(%s)', [ihtiyac_id])

                    # 2️⃣ İhtiyaç bilgilerini al
                    cursor.execute("""
                        SELECT "alanID", "urunID", "ihtiyacmiktar"
                        FROM "ihtiyac"
                        WHERE "ihtiyacID" = %s
                    """, [ihtiyac_id])

                    row = cursor.fetchone()
                    if not row:
                        raise Exception("İhtiyaç bilgileri alınamadı.")

                    alan_id, urun_id, miktar = row

# 3️⃣ YukDetay oluştur
                    cursor.execute(
                        """
                        INSERT INTO "YukDetay" ("urunID", "yukMiktar")
                        VALUES (%s, %s)
                        RETURNING "yukID"
                        """,
                        [urun_id, miktar]
                    )

                    row = cursor.fetchone()
                    if not row:
                        raise Exception("YukDetay oluşturulamadı.")

                    yuk_id = row[0]


                    # 4️⃣ Yardım Ulaşımı oluştur
                    cursor.execute("""
                        INSERT INTO "YardimUlasimi"
                            ("depoID", "alanID", "yukID", "ihtiyacID", "urunID")
                        VALUES (%s, %s, %s, %s, %s)
                    """, [depo_id, alan_id, yuk_id, ihtiyac_id, urun_id])

            # ✅ BURAYA GELİRSE HER ŞEY COMMIT
            mesaj = "✅ Talep onaylandı, yük ve yardım ulaşımı oluşturuldu."

        except Exception as e:
            # ❌ HATA OLURSA OTOMATİK ROLLBACK
            hata = f"❌ Transaction iptal edildi: {str(e)}"

    if request.method == "POST" and "gorev_atama" in request.POST:
        try:
            ihtiyac_id = request.POST.get("ihtiyac_id")

            if not ihtiyac_id:
                raise Exception("İhtiyaç ID alınamadı.")

            with transaction.atomic():
                with connection.cursor() as cursor:

                    # 1️⃣ İHTİYAÇ ID → ULAŞIM ID BUL
                    cursor.execute(
                        '''
                        SELECT "ulasimID"
                        FROM "YardimUlasimi"
                        WHERE "ihtiyacID" = %s
                        LIMIT 1;
                        ''',
                        [ihtiyac_id]
                    )

                    row = cursor.fetchone()

                    if not row:
                        raise Exception("Bu ihtiyaca ait yardım ulaşımı bulunamadı.")

                    ulasim_id = row[0]
                    print("✅ Ulaşım ID:", ulasim_id)

                    # 2️⃣ FONKSİYONA ULAŞIM ID GÖNDER
                    cursor.execute(
                        'SELECT gorev_atama(%s);',
                        [ulasim_id]
                    )

            mesaj = "🚚 Görev ataması başarıyla yapıldı."

        except Exception as e:
            hata = f"❌ Görev atama hatası: {str(e)}"

    # ======================================================
    # LİSTE
    # ======================================================
    ihtiyaclar = AlanIhtiyacListesi.objects.all().order_by("-ihtiyacID")

    return render(request, "anasayfa/talepyonetim.html", {
        "ihtiyaclar": ihtiyaclar,
        "mesaj": mesaj,
        "hata": hata
    })


def dictfetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
@user_required
@role_required([3])
def depo_sevkiyat_takip(request):
    kullanici_id = request.session.get("kullaniciID")

    if not kullanici_id:
        return redirect("login")

    # Kullanıcının deposunu bul
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT "depoID"
            FROM "Depo"
            WHERE "kullaniciID" = %s
            LIMIT 1
        """, [kullanici_id])
        depo = cursor.fetchone()

    if not depo:
        return render(request, "anasayfa/depo_sevkiyat.html", {
            "hata": "Bu kullanıcıya bağlı depo bulunamadı."
        })

    depo_id = depo[0]

    mesaj = None
    hata = None


    # Sevkiyatlar view'dan geliyor
    sevkiyatlar = YardimUlasimDetay.objects.filter(depoID=depo_id)

    return render(request, "anasayfa/depo_sevkiyat.html", {
        "sevkiyatlar": sevkiyatlar,
        "mesaj": mesaj,
        "hata": hata,
    })
@user_required
@role_required([3])
def gecmis_sevkiyatlar(request):
    kullanici_id = request.session.get("kullaniciID")

    if not kullanici_id:
        return redirect("login")

    # Kullanıcının deposunu bul
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT "depoID"
            FROM "Depo"
            WHERE "kullaniciID" = %s
            LIMIT 1
        """, [kullanici_id])
        depo = cursor.fetchone()

    if not depo:
        return render(request, "anasayfa/gecmis_sevkiyatlar.html", {
            "hata": "Bu kullanıcıya bağlı depo bulunamadı."
        })

    depo_id = depo[0]

    # Geçmiş sevkiyatlar
    gecmis_sevkiyatlar = VwTamamlananYardimUlasimlari.objects.filter(depoID=depo_id)

    return render(request, "anasayfa/gecmis_sevkiyatlar.html", {
        "gecmis_sevkiyatlar": gecmis_sevkiyatlar,
    })

################################################Surucu Dashboard #####################################################
@user_required
@role_required([4])
def driver_dashboard(request):
    kullanici_id = request.session.get("kullaniciID")

    if not kullanici_id:
        return redirect("login")

    # 1) Sürücüye ait aracı bul
    try:
        arac = Arac.objects.get(kullaniciID=kullanici_id)
    except Arac.DoesNotExist:
        return render(request, "anasayfa/driver_dashboard.html", {
            "mesaj": "Sistemde üzerinize kayıtlı bir araç bulunamadı."
        })

    detaylar = YardimUlasimDetay.objects.filter(aracID=arac.aracID)

    kalkis = None
    varis = None

    # Harita için koordinatlar
    start_lat = start_lng = None
    end_lat = end_lng = None

    if detaylar.exists():
        ilk = detaylar.first()
        kalkis = ilk.depoAd
        varis = ilk.alanAd

        # --- Depo koordinatları DB'den ---
        try:
            depo = Depo.objects.get(Ad=ilk.depoAd)
            start_lat = depo.enlem
            start_lng = depo.boylam
        except Depo.DoesNotExist:
            pass

        # --- Toplanma Alanı koordinatları DB'den ---
        try:
            alan = ToplanmaAlanlari.objects.get(Ad=ilk.alanAd)
            end_lat = alan.enlem
            end_lng = alan.boylam
        except ToplanmaAlanlari.DoesNotExist:
            pass

    # 3) Yük detayı (VIEW’den)
    yukler = SevkiyattaYukler.objects.filter(aracID=arac.aracID)

    # 4) Alan Yetkilileri (VIEW)
    alan_yetkilileri = []
    if varis:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT ad, soyad, telefon, email
                FROM view_alan_yetkilileri
                WHERE "Ad" = %s
            """, [varis])
            alan_yetkilileri = dictfetchall(cursor)


    depo_yetkilileri = []
    if kalkis:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT ad, soyad, telefon, email
                FROM depo_yetkilileri
                WHERE "Ad" = %s
            """, [kalkis])
            depo_yetkilileri = dictfetchall(cursor)


    return render(request, "anasayfa/driver_dashboard.html", {
        "arac": arac,
        "yukler": yukler,
        "detaylar": detaylar,
        "kalkis": kalkis,
        "varis": varis,

        # 🔹 Harita koordinatları
        "start_lat": start_lat,
        "start_lng": start_lng,
        "end_lat": end_lat,
        "end_lng": end_lng,

        # 🔹 Sürücünün göreceği ek tablolar
        "alan_yetkilileri": alan_yetkilileri,
        "depo_yetkilileri": depo_yetkilileri,
    })

def surucu_tamamlandi(request, ulasim_id):
    if request.method == "POST":

        with transaction.atomic():

            # --- Yardım Ulaşımı ---
            ulasim = get_object_or_404(YardimUlasim, ulasimID=ulasim_id)
            ulasim.durum = "Tamamlandı"
            ulasim.save()

            # --- Araç Durumu ---
            arac = ulasim.aracID      # 👈 ekstra sorguya gerek yok
            arac.durum = "Beklemede"
            arac.save()

            
# --- İhtiyaç Durumu ---
            Ihtiyac.objects.filter(
            alanID=ulasim.alanID_id, 
            urunID=ulasim.urunID_id 
        ).update(ihtiyacdurum="Tamamlandı")
        return redirect("driver_dashboard")

