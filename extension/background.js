const DEFAULT_SERVER = "http://localhost:8765";

// ─── Settings ─────────────────────────────────────────────────
async function getSettings() {
  return new Promise(resolve => {
    chrome.storage.local.get(
      { serverUrl: DEFAULT_SERVER, userId: "default", enabled: true },
      resolve
    );
  });
}

// ─── QUEUE SYSTEM ─────────────────────────────────────────────
// Persists in chrome.storage so nothing is lost on page reload

async function enqueue(item) {
  return new Promise(resolve => {
    chrome.storage.local.get({ mnemos_queue: [] }, ({ mnemos_queue }) => {
      mnemos_queue.push({ ...item, addedAt: Date.now(), retries: 0 });
      chrome.storage.local.set({ mnemos_queue }, resolve);
    });
  });
}

async function getQueue() {
  return new Promise(resolve => {
    chrome.storage.local.get({ mnemos_queue: [] }, ({ mnemos_queue }) => resolve(mnemos_queue));
  });
}

async function saveQueue(queue) {
  return new Promise(resolve => {
    chrome.storage.local.set({ mnemos_queue: queue }, resolve);
  });
}

let isProcessing = false;

async function processQueue() {
  if (isProcessing) return;
  isProcessing = true;

  try {
    while (true) {
      const queue = await getQueue();
      if (queue.length === 0) break;

      const item = queue[0];
      const { serverUrl, userId } = await getSettings();

      try {
        const resp = await fetch(`${serverUrl}/memory/learn`, {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({
            messages:   item.messages,
            app_id:     item.appId,
            user_id:    userId,
            session_id: item.sessionId || "",
          }),
        });

        if (resp.ok) {
          const data = await resp.json();
          console.log(`[MnemOS Queue] ✓ Stored ${data.stored} memories from ${item.appId}`);
          // Remove from queue on success
          queue.shift();
          await saveQueue(queue);

          // Notify content script
          if (data.stored > 0) {
            chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
              if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, {
                  type: "MEMORIES_STORED",
                  count: data.stored
                }).catch(() => {});
              }
            });
          }
        } else {
          throw new Error(`Server returned ${resp.status}`);
        }
      } catch (e) {
        item.retries = (item.retries || 0) + 1;
        console.warn(`[MnemOS Queue] Failed (attempt ${item.retries}): ${e.message}`);

        if (item.retries >= 5) {
          console.error(`[MnemOS Queue] Dropping item after 5 retries`);
          queue.shift();
        } else {
          // Move to back of queue, retry later
          queue.shift();
          queue.push(item);
        }
        await saveQueue(queue);
        // Wait before retrying
        await new Promise(r => setTimeout(r, 3000 * item.retries));
        break;
      }
    }
  } finally {
    isProcessing = false;
  }

  // Check queue size and update badge
  const queue = await getQueue();
  updateBadge(queue.length);
}

function updateBadge(count) {
  if (count > 0) {
    chrome.action.setBadgeText({ text: String(count) });
    chrome.action.setBadgeBackgroundColor({ color: "#7c3aed" });
  } else {
    chrome.action.setBadgeText({ text: "" });
  }
}

// Process queue every 5 seconds
setInterval(processQueue, 5000);

// ─── RETRIEVE ─────────────────────────────────────────────────
async function retrieveMemories(query, appId) {
  const { serverUrl, userId } = await getSettings();
  try {
    const resp = await fetch(`${serverUrl}/memory/retrieve`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        query, app_id: appId, user_id: userId, limit: 5
      }),
    });
    const data = await resp.json();
    return data.memories || [];
  } catch {
    return [];
  }
}

// ─── HEALTH ───────────────────────────────────────────────────
async function checkHealth() {
  const { serverUrl } = await getSettings();
  try {
    const resp = await fetch(`${serverUrl}/health`, {
      signal: AbortSignal.timeout(3000)
    });
    return resp.ok;
  } catch {
    return false;
  }
}

// ─── GET ALL MEMORIES ─────────────────────────────────────────
async function getAllMemories() {
  const { serverUrl, userId } = await getSettings();
  try {
    const resp = await fetch(`${serverUrl}/memory/all?user_id=${userId}&limit=50`);
    const data = await resp.json();
    return data.memories || [];
  } catch {
    return [];
  }
}

// ─── DELETE ───────────────────────────────────────────────────
async function deleteMemory(memoryId) {
  const { serverUrl } = await getSettings();
  try {
    await fetch(`${serverUrl}/memory/${memoryId}`, { method: "DELETE" });
    return true;
  } catch {
    return false;
  }
}

// ─── MESSAGE HANDLER ──────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {

  if (msg.type === "LEARN") {
    chrome.storage.local.get({ enabled: true }, ({ enabled }) => {
      if (!enabled) { sendResponse({ queued: false }); return; }
      enqueue({ messages: msg.messages, appId: msg.appId, sessionId: msg.sessionId }).then(() => {
        processQueue();
        sendResponse({ queued: true });
      });
    });
    return true;
  }

  if (msg.type === "RETRIEVE") {
    retrieveMemories(msg.query, msg.appId).then(sendResponse);
    return true;
  }

  if (msg.type === "HEALTH") {
    checkHealth().then(sendResponse);
    return true;
  }

  if (msg.type === "GET_ALL") {
    getAllMemories().then(sendResponse);
    return true;
  }

  if (msg.type === "DELETE") {
    deleteMemory(msg.memoryId).then(sendResponse);
    return true;
  }

  if (msg.type === "GET_QUEUE_SIZE") {
    getQueue().then(q => sendResponse({ size: q.length }));
    return true;
  }

  if (msg.type === "GET_CONFIG") {
    getSettings().then(({ serverUrl }) => {
      fetch(`${serverUrl}/config`)
        .then(r => r.json())
        .then(sendResponse)
        .catch(() => sendResponse(null));
    });
    return true;
  }

  if (msg.type === "SET_CONFIG") {
    getSettings().then(({ serverUrl }) => {
      fetch(`${serverUrl}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(msg.payload),
      })
        .then(r => r.json())
        .then(sendResponse)
        .catch(() => sendResponse(null));
    });
    return true;
  }

  if (msg.type === "GET_OLLAMA_MODELS") {
    getSettings().then(({ serverUrl }) => {
      fetch(`${serverUrl}/ollama/models`)
        .then(r => r.json())
        .then(data => sendResponse(data.models || []))
        .catch(() => sendResponse([]));
    });
    return true;
  }

  if (msg.type === "PULL_MODEL") {
    getSettings().then(({ serverUrl }) => {
      fetch(`${serverUrl}/ollama/pull`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: msg.model }),
      })
        .then(r => r.json())
        .then(sendResponse)
        .catch(() => sendResponse(null));
    });
    return true;
  }

  // ── Real-time raw session save (no extraction, fire-and-forget) ──
  if (msg.type === "SAVE_SESSION") {
    getSettings().then(({ serverUrl, userId }) => {
      fetch(`${serverUrl}/sessions`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          session_id: msg.sessionId || "",
          messages:   msg.messages,
          app_id:     msg.appId,
          user_id:    userId,
          title:      msg.title || "",
        }),
      }).catch(() => {});
    });
    return false; // fire-and-forget, no sendResponse needed
  }
});

// Process any leftover queue on startup
processQueue();

// ─── ONBOARDING ───────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === "install") {
    chrome.tabs.create({
      url: chrome.runtime.getURL("onboarding/onboarding.html")
    });
  }
});
