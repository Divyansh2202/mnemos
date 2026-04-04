// MnemOS — Claude.ai content script

let lastSentCount = 0;
let _lastUrl      = location.href;
let _idleTimer    = null;

function getMessages() {
  const messages = [];
  document.querySelectorAll('[data-testid="user-message"]').forEach(el => {
    const content = el.innerText?.trim();
    if (content) messages.push({ role: "user", content, _idx: getIndex(el) });
  });
  document.querySelectorAll(".font-claude-message").forEach(el => {
    const content = el.innerText?.trim();
    if (content) messages.push({ role: "assistant", content, _idx: getIndex(el) });
  });
  messages.sort((a, b) => a._idx - b._idx);
  return messages.map(({ role, content }) => ({ role, content }));
}

function getIndex(el) {
  let idx = 0, node = el;
  while (node) { idx++; node = node.previousElementSibling; }
  return idx;
}

function getInputBox() {
  return document.querySelector("[contenteditable='true'].ProseMirror") ||
         document.querySelector("div[contenteditable='true']");
}

function getSessionId() {
  return window.location.pathname.split("/chat/")[1] || null;
}

function runtimeOk() {
  try { return !!chrome.runtime?.id; } catch { return false; }
}

function sendMsg(msg, cb) {
  if (!runtimeOk()) { cb && cb(null); return; }
  try { chrome.runtime.sendMessage(msg, cb); } catch { cb && cb(null); }
}

async function injectMemoryContext(userText) {
  if (!userText.trim() || userText.includes("[Memory Context from MnemOS]") || !runtimeOk()) return null;

  const memories = await new Promise(resolve => sendMsg(
    { type: "RETRIEVE", query: userText, appId: "claude" }, resolve
  ));

  if (!memories || memories.length === 0) return null;

  const context = memories.map(m => `- ${m.content}`).join("\n");
  return `[Memory Context from MnemOS]\n${context}\n\uE000${userText}`;
}

function cleanBubble(el) {
  if (el.dataset.mnemosCleaned) return;
  if (!el.innerText.includes("[Memory Context from MnemOS]")) return;
  el.dataset.mnemosCleaned = "1";
  el.style.opacity = "0";

  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const idx = node.textContent.indexOf("\uE000");
    if (idx !== -1) {
      const visible = document.createTextNode(node.textContent.slice(idx + 1).trim());
      const hidden  = document.createElement("span");
      hidden.style.display = "none";
      hidden.textContent   = node.textContent.slice(0, idx + 1);
      node.parentNode.insertBefore(hidden, node);
      node.parentNode.replaceChild(visible, node);
      break;
    }
  }
  requestAnimationFrame(() => { el.style.opacity = ""; });
}

function hideContextInBubble() {
  document.querySelectorAll('[data-testid="user-message"]').forEach(cleanBubble);
}

const bubbleObserver = new MutationObserver(() => hideContextInBubble());
bubbleObserver.observe(document.body, { childList: true, subtree: true });

function interceptSend() {
  document.addEventListener("keydown", async (e) => {
    if (e.key !== "Enter" || e.shiftKey) return;
    if (!e.isTrusted) return; // skip our own re-dispatched events
    const input = getInputBox();
    if (!input) return;
    const userText = input.innerText?.trim();
    if (!userText || userText.length < 5 || userText.includes("[Memory Context from MnemOS]")) return;

    e.preventDefault();
    e.stopImmediatePropagation();

    // ── Real-time save: persist user message immediately ──────────
    const sessionId = getSessionId();
    if (sessionId) {
      const existing = cleanMessages(getMessages());
      const title    = existing.length === 0 ? userText.slice(0, 60) : "";
      sendMsg({
        type:      "SAVE_SESSION",
        messages:  [...existing, { role: "user", content: userText }],
        appId:     "claude",
        sessionId,
        title,
      }, null);
    }

    const injected = await injectMemoryContext(userText);
    if (injected) {
      input.innerText = injected;
      const range = document.createRange();
      range.selectNodeContents(input);
      range.collapse(false);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
      showToast(`MnemOS injected ${injected.split("\n").filter(l => l.startsWith("-")).length} memories`);
    }

    setTimeout(() => {
      input.dispatchEvent(new KeyboardEvent("keydown", {
        key: "Enter", code: "Enter", keyCode: 13,
        bubbles: true, cancelable: true
      }));
      hideContextInBubble();
    }, 100);
  }, true);
}

function cleanMessages(messages) {
  return messages.map(m => {
    if (m.role === "user" && m.content.includes("[Memory Context from MnemOS]")) {
      const idx = m.content.indexOf("\uE000");
      if (idx !== -1) return { ...m, content: m.content.slice(idx + 1).trim() };
      const mk = m.content.indexOf("[/MnemOS]");
      if (mk !== -1) return { ...m, content: m.content.slice(mk + 9).trim() };
      const parts = m.content.split("\n\n");
      return { ...m, content: parts.slice(1).join("\n\n").trim() };
    }
    return m;
  });
}

function saveSession() {
  const sessionId = getSessionId();
  if (!sessionId) return;

  const raw = getMessages();
  if (raw.length < 2) return;

  const messages = cleanMessages(raw);
  lastSentCount  = raw.length;

  sendMsg(
    { type: "LEARN", messages, appId: "claude", sessionId },
    (resp) => { if (resp?.queued) console.log("[MnemOS] session queued"); }
  );
}

function onDomChange() {
  clearTimeout(_idleTimer);
  _idleTimer = setTimeout(() => {
    const raw = getMessages();
    if (raw.length <= lastSentCount || raw.length < 2) return;
    const last = raw[raw.length - 1];
    if (last.role !== "assistant") return;
    lastSentCount = raw.length;
    saveSession();
    hideContextInBubble();
  }, 5000);
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) saveSession();
});
window.addEventListener("beforeunload", () => saveSession());

setInterval(() => {
  if (location.href !== _lastUrl) {
    saveSession();
    _lastUrl      = location.href;
    lastSentCount = 0;
  }
}, 1500);

const observer = new MutationObserver(onDomChange);
observer.observe(document.body, { childList: true, subtree: true });

if (runtimeOk()) {
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "MEMORIES_STORED") {
      showToast(`MnemOS saved ${msg.count} memor${msg.count > 1 ? "ies" : "y"}`);
    }
  });
}

interceptSend();
console.log("[MnemOS] Watching Claude.ai — store + inject enabled");

function showToast(text) {
  const toast = document.createElement("div");
  toast.textContent = text;
  Object.assign(toast.style, {
    position: "fixed", bottom: "24px", right: "24px",
    background: "#1a1a2e", color: "#a78bfa",
    padding: "10px 18px", borderRadius: "8px",
    fontSize: "13px", fontFamily: "monospace", zIndex: "99999",
    boxShadow: "0 4px 12px rgba(0,0,0,0.4)", border: "1px solid #6d28d9",
    opacity: "0", transition: "opacity 0.3s ease",
  });
  document.body.appendChild(toast);
  requestAnimationFrame(() => { toast.style.opacity = "1"; });
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 400);
  }, 3000);
}
