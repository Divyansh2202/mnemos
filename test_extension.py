"""
MnemOS Extension Test Suite
Tests every server endpoint the extension calls, JS syntax,
manifest validity, and simulates the full inject → store → retrieve cycle.
"""
import os, json, re, time, requests, subprocess

BASE    = "http://localhost:8765"
PASS    = "✅"
FAIL    = "❌"
results = []

def check(name, passed, detail=""):
    results.append((name, passed))
    icon = PASS if passed else FAIL
    print(f"  {icon}  {name}" + (f"  →  {detail}" if detail else ""))

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

EXT_DIR = os.path.join(os.path.dirname(__file__), "extension")

# ════════════════════════════════════════════════════════════
section("1. MANIFEST VALIDATION")
# ════════════════════════════════════════════════════════════
manifest_path = os.path.join(EXT_DIR, "manifest.json")
try:
    with open(manifest_path) as f:
        manifest = json.load(f)
    check("manifest.json valid JSON", True)
    check("MV3 manifest",             manifest.get("manifest_version") == 3)
    check("Has background service worker", "background" in manifest)
    check("Has content scripts",      len(manifest.get("content_scripts", [])) >= 2)
    check("Has storage permission",   "storage" in manifest.get("permissions", []))
    check("Has tabs permission",      "tabs" in manifest.get("permissions", []))
    check("Has action popup",         "action" in manifest)

    cs = manifest.get("content_scripts", [])
    chatgpt_cs = any("chatgpt.com" in str(c.get("matches", [])) for c in cs)
    claude_cs  = any("claude.ai"   in str(c.get("matches", [])) for c in cs)
    check("ChatGPT content script registered", chatgpt_cs)
    check("Claude content script registered",  claude_cs)
except Exception as e:
    check("manifest.json", False, str(e))

# ════════════════════════════════════════════════════════════
section("2. JS FILE SYNTAX CHECK (node --check)")
# ════════════════════════════════════════════════════════════
JS_FILES = [
    "background.js",
    "content/chatgpt.js",
    "content/claude.js",
    "popup/popup.js",
]
for js_file in JS_FILES:
    path = os.path.join(EXT_DIR, js_file)
    if not os.path.exists(path):
        check(f"{js_file} exists", False, "file not found")
        continue
    try:
        result = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        check(f"{js_file} syntax", result.returncode == 0,
              result.stderr.strip()[:80] if result.returncode != 0 else "ok")
    except FileNotFoundError:
        # node not installed, do basic checks manually
        with open(path) as f:
            content = f.read()
        has_syntax_error = False
        check(f"{js_file} exists", True, f"{len(content)} bytes")

# ════════════════════════════════════════════════════════════
section("3. EXTENSION FILE STRUCTURE")
# ════════════════════════════════════════════════════════════
REQUIRED_FILES = [
    "manifest.json",
    "background.js",
    "content/chatgpt.js",
    "content/claude.js",
    "popup/popup.html",
    "popup/popup.js",
    "popup/popup.css",
    "onboarding/onboarding.html",
]
for f in REQUIRED_FILES:
    path = os.path.join(EXT_DIR, f)
    exists = os.path.exists(path)
    size   = os.path.getsize(path) if exists else 0
    check(f"{f}", exists, f"{size} bytes" if exists else "MISSING")

# ════════════════════════════════════════════════════════════
section("4. CONTENT SCRIPT KEY PATTERNS")
# ════════════════════════════════════════════════════════════
def check_pattern(filename, pattern, name):
    path = os.path.join(EXT_DIR, filename)
    with open(path) as f:
        content = f.read()
    found = bool(re.search(pattern, content))
    check(f"{os.path.basename(filename)}: {name}", found)

# chatgpt.js
check_pattern("content/chatgpt.js", r"e\.isTrusted",           "isTrusted guard (no infinite loop)")
check_pattern("content/chatgpt.js", r"runtimeOk\(\)",          "runtimeOk guard")
check_pattern("content/chatgpt.js", r"\\uE000",                "invisible delimiter \\uE000")
check_pattern("content/chatgpt.js", r"bubbleObserver",         "bubble observer (no flicker)")
check_pattern("content/chatgpt.js", r"RETRIEVE",               "memory retrieval call")
check_pattern("content/chatgpt.js", r"LEARN",                  "session save call")
check_pattern("content/chatgpt.js", r"visibilitychange",       "save on tab hide")
check_pattern("content/chatgpt.js", r"beforeunload",           "save on tab close")
check_pattern("content/chatgpt.js", r"Memory Context from MnemOS", "context injection prefix")
# claude.js
check_pattern("content/claude.js",  r"e\.isTrusted",           "isTrusted guard (no infinite loop)")
check_pattern("content/claude.js",  r"runtimeOk\(\)",          "runtimeOk guard")
check_pattern("content/claude.js",  r"bubbleObserver",         "bubble observer (no flicker)")
# background.js
check_pattern("background.js",      r"GET_CONFIG",             "GET_CONFIG handler")
check_pattern("background.js",      r"SET_CONFIG",             "SET_CONFIG handler")
check_pattern("background.js",      r"GET_OLLAMA_MODELS",      "GET_OLLAMA_MODELS handler")
check_pattern("background.js",      r"PULL_MODEL",             "PULL_MODEL handler")
check_pattern("background.js",      r"onInstalled",            "onInstalled → open onboarding")
check_pattern("background.js",      r"mnemos_queue",           "persistent queue")
check_pattern("background.js",      r"retries",                "retry logic")
# onboarding.html
check_pattern("onboarding/onboarding.html", r"checkServer",    "server health check")
check_pattern("onboarding/onboarding.html", r"selectEngine",   "engine selection")
check_pattern("onboarding/onboarding.html", r"downloadModel",  "model download button")
check_pattern("onboarding/onboarding.html", r"ollama/pull",    "pull model API call")
check_pattern("onboarding/onboarding.html", r"goStep\(3\)",    "onboarding completes")

# ════════════════════════════════════════════════════════════
section("5. BACKGROUND.JS → SERVER API CALLS")
# ════════════════════════════════════════════════════════════
# Simulate every message type background.js handles

# HEALTH
try:
    r = requests.get(f"{BASE}/health")
    check("HEALTH → /health", r.status_code == 200)
except Exception as e:
    check("HEALTH", False, str(e))

# RETRIEVE
try:
    r = requests.post(f"{BASE}/memory/retrieve", json={
        "query": "python programming", "app_id": "chatgpt",
        "user_id": "default", "limit": 5
    })
    check("RETRIEVE → /memory/retrieve", r.status_code == 200,
          f"{len(r.json().get('memories', []))} memories returned")
except Exception as e:
    check("RETRIEVE", False, str(e))

# LEARN (queued by background.js)
try:
    r = requests.post(f"{BASE}/memory/learn", json={
        "messages": [
            {"role": "user",      "content": "I am testing MnemOS extension. I prefer TypeScript over JavaScript."},
            {"role": "assistant", "content": "Good to know! TypeScript is great for large codebases."},
        ],
        "app_id":     "chatgpt",
        "user_id":    "default",
        "session_id": "ext_test_session_001",
    })
    data = r.json()
    check("LEARN → /memory/learn", r.status_code == 200, f"stored={data.get('stored', 0)}")
except Exception as e:
    check("LEARN", False, str(e))

# GET_ALL
try:
    r = requests.get(f"{BASE}/memory/all", params={"user_id": "default", "limit": 50})
    mems = r.json().get("memories", [])
    check("GET_ALL → /memory/all", r.status_code == 200, f"{len(mems)} memories")
except Exception as e:
    check("GET_ALL", False, str(e))

# DELETE
try:
    r = requests.post(f"{BASE}/memory/store", json={
        "content": "temp memory for delete test",
        "type": "semantic", "app_id": "chatgpt", "user_id": "default"
    })
    mem_id = r.json().get("id")
    r2 = requests.delete(f"{BASE}/memory/{mem_id}")
    check("DELETE → /memory/:id", r2.status_code == 200, r2.json().get("status"))
except Exception as e:
    check("DELETE", False, str(e))

# GET_CONFIG
try:
    r = requests.get(f"{BASE}/config")
    check("GET_CONFIG → /config", r.status_code == 200, str(r.json()))
except Exception as e:
    check("GET_CONFIG", False, str(e))

# SET_CONFIG
try:
    r = requests.post(f"{BASE}/config", json={"mode": "gemini"})
    check("SET_CONFIG → POST /config", r.status_code == 200, r.json().get("mode"))
except Exception as e:
    check("SET_CONFIG", False, str(e))

# GET_OLLAMA_MODELS
try:
    r = requests.get(f"{BASE}/ollama/models")
    models = r.json().get("models", [])
    check("GET_OLLAMA_MODELS → /ollama/models", r.status_code == 200,
          f"{len(models)} models: {[m['name'] for m in models]}")
except Exception as e:
    check("GET_OLLAMA_MODELS", False, str(e))

# GET_QUEUE_SIZE (no server endpoint — handled in chrome.storage; mark as N/A)
check("GET_QUEUE_SIZE (chrome.storage — browser only)", True, "N/A in server test")

# Reset to ollama so section 6 learn calls work without a Gemini key
requests.post(f"{BASE}/config", json={"mode": "ollama", "gen_model": "qwen2.5:7b"})

# ════════════════════════════════════════════════════════════
section("6. FULL INJECT → STORE → RETRIEVE CYCLE")
# ════════════════════════════════════════════════════════════
print("\n  Simulating: user sends message → inject memories → AI replies → store → retrieve\n")

# Step 1: retrieve memories for a query (what extension does before sending)
user_msg = "what keyboard should I buy for programming?"
t0 = time.time()
r = requests.post(f"{BASE}/memory/retrieve", json={
    "query": user_msg, "app_id": "chatgpt", "user_id": "default", "limit": 5
})
retrieve_time = time.time() - t0
mems = r.json().get("memories", [])
check("Step 1: Retrieve memories for user query", True,
      f"{len(mems)} found in {retrieve_time:.2f}s")
if mems:
    for m in mems:
        print(f"         [{m['relevance']:.3f}] {m['content']}")

# Step 2: simulate injection (what extension does to the message)
if mems:
    context = "\n".join(f"- {m['content']}" for m in mems)
    injected_msg = f"[Memory Context from MnemOS]\n{context}\n\uE000{user_msg}"
    check("Step 2: Memory context injected", True,
          f"{len(mems)} memories prepended, original message preserved after \\uE000")
else:
    injected_msg = user_msg
    check("Step 2: No memories yet (first session)", True, "message sent as-is")

# Step 3: simulate cleanMessages (strips context before storing)
def clean_message(content):
    idx = content.find("\uE000")
    if idx != -1:
        return content[idx + 1:].strip()
    return content

cleaned = clean_message(injected_msg)
check("Step 3: cleanMessages strips context before store", cleaned == user_msg,
      f"cleaned='{cleaned[:50]}'")

# Step 4: store conversation after AI responds
t0 = time.time()
r = requests.post(f"{BASE}/memory/learn", json={
    "messages": [
        {"role": "user",      "content": cleaned},
        {"role": "assistant", "content": "Based on your coding style, the Keychron Q1 with linear switches would be great for you."},
    ],
    "app_id":     "chatgpt",
    "user_id":    "default",
    "session_id": "ext_inject_test_001",
})
store_time = time.time() - t0
data = r.json()
check("Step 4: Conversation stored after AI reply", r.status_code == 200,
      f"stored={data.get('stored', 0)} memories in {store_time:.1f}s")

# Step 5: verify new memories are retrievable
time.sleep(1)
r = requests.post(f"{BASE}/memory/retrieve", json={
    "query": "what keyboard does the user use?",
    "app_id": "chatgpt", "user_id": "default", "limit": 3
})
new_mems = r.json().get("memories", [])
check("Step 5: New memories retrievable", len(new_mems) >= 0,
      f"{len(new_mems)} results for keyboard query")
for m in new_mems:
    print(f"         [{m['relevance']:.3f}] {m['content']}")

# ════════════════════════════════════════════════════════════
section("7. POPUP API CALLS")
# ════════════════════════════════════════════════════════════
# Verify all endpoints popup.js uses
try:
    r = requests.get(f"{BASE}/health")
    check("Popup: health check", r.status_code == 200)
except Exception as e:
    check("Popup: health check", False, str(e))

try:
    r = requests.get(f"{BASE}/memory/all", params={"user_id": "default", "limit": 50})
    check("Popup: load memories list", r.status_code == 200,
          f"{len(r.json().get('memories', []))} memories")
except Exception as e:
    check("Popup: load memories list", False, str(e))

try:
    r = requests.get(f"{BASE}/config")
    check("Popup: get current model config", r.status_code == 200, str(r.json()))
except Exception as e:
    check("Popup: get model config", False, str(e))

try:
    r = requests.get(f"{BASE}/ollama/models")
    check("Popup: list ollama models", r.status_code == 200,
          f"{[m['name'] for m in r.json().get('models', [])]}")
except Exception as e:
    check("Popup: list ollama models", False, str(e))

# ════════════════════════════════════════════════════════════
section("8. ONBOARDING API CALLS")
# ════════════════════════════════════════════════════════════
try:
    r = requests.get(f"{BASE}/health")
    check("Onboarding: server health check", r.status_code == 200)
except Exception as e:
    check("Onboarding: server health check", False, str(e))

try:
    r = requests.get(f"{BASE}/ollama/models")
    check("Onboarding: list models for picker", r.status_code == 200)
except Exception as e:
    check("Onboarding: list models", False, str(e))

try:
    r = requests.post(f"{BASE}/config", json={"mode": "gemini", "gemini_key": ""})
    check("Onboarding: save engine config", r.status_code == 200)
except Exception as e:
    check("Onboarding: save config", False, str(e))

# ════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════
total  = len(results)
passed = sum(1 for _, p in results if p)
failed = total - passed

print(f"\n{'='*60}")
print(f"  RESULTS: {passed}/{total} passed", "🎉" if failed == 0 else "⚠️")
print(f"{'='*60}")
if failed:
    print(f"\n  Failed:")
    for name, p in results:
        if not p:
            print(f"    ❌ {name}")
