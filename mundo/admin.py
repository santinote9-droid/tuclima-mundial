from django.contrib import admin
from .models import PerfilUsuario
from .models import ReporteUsuario


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    # Aquí estaba el error. Cambiamos 'es_premium' por 'suscripcion_activa'
    list_display = ('user', 'fecha_vencimiento', 'suscripcion_activa')
    
    # Esto permite buscar por nombre de usuario
    search_fields = ('user__username',)



# Configuración para que se vea profesional en el Admin
class ReporteAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'fecha', 'mensaje_corto') # Columnas visibles
    list_filter = ('tipo', 'fecha') # Filtros a la derecha
    search_fields = ('usuario__username', 'mensaje') # Barra de búsqueda
    readonly_fields = ('fecha',) # Para que nadie truche la fecha

    # Truco para que el mensaje no ocupe toda la pantalla si es muy largo
    def mensaje_corto(self, obj):
        return obj.mensaje[:50] + "..." if len(obj.mensaje) > 50 else obj.mensaje
    mensaje_corto.short_description = 'Mensaje'

# Registramos el modelo con esa configuración
admin.site.register(ReporteUsuario, ReporteAdmin)
