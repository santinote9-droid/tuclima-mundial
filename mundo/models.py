from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import json
import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno explícitamente
load_dotenv()

logger = logging.getLogger(__name__)

class PerfilUsuario(models.Model):
    PLAN_CHOICES = [
        ('mensual', 'Mensual ($20/mes)'),
        ('anual', 'Anual ($200/año)'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)
    plan_tipo = models.CharField(max_length=10, choices=PLAN_CHOICES, default='mensual', blank=True)
    renovacion_automatica = models.BooleanField(
        default=True,
        verbose_name='Renovación automática',
        help_text='Recibir recordatorio por email 5 días antes del vencimiento'
    )

    # --- Sistema de Tokens IA ---
    tokens_disponibles = models.IntegerField(
        default=0,
        verbose_name='Tokens disponibles hoy',
        help_text='Créditos de IA disponibles para hoy'
    )
    tokens_usados_total = models.IntegerField(
        default=0,
        verbose_name='Tokens usados (total histórico)'
    )
    tokens_diarios_limite = models.IntegerField(
        default=0,
        verbose_name='Límite diario de tokens',
        help_text='0 = sin plan diario activo'
    )
    ultima_recarga_diaria = models.DateField(
        null=True, blank=True,
        verbose_name='Última recarga diaria'
    )
    fecha_vencimiento_tokens = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Vencimiento plan tokens'
    )

    # --- Alertas Proactivas ---
    alertas_activas = models.BooleanField(
        default=False,
        verbose_name='Alertas diarias activas',
    )
    alertas_sectores = models.CharField(
        max_length=50, default='', blank=True,
        verbose_name='Sectores de alerta',
        help_text='Ej: agro,naval — vacío = sin alertas configuradas',
    )
    hora_alerta = models.IntegerField(
        default=7,
        verbose_name='Hora de envío (Argentina)',
        help_text='Hora local Argentina (0-23)',
    )
    ubicacion_nombre = models.CharField(
        max_length=100, default='', blank=True,
        verbose_name='Ubicación para alertas',
        help_text='Ciudad o localidad, ej: Buenos Aires',
    )

    # --- Restricción sectorial (plan Starter) ---
    sector_elegido = models.CharField(
        max_length=10, default='', blank=True,
        verbose_name='Sector elegido (Starter)',
        help_text='Para plan Starter: sector al que tiene acceso. Vacío = puede elegir.',
    )

    # El @property debe estar alineado con 'user' y 'fecha...'
    @property
    def plan_nivel(self):
        """Calcula el nivel del plan según tokens_diarios_limite y suscripción activa."""
        if self.user.is_staff or self.user.is_superuser:
            return 'power'
        if not self.suscripcion_activa:
            # Puede tener plan de tokens sin suscripción clásica
            pass
        t = self.tokens_diarios_limite or 0
        # Umbrales alineados a PLANES_TOKENS (Gemini 3.1 Pro, techo ≈ precio)
        if t >= 180_000:
            return 'power'
        if t >= 90_000:
            return 'pro_ia'
        if t >= 42_000:
            return 'plus'
        if t >= 24_000:
            return 'starter'
        return 'free'

    @property
    def puede_excel(self):
        """Plus+ puede exportar Excel."""
        return self.plan_nivel in ('plus', 'pro_ia', 'power')

    @property
    def puede_radiacion(self):
        """Plus+: panel avanzado de radiación / balance energético (Agro + Energía)."""
        return self.plan_nivel in ('plus', 'pro_ia', 'power')

    @property
    def puede_ondas(self):
        """Plus+: panel avanzado de ondas / dinámica (Naval + Aéreo)."""
        return self.plan_nivel in ('plus', 'pro_ia', 'power')

    @property
    def puede_climatologia(self):
        """Pro IA+: panel de climatología / anomalías históricas en modos PRO."""
        return self.plan_nivel in ('pro_ia', 'power')

    @property
    def puede_devorador(self):
        """Plus+ pueden subir archivos y usar el Devorador de Reportes."""
        return self.plan_nivel in ('plus', 'pro_ia', 'power')

    @property
    def puede_alertas_proactivas(self):
        """Solo Pro IA y Power pueden tener alertas proactivas."""
        return self.plan_nivel in ('pro_ia', 'power')

    @property
    def puede_memoria_persistente(self):
        """Plus+ tiene memoria IA persistente entre sesiones."""
        return self.plan_nivel in ('plus', 'pro_ia', 'power')

    @property
    def dias_historial(self):
        """Días de historial BigQuery según plan."""
        nivel = self.plan_nivel
        if nivel == 'starter':
            return 7
        if nivel == 'plus':
            return 30
        if nivel == 'pro_ia':
            return 90
        if nivel == 'power':
            return 365
        return 0

    def tiene_acceso_sector(self, sector):
        """
        Verifica si el usuario puede acceder a un sector.
        Starter: solo el sector_elegido (o cualquiera si aún no eligió).
        Plus+: todos los sectores.
        """
        if self.user.is_staff or self.user.is_superuser:
            return True
        if self.plan_nivel in ('plus', 'pro_ia', 'power'):
            return True
        if self.plan_nivel == 'starter':
            if not self.sector_elegido:
                return True  # Todavía no eligió: puede acceder y elegirá ahora
            return self.sector_elegido.lower() == sector.lower()
        return False

    @property
    def suscripcion_activa(self):
        # Superusuarios y staff siempre tienen suscripción activa
        if self.user.is_staff or self.user.is_superuser:
            return True
        if not self.fecha_vencimiento:
            return False
        # Comparamos si la fecha de vencimiento es mayor a "ahora"
        return self.fecha_vencimiento > timezone.now()

    def _reset_diario_si_necesario(self):
        """Si hay plan diario activo y válido, repone tokens al inicio de cada día."""
        if not self.tokens_diarios_limite:
            return  # Sin plan diario, el pool es de uso único (admin / recarga manual)
        if self.fecha_vencimiento_tokens and self.fecha_vencimiento_tokens < timezone.now():
            return  # Plan vencido
        hoy = timezone.now().date()
        if self.ultima_recarga_diaria != hoy:
            self.tokens_disponibles = self.tokens_diarios_limite
            self.ultima_recarga_diaria = hoy
            self.save(update_fields=['tokens_disponibles', 'ultima_recarga_diaria'])

    def tiene_tokens(self, costo):
        """Verifica si el usuario tiene suficientes tokens para una operación."""
        if self.user.is_staff or self.user.is_superuser:
            return True  # Admin: acceso ilimitado sin restricciones
        if self.fecha_vencimiento_tokens and self.fecha_vencimiento_tokens < timezone.now():
            return False  # Plan vencido: cortar uso aunque quede saldo
        self._reset_diario_si_necesario()
        return self.tokens_disponibles >= costo

    def descontar_tokens(self, costo, descripcion):
        """
        Descuenta tokens de forma atómica y registra el uso.
        Retorna True si se descontó; False si no había saldo suficiente.
        """
        from django.db import transaction
        from django.db.models import F

        if self.user.is_staff or self.user.is_superuser:
            return True  # Admin: no se descuentan tokens

        self._reset_diario_si_necesario()
        with transaction.atomic():
            updated = (
                PerfilUsuario.objects
                .filter(pk=self.pk, tokens_disponibles__gte=costo)
                .update(
                    tokens_disponibles=F('tokens_disponibles') - costo,
                    tokens_usados_total=F('tokens_usados_total') + costo,
                )
            )
            if not updated:
                self.refresh_from_db(fields=['tokens_disponibles'])
                return False

            self.refresh_from_db(fields=['tokens_disponibles', 'tokens_usados_total'])
            HistorialTokens.objects.create(
                usuario=self.user,
                tipo='USO',
                cantidad=-costo,
                descripcion=descripcion,
                tokens_restantes=self.tokens_disponibles,
            )
        return True

    def recargar_tokens(self, cantidad, descripcion='Recarga manual'):
        """Suma tokens al saldo actual (uso admin, no cambia el límite diario)."""
        self.tokens_disponibles += cantidad
        self.save(update_fields=['tokens_disponibles'])
        HistorialTokens.objects.create(
            usuario=self.user,
            tipo='RECARGA',
            cantidad=cantidad,
            descripcion=descripcion,
            tokens_restantes=self.tokens_disponibles,
        )

    def activar_plan_tokens(self, tokens_dia, dias, descripcion):
        """Activa o renueva un plan de tokens diario + extiende acceso Pro a las páginas."""
        ahora = timezone.now()

        # Extender acceso Pro (agro / naval / aéreo / energía)
        if self.fecha_vencimiento and self.fecha_vencimiento > ahora:
            self.fecha_vencimiento += timedelta(days=dias)
        else:
            self.fecha_vencimiento = ahora + timedelta(days=dias)

        # Activar tokens diarios
        self.tokens_diarios_limite = tokens_dia
        self.fecha_vencimiento_tokens = ahora + timedelta(days=dias)
        self.tokens_disponibles = tokens_dia          # recarga inmediata del primer día
        self.ultima_recarga_diaria = ahora.date()
        self.save(update_fields=[
            'fecha_vencimiento',
            'tokens_diarios_limite', 'fecha_vencimiento_tokens',
            'tokens_disponibles', 'ultima_recarga_diaria',
        ])
        HistorialTokens.objects.create(
            usuario=self.user,
            tipo='BONO',
            cantidad=tokens_dia,
            descripcion=descripcion,
            tokens_restantes=self.tokens_disponibles,
        )

    def __str__(self):
        return self.user.username



class ReporteUsuario(models.Model):
    TIPOS = [
        ('IDEA', '💡 Sugerencia / Mejora'),
        ('BUG', '🐛 Reportar Error'),
        ('OTRO', '✉️ Otro mensaje')
    ]
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE) # Quién lo mandó
    tipo = models.CharField(max_length=10, choices=TIPOS, default='IDEA')
    mensaje = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.tipo}"


class DatoSectorial(models.Model):
    SECTORES = [
        ('NAVAL', 'Naval'),
        ('ENERGIA', 'Energía'),
        ('AEREO', 'Aéreo'), 
        ('AGRO', 'Agropecuario')
    ]
    
    sector = models.CharField(max_length=10, choices=SECTORES)
    fecha_registro = models.DateTimeField(default=timezone.now)
    valor_principal = models.FloatField(help_text="Valor principal del sector")
    valor_secundario = models.FloatField(null=True, blank=True, help_text="Valor secundario opcional")
    ubicacion = models.CharField(max_length=255, help_text="Ubicación geográfica")
    analisis_ia = models.TextField(help_text="Análisis generado por IA")
    metadatos = models.JSONField(default=dict, help_text="Datos específicos del sector")
    
    # Campos adicionales para trazabilidad
    archivo_origen = models.CharField(max_length=255, null=True, blank=True)
    usuario_carga = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    procesado_en = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Dato Sectorial"
        verbose_name_plural = "Datos Sectoriales"
        ordering = ['-fecha_registro']
    
    def __str__(self):
        return f"{self.sector} - {self.ubicacion} - {self.fecha_registro.strftime('%Y-%m-%d')}"
    
    def enviar_a_bigquery(self):
        """
        Envía los datos a BigQuery en la tabla correspondiente según el sector
        """
        try:
            # Verificar si BigQuery está configurado CORRECTAMENTE
            creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            project_id = os.getenv('BIGQUERY_PROJECT_ID')
            
            if not creds_path or not project_id:
                logger.warning("BigQuery no configurado - variables de entorno faltantes")
                return False, "BigQuery no configurado (variables de entorno faltantes)"
                
            if not os.path.exists(creds_path):
                logger.warning(f"BigQuery no configurado - archivo de credenciales no existe: {creds_path}")
                return False, f"BigQuery no configurado (archivo credenciales no existe: {creds_path})"
            
            # Configuración de BigQuery
            project_id = os.getenv('BIGQUERY_PROJECT_ID', "proyecto-bi-488218")
            
            # Mapeo de sectores a tablas
            tablas_sector = {
                'NAVAL': f'{project_id}.datos_clima.naval',
                'ENERGIA': f'{project_id}.datos_clima.energia', 
                'AEREO': f'{project_id}.datos_clima.aereo',
                'AGRO': f'{project_id}.datos_clima.agro'
            }
            
            tabla_destino = tablas_sector.get(self.sector)
            if not tabla_destino:
                raise ValueError(f"Sector {self.sector} no tiene tabla configurada")
            
            # Preparar datos para envío
            datos = {
                'id': self.id,
                'sector': self.sector,
                'fecha_registro': self.fecha_registro.isoformat(),
                'valor_principal': self.valor_principal,
                'valor_secundario': self.valor_secundario,
                'ubicacion': self.ubicacion,
                'analisis_ia': self.analisis_ia,
                'metadatos': json.dumps(self.metadatos),
                'archivo_origen': self.archivo_origen if self.archivo_origen else 'upload_web',
                'procesado_en': self.procesado_en.isoformat()
            }
            
            # Inicializar cliente BigQuery (import lazy: evita cargar pandas al arrancar Django)
            try:
                from google.cloud import bigquery
                client = bigquery.Client(project=project_id)
            except Exception as e:
                if "credentials" in str(e).lower():
                    logger.error("Error de credenciales BigQuery")
                    return False, "❌ Credenciales BigQuery no configuradas. Ver documentación para configurar GOOGLE_APPLICATION_CREDENTIALS"
                else:
                    raise e
            
            # Obtener referencia a la tabla
            try:
                table_ref = client.get_table(tabla_destino)
            except Exception as e:
                if "Not found" in str(e) or "404" in str(e):
                    logger.error(f"Tabla BigQuery no existe: {tabla_destino}")
                    return False, f"❌ Tabla BigQuery no existe: {tabla_destino}. Crear tabla primero."
                else:
                    raise e
            
            # Insertar datos
            errors = client.insert_rows_json(table_ref, [datos])
            
            if errors:
                logger.error(f"Error enviando a BigQuery: {errors}")
                return False, f"❌ Errores BigQuery: {errors[0]['message'] if errors else 'Error desconocido'}"
            else:
                logger.info(f"Datos enviados exitosamente a {tabla_destino}")
                return True, f"✅ Datos enviados correctamente a BigQuery tabla {tabla_destino}"
                
        except Exception as e:
            error_msg = str(e)
            
            # Mensajes de error más amigables
            if "credentials" in error_msg.lower() or "authentication" in error_msg.lower():
                friendly_msg = "❌ Configurar credenciales Google Cloud (GOOGLE_APPLICATION_CREDENTIALS)"
            elif "not found" in error_msg.lower() or "404" in error_msg.lower():
                friendly_msg = f"❌ Tabla BigQuery no existe: {tabla_destino}"
            elif "permission" in error_msg.lower() or "access" in error_msg.lower():
                friendly_msg = "❌ Sin permisos para escribir en BigQuery"
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                friendly_msg = "❌ Error de conexión con BigQuery"
            else:
                friendly_msg = f"❌ Error BigQuery: {error_msg[:100]}..."
            
            logger.error(f"Error en enviar_a_bigquery: {error_msg}")
            return False, friendly_msg
    
    def get_metadatos_especificos(self):
        """
        Retorna los metadatos específicos según el sector
        """
        metadatos_base = self.metadatos.copy()
        
        if self.sector == 'ENERGIA':
            return {
                'voltaje': metadatos_base.get('voltaje'),
                'frecuencia': metadatos_base.get('frecuencia'),
                'potencia': metadatos_base.get('potencia'),
                'factor_potencia': metadatos_base.get('factor_potencia')
            }
        elif self.sector == 'AEREO':
            return {
                'altitud': metadatos_base.get('altitud'),
                'presion_atmosferica': metadatos_base.get('presion_atmosferica'), 
                'visibilidad': metadatos_base.get('visibilidad'),
                'turbulencia': metadatos_base.get('turbulencia')
            }
        elif self.sector == 'AGRO':
            return {
                'humedad_suelo': metadatos_base.get('humedad_suelo'),
                'ph_suelo': metadatos_base.get('ph_suelo'),
                'nutrientes': metadatos_base.get('nutrientes'),
                'tipo_cultivo': metadatos_base.get('tipo_cultivo')
            }
        elif self.sector == 'NAVAL':
            return {
                'altura_olas': metadatos_base.get('altura_olas'),
                'corriente_marina': metadatos_base.get('corriente_marina'),
                'salinidad': metadatos_base.get('salinidad'),
                'marea': metadatos_base.get('marea')
            }
        
        return metadatos_base


class FeedbackIA(models.Model):
    """
    Modelo para almacenar feedback de usuarios sobre respuestas de la IA
    Incluye: likes, dislikes y comentarios
    """
    SECTORES = [
        ('NAVAL', 'Naval'),
        ('ENERGIA', 'Energía'),
        ('AEREO', 'Aéreo'), 
        ('AGRO', 'Agropecuario')
    ]
    
    TIPOS_FEEDBACK = [
        ('LIKE', 'Me gusta'),
        ('DISLIKE', 'No me gusta'),
        ('COMENTARIO', 'Comentario')
    ]
    
    # Información del feedback
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                help_text="Usuario que dejó el feedback (opcional)")
    sector = models.CharField(max_length=10, choices=SECTORES, help_text="Sector donde se generó el feedback")
    tipo_feedback = models.CharField(max_length=15, choices=TIPOS_FEEDBACK)
    
    # Contenido
    mensaje_ia = models.TextField(help_text="Mensaje de la IA que recibió feedback")
    comentario = models.TextField(blank=True, null=True, help_text="Comentario del usuario (opcional)")
    
    # Metadatos
    session_id = models.CharField(max_length=100, blank=True, null=True, 
                                  help_text="ID de sesión del chat")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    ip_usuario = models.GenericIPAddressField(null=True, blank=True)
    
    # Estado
    revisado = models.BooleanField(default=False, help_text="Marcado como revisado por administrador")
    notas_admin = models.TextField(blank=True, null=True, help_text="Notas del administrador")
    
    class Meta:
        verbose_name = "Feedback IA"
        verbose_name_plural = "Feedbacks IA"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['-fecha_creacion']),
            models.Index(fields=['sector', '-fecha_creacion']),
            models.Index(fields=['tipo_feedback', '-fecha_creacion']),
        ]
    
    def __str__(self):
        usuario_str = self.usuario.username if self.usuario else "Anónimo"
        return f"{self.sector} - {self.tipo_feedback} - {usuario_str} - {self.fecha_creacion.strftime('%Y-%m-%d %H:%M')}"
    
    def mensaje_preview(self):
        """Retorna preview del mensaje de la IA (primeros 100 caracteres)"""
        if len(self.mensaje_ia) > 100:
            return self.mensaje_ia[:100] + "..."
        return self.mensaje_ia
    
    def comentario_preview(self):
        """Retorna preview del comentario (primeros 100 caracteres)"""
        if not self.comentario:
            return "-"
        if len(self.comentario) > 100:
            return self.comentario[:100] + "..."
        return self.comentario


# ==========================================
# SISTEMA DE TOKENS IA (Gemini Pro)
# ==========================================

# Costos por operación (en créditos internos)
# Gemini 3.1 Pro (~$2/M input, $12/M output + thinking).
# Cupos diarios calibrados a techo API ≈ precio del plan (CHAT_N8N ≈ $0.08).
COSTO_TOKENS = {
    'CHAT_N8N':           3_000,   # Consulta al chat IA (con memoria y tools) ≈ $0.08
    'CHAT_SIMPLE':        2_000,   # Consulta rápida sin tools externas
    'CHAT_HEAVY':         5_000,   # Generación de Excel, Docs o reporte BI ≈ $0.15–0.25
    'ANALISIS_ARCHIVO':  10_000,   # Procesar archivo + análisis IA completo ≈ $0.25–0.40
    'DEVORADOR_REPORTE': 10_000,   # Devorador de Reportes PDF + Gemini
}

# Legacy suscripción Pro → cupo Starter (techo API ~$20/mes)
TOKENS_DIARIOS_SUSCRIPCION = 24_000


class HistorialTokens(models.Model):
    """
    Registro de cada uso o recarga de tokens de IA por usuario.
    Sirve tanto para auditoría como para mostrar el estado en la cuenta.
    """
    TIPOS = [
        ('USO',     'Uso IA'),
        ('RECARGA', 'Recarga pagada'),
        ('BONO',    'Bono / activación suscripción'),
    ]

    usuario          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='historial_tokens')
    tipo             = models.CharField(max_length=10, choices=TIPOS)
    cantidad         = models.IntegerField(help_text='Positivo = recarga, Negativo = consumo')
    descripcion      = models.CharField(max_length=255)
    tokens_restantes = models.IntegerField(help_text='Saldo tras esta operación')
    fecha            = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Historial de Tokens"
        verbose_name_plural = "Historial de Tokens"
        ordering            = ['-fecha']

    def __str__(self):
        signo = '+' if self.cantidad > 0 else ''
        return f"{self.usuario.username} | {signo}{self.cantidad} ({self.tipo}) | saldo: {self.tokens_restantes}"


# ==========================================
# NUEVAS FUNCIONALIDADES (multi-ubicación, reportes, api key)
# ==========================================

class UbicacionGuardada(models.Model):
    """
    Permite guardar múltiples ubicaciones geográficas por usuario.
    Límite según plan: Starter=1, Plus=5, Pro IA=10, Power=ilimitado.
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ubicaciones')
    nombre = models.CharField(max_length=100)
    lat = models.FloatField()
    lon = models.FloatField()
    sector = models.CharField(max_length=10, blank=True,
                              help_text="Sector preferido para esta ubicación: agro/naval/aereo/energia")
    es_principal = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ubicación guardada"
        verbose_name_plural = "Ubicaciones guardadas"
        ordering = ['-es_principal', '-creada']

    def __str__(self):
        return f"{self.usuario.username} — {self.nombre} ({self.lat:.3f}, {self.lon:.3f})"

    @staticmethod
    def limite_para_plan(nivel):
        """Retorna el número máximo de ubicaciones para cada nivel de plan."""
        return {'starter': 1, 'plus': 5, 'pro_ia': 10, 'power': None}.get(nivel, 0)


class ReporteProgramado(models.Model):
    """
    Define un reporte automático periódico por email para un sector determinado.
    Requiere plan Pro IA o Power.
    """
    FRECUENCIAS = [
        ('diario', 'Diario'),
        ('semanal', 'Semanal'),
        ('mensual', 'Mensual'),
    ]
    SECTORES = [
        ('agro', 'Agropecuario'),
        ('naval', 'Naval'),
        ('aereo', 'Aéreo'),
        ('energia', 'Energía'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reportes_programados')
    sector = models.CharField(max_length=10, choices=SECTORES)
    frecuencia = models.CharField(max_length=10, choices=FRECUENCIAS, default='diario')
    hora_envio = models.PositiveSmallIntegerField(default=8,
                                                  help_text="Hora UTC (0–23) en la que se envía el reporte")
    email_destino = models.EmailField(blank=True,
                                      help_text="Dejar vacío para usar el email de la cuenta")
    activo = models.BooleanField(default=True)
    ultimo_envio = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reporte programado"
        verbose_name_plural = "Reportes programados"
        ordering = ['-creado']

    def __str__(self):
        return f"{self.usuario.username} — {self.get_sector_display()} {self.get_frecuencia_display()}"

    def email_efectivo(self):
        """Email que recibirá el reporte (propio o personalizado)."""
        return self.email_destino or self.usuario.email


class ConfiguracionModal(models.Model):
    """
    Personalización guardada por el usuario dentro de un modal interactivo
    de las páginas profesionales (agro/naval/aereo/energia). Ej: cultivo
    elegido, fecha de siembra, tipo de suelo, capacidad de riego, etc.
    Los campos varían por modal, por eso se guardan en un JSONField libre.
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='config_modal')
    sector = models.CharField(max_length=10, help_text="agro/naval/aereo/energia")
    modal_id = models.CharField(max_length=40, help_text="Ej: modGDD, modVPD, modEol...")
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    datos = models.JSONField(default=dict, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de modal"
        verbose_name_plural = "Configuraciones de modales"
        unique_together = ('usuario', 'sector', 'modal_id', 'lat', 'lon')

    def __str__(self):
        return f"{self.usuario.username} — {self.sector}/{self.modal_id}"


class AlertaModal(models.Model):
    """
    Regla de alerta configurada por el usuario sobre una variable puntual
    de un modal (ej. avisar si VPD > 1.5 kPa). Se evalúa en cada carga de
    la página contra el valor calculado en ese momento.
    """
    OPERADORES = [('gt', 'Mayor que'), ('lt', 'Menor que')]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alertas_modal')
    sector = models.CharField(max_length=10)
    modal_id = models.CharField(max_length=40)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    variable = models.CharField(max_length=40, help_text="Clave de la variable a evaluar, ej: 'vpd'")
    operador = models.CharField(max_length=2, choices=OPERADORES, default='gt')
    umbral = models.FloatField()
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alerta de modal"
        verbose_name_plural = "Alertas de modales"
        ordering = ['-creada']

    def __str__(self):
        return f"{self.usuario.username} — {self.modal_id}.{self.variable} {self.operador} {self.umbral}"

    def evaluar(self, valor_actual):
        if valor_actual is None:
            return False
        if self.operador == 'gt':
            return valor_actual > self.umbral
        return valor_actual < self.umbral


class NotaModal(models.Model):
    """
    Bitácora libre del usuario asociada a un modal puntual (ej. registrar
    una aplicación fitosanitaria, un riego, o cualquier observación de campo).
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notas_modal')
    sector = models.CharField(max_length=10)
    modal_id = models.CharField(max_length=40)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    texto = models.TextField(max_length=500)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nota de modal"
        verbose_name_plural = "Notas de modales"
        ordering = ['-creada']

    def __str__(self):
        return f"{self.usuario.username} — {self.modal_id} ({self.creada:%Y-%m-%d})"


class ApiKeyPersonal(models.Model):
    """
    API key de acceso personal para que usuarios Plus+ puedan integrar
    sus datos en herramientas externas (Power BI, scripts, etc.).
    """
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_key')
    clave = models.CharField(max_length=64, unique=True)
    nombre = models.CharField(max_length=60, default='Mi API Key')
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "API key personal"
        verbose_name_plural = "API keys personales"

    def __str__(self):
        return f"{self.usuario.username} — {self.nombre} ({'activa' if self.activa else 'inactiva'})"