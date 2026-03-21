from django.contrib import admin
from django.urls import path, include
from mundo import views  # Importamos las vistas
from mundo.views import home, comparador_modelos, api_papers



urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),          # Página Principal (Público General)
    path('api/clima-data/', views.clima_data_api, name='clima_data_api'),  # API para datos del clima en JSON
    path('agro/', views.agro, name='agro'),     # MODO AGRO 🚜
    path('naval/', views.naval, name='naval'),  # MODO NAVAL ⚓
    path('aereo/', views.aereo, name='aereo'),  # MODO AÉREO ✈️
    path('energia/', views.energia, name='energia'), # ENERGÍA ⚡
    
    path('pricing/', views.pricing, name='pricing'),
    path('activar-pro/', views.activar_suscripcion, name='activar_pro'),

    path('pagar-paypal/', views.crear_pago_paypal, name='crear_pago_paypal'),
    path('paypal-retorno/', views.paypal_retorno, name='paypal_retorno'),

    # Lemon Squeezy
    path('ls-checkout/', views.ls_checkout, name='ls_checkout'),
    path('ls-retorno/', views.ls_retorno, name='ls_retorno'),
    path('ls-webhook/', views.ls_webhook, name='ls_webhook'),

    # MercadoPago Checkout Pro (automatizado)
    path('pagar-mercadopago/', views.mp_crear_preferencia, name='mp_crear_preferencia'),
    path('mp-webhook/', views.mp_webhook, name='mp_webhook'),
    path('mp-retorno/', views.mp_retorno, name='mp_retorno'),

    path('pago-exitoso/', views.pago_exitoso_view, name='pago_exitoso_view'),

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
    
    # URLs para funcionalidad multisectorial
    path('carga-sectorial/', views.vista_carga_archivos, name='carga_sectorial'),
    path('procesar-archivo-sectorial/', views.procesar_archivo_sectorial, name='procesar_archivo_sectorial'),
    
    # URLs para webhooks n8n
    path('probar-n8n/', views.probar_conexion_n8n, name='probar_n8n'),
    path('enviar-n8n/', views.enviar_dato_sectorial_a_n8n, name='enviar_n8n'),
    
    # URLs para feedback de IA
    path('api/guardar-feedback/', views.guardar_feedback, name='guardar_feedback'),
    path('panel-feedback/', views.panel_feedback, name='panel_feedback'),
    path('api/marcar-feedback-revisado/<int:feedback_id>/', views.marcar_feedback_revisado, name='marcar_feedback_revisado'),
    
    # Panel de administración
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    #Panel de noticias
    path('api/noticias/', views.obtener_noticias_clima, name='api_noticias'),

    # Laboratorio 3D
    path('laboratorio/', views.laboratorio, name='laboratorio'),
    path('api/laboratorio/viento/', views.api_viento_proxy, name='api_viento_proxy'),
    path('api/laboratorio/eventos/', views.api_eventos_proxy, name='api_eventos_proxy'),

    # Mi Cuenta — perfil y preferencias
    path('mi-cuenta/', views.mi_cuenta, name='mi_cuenta'),

    # Admin — acciones sobre suscripciones
    path('admin-activar-usuario/', views.admin_activar_usuario, name='admin_activar_usuario'),
    path('admin-toggle-renovacion/', views.admin_toggle_renovacion, name='admin_toggle_renovacion'),

    # Sistema de Tokens IA
    path('api/tokens/saldo/', views.api_saldo_tokens, name='api_saldo_tokens'),
    path('api/tokens/recargar/', views.admin_recargar_tokens, name='admin_recargar_tokens'),
    path('recargar-tokens/', views.recargar_tokens_view, name='recargar_tokens'),
    path('activar-plan/', views.seleccionar_pago_tokens, name='seleccionar_pago_tokens'),
    path('confirmar-manual-tokens/', views.confirmar_manual_tokens, name='confirmar_manual_tokens'),
    path('pagar-tokens/', views.mp_crear_preferencia_tokens, name='mp_crear_preferencia_tokens'),
    path('tokens-retorno/', views.tokens_retorno_view, name='tokens_retorno'),

    # Alertas Proactivas — endpoint para n8n
    path('api/alertas/usuarios/', views.api_alertas_usuarios, name='api_alertas_usuarios'),

    # Devorador de Reportes — Procesamiento Documental con IA
    path('devorador/', views.devorador_vista, name='devorador'),
    path('api/devorador/', views.devorador_api, name='devorador_api'),
]


