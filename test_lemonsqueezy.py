#!/usr/bin/env python3
"""
Test de integración Lemon Squeezy — sin pagos reales.
Cubre:
  1. Mapeo de variant IDs en PLANES_TOKENS
  2. Verificación de firma HMAC del webhook
  3. Simulación completa de webhook order_created → plan activado
  4. Idempotencia (mismo webhook dos veces no recarga dos veces)
  5. Webhook con firma inválida → 401
  6. Redirect de ls_checkout hacia URL correcta

Uso:
    python manage.py test test_lemonsqueezy   (si lo movés a mundo/tests/)
    python test_lemonsqueezy.py               (standalone con Django configurado)
"""

import os
import sys
import json
import hmac
import hashlib

# --- Bootstrap Django ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nucleo.settings')
import django
django.setup()

from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User
from django.urls import reverse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = 'test-secret-lemonsqueezy'

# Los 12 variant IDs esperados
EXPECTED_VARIANTS = {
    'starter_1m': '1404219',
    'starter_3m': '1404160',
    'starter_6m': '1404236',
    'plus_1m':    '1404246',
    'plus_3m':    '1404247',
    'plus_6m':    '1404252',
    'pro_ia_1m':  '1404261',
    'pro_ia_3m':  '1404272',
    'pro_ia_6m':  '1404275',
    'power_1m':   '1404277',
    'power_3m':   '1404280',
    'power_6m':   '1404282',
}


def make_ls_payload(user_id: int, paquete_id: str) -> bytes:
    """Construye un payload de webhook order_created como lo envía Lemon Squeezy."""
    payload = {
        "meta": {
            "event_name": "order_created",
            "custom_data": {
                "user_id": str(user_id),
                "paquete_id": paquete_id,
            }
        },
        "data": {
            "attributes": {
                "status": "paid"
            }
        }
    }
    return json.dumps(payload).encode('utf-8')


def sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVariantMapping(TestCase):
    """Verifica que todos los variant IDs estén cargados en _PAQUETES_MAP."""

    def test_todos_los_variant_ids_presentes(self):
        from mundo.views import _PAQUETES_MAP
        errores = []
        for paquete_id, variant_id_esperado in EXPECTED_VARIANTS.items():
            paquete = _PAQUETES_MAP.get(paquete_id)
            if paquete is None:
                errores.append(f'  FALTA paquete "{paquete_id}" en _PAQUETES_MAP')
                continue
            actual = paquete.get('ls_variant_id', '')
            if actual != variant_id_esperado:
                errores.append(
                    f'  "{paquete_id}": esperado {variant_id_esperado}, obtenido "{actual}"'
                )
        if errores:
            self.fail('Variant IDs incorrectos:\n' + '\n'.join(errores))

    def test_todos_los_paquetes_tienen_precio(self):
        from mundo.views import _PAQUETES_MAP
        for key, p in _PAQUETES_MAP.items():
            self.assertGreater(p['precio'], 0, f'{key} tiene precio 0')

    def test_todos_los_paquetes_tienen_tokens_dia(self):
        from mundo.views import _PAQUETES_MAP
        for key, p in _PAQUETES_MAP.items():
            self.assertGreater(p['tokens_dia'], 0, f'{key} tiene tokens_dia 0')


class TestLsWebhookFirma(TestCase):
    """Verifica la validación de firma HMAC del webhook."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_ls_firma', password='pass123'
        )
        # Crear perfil si no existe
        from mundo.models import PerfilUsuario
        PerfilUsuario.objects.get_or_create(user=self.user)

    def _post_webhook(self, body: bytes, secret: str, sig_override: str = None):
        sig = sig_override if sig_override is not None else sign_payload(body, secret)
        with self.settings(LEMONSQUEEZY_WEBHOOK_SECRET=secret):
            return self.client.post(
                '/ls-webhook/',
                data=body,
                content_type='application/json',
                HTTP_X_SIGNATURE=sig,
            )

    def test_firma_valida_retorna_200(self):
        body = make_ls_payload(self.user.id, 'starter_1m')
        resp = self._post_webhook(body, WEBHOOK_SECRET)
        self.assertEqual(resp.status_code, 200)

    def test_firma_invalida_retorna_401(self):
        body = make_ls_payload(self.user.id, 'starter_1m')
        resp = self._post_webhook(body, WEBHOOK_SECRET, sig_override='firma-falsa')
        self.assertEqual(resp.status_code, 401)

    def test_sin_secret_configurado_pasa_igual(self):
        """Si LEMONSQUEEZY_WEBHOOK_SECRET está vacío, el webhook no bloquea (fail-open)."""
        body = make_ls_payload(self.user.id, 'starter_1m')
        with self.settings(LEMONSQUEEZY_WEBHOOK_SECRET=''):
            resp = self.client.post(
                '/ls-webhook/',
                data=body,
                content_type='application/json',
                HTTP_X_SIGNATURE='cualquier-cosa',
            )
        self.assertEqual(resp.status_code, 200)


class TestLsWebhookActivacion(TestCase):
    """Simula un webhook completo y verifica que el plan se active."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_ls_activ', password='pass123'
        )
        from mundo.models import PerfilUsuario
        PerfilUsuario.objects.get_or_create(user=self.user)

    def _post(self, paquete_id: str):
        body = make_ls_payload(self.user.id, paquete_id)
        sig  = sign_payload(body, WEBHOOK_SECRET)
        with self.settings(LEMONSQUEEZY_WEBHOOK_SECRET=WEBHOOK_SECRET):
            return self.client.post(
                '/ls-webhook/',
                data=body,
                content_type='application/json',
                HTTP_X_SIGNATURE=sig,
            )

    def test_starter_1m_activa_tokens(self):
        resp = self._post('starter_1m')
        self.assertEqual(resp.status_code, 200)
        self.user.perfil.refresh_from_db()
        self.assertEqual(self.user.perfil.tokens_diarios_limite, 27_000)
        self.assertGreater(self.user.perfil.tokens_disponibles, 0)

    def test_plus_3m_activa_tokens(self):
        resp = self._post('plus_3m')
        self.assertEqual(resp.status_code, 200)
        self.user.perfil.refresh_from_db()
        self.assertEqual(self.user.perfil.tokens_diarios_limite, 51_000)

    def test_power_6m_activa_tokens(self):
        resp = self._post('power_6m')
        self.assertEqual(resp.status_code, 200)
        self.user.perfil.refresh_from_db()
        self.assertEqual(self.user.perfil.tokens_diarios_limite, 135_000)

    def test_plan_extiende_fecha_vencimiento(self):
        from django.utils import timezone
        resp = self._post('starter_1m')
        self.assertEqual(resp.status_code, 200)
        self.user.perfil.refresh_from_db()
        self.assertIsNotNone(self.user.perfil.fecha_vencimiento_tokens)
        self.assertGreater(self.user.perfil.fecha_vencimiento_tokens, timezone.now())

    def test_idempotencia_no_recarga_dos_veces(self):
        """Enviar el mismo webhook dos veces no debe duplicar la recarga."""
        self._post('starter_1m')
        self.user.perfil.refresh_from_db()
        tokens_tras_primera = self.user.perfil.tokens_disponibles

        self._post('starter_1m')
        self.user.perfil.refresh_from_db()
        tokens_tras_segunda = self.user.perfil.tokens_disponibles

        self.assertEqual(
            tokens_tras_primera,
            tokens_tras_segunda,
            'El webhook duplicado cargó tokens dos veces'
        )

    def test_paquete_inexistente_retorna_200_sin_crash(self):
        body = make_ls_payload(self.user.id, 'plan_que_no_existe')
        sig  = sign_payload(body, WEBHOOK_SECRET)
        with self.settings(LEMONSQUEEZY_WEBHOOK_SECRET=WEBHOOK_SECRET):
            resp = self.client.post(
                '/ls-webhook/',
                data=body,
                content_type='application/json',
                HTTP_X_SIGNATURE=sig,
            )
        self.assertEqual(resp.status_code, 200)

    def test_usuario_inexistente_retorna_200_sin_crash(self):
        body = make_ls_payload(user_id=999999, paquete_id='starter_1m')
        sig  = sign_payload(body, WEBHOOK_SECRET)
        with self.settings(LEMONSQUEEZY_WEBHOOK_SECRET=WEBHOOK_SECRET):
            resp = self.client.post(
                '/ls-webhook/',
                data=body,
                content_type='application/json',
                HTTP_X_SIGNATURE=sig,
            )
        self.assertEqual(resp.status_code, 200)


class TestLsCheckoutRedirect(TestCase):
    """Verifica que ls_checkout redirija a la URL correcta de Lemon Squeezy."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_ls_checkout', password='pass123'
        )
        from mundo.models import PerfilUsuario
        PerfilUsuario.objects.get_or_create(user=self.user)
        self.client.login(username='test_ls_checkout', password='pass123')

    def test_checkout_starter_1m_redirige_a_ls(self):
        with self.settings(
            LEMONSQUEEZY_STORE_SLUG='tuclima',
            SITE_URL='https://tuclima.com',
        ):
            resp = self.client.get('/ls-checkout/?paquete=starter_1m')
        self.assertEqual(resp.status_code, 302)
        location = resp['Location']
        self.assertIn('lemonsqueezy.com', location)
        self.assertIn('1404219', location)          # variant ID de starter_1m
        self.assertIn('user_id', location)
        self.assertIn('paquete_id', location)

    def test_checkout_sin_paquete_redirige_a_pricing(self):
        resp = self.client.get('/ls-checkout/?paquete=inexistente')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('recargar-tokens', resp['Location'])

    def test_checkout_requiere_login(self):
        self.client.logout()
        resp = self.client.get('/ls-checkout/?paquete=starter_1m')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp['Location'])


# ---------------------------------------------------------------------------
# Runner standalone
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import unittest

    # Usar la DB de tests de Django
    from django.test.utils import get_runner
    from django.conf import settings as django_settings

    TestRunner = get_runner(django_settings)
    test_runner = TestRunner(verbosity=2, keepdb=False)

    suite = unittest.TestLoader().loadTestsFromModule(
        __import__(__name__)
    )
    result = test_runner.run_suite(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
