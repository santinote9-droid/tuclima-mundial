from django.contrib import admin
from .models import PerfilUsuario, ReporteUsuario, FeedbackIA


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


# Configuración para FeedbackIA
@admin.register(FeedbackIA)
class FeedbackIAAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo_feedback', 'sector', 'usuario_display', 'fecha_creacion', 'revisado', 'mensaje_corto')
    list_filter = ('tipo_feedback', 'sector', 'revisado', 'fecha_creacion')
    search_fields = ('mensaje_ia', 'comentario', 'usuario__username', 'session_id')
    readonly_fields = ('fecha_creacion', 'ip_usuario', 'session_id')
    list_editable = ('revisado',)  # Permite marcar como revisado directamente desde la lista
    ordering = ('-fecha_creacion',)
    
    # Campos a mostrar en el formulario de edición
    fieldsets = (
        ('Información del Feedback', {
            'fields': ('usuario', 'sector', 'tipo_feedback', 'revisado')
        }),
        ('Contenido', {
            'fields': ('mensaje_ia', 'comentario')
        }),
        ('Metadatos', {
            'fields': ('session_id', 'ip_usuario', 'fecha_creacion'),
            'classes': ('collapse',)  # Colapsado por defecto
        }),
        ('Notas Administrativas', {
            'fields': ('notas_admin',),
            'classes': ('collapse',)
        }),
    )
    
    def usuario_display(self, obj):
        return obj.usuario.username if obj.usuario else 'Anónimo'
    usuario_display.short_description = 'Usuario'
    
    def mensaje_corto(self, obj):
        return obj.mensaje_preview()
    mensaje_corto.short_description = 'Preview Mensaje IA'
    
    # Acción personalizada para marcar múltiples feedbacks como revisados
    actions = ['marcar_como_revisado', 'marcar_como_no_revisado']
    
    def marcar_como_revisado(self, request, queryset):
        count = queryset.update(revisado=True)
        self.message_user(request, f'{count} feedback(s) marcado(s) como revisado(s).')
    marcar_como_revisado.short_description = 'Marcar seleccionados como revisados'
    
    def marcar_como_no_revisado(self, request, queryset):
        count = queryset.update(revisado=False)
        self.message_user(request, f'{count} feedback(s) marcado(s) como no revisado(s).')
    marcar_como_no_revisado.short_description = 'Marcar seleccionados como no revisados'
