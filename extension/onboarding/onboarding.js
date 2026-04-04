const SERVER = "http://localhost:8765";

const MODELS = [
  { name: "qwen2.5:0.5b", size: "0.4 GB", note: "Fastest · Lightest" },
  { name: "qwen2.5:1.5b", size: "1.0 GB", note: "Fast · Good quality" },
  { name: "qwen2.5:3b",   size: "1.9 GB", note: "Balanced ⭐ Recommended" },
  { name: "qwen2.5:7b",   size: "4.7 GB", note: "High quality" },
  { name: "qwen2.5:14b",  size: "9.0 GB", note: "Very high quality" },
  { name: "llama3.2:3b",  size: "2.0 GB", note: "Meta Llama 3.2" },
  { name: "mistral:7b",   size: "4.1 GB", note: "Mistral 7B" },
  { name: "phi3:mini",    size: "2.2 GB", note: "Microsoft Phi-3" },
];

let selectedEngine    = "gemini";
let selectedModel     = "qwen2.5:3b";
let downloadedModels  = [];

// ── Step navigation ──────────────────────────────────────────
function goStep(n) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.getElementById("panel-" + n).classList.add("active");

  [1, 2, 3].forEach(i => {
    const dot = document.getElementById("dot-" + i);
    const lbl = document.getElementById("lbl-" + i);
    dot.className = "step-dot" + (i < n ? " done" : i === n ? " active" : "");
    lbl.className = "step-label-item" + (i < n ? " done" : i === n ? " active" : "");
    if (i < 3) {
      const line = document.getElementById("line-" + i);
      line.className = "step-line" + (i < n ? " done" : "");
    }
  });

  if (n === 2) loadOllamaModels();
}

// ── Step 1: Server check ─────────────────────────────────────
async function checkServer() {
  setServerStatus("checking");
  try {
    const r = await fetch(`${SERVER}/health`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      setServerStatus("online");
      document.getElementById("step1-next-btn").style.display = "block";
      document.getElementById("check-again-btn").style.display = "none";
      document.getElementById("offline-help").style.display = "none";
    } else {
      setServerStatus("offline");
    }
  } catch {
    setServerStatus("offline");
  }
}

function setServerStatus(state) {
  const box   = document.getElementById("server-status-box");
  const icon  = document.getElementById("server-icon");
  const title = document.getElementById("server-status-title");
  const sub   = document.getElementById("server-status-sub");
  const help  = document.getElementById("offline-help");

  box.className = "status-box " + state;
  if (state === "checking") {
    icon.textContent   = "⏳";
    title.textContent  = "Checking server...";
    sub.textContent    = "Looking for MnemOS at localhost:8765";
    help.style.display = "none";
  } else if (state === "online") {
    icon.textContent   = "✅";
    title.textContent  = "Server is running!";
    sub.textContent    = "MnemOS is ready at localhost:8765";
    help.style.display = "none";
  } else {
    icon.textContent   = "❌";
    title.textContent  = "Server not found";
    sub.textContent    = "Please download and start the MnemOS server app";
    help.style.display = "block";
  }
}

// ── Step 2: Engine ───────────────────────────────────────────
function selectEngine(engine) {
  selectedEngine = engine;
  document.getElementById("card-gemini").classList.toggle("selected", engine === "gemini");
  document.getElementById("card-ollama").classList.toggle("selected", engine === "ollama");
  document.getElementById("gemini-setup").style.display = engine === "gemini" ? "" : "none";
  document.getElementById("ollama-setup").style.display = engine === "ollama" ? "" : "none";
}

async function loadOllamaModels() {
  try {
    const r    = await fetch(`${SERVER}/ollama/models`);
    const data = await r.json();
    downloadedModels = (data.models || []).map(m => m.name);
  } catch {
    downloadedModels = [];
  }
  renderModels();
}

function renderModels() {
  const list = document.getElementById("model-list");
  list.innerHTML = MODELS.map(m => {
    const isDl = downloadedModels.some(d => d === m.name || d.startsWith(m.name));
    const dlBtnId = "dl-" + m.name.replace(":", "-");
    return `
      <div class="model-row ${isDl ? "downloaded" : ""} ${m.name === selectedModel ? "selected" : ""}"
           data-model="${m.name}">
        <div class="model-info">
          <div class="model-name">${m.name}</div>
          <div class="model-meta">${m.note}</div>
        </div>
        <span class="model-badge badge-size">${m.size}</span>
        ${isDl
          ? `<span class="model-badge badge-dl">✓ Ready</span>`
          : `<button class="dl-btn" id="${dlBtnId}" data-model="${m.name}">⬇ Download</button>`
        }
      </div>`;
  }).join("");

  // Attach listeners after rendering
  list.querySelectorAll(".model-row").forEach(row => {
    row.addEventListener("click", () => {
      selectedModel = row.dataset.model;
      list.querySelectorAll(".model-row").forEach(r => r.classList.remove("selected"));
      row.classList.add("selected");
    });
  });

  list.querySelectorAll(".dl-btn").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      downloadModel(btn.dataset.model, btn);
    });
  });
}

async function downloadModel(modelName, btn) {
  btn.disabled     = true;
  btn.textContent  = "Downloading...";
  try {
    await fetch(`${SERVER}/ollama/pull`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ model: modelName }),
    });
    btn.textContent = "✓ Ready";
    btn.className   = "dl-btn done-btn";
    const row = btn.closest(".model-row");
    row.classList.add("downloaded");
    downloadedModels.push(modelName);
    selectedModel = modelName;
    document.querySelectorAll(".model-row").forEach(r => r.classList.remove("selected"));
    row.classList.add("selected");
  } catch {
    btn.disabled    = false;
    btn.textContent = "⬇ Download";
  }
}

async function applyEngine() {
  const btn = document.getElementById("step2-btn");
  btn.disabled     = true;
  btn.textContent  = "Saving...";

  const payload = { mode: selectedEngine };
  if (selectedEngine === "gemini") {
    const key = document.getElementById("gemini-key-input").value.trim();
    if (!key) {
      btn.disabled    = false;
      btn.textContent = "Save & Continue →";
      document.getElementById("gemini-key-input").style.borderColor = "#ef4444";
      return;
    }
    payload.gemini_key = key;
  } else {
    payload.gen_model = selectedModel;
  }

  try {
    await fetch(`${SERVER}/config`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });
    goStep(3);
  } catch {
    btn.disabled    = false;
    btn.textContent = "Save & Continue →";
  }
}

// ── Wire up all static buttons ────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("check-again-btn").addEventListener("click", checkServer);
  document.getElementById("step1-next-btn").addEventListener("click", () => goStep(2));
  document.getElementById("card-gemini").addEventListener("click", () => selectEngine("gemini"));
  document.getElementById("card-ollama").addEventListener("click", () => selectEngine("ollama"));
  document.getElementById("step2-btn").addEventListener("click", applyEngine);
  document.getElementById("step2-back-btn").addEventListener("click", () => goStep(1));
  document.getElementById("open-chatgpt-btn").addEventListener("click", () => window.open("https://chatgpt.com", "_blank"));

  checkServer();
});
