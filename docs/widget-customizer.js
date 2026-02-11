/**
 * Widget Customizer Module
 *
 * Handles Step 3 of the self-serve setup:
 * - Generates a themed widget via the backend (SSE streaming)
 * - Injects a live floating widget (button + chat window) for testing
 * - Provides compact customization inputs with a single Apply button
 * - Copy/View code and Integration Guide via modals
 */

// SVG icons matching the backend's WIDGET_ICONS
const WIDGET_ICONS = {
  chat: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>',
  robot: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M17.753 14a2.25 2.25 0 1 1 0 4.5 2.25 2.25 0 0 1 0-4.5zm-11.506 0a2.25 2.25 0 1 1 0 4.5 2.25 2.25 0 0 1 0-4.5zM12 1.5a2 2 0 0 1 2 2v.537A7.003 7.003 0 0 1 19 11v1h1.5a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H19v2a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-2H3.5a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1H5v-1a7.003 7.003 0 0 1 5-6.963V3.5a2 2 0 0 1 2-2z"/></svg>',
  help: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M11 18h2v-2h-2v2zm1-16C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-2.21 0-4 1.79-4 4h2c0-1.1.9-2 2-2s2 .9 2 2c0 2-3 1.75-3 5h2c0-2.25 3-2.5 3-5 0-2.21-1.79-4-4-4z"/></svg>',
  headset: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 1c-4.97 0-9 4.03-9 9v7c0 1.66 1.34 3 3 3h3v-8H5v-2c0-3.87 3.13-7 7-7s7 3.13 7 7v2h-4v8h3c1.66 0 3-1.34 3-3v-7c0-4.97-4.03-9-9-9z"/></svg>',
  sparkle: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61z"/></svg>',
};

export class WidgetCustomizerModule {
  constructor(config) {
    this.apiBase = config.apiBase;
    this.updateStatus = config.updateStatus;
    this.showError = config.showError;
    this.showSuccess = config.showSuccess;
    this.resetInactivityTimer = config.resetInactivityTimer;
    this.clearInactivityTimer = config.clearInactivityTimer;

    // State
    this.currentConfig = null;
    this.currentCode = null;
    this.currentGuide = null;
    this.namespace = null;
    this.widgetApiBase = null;
    this.websiteUrl = null;
    this.extractedTheme = null;
    this.liveConversationHistory = [];
    this.autoOpenTimer = null;

    // DOM elements
    this.elements = {
      section: document.getElementById('widget-section'),
      codeBlock: document.getElementById('widget-code-block'),
      copyBtn: document.getElementById('copy-code-btn'),
      viewCodeBtn: document.getElementById('view-code-btn'),
      viewGuideBtn: document.getElementById('view-guide-btn'),
      guideContent: document.getElementById('integration-guide-content'),
      actionsSection: document.getElementById('widget-actions'),
      // Customization inputs
      customText: document.getElementById('custom-widget-text'),
      customShape: document.getElementById('custom-widget-shape'),
      customIcon: document.getElementById('custom-widget-icon'),
      applyAllBtn: document.getElementById('apply-all-btn'),
      recolorBtn: document.getElementById('recolor-btn'),
      // Modals
      codeModal: document.getElementById('code-modal'),
      codeModalClose: document.getElementById('code-modal-close'),
      guideModal: document.getElementById('guide-modal'),
      guideModalClose: document.getElementById('guide-modal-close'),
      // Thinking indicator
      widgetThinking: document.getElementById('widget-thinking'),
      widgetThinkingText: document.getElementById('widget-thinking-text'),
    };

    this.init();
  }

  init() {
    // Copy code button
    if (this.elements.copyBtn) {
      this.elements.copyBtn.addEventListener('click', () => this.copyCode());
    }

    // View code button
    if (this.elements.viewCodeBtn) {
      this.elements.viewCodeBtn.addEventListener('click', () => this.openCodeModal());
    }

    // View guide button
    if (this.elements.viewGuideBtn) {
      this.elements.viewGuideBtn.addEventListener('click', () => this.openGuideModal());
    }

    // Modal close buttons
    if (this.elements.codeModalClose) {
      this.elements.codeModalClose.addEventListener('click', () => this.closeCodeModal());
    }
    if (this.elements.guideModalClose) {
      this.elements.guideModalClose.addEventListener('click', () => this.closeGuideModal());
    }

    // Close modals on overlay click
    if (this.elements.codeModal) {
      this.elements.codeModal.addEventListener('click', (e) => {
        if (e.target === this.elements.codeModal) this.closeCodeModal();
      });
    }
    if (this.elements.guideModal) {
      this.elements.guideModal.addEventListener('click', (e) => {
        if (e.target === this.elements.guideModal) this.closeGuideModal();
      });
    }

    // Single Apply button
    if (this.elements.applyAllBtn) {
      this.elements.applyAllBtn.addEventListener('click', () => this.applyAllCustomizations());
    }

    // Recolor button
    if (this.elements.recolorBtn) {
      this.elements.recolorBtn.addEventListener('click', () => this.recolorWidget());
    }

    // Enter key on any customization input
    const inputs = [this.elements.customText, this.elements.customShape, this.elements.customIcon];
    inputs.forEach(input => {
      if (input) {
        input.addEventListener('keypress', (e) => {
          if (e.key === 'Enter') this.applyAllCustomizations();
        });
      }
    });
  }

  // ========================================
  // Widget Generation (SSE Streaming)
  // ========================================

  async startGeneration(url, namespace, apiBase) {
    this.namespace = namespace;
    this.widgetApiBase = apiBase;
    this.websiteUrl = url;

    if (this.elements.section) {
      this.elements.section.classList.remove('hidden');
      this.elements.section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Hide customization UI and theme preview until widget is first rendered
    const customSection = document.getElementById('customization-section');
    if (customSection) customSection.classList.add('hidden');
    if (this.elements.actionsSection) this.elements.actionsSection.classList.add('hidden');
    const themePreview = document.getElementById('theme-preview');
    if (themePreview) themePreview.classList.add('hidden');

    this.showThinking('Analyzing website theme...');

    try {
      const response = await fetch(`${this.apiBase}/widget/generate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: url,
          namespace: namespace,
          api_base: apiBase,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              this.handleGenerateEvent(data);
            } catch (e) {
              console.error('Error parsing widget event:', e, line);
            }
          }
        }
      }
    } catch (error) {
      console.error('Widget generation error:', error);
      this.showError(`Failed to generate widget: ${error.message}`);
      this.hideThinking();
    }
  }

  handleGenerateEvent(data) {
    console.log('Widget event:', data);

    switch (data.type) {
      case 'status':
        this.showThinking(data.message);
        break;

      case 'theme':
        this.extractedTheme = data.colors;
        this.renderThemePreview(data.colors);
        this.showThinking('Theme colors extracted, generating widget...');
        break;

      case 'config':
        this.currentConfig = data.config;
        this.showThinking('Rendering widget code...');
        break;

      case 'complete':
        this.hideThinking();
        this.currentConfig = data.config;
        this.currentCode = data.code;
        this.currentGuide = data.guide;
        this.renderLiveWidget(data.config);
        this.updateCodeBlock(data.code);
        this.updateGuideContent(data.guide);
        this.showCustomizationInputs();
        this.showActionButtons();
        this.updatePlaceholders(data.config);
        this.showSuccess('Widget generated! Try it out using the floating button, or customize it further.');
        if (this.elements.actionsSection) {
          this.elements.actionsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        break;

      case 'error':
        this.hideThinking();
        this.showError(`Widget generation error: ${data.message}`);
        break;
    }
  }

  // ========================================
  // Extracted Theme Preview
  // ========================================

  renderThemePreview(colors) {
    const container = document.getElementById('theme-preview');
    const swatchesEl = document.getElementById('theme-swatches');
    const modeBadge = document.getElementById('theme-mode-badge');
    if (!container || !swatchesEl) return;

    const swatches = [
      { label: 'Background', color: colors.background_color },
      { label: 'Text', color: colors.text_color },
      { label: 'Accent', color: colors.accent_color },
      { label: 'Primary', color: colors.primary_color },
      { label: 'Secondary', color: colors.secondary_color },
    ];

    swatchesEl.innerHTML = swatches.map(s => `
      <div class="theme-swatch">
        <div class="theme-swatch-color" style="background: ${this.escapeHtml(s.color)};"></div>
        <div class="theme-swatch-info">
          <span class="theme-swatch-label">${s.label}</span>
          <span class="theme-swatch-value">${this.escapeHtml(s.color)}</span>
        </div>
      </div>
    `).join('');

    if (modeBadge) {
      const isDark = colors.is_dark;
      modeBadge.textContent = isDark ? 'Dark' : 'Light';
      modeBadge.className = `theme-preview-mode ${isDark ? 'dark' : 'light'}`;
    }

    container.classList.remove('hidden');
  }

  // ========================================
  // Live Widget (floating button + chat)
  // ========================================

  renderLiveWidget(config) {
    this.removeLiveWidget();

    const iconSvg = WIDGET_ICONS[config.button_icon] || WIDGET_ICONS.chat;
    const buttonRadius = this.getButtonRadius(config.button_shape);
    const buttonSizeCss = config.button_shape === 'circle'
      ? 'width: 60px !important; height: 60px !important; padding: 0 !important;'
      : 'width: auto !important; height: 60px !important; padding: 0 24px !important;';

    // Create style
    const style = document.createElement('style');
    style.id = 'live-widget-style';
    style.textContent = `
      #live-cw-btn {
        position: fixed !important;
        bottom: 20px !important;
        right: 20px !important;
        ${buttonSizeCss}
        border-radius: ${buttonRadius} !important;
        background: linear-gradient(135deg, ${config.primary_color} 0%, ${config.secondary_color} 100%) !important;
        border: none !important;
        cursor: pointer !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 12px !important;
        transition: transform 0.2s, box-shadow 0.2s !important;
        z-index: 99999 !important;
        color: white !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
      }
      #live-cw-btn.live-cw-hide { display: none !important; }
      #live-cw-btn:hover { transform: scale(1.05) !important; box-shadow: 0 6px 16px rgba(0,0,0,0.2) !important; }
      #live-cw-btn svg { width: 24px !important; height: 24px !important; fill: white !important; flex-shrink: 0 !important; }
      #live-cw-win {
        position: fixed !important;
        bottom: 20px !important;
        right: 20px !important;
        width: 450px !important;
        height: 600px !important;
        background: ${config.bg_color} !important;
        border-radius: 12px !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4) !important;
        border: 1px solid ${config.border_color} !important;
        display: none !important;
        flex-direction: column !important;
        z-index: 99999 !important;
        overflow: hidden !important;
      }
      #live-cw-win.live-cw-open { display: flex !important; animation: liveCwSlide 0.3s ease !important; }
      @keyframes liveCwSlide { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
      #live-cw-hdr {
        background: linear-gradient(135deg, ${config.primary_color} 0%, ${config.secondary_color} 100%) !important;
        color: white !important;
        padding: 16px 20px !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
      }
      #live-cw-hdr h3 { font-size: 16px !important; font-weight: 600 !important; margin: 0 !important; }
      #live-cw-hdr-actions { display: flex !important; gap: 12px !important; align-items: center !important; }
      #live-cw-clear {
        background: rgba(255,255,255,0.2) !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        color: white !important;
        font-size: 12px !important;
        padding: 6px 12px !important;
        border-radius: 16px !important;
        cursor: pointer !important;
        font-weight: 500 !important;
      }
      #live-cw-clear:hover { background: rgba(255,255,255,0.3) !important; }
      #live-cw-close {
        background: none !important;
        border: none !important;
        color: white !important;
        font-size: 24px !important;
        cursor: pointer !important;
        padding: 0 !important;
      }
      #live-cw-close:hover { transform: none !important; box-shadow: none !important; }
      #live-cw-msgs {
        flex: 1 !important;
        padding: 20px !important;
        overflow-y: auto !important;
        background: ${config.bg_color} !important;
      }
      .live-cw-msg { margin-bottom: 16px !important; animation: liveCwFade 0.3s ease !important; }
      @keyframes liveCwFade { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      .live-cw-msg.live-cw-usr { text-align: right !important; }
      .live-cw-msg-c {
        display: inline-block !important;
        padding: 12px 16px !important;
        border-radius: 18px !important;
        max-width: 85% !important;
        word-wrap: break-word !important;
        line-height: 1.5 !important;
      }
      .live-cw-msg.live-cw-usr .live-cw-msg-c {
        background: linear-gradient(135deg, ${config.primary_color} 0%, ${config.secondary_color} 100%) !important;
        color: ${config.user_msg_text_color} !important;
      }
      .live-cw-msg.live-cw-bot .live-cw-msg-c {
        background: ${config.bot_msg_bg_color} !important;
        color: ${config.bot_msg_text_color} !important;
        text-align: left !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
      }
      .live-cw-msg.live-cw-bot .live-cw-msg-c p { margin: 0 0 8px 0 !important; }
      .live-cw-msg.live-cw-bot .live-cw-msg-c p:last-child { margin-bottom: 0 !important; }
      .live-cw-msg.live-cw-bot .live-cw-msg-c code {
        background: ${config.border_color} !important;
        color: ${config.bot_msg_text_color} !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-family: 'Courier New', monospace !important;
        font-size: 0.9em !important;
      }
      .live-cw-msg.live-cw-bot .live-cw-msg-c pre {
        background: ${config.border_color} !important;
        padding: 12px !important;
        border-radius: 6px !important;
        overflow-x: auto !important;
        margin: 8px 0 !important;
      }
      .live-cw-msg.live-cw-bot .live-cw-msg-c ul,
      .live-cw-msg.live-cw-bot .live-cw-msg-c ol {
        margin: 8px 0 !important;
        padding-left: 20px !important;
      }
      .live-cw-think {
        display: inline-flex !important;
        gap: 6px !important;
        padding: 12px 16px !important;
        background: ${config.bot_msg_bg_color} !important;
        border-radius: 18px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
      }
      .live-cw-think span {
        display: inline-block !important;
        width: 8px !important;
        height: 8px !important;
        border-radius: 50% !important;
        background: ${config.primary_color} !important;
        animation: liveCwBounce 1.4s infinite ease-in-out !important;
      }
      .live-cw-think span:nth-child(1) { animation-delay: -0.32s !important; }
      .live-cw-think span:nth-child(2) { animation-delay: -0.16s !important; }
      @keyframes liveCwBounce { 0%,80%,100% { transform: scale(0); } 40% { transform: scale(1); } }
      #live-cw-inp-wrap {
        padding: 16px 20px !important;
        background: ${config.bg_color} !important;
        border-top: 1px solid ${config.border_color} !important;
        display: flex !important;
        gap: 10px !important;
        align-items: center !important;
      }
      #live-cw-inp {
        flex: 1 !important;
        padding: 10px 14px !important;
        border: 1px solid ${config.border_color} !important;
        border-radius: 20px !important;
        font-size: 14px !important;
        outline: none !important;
        background: ${config.input_bg_color} !important;
        color: ${config.input_text_color} !important;
        font-family: inherit !important;
      }
      #live-cw-inp::placeholder { color: ${config.input_placeholder_color} !important; }
      #live-cw-inp:focus { border-color: ${config.primary_color} !important; }
      #live-cw-send {
        width: 40px !important; min-width: 40px !important; height: 40px !important;
        border-radius: 50% !important;
        background: linear-gradient(135deg, ${config.primary_color} 0%, ${config.secondary_color} 100%) !important;
        border: none !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        flex-shrink: 0 !important;
        transition: transform 0.2s !important;
        padding: 0 !important;
      }
      #live-cw-send:hover { transform: scale(1.05) !important; box-shadow: none !important; }
      #live-cw-send:disabled { opacity: 0.5 !important; cursor: not-allowed !important; }
      #live-cw-send svg { width: 18px !important; height: 18px !important; fill: white !important; }
      @media (max-width: 480px) {
        #live-cw-win { width: calc(100% - 40px) !important; height: calc(100% - 120px) !important; }
      }
      @keyframes liveCwBtnEntry {
        0% { transform: translateY(0); }
        15% { transform: translateY(-80px); }
        30% { transform: translateY(0); }
        42% { transform: translateY(-35px); }
        55% { transform: translateY(0); }
        65% { transform: translateY(-15px); }
        75% { transform: translateY(0); }
        83% { transform: translateY(-5px); }
        90% { transform: translateY(0); }
        100% { transform: translateY(0); }
      }
      #live-cw-btn.live-cw-bounce {
        animation: liveCwBtnEntry 1.5s ease !important;
      }
    `;
    document.head.appendChild(style);

    // Button inner HTML
    let buttonInnerHtml;
    if (config.button_shape === 'circle') {
      buttonInnerHtml = iconSvg;
    } else {
      buttonInnerHtml = `<span>${this.escapeHtml(config.button_text)}</span>${iconSvg}`;
    }

    // Create button
    const btn = document.createElement('button');
    btn.id = 'live-cw-btn';
    btn.setAttribute('aria-label', 'Open chat');
    btn.innerHTML = buttonInnerHtml;
    document.body.appendChild(btn);
    btn.classList.add('live-cw-bounce');
    // Remove bounce class after animation completes so it doesn't replay on chat close
    btn.addEventListener('animationend', () => {
      btn.classList.remove('live-cw-bounce');
    }, { once: true });

    // Create chat window
    const win = document.createElement('div');
    win.id = 'live-cw-win';
    win.innerHTML = `
      <div id="live-cw-hdr">
        <h3>${this.escapeHtml(config.header_title)}</h3>
        <div id="live-cw-hdr-actions">
          <button id="live-cw-clear">Clear Chat</button>
          <button id="live-cw-close">&times;</button>
        </div>
      </div>
      <div id="live-cw-msgs"></div>
      <div id="live-cw-inp-wrap">
        <input type="text" id="live-cw-inp" placeholder="${this.escapeHtml(config.input_placeholder)}" />
        <button id="live-cw-send">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
      </div>
    `;
    document.body.appendChild(win);

    // Wire up events
    this.wireLiveWidgetEvents(config);

    // Auto-open chat window after bounce animation (1.5s) + settle time (1.5s)
    if (this.autoOpenTimer) {
      clearTimeout(this.autoOpenTimer);
    }
    this.autoOpenTimer = setTimeout(() => {
      const liveBtn = document.getElementById('live-cw-btn');
      const liveWin = document.getElementById('live-cw-win');
      if (liveBtn && liveWin && !liveWin.classList.contains('live-cw-open')) {
        liveBtn.click();
      }
      this.autoOpenTimer = null;
    }, 3000);
  }

  wireLiveWidgetEvents(config) {
    const btn = document.getElementById('live-cw-btn');
    const win = document.getElementById('live-cw-win');
    const closeBtn = document.getElementById('live-cw-close');
    const clearBtn = document.getElementById('live-cw-clear');
    const msgs = document.getElementById('live-cw-msgs');
    const inp = document.getElementById('live-cw-inp');
    const sendBtn = document.getElementById('live-cw-send');
    const self = this;

    function renderMd(text) {
      if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        return DOMPurify.sanitize(marked.parse(text));
      }
      return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function escHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    function addWelcome() {
      const m = document.createElement('div');
      m.className = 'live-cw-msg live-cw-bot';
      const welcomeText = `Hi! I'm your virtual assistant for **${self.namespace}**!\n\nI can answer questions about this website. Ask me anything!`;
      m.innerHTML = '<div class="live-cw-msg-c">' + renderMd(welcomeText) + '</div>';
      msgs.appendChild(m);
    }

    function fmtHistory() {
      if (!self.liveConversationHistory.length) return "";
      return self.liveConversationHistory.map(h => "User: " + h.u + "\nChatbot: " + h.b).join("\n\n");
    }

    function sendMsg() {
      const q = inp.value.trim();
      if (!q) return;

      const um = document.createElement('div');
      um.className = 'live-cw-msg live-cw-usr';
      um.innerHTML = '<div class="live-cw-msg-c">' + escHtml(q) + '</div>';
      msgs.appendChild(um);
      inp.value = '';
      sendBtn.disabled = true;

      const tm = document.createElement('div');
      tm.className = 'live-cw-msg live-cw-bot';
      tm.innerHTML = '<div class="live-cw-think"><span></span><span></span><span></span></div>';
      msgs.appendChild(tm);
      msgs.scrollTop = msgs.scrollHeight;

      fetch(self.widgetApiBase + '/chat', {
        method: 'POST',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, conv_history: fmtHistory(), namespace: self.namespace })
      })
      .then(r => { if (!r.ok) throw new Error('Network error'); return r.json(); })
      .then(data => {
        msgs.removeChild(tm);
        const bm = document.createElement('div');
        bm.className = 'live-cw-msg live-cw-bot';
        bm.innerHTML = '<div class="live-cw-msg-c">' + renderMd(data.answer) + '</div>';
        msgs.appendChild(bm);
        msgs.scrollTop = msgs.scrollHeight;
        self.liveConversationHistory.push({ u: q, b: data.answer });
      })
      .catch(() => {
        msgs.removeChild(tm);
        const em = document.createElement('div');
        em.className = 'live-cw-msg live-cw-bot';
        em.innerHTML = '<div class="live-cw-msg-c">Sorry, I encountered an error. Please try again.</div>';
        msgs.appendChild(em);
      })
      .finally(() => { sendBtn.disabled = false; inp.focus(); });
    }

    btn.addEventListener('click', () => {
      if (self.autoOpenTimer) {
        clearTimeout(self.autoOpenTimer);
        self.autoOpenTimer = null;
      }
      win.classList.add('live-cw-open');
      btn.classList.add('live-cw-hide');
      if (!msgs.children.length) addWelcome();
      inp.focus();
    });

    closeBtn.addEventListener('click', () => {
      win.classList.remove('live-cw-open');
      btn.classList.remove('live-cw-hide');
    });

    clearBtn.addEventListener('click', () => {
      self.liveConversationHistory = [];
      msgs.innerHTML = '';
      addWelcome();
    });

    sendBtn.addEventListener('click', sendMsg);
    inp.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendMsg();
    });
  }

  removeLiveWidget() {
    if (this.autoOpenTimer) {
      clearTimeout(this.autoOpenTimer);
      this.autoOpenTimer = null;
    }
    const style = document.getElementById('live-widget-style');
    const btn = document.getElementById('live-cw-btn');
    const win = document.getElementById('live-cw-win');
    if (style) style.remove();
    if (btn) btn.remove();
    if (win) win.remove();
  }

  // ========================================
  // Code Display & Modals
  // ========================================

  updateCodeBlock(code) {
    if (this.elements.codeBlock) {
      this.elements.codeBlock.textContent = code;
    }
  }

  openCodeModal() {
    if (this.elements.codeModal) {
      this.elements.codeModal.classList.remove('hidden');
    }
  }

  closeCodeModal() {
    if (this.elements.codeModal) {
      this.elements.codeModal.classList.add('hidden');
    }
  }

  async copyCode() {
    if (!this.currentCode) return;

    try {
      await navigator.clipboard.writeText(this.currentCode);
      const btn = this.elements.copyBtn;
      const originalText = btn.textContent;
      btn.textContent = 'Copied!';
      btn.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
      setTimeout(() => {
        btn.textContent = originalText;
        btn.style.background = '';
      }, 2000);
    } catch (err) {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = this.currentCode;
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);

      const btn = this.elements.copyBtn;
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = 'Copy Embed Code'; }, 2000);
    }
  }

  // ========================================
  // Integration Guide
  // ========================================

  updateGuideContent(guideText) {
    if (!this.elements.guideContent) return;

    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
      this.elements.guideContent.innerHTML = DOMPurify.sanitize(marked.parse(guideText));
    } else {
      this.elements.guideContent.textContent = guideText;
    }
  }

  openGuideModal() {
    if (this.elements.guideModal) {
      this.elements.guideModal.classList.remove('hidden');
    }
  }

  closeGuideModal() {
    if (this.elements.guideModal) {
      this.elements.guideModal.classList.add('hidden');
    }
  }

  // ========================================
  // Customization
  // ========================================

  showCustomizationInputs() {
    const customSection = document.getElementById('customization-section');
    if (customSection) {
      customSection.classList.remove('hidden');
    }
  }

  showActionButtons() {
    if (this.elements.actionsSection) {
      this.elements.actionsSection.classList.remove('hidden');
    }
  }

  updatePlaceholders(config) {
    if (this.elements.customText) {
      this.elements.customText.placeholder = config.button_text || 'Virtual Assistant';
    }
    if (this.elements.customShape) {
      this.elements.customShape.placeholder = config.button_shape || 'pill';
    }
    if (this.elements.customIcon) {
      this.elements.customIcon.placeholder = config.button_icon || 'chat';
    }
  }

  async applyAllCustomizations() {
    const textVal = this.elements.customText ? this.elements.customText.value.trim() : '';
    const shapeVal = this.elements.customShape ? this.elements.customShape.value.trim() : '';
    const iconVal = this.elements.customIcon ? this.elements.customIcon.value.trim() : '';

    if (!textVal && !shapeVal && !iconVal) {
      this.showError('Please enter at least one customization value');
      return;
    }

    if (!this.currentConfig) {
      this.showError('No widget to customize. Generate one first.');
      return;
    }

    // Build instruction from field values
    const parts = [];
    if (textVal) parts.push(`Change the button text to "${textVal}"`);
    if (shapeVal) parts.push(`Change the button shape to "${shapeVal}"`);
    if (iconVal) parts.push(`Change the button icon to "${iconVal}"`);
    const instruction = parts.join('. ') + '.';

    this.showThinking('Applying customizations...');
    this.setCustomizationButtonsEnabled(false);

    try {
      const response = await fetch(`${this.apiBase}/widget/customize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: this.currentConfig,
          instruction: instruction,
          namespace: this.namespace,
          api_base: this.widgetApiBase,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error ${response.status}`);
      }

      const data = await response.json();
      this.currentConfig = data.config;
      this.currentCode = data.code;

      this.renderLiveWidget(data.config);
      this.updateCodeBlock(data.code);
      this.updatePlaceholders(data.config);
      this.hideThinking();

      // Clear inputs after successful apply
      if (this.elements.customText) this.elements.customText.value = '';
      if (this.elements.customShape) this.elements.customShape.value = '';
      if (this.elements.customIcon) this.elements.customIcon.value = '';

      this.showSuccess('Widget customized successfully!');
    } catch (error) {
      console.error('Customization error:', error);
      this.hideThinking();
      this.showError(`Customization failed: ${error.message}`);
    } finally {
      this.setCustomizationButtonsEnabled(true);
    }
  }

  // ========================================
  // Recolor Widget
  // ========================================

  async recolorWidget() {
    if (!this.currentConfig) {
      this.showError('No widget to recolor. Generate one first.');
      return;
    }

    this.showThinking('Generating new color scheme...');
    this.setCustomizationButtonsEnabled(false);

    try {
      const response = await fetch(`${this.apiBase}/widget/recolor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: this.currentConfig,
          url: this.websiteUrl,
          namespace: this.namespace,
          api_base: this.widgetApiBase,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error ${response.status}`);
      }

      const data = await response.json();
      this.currentConfig = data.config;
      this.currentCode = data.code;

      this.renderLiveWidget(data.config);
      this.updateCodeBlock(data.code);
      this.updatePlaceholders(data.config);
      this.hideThinking();

      this.showSuccess('Widget colors updated!');
    } catch (error) {
      console.error('Recolor error:', error);
      this.hideThinking();
      this.showError(`Recolor failed: ${error.message}`);
    } finally {
      this.setCustomizationButtonsEnabled(true);
    }
  }

  // ========================================
  // Thinking / Status Indicators
  // ========================================

  showThinking(message) {
    if (this.elements.widgetThinking) {
      this.elements.widgetThinking.classList.remove('hidden');
    }
    if (this.elements.widgetThinkingText) {
      this.elements.widgetThinkingText.textContent = message;
    }
  }

  hideThinking() {
    if (this.elements.widgetThinking) {
      this.elements.widgetThinking.classList.add('hidden');
    }
  }

  setCustomizationButtonsEnabled(enabled) {
    if (this.elements.applyAllBtn) this.elements.applyAllBtn.disabled = !enabled;
    if (this.elements.recolorBtn) this.elements.recolorBtn.disabled = !enabled;
  }

  // ========================================
  // Utility
  // ========================================

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  getButtonRadius(shape) {
    switch (shape) {
      case 'circle': return '50%';
      case 'rounded-square': return '12px';
      default: return '30px'; // pill
    }
  }
}
