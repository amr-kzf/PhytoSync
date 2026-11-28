// Chatbot Logic
const chatbotToggle = document.getElementById('chatbot-toggle');
const chatbotWindow = document.getElementById('chatbot-window');
const chatbotCloseBtn = document.getElementById('chatbot-close-btn');
const chatbotExpandBtn = document.getElementById('chatbot-expand-btn');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatMessages = document.getElementById('chat-messages');

let isOpen = false;

function openChatbot() {
    isOpen = true;
    chatbotWindow.classList.remove('hidden');
    chatbotWindow.classList.add('flex');
    chatbotToggle.setAttribute('aria-expanded', 'true');
    chatbotToggle.setAttribute('aria-label', 'Close AI farming assistant');
    chatbotToggle.innerHTML = `<i data-lucide="x" class="w-6 h-6"></i>`;
    if (typeof lucide !== 'undefined') lucide.createIcons();
    chatInput?.focus();
}

function closeChatbot() {
    isOpen = false;
    chatbotWindow.classList.remove('flex');
    chatbotWindow.classList.add('hidden');
    chatbotToggle.setAttribute('aria-expanded', 'false');
    chatbotToggle.setAttribute('aria-label', 'Open AI farming assistant');
    chatbotWindow.classList.remove('chatbot-expanded');
    chatbotExpandBtn?.setAttribute('aria-pressed', 'false');
    chatbotExpandBtn?.setAttribute('aria-label', 'Expand chat');
    if (chatbotExpandBtn) {
        chatbotExpandBtn.title = 'Expand chat';
        chatbotExpandBtn.innerHTML = '<i data-lucide="maximize-2" class="w-5 h-5"></i>';
    }
    chatbotToggle.innerHTML = `<i data-lucide="sparkles" class="w-6 h-6 group-hover:rotate-12 transition-transform"></i>`;
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

// Toggle Chatbot Window
chatbotToggle?.addEventListener('click', () => {
    if (isOpen) {
        closeChatbot();
    } else {
        openChatbot();
    }
});

chatbotCloseBtn?.addEventListener('click', () => {
    closeChatbot();
});

chatbotExpandBtn?.addEventListener('click', () => {
    const isExpanded = chatbotWindow.classList.toggle('chatbot-expanded');
    chatbotExpandBtn.setAttribute('aria-pressed', String(isExpanded));
    chatbotExpandBtn.setAttribute('aria-label', isExpanded ? 'Restore chat size' : 'Expand chat');
    chatbotExpandBtn.title = isExpanded ? 'Restore chat size' : 'Expand chat';
    chatbotExpandBtn.innerHTML = `<i data-lucide="${isExpanded ? 'minimize-2' : 'maximize-2'}" class="w-5 h-5"></i>`;
    if (typeof lucide !== 'undefined') lucide.createIcons();
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && isOpen) closeChatbot();
});

// Append Message to UI
function appendMessage(text, type) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `flex items-end gap-2 max-w-full min-w-0 ${type === 'user' ? 'justify-end' : 'justify-start'}`;

    if (type === 'user') {
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble-content bg-primary text-white p-3 rounded-2xl rounded-br-none max-w-[85%] text-sm leading-relaxed shadow-sm min-w-0 break-words';
        bubble.innerHTML = text;
        msgDiv.appendChild(bubble);
    } else {
        const iconDiv = document.createElement('div');
        iconDiv.className = 'w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0';
        iconDiv.innerHTML = '<i data-lucide="bot" class="w-3.5 h-3.5 text-emerald-600"></i>';

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble-content bg-white border border-gray-100 shadow-sm p-3 rounded-2xl rounded-bl-none max-w-[85%] text-sm text-gray-700 leading-relaxed min-w-0 break-words';
        bubble.innerHTML = text;

        msgDiv.appendChild(iconDiv);
        msgDiv.appendChild(bubble);
    }

    chatMessages.appendChild(msgDiv);
    if (typeof lucide !== 'undefined') lucide.createIcons();
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Show Typing Indicator
function showTypingIndicator() {
    const indicatorDiv = document.createElement('div');
    indicatorDiv.id = 'bot-typing-indicator';
    indicatorDiv.className = 'flex items-end gap-2 justify-start max-w-full min-w-0';
    indicatorDiv.innerHTML = `
        <div class="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
            <i data-lucide="bot" class="w-3.5 h-3.5 text-emerald-600"></i>
        </div>
        <div class="bg-white border border-gray-100 shadow-sm px-4 py-3 rounded-2xl rounded-bl-none max-w-[85%] text-sm text-gray-400 flex items-center gap-1.5">
            <span class="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"></span>
            <span class="w-2 h-2 bg-emerald-500 rounded-full animate-bounce [animation-delay:0.2s]"></span>
            <span class="w-2 h-2 bg-emerald-500 rounded-full animate-bounce [animation-delay:0.4s]"></span>
        </div>
    `;
    chatMessages.appendChild(indicatorDiv);
    if (typeof lucide !== 'undefined') lucide.createIcons();
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Hide Typing Indicator
function hideTypingIndicator() {
    const indicator = document.getElementById('bot-typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Send Message Logic
async function handleSend() {
    const questionText = chatInput.value.trim();
    if (!questionText) return;

    // Add User Message (escaped plain text)
    const userMessageDiv = document.createElement('div');
    userMessageDiv.textContent = questionText;
    appendMessage(userMessageDiv.innerHTML, 'user');
    chatInput.value = '';

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Show Typing Indicator
    showTypingIndicator();

    let response;
    try {
        response = await fetch('/chatbot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question: questionText })
        });
    } catch (err) {
        hideTypingIndicator();
        appendMessage("Can't reach PhytoSync. Make sure the Flask server is running, then try again.", "bot");
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return;
    }

    hideTypingIndicator();

    let data;
    try {
        data = await response.json();
    } catch (err) {
        appendMessage(`PhytoSync returned an unexpected response (HTTP ${response.status}). Check the server terminal for errors.`, 'bot');
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return;
    }

    if (response.ok) {
        const chatMode = document.getElementById('chat-mode');
        if (chatMode) {
            chatMode.textContent = data.mode === 'groq'
                ? 'Powered by Groq'
                : 'Offline farming guide · add GROQ_API_KEY for AI answers';
        }
        const rawMarkdown = data.response || "No response received.";
        let safeHTML = rawMarkdown;
        if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
            safeHTML = marked.parse(rawMarkdown);
        }
        if (typeof DOMPurify !== 'undefined') {
            safeHTML = DOMPurify.sanitize(safeHTML);
        }

        appendMessage(safeHTML, 'bot');
    } else {
        appendMessage(data.error || `PhytoSync AI couldn't respond (HTTP ${response.status}). Please try again.`, "bot");
    }

    // Scroll to Bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Event Listeners for Sending
chatSend?.addEventListener('click', handleSend);
chatInput?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSend();
});

if (typeof lucide !== 'undefined') lucide.createIcons();
