"""Baja la grilla del modelo (DWD ICON) para la región del lab de mapas.

Tarda del orden de minutos. DWD publica una corrida nueva cada 6 horas;
el lab también dispara la bajada solo si la que hay en disco se quedó vieja.

    python manage.py sincronizar_grilla
"""
from django.core.management.base import BaseCommand

from mundo import grilla_modelo


class Command(BaseCommand):
    help = 'Sincroniza la grilla del modelo desde el open data de Open-Meteo'

    def add_arguments(self, parser):
        parser.add_argument('--forzar', action='store_true',
                            help='rebaja la corrida aunque ya esté al día')
        parser.add_argument(
            '--horas', type=int, default=0,
            help='horas a guardar (0 = todas las que publique el modelo)')

    def handle(self, *args, **opciones):
        res = grilla_modelo.sincronizar(
            log=lambda msg: self.stdout.write(msg),
            horas=opciones['horas'],
            forzar=opciones['forzar'],
        )
        estado = res.get('estado')
        if estado == 'ok':
            self.stdout.write(self.style.SUCCESS(
                f'Corrida {res["reference_time"]} lista en {res["segundos"]}s'))
        elif estado == 'al_dia':
            self.stdout.write(f'Sin cambios: {res["reference_time"]}')
        else:
            self.stdout.write(self.style.WARNING(f'Estado: {estado}'))
