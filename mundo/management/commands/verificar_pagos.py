"""
Diagnóstico de lo imprescindible para que los pagos funcionen en producción.

Uso:
    python manage.py verificar_pagos
    python manage.py verificar_pagos --remoto   # también consulta APIs LS/MP

No imprime secretos completos.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand


def _mask(value: str, keep: int = 6) -> str:
    if not value:
        return '(vacío)'
    if len(value) <= keep:
        return '***'
    return f'{value[:keep]}… (len={len(value)})'


def _ok(msg: str) -> str:
    return f'  OK   {msg}'


def _fail(msg: str) -> str:
    return f'  FAIL {msg}'


def _warn(msg: str) -> str:
    return f'  WARN {msg}'


class Command(BaseCommand):
    help = 'Verifica variables y configuración imprescindible de pagos (USD / LS / MP).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--remoto',
            action='store_true',
            help='Consulta API Lemon Squeezy (y formato token MP) con las credenciales locales.',
        )

    def handle(self, *args, **options):
        remoto = options['remoto']
        fallos = 0
        avisos = 0

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 1. Variables de entorno ===\n'))

        site = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
        debug = bool(settings.DEBUG)
        ls_key = (getattr(settings, 'LEMONSQUEEZY_API_KEY', '') or '').strip()
        ls_store = (getattr(settings, 'LEMONSQUEEZY_STORE_ID', '') or '').strip()
        ls_slug = (getattr(settings, 'LEMONSQUEEZY_STORE_SLUG', '') or '').strip()
        ls_secret = (getattr(settings, 'LEMONSQUEEZY_WEBHOOK_SECRET', '') or '').strip()
        mp_token = (getattr(settings, 'MP_ACCESS_TOKEN', '') or '').strip()
        email_user = (getattr(settings, 'EMAIL_HOST_USER', '') or '').strip()
        email_pass = (getattr(settings, 'EMAIL_HOST_PASSWORD', '') or '').strip()

        # SITE_URL
        if not site or 'tudominio' in site or '127.0.0.1' in site or 'localhost' in site:
            fallos += 1
            self.stdout.write(self.style.ERROR(_fail(
                f'SITE_URL={site or "(vacio)"} - debe ser la URL HTTPS publica de Render'
            )))
        elif not site.startswith('https://'):
            fallos += 1
            self.stdout.write(self.style.ERROR(_fail(f'SITE_URL debe ser https:// -> {site}')))
        else:
            self.stdout.write(self.style.SUCCESS(_ok(f'SITE_URL={site}')))

        # DEBUG
        if debug:
            avisos += 1
            self.stdout.write(self.style.WARNING(_warn('DEBUG=True - en produccion deberia ser False')))
        else:
            self.stdout.write(self.style.SUCCESS(_ok('DEBUG=False')))

        # Lemon Squeezy
        for label, val, required in [
            ('LEMONSQUEEZY_API_KEY', ls_key, True),
            ('LEMONSQUEEZY_STORE_ID', ls_store, True),
            ('LEMONSQUEEZY_WEBHOOK_SECRET', ls_secret, True),
            ('LEMONSQUEEZY_STORE_SLUG', ls_slug, False),
        ]:
            if val:
                self.stdout.write(self.style.SUCCESS(_ok(f'{label}={_mask(val)}')))
            elif required:
                fallos += 1
                self.stdout.write(self.style.ERROR(_fail(f'{label} no configurada')))
            else:
                avisos += 1
                self.stdout.write(self.style.WARNING(_warn(f'{label} vacía (opcional)')))

        # Mercado Pago
        if not mp_token:
            fallos += 1
            self.stdout.write(self.style.ERROR(_fail('MP_ACCESS_TOKEN no configurado')))
        else:
            self.stdout.write(self.style.SUCCESS(_ok(f'MP_ACCESS_TOKEN={_mask(mp_token)}')))
            if mp_token.startswith('TEST-'):
                avisos += 1
                self.stdout.write(self.style.WARNING(_warn(
                    'MP_ACCESS_TOKEN es TEST-… (sandbox). Para cobros reales usá APP_USR-…'
                )))
            elif not mp_token.startswith('APP_USR-'):
                avisos += 1
                self.stdout.write(self.style.WARNING(_warn(
                    'MP_ACCESS_TOKEN no empieza con APP_USR- (¿token de producción?)'
                )))

        # Email (transferencias)
        if email_user and email_pass:
            self.stdout.write(self.style.SUCCESS(_ok(f'EMAIL_HOST_USER={email_user}')))
        else:
            avisos += 1
            self.stdout.write(self.style.WARNING(_warn(
                'EMAIL_* incompleto - las transferencias no avisaran al admin'
            )))

        # Paquetes / variants
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 2. Planes y variant IDs (código) ===\n'))
        from mundo.views import _PAQUETES_MAP, PLANES_TOKENS
        n = len(_PAQUETES_MAP)
        sin_variant = [k for k, p in _PAQUETES_MAP.items() if not p.get('ls_variant_id')]
        self.stdout.write(self.style.SUCCESS(_ok(f'{n} paquetes en _PAQUETES_MAP')))
        if sin_variant:
            fallos += 1
            self.stdout.write(self.style.ERROR(_fail(f'Sin ls_variant_id: {", ".join(sin_variant)}')))
        else:
            self.stdout.write(self.style.SUCCESS(_ok('Todos los paquetes tienen ls_variant_id')))

        precios = sorted({p['precio'] for p in _PAQUETES_MAP.values()})
        self.stdout.write(_ok(f'Precios USD en código: {", ".join(f"${x:g}" for x in precios)}'))

        # Endpoints
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 3. Endpoints que debés configurar afuera ===\n'))
        if site and site.startswith('https://'):
            self.stdout.write(f'  LS webhook URL : {site}/ls-webhook/')
            self.stdout.write(f'  Evento LS      : order_created')
            self.stdout.write(f'  MP notifica a  : {site}/mp-webhook/  (ya va en la preferencia)')
            self.stdout.write(f'  LS retorno     : {site}/ls-retorno/')
            self.stdout.write(f'  MP tokens OK   : {site}/tokens-retorno/')
        else:
            self.stdout.write(self.style.WARNING(_warn(
                'Definí SITE_URL https primero; después configurá estos webhooks'
            )))

        self.stdout.write('')
        self.stdout.write('  Lemon Squeezy > Settings > Webhooks > Add webhook')
        self.stdout.write('  - Signing secret = LEMONSQUEEZY_WEBHOOK_SECRET')
        self.stdout.write('  - Cada product/variant debe estar en moneda USD')
        self.stdout.write('  - Los variant IDs del dashboard deben coincidir con PLANES_TOKENS')

        if remoto:
            self.stdout.write(self.style.MIGRATE_HEADING('\n=== 4. Consulta remota Lemon Squeezy ===\n'))
            if not ls_key:
                fallos += 1
                self.stdout.write(self.style.ERROR(_fail('Sin API key: no se puede consultar LS')))
            else:
                fallos += self._check_ls_variants(ls_key, ls_store, _PAQUETES_MAP)

        # Resumen + checklist humano
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Checklist manual (imprescindible) ===\n'))
        checklist = [
            '[ ] Render: SITE_URL, LEMONSQUEEZY_*, MP_ACCESS_TOKEN (APP_USR), EMAIL_*',
            '[ ] Deploy del branch con los fixes de pagos',
            '[ ] LS webhook -> {SITE_URL}/ls-webhook/  evento order_created',
            '[ ] LS products/variants en USD y IDs = codigo',
            '[ ] Smoke test LS: pagar 1 variant -> HistorialTokens BONO + tokens activos',
            '[ ] Smoke test MP: pagar tokens -> mismo resultado, sin doble activacion',
            '[ ] Smoke test transferencia: mail admin + activar manual',
        ]
        for line in checklist:
            self.stdout.write(f'  {line}')

        self.stdout.write('')
        if fallos:
            self.stdout.write(self.style.ERROR(
                f'Resultado: {fallos} fallo(s), {avisos} aviso(s). Completá lo FAIL antes del smoke test.'
            ))
        elif avisos:
            self.stdout.write(self.style.WARNING(
                f'Resultado: config mínima OK, {avisos} aviso(s). Seguís con webhooks + smoke test.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'Resultado: variables locales OK. Falta confirmar webhooks en LS/MP y hacer smoke test.'
            ))

        # Exit code útil en CI
        if fallos:
            raise SystemExit(1)

    def _check_ls_variants(self, api_key: str, store_id: str, paquetes: dict) -> int:
        """Devuelve cantidad de fallos detectados vía API."""
        fallos = 0
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/vnd.api+json',
        }

        # Store
        if store_id:
            try:
                store = self._ls_get(f'https://api.lemonsqueezy.com/v1/stores/{store_id}', headers)
                attrs = store.get('data', {}).get('attributes', {})
                currency = attrs.get('currency', '')
                name = attrs.get('name', '')
                self.stdout.write(self.style.SUCCESS(_ok(
                    f'Store {store_id} "{name}" currency={currency or "?"}'
                )))
                if currency and currency.upper() != 'USD':
                    fallos += 1
                    self.stdout.write(self.style.ERROR(_fail(
                        f'La tienda no está en USD (currency={currency}). Cambiála a USD en LS.'
                    )))
            except Exception as e:
                fallos += 1
                self.stdout.write(self.style.ERROR(_fail(f'No se pudo leer store {store_id}: {e}')))
        else:
            avisos_msg = 'Sin STORE_ID: se listarán variants igual si la API lo permite'
            self.stdout.write(self.style.WARNING(_warn(avisos_msg)))

        # Variants
        try:
            body = self._ls_get(
                'https://api.lemonsqueezy.com/v1/variants?page[size]=100',
                headers,
            )
            items = body.get('data', []) or []
            by_id = {str(v['id']): v for v in items}
            self.stdout.write(_ok(f'API devolvió {len(items)} variants'))

            for pac_id, pac in sorted(paquetes.items()):
                vid = str(pac.get('ls_variant_id') or '')
                if not vid:
                    continue
                v = by_id.get(vid)
                if not v:
                    fallos += 1
                    self.stdout.write(self.style.ERROR(_fail(
                        f'{pac_id}: variant {vid} NO encontrado en la cuenta LS'
                    )))
                    continue
                attrs = v.get('attributes', {})
                status = attrs.get('status', '')
                # price en centavos
                price_cents = attrs.get('price')
                price_usd = None
                if isinstance(price_cents, int):
                    price_usd = price_cents / 100.0
                expected = float(pac['precio'])
                line = f'{pac_id}: variant={vid} status={status}'
                if price_usd is not None:
                    line += f' price=${price_usd:g}'
                    if abs(price_usd - expected) > 0.01:
                        fallos += 1
                        self.stdout.write(self.style.ERROR(_fail(
                            f'{line} - codigo espera ${expected:g} USD'
                        )))
                        continue
                if status and status != 'published':
                    fallos += 1
                    self.stdout.write(self.style.ERROR(_fail(f'{line} - debe estar published')))
                else:
                    self.stdout.write(self.style.SUCCESS(_ok(line)))
        except Exception as e:
            fallos += 1
            self.stdout.write(self.style.ERROR(_fail(f'Error listando variants: {e}')))

        return fallos

    def _ls_get(self, url: str, headers: dict) -> dict:
        req = urllib.request.Request(url, headers=headers, method='GET')
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', errors='replace')
            raise RuntimeError(f'HTTP {e.code}: {detail[:300]}') from e
