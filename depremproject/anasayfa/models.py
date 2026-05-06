from django.db import models


# ======================
#        ROL
# ======================
class Rol(models.Model):
    rolID = models.AutoField(primary_key=True)
    rolAd = models.TextField(max_length=100)

    class Meta:
        managed = False          # Django tabloyu oluşturmasın
        db_table = '"Rol"'

class ToplanmaAlanlari(models.Model):
    alanID = models.AutoField(primary_key=True)
    enlem = models.FloatField()
    boylam = models.FloatField()
    alan = models.IntegerField()
    ilceAd = models.CharField(max_length=255)
    mahalleAdı = models.CharField(max_length=255)
    depoID = models.ForeignKey(
        'Depo', on_delete=models.SET_NULL, null=True, blank=True, db_column="depoID")


    class Meta:
        db_table = '"ToplanmaAlanları"'

    def __str__(self):
        return self.Ad
# ======================
#       KULLANICI
# ======================
class Kullanici(models.Model):
    kullaniciID = models.AutoField(primary_key=True)
    rolID = models.ForeignKey(
        Rol, on_delete=models.CASCADE, db_column="rolID"
    )
    email = models.CharField(max_length=255)
    telefon = models.CharField(max_length=20)
    yas = models.IntegerField(null=True)
    alanID = models.ForeignKey(
        ToplanmaAlanlari,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="alanID"
    )
    kullaniciDurum = models.CharField(max_length=50, null=True,blank=True,default='bilinmiyor')
    yakinID = models.CharField(max_length=50, null=True,blank=True)
    Ad = models.CharField(max_length=255)
    Soyad = models.CharField(max_length=255)
    Sifre = models.CharField(max_length=255)
    TC = models.CharField(max_length=11)
    cinsiyet = models.BooleanField(default=True)

    rolID = models.ForeignKey(Rol, on_delete=models.CASCADE, db_column="rolID")

    class Meta:
        db_table = '"Kullanici"'

    def __str__(self):
        return f"{self.ad} {self.soyad}"





# ======================
#     URUNLER
# ======================
class Urunler(models.Model):
    urunID = models.AutoField(primary_key=True)
    urunAd = models.CharField(max_length=255)
    urunHacim = models.IntegerField()
    Aciliyet = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = '"urunler"'

    def __str__(self):
        return self.urunAd


# ======================
#       İHTİYAÇ
# ======================
class Ihtiyac(models.Model):
    ihtiyacID = models.AutoField(primary_key=True)
    urunID = models.ForeignKey(Urunler, on_delete=models.CASCADE, db_column="urunID")
    ihtiyacmiktar = models.IntegerField()
    alanID = models.ForeignKey(
        ToplanmaAlanlari, on_delete=models.CASCADE, db_column="alanID"
    )
    ihtiyacdurum = models.CharField(max_length=50)
    talepZamanı = models.DateTimeField()
    

    class Meta:
        db_table = '"ihtiyac"'


# ======================
#         DEPO
# ======================
class Depo(models.Model):
    depoID = models.AutoField(primary_key=True)
    enlem = models.FloatField()
    boylam = models.FloatField()
    kullaniciID = models.ForeignKey(Kullanici, on_delete=models.CASCADE, db_column="kullaniciID")
    depoKapasite = models.IntegerField()
    kapasiteoran = models.FloatField()
    Ad = models.CharField(max_length=255)

    class Meta:
        db_table = '"Depo"'


# ======================
#      DEPO ÜRÜNLERİ
# ======================
class DepoUrunler(models.Model):
    depoUrunID = models.AutoField(primary_key=True)
    depoID = models.ForeignKey(Depo, on_delete=models.CASCADE, db_column="depoID")
    urunID = models.ForeignKey(Urunler, on_delete=models.CASCADE, db_column="urunID")
    urunMiktar = models.IntegerField()

    class Meta:
        db_table = '"depo_urun"'


# ======================
#     YÜK KAYDI
# ======================
class YukKaydi(models.Model):
    yukID = models.AutoField(primary_key=True)
    urunID = models.ForeignKey(Urunler, on_delete=models.CASCADE, db_column="urunID")
    yukMiktar = models.IntegerField()

    class Meta:
        db_table = '"YukDetay"'


# ======================
#       ARAÇLAR
# ======================
class Arac(models.Model):
    #enlem = models.FloatField()
    #boylam = models.FloatField()
    #son_guncelleme = models.DateTimeField(auto_now=True)
    aracID = models.AutoField(primary_key=True)
    plaka = models.CharField(max_length=255)
    durum = models.CharField(max_length=255)
    kapasite = models.IntegerField()
    aracTip = models.CharField(max_length=255)
    kullaniciID = models.IntegerField()
    depoID = models.ForeignKey(Depo, on_delete=models.CASCADE, db_column="depoID")

    class Meta:
        db_table = '"Arac"'






# ======================
#    YARDIM ULASIMI
# ======================
class YardimUlasim(models.Model):
    ulasimID = models.AutoField(primary_key=True)
    depoID = models.ForeignKey(Depo, on_delete=models.CASCADE, db_column="depoID")
    alanID = models.ForeignKey(ToplanmaAlanlari, on_delete=models.CASCADE, db_column="alanID")
    aracID = models.ForeignKey(
        Arac,
        on_delete=models.CASCADE,
        db_column="aracID",
        null=True,
        blank=True
    )
    yukID=models.ForeignKey(YukKaydi, on_delete=models.CASCADE, db_column="yukID")
    durum = models.CharField(max_length=255)
    urunID = models.ForeignKey(
        "Urunler",
        on_delete=models.RESTRICT,
        db_column="urunID"
    )

    class Meta:
        db_table = '"YardimUlasimi"'


class ToplanmaAlaniIhtiyacVeYardim(models.Model):
    alanID = models.IntegerField()
    alan_adi = models.CharField(max_length=255)

    ihtiyacID = models.IntegerField(primary_key=True)
    urunID = models.IntegerField()

    ihtiyac_miktari = models.IntegerField()
    ihtiyac_onceligi = models.CharField(max_length=50)

    onaylanan_miktar = models.IntegerField()
    sevkiyatta_miktar = models.IntegerField()
    beklemede_miktar = models.IntegerField()

    kalan_miktar = models.IntegerField()

    class Meta:
        managed = False
        db_table = '"toplanma_alani_ihtiyac_ve_yardim"'


class SurucuSevkiyatView(models.Model):
    kullaniciid = models.IntegerField(primary_key=True)

    surucu_ad = models.CharField(max_length=100)
    surucu_soyad = models.CharField(max_length=100)
    surucu_telefon = models.CharField(max_length=20)
    surucu_email = models.CharField(max_length=150)
    surucu_tc = models.CharField(max_length=20)

    aracid = models.IntegerField()
    plaka = models.CharField(max_length=50)
    arac_durumu = models.CharField(max_length=50)
    arac_kapasitesi = models.IntegerField()
    aractip = models.CharField(max_length=50)

    ulasimid = models.IntegerField()
    depoid = models.IntegerField()
    alanid = models.IntegerField()
    yukid = models.IntegerField()
    sevkiyat_durumu = models.CharField(max_length=50)

    Ad = models.CharField(max_length=255)          # toplanma alanı adı
    depo_Ad = models.CharField(max_length=255)     # depo adı

    class Meta:
        managed = False
        db_table = '"surucu_sevkiyat_view"'


class YardimUlasimDetay(models.Model):
   # ulasimID = models.IntegerField()
    depoID = models.IntegerField(null=True)
    depoAd = models.CharField(max_length=255, null=True)
    alanID = models.IntegerField(null=True)
    alanAd = models.CharField(max_length=255, null=True)
    aracID = models.IntegerField(null=True)
    urunID = models.IntegerField(null=True)
    urunAd = models.CharField(max_length=255, null=True)
    yukID = models.IntegerField()
    durum = models.CharField(max_length=100)
    id = models.IntegerField(primary_key=True, db_column="ulasimID")


    class Meta:
        managed = False
        db_table = '"vw_yardim_ulasim_detay"'
class VwTamamlananYardimUlasimlari(models.Model):
    ulasimID = models.IntegerField(primary_key=True)
    depoID = models.IntegerField(null=True, blank=True)
    depoAd = models.CharField(max_length=255, null=True, blank=True)
    alanID = models.IntegerField(null=True, blank=True)
    alanAd = models.CharField(max_length=255, null=True, blank=True)
    aracID = models.IntegerField(null=True, blank=True)
    urunID = models.IntegerField(null=True, blank=True)
    urunAd = models.CharField(max_length=255, null=True, blank=True)
    yukID = models.IntegerField(null=True, blank=True)
    durum = models.CharField(max_length=50)
    yukMiktar = models.IntegerField(null=True, blank=True)

    class Meta:
        managed = False  # ❗ View olduğu için
        db_table = '"vw_tamamlanan_yardim_ulasimlari"'


class IhtiyacSevkiyat(models.Model):
    ihtiyacID = models.IntegerField(primary_key=True)
    urunAd = models.CharField(max_length=255)
    miktar = models.IntegerField()
    toplanmaAlani = models.CharField(max_length=255)
    durum = models.CharField(max_length=100)
    sevkiyatDurumu = models.CharField(max_length=100, null=True)

    class Meta:
        managed = False
        db_table = '"vw_ihtiyac_sevkiyat"'

class AlanIhtiyacListesi(models.Model):
    ihtiyacID = models.IntegerField(db_column="ihtiyacID", primary_key=True)
    alanID = models.IntegerField(db_column="alanID")
    alanAd = models.TextField(db_column="alanAd")
    urunID = models.IntegerField(db_column="urunID")
    urunAd = models.TextField(db_column="urunAd")
    miktar = models.IntegerField(db_column="miktar")
    durum = models.TextField(db_column="durum")


    class Meta:
        managed = False  # çünkü bu bir VIEW
        db_table = '"vw_alan_ihtiyac_listesi"'
class TamamlananIhtiyaclar(models.Model):
    urunAd = models.CharField(max_length=255)
    durum = models.CharField(db_column="durum", max_length=50)
    yukMiktar = models.IntegerField()
    alanID = models.IntegerField(db_column="alanID")
    yukID= models.IntegerField(db_column="yukID",primary_key=True)

    class Meta:
        managed = False              # ⚠️ VIEW olduğu için
        db_table = '"tamamlanan_ihtiyaclar"'



class SevkiyattaYukler(models.Model):
    yukMiktar = models.IntegerField()
    urunAd = models.CharField(max_length=255)
    aracID = models.IntegerField(primary_key=True)

    class Meta:
        managed = False  # ❗ view olduğu için
        db_table = '"view_sevkiyatta_yukler"'

class KullaniciYakinView(models.Model):
    kullanici_id = models.IntegerField()
    kullanici_ad = models.CharField(max_length=255)
    kullanici_soyad = models.CharField(max_length=255)
    kullanici_email = models.CharField(max_length=255)
    kullanici_telefon = models.CharField(max_length=50)

    yakin_id = models.IntegerField(primary_key=True)
    yakin_ad = models.CharField(max_length=255)
    yakin_soyad = models.CharField(max_length=255)
    yakin_email = models.CharField(max_length=255)
    yakin_telefon = models.CharField(max_length=50)
    yakin_durum = models.CharField(max_length=50, null=True)

    class Meta:
        managed = False  # VIEW olduğu için Django migrate etmeyecek
        db_table = '"view_kullanici_yakinlari"'



class ViewAlanYetkilileri(models.Model):
    kullaniciID = models.IntegerField(primary_key=True)
    ad = models.CharField(max_length=100)
    soyad = models.CharField(max_length=100)
    email = models.CharField(max_length=150)
    telefon = models.CharField(max_length=20, null=True)
    yas = models.IntegerField(null=True)
    cinsiyet = models.CharField(max_length=20, null=True)
    tc = models.CharField(max_length=11)

    rolAd = models.CharField(max_length=50)

    alanID = models.IntegerField()
    Ad = models.CharField(max_length=200)

    class Meta:
        managed = False  # Django bu tabloyu oluşturmaz
        db_table = '"view_alan_yetkilileri"'

class ViewDepoYetkilileri(models.Model):
    kullaniciID = models.IntegerField(primary_key=True)
    ad = models.CharField(max_length=100)
    soyad = models.CharField(max_length=100)
    email = models.CharField(max_length=150)
    telefon = models.CharField(max_length=20, null=True)
    yas = models.IntegerField(null=True)
    cinsiyet = models.CharField(max_length=20, null=True)
    tc = models.CharField(max_length=11)

    rolAd = models.CharField(max_length=50)

    alanID = models.IntegerField()
    Ad = models.CharField(max_length=200)

    class Meta:
        managed = False  # Django bu tabloyu oluşturmaz
        db_table = '"view_depo_yetkilileri"'

class DepoYetkilisiView(models.Model):
    kullaniciID = models.IntegerField(primary_key=True)

    ad = models.CharField(max_length=255)
    soyad = models.CharField(max_length=255)

    email = models.EmailField()
    telefon = models.CharField(max_length=50)

    yas = models.IntegerField()
    cinsiyet = models.CharField(max_length=50)

    tc = models.CharField(max_length=11)

    rolAd = models.CharField(max_length=255)

    depoID = models.IntegerField()
    Ad = models.CharField(max_length=255)

    class Meta:
        managed = False               # 👈 ÇOK ÖNEMLİ
        db_table = '"depo_yetkilileri"'