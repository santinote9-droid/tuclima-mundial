"""
Management command: enviar_recordatorios_renovacion

Busca usuarios con renovacion_automatica=True cuya suscripción vence
en los próximos 5 días y les envía un email con el link de renovación.

Uso:
    python manage.py enviar_recordatorios_renovacion

Programar (cron en Linux/Render):
    0 9 * * * /ruta/venv/bin/python /ruta/manage.py enviar_recordatorios_renovacion

Programar (Windows Task Scheduler — verificacion_diaria.bat):
    python manage.py enviar_recordatorios_renovacion
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.urls import reverse
from datetime import timedelta
import os

from mundo.models import PerfilUsuario


class Command(BaseCommand):
    help = 'Envía recordatorios de renovación a usuarios cuya suscripción vence en 5 días.'

    def handle(self, *args, **options):
        ahora = timezone.now()
        limite_inf = ahora + timedelta(days=4)   # más de 4 días → aún no
        limite_sup = ahora + timedelta(days=6)   # más de 6 días → todavía lejos

        perfiles = PerfilUsuario.objects.filter(
            renovacion_automatica=True,
            fecha_vencimiento__gte=limite_inf,
            fecha_vencimiento__lt=limite_sup,
        ).select_related('user')

        site_url = os.getenv('SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
        enviados = 0
        errores = 0

        for perfil in perfiles:
            usuario = perfil.user
            if not usuario.email:
                self.stdout.write(self.style.WARNING(
                    f'  [SKIP] {usuario.username} no tiene email.'
                ))
                continue

            plan = perfil.plan_tipo or 'mensual'
            plan_label = 'Anual ($200 USD)' if plan == 'anual' else 'Mensual ($20 USD)'
            venc_str = perfil.fecha_vencimiento.strftime('%d/%m/%Y')
            link_renovacion = f"{site_url}/metodos-pago/?plan={plan}"

            asunto = '🔔 Tu suscripción Weather PRO vence pronto'
            cuerpo_html = f"""
<html>
<body style="font-family: 'Segoe UI', sans-serif; background:#0f172a; color:#e2e8f0; padding:30px;">
    <div style="max-width:520px; margin:0 auto; background:#1e293b; border-radius:16px; padding:32px; border:1px solid #334155;">
        <h2 style="color:#fff; margin-bottom:8px;">Tu suscripción vence el {venc_str}</h2>
        <p style="color:#94a3b8; margin-bottom:24px;">Hola <strong style="color:#fff;">{usuario.username}</strong>,
        tu plan <strong style="color:#60a5fa;">{plan_label}</strong> vence en 5 días.</p>
        <a href="{link_renovacion}"
           style="display:inline-block; background:linear-gradient(135deg,#3b82f6,#6366f1);
                  color:#fff; padding:14px 28px; border-radius:10px; text-decoration:none;
                  font-weight:700; font-size:1rem;">
            ✅ Renovar ahora
        </a>
        <p style="color:#64748b; font-size:0.8rem; margin-top:24px;">
            No querés más estos recordatorios?
            <a href="{site_url}/mi-cuenta/" style="color:#3b82f6;">Desactivarlos desde Mi Cuenta</a>.
        </p>
    </div>
</body>
</html>
"""
            try:
                send_mail(
                    subject=asunto,
                    message=f'Tu suscripción vence el {venc_str}. Renovar en: {link_renovacion}',
                    from_email=None,   # usa DEFAULT_FROM_EMAIL de settings
                    recipient_list=[usuario.email],
                    html_message=cuerpo_html,
                    fail_silently=False,
                )
                enviados += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK] Recordatorio enviado a {usuario.username} ({usuario.email})'
                ))
            except Exception as exc:
                errores += 1
                self.stdout.write(self.style.ERROR(
                    f'  [ERROR] No se pudo enviar a {usuario.username}: {exc}'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {enviados} recordatorio(s) enviado(s), {errores} error(es).'
        ))
