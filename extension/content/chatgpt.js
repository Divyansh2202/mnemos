// MnemOS — ChatGPT content script

let lastSentCount = 0;
let _lastUrl      = location.href;
let _idleTimer    = null;

// ─── GET MESSAGES ─────────────────────────────────────────────
function getMessages() {
  const turns = document.querySelectorAll("[data-message-author-role]");
  const messages = [];
  turns.forEach(el => {
    const role    = el.getAttribute("data-message-author-role");
    const content = el.innerText?.trim();
    if (role && content) messages.push({ role, content });
  });
  return messages;
}

// ─── INPUT BOX ────────────────────────────────────────────────
function getInputBox() {
  return document.querySelector("#prompt-textarea") ||
         document.querySelector("[contenteditable='true'][data-id]") ||
         document.querySelector("div[contenteditable='true']");
}

// ─── SESSION ID ───────────────────────────────────────────────
function getSessionId() {
  // Only return real conversation IDs — never the homepage
  return window.location.pathname.split("/c/")[1] || null;
}

// ─── RUNTIME GUARD ────────────────────────────────────────────
function runtimeOk() {
  try { return !!chrome.runtime?.id; } catch { return false; }
}

function sendMsg(msg, cb) {
  if (!runtimeOk()) { cb && cb(null); return; }
  try { chrome.runtime.sendMessage(msg, cb); } catch { cb && cb(null); }
}

// ─── INJECT MEMORIES ──────────────────────────────────────────
async function injectMemoryContext(userText) {
  if (!userText.trim() || !runtimeOk()) return null;

  const memories = await new Promise(resolve => sendMsg(
    { type: "RETRIEVE", query: userText, appId: "chatgpt" }, resolve
  ));

  if (!memories || memories.length === 0) return null;

  const context = memories.map(m => `- ${m.content}`).join("\n");
  return `[Memory Context from MnemOS]\n${context}\n\uE000${userText}`;
}

// ─── HIDE CONTEXT IN SENT BUBBLE ──────────────────────────────
// Watches for user bubbles containing the memory context prefix
// and immediately hides it — no visible flicker.
function cleanBubble(el) {
  if (el.dataset.mnemosCleaned) return;
  if (!el.innerText.includes("[Memory Context from MnemOS]")) return;
  el.dataset.mnemosCleaned = "1";
  el.style.opacity = "0"; // hide instantly while we edit DOM

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
  requestAnimationFrame(() => { el.style.opacity = ""; }); // restore
}

function hideContextInBubble() {
  document.querySelectorAll("[data-message-author-role='user']").forEach(cleanBubble);
}

// Dedicated observer — fires on every DOM change to catch bubbles the moment they appear
const bubbleObserver = new MutationObserver(() => hideContextInBubble());
bubbleObserver.observe(document.body, { childList: true, subtree: true });

// ─── INTERCEPT SEND ───────────────────────────────────────────
function interceptSend() {
  document.addEventListener("keydown", async (e) => {
    if (e.key !== "Enter" || e.shiftKey) return;
    if (!e.isTrusted) return; // skip our own re-dispatched events
    const input = getInputBox();
    if (!input) return;
    const userText = input.innerText?.trim() || input.value?.trim();
    if (!userText || userText.length < 5) return;
    if (userText.includes("[Memory Context from MnemOS]")) return;

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
        appId:     "chatgpt",
        sessionId,
        title,
      }, null);
    }

    const injected = await injectMemoryContext(userText);
    if (injected) {
      if (input.isContentEditable) {
        input.innerText = injected;
        const range = document.createRange();
        range.selectNodeContents(input);
        range.collapse(false);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
      } else {
        input.value = injected;
      }
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

  document.addEventListener("click", async (e) => {
    if (!e.isTrusted) return; // skip programmatic clicks
    const btn = e.target.closest("[data-testid='send-button']") ||
                e.target.closest("button[aria-label='Send message']");
    if (!btn) return;
    const input = getInputBox();
    if (!input) return;
    const userText = input.innerText?.trim() || input.value?.trim();
    if (!userText || userText.includes("[Memory Context from MnemOS]") || userText.length < 5) return;

    e.preventDefault();
    e.stopImmediatePropagation();

    // ── Real-time save: persist user message immediately ──────────
    const sessionId2 = getSessionId();
    if (sessionId2) {
      const existing2 = cleanMessages(getMessages());
      const title2    = existing2.length === 0 ? userText.slice(0, 60) : "";
      sendMsg({
        type:      "SAVE_SESSION",
        messages:  [...existing2, { role: "user", content: userText }],
        appId:     "chatgpt",
        sessionId: sessionId2,
        title:     title2,
      }, null);
    }

    const injected = await injectMemoryContext(userText);
    if (injected) {
      if (input.isContentEditable) input.innerText = injected;
      else input.value = injected;
      showToast(`MnemOS injected ${injected.split("\n").filter(l => l.startsWith("-")).length} memories`);
    }

    setTimeout(() => { btn.click(); hideContextInBubble(); }, 100);
  }, true);
}

// ─── CLEAN MESSAGES BEFORE STORING ───────────────────────────
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

// ─── SAVE SESSION ─────────────────────────────────────────────
function saveSession() {
  const sessionId = getSessionId();
  if (!sessionId) return; // Skip homepage / no conversation yet

  const raw = getMessages();
  if (raw.length < 2) return;

  const messages = cleanMessages(raw);
  lastSentCount  = raw.length;

  sendMsg(
    { type: "LEARN", messages, appId: "chatgpt", sessionId },
    (resp) => { if (resp?.queued) console.log("[MnemOS] session queued"); }
  );
}

// ─── IDLE SAVE (extract memories during conversation) ────────
// Fires 5s after the last DOM change — captures each exchange
// for memory extraction while the session upsert keeps ONE card.
function onDomChange() {
  clearTimeout(_idleTimer);
  _idleTimer = setTimeout(() => {
    const raw = getMessages();
    if (raw.length <= lastSentCount || raw.length < 2) return;
    const last = raw[raw.length - 1];
    if (last.role !== "assistant") return;
    lastSentCount = raw.length;
    saveSession(); // upsert → always one card per sessionId
    hideContextInBubble();
  }, 5000);
}

// ─── END-OF-SESSION SAVES ────────────────────────────────────
// Save when user hides/closes the tab or starts a new chat
document.addEventListener("visibilitychange", () => {
  if (document.hidden) saveSession();
});
window.addEventListener("beforeunload", () => saveSession());

// Detect navigation to a new conversation
setInterval(() => {
  if (location.href !== _lastUrl) {
    saveSession();         // save old conversation
    _lastUrl      = location.href;
    lastSentCount = 0;     // reset for the new one
  }
}, 1500);

// ─── INIT ─────────────────────────────────────────────────────
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
console.log("[MnemOS] Watching ChatGPT — store + inject enabled");

// ─── TOAST ────────────────────────────────────────────────────
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
