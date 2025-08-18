from django.urls import path
from . import views

urlpatterns = [
    path('', views.home),
    # Excel Import API
    path('my-products/import/', views.import_user_products_view, name='import_user_products'),
    path('my-products/import/init/', views.import_user_products_init, name='import_user_products_init'),
    path('my-products/import/batch/', views.import_user_products_batch, name='import_user_products_batch'),
    path('my-products/import/finalize/', views.import_user_products_finalize, name='import_user_products_finalize'),
]