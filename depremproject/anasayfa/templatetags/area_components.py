from django import template
from django.db import connection
from django.template.loader import render_to_string

register = template.Library()

class SonEklenenVatandasComponent:
    template_name = "anasayfa/partials/son_eklenen_vatandas.html"

    def __init__(self, request):
        self.request = request

    def get_context_data(self):
        current_alan_id = self.request.session.get("alanID")
        if not current_alan_id:
            return {'kisiler': []}

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM fn_vatandas_by_alan(%s)
                ORDER BY kullaniciid DESC
                LIMIT 5
            """, [current_alan_id])
            columns = [col[0] for col in cursor.description]
            data = cursor.fetchall()

        kisiler_listesi = []
        for row in data:
            kisi = dict(zip(columns, row))
            kisi["ad_soyad"] = f"{kisi['ad']} {kisi['soyad']}"
            kisiler_listesi.append(kisi)

        return {'kisiler': kisiler_listesi}

@register.simple_tag(takes_context=True)
def render_son_eklenen_vatandas(context):
    request = context['request']
    component = SonEklenenVatandasComponent(request)
    return render_to_string(component.template_name, component.get_context_data())
