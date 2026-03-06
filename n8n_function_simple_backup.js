// 🛡️ FUNCIÓN N8N SIMPLIFICADA Y ROBUSTA
// Para usar en caso de problemas con la versión profesional

try {
  console.log('=== FUNCTION NODE START ===');
  
  // Obtener datos usando sintaxis n8n correcta
  const inputData = $input.first()?.json || {};
  console.log('Input data:', JSON.stringify(inputData, null, 2));
  
  // Extraer datos básicos
  const webhookData = inputData.body || inputData;
  const chatInput = webhookData.chatInput || webhookData.mensaje || "";
  const sessionId = webhookData.sessionId || `session-${Date.now()}`;
  
  console.log('Chat input:', chatInput);
  console.log('Session ID:', sessionId);
  
  // Extraer respuesta de IA (puede venir de diferentes fuentes)
  let aiResponse = "";
  
  if (inputData.choices && inputData.choices[0]) {
    // OpenAI format
    aiResponse = inputData.choices[0].message?.content || "";
  } else if (inputData.candidates && inputData.candidates[0]) {
    // Gemini format
    aiResponse = inputData.candidates[0].content?.parts?.[0]?.text || "";
  } else if (inputData.content) {
    // Direct AI response
    aiResponse = inputData.content;
  }
  
  console.log('AI Response length:', aiResponse.length);
  
  // Detección simple de sector
  let sector = "GENERAL";
  if (/puerto|naval|mar/i.test(chatInput)) sector = "NAVAL";
  else if (/energia|solar|electric/i.test(chatInput)) sector = "ENERGIA";
  else if (/agro|cultivo|campo/i.test(chatInput)) sector = "AGRO";
  else if (/aereo|vuelo|avion/i.test(chatInput)) sector = "AEREO";
  
  console.log('Detected sector:', sector);
  
  // Extraer números básicos
  const extractNumber = (text, regex) => {
    const match = text.match(regex);
    return match ? parseFloat(match[1]) : null;
  };
  
  // Crear datos de salida
  const outputData = {
    timestamp: new Date().toISOString(),
    session_id: sessionId,
    sector: sector,
    chat_input: chatInput.substring(0, 1000),
    ai_response: aiResponse.substring(0, 3000),
    location: null,
    puerto: sector === "NAVAL" ? "Puerto detectado" : null,
    viento_velocidad: extractNumber(chatInput, /viento[^0-9]*([0-9.]+)/i),
    altura_olas: extractNumber(chatInput, /olas[^0-9]*([0-9.]+)/i),
    temperatura: extractNumber(chatInput, /temperatura[^0-9]*([0-9.]+)/i),
    temperatura_agua: extractNumber(chatInput, /agua[^0-9]*([0-9.]+)/i),
    humedad: extractNumber(chatInput, /humedad[^0-9]*([0-9.]+)/i),
    presion: extractNumber(chatInput, /presion[^0-9]*([0-9.]+)/i),
    visibilidad: extractNumber(chatInput, /visibilidad[^0-9]*([0-9.]+)/i),
    metadata: JSON.stringify({
      version: "simple_v1",
      timestamp: Date.now(),
      input_length: chatInput.length,
      ai_length: aiResponse.length
    })
  };
  
  console.log('Output data created successfully');
  console.log('=== FUNCTION NODE END ===');
  
  return outputData;
  
} catch (error) {
  console.error('=== FUNCTION NODE ERROR ===');
  console.error('Error:', error.message);
  console.error('Stack:', error.stack);
  
  return {
    timestamp: new Date().toISOString(),
    session_id: `error-${Date.now()}`,
    sector: "ERROR",
    chat_input: "Error en Function Node",
    ai_response: `Error: ${error.message}`,
    location: null,
    metadata: JSON.stringify({
      error: true,
      message: error.message,
      timestamp: Date.now()
    })
  };
}