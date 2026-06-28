// Fonction pour ouvrir/fermer le chat
function toggleChatWindow() {
    const windowChat = document.getElementById('yatout-chat-window');
    if (windowChat.style.display === 'none' || windowChat.style.display === '') {
        windowChat.style.display = 'flex';
        const box = document.getElementById('chat-messages-box');
        box.scrollTop = box.scrollHeight;
    } else {
        windowChat.style.display = 'none';
    }
}

// Fonction appelée par le bouton du header Impression
function openChatWithWhatsApp() {
    // 1. Ouvre la fenêtre de chat
    const windowChat = document.getElementById('yatout-chat-window');
    windowChat.style.display = 'flex';
    
    // 2. Ajoute un message automatique contenant le lien WhatsApp
    const box = document.getElementById('chat-messages-box');
    const whatsappDiv = document.createElement('div');
    whatsappDiv.className = "bot-message";
    
    // Remplacer par votre vrai numéro WhatsApp (ex: 212600000000)
    const numeroWhatsApp = "212600000000"; 
    const messageAuto = encodeURIComponent("Bonjour, je viens de l'espace impression YaTout et j'aimerais parler à un conseiller.");
    const lienWhatsApp = `https://wa.me{numeroWhatsApp}?text=${messageAuto}`;

    whatsappDiv.innerHTML = `Bonjour ! Cliquez ici pour discuter directement avec notre conseiller sur WhatsApp : <br><br> <a href="${lienWhatsApp}" target="_blank" style="color: #25d366; font-weight: bold; text-decoration: underline;">👉 Ouvrir WhatsApp</a>`;
    
    box.appendChild(whatsappDiv);
    box.scrollTop = box.scrollHeight;
}

// Fonction d'envoi du message à l'IA Django
function sendChatMessage() {
    const input = document.getElementById('chat-user-input');
    const message = input.value.trim();
    if (!message) return;

    const box = document.getElementById('chat-messages-box');
    
    // Ajouter le message du client à l'écran
    const clientDiv = document.createElement('div');
    clientDiv.className = "client-message";
    clientDiv.innerText = message;
    box.appendChild(clientDiv);
    
    input.value = '';
    box.scrollTop = box.scrollHeight;

    // Récupérer le jeton CSRF de Django
    let csrfToken = "";
    const cookieCookie = document.cookie.split(';').find(row => row.trim().startsWith('csrftoken='));
    if (cookieCookie) {
        csrfToken = cookieCookie.split('=')[1];
    }

    // Appel vers l'API Django
    fetch('/api/assistant/chat/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => {
        if (!response.ok) throw new Error("Erreur serveur");
        return response.json();
    })
    .then(data => {
        if (data.reponse) {
            const botDiv = document.createElement('div');
            botDiv.className = "bot-message";
            botDiv.innerText = data.reponse;
            box.appendChild(botDiv);
            box.scrollTop = box.scrollHeight;
        }
    })
    .catch(error => {
        const errorDiv = document.createElement('div');
        errorDiv.className = "error-message";
        errorDiv.innerText = "⚠️ Connexion interrompue avec l'assistant YaTout.";
        box.appendChild(errorDiv);
        box.scrollTop = box.scrollHeight;
    });
}