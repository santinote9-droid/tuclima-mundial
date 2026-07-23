import requests
from datetime import datetime

# Coordenadas Martín Coronado, Buenos Aires
LAT = -34.5792
LON = -58.5942

print("=" * 55)
print("COMPARACIÓN DE FUENTES - Martín Coronado, Buenos Aires")
print("=" * 55)

# ── 1. OPEN-METEO ──────────────────────────────────────────
url_om = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
    f"wind_speed_10m,surface_pressure,visibility,precipitation"
    f"&timezone=auto"
)
om = requests.get(url_om, timeout=8).json()
cur = om["current"]
print("\n[Open-Meteo]")
print(f"  Temperatura:     {cur['temperature_2m']} °C")
print(f"  Sensación:       {cur['apparent_temperature']} °C")
print(f"  Humedad:         {cur['relative_humidity_2m']} %")
print(f"  Viento:          {cur['wind_speed_10m']} km/h")
print(f"  Presión:         {cur['surface_pressure']} hPa")
print(f"  Visibilidad:     {cur['visibility']} m = {cur['visibility']/1000:.1f} km")
print(f"  Precipitación:   {cur['precipitation']} mm")
print(f"  Hora dato:       {cur['time']}")

# ── 2. SMN — buscar estación más cercana ───────────────────
smn = requests.get("https://ws.smn.gob.ar/map_items/weather", timeout=8).json()

# Calcular distancia simple (no requiere haversine para comparar)
def dist2(e):
    dlat = float(e["lat"]) - LAT
    dlon = float(e["lon"]) - LON
    return dlat*dlat + dlon*dlon

closest = sorted(smn, key=dist2)[:5]

print("\n[SMN] — 5 estaciones más cercanas:")
for e in closest:
    ts = e.get("updated", 0)
    dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    w = e["weather"]
    dist_km = (dist2(e)**0.5) * 111  # aprox km
    print(f"\n  Estación: {e['name']} ({e['province']}) — ~{dist_km:.0f} km")
    print(f"  Actualizado: {dt}")
    print(f"  Temp: {w.get('temp')} °C | ST: {w.get('st')} | Humedad: {w.get('humidity')}%")
    print(f"  Viento: {w.get('wind_speed')} km/h {w.get('wing_deg')} | Presión: {w.get('pressure')} hPa")
    print(f"  Visibilidad: {w.get('visibility')} km | Desc: {w.get('description')}")

# ── 3. Diferencia resumen ──────────────────────────────────
smn0 = closest[0]
ts0 = smn0.get("updated", 0)
horas_viejos = (datetime.now().timestamp() - ts0) / 3600
print(f"\n[Resumen]")
print(f"  Open-Meteo temp: {cur['temperature_2m']} °C (datos de hace minutos)")
print(f"  SMN estación más cercana ({smn0['name']}): {smn0['weather'].get('temp')} °C")
print(f"  SMN datos de hace: {horas_viejos:.0f} horas ← ojo con esto")
