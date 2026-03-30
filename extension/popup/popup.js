const $ = id => document.getElementById(id);

// ─── Load settings ────────────────────────────────────────────
chrome.storage.local.get(
  { serverUrl: "http://localhost:8765", userId: "default", enabled: true },
  ({ serverUrl, userId, enabled }) => {
    $("server-url").value    = serverUrl;
    $("user-id").value       = userId;
    $("enabled-toggle").checked = enabled;
  }
);

// ─── Save settings ────────────────────────────────────────────
$("save-btn").addEventListener("click", () => {
  const serverUrl = $("server-url").value.trim();
  const userId    = $("user-id").value.trim() || "default";
  chrome.storage.local.set({ serverUrl, userId }, () => {
    $("save-btn").textContent = "Saved ✓";
    setTimeout(() => { $("save-btn").textContent = "Save"; }, 1500);
    checkHealth();
    loadMemories();
  });
});

// ─── Toggle auto-capture ──────────────────────────────────────
$("enabled-toggle").addEventListener("change", e => {
  chrome.storage.local.set({ enabled: e.target.checked });
});

// ─── Health check ─────────────────────────────────────────────
function checkHealth() {
  chrome.runtime.sendMessage({ type: "HEALTH" }, ok => {
    const dot = $("status-dot");
    dot.className = ok ? "dot dot-on" : "dot dot-off";
    dot.title = ok ? "Server online" : "Server offline";
  });
}

// ─── Load memories ────────────────────────────────────────────
function loadMemories() {
  chrome.runtime.sendMessage({ type: "GET_ALL" }, memories => {
    const list = $("memory-list");
    $("mem-count").textContent = memories.length;

    if (!memories || memories.length === 0) {
      list.innerHTML = '<div class="empty">No memories yet</div>';
      return;
    }

    list.innerHTML = "";
    memories.slice(0, 30).forEach(m => {
      const item = document.createElement("div");
      item.className = "memory-item";
      item.innerHTML = `
        <span class="memory-text">${escHtml(m.content)}</span>
        <span class="memory-tag">${escHtml(m.type)}</span>
        <button class="del-btn" data-id="${escHtml(m.id)}" title="Delete">×</button>
      `;
      list.appendChild(item);
    });

    list.querySelectorAll(".del-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        chrome.runtime.sendMessage({ type: "DELETE", memoryId: id }, () => {
          btn.closest(".memory-item").remove();
          const count = $("mem-count");
          count.textContent = parseInt(count.textContent) - 1;
        });
      });
    });
  });
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ─── Refresh button ───────────────────────────────────────────
$("refresh-btn").addEventListener("click", () => {
  checkHealth();
  loadMemories();
});

// ─── Queue status ─────────────────────────────────────────────
function checkQueue() {
  chrome.runtime.sendMessage({ type: "GET_QUEUE_SIZE" }, ({ size }) => {
    const bar = $("queue-bar");
    if (size > 0) {
      bar.style.display = "block";
      $("queue-text").textContent = `⏳ ${size} conversation${size > 1 ? "s" : ""} queued to store`;
    } else {
      bar.style.display = "none";
    }
  });
}

// ─── Dashboard / Sessions links ───────────────────────────────
$("dashboard-btn").addEventListener("click", () => {
  chrome.storage.local.get({ serverUrl: "http://localhost:8765" }, ({ serverUrl }) => {
    chrome.tabs.create({ url: serverUrl + "/dashboard" });
  });
});
$("sessions-btn").addEventListener("click", () => {
  chrome.storage.local.get({ serverUrl: "http://localhost:8765" }, ({ serverUrl }) => {
    chrome.tabs.create({ url: serverUrl + "/dashboard#sessions" });
  });
});

// ─── Model switcher ───────────────────────────────────────────
let _downloadedModels = [];

function loadModelConfig() {
  chrome.runtime.sendMessage({ type: "GET_CONFIG" }, cfg => {
    if (!cfg) return;
    $("engine-select").value = cfg.mode || "gemini";
    onEngineSelectChange();
    if (cfg.mode === "ollama") {
      chrome.runtime.sendMessage({ type: "GET_OLLAMA_MODELS" }, models => {
        _downloadedModels = models || [];
        renderModelSelect(cfg.gen_model);
      });
    }
  });
}

function onEngineSelectChange() {
  const isOllama = $("engine-select").value === "ollama";
  $("model-select").style.display        = isOllama ? "" : "none";
  $("model-download-btn").style.display  = isOllama ? "" : "none";
  if (isOllama && _downloadedModels.length === 0) {
    chrome.runtime.sendMessage({ type: "GET_OLLAMA_MODELS" }, models => {
      _downloadedModels = models || [];
      renderModelSelect();
    });
  }
}

function renderModelSelect(selected) {
  const sel = $("model-select");
  if (_downloadedModels.length === 0) {
    sel.innerHTML = '<option value="">No models downloaded</option>';
    return;
  }
  sel.innerHTML = _downloadedModels
    .map(m => `<option value="${m.name}">${m.name}</option>`)
    .join("");
  if (selected) sel.value = selected;
}

$("engine-select").addEventListener("change", onEngineSelectChange);

$("model-apply-btn").addEventListener("click", () => {
  const engine = $("engine-select").value;
  const model  = $("model-select").value;
  const payload = { mode: engine };
  if (engine === "ollama" && model) payload.gen_model = model;

  $("model-status").textContent = "Applying...";
  chrome.runtime.sendMessage({ type: "SET_CONFIG", payload }, cfg => {
    if (cfg) {
      $("model-status").textContent =
        `✓ ${cfg.mode}${cfg.mode === "ollama" ? " / " + cfg.gen_model : ""}`;
      setTimeout(() => { $("model-status").textContent = ""; }, 3000);
    } else {
      $("model-status").textContent = "Failed — is server running?";
    }
  });
});

$("model-download-btn").addEventListener("click", () => {
  const POPULAR = [
    "qwen2.5:0.5b","qwen2.5:1.5b","qwen2.5:3b","qwen2.5:7b",
    "qwen2.5:14b","llama3.2:3b","mistral:7b","phi3:mini"
  ];
  const already = _downloadedModels.map(m => m.name);
  const available = POPULAR.filter(m => !already.includes(m));
  if (available.length === 0) {
    $("model-status").textContent = "All popular models downloaded";
    return;
  }
  // open dashboard models page for download
  chrome.storage.local.get({ serverUrl: "http://localhost:8765" }, ({ serverUrl }) => {
    chrome.tabs.create({ url: serverUrl + "/dashboard#settings" });
  });
});

// ─── Init ─────────────────────────────────────────────────────
checkHealth();
loadMemories();
checkQueue();
loadModelConfig();
