from django.contrib import admin
from django.urls import path, include
from mundo import views  # Importamos las vistas
from mundo.views import home, comparador_modelos, api_papers


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),          # Página Principal (Público General)
    path('agro/', views.agro, name='agro'),     # MODO AGRO 🚜
    path('naval/', views.naval, name='naval'),  # MODO NAVAL ⚓
    path('aereo/', views.aereo, name='aereo'),  # MODO AÉREO ✈️
    path('energia/', views.energia, name='energia'), # ENERGÍA ⚡
    
    path('pricing/', views.pricing, name='pricing'),
    path('activar-pro/', views.activar_suscripcion, name='activar_pro'),

    path('pagar-paypal/', views.crear_pago_paypal, name='crear_pago_paypal'),
    path('paypal-retorno/', views.paypal_retorno, name='paypal_retorno'),

    path('metodos-pago/', views.metodos_pago, name='metodos_pago'), 
    path('transferencia/', views.transferencia, name='transferencia'), 
    path('confirmar-manual/', views.confirmar_manual, name='confirmar_manual'),

    # ... tus otras rutas ...
    path('registro/', views.registro, name='registro'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('i18n/', include('django.conf.urls.i18n')),

    path('enviar-reporte/', views.procesar_reporte, name='enviar_reporte'),
    path('ayuda/', views.ayuda, name='ayuda'),

    path('ciencia/', views.ciencia, name='ciencia'),

    path('mapas/', views.mapas, name='mapas'),

    path('comparador/', comparador_modelos, name='comparador'),

    # Endpoint para papers de arXiv
    path('api/papers/', api_papers, name='api_papers'),

    path('espacio/', views.meteorologia_espacial, name='espacio'),

    path('legal/', views.legal, name='legal'),
]


