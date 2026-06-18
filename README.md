<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=32&duration=3000&pause=1000&color=6E40C9&center=true&vCenter=true&width=600&lines=%E2%AC%A1+MnemOS;Universal+Memory+for+AI+Apps;One+memory%2C+every+AI." alt="MnemOS" />

<br/>

**Give persistent memory to ChatGPT, Claude, and any AI tool — without changing how you use them.**

<br/>

<a href="https://github.com/Divyansh2202/mnemos/stargazers">
  <img src="https://img.shields.io/github/stars/Divyansh2202/mnemos?style=flat-square&color=6E40C9&labelColor=1a1a2e" />
</a>
<a href="https://github.com/Divyansh2202/mnemos/blob/main/LICENSE">
  <img src="https://img.shields.io/badge/License-MIT-10B981?style=flat-square&labelColor=1a1a2e" />
</a>
<img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white&labelColor=1a1a2e" />
<img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white&labelColor=1a1a2e" />
<img src="https://img.shields.io/badge/pgVector-316192?style=flat-square&logo=postgresql&logoColor=white&labelColor=1a1a2e" />
<img src="https://img.shields.io/badge/Chrome_Extension-4285F4?style=flat-square&logo=googlechrome&logoColor=white&labelColor=1a1a2e" />
<img src="https://img.shields.io/badge/MCP-6E40C9?style=flat-square&logoColor=white&labelColor=1a1a2e" />

</div>

---

## The Problem

Every time you start a new conversation on ChatGPT or Claude, the AI has **no idea who you are**.

```
You: "I work in Python and use Neovim."
AI:  "Got it!"    ← stored nowhere

[next session]

You: "help me write a script"
AI:  "Sure! What language do you use?"   ← forgot everything
```

Your context is **locked inside each platform**. Switch from ChatGPT to Claude — start from zero. Every session is a blank slate.

---

## The Solution

MnemOS is a **Universal Memory Layer** that sits silently between you and any AI.

```
WITHOUT MnemOS                          WITH MnemOS
──────────────────────────────────      ─────────────────────────────────────
[ChatGPT]                               [ChatGPT]
You: "I love Python, I use Neovim"      You: "I love Python, I use Neovim"
AI:  "Great!"                           AI:  "Great!"  →  facts stored silently

[next session on Claude]                [next session on Claude]
You: "help me with code"                You: "help me with code"
Claude: "Sure, what language?"          Claude: "Here's Python, optimized
You: "Python..." ← repeating                    for Neovim users..."
                                        ↑ MnemOS injected your context
```

| | Without MnemOS | With MnemOS |
|--|---|---|
| Context across sessions | ❌ Lost | ✅ Persistent |
| Switch ChatGPT → Claude | ❌ Start over | ✅ Seamless |
| AI knows your preferences | ❌ Never | ✅ Always |
| Your data ownership | ❌ Platform-locked | ✅ Yours, local |

---

## ✨ Features

- 🧠 **Auto Memory** — after every conversation, silently extracts facts about you (preferences, skills, habits, projects)
- ⚡ **Smart Injection** — before every message, injects relevant memories invisibly so the AI responds as if it knows you
- 🌐 **Cross-Platform** — memory stored by user ID, not platform. ChatGPT memories work on Claude automatically
- 🔒 **Fully Private** — embeddings run locally via Ollama. Nothing leaves your machine unless you choose Gemini extraction
- 📤 **Export Conversations** — download any raw conversation as JSON and paste into any AI
- 🔌 **3 Integration Paths** — Browser Extension, Python SDK, or MCP (Claude Desktop)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              MnemOS                                      │
│                                                                         │
│  ┌───────────┐  ┌───────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  ChatGPT  │  │  Claude   │  │  Your App    │  │  Claude Desktop  │  │
│  │(Extension)│  │(Extension)│  │ (Python SDK) │  │  (MCP Server)    │  │
│  └─────┬─────┘  └─────┬─────┘  └──────┬───────┘  └────────┬─────────┘  │
│        └──────────────┴───────────────┴───────────────────┘            │
│                                    │                                    │
│                                    ▼                                    │
│                     ┌──────────────────────────┐                        │
│                     │     MnemOS Server          │                      │
│                     │     FastAPI  :8765          │                     │
│                     └──────────────┬─────────────┘                      │
│                 ┌──────────────────┴──────────────────┐                 │
│                 ▼                                      ▼                │
│   ┌───────────────────────┐              ┌──────────────────────────┐   │
│   │    Context Engine     │              │      Memory Store         │   │
│   │                       │              │                           │   │
│   │  Gemini 2.5 Flash     │              │  PostgreSQL + pgvector    │   │
│   │  (cloud, fast)        │              │  bge-m3 embeddings        │   │
│   │      — or —           │              │  1024-dim · cosine sim    │   │
│   │  Ollama (local)       │              │  threshold: 0.65          │   │
│   │  qwen2.5 / llama      │              │                           │   │
│   └───────────────────────┘              └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ How It Works

```
  User types: "what keyboard should I buy?"
              │
              ▼
  ┌─────────────────────────────────────────────┐
  │  STEP 1 — RETRIEVE                          │
  │  pgvector cosine search (threshold: 0.65)   │
  │  → [0.82] User codes in Python and FastAPI  │
  │  → [0.76] User works 11pm–3am               │
  │  → [0.70] User uses Neovim on Arch Linux    │
  └─────────────────────────────────────────────┘
              │
              ▼
  ┌─────────────────────────────────────────────┐
  │  STEP 2 — INJECT (invisibly)                │
  │  [Memory Context from MnemOS]               │
  │  - User codes in Python and FastAPI         │
  │  - User works late at night, 11pm to 3am    │
  │  - User uses Neovim on Arch Linux           │
  │  ⌀ what keyboard should I buy?              │
  └─────────────────────────────────────────────┘
              │
              ▼
  ┌─────────────────────────────────────────────┐
  │  STEP 3 — AI RESPONDS with full context     │
  │  "Given you code in Python and work nights, │
  │   the Keychron Q1 with linear switches..."  │
  └─────────────────────────────────────────────┘
              │
              ▼
  ┌─────────────────────────────────────────────┐
  │  STEP 4 — LEARN (on session end)            │
  │  Gemini / Ollama extracts new facts         │
  │  → "User prefers linear switches"           │
  │  bge-m3 embeds → stored in pgvector         │
  └─────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

Choose your path:

| Path | Best For | Time |
|------|----------|------|
| [🌐 Browser Extension](#-path-1--browser-extension) | ChatGPT / Claude users, no code needed | 2 min |
| [💻 CLI](#-path-2--cli) | Developers, full control | 5 min |
| [🐍 Python SDK](#-path-3--python-sdk) | Building AI apps with memory | 5 min |

---

## 🌐 Path 1 — Browser Extension

> No coding required. Works on ChatGPT and Claude.

**Step 1 — Install the extension**
1. Go to `chrome://extensions`
2. Enable **Developer mode** (toggle, top-right)
3. Click **Load unpacked** → select the `extension/` folder

A **Welcome tab opens automatically** and walks you through 3 steps:

```
Step 1 — Connect          Step 2 — Engine           Step 3 — Done
─────────────────         ─────────────────          ─────────────────
⬡ MnemOS                  ⬡ MnemOS                   ⬡ MnemOS
●━━━━━○━━━━━○             ✓━━━━━●━━━━━○              ✓━━━━━✓━━━━━●

✅ Server running          Choose AI Engine            🎉 You're all set!
   localhost:8765          ┌──────┐ ┌──────┐          MnemOS will silently
                           │Gemini│ │Ollama│          remember everything.
[ Continue → ]             │Cloud │ │Local │
                           └──────┘ └──────┘          [ Open ChatGPT → ]
                           [ Save → ]
```

**Extension popup (daily use):**
```
┌──────────────────────────────────────┐
│  ⬡ MnemOS                    🟢     │
├──────────────────────────────────────┤
│  Memories  [13]                      │
│  • User codes in Python              │
│  • User prefers dark mode editors    │
│  • User is building a REST API       │
│  • User wants to learn Rust          │
├──────────────────────────────────────┤
│  Engine: [ Ollama ▼ ] [ qwen2.5:7b ] │
├──────────────────────────────────────┤
│  [ ⬡ Dashboard ]  [ ◎ Sessions ]     │
│  ☑ Auto-capture              [ ↻ ]   │
└──────────────────────────────────────┘
```

---

## 💻 Path 2 — CLI

```bash
git clone https://github.com/Divyansh2202/mnemos.git
cd mnemos
python3 -m venv myenv && source myenv/bin/activate
pip install -e .
```

**First-time setup:**
```bash
mnemos init
```
```
╭─────────────────╮
│  MnemOS Setup   │
╰─────────────────╯

Step 1: Choose extraction engine
  1  Gemini 2.5 Flash  (fast, cloud, needs API key)
  2  Ollama            (local, private)
Engine [1]: 1

Gemini API key: AIzaSy...
✓ Config saved

Next:  mnemos db-start  →  mnemos start  →  mnemos doctor
```

**Start everything:**
```bash
mnemos db-start       # Start PostgreSQL
mnemos start          # Start MnemOS server on :8765
mnemos doctor         # Health check
```
```
╭──────────────────────╮
│  MnemOS Health Check │
╰──────────────────────╯
✓ MnemOS server    running
✓ Ollama binary    found
✓ bge-m3           ready
✓ PostgreSQL       running

All systems go!
```

**Browse and search memories:**
```bash
mnemos list
```
```
ID           Content                                Type      Conf   App
────────────────────────────────────────────────────────────────────────────
mem_a1b2c3   User codes in Python and FastAPI       semantic  0.95   chatgpt
mem_e5f6g7   User has a golden retriever, Bruno     semantic  0.90   chatgpt
mem_i9j0k1   User drinks dark roast, no milk        semantic  0.88   claude
mem_m3n4o5   User uses Neovim on Arch Linux         semantic  0.85   chatgpt
```

```bash
mnemos search "what does the user drink?"
```
```
Content                                  Relevance   App
──────────────────────────────────────────────────────────
User drinks dark roast coffee, no milk   0.891       claude
User dislikes sweet drinks               0.712       chatgpt
```

**Full CLI reference:**
```
mnemos init                              First-time setup wizard
mnemos db-start                          Start PostgreSQL
mnemos install-ollama                    Download Ollama binary
mnemos serve-ollama                      Start Ollama server
mnemos pull-models                       Download bge-m3 + qwen2.5:3b
mnemos start                             Start MnemOS server on :8765
mnemos doctor                            Health check all components
mnemos stats                             Memory statistics by type + app
mnemos list                              Browse all stored memories
mnemos search <query>                    Semantic search
mnemos model                             View/switch extraction engine
mnemos model --list                      Show all models + download status
mnemos model --pull <model>              Download a model
mnemos model --engine <e> --name <m>     Switch engine/model live
mnemos mcp-config                        Print Claude Desktop MCP config
```

---

## 🐍 Path 3 — Python SDK

```bash
pip install -e .   # from repo root
```

```python
from mnemos import MnemOS

mem = MnemOS(app_id="my-app", user_id="alice")

# Store a fact
mem.store("User prefers dark mode and large fonts")

# Learn from a conversation
mem.learn([
    {"role": "user",      "content": "I hate React, only use Vue."},
    {"role": "assistant", "content": "Vue is great for smaller projects!"},
])

# Retrieve relevant memories
results = mem.retrieve("what frontend does the user prefer?")
# → [{"content": "User dislikes React, only uses Vue", "relevance": 0.89}]

# Inject context into any AI call
context = mem.inject("tech stack and preferences")
# → "[Relevant memories]\n1. User dislikes React..."
```

**Full example with OpenAI:**
```python
from mnemos import MnemOS
import openai

mem = MnemOS(app_id="my-chatbot", user_id="user-123")
client = openai.OpenAI()

def chat(user_message: str) -> str:
    context = mem.inject(user_message)
    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(model="gpt-4o", messages=messages)
    answer = response.choices[0].message.content

    mem.learn([
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": answer},
    ])
    return answer

chat("I work in Python and love Rust")
chat("what language do I prefer?")
# → "Based on our conversation, you prefer Python for work and love Rust..."
```

---

## 🔌 REST API

```
GET  /health                    Server status + version
GET  /stats                     Memory counts by type and app
GET  /config                    Current extraction engine + model
POST /config                    Update engine / model / API key

POST /memory/store              Store a single memory
POST /memory/retrieve           Semantic search (returns top-N with scores)
POST /memory/learn              Extract + store facts from a conversation
GET  /memory/all                List all memories
DELETE /memory/{id}             Delete a specific memory

GET  /sessions                  List conversation sessions
GET  /sessions/{session_id}     Get full session + messages + export

GET  /ollama/models             List downloaded Ollama models
POST /ollama/pull               Download an Ollama model
```

```bash
# Store
curl -X POST http://localhost:8765/memory/store \
  -H "Content-Type: application/json" \
  -d '{"content":"User loves dark roast coffee","app_id":"myapp","user_id":"alice"}'

# Retrieve
curl -X POST http://localhost:8765/memory/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"what does the user drink?","user_id":"alice","limit":3}'
```

---

## 🧪 Extraction Engines

| | Gemini 2.5 Flash | Ollama (local) |
|-|-----------------|----------------|
| Speed | ~13s / conversation | Depends on model + hardware |
| Quality | 15–34 facts extracted | 8–20 facts |
| Cost | ~$0.001 / conversation | Free |
| Privacy | Data sent to Google | 100% local |
| Setup | Free key at [aistudio.google.com](https://aistudio.google.com) | `mnemos install-ollama` |

> **Recommendation:** Gemini for extraction (fast, high quality). `bge-m3` embeddings always run locally — your memory vectors never leave your machine.

**Supported Ollama models:**

| Model | Size | Notes |
|-------|------|-------|
| `qwen2.5:0.5b` | 0.4 GB | Fastest |
| `qwen2.5:3b` | 1.9 GB | ⭐ Recommended |
| `qwen2.5:7b` | 4.7 GB | High quality |
| `llama3.2:3b` | 2.0 GB | Meta Llama 3.2 |
| `mistral:7b` | 4.1 GB | Mistral 7B |

---

## 📁 Project Structure

```
mnemos/
├── server/
│   ├── main.py              FastAPI server — all REST endpoints
│   ├── memory_store.py      PostgreSQL + pgvector store / retrieve / dedup
│   └── context_engine.py    Gemini + Ollama extraction, config persistence
│
├── extension/
│   ├── manifest.json        Chrome MV3
│   ├── background.js        Service worker — message hub, queue, retry
│   ├── content/
│   │   ├── chatgpt.js       ChatGPT inject + extract
│   │   └── claude.js        Claude inject + extract
│   ├── popup/               Extension popup UI
│   └── onboarding/          First-install setup wizard
│
├── cli/
│   └── main.py              Typer CLI
│
├── sdk/python/mnemos/
│   └── client.py            Python SDK
│
├── dashboard/
│   └── index.html           Web UI — view and manage memories
│
├── integrations/
│   └── mcp_server.py        MCP server for Claude Desktop
│
└── protocol/
    └── types.py             Shared Pydantic types
```

---

## ⚙️ Configuration

**`.env`**
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

---

## 📝 Note

This is not a production-ready system. I saw a problem, thought about how it should work, and built an initial implementation covering all the core pieces — server, browser extension, CLI, Python SDK, dashboard, and MCP integration. It works end to end but is not optimized or hardened for scale. Think of it as a working proof of concept that solves a real problem.

---

<div align="center">

**Built by [Divyansh Rai](https://github.com/Divyansh2202) · [LinkedIn](https://linkedin.com/in/divyanshrai01)**

<img src="https://img.shields.io/badge/License-MIT-10B981?style=flat-square" />
&nbsp;
<a href="https://github.com/Divyansh2202/mnemos/stargazers">
  <img src="https://img.shields.io/github/stars/Divyansh2202/mnemos?style=flat-square&color=6E40C9" />
</a>

</div>
