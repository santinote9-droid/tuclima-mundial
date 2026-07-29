"""Fix aereo_BI Function + prompt brackets; fix energia_BI prompt brackets."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

AEREO_FN = r"""const inputData = $input.first().json;
const texto_bruto = inputData.output || inputData.text || "";

const extraerTexto = (campo, fallback) => {
    const regex = new RegExp(`${campo}[:\\s]+([^\\n]+)`, 'i');
    const match = texto_bruto.match(regex);
    return match ? match[1].trim() : fallback;
};

// Primer número de una lista "a, b, c" para columnas escalares en BigQuery
const extraerPrimerNumero = (campo, fallback) => {
    const texto = extraerTexto(campo, "");
    if (!texto) return fallback;
    const primerNumero = texto.split(',')[0].trim();
    const n = parseFloat(primerNumero.replace(',', '.'));
    return Number.isFinite(n) ? n : fallback;
};

const reporte_limpio = texto_bruto.replace(/\[MOSTRAR_GRAFICO\][\s\S]*/i, "").trim();

// Aeropuertos por separado (BigQuery espera columnas distintas)
const aeropuerto_origen = extraerTexto("aeropuerto_origen", "Origen no especificado");
const aeropuerto_destino = extraerTexto("aeropuerto_destino", "Destino no especificado");

// corrientes_viento debe ser objeto JSON (no un número suelto)
const velocidadViento = extraerPrimerNumero("corrientes_viento", extraerPrimerNumero("viento_velocidad", 0));
const direccionViento = extraerPrimerNumero("viento_direccion", null);
const altitudRef = extraerPrimerNumero("altitud_vuelo", 10000);
const corrientes_viento = {
    velocidad: velocidadViento,
    direccion: (direccionViento !== null && Number.isFinite(direccionViento))
        ? direccionViento
        : "variable",
    altitud: altitudRef
};

return [{
    json: {
        timestamp: new Date().toISOString(),
        session_id: inputData.session_id || `aereo-${Date.now()}`,
        sector: "AEREO",

        aeropuerto_origen,
        aeropuerto_destino,
        altitud_vuelo: altitudRef,
        temperatura_altitud: extraerPrimerNumero("temperatura_altitud", 15),
        corrientes_viento,
        visibilidad_km: extraerPrimerNumero("visibilidad_km", 10),
        condiciones_atmosfericas: extraerTexto("condiciones_atmosfericas", "Sin datos"),
        ai_flight_analysis: reporte_limpio,
        metadata: JSON.stringify({ status: "success" }),

        // Chart.js / front sigue usando el bloque completo
        output: texto_bruto
    }
}];
"""


def fix_bracket_examples(text: str) -> str:
    """Replace [Ej: ...] wrappers with bare comma-separated examples."""
    # [Ej: 3500, 7000, 8500, 10000] -> 3500, 7000, 8500, 10000
    text = re.sub(r"\[Ej:\s*([^\]]+)\]", r"\1", text)
    # chart_type: [line / bar] -> chart_type: line
    text = re.sub(
        r"chart_type:\s*\[line\s*/\s*bar\]",
        "chart_type: line",
        text,
        flags=re.I,
    )
    # tipo_energia: [Solar / Eólica / Híbrida] -> tipo_energia: Solar
    text = re.sub(
        r"tipo_energia:\s*\[[^\]]+\]",
        "tipo_energia: Solar",
        text,
        flags=re.I,
    )
    # ubicacion: [Nombre de la región] -> ubicacion: Patagonia
    text = re.sub(
        r"ubicacion:\s*\[Nombre[^\]]*\]",
        "ubicacion: Patagonia",
        text,
        flags=re.I,
    )
    # Ensure anti-bracket rule exists near MOSTRAR_GRAFICO rules
    if "NO USES CORCHETES" not in text and "[MOSTRAR_GRAFICO]" in text:
        text = text.replace(
            'imprimir literalmente la palabra "[MOSTRAR_GRAFICO]"',
            'imprimir literalmente la palabra "[MOSTRAR_GRAFICO]"',
        )
        # Insert rule after line about nueva línea if present
        needle = "Cada variable DEBE ir en una NUEVA LÍNEA"
        if needle in text and "NO USES CORCHETES" not in text:
            text = text.replace(
                needle,
                needle
                + "\n3. Escribe solo números/etiquetas separados por comas. "
                "¡NO USES CORCHETES [] ALREDEDOR DE LOS NÚMEROS NI EN LOS EJEMPLOS!",
            )
        elif "REGLAS ABSOLUTAS:" in text and "NO USES CORCHETES" not in text:
            text = text.replace(
                "REGLAS ABSOLUTAS:",
                "REGLAS ABSOLUTAS:\n"
                "- Escribe solo números/etiquetas separados por comas. "
                "¡NO USES CORCHETES [] ALREDEDOR DE LOS VALORES!",
            )
    # Strengthen existing rule if present
    text = text.replace(
        "¡NO USES CORCHETES `[]` ALREDEDOR DE LOS NÚMEROS!",
        "¡NO USES CORCHETES [] ALREDEDOR DE LOS NÚMEROS! "
        "Los ejemplos también van SIN corchetes (ej: 800, 950, 1000).",
    )
    return text


def patch_file(fname: str, *, fix_fn: bool = False):
    path = ROOT / fname
    data = json.loads(path.read_text(encoding="utf-8"))
    for n in data["nodes"]:
        if fix_fn and n.get("name") == "Function":
            n["parameters"]["jsCode"] = AEREO_FN
            print(f"{fname}: Function fixed")
        if n.get("name") == "Basic LLM Chain":
            old = n["parameters"].get("text", "")
            new = fix_bracket_examples(old)
            if new != old:
                n["parameters"]["text"] = new
                print(f"{fname}: prompt brackets cleaned")
            else:
                print(f"{fname}: prompt unchanged?")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


patch_file("aereo_BI.json", fix_fn=True)
patch_file("energia_BI.json", fix_fn=False)

# verify
for f in ("aereo_BI.json", "energia_BI.json"):
    d = json.loads((ROOT / f).read_text(encoding="utf-8"))
    for n in d["nodes"]:
        if n.get("name") == "Function" and f.startswith("aereo"):
            code = n["parameters"]["jsCode"]
            assert "aeropuerto_origen" in code and "aeropuerto_destino" in code
            assert "region:" not in code or "aeropuerto_origen" in code
            assert "ai_flight_analysis" in code
            assert "velocidad:" in code
            print("aereo Function OK")
        if n.get("name") == "Basic LLM Chain":
            t = n["parameters"]["text"]
            leftover = re.findall(r"\[Ej:[^\]]+\]", t)
            print(f, "leftover [Ej:]", leftover[:3], "NO USES", "NO USES CORCHETES" in t)
