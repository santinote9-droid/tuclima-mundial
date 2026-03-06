from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json
from google.cloud import bigquery
from google.oauth2 import service_account
import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno explícitamente
load_dotenv()

logger = logging.getLogger(__name__)

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)

    # El @property debe estar alineado con 'user' y 'fecha...'
    @property
    def suscripcion_activa(self):
        if not self.fecha_vencimiento:
            return False
        # Comparamos si la fecha de vencimiento es mayor a "ahora"
        return self.fecha_vencimiento > timezone.now()

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
            
            # Inicializar cliente BigQuery
            try:
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