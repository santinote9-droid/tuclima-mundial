from django.contrib import admin
from django.shortcuts import render
from .models import (
    PerfilUsuario, ReporteUsuario, FeedbackIA, HistorialTokens,
    UbicacionGuardada, ReporteProgramado, ApiKeyPersonal,
    ConfiguracionModal, AlertaModal, NotaModal,
)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'fecha_vencimiento', 'suscripcion_activa',
        'tokens_diarios_limite', 'tokens_disponibles', 'fecha_vencimiento_tokens',
    )
    search_fields = ('user__username', 'user__email')
    list_filter = ('tokens_diarios_limite',)
    actions = ['activar_plan_tokens_action']

    @admin.action(description='Activar plan de tokens…')
    def activar_plan_tokens_action(self, request, queryset):
        from mundo.views import _PAQUETES_MAP, _descripcion_plan_tokens

        if 'apply' in request.POST:
            paquete_id = (request.POST.get('paquete_id') or '').strip()
            paquete = _PAQUETES_MAP.get(paquete_id)
            if not paquete:
                self.message_user(request, 'Paquete inválido.', level='error')
                return None

            activados = 0
            for perfil in queryset.select_related('user'):
                desc = f"[Admin] {_descripcion_plan_tokens(paquete)}"
                perfil.activar_plan_tokens(
                    paquete['tokens_dia'],
                    paquete['dias'],
                    desc,
                )
                activados += 1

            self.message_user(
                request,
                f'Plan {paquete["nombre"]} ({paquete_id}) activado para {activados} usuario(s).',
            )
            return None

        paquetes = sorted(_PAQUETES_MAP.values(), key=lambda p: (p['precio'], p['id']))
        return render(
            request,
            'admin/activar_plan_tokens.html',
            context={
                **self.admin_site.each_context(request),
                'title': 'Activar plan de tokens',
                'queryset': queryset,
                'paquetes': paquetes,
                'opts': self.model._meta,
            },
        )



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


@admin.register(HistorialTokens)
class HistorialTokensAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'cantidad', 'tokens_restantes', 'descripcion_corta', 'fecha')
    list_filter = ('tipo', 'fecha')
    search_fields = ('usuario__username', 'descripcion')
    ordering = ('-fecha',)
    readonly_fields = ('fecha',)

    def descripcion_corta(self, obj):
        return obj.descripcion[:60] + '...' if len(obj.descripcion) > 60 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'


# ── Nuevos modelos ──────────────────────────────────────────────────────────

@admin.register(UbicacionGuardada)
class UbicacionGuardadaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nombre', 'lat', 'lon', 'sector', 'es_principal', 'creada')
    list_filter = ('sector', 'es_principal')
    search_fields = ('usuario__username', 'nombre')
    ordering = ('-creada',)


@admin.register(ReporteProgramado)
class ReporteProgramadoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'sector', 'frecuencia', 'hora_envio', 'activo', 'ultimo_envio', 'creado')
    list_filter = ('sector', 'frecuencia', 'activo')
    search_fields = ('usuario__username', 'email_destino')
    ordering = ('-creado',)
    list_editable = ('activo',)


@admin.register(ApiKeyPersonal)
class ApiKeyPersonalAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nombre', 'activa', 'creada', 'ultimo_uso')
    list_filter = ('activa',)
    search_fields = ('usuario__username', 'nombre')
    ordering = ('-creada',)
    readonly_fields = ('clave', 'creada', 'ultimo_uso')


# ── Modales interactivos (personalización / alertas / notas) ────────────────

@admin.register(ConfiguracionModal)
class ConfiguracionModalAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'sector', 'modal_id', 'lat', 'lon', 'actualizado_en')
    list_filter = ('sector', 'modal_id')
    search_fields = ('usuario__username', 'modal_id')
    ordering = ('-actualizado_en',)


@admin.register(AlertaModal)
class AlertaModalAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'sector', 'modal_id', 'variable', 'operador', 'umbral', 'activa', 'creada')
    list_filter = ('sector', 'modal_id', 'activa')
    search_fields = ('usuario__username', 'modal_id', 'variable')
    ordering = ('-creada',)
    list_editable = ('activa',)


@admin.register(NotaModal)
class NotaModalAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'sector', 'modal_id', 'texto_corto', 'creada')
    list_filter = ('sector', 'modal_id')
    search_fields = ('usuario__username', 'modal_id', 'texto')
    ordering = ('-creada',)

    def texto_corto(self, obj):
        return obj.texto[:60] + '...' if len(obj.texto) > 60 else obj.texto
    texto_corto.short_description = 'Nota'
