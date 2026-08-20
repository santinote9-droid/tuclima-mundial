from django.conf import settings


def site_seo(request):
    """Inyecta URL canónica, AdSense y flags de Weglot en todos los templates."""
    site_url = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if not site_url:
        # Fallback: construir desde el request (útil en local)
        site_url = request.build_absolute_uri('/').rstrip('/')

    adsense_client = getattr(settings, 'ADSENSE_CLIENT', '') or ''
    adsense_enabled = bool(getattr(settings, 'ADSENSE_ENABLED', False)) and bool(adsense_client)
    weglot_key = getattr(settings, 'WEGLOT_API_KEY', '') or ''
    weglot_enabled = bool(getattr(settings, 'WEGLOT_ENABLED', False)) and bool(weglot_key)

    return {
        'SITE_URL': site_url,
        'GOOGLE_SITE_VERIFICATION': getattr(settings, 'GOOGLE_SITE_VERIFICATION', '') or '',
        'ADSENSE_ENABLED': adsense_enabled,
        'ADSENSE_CLIENT': adsense_client,
        'ADSENSE_SLOT_A': getattr(settings, 'ADSENSE_SLOT_A', '') or '',
        'ADSENSE_SLOT_B': getattr(settings, 'ADSENSE_SLOT_B', '') or '',
        'ADSENSE_SLOT_C': getattr(settings, 'ADSENSE_SLOT_C', '') or '',
        'WEGLOT_ENABLED': weglot_enabled,
        'WEGLOT_API_KEY': weglot_key,
    }
