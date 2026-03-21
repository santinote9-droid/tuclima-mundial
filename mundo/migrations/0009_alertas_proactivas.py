from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mundo', '0008_tokens_diarios'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuario',
            name='alertas_activas',
            field=models.BooleanField(default=False, verbose_name='Alertas diarias activas'),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='alertas_sectores',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Sectores de alerta'),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='hora_alerta',
            field=models.IntegerField(default=7, verbose_name='Hora de envío (Argentina)'),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='ubicacion_nombre',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Ubicación para alertas'),
        ),
    ]
