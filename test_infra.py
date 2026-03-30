import os, sys, json, requests
from dotenv import load_dotenv
load_dotenv()

LONG_CONVO = (
    "User: I am a software engineer with 5 years of experience, primarily working with Python and FastAPI for backend development. "
    "I love building developer tools and open source projects. I use Neovim as my primary editor and run Arch Linux on my machine. "
    "I am currently working on an AI memory system called MnemOS that stores and retrieves memories from conversations. "
    "I drink 4 cups of coffee every day and prefer dark roast. I hate JavaScript frameworks like React but I tolerate Vue.js. "
    "My favorite programming language after Python is Rust. I play chess online in my free time and my ELO is around 1400. "
    "I also enjoy hiking on weekends and have completed several trails in the Himalayas. "
    "I am learning Japanese and can speak basic conversational phrases. "
    "I have a dog named Bruno who is a golden retriever. "
    "I prefer working late at night and my productive hours are between 11pm and 3am.\n"
    "Assistant: That is really interesting! It sounds like you have a very rich set of hobbies and skills. "
    "MnemOS sounds like a fascinating project. How does the memory retrieval work exactly?\n"
    "User: It uses pgvector for similarity search with bge-m3 embeddings. "
    "When I type a message, it embeds the query, does cosine similarity search, and injects the top memories as context. "
    "I am also using Gemini Flash for memory extraction from conversations."
)

# ── 1. TEST GEMINI ─────────────────────────────────────────────────────────
print("\n" + "="*60)
print("TEST 1: GEMINI EXTRACTION")
print("="*60)

key = os.getenv("GEMINI_API_KEY")
if not key:
    print("FAIL: GEMINI_API_KEY not set")
    sys.exit(1)

print(f"Key loaded: {key[:12]}...")

prompt = (
    'You are a memory extraction system. Extract ALL facts worth remembering from this conversation.\n\n'
    'Return ONLY valid JSON: {"memories": [{"content": "...", "type": "semantic", "confidence": 0.9, "tags": []}]}\n\n'
    'Rules:\n'
    '- Extract EVERY user preference, hobby, tool, skill, topic, decision, and fact mentioned\n'
    '- Be generous — extract as much as possible\n\n'
    f'Conversation:\n{LONG_CONVO}\n\nJSON:'
)

resp = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
    headers={"Content-Type": "application/json"},
    json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
    },
)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    print(f"Raw response (first 800 chars):\n{text[:800]}")
    import re
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        data = json.loads(cleaned)
        mems = data.get("memories", [])
        print(f"\nSUCCESS: Extracted {len(mems)} memories")
        for i, m in enumerate(mems, 1):
            print(f"  {i}. [{m.get('type','?')}] {m.get('content','')}")
    except Exception as e:
        print(f"JSON parse error: {e}")
else:
    print(f"Error: {resp.text[:300]}")

# ── 2. TEST OLLAMA EMBEDDINGS ──────────────────────────────────────────────
print("\n" + "="*60)
print("TEST 2: OLLAMA bge-m3 EMBEDDINGS")
print("="*60)

ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
embed_model = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
print(f"URL: {ollama_url}  Model: {embed_model}")

test_text = "I am a software engineer who loves Python and Rust"
try:
    resp = requests.post(
        f"{ollama_url}/api/embed",
        json={"model": embed_model, "input": test_text},
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        emb = resp.json()["embeddings"][0]
        print(f"SUCCESS: Embedding dim = {len(emb)}")
        print(f"Sample (first 5 values): {emb[:5]}")
    else:
        print(f"Error: {resp.text[:200]}")
except Exception as e:
    print(f"FAIL: {e}")
