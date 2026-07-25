/**
 * Floating AI tourist guide chat widget, injected into every page (loaded
 * after i18n.js). Conversation history lives only in memory (page reload
 * resets it) - no server-side session, matching the stateless pattern used
 * by the rest of this frontend. Every request sends the current language
 * (fr/en/ar) so backend/chat_agent.py replies and is grounded in the same
 * language the tourist is browsing in.
 */

let chatHistory = [];
let chatWelcomed = false;
let chatSending = false;

function injectChatWidget() {
  if (document.getElementById("chat-widget-btn")) return;

  const btn = document.createElement("button");
  btn.id = "chat-widget-btn";
  btn.className = "chat-widget";
  btn.innerHTML = "💬";
  btn.setAttribute("aria-label", t("chatButtonLabel"));

  const panel = document.createElement("div");
  panel.id = "chat-panel";
  panel.className = "chat-panel";
  panel.innerHTML = `
    <div class="chat-panel-header">
      <span id="chat-panel-title">${t("chatTitle")}</span>
      <button class="chat-panel-close" id="chat-panel-close" aria-label="Close">✕</button>
    </div>
    <div class="chat-messages" id="chat-messages"></div>
    <div class="chat-input-row">
      <input type="text" id="chat-input" placeholder="${t("chatPlaceholder")}" autocomplete="off" />
      <button id="chat-send-btn">${t("chatSend")}</button>
    </div>
  `;

  document.body.appendChild(panel);
  document.body.appendChild(btn);

  const messagesEl = document.getElementById("chat-messages");
  const inputEl = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");

  function openPanel() {
    panel.classList.add("open");
    if (!chatWelcomed) {
      appendMessage("assistant", t("chatWelcome"));
      chatWelcomed = true;
    }
    inputEl.focus();
  }
  function closePanel() {
    panel.classList.remove("open");
  }

  btn.addEventListener("click", () => {
    panel.classList.contains("open") ? closePanel() : openPanel();
  });
  document.getElementById("chat-panel-close").addEventListener("click", closePanel);

  function appendMessage(role, text) {
    const el = document.createElement("div");
    el.className = `chat-msg ${role}`;
    el.textContent = text;
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || chatSending) return;

    chatSending = true;
    sendBtn.disabled = true;
    appendMessage("user", text);
    chatHistory.push({ role: "user", content: text });
    inputEl.value = "";

    const thinkingEl = appendMessage("assistant thinking", t("chatThinking"));

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: chatHistory, lang: getLang() }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      thinkingEl.remove();
      appendMessage("assistant", data.reply);
      chatHistory.push({ role: "assistant", content: data.reply });
    } catch (err) {
      thinkingEl.remove();
      appendMessage("assistant", t("chatError"));
    } finally {
      chatSending = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });

  document.addEventListener("langchange", () => {
    btn.setAttribute("aria-label", t("chatButtonLabel"));
    document.getElementById("chat-panel-title").textContent = t("chatTitle");
    inputEl.placeholder = t("chatPlaceholder");
    sendBtn.textContent = t("chatSend");
  });
}

document.addEventListener("DOMContentLoaded", injectChatWidget);
