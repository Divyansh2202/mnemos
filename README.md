# MnemOS — Universal Memory for AI Apps

> Give any AI app a persistent, searchable memory. Works with ChatGPT, Claude, your own apps, and any LLM — without changing a single line of their code.

```
┌─────────────────────────────────────────────────────────────────┐
│                        MnemOS Architecture                      │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  ChatGPT.com │    │  Claude.ai   │    │   Your Own App   │  │
│  │  (Extension) │    │  (Extension) │    │  (Python SDK)    │  │
│  └──────┬───────┘    └──────┬───────┘    └────────┬─────────┘  │
│         │                   │                     │            │
│         └─────────────┬─────┘                     │            │
│                       ▼                           ▼            │
│              ┌─────────────────┐        ┌──────────────────┐   │
│              │  MnemOS Server  │        │   CLI / MCP      │   │
│              │  FastAPI :8765  │        │   Integrations   │   │
│              └────────┬────────┘        └──────────────────┘   │
│                       │                                        │
│          ┌────────────┴────────────┐                           │
│          ▼                         ▼                           │
│  ┌──────────────────┐   ┌────────────────────┐                 │
│  │  Context Engine  │   │   Memory Store     │                 │
│  │  Gemini Flash or │   │  PostgreSQL +      │                 │
│  │  Ollama (local)  │   │  pgvector (cosine) │                 │
│  └──────────────────┘   └────────────────────┘                 │
│          │                         │                           │
│          ▼                         ▼                           │
│  Extract facts from        bge-m3 embeddings                   │
│  conversations             1024-dim vectors                    │
└─────────────────────────────────────────────────────────────────┘
```

## What It Does

You're talking to ChatGPT. You mention you love Python, hate React, have a dog named Bruno. You close the tab.

**Without MnemOS:** Next session — AI has no idea who you are.

**With MnemOS:** The extension silently extracts those facts, stores them as vector embeddings, and injects them into every future message — automatically. You never type your preferences twice.

---

## Full Data Flow

```
User types message
       │
       ▼
  content script (chatgpt.js / claude.js)
       │
       ├─── 1. RETRIEVE: POST /memory/retrieve
       │         query = user's message
       │         → semantic search in pgvector (cosine ≥ 0.65)
       │         → returns top-5 relevant memories
       │
       ├─── 2. INJECT: prepend context to message
       │         [Memory Context from MnemOS]
       │         - User prefers Python over JavaScript
       │         - User has a golden retriever named Bruno
       │         \uE000 <original message here>
       │         (\uE000 = invisible delimiter — AI never sees it)
       │
       ├─── 3. AI responds normally (sees full context)
       │
       └─── 4. LEARN: POST /memory/learn (on tab hide/close)
                 conversation → Context Engine (Gemini/Ollama)
                 → extract facts as JSON memories
                 → embed with bge-m3 → store in pgvector
```

---

## Components

| Component | Description |
|-----------|-------------|
| `server/` | FastAPI server — REST API for store/retrieve/learn |
| `extension/` | Chrome MV3 extension — ChatGPT + Claude support |
| `cli/` | Typer CLI — setup, model management, search |
| `sdk/python/` | Python SDK — for your own apps |
| `dashboard/` | Web UI — view/manage memories |
| `integrations/` | MCP server — Claude Desktop integration |
| `protocol/` | Shared Pydantic types |

---

## Quick Start

### 1. Prerequisites

- Docker (for PostgreSQL)
- Python 3.10+
- Ollama (for local embeddings) **or** Gemini API key (cloud extraction)

### 2. Install

```bash
git clone https://github.com/Divyansh2202/mnemos.git
cd mnemos
python3 -m venv myenv
source myenv/bin/activate
pip install -e .
```

### 3. Setup (interactive)

```bash
mnemos init
```

```
╭─────────────────╮
│  MnemOS Setup   │
╰─────────────────╯

Step 1: Choose extraction engine
  1  Gemini 2.5 Flash  (fast, cloud, needs API key)
  2  Ollama            (local, private, needs GPU/CPU)
Engine [1]: 1
Gemini API key (from aistudio.google.com): AIzaSy...

✓ Gemini key saved
✓ Config saved → gemini

Next steps:
  1. Start PostgreSQL:  mnemos db-start
  2. Start server:      mnemos start
  3. Check health:      mnemos doctor
```

### 4. Start services

```bash
mnemos db-start    # starts PostgreSQL via Docker
mnemos start       # starts MnemOS server on :8765
```

### 5. Verify everything works

```bash
mnemos doctor
```

```
╭──────────────────────╮
│  MnemOS Health Check │
╰──────────────────────╯
✓ MnemOS server    running
✓ Ollama binary    found at /usr/bin/ollama
✓ Ollama server    running  (3 models)
  ✓ bge-m3
  ✓ qwen2.5:3b
✓ PostgreSQL       running

All systems go!
```

### 6. Install the Chrome Extension

1. Open `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `extension/` folder

On first install, the **onboarding wizard** opens automatically:

```
Step 1 — Check Server
  ✅  MnemOS server is running at localhost:8765

Step 2 — Choose Extraction Engine
  ○  Gemini 2.5 Flash  [API Key: ____________]
  ●  Ollama (local)
     Model: [qwen2.5:3b ▼]  [Download]

Step 3 — Done!
  ✓ Memory injection active on ChatGPT and Claude
```

---

## CLI Reference

```
mnemos init              Interactive setup wizard
mnemos db-start          Start PostgreSQL (Docker)
mnemos install-ollama    Download Ollama binary (no sudo)
mnemos serve-ollama      Start Ollama server
mnemos pull-models       Download bge-m3 + qwen2.5:3b
mnemos start             Start MnemOS server
mnemos doctor            Health check all components
mnemos stats             Memory store statistics
mnemos list              List all stored memories
mnemos search <query>    Semantic search through memories
mnemos model             View current extraction config
mnemos model --list      Show all models + download status
mnemos model --pull <m>  Download an Ollama model
mnemos model --engine <e> --name <m>  Switch model
mnemos mcp-config        Print Claude Desktop MCP config
```

### Model switching examples

```bash
# Switch to Gemini
mnemos model --engine gemini

# Switch to Ollama with a specific model
mnemos model --engine ollama --name qwen2.5:7b

# Download a new model
mnemos model --pull qwen2.5:14b

# List all available models
mnemos model --list
```

```
╭────────────────╮
│  Ollama Models │
╰────────────────╯
Model          Size    Notes                  Downloaded
qwen2.5:0.5b   0.4 GB  Fastest, lowest quality    —
qwen2.5:1.5b   1.0 GB  Fast, decent quality        —
qwen2.5:3b     1.9 GB  Balanced (default)          ✓
qwen2.5:7b     4.7 GB  Good quality                —
qwen2.5:14b    9.0 GB  High quality                —
qwen2.5:32b    20 GB   Very high quality           —
llama3.2:3b    2.0 GB  Meta Llama 3.2              —
mistral:7b     4.1 GB  Mistral 7B                  —
phi3:mini      2.2 GB  Microsoft Phi-3 Mini        —
```

---

## Python SDK

```python
from mnemos import MnemOS

mem = MnemOS(app_id="my-app", user_id="user-123")

# Store a memory manually
mem.store("User prefers dark mode and large fonts")

# Semantic search
results = mem.retrieve("what are the user's UI preferences?")
# → [{"content": "User prefers dark mode...", "relevance": 0.87}, ...]

# Auto-extract from conversation
mem.learn([
    {"role": "user",      "content": "I hate React, I only use Vue."},
    {"role": "assistant", "content": "Vue is great for smaller apps!"},
])

# Inject context into your AI calls
system_prompt = mem.inject("user preferences")
# → "[Relevant memories about this user]\n1. User prefers dark mode..."

response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]
)

# Model management
mem.set_model(engine="gemini")
mem.set_model(engine="ollama", model="qwen2.5:7b")
models = mem.list_models()
mem.pull_model("qwen2.5:14b")
```

---

## REST API

```
GET  /health                      Server health check
GET  /stats                       Memory store statistics
GET  /config                      Get current extraction config
POST /config                      Update extraction config

POST /memory/store                Store a memory manually
POST /memory/retrieve             Semantic search
POST /memory/learn                Extract + store from conversation
GET  /memory/all                  List all memories
DELETE /memory/{id}               Delete a memory

GET  /sessions                    List conversation sessions
GET  /sessions/{session_id}       Get full session with messages

GET  /ollama/models               List downloaded Ollama models
POST /ollama/pull                 Download an Ollama model
```

### Example: Store and retrieve

```bash
# Store
curl -X POST http://localhost:8765/memory/store \
  -H "Content-Type: application/json" \
  -d '{"content": "User loves dark roast coffee, no milk", "app_id": "myapp", "user_id": "alice"}'

# Retrieve
curl -X POST http://localhost:8765/memory/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "what does the user drink?", "app_id": "myapp", "user_id": "alice", "limit": 5}'
```

### Example: Learn from conversation

```bash
curl -X POST http://localhost:8765/memory/learn \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I work with Python and FastAPI. I love Rust."},
      {"role": "assistant", "content": "That is a great combo for backend work!"}
    ],
    "app_id": "chatgpt",
    "user_id": "default",
    "session_id": "session_001"
  }'
```

Response:
```json
{
  "stored": 3,
  "memories": [
    {"id": "mem_abc123", "content": "User works with Python and FastAPI"},
    {"id": "mem_def456", "content": "User loves Rust programming language"},
    {"id": "mem_ghi789", "content": "User is a backend engineer"}
  ]
}
```

---

## Extension Deep Dive

### Files

```
extension/
├── manifest.json              Chrome MV3 manifest
├── background.js              Service worker — message hub, queue
├── content/
│   ├── chatgpt.js             ChatGPT injection + extraction
│   └── claude.js              Claude.ai injection + extraction
├── popup/
│   ├── popup.html             Extension popup UI
│   ├── popup.js               Memory list + model switcher
│   └── popup.css              Styles
└── onboarding/
    └── onboarding.html        First-install setup wizard
```

### How the extension handles each message

```
User types → Enter key pressed
                │
                ├── isTrusted check (blocks synthetic events = no infinite loop)
                ├── runtimeOk() check (blocks if extension context invalid)
                │
                ├── Retrieve memories → POST /memory/retrieve
                │   Returns top-5 semantically relevant facts
                │
                ├── Inject: prepend [Memory Context from MnemOS]\n{facts}\n\uE000
                │   \uE000 (U+E000) is an invisible delimiter in Private Use Area
                │   The AI never sees it — it's stripped before storage
                │
                ├── Dispatch synthetic Enter event (isTrusted: false)
                │   Content script ignores this → no infinite loop
                │
                └── On visibilitychange / beforeunload:
                    Strip \uE000 prefix from messages (cleanMessages)
                    POST /memory/learn → extract + store conversation
```

### Queue system

Background.js uses a persistent queue (`mnemos_queue` in `chrome.storage.sync`) to handle offline/slow server scenarios:
- Requests added to queue if server is unreachable
- Queue processed in order when server comes back up
- Retry logic with exponential backoff

---

## MCP Integration (Claude Desktop)

```bash
mnemos mcp-config
```

Copy the output into `~/.config/claude/claude_desktop_config.json`. Claude Desktop will then have a `mnemos` tool that can read and write memories directly from conversation.

---

## Extraction Engines

### Gemini 2.5 Flash (recommended)

- Speed: ~13 seconds for a long conversation
- Quality: Extracts 15-30 memories from a rich conversation
- Cost: ~$0.001 per conversation (very cheap)
- Setup: Get API key from [aistudio.google.com](https://aistudio.google.com)

### Ollama (local / private)

- Speed: Depends on model size and hardware
- Privacy: 100% local, no data leaves your machine
- Cost: Free
- Recommended model: `qwen2.5:3b` (balanced), `qwen2.5:7b` (better quality)

### Benchmark (same long conversation)

| Engine | Time | Memories Extracted | Quality |
|--------|------|-------------------|---------|
| Gemini 2.5 Flash | 13s | 34 | Excellent — every fact captured |
| qwen2.5:3b (Ollama) | 429s | 2 | Poor — copied input instead of extracting |
| qwen2.5:7b (Ollama) | ~60s | 15-20 | Good |

**Recommendation:** Use Gemini for extraction (fast, cheap, high quality). Use Ollama only for embeddings (bge-m3 — always local).

---

## Embeddings

Always uses **bge-m3** via Ollama (local):
- Dimension: 1024
- Speed: ~0.25s per embed
- Similarity threshold for retrieval: **0.65** (cosine)
- Deduplication threshold: **0.88** (exact text match first, then cosine)

---

## Problems Solved

### 1. Infinite loop on Enter key
**Problem:** Content script dispatches a synthetic Enter keypress to submit the injected message — but this triggers the content script again → infinite loop.

**Solution:** Check `e.isTrusted`. Real user keypresses have `isTrusted: true`. Synthetic events dispatched by script have `isTrusted: false`. Content script ignores non-trusted events.

### 2. Memory injection flicker
**Problem:** When prepending context to the textarea, the text briefly appears visible to the user before the message sends.

**Solution:** `bubbleObserver` — a `MutationObserver` that watches for the "thinking" bubble appearing in the chat. When it appears, the memory prefix is already gone (it was stripped before the user sees the AI respond).

### 3. Extension context invalidation
**Problem:** Chrome can invalidate the extension context (e.g., after an update). Any `chrome.*` API call after invalidation throws an uncatchable error.

**Solution:** `runtimeOk()` guard — checks `chrome.runtime.id` before any API call. If undefined, the content script goes silent instead of throwing.

### 4. AI extracting "Divyansh knows Python" instead of "User knows Python"
**Problem:** If the user's name appeared in conversation, Gemini/Ollama would use their real name in extracted memories. Retrieval queries use "user" → no match.

**Solution:** Hard rule in extraction prompt: `ALWAYS start every memory with "User" — never use the person's real name`.

### 5. Similarity threshold tuning
**Problem:** Threshold 0.80 returned 0 results because bge-m3 cosine scores for semantically related (but not identical) text top out at 0.66–0.82.

**Solution:** Tested 0.80 → 0.70 → 0.65. At 0.65, the right memories are retrieved without noise.

### 6. Gemini JSON truncation
**Problem:** Gemini was cutting off the JSON response mid-array. Result: `JSONDecodeError at char 3952`.

**Solution:** `maxOutputTokens` was set to 1024. Changed to 8192 — fits even the largest memory arrays.

### 7. Duplicate memory accumulation
**Problem:** Re-sending the same conversation extracted the same facts again, doubling stored memories.

**Solution:** Two-step dedup in `_find_duplicate`:
1. Exact text match (fast, no embedding)
2. Cosine similarity ≥ 0.88 (catches paraphrases)

If duplicate found → boost `confidence` by 0.05 instead of inserting.

### 8. No-code onboarding for non-technical users
**Problem:** Extension users aren't developers. They can't run terminal commands to download Ollama, start PostgreSQL, or set API keys.

**Solution:** `onboarding.html` — a full GUI wizard that opens automatically on first install:
- Checks server health with ✅/❌
- Shows engine picker with API key input
- Lists available models with Download buttons
- Zero terminal commands needed

---

## Configuration

### Environment variables (`.env`)

```env
POSTGRES_URL=postgresql://mnemos:mnemos@localhost:5432/mnemos
OLLAMA_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=bge-m3
OLLAMA_GEN_MODEL=qwen2.5:3b
MNEMOS_EXTRACTION=gemini
GEMINI_API_KEY=your_key_here
MNEMOS_HOST=localhost
MNEMOS_PORT=8765
```

### Runtime config (`mnemos_config.json`)

```json
{
  "mode": "gemini",
  "gen_model": "qwen2.5:3b"
}
```

This file is written by `mnemos init`, the CLI `model` command, the extension popup, and the dashboard. It survives server restarts and syncs across all interfaces.

---

## Docker Compose (PostgreSQL + pgvector)

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: mnemos
      POSTGRES_USER: mnemos
      POSTGRES_PASSWORD: mnemos
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

---

## Setup.py / pip install

```bash
pip install -e .
```

This installs the `mnemos` CLI entry point and the Python SDK.

```python
# entry_points in setup.py
"console_scripts": ["mnemos=cli.main:app"]
```

---

## Running Tests

```bash
source myenv/bin/activate

# Full end-to-end test (requires server running)
python3 test_complete.py

# Extension API + pattern test
python3 test_extension.py

# Gemini vs Ollama benchmark
python3 test_extraction_benchmark.py
```

---

## Memory Privacy Levels

| Level | Description |
|-------|-------------|
| `global` | Shared across all apps for this user |
| `app_shared` | Visible to all instances of the same app |
| `private` | Only visible within the specific app that stored it |

---

## License

MIT
