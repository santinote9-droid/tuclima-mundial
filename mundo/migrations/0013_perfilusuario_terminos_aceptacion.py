from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mundo', '0012_modal_interactivo'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuario',
            name='terminos_aceptados',
            field=models.BooleanField(
                default=False,
                verbose_name='Términos y Privacidad aceptados',
            ),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='terminos_aceptados_en',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Fecha de aceptación legal',
            ),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='terminos_version',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Ej: 2026-08-21 — debe coincidir con LEGAL_TERMS_VERSION',
                max_length=32,
                verbose_name='Versión de documentos legales aceptada',
            ),
        ),
    ]
