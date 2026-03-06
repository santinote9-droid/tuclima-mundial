/**
 * 🤖 N8N WORKFLOW - GENERACIÓN DINÁMICA DE GRÁFICOS POWER BI
 * 
 * Este código va en un Function Node de N8N que procesa peticiones del chat
 * y genera URLs específicas de Power BI basadas en lo que pide el usuario
 */

// 🎯 CONFIGURACIÓN PRINCIPAL
const POWERBI_BASE_URL = "https://app.powerbi.com/view?r=eyJrIjoiOGVkMzlkY2QtYjJmOC00NmY3LTkzOWYtMTE5NTljYzAxOGJhIiwidCI6IjU4MWJhNzMyLTczYWUtNDhiZC1iNmQ2LTY4ZTA0NzYxNjA4OCIsImMiOjR9";

// 📊 MAPEO DE TIPOS DE GRÁFICOS
const CHART_TYPES = {
    // Gráficos temporales
    "lineal": "&pageName=ReportSection_Lineal",
    "tendencia": "&pageName=ReportSection_Lineal",
    "evolucion": "&pageName=ReportSection_Lineal",
    "historico": "&pageName=ReportSection_Lineal",
    
    // Mapas y ubicaciones
    "mapa": "&pageName=ReportSection_Mapa",
    "geografico": "&pageName=ReportSection_Mapa",
    "ubicacion": "&pageName=ReportSection_Mapa",
    "regional": "&pageName=ReportSection_Mapa",
    
    // Comparativas
    "comparativa": "&pageName=ReportSection_Comparativa",
    "comparacion": "&pageName=ReportSection_Comparativa",
    "sectorial": "&pageName=ReportSection_Comparativa",
    "ranking": "&pageName=ReportSection_Comparativa",
    
    // Predictivo
    "prediccion": "&pageName=ReportSection_Predictivo",
    "pronostico": "&pageName=ReportSection_Predictivo",
    "futuro": "&pageName=ReportSection_Predictivo",
    "tendencia": "&pageName=ReportSection_Predictivo",
    
    // Dashboard general
    "general": "&pageName=ReportSection_Dashboard",
    "resumen": "&pageName=ReportSection_Dashboard",
    "overview": "&pageName=ReportSection_Dashboard"
};

// 🌍 SECTORES Y PARÁMETROS ESPECÍFICOS EXISTENTES
const SECTOR_PARAMS = {
    "agro": {
        "name": "agro",
        "table": "AGRO_BI",
        "fields": ["cultivo", "region", "temperatura_suelo", "humedad_relativa", "precipitacion", "horas_sol", "fase_lunar", "ai_recommendations"]
    },
    "naval": {
        "name": "naval", 
        "table": "NAVAL_BI",
        "fields": ["puerto", "condiciones_mar", "viento_velocidad", "viento_direccion", "temperatura_agua", "altura_olas", "visibilidad", "ai_analysis"]
    },
    "aereo": {
        "name": "aereo",
        "table": "AEREO_BI", 
        "fields": ["aeropuerto_origen", "aeropuerto_destino", "altitud_vuelo", "temperatura_altitud", "corrientes_viento", "visibilidad_km", "condiciones_atmosfericas", "ai_flight_analysis"]
    },
    "energia": {
        "name": "energia",
        "table": "ENERGIA_BI",
        "fields": ["tipo_energia", "ubicacion", "radiacion_solar", "velocidad_viento", "temperatura_ambiente", "eficiencia_estimada", "produccion_kwh", "ai_efficiency_analysis"]
    }
};

// Keywords para detectar sectores
const SECTORS = {
    "agro": "agro", "agricola": "agro", "siembra": "agro", "cosecha": "agro", "cultivo": "agro",
    "naval": "naval", "maritimo": "naval", "mar": "naval", "puerto": "naval", "navegacion": "naval",
    "aereo": "aereo", "aviacion": "aereo", "vuelo": "aereo", "aeropuerto": "aereo", "aerolinea": "aereo",
    "energia": "energia", "electrico": "energia", "renovable": "energia", "eolico": "energia", "solar": "energia"
};

// 📈 MÉTRICAS ESPECÍFICAS POR SECTOR
const SECTOR_METRICS = {
    "naval": {
        "viento": "viento_velocidad",
        "olas": "altura_olas", 
        "temperatura": "temperatura_agua",
        "visibilidad": "visibilidad",
        "condiciones": "condiciones_mar",
        "puerto": "puerto",
        "analisis": "ai_analysis"
    },
    "agro": {
        "cultivo": "cultivo",
        "temperatura": "temperatura_suelo",
        "humedad": "humedad_relativa", 
        "lluvia": "precipitacion",
        "sol": "horas_sol",
        "luna": "fase_lunar",
        "region": "region",
        "recomendaciones": "ai_recommendations"
    },
    "aereo": {
        "temperatura": "temperatura_altitud",
        "viento": "corrientes_viento",
        "visibilidad": "visibilidad_km",
        "altitud": "altitud_vuelo",
        "condiciones": "condiciones_atmosfericas",
        "origen": "aeropuerto_origen",
        "destino": "aeropuerto_destino",
        "analisis": "ai_flight_analysis"
    },
    "energia": {
        "solar": "radiacion_solar",
        "viento": "velocidad_viento",
        "temperatura": "temperatura_ambiente",
        "eficiencia": "eficiencia_estimada",
        "produccion": "produccion_kwh",
        "tipo": "tipo_energia",
        "analisis": "ai_efficiency_analysis"
    }
};

// Keywords generales de métricas
const METRICS = {
    "temperatura": "temperatura", "temp": "temperatura", "calor": "temperatura",
    "humedad": "humedad", "humidity": "humedad",
    "viento": "viento", "wind": "viento", "velocidad": "viento",
    "precipitacion": "precipitacion", "lluvia": "precipitacion", "rain": "precipitacion",
    "presion": "presion", "pressure": "presion", "barometrica": "presion",
    "riesgo": "riesgo", "alerta": "riesgo", "peligro": "riesgo",
    "eficiencia": "eficiencia", "produccion": "produccion", "solar": "solar",
    "olas": "olas", "visibilidad": "visibilidad", "cultivo": "cultivo"
};

// 🕒 RANGOS TEMPORALES
const TIME_RANGES = {
    "hoy": "24h",
    "dia": "24h", 
    "diario": "24h",
    
    "semana": "7d",
    "semanal": "7d",
    "7dias": "7d",
    
    "mes": "30d",
    "mensual": "30d",
    "30dias": "30d",
    
    "trimestre": "90d",
    "trimestral": "90d",
    
    "año": "365d",
    "anual": "365d",
    "historico": "365d"
};

// 🧠 FUNCIÓN PRINCIPAL - PROCESAR PETICIÓN DEL USUARIO
function procesarPeticionGrafico(userInput, sessionData) {
    
    const input = userInput.toLowerCase();
    
    // 1️⃣ DETECTAR SOLICITUD DE GRÁFICO
    const solicitudGrafico = 
        input.includes("grafico") || 
        input.includes("gráfico") || 
        input.includes("mostrar") || 
        input.includes("ver") || 
        input.includes("crear") || 
        input.includes("generar") || 
        input.includes("dashboard") || 
        input.includes("reporte") ||
        input.includes("mapa") ||
        input.includes("comparar") ||
        input.includes("comparativa");
    
    if (!solicitudGrafico) {
        return null; // No es una petición de gráfico
    }
    
    // 2️⃣ EXTRAER COMPONENTES
    const tipoGrafico = extraerTipoGrafico(input);
    const sector = extraerSector(input, sessionData);
    const metrica = extraerMetrica(input, sector); // Pasar sector para métricas específicas
    const rangoTiempo = extraerRangoTiempo(input);
    const ubicacion = extraerUbicacion(input, sessionData);
    
    // 3️⃣ GENERAR URL ESPECÍFICA
    const urlPowerBI = generarUrlPowerBI({
        tipo: tipoGrafico,
        sector: sector,
        metrica: metrica,
        tiempo: rangoTiempo,
        ubicacion: ubicacion
    });
    
    // 4️⃣ GENERAR RESPUESTA CONTEXTUAL
    const respuesta = generarRespuestaContextual({
        tipo: tipoGrafico,
        sector: sector,
        metrica: metrica,
        tiempo: rangoTiempo,
        url: urlPowerBI
    });
    
    return {
        mostrarGrafico: true,
        urlPowerBI: urlPowerBI,
        respuesta: respuesta
    };
}

// 🔍 FUNCIONES DE EXTRACCIÓN

function extraerTipoGrafico(input) {
    for (const [keyword, chartType] of Object.entries(CHART_TYPES)) {
        if (input.includes(keyword)) {
            return chartType;
        }
    }
    
    // Detectar por contexto
    if (input.includes("tiempo") || input.includes("evolucion") || input.includes("historico")) {
        return CHART_TYPES.lineal;
    }
    if (input.includes("donde") || input.includes("ubicacion") || input.includes("zona")) {
        return CHART_TYPES.mapa;
    }
    if (input.includes("vs") || input.includes("contra") || input.includes("diferencia")) {
        return CHART_TYPES.comparativa;
    }
    
    return CHART_TYPES.general; // Por defecto dashboard general
}

function extraerSector(input, sessionData) {
    // Primero verificar el contexto de la página actual
    if (sessionData && sessionData.currentPage) {
        const currentSector = sessionData.currentPage.toLowerCase();
        if (SECTORS[currentSector]) {
            return SECTORS[currentSector];
        }
    }
    
    // Luego buscar en el input del usuario
    for (const [keyword, sector] of Object.entries(SECTORS)) {
        if (input.includes(keyword)) {
            return sector;
        }
    }
    
    return "todos"; // Por defecto todos los sectores
}

function extraerMetrica(input, sector) {
    const sectorMetricas = SECTOR_METRICS[sector] || {};
    
    // Buscar métricas específicas del sector primero
    for (const [keyword, fieldName] of Object.entries(sectorMetricas)) {
        if (input.includes(keyword)) {
            return fieldName;
        }
    }
    
    // Buscar métricas generales
    for (const [keyword, metric] of Object.entries(METRICS)) {
        if (input.includes(keyword)) {
            // Mapear a campo específico del sector si existe
            if (sectorMetricas[metric]) {
                return sectorMetricas[metric];
            }
            return metric;
        }
    }
    
    // Métricas por defecto según sector
    const defaultMetrics = {
        "naval": "viento_velocidad",
        "agro": "humedad_relativa", 
        "aereo": "corrientes_viento",
        "energia": "eficiencia_estimada"
    };
    
    return defaultMetrics[sector] || "timestamp";
}

function extraerRangoTiempo(input) {
    for (const [keyword, range] of Object.entries(TIME_RANGES)) {
        if (input.includes(keyword)) {
            return range;
        }
    }
    
    // Detectar números específicos
    if (input.includes("24") || input.includes("horas")) {
        return "24h";
    }
    if (input.includes("7") || input.includes("semana")) {
        return "7d";
    }
    if (input.includes("30") || input.includes("mes")) {
        return "30d";
    }
    
    return "7d"; // Por defecto última semana
}

function extraerUbicacion(input, sessionData) {
    // Intentar extraer coordenadas o nombres de ciudad
    const coordRegex = /(-?\d+\.?\d*),?\s*(-?\d+\.?\d*)/;
    const match = input.match(coordRegex);
    
    if (match) {
        return {
            lat: parseFloat(match[1]),
            lon: parseFloat(match[2])
        };
    }
    
    // Usar ubicación de la sesión si está disponible
    if (sessionData && sessionData.location) {
        return sessionData.location;
    }
    
    return null; // Sin filtro de ubicación específica
}

// 🔗 GENERAR URL DE POWER BI

function generarUrlPowerBI(params) {
    let url = POWERBI_BASE_URL;
    
    // Agregar página específica
    if (params.tipo) {
        url += params.tipo;
    }
    
    // Obtener configuración del sector
    const sectorConfig = SECTOR_PARAMS[params.sector];
    const tableName = sectorConfig ? sectorConfig.table : 'DatosClima';
    
    // Agregar filtros
    const filtros = [];
    
    // Filtro de sector usando tabla específica
    if (params.sector && params.sector !== "todos" && tableName) {
        // No filtrar por sector, ya estamos usando la tabla específica
        // filtros.push(`${tableName}/session_id ne ''`); // Filtro dummy para activar la tabla
    }
    
    // Filtro de métrica específica del sector
    if (params.metrica && sectorConfig && sectorConfig.fields.includes(params.metrica)) {
        // Solo filtrar si el campo tiene valor válido
        filtros.push(`${tableName}/${params.metrica} ne null`);
    }
    
    // Filtro temporal
    if (params.tiempo) {
        const fechaInicio = calcularFechaInicio(params.tiempo);
        filtros.push(`${tableName}/timestamp ge datetime'${fechaInicio}'`);
    }
    
    // Filtro de ubicación (solo para sectores que lo tienen)
    if (params.ubicacion && params.sector === 'energia') {
        // Solo ENERGIA_BI tiene campo ubicacion específico
        if (typeof params.ubicacion === 'string') {
            filtros.push(`${tableName}/ubicacion eq '${params.ubicacion}'`);
        }
    }
    
    // Agregar filtros a la URL
    if (filtros.length > 0) {
        url += "&filter=" + filtros.join("&filter=");
    }
    
    // Configuración de visualización
    url += "&pageView=fitToWidth&navContentPaneEnabled=false";
    
    return url;
}

function calcularFechaInicio(rango) {
    const ahora = new Date();
    let fecha = new Date(ahora);
    
    switch(rango) {
        case "24h":
            fecha.setHours(ahora.getHours() - 24);
            break;
        case "7d":
            fecha.setDate(ahora.getDate() - 7);
            break;
        case "30d":
            fecha.setDate(ahora.getDate() - 30);
            break;
        case "90d":
            fecha.setDate(ahora.getDate() - 90);
            break;
        case "365d":
            fecha.setFullYear(ahora.getFullYear() - 1);
            break;
    }
    
    return fecha.toISOString();
}

// 💬 GENERAR RESPUESTA CONTEXTUAL

function generarRespuestaContextual(params) {
    const tipoNombre = Object.keys(CHART_TYPES).find(key => CHART_TYPES[key] === params.tipo) || "gráfico";
    const metricaNombre = params.metrica || "datos";
    const sectorNombre = params.sector === "todos" ? "todos los sectores" : `sector ${params.sector}`;
    const tiempoNombre = TIME_RANGES_NAMES[params.tiempo] || "período seleccionado";
    
    const respuestas = [
        `✅ He generado un ${tipoNombre} de ${metricaNombre} para ${sectorNombre} en el ${tiempoNombre}.`,
        `📊 Aquí tienes el análisis de ${metricaNombre} para ${sectorNombre}. Los datos están actualizados.`,
        `🎯 Perfecto, te muestro los ${metricaNombre} de ${sectorNombre} con visualización ${tipoNombre}.`,
        `📈 El ${tipoNombre} está listo con datos de ${metricaNombre} para ${sectorNombre}.`
    ];
    
    const respuestaAleatoria = respuestas[Math.floor(Math.random() * respuestas.length)];
    
    return respuestaAleatoria + "\n\n[MOSTRAR_GRAFICO] Toca el botón de Power BI 📊 para ver el reporte interactivo.";
}

const TIME_RANGES_NAMES = {
    "24h": "últimas 24 horas",
    "7d": "última semana", 
    "30d": "último mes",
    "90d": "último trimestre",
    "365d": "último año"
};

// 🚀 EXPORTAR FUNCIÓN PRINCIPAL PARA N8N
// Esta función se debe llamar desde el Function Node de N8N

module.exports = {
    procesarPeticionGrafico,
    POWERBI_BASE_URL
};