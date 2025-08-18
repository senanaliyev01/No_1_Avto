from django.contrib import admin
from .models import Mehsul, Firma, Reklam


class FirmaAdmin(admin.ModelAdmin):
    list_display = ['adi']

class ReklamAdmin(admin.ModelAdmin):
    list_display = ['adi']


class MehsulAdmin(admin.ModelAdmin):
    list_display = ['adi', 'firma', 'kod', 'qiymet', 'stok']
    search_fields = ['adi', 'kod', 'kodlar']
    list_filter = ['firma']
    change_list_template = 'admin/home/mehsul/change_list.html'





admin.site.register(Mehsul, MehsulAdmin)
admin.site.register(Firma, FirmaAdmin)
admin.site.register(Reklam, ReklamAdmin)

