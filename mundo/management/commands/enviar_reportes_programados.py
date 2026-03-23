"""
Management command: enviar_reportes_programados

Busca los reportes programados activos que corresponde enviar según
su frecuencia y hora, llama al webhook de n8n para que genere y envíe
el análisis IA por email.

Uso:
    python manage.py enviar_reportes_programados

Programar (cron — cada hora):
    0 * * * * /ruta/venv/bin/python /ruta/manage.py enviar_reportes_programados
"""

import requests
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from mundo.models import ReporteProgramado


class Command(BaseCommand):
    help = 'Dispara los reportes programados activos que corresponde enviar en este momento.'

    N8N_WEBHOOK_URL = getattr(settings, 'N8N_REPORTE_WEBHOOK_URL', '')

    def handle(self, *args, **options):
        ahora = timezone.now()
        hora_actual = ahora.hour
        dia_semana = ahora.weekday()   # 0=lunes … 6=domingo
        dia_mes = ahora.day

        reportes_a_enviar = []

        for rep in (ReporteProgramado.objects
                    .filter(activo=True)
                    .select_related('usuario')):

            if rep.hora_envio != hora_actual:
                continue

            # Verificar frecuencia
            if rep.frecuencia == 'diario':
                debe_enviar = True
            elif rep.frecuencia == 'semanal':
                debe_enviar = (dia_semana == 0)  # Lunes
            elif rep.frecuencia == 'mensual':
                debe_enviar = (dia_mes == 1)
            else:
                debe_enviar = False

            if not debe_enviar:
                continue

            # Evitar doble envío dentro de la misma hora
            if rep.ultimo_envio and rep.ultimo_envio >= ahora - timedelta(hours=1):
                continue

            reportes_a_enviar.append(rep)

        self.stdout.write(f'Reportes a enviar esta hora: {len(reportes_a_enviar)}')

        enviados = 0
        errores = 0

        for rep in reportes_a_enviar:
            email = rep.email_efectivo()
            nombre = rep.usuario.first_name or rep.usuario.username

            payload = {
                'email': email,
                'nombre': nombre,
                'sector': rep.sector,
                'frecuencia': rep.frecuencia,
                'reporte_id': rep.id,
            }

            n8n_url = self.N8N_WEBHOOK_URL
            if not n8n_url:
                self.stdout.write(self.style.WARNING(
                    'N8N_REPORTE_WEBHOOK_URL no configurado — reporte no enviado.'
                ))
                continue

            try:
                resp = requests.post(n8n_url, json=payload, timeout=30)
                resp.raise_for_status()
                rep.ultimo_envio = ahora
                rep.save(update_fields=['ultimo_envio'])
                enviados += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ {rep.usuario.username} — {rep.sector} — {email}'
                ))
            except requests.RequestException as e:
                errores += 1
                self.stdout.write(self.style.ERROR(
                    f'  ✗ Error en reporte {rep.id} para {email}: {e}'
                ))

        self.stdout.write(
            self.style.SUCCESS(f'Listo. Enviados: {enviados} | Errores: {errores}')
        )
