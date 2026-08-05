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

const _helpers = (typeof this !== 'undefined' && this.helpers) ? this.helpers : null;
async function httpReq(opts) {
  if (typeof $http !== 'undefined' && $http.request) return $http.request(opts);
  if (_helpers && _helpers.httpRequest) return _helpers.httpRequest(opts);
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