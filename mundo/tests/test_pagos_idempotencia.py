"""
Tests de idempotencia de activación de planes (webhook + retorno).

Cubre:
  - Helper _activar_plan_tokens_si_nuevo (doble llamada)
  - Webhook Lemon Squeezy duplicado
  - Webhook MP + retorno tokens (mismo día, mismo paquete)
"""

from __future__ import annotations

import json
import hmac
import hashlib
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from mundo.models import HistorialTokens, PerfilUsuario
from mundo.views import (
    _PAQUETES_MAP,
    _activar_plan_tokens_si_nuevo,
    _descripcion_plan_tokens,
    _plan_tokens_ya_activado,
)


WEBHOOK_SECRET = 'test-secret-idempotencia'


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()


def _ls_payload(user_id: int, paquete_id: str) -> bytes:
    return json.dumps({
        'meta': {
            'event_name': 'order_created',
            'custom_data': {
                'user_id': str(user_id),
                'paquete_id': paquete_id,
            },
        },
        'data': {'attributes': {'status': 'paid'}},
    }).encode('utf-8')


class TestHelperIdempotencia(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('idem_helper', password='x')
        PerfilUsuario.objects.get_or_create(user=self.user)
        self.paquete = _PAQUETES_MAP['starter_1m']

    def test_activar_dos_veces_no_duplica_bono(self):
        self.assertTrue(_activar_plan_tokens_si_nuevo(self.user, self.paquete))
        self.assertFalse(_activar_plan_tokens_si_nuevo(self.user, self.paquete))

        bonos = HistorialTokens.objects.filter(
            usuario=self.user, tipo='BONO', fecha__date=timezone.now().date()
        )
        self.assertEqual(
            bonos.filter(descripcion__icontains='[starter_1m]').count(),
            1,
        )
        self.assertTrue(_plan_tokens_ya_activado(self.user, self.paquete))

    def test_descripcion_incluye_paquete_id(self):
        desc = _descripcion_plan_tokens(self.paquete)
        self.assertIn('[starter_1m]', desc)
        self.assertIn('Starter', desc)


@override_settings(LEMONSQUEEZY_WEBHOOK_SECRET=WEBHOOK_SECRET, DEBUG=False)
class TestLsWebhookIdempotencia(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('idem_ls', password='x')
        PerfilUsuario.objects.get_or_create(user=self.user)
        self.client = Client()

    def _post(self, paquete_id='starter_1m'):
        body = _ls_payload(self.user.id, paquete_id)
        return self.client.post(
            '/ls-webhook/',
            data=body,
            content_type='application/json',
            HTTP_X_SIGNATURE=_sign(body),
        )

    def test_doble_webhook_una_sola_activacion(self):
        r1 = self._post()
        r2 = self._post()
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

        self.user.perfil.refresh_from_db()
        self.assertEqual(self.user.perfil.tokens_diarios_limite, 42_000)
        self.assertEqual(
            HistorialTokens.objects.filter(
                usuario=self.user,
                tipo='BONO',
                descripcion__icontains='[starter_1m]',
                fecha__date=timezone.now().date(),
            ).count(),
            1,
        )

    def test_sin_secret_en_produccion_503(self):
        body = _ls_payload(self.user.id, 'starter_1m')
        with self.settings(LEMONSQUEEZY_WEBHOOK_SECRET='', DEBUG=False):
            resp = self.client.post(
                '/ls-webhook/',
                data=body,
                content_type='application/json',
                HTTP_X_SIGNATURE='x',
            )
        self.assertEqual(resp.status_code, 503)


@override_settings(MP_ACCESS_TOKEN='TEST-fake', SITE_URL='https://example.com', DEBUG=True)
class TestMpWebhookYRetornoIdempotencia(TestCase):
    """Webhook MP + retorno no deben activar dos veces el mismo plan el mismo día."""

    def setUp(self):
        self.user = User.objects.create_user('idem_mp', password='x')
        PerfilUsuario.objects.get_or_create(user=self.user)
        self.client = Client()
        self.client.login(username='idem_mp', password='x')
        self.paquete_id = 'plus_1m'
        self.paquete = _PAQUETES_MAP[self.paquete_id]

    def _mock_payment(self, payment_id=555):
        payment = {
            'status': 'approved',
            'external_reference': f'{self.user.id}_tk_{self.paquete_id}',
            'id': payment_id,
        }
        sdk = MagicMock()
        sdk.payment().get.return_value = {'status': 200, 'response': payment}
        return sdk

    def test_webhook_luego_retorno_una_sola_activacion(self):
        with patch('mundo.views.mercadopago.SDK', return_value=self._mock_payment(901)):
            body = json.dumps({'type': 'payment', 'data': {'id': 901}}).encode('utf-8')
            rw = self.client.post(
                '/mp-webhook/',
                data=body,
                content_type='application/json',
            )
            self.assertEqual(rw.status_code, 200)

            rr = self.client.get(
                f'/tokens-retorno/?paquete={self.paquete_id}&status=approved&payment_id=901'
            )
            self.assertEqual(rr.status_code, 200)

        self.user.perfil.refresh_from_db()
        self.assertEqual(self.user.perfil.tokens_diarios_limite, 75_000)
        self.assertEqual(
            HistorialTokens.objects.filter(
                usuario=self.user,
                tipo='BONO',
                descripcion__icontains=f'[{self.paquete_id}]',
                fecha__date=timezone.now().date(),
            ).count(),
            1,
        )

    def test_retorno_luego_webhook_una_sola_activacion(self):
        with patch('mundo.views.mercadopago.SDK', return_value=self._mock_payment(902)):
            rr = self.client.get(
                f'/tokens-retorno/?paquete={self.paquete_id}&status=approved&payment_id=902'
            )
            self.assertEqual(rr.status_code, 200)

            body = json.dumps({'type': 'payment', 'data': {'id': 902}}).encode('utf-8')
            rw = self.client.post(
                '/mp-webhook/',
                data=body,
                content_type='application/json',
            )
            self.assertEqual(rw.status_code, 200)

        self.assertEqual(
            HistorialTokens.objects.filter(
                usuario=self.user,
                tipo='BONO',
                descripcion__icontains=f'[{self.paquete_id}]',
                fecha__date=timezone.now().date(),
            ).count(),
            1,
        )
