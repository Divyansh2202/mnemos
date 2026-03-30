import time, json, re, requests, os
from dotenv import load_dotenv
load_dotenv()

LONG_CONVO = (
    "User: I am a 27-year-old software engineer based in Delhi, India. "
    "I have been coding for about 5 years, mostly backend using Python and FastAPI. "
    "I also know Rust and have been learning it seriously for the past year — love the ownership model. "
    "I use Neovim with a heavily customized config and run Arch Linux on my main machine. "
    "At work I use a MacBook Pro M2 but at home it is all Linux. "
    "I drink 4-5 cups of coffee a day, always dark roast, no milk no sugar. "
    "I absolutely hate React and most JavaScript frameworks, though Vue.js is tolerable. "
    "I play chess online, my ELO is around 1400 on Lichess, mostly blitz. "
    "I enjoy hiking and have done trails in the Himalayas — Kedarkantha and Hampta Pass so far. "
    "I have a golden retriever named Bruno, he is 2 years old. "
    "I work best late at night, usually from 11pm to 3am is when I get into flow state. "
    "I am learning Japanese, been at it for 8 months, can hold basic conversations. "
    "My current side project is MnemOS, an AI memory system for chat apps. "
    "I am into mechanical keyboards — currently using a Keychron Q1 with Gateron Brown switches. "
    "Favorite food is Hyderabadi dum biryani. "
    "I listen to lo-fi hip hop and jazz while coding. "
    "I have a YouTube channel with about 3000 subscribers where I post dev tutorials. "
    "I am currently reading Designing Data-Intensive Applications by Martin Kleppmann. "
    "My long-term goal is to build developer tools and eventually start my own company.\n"
    "Assistant: That is impressive! MnemOS sounds fascinating. What is the biggest challenge?\n"
    "User: The hardest part was the memory injection pipeline — prepending context to the message "
    "but hiding it in the UI using a Unicode private-use character U+E000 as an invisible delimiter. "
    "Also dealt with Chrome extension context invalidation errors. "
    "Removed JSON format mode from Ollama qwen2.5:3b as it was too conservative. "
    "Now using Gemini Flash for extraction. Changed similarity threshold from 0.35 to 0.65. "
    "MnemOS stores full sessions in PostgreSQL with pgvector for semantic search."
)

PROMPT = (
    'You are a memory extraction system. Extract ALL facts worth remembering from this conversation.\n\n'
    'Return ONLY valid JSON: {{"memories": [{{"content": "...", "type": "semantic", "confidence": 0.9, "tags": []}}]}}\n\n'
    'Rules:\n'
    '- Extract EVERY user preference, hobby, tool, skill, topic, decision, and fact mentioned\n'
    '- Be generous — extract as much as possible\n\n'
    f'Conversation:\n{LONG_CONVO}\n\nJSON:'
)

def parse_memories(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text.strip())
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text).get("memories", [])
    except:
        return []

# ── GEMINI ─────────────────────────────────────────────────────
print("=" * 55)
print("GEMINI 2.5 FLASH")
print("=" * 55)
key = os.getenv("GEMINI_API_KEY")
t0 = time.time()
resp = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
    headers={"Content-Type": "application/json"},
    json={
        "contents": [{"parts": [{"text": PROMPT}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
    },
)
t1 = time.time()
if resp.status_code == 200:
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    mems = parse_memories(text)
    print(f"Time      : {t1-t0:.2f}s")
    print(f"Memories  : {len(mems)}")
    for i, m in enumerate(mems[:5], 1):
        print(f"  {i}. {m['content']}")
    if len(mems) > 5:
        print(f"  ... and {len(mems)-5} more")
else:
    print(f"FAILED: {resp.status_code} {resp.text[:200]}")

# ── QWEN2.5:3B ─────────────────────────────────────────────────
print()
print("=" * 55)
print("QWEN2.5:3B (Ollama)")
print("=" * 55)
ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
t0 = time.time()
resp = requests.post(
    f"{ollama_url}/api/generate",
    json={
        "model":   "qwen2.5:3b",
        "prompt":  PROMPT,
        "stream":  False,
        "options": {"temperature": 0.1}
    },
)
t1 = time.time()
if resp.status_code == 200:
    text = resp.json().get("response", "")
    mems = parse_memories(text)
    print(f"Time      : {t1-t0:.2f}s")
    print(f"Memories  : {len(mems)}")
    for i, m in enumerate(mems[:5], 1):
        print(f"  {i}. {m['content']}")
    if len(mems) > 5:
        print(f"  ... and {len(mems)-5} more")
    if not mems:
        print(f"  Raw (first 300): {text[:300]}")
else:
    print(f"FAILED: {resp.status_code} {resp.text[:200]}")

print()
print("=" * 55)
