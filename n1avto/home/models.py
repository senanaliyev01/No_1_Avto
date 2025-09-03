from django.db import models
import re

class Firma(models.Model):
    adi = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Firma'
        verbose_name_plural = 'Firmalar'
    
    def __str__(self):
        return f'{self.adi}'

class Mehsul(models.Model):
    adi = models.CharField(max_length=100)
    kod = models.CharField(max_length=100)
    firma = models.ForeignKey(Firma, on_delete=models.CASCADE)
    kodlar = models.TextField(null=True, blank=True)
    qiymet = models.DecimalField(max_digits=10, decimal_places=2)
    sekil = models.ImageField(upload_to='mehsul_sekilleri',default='mehsul_sekilleri/noimage.webp', null=True, blank=True)
    stok = models.IntegerField()

    class Meta:
        verbose_name = 'Mehsul'
        verbose_name_plural = 'Mehsullar'
    
    def __str__(self):
        return f'{self.adi} - {self.kod}'

    def save(self, *args, **kwargs):
        if self.kodlar:
            # Yalnız hərf, rəqəm və boşluq saxla
            self.kodlar = re.sub(r'[^a-zA-Z0-9 ]', '', self.kodlar)
        super().save(*args, **kwargs)




class Reklam(models.Model):
    adi = models.CharField(max_length=100)
    foto = models.ImageField(upload_to='reklam_sekilleri')

    class Meta:
        verbose_name = 'Reklam'
        verbose_name_plural = 'Reklamlar'
    
    def __str__(self):
        return f'{self.adi}'

