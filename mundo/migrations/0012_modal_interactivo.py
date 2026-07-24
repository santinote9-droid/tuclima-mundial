# Generated manually for modales interactivos (config / alertas / notas)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mundo', '0011_ubicaciones_reportes_apikey'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionModal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sector', models.CharField(help_text='agro/naval/aereo/energia', max_length=10)),
                ('modal_id', models.CharField(help_text='Ej: modGDD, modVPD, modEol...', max_length=40)),
                ('lat', models.FloatField(blank=True, null=True)),
                ('lon', models.FloatField(blank=True, null=True)),
                ('datos', models.JSONField(blank=True, default=dict)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='config_modal', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Configuración de modal',
                'verbose_name_plural': 'Configuraciones de modales',
                'unique_together': {('usuario', 'sector', 'modal_id', 'lat', 'lon')},
            },
        ),
        migrations.CreateModel(
            name='AlertaModal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sector', models.CharField(max_length=10)),
                ('modal_id', models.CharField(max_length=40)),
                ('lat', models.FloatField(blank=True, null=True)),
                ('lon', models.FloatField(blank=True, null=True)),
                ('variable', models.CharField(help_text="Clave de la variable a evaluar, ej: 'vpd'", max_length=40)),
                ('operador', models.CharField(choices=[('gt', 'Mayor que'), ('lt', 'Menor que')], default='gt', max_length=2)),
                ('umbral', models.FloatField()),
                ('activa', models.BooleanField(default=True)),
                ('creada', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alertas_modal', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Alerta de modal',
                'verbose_name_plural': 'Alertas de modales',
                'ordering': ['-creada'],
            },
        ),
        migrations.CreateModel(
            name='NotaModal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sector', models.CharField(max_length=10)),
                ('modal_id', models.CharField(max_length=40)),
                ('lat', models.FloatField(blank=True, null=True)),
                ('lon', models.FloatField(blank=True, null=True)),
                ('texto', models.TextField(max_length=500)),
                ('creada', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notas_modal', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Nota de modal',
                'verbose_name_plural': 'Notas de modales',
                'ordering': ['-creada'],
            },
        ),
    ]
