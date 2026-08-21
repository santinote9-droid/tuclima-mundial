from django.contrib import admin
from django.urls import path, include
from mundo import views  # Importamos las vistas
from mundo.views import home, comparador_modelos, api_papers
from mundo.seo import robots_txt, sitemap_xml, ads_txt

# Manejadores de error personalizados
handler403 = 'mundo.views.error_403'
handler404 = 'mundo.views.error_404'
handler500 = 'mundo.views.error_500'



urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    path('ads.txt', ads_txt, name='ads_txt'),
    path('', views.landing, name='landing'),  # Bienvenida pública
    path('clima/', views.home, name='home'),  # Dashboard clima (antes en /)
    path('api/clima-data/', views.clima_data_api, name='clima_data_api'),  # API para datos del clima en JSON
    path('agro/', views.agro, name='agro'),     # MODO AGRO 🚜
    path('agro/<slug:funcion>/', views.agro, name='agro_pro'),
    path('naval/', views.naval, name='naval'),  # MODO NAVAL ⚓
    path('naval/<slug:funcion>/', views.naval, name='naval_pro'),
    path('aereo/', views.aereo, name='aereo'),  # MODO AÉREO ✈️
    path('aereo/<slug:funcion>/', views.aereo, name='aereo_pro'),
    path('energia/', views.energia, name='energia'), # ENERGÍA ⚡
    path('energia/<slug:funcion>/', views.energia, name='energia_pro'),

    # API Estadística — Poisson, boxplot, frecuencias relativas, test de hipótesis (por sector)
    path('api/estadisticas/agro/', views.estadisticas_agro, name='estadisticas_agro'),
    path('api/estadisticas/naval/', views.estadisticas_naval, name='estadisticas_naval'),
    path('api/estadisticas/aereo/', views.estadisticas_aereo, name='estadisticas_aereo'),
    path('api/estadisticas/energia/', views.estadisticas_energia, name='estadisticas_energia'),
    
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
    path('api/historial/export/', views.exportar_historial_punto, name='exportar_historial_punto'),
    path('api/v1/widget/', views.api_widget_clima, name='api_widget_clima'),
    path('widget-demo/', views.widget_demo, name='widget_demo'),

    # Endpoint para papers de arXiv
    path('api/papers/', api_papers, name='api_papers'),
    path('api/ciencia/buscar/', views.api_ciencia_buscar, name='api_ciencia_buscar'),

    path('espacio/', views.meteorologia_espacial, name='espacio'),

    path('legal/', views.legal, name='legal'),
    path('legal/terminos/', views.legal_terminos, name='legal_terminos'),
    path('legal/privacidad/', views.legal_privacidad, name='legal_privacidad'),
    path('legal/cookies/', views.legal_cookies, name='legal_cookies'),
    path('legal/reembolsos/', views.legal_reembolsos, name='legal_reembolsos'),
    path('aceptar-terminos/', views.aceptar_terminos, name='aceptar_terminos'),
    
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
    path('api/tokens/consumir/', views.api_consumir_tokens, name='api_consumir_tokens'),
    path('api/chat-ia/', views.api_chat_ia, name='api_chat_ia'),
    path('api/tokens/recargar/', views.admin_recargar_tokens, name='admin_recargar_tokens'),
    path('recargar-tokens/', views.recargar_tokens_view, name='recargar_tokens'),
    path('activar-plan/', views.seleccionar_pago_tokens, name='seleccionar_pago_tokens'),
    path('confirmar-manual-tokens/', views.confirmar_manual_tokens, name='confirmar_manual_tokens'),
    path('pagar-tokens/', views.mp_crear_preferencia_tokens, name='mp_crear_preferencia_tokens'),
    path('tokens-retorno/', views.tokens_retorno_view, name='tokens_retorno'),

    # Alertas Proactivas — endpoint para n8n + banner web
    path('api/alertas/usuarios/', views.api_alertas_usuarios, name='api_alertas_usuarios'),
    path('api/alertas/web/', views.api_alertas_web, name='api_alertas_web'),

    # Histórico climático (Fase 2 · n8n + BigQuery)
    path('api/n8n/ubicaciones/', views.api_n8n_ubicaciones, name='api_n8n_ubicaciones'),
    path('api/estadisticas/<str:sector>/historico/', views.api_estadisticas_historico, name='api_estadisticas_historico'),

    # Devorador de Reportes — Procesamiento Documental con IA
    path('devorador/', views.devorador_vista, name='devorador'),
    path('api/devorador/', views.devorador_api, name='devorador_api'),

    # Multi-ubicación
    path('api/ubicaciones/', views.api_ubicaciones, name='api_ubicaciones'),
    path('api/ubicaciones/<int:pk>/', views.api_ubicacion_delete, name='api_ubicacion_delete'),

    # Modales interactivos (personalización / alertas / notas) — agro/naval/aereo/energia
    path('api/modal/config/', views.api_modal_config, name='api_modal_config'),
    path('api/modal/alertas/', views.api_modal_alertas, name='api_modal_alertas'),
    path('api/modal/notas/', views.api_modal_notas, name='api_modal_notas'),
    path('api/agro/gdd-siembra/', views.api_agro_gdd_siembra, name='api_agro_gdd_siembra'),

    # Reportes programados
    path('mis-reportes/', views.reportes_programados, name='reportes_programados'),

    # API Key personal
    path('mi-api-key/', views.api_key_personal, name='api_key_personal'),

    # Historial de anomalías
    path('historial-anomalias/', views.historial_anomalias, name='historial_anomalias'),
]


