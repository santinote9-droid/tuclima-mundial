from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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

    
