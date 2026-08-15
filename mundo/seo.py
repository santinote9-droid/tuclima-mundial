"""SEO helpers: robots.txt y sitemap.xml públicos."""
from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone


def _site_base():
    base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if not base:
        base = 'https://tuclima.com.ar'
    return base


# Páginas públicas indexables (sin login)
SITEMAP_PATHS = [
    ('landing', 1.0, 'daily'),
    ('home', 1.0, 'daily'),
    ('pricing', 0.9, 'weekly'),
    ('ayuda', 0.7, 'monthly'),
    ('ciencia', 0.7, 'weekly'),
    ('mapas', 0.6, 'weekly'),
    ('laboratorio', 0.6, 'weekly'),
    ('espacio', 0.6, 'weekly'),
    ('comparador', 0.5, 'weekly'),
    ('legal', 0.3, 'yearly'),
    ('registro', 0.5, 'monthly'),
    ('login', 0.3, 'monthly'),
]


def robots_txt(request):
    base = _site_base()
    body = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Disallow: /mi-cuenta/
Disallow: /mi-api-key/
Disallow: /mis-reportes/
Disallow: /historial-anomalias/
Disallow: /carga-sectorial/
Disallow: /devorador/
Disallow: /panel-feedback/
Disallow: /admin-dashboard/
Disallow: /admin-activar-usuario/
Disallow: /admin-toggle-renovacion/
Disallow: /activar-pro/
Disallow: /pagar-
Disallow: /mp-
Disallow: /ls-
Disallow: /paypal-
Disallow: /pago-exitoso/
Disallow: /confirmar-manual
Disallow: /tokens-
Disallow: /recargar-tokens/
Disallow: /activar-plan/
Disallow: /enviar-
Disallow: /procesar-
Disallow: /probar-n8n/
Disallow: /widget-demo/

# Modos PRO (requieren login — no indexar)
Disallow: /agro/
Disallow: /naval/
Disallow: /aereo/
Disallow: /energia/

Sitemap: {base}/sitemap.xml
"""
    return HttpResponse(body, content_type='text/plain; charset=utf-8')


def sitemap_xml(request):
    base = _site_base()
    lastmod = timezone.now().date().isoformat()
    urls = []
    for name, priority, changefreq in SITEMAP_PATHS:
        try:
            path = reverse(name)
        except Exception:
            continue
        loc = f'{base}{path}'
        urls.append(
            f'  <url>\n'
            f'    <loc>{loc}</loc>\n'
            f'    <lastmod>{lastmod}</lastmod>\n'
            f'    <changefreq>{changefreq}</changefreq>\n'
            f'    <priority>{priority:.1f}</priority>\n'
            f'  </url>'
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(urls)
        + '\n</urlset>\n'
    )
    return HttpResponse(body, content_type='application/xml; charset=utf-8')


def ads_txt(request):
    """IAB ads.txt para Google AdSense (requerido en el dominio raíz)."""
    client = (getattr(settings, 'ADSENSE_CLIENT', '') or '').strip()
    # ca-pub-123... → pub-123...
    pub_id = client[3:] if client.startswith('ca-') else client
    if not pub_id:
        return HttpResponse(
            '# AdSense aún no configurado (ADSENSE_CLIENT)\n',
            content_type='text/plain; charset=utf-8',
        )
    body = f'google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n'
    return HttpResponse(body, content_type='text/plain; charset=utf-8')
