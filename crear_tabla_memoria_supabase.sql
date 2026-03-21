-- 🧠 TABLA DE MEMORIA PARA IA EN N8N
-- Ejecutar en Supabase SQL Editor

-- Eliminar tabla si existe para recrearla limpia
DROP TABLE IF EXISTS public.conversaciones_memoria CASCADE;

CREATE TABLE public.conversaciones_memoria (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT,
    timestamp TIMESTAMPTZ DEFAULT now(),
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    contexto_previo JSONB DEFAULT '{}',
    metadatos JSONB DEFAULT '{}',
    sector TEXT, -- naval, agro, aereo, energia
    ubicacion JSONB, -- {lat: -34.5794, lon: -58.5944}
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Índices para búsqueda rápida
CREATE INDEX idx_session_id ON public.conversaciones_memoria(session_id);
CREATE INDEX idx_user_id ON public.conversaciones_memoria(user_id);
CREATE INDEX idx_timestamp ON public.conversaciones_memoria(timestamp DESC);
CREATE INDEX idx_sector ON public.conversaciones_memoria(sector);

-- RLS (Row Level Security) - opcional pero recomendado
ALTER TABLE public.conversaciones_memoria ENABLE ROW LEVEL SECURITY;

-- Política para permitir insertar/leer todas las conversaciones
DROP POLICY IF EXISTS "Permitir acceso completo a conversaciones" ON public.conversaciones_memoria;
CREATE POLICY "Permitir acceso completo a conversaciones" ON public.conversaciones_memoria
    FOR ALL USING (true) WITH CHECK (true);

-- Función para limpiar conversaciones antiguas automáticamente
CREATE OR REPLACE FUNCTION limpiar_conversaciones_antiguas()
RETURNS void AS $$
BEGIN
    DELETE FROM public.conversaciones_memoria 
    WHERE created_at < now() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar timestamp automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_conversaciones_memoria_updated_at ON public.conversaciones_memoria;
CREATE TRIGGER update_conversaciones_memoria_updated_at 
    BEFORE UPDATE ON public.conversaciones_memoria 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ══════════════════════════════════════════════════════
-- PUNTO 1: LIMITAR CONTEXTO RECUPERADO POR n8n
-- ══════════════════════════════════════════════════════
-- En el nodo "Get many rows" de Supabase en n8n, configurar así:
--
-- Operation:  Get many rows
-- Table:       conversaciones_memoria
-- Filter:      user_id = {{ $json.userId }}   ← campo que ahora llega en FormData
--              (también podés usar session_id si preferís)
-- Sort:        timestamp DESC
-- Limit:       6   ← máximo de conversaciones previas al contexto de Gemini
--
-- Esto garantiza que Gemini recibe el historial justo, sin exceder el context window.
-- Si el GET anterior usaba session_id, podés agregar OR:
--   WHERE user_id = 'X' OR session_id = 'X' para compatibilidad con sesiones viejas.

-- ══════════════════════════════════════════════════════
-- PUNTO 2: AUTO-LIMPIEZA PROGRAMADA CON pg_cron
-- ══════════════════════════════════════════════════════
-- Ejecutar esto en Supabase > SQL Editor (requiere extensión pg_cron, disponible en Supabase Pro)
-- En plan Free, usar la alternativa n8n que está más abajo.

-- Habilitar pg_cron (solo necesario una vez):
-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Programar limpieza diaria a las 3 AM UTC:
-- SELECT cron.schedule(
--     'limpiar_memoria_ia',             -- nombre del job
--     '0 3 * * *',                       -- cron: todos los días a las 03:00 UTC
--     $$DELETE FROM public.conversaciones_memoria WHERE created_at < now() - INTERVAL '30 days';$$
-- );

-- Para verificar que el job quedó registrado:
-- SELECT * FROM cron.job;

-- Para cancelar el job si hace falta:
-- SELECT cron.unschedule('limpiar_memoria_ia');

-- ── ALTERNATIVA GRATIS (n8n Schedule Trigger) ──────────
-- Si usás Supabase Free (sin pg_cron), agregá este workflow en n8n:
--
--  [Schedule Trigger]  → cron: 0 3 * * *  (diario 03:00 UTC)
--       ↓
--  [Supabase: Execute SQL]
--       Query: DELETE FROM public.conversaciones_memoria
--              WHERE created_at < now() - INTERVAL '30 days';
--
-- Esto es equivalente y no requiere pagar el plan Pro de Supabase.

-- ══════════════════════════════════════════════════════
-- ÍNDICE ADICIONAL: user_id para la nueva query de n8n
-- ══════════════════════════════════════════════════════
-- Si no existía, crear índice para acelerar búsquedas por user_id:
CREATE INDEX IF NOT EXISTS idx_user_id_ts ON public.conversaciones_memoria(user_id, timestamp DESC);

-- Ver datos para verificar
-- SELECT * FROM public.conversaciones_memoria ORDER BY created_at DESC LIMIT 5;

-- Verificar que la tabla se creó correctamente
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable 
FROM information_schema.columns 
WHERE table_name = 'conversaciones_memoria' 
    AND table_schema = 'public'
ORDER BY ordinal_position;