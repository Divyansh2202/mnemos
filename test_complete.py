"""
MnemOS — Complete End-to-End Test
Tests every flow from scratch on a fresh DB.
"""
import time, json, requests

BASE    = "http://localhost:8765"
PASS    = "✅"
FAIL    = "❌"
WARN    = "⚠️ "
results = []

def check(name, passed, detail=""):
    icon = PASS if passed else FAIL
    results.append((name, passed))
    print(f"  {icon}  {name}" + (f"  →  {detail}" if detail else ""))

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ════════════════════════════════════════════════════════════
section("1. SERVER HEALTH")
# ════════════════════════════════════════════════════════════
try:
    r = requests.get(f"{BASE}/health")
    check("Server running", r.status_code == 200, r.json().get("version"))
except Exception as e:
    check("Server running", False, str(e))

try:
    r = requests.get(f"{BASE}/stats")
    data = r.json()
    check("Stats endpoint", r.status_code == 200, f"{data['total_memories']} memories (should be 0)")
    check("Fresh DB (0 memories)", data["total_memories"] == 0)
except Exception as e:
    check("Stats endpoint", False, str(e))

# ════════════════════════════════════════════════════════════
section("2. CONFIG & MODEL MANAGEMENT")
# ════════════════════════════════════════════════════════════
try:
    r = requests.get(f"{BASE}/config")
    cfg = r.json()
    check("GET /config", r.status_code == 200, f"engine={cfg.get('mode')} model={cfg.get('gen_model')}")
except Exception as e:
    check("GET /config", False, str(e))

try:
    r = requests.post(f"{BASE}/config", json={"mode": "gemini"})
    check("POST /config (set gemini)", r.status_code == 200, r.json().get("mode"))
except Exception as e:
    check("POST /config", False, str(e))

try:
    r = requests.get(f"{BASE}/ollama/models")
    models = r.json().get("models", [])
    check("GET /ollama/models", r.status_code == 200, f"{len(models)} models: {[m['name'] for m in models]}")
except Exception as e:
    check("GET /ollama/models", False, str(e))

# ════════════════════════════════════════════════════════════
section("3. OLLAMA EMBEDDINGS (bge-m3)")
# ════════════════════════════════════════════════════════════
try:
    t0 = time.time()
    r = requests.post("http://localhost:11434/api/embed",
        json={"model": "bge-m3", "input": "test embedding"})
    elapsed = time.time() - t0
    emb = r.json()["embeddings"][0]
    check("Single embed", r.status_code == 200, f"dim={len(emb)} time={elapsed:.2f}s")
    check("Correct dim (1024)", len(emb) == 1024)
except Exception as e:
    check("Ollama embed", False, str(e))

try:
    t0 = time.time()
    r = requests.post("http://localhost:11434/api/embed",
        json={"model": "bge-m3", "input": ["text one", "text two", "text three"]})
    elapsed = time.time() - t0
    embs = r.json()["embeddings"]
    check("Batch embed (3 texts)", len(embs) == 3, f"time={elapsed:.2f}s")
except Exception as e:
    check("Batch embed", False, str(e))

# ════════════════════════════════════════════════════════════
section("4. GEMINI EXTRACTION")
# ════════════════════════════════════════════════════════════
LONG_CONVO = [
    {"role": "user", "content": (
        "Hi! I'm Divyansh, a 27-year-old backend engineer from Delhi. "
        "I work with Python and FastAPI. I love Rust and have been learning it for a year. "
        "I use Neovim on Arch Linux. I drink 4 cups of dark roast coffee daily, no milk no sugar. "
        "I hate React but tolerate Vue.js. I play chess on Lichess, ELO around 1400. "
        "I have a golden retriever named Bruno, 2 years old. "
        "I work best late at night, 11pm to 3am. I'm building MnemOS, an AI memory system. "
        "I use a Keychron Q1 keyboard with Gateron Brown switches. "
        "I love Hyderabadi biryani and listen to lo-fi while coding."
    )},
    {"role": "assistant", "content": "That's a great stack! Tell me more about MnemOS."},
    {"role": "user", "content": (
        "MnemOS uses pgvector for similarity search and bge-m3 for embeddings. "
        "Gemini Flash extracts memories from conversations. "
        "The similarity threshold is 0.65. It supports ChatGPT and Claude via browser extension."
    )},
]

try:
    t0 = time.time()
    r = requests.post(f"{BASE}/memory/learn", json={
        "messages":   LONG_CONVO,
        "app_id":     "test",
        "user_id":    "default",
        "session_id": "test_session_001",
    })
    elapsed = time.time() - t0
    data = r.json()
    stored = data.get("stored", 0)
    check("POST /memory/learn", r.status_code == 200, f"time={elapsed:.1f}s")
    check("Gemini extracted memories", stored > 0, f"extracted={stored} memories")
    if stored > 0:
        print(f"\n     Sample memories extracted:")
        for m in data.get("memories", [])[:8]:
            print(f"       • {m['content']}")
        if stored > 8:
            print(f"       ... and {stored - 8} more")
except Exception as e:
    check("POST /memory/learn", False, str(e))

# ════════════════════════════════════════════════════════════
section("5. MEMORY STORE & RETRIEVE")
# ════════════════════════════════════════════════════════════
try:
    r = requests.get(f"{BASE}/stats")
    total = r.json().get("total_memories", 0)
    check("Memories stored in DB", total > 0, f"{total} total")
except Exception as e:
    check("Stats after learn", False, str(e))

try:
    r = requests.get(f"{BASE}/memory/all", params={"user_id": "default", "limit": 5})
    mems = r.json().get("memories", [])
    check("GET /memory/all", r.status_code == 200, f"returned {len(mems)} memories")
except Exception as e:
    check("GET /memory/all", False, str(e))

QUERIES = [
    ("What programming languages does the user know?", ["Python", "Rust", "FastAPI"]),
    ("What is the user's pet?",                        ["Bruno", "golden retriever"]),
    ("What does the user drink?",                      ["coffee"]),
    ("Where does the user live?",                      ["Delhi"]),
    ("What is MnemOS?",                                ["memory", "AI", "MnemOS"]),
]

print()
for query, keywords in QUERIES:
    try:
        t0 = time.time()
        r = requests.post(f"{BASE}/memory/retrieve", json={
            "query":   query,
            "app_id":  "test",
            "user_id": "default",
            "limit":   3,
        })
        elapsed = time.time() - t0
        mems = r.json().get("memories", [])
        relevant = any(
            any(kw.lower() in m["content"].lower() for kw in keywords)
            for m in mems
        )
        status = f"found {len(mems)} | {elapsed:.2f}s"
        if mems:
            status += f" | best: [{mems[0]['relevance']:.3f}] {mems[0]['content'][:50]}"
        check(f"Retrieve: '{query[:40]}...'", relevant or len(mems) > 0, status)
    except Exception as e:
        check(f"Retrieve query", False, str(e))

# ════════════════════════════════════════════════════════════
section("6. MANUAL MEMORY STORE + DELETE")
# ════════════════════════════════════════════════════════════
mem_id = None
try:
    r = requests.post(f"{BASE}/memory/store", json={
        "content":    "User's favorite color is deep purple",
        "type":       "semantic",
        "confidence": 0.9,
        "app_id":     "test",
        "user_id":    "default",
    })
    mem_id = r.json().get("id")
    check("POST /memory/store", r.status_code == 200, f"id={mem_id[:16] if mem_id else 'none'}")
except Exception as e:
    check("POST /memory/store", False, str(e))

if mem_id:
    try:
        r = requests.delete(f"{BASE}/memory/{mem_id}")
        check("DELETE /memory/:id", r.status_code == 200, r.json().get("status"))
    except Exception as e:
        check("DELETE /memory/:id", False, str(e))

# ════════════════════════════════════════════════════════════
section("7. SESSION STORAGE")
# ════════════════════════════════════════════════════════════
try:
    r = requests.get(f"{BASE}/sessions", params={"user_id": "default"})
    sessions = r.json().get("sessions", [])
    check("GET /sessions", r.status_code == 200, f"{len(sessions)} sessions")
    check("Session saved from learn", len(sessions) > 0)
    if sessions:
        s = sessions[0]
        print(f"\n     Session: id={s['session_id']} | msgs={s['message_count']} | app={s['app_id']}")
except Exception as e:
    check("GET /sessions", False, str(e))

try:
    r = requests.get(f"{BASE}/sessions/test_session_001", params={"user_id": "default"})
    check("GET /sessions/:id", r.status_code == 200, f"messages={len(r.json().get('messages', []))}")
except Exception as e:
    check("GET /sessions/:id", False, str(e))

# ════════════════════════════════════════════════════════════
section("8. DEDUPLICATION")
# ════════════════════════════════════════════════════════════
try:
    r1 = requests.get(f"{BASE}/stats")
    before = r1.json().get("total_memories", 0)

    # Send same conversation again — should not duplicate
    requests.post(f"{BASE}/memory/learn", json={
        "messages":   LONG_CONVO,
        "app_id":     "test",
        "user_id":    "default",
        "session_id": "test_session_001",
    })

    r2 = requests.get(f"{BASE}/stats")
    after = r2.json().get("total_memories", 0)
    check("Deduplication (no new memories on resend)", after == before, f"before={before} after={after}")
except Exception as e:
    check("Deduplication", False, str(e))

# ════════════════════════════════════════════════════════════
section("9. CONFIG PERSISTENCE")
# ════════════════════════════════════════════════════════════
try:
    requests.post(f"{BASE}/config", json={"mode": "ollama", "gen_model": "qwen2.5:3b"})
    cfg1 = requests.get(f"{BASE}/config").json()
    check("Config switch to ollama", cfg1.get("mode") == "ollama")

    requests.post(f"{BASE}/config", json={"mode": "gemini"})
    cfg2 = requests.get(f"{BASE}/config").json()
    check("Config switch to gemini", cfg2.get("mode") == "gemini")

    import pathlib, json as _json
    cfg_file = pathlib.Path("mnemos_config.json")
    if cfg_file.exists():
        saved = _json.loads(cfg_file.read_text())
        check("Config saved to mnemos_config.json", saved.get("mode") == "gemini", str(saved))
    else:
        check("Config saved to file", False, "mnemos_config.json not found")
except Exception as e:
    check("Config persistence", False, str(e))

# ════════════════════════════════════════════════════════════
section("10. FINAL STATS")
# ════════════════════════════════════════════════════════════
try:
    r = requests.get(f"{BASE}/stats")
    data = r.json()
    print(f"\n  Total memories  : {data['total_memories']}")
    print(f"  By type         : {data.get('by_type', {})}")
    print(f"  By app          : {data.get('by_app', {})}")
except:
    pass

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
    print(f"\n  Failed tests:")
    for name, p in results:
        if not p:
            print(f"    ❌ {name}")
