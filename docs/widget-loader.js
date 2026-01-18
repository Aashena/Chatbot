// widget-loader.js
// This file dynamically loads the chat widget with custom namespace

function loadChatWidget(customNamespace, apiBase) {
  // Configure marked.js
  if (typeof marked !== 'undefined') {
    marked.setOptions({
      breaks: true,
      gfm: true,
      headerIds: false,
      mangle: false
    });
  }

  let conversationHistory = [];
  let hasInitialHiBeenSent = false;
  
  // Create widget styles with higher specificity
  const style = document.createElement('style');
  style.textContent = `
    #chat-widget-button {
      position: fixed !important;
      bottom: 20px !important;
      right: 20px !important;
      width: auto !important;
      height: 60px !important;
      padding: 0 24px !important;
      border-radius: 30px !important;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
      border: none !important;
      cursor: pointer !important;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      gap: 12px !important;
      transition: transform 0.2s, box-shadow 0.2s !important;
      z-index: 99999 !important;
      color: white !important;
      font-size: 16px !important;
      font-weight: 600 !important;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif !important;
    }
    #chat-widget-button.chat-hidden { display: none !important; }
    #chat-widget-button:hover {
      transform: scale(1.05) !important;
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2) !important;
    }
    #chat-widget-button svg {
      width: 24px !important;
      height: 24px !important;
      fill: white !important;
      flex-shrink: 0 !important;
    }
    #chat-widget-window {
      position: fixed !important;
      bottom: 20px !important;
      right: 20px !important;
      width: 450px !important;
      height: 600px !important;
      background: white !important;
      border-radius: 12px !important;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12) !important;
      display: none !important;
      flex-direction: column !important;
      z-index: 99999 !important;
      overflow: hidden !important;
    }
    #chat-widget-window.chat-open {
      display: flex !important;
      animation: chatSlideUp 0.3s ease !important;
    }
    @keyframes chatSlideUp {
      from { opacity: 0; transform: translateY(20px); }
      to { opacity: 1; transform: translateY(0); }
    }
    #chat-widget-header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
      color: white !important;
      padding: 16px 20px !important;
      display: flex !important;
      justify-content: space-between !important;
      align-items: center !important;
    }
    #chat-widget-header h3 {
      font-size: 16px !important;
      font-weight: 600 !important;
      margin: 0 !important;
    }
    #chat-widget-header-actions {
      display: flex !important;
      gap: 12px !important;
      align-items: center !important;
    }
    #chat-widget-clear {
      background: rgba(255, 255, 255, 0.2) !important;
      border: 1px solid rgba(255, 255, 255, 0.3) !important;
      color: white !important;
      font-size: 12px !important;
      padding: 6px 12px !important;
      border-radius: 16px !important;
      cursor: pointer !important;
      transition: background 0.2s !important;
      font-weight: 500 !important;
    }
    #chat-widget-clear:hover {
      background: rgba(255, 255, 255, 0.3) !important;
    }
    #chat-widget-close {
      background: none !important;
      border: none !important;
      color: white !important;
      font-size: 24px !important;
      cursor: pointer !important;
      padding: 0 !important;
      width: 24px !important;
      height: 24px !important;
      line-height: 1 !important;
    }
    #chat-widget-content {
      flex: 1 !important;
      padding: 20px !important;
      overflow-y: auto !important;
      background: #f7f8fa !important;
    }
    .chat-message {
      margin-bottom: 16px !important;
      animation: chatFadeIn 0.3s ease !important;
    }
    @keyframes chatFadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .chat-message.chat-user { text-align: right !important; }
    .chat-message-content {
      display: inline-block !important;
      padding: 12px 16px !important;
      border-radius: 18px !important;
      max-width: 85% !important;
      word-wrap: break-word !important;
      line-height: 1.5 !important;
    }
    .chat-message.chat-user .chat-message-content {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
      color: white !important;
    }
    .chat-message.chat-bot .chat-message-content {
      background: white !important;
      color: #333 !important;
      text-align: left !important;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }
    .chat-message.chat-bot .chat-message-content p {
      margin: 0 0 8px 0 !important;
    }
    .chat-message.chat-bot .chat-message-content p:last-child {
      margin-bottom: 0 !important;
    }
    .chat-message.chat-bot .chat-message-content code {
      background: #f3f4f6 !important;
      padding: 2px 6px !important;
      border-radius: 4px !important;
      font-family: 'Courier New', monospace !important;
      font-size: 0.9em !important;
    }
    .chat-message.chat-bot .chat-message-content pre {
      background: #f3f4f6 !important;
      padding: 12px !important;
      border-radius: 6px !important;
      overflow-x: auto !important;
      margin: 8px 0 !important;
    }
    .chat-message.chat-bot .chat-message-content ul,
    .chat-message.chat-bot .chat-message-content ol {
      margin: 8px 0 !important;
      padding-left: 20px !important;
    }
    .chat-thinking {
      display: inline-flex !important;
      gap: 6px !important;
      padding: 12px 16px !important;
      background: white !important;
      border-radius: 18px !important;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }
    .chat-thinking span {
      display: inline-block !important;
      width: 8px !important;
      height: 8px !important;
      border-radius: 50% !important;
      background: #667eea !important;
      animation: chatBounce 1.4s infinite ease-in-out !important;
    }
    .chat-thinking span:nth-child(1) { animation-delay: -0.32s !important; }
    .chat-thinking span:nth-child(2) { animation-delay: -0.16s !important; }
    @keyframes chatBounce {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }
    #chat-widget-input-container {
      padding: 16px 20px !important;
      background: white !important;
      border-top: 1px solid #e5e7eb !important;
      display: flex !important;
      gap: 10px !important;
      align-items: center !important;
    }
    #chat-widget-input {
      flex: 1 !important;
      padding: 10px 14px !important;
      border: 1px solid #e5e7eb !important;
      border-radius: 20px !important;
      font-size: 14px !important;
      outline: none !important;
      font-family: inherit !important;
    }
    #chat-widget-input:focus {
      border-color: #667eea !important;
    }
    
    /* CRITICAL: Send button styling - must be perfectly circular */
    button#chat-widget-send {
      width: 40px !important;
      min-width: 40px !important;
      max-width: 40px !important;
      height: 40px !important;
      min-height: 40px !important;
      max-height: 40px !important;
      padding: 0 !important;
      margin: 0 !important;
      border-radius: 50% !important;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
      background-color: #667eea !important;
      border: none !important;
      cursor: pointer !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      transition: transform 0.2s !important;
      flex-shrink: 0 !important;
      box-sizing: border-box !important;
      overflow: visible !important;
    }
    button#chat-widget-send:hover { 
      transform: scale(1.05) !important; 
    }
    button#chat-widget-send:disabled {
      opacity: 0.5 !important;
      cursor: not-allowed !important;
      transform: none !important;
    }
    button#chat-widget-send svg {
      width: 18px !important;
      height: 18px !important;
      min-width: 18px !important;
      min-height: 18px !important;
      fill: white !important;
      display: block !important;
      pointer-events: none !important;
    }
    button#chat-widget-send svg path {
      fill: white !important;
    }
    
    @media (max-width: 480px) {
      #chat-widget-window {
        width: calc(100% - 40px) !important;
        height: calc(100% - 120px) !important;
      }
    }
  `;
  document.head.appendChild(style);

  // Create chat button
  const chatButton = document.createElement('button');
  chatButton.id = 'chat-widget-button';
  chatButton.setAttribute('aria-label', 'Open chat');
  chatButton.innerHTML = '<span>Virtual Assistant</span><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>';
  document.body.appendChild(chatButton);

  // Create chat window
  const chatWindow = document.createElement('div');
  chatWindow.id = 'chat-widget-window';
  chatWindow.innerHTML = `
    <div id="chat-widget-header">
      <h3>Chat Assistant</h3>
      <div id="chat-widget-header-actions">
        <button id="chat-widget-clear" aria-label="Clear chat history">Clear Chat</button>
        <button id="chat-widget-close" aria-label="Close chat">&times;</button>
      </div>
    </div>
    <div id="chat-widget-content"></div>
    <div id="chat-widget-input-container">
      <input type="text" id="chat-widget-input" placeholder="Ask a question..." aria-label="Chat input">
      <button id="chat-widget-send" aria-label="Send message">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
      </button>
    </div>
  `;
  document.body.appendChild(chatWindow);

  // Get DOM elements
  const closeButton = document.getElementById('chat-widget-close');
  const clearButton = document.getElementById('chat-widget-clear');
  const chatContent = document.getElementById('chat-widget-content');
  const chatInput = document.getElementById('chat-widget-input');
  const sendButton = document.getElementById('chat-widget-send');

  // Apply inline styles as backup to ensure button is circular
  sendButton.style.cssText = `
    width: 40px !important;
    height: 40px !important;
    min-width: 40px !important;
    min-height: 40px !important;
    max-width: 40px !important;
    max-height: 40px !important;
    border-radius: 50% !important;
    padding: 0 !important;
    margin: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    border: none !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
  `;

  // Helper functions
  function renderMarkdown(text) {
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
      const htmlContent = marked.parse(text);
      return DOMPurify.sanitize(htmlContent);
    }
    return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function addWelcomeMessage() {
    const welcomeMessage = document.createElement('div');
    welcomeMessage.className = 'chat-message chat-bot';
    const welcomeText = `Hi! I'm your custom chatbot for **${customNamespace}**!\n\nI can answer questions about this website. Ask me anything!`;
    welcomeMessage.innerHTML = '<div class="chat-message-content">' + renderMarkdown(welcomeText) + '</div>';
    chatContent.appendChild(welcomeMessage);
  }

  function formatConversationHistory() {
    if (conversationHistory.length === 0) return "";
    let formatted = "";
    for (let i = 0; i < conversationHistory.length; i++) {
      formatted += "User: " + conversationHistory[i].user + "\nChatbot: " + conversationHistory[i].bot;
      if (i < conversationHistory.length - 1) formatted += "\n\n";
    }
    return formatted;
  }

  function sendMessage() {
    const question = chatInput.value.trim();
    if (!question) return;

    const userMessage = document.createElement('div');
    userMessage.className = 'chat-message chat-user';
    userMessage.innerHTML = '<div class="chat-message-content">' + escapeHtml(question) + '</div>';
    chatContent.appendChild(userMessage);

    chatInput.value = '';
    sendButton.disabled = true;

    const thinkingMessage = document.createElement('div');
    thinkingMessage.className = 'chat-message chat-bot';
    thinkingMessage.innerHTML = '<div class="chat-thinking"><span></span><span></span><span></span></div>';
    chatContent.appendChild(thinkingMessage);
    chatContent.scrollTop = chatContent.scrollHeight;

    const convHistory = formatConversationHistory();

    fetch(`${apiBase}/chat`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        question: question,
        conv_history: convHistory,
        namespace: customNamespace
      })
    })
    .then(response => {
      if (!response.ok) throw new Error('Network response was not ok');
      return response.json();
    })
    .then(data => {
      chatContent.removeChild(thinkingMessage);
      
      const botMessage = document.createElement('div');
      botMessage.className = 'chat-message chat-bot';
      botMessage.innerHTML = '<div class="chat-message-content">' + renderMarkdown(data.answer) + '</div>';
      chatContent.appendChild(botMessage);
      chatContent.scrollTop = chatContent.scrollHeight;

      conversationHistory.push({
        user: question,
        bot: data.answer
      });
    })
    .catch(error => {
      chatContent.removeChild(thinkingMessage);
      const errorMessage = document.createElement('div');
      errorMessage.className = 'chat-message chat-bot';
      errorMessage.innerHTML = '<div class="chat-message-content">Sorry, I encountered an error. Please try again.</div>';
      chatContent.appendChild(errorMessage);
      console.error('Error:', error);
    })
    .finally(() => {
      sendButton.disabled = false;
      chatInput.focus();
    });
  }

  // Event listeners
  chatButton.addEventListener('click', () => {
    chatWindow.classList.add('chat-open');
    chatButton.classList.add('chat-hidden');
    if (chatContent.children.length === 0) {
      addWelcomeMessage();
    }
    chatInput.focus();
  });

  closeButton.addEventListener('click', () => {
    chatWindow.classList.remove('chat-open');
    chatButton.classList.remove('chat-hidden');
  });

  clearButton.addEventListener('click', () => {
    conversationHistory = [];
    hasInitialHiBeenSent = false;
    chatContent.innerHTML = '';
    addWelcomeMessage();
  });

  sendButton.addEventListener('click', sendMessage);
  chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  // Auto-open the widget to show it's ready
  setTimeout(() => {
    chatButton.click();
  }, 500);

  console.log(`Chat widget loaded successfully for namespace: ${customNamespace}`);
}