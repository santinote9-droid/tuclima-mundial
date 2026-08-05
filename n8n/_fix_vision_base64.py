"""Fix Preparar_Vision to read imageBase64 / binary data00 (not only imageUrl)."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "chatbot_tuclima.json"
c = json.loads(p.read_text(encoding="utf-8"))

VISION_JS = r"""
// PREPARAR_VISION — imagen desde binary data00, imageBase64 o imageUrl
const item = $input.first() || {};
const prev = item.json || {};
const body = prev.body || prev || {};
const chatInput = String(body.chatInput || body.text || prev.chatInput || '');

let base64 = body.imageBase64 || body.image_base64 || prev.imageBase64 || null;
let mimeType = body.imageMimeType || body.image_mime_type || prev.imageMimeType || 'image/jpeg';
const imageUrl = body.imageUrl || body.image_url || prev.imageUrl || null;
const hasFlag = String(body.hasImage || prev.hasImage || '') === '1' || body.hasImage === true;

// Binary del webhook (campo data00)
const bin = (item.binary && (item.binary.data00 || item.binary.data0 || item.binary.data)) || null;
if (!base64 && bin && bin.data) {
  base64 = bin.data; // n8n ya lo trae en base64
  mimeType = bin.mimeType || mimeType;
}

const hasImage = !!(base64 || imageUrl || (hasFlag && bin));

if (!hasImage) {
  // Sin imagen: pasar el item tal cual al Merge
  return [{ json: prev, binary: item.binary }];
}

let apiKey = '';
try { apiKey = process.env.GOOGLE_API_KEY || process.env.GOOGLE_GEMINI_API_KEY || ''; } catch (e) {}
if (!apiKey) { try { apiKey = $vars['GOOGLE_API_KEY'] || ''; } catch (e) {} }

let imageAnalysis = '';

async function analyzeInline(b64, mime) {
  const visionResp = await this.helpers.httpRequest({
    method: 'POST',
    url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + apiKey,
    headers: { 'Content-Type': 'application/json' },
    body: {
      contents: [{
        parts: [
          {
            text: 'Sos experto en meteorologia, aviacion, navegacion y agronomia. Analiza la imagen con detalle tecnico. Identifica: tipo de nubes, radar/mapa, cultivo, paneles, etc. Contexto del usuario: ' + chatInput
          },
          { inline_data: { mime_type: mime, data: b64 } }
        ]
      }],
      generationConfig: { temperature: 0.1, maxOutputTokens: 2000 }
    },
    json: true
  });
  return visionResp?.candidates?.[0]?.content?.parts?.[0]?.text
    || visionResp?.candidates?.[0]?.content?.parts?.map(p => p.text).filter(Boolean).join('\n')
    || 'No se pudo extraer analisis visual.';
}

try {
  if (!apiKey) {
    imageAnalysis = 'Imagen recibida pero falta GOOGLE_API_KEY en n8n. El agente debe indicar que vio un adjunto y pedir reintento.';
  } else if (base64) {
    // Quitar prefijo data:image/...;base64, si viniera
    const clean = String(base64).replace(/^data:[^;]+;base64,/, '');
    mimeType = String(mimeType || 'image/jpeg').split(';')[0];
    // helpers.httpRequest en Code node
    const visionResp = await this.helpers.httpRequest({
      method: 'POST',
      url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + apiKey,
      headers: { 'Content-Type': 'application/json' },
      body: {
        contents: [{
          parts: [
            {
              text: 'Sos experto en meteorologia, aviacion, navegacion y agronomia. Analiza la imagen con detalle tecnico (tipo de nubes, radar, cultivo, energia). Contexto: ' + chatInput
            },
            { inline_data: { mime_type: mimeType, data: clean } }
          ]
        }],
        generationConfig: { temperature: 0.1, maxOutputTokens: 2000 }
      },
      json: true
    });
    imageAnalysis = visionResp?.candidates?.[0]?.content?.parts?.[0]?.text
      || visionResp?.candidates?.[0]?.content?.parts?.map(p => p.text).filter(Boolean).join('\n')
      || 'No se pudo extraer analisis visual.';
  } else if (imageUrl) {
    const imgResp = await this.helpers.httpRequest({
      method: 'GET',
      url: imageUrl,
      encoding: 'arraybuffer',
      returnFullResponse: true
    });
    const b64 = Buffer.from(imgResp.body).toString('base64');
    mimeType = ((imgResp.headers['content-type'] || mimeType) + '').split(';')[0];
    const visionResp = await this.helpers.httpRequest({
      method: 'POST',
      url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + apiKey,
      headers: { 'Content-Type': 'application/json' },
      body: {
        contents: [{
          parts: [
            { text: 'Analiza esta imagen con detalle tecnico. Contexto: ' + chatInput },
            { inline_data: { mime_type: mimeType, data: b64 } }
          ]
        }],
        generationConfig: { temperature: 0.1, maxOutputTokens: 2000 }
      },
      json: true
    });
    imageAnalysis = visionResp?.candidates?.[0]?.content?.parts?.[0]?.text || 'No se pudo extraer analisis.';
  }
} catch (err) {
  imageAnalysis = 'Error al procesar imagen: ' + (err.message || String(err));
}

const enrichedChat = '[ANALISIS VISUAL — VISION IA]\n' + imageAnalysis + '\n\n---\nConsulta: ' + chatInput;

return [{
  json: {
    ...prev,
    chatInput: enrichedChat,
    imageAnalysis,
    hasImage: true,
    imageMimeType: mimeType,
    body: {
      ...(typeof body === 'object' && body ? body : {}),
      chatInput: enrichedChat,
      imageAnalysis,
      hasImage: true,
      imageMimeType: mimeType,
      // no reenviar base64 enorme al Agent
      imageBase64: undefined
    }
  },
  binary: item.binary || {}
}];
""".strip()

# n8n Code node v2 uses $helpers or this.helpers - older used $http.request
# Looking at original: await $http.request - that might be their custom. In n8n 2.x Code it's often:
# await this.helpers.httpRequest(...)
# But original used $http.request which works in some setups.

# Safer: use same $http.request as original for compatibility on their Railway
VISION_JS = r"""
// PREPARAR_VISION — soporta binary data00, imageBase64 y imageUrl
const item = $input.first() || {};
const prev = item.json || {};
const body = prev.body || prev || {};
const chatInput = String(body.chatInput || body.text || prev.chatInput || '');

let base64 = body.imageBase64 || body.image_base64 || prev.imageBase64 || null;
let mimeType = String(body.imageMimeType || body.image_mime_type || prev.imageMimeType || 'image/jpeg').split(';')[0];
const imageUrl = body.imageUrl || body.image_url || prev.imageUrl || null;
const hasFlag = String(body.hasImage || prev.hasImage || '') === '1' || body.hasImage === true;

const bin = (item.binary && (item.binary.data00 || item.binary.data0 || item.binary.data)) || null;
if (!base64 && bin && bin.data) {
  base64 = bin.data;
  mimeType = (bin.mimeType || mimeType).split(';')[0];
}

const hasImage = !!(base64 || imageUrl);

if (!hasImage) {
  return [{ json: prev, binary: item.binary }];
}

let apiKey = '';
try { apiKey = process.env.GOOGLE_API_KEY || process.env.GOOGLE_GEMINI_API_KEY || ''; } catch (e) {}
if (!apiKey) { try { apiKey = $vars['GOOGLE_API_KEY'] || ''; } catch (e) {} }

let imageAnalysis = '';

async function httpReq(opts) {
  if (typeof $http !== 'undefined' && $http.request) return $http.request(opts);
  if (typeof this !== 'undefined' && this.helpers && this.helpers.httpRequest) return this.helpers.httpRequest(opts);
  throw new Error('No hay cliente HTTP disponible en el Code node');
}

try {
  if (!apiKey) {
    imageAnalysis = 'Imagen recibida en el servidor, pero falta GOOGLE_API_KEY en n8n (Railway Variables).';
  } else {
    if (!base64 && imageUrl) {
      const imgResp = await httpReq({
        method: 'GET', url: imageUrl, encoding: 'arraybuffer', returnFullResponse: true
      });
      base64 = Buffer.from(imgResp.body).toString('base64');
      mimeType = ((imgResp.headers && imgResp.headers['content-type']) || mimeType).split(';')[0];
    }
    base64 = String(base64 || '').replace(/^data:[^;]+;base64,/, '');
    if (!base64) throw new Error('No hay bytes de imagen (base64 vacio)');

    const visionResp = await httpReq({
      method: 'POST',
      url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + apiKey,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{
          parts: [
            {
              text: 'Sos experto en meteorologia, aviacion, navegacion y agronomia. Analiza la imagen con detalle tecnico (tipo de nubes, radar, cultivo, energia, etc). Contexto del usuario: ' + chatInput
            },
            { inlineData: { mimeType: mimeType || 'image/jpeg', data: base64 } }
          ]
        }],
        generationConfig: { temperature: 0.1, maxOutputTokens: 2000 }
      })
    });
    const parsed = typeof visionResp === 'string' ? JSON.parse(visionResp) : visionResp;
    imageAnalysis = parsed?.candidates?.[0]?.content?.parts?.[0]?.text
      || (parsed?.candidates?.[0]?.content?.parts || []).map(p => p.text).filter(Boolean).join('\n')
      || 'No se pudo extraer analisis visual.';
  }
} catch (err) {
  imageAnalysis = 'Error al procesar imagen: ' + (err.message || String(err));
}

const enrichedChat = '[ANALISIS VISUAL — VISION IA]\n' + imageAnalysis + '\n\n---\nConsulta: ' + chatInput;

return [{
  json: {
    ...prev,
    chatInput: enrichedChat,
    imageAnalysis: imageAnalysis,
    hasImage: true,
    imageMimeType: mimeType,
    body: Object.assign({}, (typeof body === 'object' && body) ? body : {}, {
      chatInput: enrichedChat,
      imageAnalysis: imageAnalysis,
      hasImage: true,
      imageMimeType: mimeType,
      imageBase64: undefined
    })
  },
  binary: item.binary || {}
}];
""".strip()

for n in c["nodes"]:
    if n.get("name") == "Preparar_Vision":
        n["parameters"]["jsCode"] = VISION_JS
        print("Preparar_Vision updated")
    if n.get("name") == "AI Agent":
        text = n["parameters"].get("text") or ""
        # Ensure VISION reads from merged fields
        old = "{{ $json.imageAnalysis ? '\\n[VISION]\\n' + String($json.imageAnalysis).substring(0, 4000) : '' }}"
        new = "{{ ($json.imageAnalysis || $json.body?.imageAnalysis) ? '\\n[VISION]\\n' + String($json.imageAnalysis || $json.body.imageAnalysis).substring(0, 4000) : '' }}"
        if old in text:
            text = text.replace(old, new, 1)
            print("AI Agent VISION expression updated")
        elif "imageAnalysis || $json.body" in text:
            print("AI Agent VISION already patched")
        else:
            # try looser replace
            import re
            text2, nsub = re.subn(
                r"\{\{\s*\$json\.imageAnalysis \?[^}]+\}\}",
                new,
                text,
                count=1,
            )
            if nsub:
                text = text2
                print("AI Agent VISION regex updated")
            else:
                print("WARN: could not patch Agent VISION expr")
        # Prefer enriched chatInput from Merge when present
        old_chat = "{{ $('Webhook').item.json.body.chatInput }}"
        new_chat = "{{ $json.chatInput || $json.body?.chatInput || $('Webhook').item.json.body.chatInput }}"
        if old_chat in text and " $json.chatInput ||" not in text:
            text = text.replace(old_chat, new_chat, 1)
            print("AI Agent chatInput prefers vision-enriched")
        n["parameters"]["text"] = text

p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("saved")
