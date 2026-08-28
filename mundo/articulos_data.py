"""Artículos públicos originales — contenido editorial para SEO / AdSense."""

SECTOR_LABELS = {
    'agro': 'Agro',
    'aereo': 'Aéreo',
    'naval': 'Naval',
    'energia': 'Energía',
}

# Cada artículo: slug único, sector, título, resumen, fecha ISO, cuerpo (lista de párrafos / subtítulos)
ARTICULOS = [
    {
        'slug': 'ventana-de-pulverizacion-y-viento-en-superficie',
        'sector': 'agro',
        'titulo': 'Ventana de pulverización: qué mirar en viento y estabilidad',
        'resumen': (
            'Cómo combinar viento a 10 m, rachas y estabilidad atmosférica para reducir '
            'deriva y elegir una ventana operativa más segura en el lote.'
        ),
        'fecha': '2026-08-20',
        'lectura_min': 6,
        'cuerpo': [
            ('h2', 'Por qué el “solo viento” no alcanza'),
            ('p',
             'En agricultura de precisión, la decisión de pulverizar suele reducirse a '
             '“¿hay mucho viento?”. En la práctica importan tres capas: la velocidad media '
             'a 10 metros, las rachas (gust) y el perfil de estabilidad. Un día con 12 km/h '
             'de media pero rachas de 30 km/h no es la misma ventana que un flujo estable '
             'y sostenido.'),
            ('p',
             'La deriva de gotas aumenta cuando el viento superficial es alto y cuando hay '
             'mezcla turbulenta fuerte. Inversiones térmicas bajas también complican: el '
             'producto puede quedar “atrapado” cerca del suelo o comportarse de forma poco '
             'predecible respecto al modelo mental del operador.'),
            ('h2', 'Qué variables conviene cruzar'),
            ('p',
             'Una checklist operativa mínima incluye: viento medio y máximo previsto en las '
             'próximas 6–12 h, dirección predominante respecto a linderos sensibles, '
             'humedad relativa (evaporación de gota), temperatura y probabilidad de lluvia '
             'corta. Si usás índices de operabilidad en TuClima, tomalos como apoyo '
             'informativo: no reemplazan el criterio agronómico ni la etiqueta del producto.'),
            ('p',
             'Cuando el lote está cerca de escuelas, cursos de agua o viviendas, conviene '
             'endurecer el umbral: menos velocidad máxima aceptada y más margen horario. '
             'Documentar la ventana elegida (hora, viento observado, motivo) ayuda al '
             'asesoramiento y a la trazabilidad interna del grupo.'),
            ('h2', 'Cómo usar TuClima en este caso'),
            ('p',
             'En el modo Agro podés anclar el punto del lote, mirar la tendencia de viento '
             'y cruzarla con otras variables de superficie. La idea no es automatizar la '
             'pulverización, sino acortar el tiempo entre “abrir cinco apps” y “tener un '
             'criterio común para el equipo”.'),
            ('p',
             'Recordá contrastar con estaciones locales y con el protocolo de tu cooperativa '
             'o CREA. Los modelos globales suavizan fenómenos de microescala; tu observación '
             'en el campo sigue siendo la última palabra.'),
        ],
    },
    {
        'slug': 'spi-y-sequia-agricola-leer-el-indice-sin-confundirse',
        'sector': 'agro',
        'titulo': 'SPI y sequía agrícola: cómo leer el índice sin confundirse',
        'resumen': (
            'El SPI resume anomalías de precipitación. Sirve para contexto de sequía, '
            'pero no mide humedad de suelo ni stress del cultivo por sí solo.'
        ),
        'fecha': '2026-08-18',
        'lectura_min': 7,
        'cuerpo': [
            ('h2', 'Qué es el SPI (en una frase)'),
            ('p',
             'El Standardized Precipitation Index compara la lluvia acumulada en una '
             'ventana (1, 3, 6, 12 meses, etc.) contra la climatología del lugar. Valores '
             'negativos indican déficit relativo; positivos, exceso. Es un lenguaje común '
             'entre asesores, pero no es un sensor de raíz.'),
            ('h2', 'Errores frecuentes'),
            ('p',
             'Primero: confundir SPI-1 con “sequía de campaña”. Un mes seco no define una '
             'sequía agrícola si el perfil de suelo venía cargado. Segundo: comparar SPI '
             'entre regiones con climatologías distintas sin mirar la escala temporal. '
             'Tercero: usar solo el índice y olvidar ETo, reservas y fenología.'),
            ('p',
             'Para decisiones de siembra o riego, el SPI aporta contexto de “cómo venimos '
             'de lluvia”, mientras que balances hídricos, humedad de suelo y pronóstico '
             'corto responden “qué pasa esta semana en el lote”.'),
            ('h2', 'Uso práctico con TuClima'),
            ('p',
             'En paneles de climatología del modo Agro podés ubicar el SPI/SPEI junto a '
             'anomalías y series. Usalo para alinear al equipo (“estamos en déficit de '
             '3 meses”) y después bajá a la escala operativa del pronóstico diario. '
             'Siempre como información de apoyo, no como única fuente.'),
        ],
    },
    {
        'slug': 'briefing-vfr-ifr-cape-shear-para-escuelas-de-vuelo',
        'sector': 'aereo',
        'titulo': 'Briefing VFR/IFR: CAPE, shear y qué mirar antes de volar instrucción',
        'resumen': (
            'Una guía corta para instructores y alumnos: inestabilidad (CAPE), '
            'cizalladura y techos, sin reemplazar METAR/TAF ni el criterio del piloto.'
        ),
        'fecha': '2026-08-21',
        'lectura_min': 7,
        'cuerpo': [
            ('h2', 'El briefing no empieza en el modelo global'),
            ('p',
             'En escuelas de vuelo el orden sano suele ser: NOTAMs y estado del aeródromo, '
             'METAR/TAF oficiales, luego capas de análisis (sondeo, CAPE, shear, viento en '
             'altura). TuClima puede ayudar en esa segunda capa, pero no sustituye fuentes '
             'aeronáuticas oficiales ni el juicio del instructor.'),
            ('h2', 'CAPE y convección'),
            ('p',
             'CAPE alto sugiere energía disponible para ascensos. No implica “va a haber '
             'tormenta encima de la pista”, pero sí eleva la atención sobre células, '
             'visibilidad y posible actividad eléctrica. Combinarlo con CIN, humedad en '
             'capas medias y forzado sinóptico evita sobrerreaccionar a un solo número.'),
            ('h2', 'Shear y fase de alumno'),
            ('p',
             'La cizalladura vertical importa en despegue/aterrizaje y en lecciones de '
             'tráfico. Un alumno en fase inicial necesita márgenes más amplios: menos '
             'rachas, mejor techo y visibilidad, y un plan B claro. El shear en altura '
             'también anticipa turbulencia en crucero corto.'),
            ('p',
             'Si usás el modo Aéreo de TuClima, tomá los paneles como apoyo didáctico para '
             'discutir el día con el alumno: “¿qué dice el perfil de viento?”, “¿dónde está '
             'la inestabilidad?”. La decisión final de salir o no sigue siendo operativa '
             'y normativa, no automática.'),
        ],
    },
    {
        'slug': 'ondas-de-montana-y-froude-cuando-el-relieve-manda',
        'sector': 'aereo',
        'titulo': 'Ondas de montaña y Froude: cuándo el relieve manda sobre el modelo',
        'resumen': (
            'El número de Froude ayuda a intuir si el flujo va a “pasar” el obstáculo '
            'o generar ondas y rotor. Útil cerca de cordillera y sierras.'
        ),
        'fecha': '2026-08-16',
        'lectura_min': 6,
        'cuerpo': [
            ('h2', 'Relieve + viento estable = escenario especial'),
            ('p',
             'Cuando un flujo estable choca con una cadena montañosa, pueden aparecer '
             'ondas de montaña, rotor y cizalladura intensa a sotavento. No siempre el '
             'modelo de superficie lo muestra con claridad en un mapa simple de viento.'),
            ('h2', 'Qué aporta Froude (sin fórmula de pizarra)'),
            ('p',
             'En términos operativos, Froude bajo sugiere más bloqueo / ondas; Froude alto, '
             'flujo que “supera” el obstáculo con menos respuesta ondulatoria. Es una '
             'heurística: depende de la estabilidad, la velocidad y la altura efectiva del '
             'relieve. Por eso conviene cruzarlo con el perfil vertical y reportes locales.'),
            ('p',
             'Para aviación general y planeadores, el mensaje es de precaución: planificar '
             'márgenes, conocer rutas de escape y no tratar un índice como semáforo único. '
             'TuClima puede mostrar paneles de dinámica; tu briefing oficial y la experiencia '
             'en la zona cierran la decisión.'),
        ],
    },
    {
        'slug': 'oleaje-viento-y-ventana-de-navegacion-costera',
        'sector': 'naval',
        'titulo': 'Oleaje, viento y ventana de navegación costera',
        'resumen': (
            'Cómo combinar altura significativa, período y viento para decidir si una '
            'salida costera es razonable — siempre como apoyo, no como carta náutica.'
        ),
        'fecha': '2026-08-19',
        'lectura_min': 6,
        'cuerpo': [
            ('h2', 'Altura no es lo único'),
            ('p',
             'Una Hs (altura significativa) de 1,5 m con período corto se siente distinto '
             'a la misma Hs con período largo. El período habla de la energía y del '
             'comportamiento de la embarcación. Sumá dirección del oleaje respecto al '
             'rumbo y la exposición de la costa.'),
            ('h2', 'Viento local vs. estado de mar'),
            ('p',
             'El viento puede “levantar” mar en pocas horas o, al contrario, aliviar un '
             'swell previo. Por eso la ventana no es solo el mapa de oleaje a las 12:00: '
             'es la evolución 24–48 h y el cruce con rachas. En desembocaduras y canales, '
             'corrientes y bajofondo cambian el riesgo aunque el modelo “se vea bien”.'),
            ('p',
             'Usá el modo Naval de TuClima para anticipar tendencias y discutir el plan '
             'con la tripulación. La decisión final debe incluir cartas, avisos oficiales, '
             'estado de la embarcación y experiencia del patrón.'),
        ],
    },
    {
        'slug': 'mar-de-fondo-y-mar-de-viento-no-son-lo-mismo',
        'sector': 'naval',
        'titulo': 'Mar de fondo y mar de viento: no son lo mismo',
        'resumen': (
            'Distinguir swell (fondo) de wind sea evita malas lecturas del parte y '
            'mejora la conversación operativa a bordo.'
        ),
        'fecha': '2026-08-14',
        'lectura_min': 5,
        'cuerpo': [
            ('h2', 'Dos componentes, una sensación en cubierta'),
            ('p',
             'El mar de viento se genera localmente y responde rápido al forzante. El mar '
             'de fondo viaja desde lejos: puede llegar con viento local flojo y aun así '
             'mover la embarcación. Mezclar ambos en una sola frase (“hay 2 metros”) '
             'esconde el tipo de riesgo.'),
            ('h2', 'Lectura práctica'),
            ('p',
             'Si el parte muestra swell largo desde el sur y viento NE flojo, el escenario '
             'no es “calma”. Si hay wind sea cruzado sobre swell, la cubierta se vuelve '
             'más impredecible. Anotá dirección, período y altura por componente cuando '
             'el modelo lo permita.'),
            ('p',
             'En TuClima, los paneles navales buscan acercar esa lectura sin pedirte cinco '
             'sitios distintos. Seguís necesitando criterio náutico y fuentes oficiales.'),
        ],
    },
    {
        'slug': 'ghi-claridad-y-estimacion-solar-sin-sobreprometer',
        'sector': 'energia',
        'titulo': 'GHI, claridad y estimación solar sin sobreprometer',
        'resumen': (
            'Irradiancia global horizontal y clearness index ayudan a dimensionar '
            'expectativas de generación; no reemplazan un estudio de recurso certificado.'
        ),
        'fecha': '2026-08-22',
        'lectura_min': 6,
        'cuerpo': [
            ('h2', 'Qué es GHI en lenguaje de planta'),
            ('p',
             'La irradiancia global horizontal (GHI) resume la energía solar que llega a '
             'una superficie plana. Es la base de muchas estimaciones de generación FV, '
             'junto con temperatura de módulo, inclinación/azimut y pérdidas del sistema.'),
            ('h2', 'Índice de claridad'),
            ('p',
             'El clearness index compara la GHI observada/pronosticada con la irradiancia '
             'extraterrestre esperable ese día. Valores bajos indican cielo opaco (nubes, '
             'aerosoles). Sirve para explicar por qué “hoy el sol está alto pero generamos '
             'poco”.'),
            ('p',
             'Para O&M y trading intradiario, un pronóstico de GHI con incertidumbre es '
             'más útil que un número único. TuClima modo Energía puede apoyar esa mirada '
             'operativa; un banco o un PPA exigirán estudios de recurso y normas propias.'),
        ],
    },
    {
        'slug': 'viento-para-eolica-cortes-y-umbrales-operativos',
        'sector': 'energia',
        'titulo': 'Viento para eólica: cortes, umbrales y operación diaria',
        'resumen': (
            'Entre el cut-in y el cut-out hay una curva de potencia. El pronóstico de '
            'viento ayuda a anticipar rampas y paradas, no a certificar el parque.'
        ),
        'fecha': '2026-08-12',
        'lectura_min': 6,
        'cuerpo': [
            ('h2', 'La curva importa más que el promedio'),
            ('p',
             'Un promedio diario de 7 m/s puede esconder horas bajo cut-in y otras cerca '
             'de cut-out. Para despacho y mantenimiento, mirá la distribución horaria, '
             'rachas y dirección (estelas, sector restringido).'),
            ('h2', 'Rampas y seguridad'),
            ('p',
             'Frentes y líneas de inestabilidad generan rampas rápidas. Anticiparlas '
             'permite ajustar expectativas de generación y planificar intervenciones. '
             'El personal en torre necesita además umbrales de seguridad propios del OEM.'),
            ('p',
             'Usá el modo Energía / paneles de viento de TuClima como capa informativa '
             'junto a SCADA y pronósticos del operador del sistema. Nunca como única '
             'fuente para decisiones de seguridad o contratos.'),
        ],
    },
]


def get_articulo(slug: str):
    for art in ARTICULOS:
        if art['slug'] == slug:
            return art
    return None


def listar_articulos(sector=None):
    items = ARTICULOS
    if sector:
        items = [a for a in ARTICULOS if a['sector'] == sector]
    return sorted(items, key=lambda a: a['fecha'], reverse=True)


def articulos_por_sector():
    out = {k: [] for k in SECTOR_LABELS}
    for art in listar_articulos():
        out[art['sector']].append(art)
    return out
