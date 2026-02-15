async function enviarMensaje() {
    const input = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const texto = input.value;

    if (texto === "") return;

    // 1. Mostrar mensaje del usuario en pantalla
    chatBox.innerHTML += `<div class="message user-msg">${texto}</div>`;
    input.value = ""; // Limpiar input
    chatBox.scrollTop = chatBox.scrollHeight; // Bajar scroll

    // 2. Enviar a n8n
    try {
        // 👇 PEGA AQUÍ TU URL DEL WEBHOOK (Production URL recomendada)
        const urlN8N = "http://localhost:5678/webhook/chat"; 

        const respuesta = await fetch(urlN8N, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "x-api-key": "santino_seguridad_99" // La contraseña que pusimos
            },
            body: JSON.stringify({ chatInput: texto })
        });

        const datos = await respuesta.json();

        // 3. Mostrar respuesta de la IA
        const respuestaIA = datos.output || "No entendí, pero recibí algo.";
        chatBox.innerHTML += `<div class="message bot-msg">${respuestaIA}</div>`;

    } catch (error) {
        console.error("Error:", error);
        chatBox.innerHTML += `<div class="message bot-msg" style="color:red;">Error al conectar con el servidor.</div>`;
    }
    
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Permitir enviar con la tecla Enter
document.getElementById("user-input").addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        enviarMensaje();
    }
});