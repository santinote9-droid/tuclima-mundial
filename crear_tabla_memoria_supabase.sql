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