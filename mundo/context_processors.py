from django.conf import settings


def site_seo(request):
    """Inyecta URL canónica del sitio y verificación Google en todos los templates."""
    site_url = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if not site_url:
        # Fallback: construir desde el request (útil en local)
        site_url = request.build_absolute_uri('/').rstrip('/')
    return {
        'SITE_URL': site_url,
        'GOOGLE_SITE_VERIFICATION': getattr(settings, 'GOOGLE_SITE_VERIFICATION', '') or '',
    }
