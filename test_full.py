import time, json, requests
from dotenv import load_dotenv
load_dotenv()

BASE = "http://localhost:8765"

LONG_CONVO = [
    {"role": "user", "content": (
        "Hey! Let me tell you a bit about myself. I'm a 27-year-old software engineer based in Delhi, India. "
        "I've been coding for about 5 years now, mostly backend stuff using Python and FastAPI. "
        "I also know Rust and I've been learning it seriously for the past year — love the ownership model. "
        "I use Neovim with a heavily customized config and I run Arch Linux on my main machine. "
        "At work I use a MacBook Pro M2 but at home it's all Linux. "
        "I drink way too much coffee — like 4-5 cups a day, always dark roast, no milk no sugar. "
        "I absolutely hate React and most JavaScript frameworks honestly, though Vue.js is tolerable. "
        "I play chess online, my ELO is around 1400 on Lichess. I play mostly blitz. "
        "I enjoy hiking and have done trails in the Himalayas — Kedarkantha and Hampta Pass so far. "
        "I have a golden retriever named Bruno, he's 2 years old. "
        "I work best late at night, usually from 11pm to 3am is when I get into flow state. "
        "I'm also learning Japanese — been at it for 8 months, can hold basic conversations. "
        "My current side project is MnemOS, an AI memory system for chat apps. "
        "I'm into mechanical keyboards — currently using a Keychron Q1 with Gateron Brown switches. "
        "Favorite food is biryani, specifically Hyderabadi dum biryani. "
        "I listen to lo-fi hip hop and jazz while coding. "
        "I have a YouTube channel where I post dev tutorials, about 3000 subscribers. "
        "I read a lot — currently reading 'Designing Data-Intensive Applications' by Martin Kleppmann. "
        "My long-term goal is to build developer tools and eventually start my own company."
    )},
    {"role": "assistant", "content": (
        "That's a really impressive background! The combination of Python, Rust, and systems thinking is powerful. "
        "MnemOS sounds like a fascinating project — using pgvector for semantic search is a smart approach. "
        "Kedarkantha is a beautiful trek, especially in winter. "
        "What's the biggest technical challenge you've faced with MnemOS so far?"
    )},
    {"role": "user", "content": (
        "The hardest part was the memory injection pipeline — making sure the context gets prepended to the user message "
        "before it's sent to the AI, but hiding it from the UI so the user only sees their original message. "
        "I used a Unicode private-use character (U+E000) as an invisible delimiter between the injected context and the real message. "
        "Also had to deal with Chrome extension context invalidation errors when the extension reloads. "
        "Another issue was Ollama's qwen2.5:3b model being too conservative with JSON format mode — had to remove that. "
        "Now using Gemini Flash for extraction which is much better. "
        "The similarity threshold was 0.35 which was too low — I just changed it to 0.80 for better precision. "
        "I'm also storing full conversation sessions in PostgreSQL alongside the extracted memories. "
        "The deduplication uses 0.92 cosine similarity threshold to avoid storing nearly identical memories."
    )},
    {"role": "assistant", "content": (
        "The U+E000 delimiter trick is clever — it's invisible in the DOM but survives text node manipulation. "
        "Using 0.92 for dedup and 0.80 for retrieval gives you a tight precision-recall tradeoff. "
        "Are you planning to add multi-user support or keep it single-user for now?"
    )},
    {"role": "user", "content": (
        "Single user for now, but the schema already has user_id so it's ready for multi-user. "
        "I plan to add a REST SDK so other developers can integrate MnemOS into their own apps. "
        "Also thinking about adding memory decay — older memories that haven't been accessed should lose confidence over time. "
        "And I want to support Gemini, ChatGPT and Claude as content script targets — currently have ChatGPT and Claude done. "
        "Eventually I want to open source this and maybe monetize via a hosted cloud version. "
        "My tech stack for the server is FastAPI + PostgreSQL + pgvector + Ollama (for embeddings) + Gemini (for extraction). "
        "The extension is vanilla JS, no framework, MV3 manifest."
    )},
]

print("=" * 65)
print("FULL PIPELINE TEST — STORE + RETRIEVE")
print("=" * 65)

# ── 1. LEARN (store conversation) ──────────────────────────────
print("\n[1] Sending long conversation to /memory/learn ...")
t0 = time.time()
resp = requests.post(f"{BASE}/memory/learn", json={
    "messages":   LONG_CONVO,
    "app_id":     "test",
    "user_id":    "default",
    "session_id": "test_session_001",
})
t1 = time.time()

print(f"    Status : {resp.status_code}")
print(f"    Total  : {t1-t0:.2f}s  (Gemini extraction + Ollama embed + DB write)")
if resp.status_code == 200:
    data = resp.json()
    print(f"    Stored : {data['stored']} memories")
    print("\n    Extracted memories:")
    for i, m in enumerate(data.get("memories", []), 1):
        print(f"      {i:02d}. {m['content']}")
else:
    print(f"    Error: {resp.text[:300]}")

# ── 2. Time Gemini alone ────────────────────────────────────────
print("\n[2] Timing Gemini extraction alone ...")
import os, re
key = os.getenv("GEMINI_API_KEY")
convo_text = "\n".join(
    f"{m['role'].capitalize()}: {m['content']}" for m in LONG_CONVO
)
prompt = (
    'You are a memory extraction system. Extract ALL facts worth remembering.\n'
    'Return ONLY valid JSON: {"memories": [{"content": "...", "type": "semantic", "confidence": 0.9, "tags": []}]}\n\n'
    f'Conversation:\n{convo_text}\n\nJSON:'
)
t0 = time.time()
gr = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
    headers={"Content-Type": "application/json"},
    json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
    },
)
t1 = time.time()
print(f"    Status : {gr.status_code}")
print(f"    Time   : {t1-t0:.2f}s")
if gr.status_code == 200:
    raw = gr.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw.strip())
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    try:
        mems = json.loads(raw).get("memories", [])
        print(f"    Memories extracted: {len(mems)}")
    except:
        print("    JSON parse error (response may be fine but truncated in test)")

# ── 3. Time Ollama embedding alone ──────────────────────────────
print("\n[3] Timing Ollama bge-m3 embed (single text) ...")
t0 = time.time()
er = requests.post("http://localhost:11434/api/embed", json={
    "model": "bge-m3",
    "input": "software engineer Python Rust Neovim Arch Linux"
})
t1 = time.time()
print(f"    Status : {er.status_code}")
print(f"    Time   : {t1-t0:.2f}s")
if er.status_code == 200:
    print(f"    Dim    : {len(er.json()['embeddings'][0])}")

# ── 4. RETRIEVE ─────────────────────────────────────────────────
print("\n[4] Retrieving memories for test queries ...")
queries = [
    "What programming languages does the user know?",
    "What are the user's hobbies?",
    "Tell me about the user's pet",
    "What is MnemOS?",
    "What does the user drink?",
]
for q in queries:
    t0 = time.time()
    rr = requests.post(f"{BASE}/memory/retrieve", json={
        "query":   q,
        "app_id":  "test",
        "user_id": "default",
        "limit":   3,
    })
    t1 = time.time()
    data = rr.json()
    mems = data.get("memories", [])
    print(f"\n    Query : \"{q}\"")
    print(f"    Time  : {t1-t0:.2f}s  | Found: {len(mems)}")
    for m in mems:
        print(f"      [{m['relevance']:.3f}] {m['content']}")

# ── 5. STATS ────────────────────────────────────────────────────
print("\n[5] DB Stats ...")
sr = requests.get(f"{BASE}/stats")
print(f"    {sr.json()}")

print("\n" + "=" * 65)
print("TEST COMPLETE")
print("=" * 65)
