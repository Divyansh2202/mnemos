# ⬡ MnemOS — Universal Memory for AI Apps

---

## Note

This is not a production-ready system. I saw a problem, thought about how it should work, and built an initial implementation covering all the core pieces — server, browser extension, CLI, Python SDK, dashboard, and MCP integration. It works end to end but is not optimized or hardened for scale. Think of it as a working proof of concept that solves a real problem.

---

## The Problem

Every time you start a new conversation with ChatGPT or Claude, the AI has **no idea who you are**.

You mention you work in Python. Next session — you explain it again.
You say you have a dog named Bruno. Next session — gone.
You describe your keyboard preference. Next session — you type it again.

AI assistants have **no persistent memory**. Every session is a blank slate.
You waste time re-explaining yourself. The AI gives generic answers instead of personalized ones.

**And switching platforms means starting from zero.**

You had a long conversation on ChatGPT — your preferences, your projects, everything it learned about you.
Now you open Claude. It has no idea about any of it. All that context is gone.
There is no way to carry memory from one AI platform to another.

**And your raw conversations are trapped.**

Every question you asked, every answer you got — locked inside each platform.
You cannot export it, search it, or use it anywhere else.

This is not a ChatGPT problem. It is not a Claude problem. It is a **fundamental missing layer** in every AI interface.

---

## The Solution

MnemOS is a **Universal Memory Layer** that sits between you and any AI.

- After every conversation, it **silently extracts facts** about you (preferences, skills, habits, projects)
- Before every message you send, it **injects relevant memories** into your prompt invisibly
- The AI responds as if it already knows you — **without you changing anything**
- Memory is stored by **user ID, not by platform** — so switching from ChatGPT to Claude automatically carries all your context over
- You can **export your raw conversation** from any platform as JSON and use it anywhere else

You never type your preferences twice. You never repeat context. Switch platforms freely. The AI just knows.

```
WITHOUT MnemOS                        WITH MnemOS
───────────────────────────────────   ──────────────────────────────────────
[ChatGPT]                             [ChatGPT]
You: "I love Python, I use Neovim"    You: "I love Python, I use Neovim"
AI:  "Great!"                         AI:  "Great!"  → facts stored silently

[next session on Claude]              [next session on Claude]
You: "help me with code"              You: "help me with code"
Claude: "Sure, what language?"        Claude: "Here's a Python solution
                                              optimized for Neovim users..."
You: "Python..." ← repeating
                                      [MnemOS injected context from ChatGPT]
```

### Cross-Platform Memory

Memories are stored by **user ID**, not by platform. Everything you told ChatGPT is available on Claude automatically — no setup needed.

```
ChatGPT  ──stores──▶  MnemOS (user_id: "default")  ◀──retrieves──  Claude
Claude   ──stores──▶  MnemOS (user_id: "default")  ◀──retrieves──  ChatGPT
Your App ──stores──▶  MnemOS (user_id: "default")  ◀──retrieves──  Any platform
```

### Export Raw Conversations

Every raw conversation is saved automatically. You can export it from the **Dashboard → Sessions tab**:

```
┌──────────────────────────────────────────────────────┐
│  Session: "I love Python and FastAPI"                │
│  ChatGPT  ·  14 messages  ·  2 days ago              │
│                                  [ ↓ Export ]        │
└──────────────────────────────────────────────────────┘
```

Click **Export** → a modal shows the full raw JSON + a formatted preview → click **Download** to save as `.json`, or **Copy** to clipboard.

```json
{
  "session_id": "chatgpt_default",
  "title": "I love Python and FastAPI",
  "app_id": "chatgpt",
  "exported_at": "2026-03-30T12:00:00Z",
  "messages": [
    {"role": "user",      "content": "I love Python and FastAPI"},
    {"role": "assistant", "content": "Great choice for backend work!"}
  ]
}
```

Or via API directly:
```bash
curl http://localhost:8765/sessions/chatgpt_default?user_id=default
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             MnemOS System                                    │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ ChatGPT.com │  │  Claude.ai  │  │  Your App    │  │  Claude Desktop  │  │
│  │ (Extension) │  │ (Extension) │  │  (Python SDK)│  │  (MCP Server)    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘  │
│         └────────────────┴─────────────────┴───────────────────┘            │
│                                    │                                         │
│                                    ▼                                         │
│                     ┌──────────────────────────┐                            │
│                     │     MnemOS Server         │                            │
│                     │     FastAPI  :8765         │                            │
│                     └─────────────┬────────────┘                            │
│                                   │                                          │
│              ┌────────────────────┴──────────────────────┐                  │
│              ▼                                            ▼                  │
│   ┌──────────────────────┐                  ┌───────────────────────┐       │
│   │   Context Engine     │                  │    Memory Store       │       │
│   │                      │                  │                       │       │
│   │  ┌────────────────┐  │                  │  PostgreSQL + pgvector│       │
│   │  │ Gemini 2.5 Flash│  │                  │  cosine similarity    │       │
│   │  │ (cloud, fast)  │  │                  │  threshold: 0.65      │       │
│   │  └────────────────┘  │                  └──────────┬────────────┘       │
│   │         OR           │                             │                    │
│   │  ┌────────────────┐  │                             ▼                    │
│   │  │ Ollama (local) │  │                  ┌───────────────────────┐       │
│   │  │ qwen2.5 / llama│  │                  │  bge-m3 embeddings    │       │
│   │  └────────────────┘  │                  │  1024-dim vectors     │       │
│   └──────────────────────┘                  │  Ollama (always local)│       │
│                                             └───────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## How It Works (Full Data Flow)

```
  User types: "what keyboard should I buy?"
              │
              ▼
  ┌─────────────────────────────────────────────────────────┐
  │  STEP 1 — RETRIEVE                                      │
  │                                                         │
  │  Content script sends query to MnemOS server            │
  │  POST /memory/retrieve  { query: "what keyboard..." }   │
  │                                                         │
  │  pgvector does cosine similarity search                 │
  │  threshold: 0.65 — returns top 5 relevant memories      │
  │                                                         │
  │  Returns:                                               │
  │  • [0.821] User codes in Python and FastAPI             │
  │  • [0.764] User works late at night, 11pm to 3am        │
  │  • [0.703] User uses Neovim on Arch Linux               │
  └─────────────────────────────────────────────────────────┘
              │
              ▼
  ┌─────────────────────────────────────────────────────────┐
  │  STEP 2 — INJECT                                        │
  │                                                         │
  │  Context prepended to user's message (invisibly):       │
  │                                                         │
  │  [Memory Context from MnemOS]                           │
  │  - User codes in Python and FastAPI                     │
  │  - User works late at night, 11pm to 3am                │
  │  - User uses Neovim on Arch Linux                       │
  │  \uE000 what keyboard should I buy?                     │
  │                                                         │
  │  \uE000 = invisible Unicode delimiter (U+E000)          │
  │  Everything before it is stripped before storing        │
  └─────────────────────────────────────────────────────────┘
              │
              ▼
  ┌─────────────────────────────────────────────────────────┐
  │  STEP 3 — AI RESPONDS                                   │
  │                                                         │
  │  ChatGPT / Claude sees full context and replies:        │
  │  "Given that you code in Python and work at night,      │
  │   the Keychron Q1 with linear switches is ideal..."     │
  └─────────────────────────────────────────────────────────┘
              │
              ▼
  ┌─────────────────────────────────────────────────────────┐
  │  STEP 4 — LEARN (on tab close / hide)                   │
  │                                                         │
  │  cleanMessages() strips \uE000 prefix from all messages │
  │  POST /memory/learn  { messages: [...] }                │
  │                                                         │
  │  Context Engine (Gemini or Ollama) extracts facts:      │
  │  "User prefers linear switches for keyboards"           │
  │  "User asked about keyboards for programming"           │
  │                                                         │
  │  Embeddings generated by bge-m3 → stored in pgvector    │
  └─────────────────────────────────────────────────────────┘
```

---

## Setup Paths

There are **3 ways** to set up MnemOS depending on your use case:

| Path | Best For | Time |
|------|----------|------|
| **Extension** | Non-technical users, ChatGPT/Claude | 2 min |
| **CLI** | Developers, full control, local setup | 5 min |
| **Python SDK** | Building your own AI apps | 5 min |

---

# PATH 1 — Browser Extension

> Best for: anyone who uses ChatGPT or Claude in their browser.
> No coding required.

### Step A — Install the Extension

1. Go to `chrome://extensions`
2. Turn on **Developer mode** (toggle, top-right)
3. Click **Load unpacked**
4. Select the `extension/` folder from this repo

As soon as the extension installs, a **Welcome tab opens automatically**.

---

### Step 1 of 3 — Connect to Server

```
┌─────────────────────────────────────────────────────┐
│  ⬡ MnemOS                                           │
│  Universal Memory for AI — set up in 2 minutes      │
│                                                     │
│  ●━━━━━━━━━━━○━━━━━━━━━━━○                          │
│  Connect       Engine      Done                     │
│                                                     │
│  Connect to MnemOS Server                           │
│  MnemOS needs a local server running on your        │
│  machine to store and retrieve memories.            │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  ⏳  Checking server...                     │   │
│  │      Looking for MnemOS at localhost:8765   │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [ ↻ Check Again ]                                  │
└─────────────────────────────────────────────────────┘
```

**If server is running** → status turns green:
```
│  ┌─────────────────────────────────────────────┐   │
│  │  ✅  Server is running!                     │   │
│  │      MnemOS is ready at localhost:8765      │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [ Continue → ]                                     │
```

**If server is NOT running** → status turns red with download button:
```
│  ┌─────────────────────────────────────────────┐   │
│  │  ❌  Server not found                       │   │
│  │      Please download and start MnemOS server│   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Download and run the MnemOS server app:            │
│  [ ⬇ Download MnemOS Server ]                       │
│  After installing, launch and come back here.       │
│                                                     │
│  [ ↻ Check Again ]                                  │
```

---

### Step 2 of 3 — Choose Extraction Engine

```
┌─────────────────────────────────────────────────────┐
│  ⬡ MnemOS                                           │
│                                                     │
│  ✓━━━━━━━━━━━●━━━━━━━━━━━○                          │
│  Connect       Engine      Done                     │
│                                                     │
│  Choose Your AI Engine                              │
│  How should MnemOS extract memories from            │
│  your conversations?                                │
│                                                     │
│  ┌───────────────────┐  ┌───────────────────┐      │
│  │  ✦                │  │  🦙               │      │
│  │  Gemini Flash     │  │  Ollama           │      │
│  │  Fast · Cloud     │  │  Private · Local  │      │
│  │  Needs API key    │  │  No internet      │      │
│  │  [SELECTED]       │  │                   │      │
│  └───────────────────┘  └───────────────────┘      │
│                                                     │
│  Gemini API Key  — free at aistudio.google.com      │
│  ┌─────────────────────────────────────────────┐   │
│  │  AIzaSy...                              🔒  │   │
│  └─────────────────────────────────────────────┘   │
│  Get a free API key →                               │
│                                                     │
│  [ Save & Continue → ]   [ ← Back ]                 │
└─────────────────────────────────────────────────────┘
```

**If you pick Ollama** → engine card switches, model list appears:
```
│  ┌───────────────────┐  ┌───────────────────┐      │
│  │  ✦                │  │  🦙               │      │
│  │  Gemini Flash     │  │  Ollama           │      │
│  │                   │  │  [SELECTED]       │      │
│  └───────────────────┘  └───────────────────┘      │
│                                                     │
│  Select a model. Click Download if not downloaded.  │
│                                                     │
│  ┌─────────────────────────────────┬──────┬───────┐ │
│  │ qwen2.5:0.5b  Fastest · Lightest│0.4 GB│Download│ │
│  ├─────────────────────────────────┼──────┼───────┤ │
│  │ qwen2.5:1.5b  Fast · Good       │1.0 GB│Download│ │
│  ├─────────────────────────────────┼──────┼───────┤ │
│  │ qwen2.5:3b  ⭐ Recommended      │1.9 GB│✓ Ready│ │  ← green border
│  ├─────────────────────────────────┼──────┼───────┤ │
│  │ qwen2.5:7b  High quality        │4.7 GB│Download│ │
│  ├─────────────────────────────────┼──────┼───────┤ │
│  │ qwen2.5:14b Very high quality   │9.0 GB│Download│ │
│  ├─────────────────────────────────┼──────┼───────┤ │
│  │ llama3.2:3b  Meta Llama 3.2     │2.0 GB│Download│ │
│  ├─────────────────────────────────┼──────┼───────┤ │
│  │ mistral:7b   Mistral 7B         │4.1 GB│Download│ │
│  ├─────────────────────────────────┼──────┼───────┤ │
│  │ phi3:mini    Microsoft Phi-3    │2.2 GB│Download│ │
│  └─────────────────────────────────┴──────┴───────┘ │
│                                                     │
│  Click a row to select. Click Download to fetch it. │
│  ┌──────────────────────────────────────────────┐   │
│  │ Downloading...  ████████░░░░░░░░░  54%       │   │
│  └──────────────────────────────────────────────┘   │
```

---

### Step 3 of 3 — Done

```
┌─────────────────────────────────────────────────────┐
│  ⬡ MnemOS                                           │
│                                                     │
│  ✓━━━━━━━━━━━✓━━━━━━━━━━━●                          │
│  Connect       Engine      Done                     │
│                                                     │
│               🎉                                    │
│           You're all set!                           │
│  MnemOS will now silently remember everything       │
│  across your AI conversations.                      │
│                                                     │
│  ┌────────────────────────────────────────────┐    │
│  │ 🧠  Auto Memory                            │    │
│  │     After each conversation, MnemOS        │    │
│  │     extracts and stores key facts.         │    │
│  ├────────────────────────────────────────────┤    │
│  │ ⚡  Smart Injection                        │    │
│  │     Relevant memories are silently added   │    │
│  │     so AI always has context.              │    │
│  ├────────────────────────────────────────────┤    │
│  │ 🔒  Fully Private                          │    │
│  │     Everything stays on your machine.      │    │
│  │     No data sent to MnemOS servers.        │    │
│  └────────────────────────────────────────────┘    │
│                                                     │
│  [ Open ChatGPT and try it → ]                      │
│  Or open Claude — MnemOS works on all of them.      │
└─────────────────────────────────────────────────────┘
```

---

### Extension Popup (daily use)

Click the ⬡ icon in your toolbar any time:

```
┌──────────────────────────────────────┐
│  ⬡ MnemOS                    🟢     │  ← green dot = server connected
├──────────────────────────────────────┤
│  Server                              │
│  [ http://localhost:8765           ] │
│  User ID                             │
│  [ default                         ] │
│  [ Save ]                            │
├──────────────────────────────────────┤
│  ⏳ 2 conversations queued           │  ← shows if server was briefly offline
├──────────────────────────────────────┤
│  Memories  [34]                      │
│  ┌────────────────────────────────┐  │
│  │ User codes in Python and Rust  │  │
│  │ User has a dog named Bruno     │  │
│  │ User prefers dark roast coffee │  │
│  │ User uses Neovim on Arch Linux │  │
│  │ User works late night, 11pm–3am│  │
│  │ ...                            │  │
│  └────────────────────────────────┘  │
├──────────────────────────────────────┤
│  Extraction Model                    │
│  [ Gemini Flash      ▼ ]             │  ← or Ollama
│  [ qwen2.5:3b        ▼ ] [Download]  │  ← appears when Ollama selected
│  [ Apply ]                           │
├──────────────────────────────────────┤
│  [ ⬡ Dashboard ]  [ ◎ Sessions ]    │
├──────────────────────────────────────┤
│  ☑ Auto-capture              [ ↻ ]  │
└──────────────────────────────────────┘
```

---

# PATH 2 — CLI (Command Line)

> Best for: developers who want full control over the setup.

### Install

```bash
git clone https://github.com/Divyansh2202/mnemos.git
cd mnemos
python3 -m venv myenv
source myenv/bin/activate
pip install -e .
```

---

### `mnemos init` — First-time setup wizard

Run this first:

```bash
mnemos init
```

**What you see:**

```
╭─────────────────╮
│  MnemOS Setup   │
╰─────────────────╯

Step 1: Choose extraction engine
  1  Gemini 2.5 Flash  (fast, cloud, needs API key)
  2  Ollama            (local, private, needs GPU/CPU)
Engine [1]:
```

**If you choose Gemini (type `1`):**
```
Engine [1]: 1
Gemini API key (from aistudio.google.com): AIzaSy...

✓ Gemini key saved
✓ Config saved → gemini

Next steps:
  1. Start PostgreSQL:  mnemos db-start
  2. Start server:      mnemos start
  3. Check health:      mnemos doctor

  Switch model later:   mnemos model --list
```

**If you choose Ollama (type `2`):**
```
Engine [1]: 2

Step 2: Choose Ollama model
 #   Model          Size    Notes
─────────────────────────────────────────────────────────
 1   qwen2.5:0.5b   0.4 GB  Fastest, lowest quality
 2   qwen2.5:1.5b   1.0 GB  Fast, decent quality
 3   qwen2.5:3b     1.9 GB  Balanced (default)
 4   qwen2.5:7b     4.7 GB  Good quality
 5   qwen2.5:14b    9.0 GB  High quality
 6   qwen2.5:32b    20 GB   Very high quality
 7   llama3.2:3b    2.0 GB  Meta Llama 3.2
 8   mistral:7b     4.1 GB  Mistral 7B
 9   phi3:mini      2.2 GB  Microsoft Phi-3 Mini

Pick a model (number or name) [3]: 3

Selected: qwen2.5:3b
Download it now? [Y/n]: Y

Downloading qwen2.5:3b...
pulling manifest...
pulling 6e9f90fcbc6...  1.9 GB / 1.9 GB ████████████ 100%

✓ qwen2.5:3b ready
✓ Config saved → ollama / qwen2.5:3b

Next steps:
  1. Start PostgreSQL:  mnemos db-start
  2. Start Ollama:      mnemos serve-ollama
  3. Start server:      mnemos start
  4. Check health:      mnemos doctor

  Switch model later:   mnemos model --list
```

---

### `mnemos db-start` — Start PostgreSQL

```bash
mnemos db-start
```
```
Starting PostgreSQL...
✓ PostgreSQL is running on port 5432
```

---

### `mnemos install-ollama` — Install Ollama (if not installed)

```bash
mnemos install-ollama
```
```
Downloading Ollama v0.19.0 (amd64)...
  100% (87MB / 87MB)
Extracting...
✓ Ollama installed at /home/user/.local/bin/ollama
✓ Added ~/.local/bin to PATH in ~/.bashrc

Run: source ~/.bashrc && mnemos serve-ollama
```

---

### `mnemos serve-ollama` — Start Ollama

```bash
mnemos serve-ollama
```
```
Starting Ollama server...
✓ Ollama is running on port 11434
```

---

### `mnemos start` — Start MnemOS Server

```bash
mnemos start
```
```
╭──────────────────────────╮
│  Starting MnemOS         │
│  http://localhost:8765   │
╰──────────────────────────╯
INFO:     Uvicorn running on http://localhost:8765
[MemoryStore] Ready | Model: bge-m3 | Dim: 1024
[ContextEngine] Mode: gemini | Model: qwen2.5:3b
```

---

### `mnemos doctor` — Health check

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

If something is missing:
```
✗ MnemOS server    not running  →  run: mnemos start
✗ Ollama binary    not found    →  run: mnemos install-ollama
✗ bge-m3                        →  run: mnemos pull-models
✗ PostgreSQL       not running  →  run: mnemos db-start
```

---

### `mnemos model` — View and switch models

**View current config:**
```bash
mnemos model
```
```
╭────────────────────╮
│  Extraction Config │
╰────────────────────╯
Engine : gemini
Model  : qwen2.5:3b

Commands:
  mnemos model --list                            show all models
  mnemos model --pull qwen2.5:7b                 download a model
  mnemos model --engine ollama --name qwen2.5:7b use a model
  mnemos model --engine gemini                   switch to Gemini
```

**List all models + download status:**
```bash
mnemos model --list
```
```
╭────────────────╮
│  Ollama Models │
╰────────────────╯
Model          Size    Notes                    Downloaded
─────────────────────────────────────────────────────────
qwen2.5:0.5b   0.4 GB  Fastest, lowest quality      —
qwen2.5:1.5b   1.0 GB  Fast, decent quality          —
qwen2.5:3b     1.9 GB  Balanced (default)            ✓
qwen2.5:7b     4.7 GB  Good quality                  —
qwen2.5:14b    9.0 GB  High quality                  —
qwen2.5:32b    20 GB   Very high quality              —
llama3.2:3b    2.0 GB  Meta Llama 3.2                —
mistral:7b     4.1 GB  Mistral 7B                    —
phi3:mini      2.2 GB  Microsoft Phi-3 Mini           —

Download a model:  mnemos model --pull qwen2.5:7b
```

**Download a model:**
```bash
mnemos model --pull qwen2.5:7b
```
```
Downloading qwen2.5:7b ...
pulling manifest...
pulling abc123...  4.7 GB / 4.7 GB ████████████ 100%

✓ qwen2.5:7b downloaded

Now set it: mnemos model --engine ollama --name qwen2.5:7b
```

**Switch to a model:**
```bash
mnemos model --engine ollama --name qwen2.5:7b
```
```
✓ Engine:  ollama
✓ Model:   qwen2.5:7b
```

**Switch to Gemini:**
```bash
mnemos model --engine gemini
```
```
✓ Engine:  gemini
✓ Model:   qwen2.5:3b
```

---

### `mnemos stats` — Memory statistics

```bash
mnemos stats
```
```
╭───────────────╮
│  MnemOS Stats │
╰───────────────╯
Total memories: 34

Type       Count
─────────────────
semantic   28
episodic   4
procedural 2

App        Count
─────────────────
chatgpt    20
claude     14
```

---

### `mnemos list` — Browse stored memories

```bash
mnemos list
```
```
ID               Content                                  Type      Conf  App
─────────────────────────────────────────────────────────────────────────────────
mem_a1b2c3d4     User codes in Python and FastAPI         semantic  0.95  chatgpt
mem_e5f6g7h8     User has a golden retriever named Bruno  semantic  0.90  chatgpt
mem_i9j0k1l2     User drinks dark roast coffee, no milk   semantic  0.88  claude
mem_m3n4o5p6     User uses Neovim on Arch Linux           semantic  0.85  chatgpt
mem_q7r8s9t0     User works late night, 11pm to 3am       episodic  0.80  chatgpt
```

---

### `mnemos search` — Semantic search

```bash
mnemos search "what does the user drink?"
```
```
Content                                   Type      Relevance  App
────────────────────────────────────────────────────────────────────
User drinks dark roast coffee, no milk    semantic  0.891      claude
User dislikes sweet drinks                semantic  0.712      chatgpt
```

---

### Full CLI Command Reference

```
mnemos init              Interactive setup wizard
mnemos db-start          Start PostgreSQL (Docker)
mnemos install-ollama    Download Ollama binary (no sudo needed)
mnemos serve-ollama      Start Ollama server
mnemos pull-models       Download bge-m3 + qwen2.5:3b
mnemos start             Start MnemOS server on :8765
mnemos doctor            Health check all components
mnemos stats             Memory store statistics
mnemos list              List all stored memories
mnemos search <query>    Semantic search through memories
mnemos model             View current extraction config
mnemos model --list      Show all models with download status
mnemos model --pull <m>  Download an Ollama model
mnemos model --engine <e> --name <m>  Switch engine/model live
mnemos mcp-config        Print Claude Desktop MCP config
```

---

# PATH 3 — Python SDK

> Best for: building your own AI apps with persistent memory.

### Install

```bash
pip install -e .   # from the repo root
```

### Basic Usage

```python
from mnemos import MnemOS

mem = MnemOS(app_id="my-app", user_id="alice")

# Store a fact manually
mem.store("User prefers dark mode and large fonts")

# Auto-extract from a conversation
mem.learn([
    {"role": "user",      "content": "I hate React, I only use Vue."},
    {"role": "assistant", "content": "Vue is great for smaller projects!"},
])

# Semantic search
results = mem.retrieve("what frontend framework does the user use?")
# → [{"content": "User dislikes React, only uses Vue", "relevance": 0.89}]

# Inject context directly into your OpenAI / Anthropic call
system_prompt = mem.inject("user preferences and tech stack")
# → "[Relevant memories about this user]\n1. User dislikes React..."
```

### Full SDK Example with OpenAI

```python
from mnemos import MnemOS
import openai

mem = MnemOS(app_id="my-chatbot", user_id="user-123")
client = openai.OpenAI()

def chat(user_message: str) -> str:
    # 1. Get relevant context
    context = mem.inject(user_message)

    # 2. Build messages with memory context
    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": user_message})

    # 3. Call AI
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
    )
    answer = response.choices[0].message.content

    # 4. Store conversation for future memory
    mem.learn([
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": answer},
    ])

    return answer

# Now every conversation builds memory
print(chat("I work in Python and love Rust"))
print(chat("what language do I prefer?"))
# → "Based on our conversation, you prefer Python for work and love Rust..."
```

### Model Management via SDK

```python
# Check current engine
config = mem.get_model()
# → {"mode": "gemini", "gen_model": "qwen2.5:3b"}

# Switch to Gemini
mem.set_model(engine="gemini")

# Switch to Ollama with a specific model
mem.set_model(engine="ollama", model="qwen2.5:7b")

# List downloaded Ollama models
models = mem.list_models()
# → [{"name": "qwen2.5:3b", "size_gb": 1.9}, ...]

# Download a model
mem.pull_model("qwen2.5:14b")
```

---

## REST API Quick Reference

```
GET  /health                      {"status": "ok", "version": "0.1.0"}
GET  /stats                       memory counts by type and app
GET  /config                      current extraction engine + model
POST /config                      update engine/model/gemini_key

POST /memory/store                store a single memory
POST /memory/retrieve             semantic search
POST /memory/learn                extract + store from conversation
GET  /memory/all                  list all memories
DELETE /memory/{id}               delete a memory

GET  /sessions                    list conversation sessions
GET  /sessions/{session_id}       get full session with messages

GET  /ollama/models               list downloaded Ollama models
POST /ollama/pull                 download an Ollama model
```

**Example — store and retrieve:**
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

## Extraction Engines

### Gemini 2.5 Flash (recommended)

| | |
|-|-|
| Speed | ~13 seconds for a long conversation |
| Quality | 15–34 facts extracted per conversation |
| Cost | ~$0.001 per conversation |
| Privacy | Data sent to Google |
| Setup | Free API key at [aistudio.google.com](https://aistudio.google.com) |

### Ollama (local)

| | |
|-|-|
| Speed | Depends on model and hardware |
| Privacy | 100% local — nothing leaves your machine |
| Cost | Free |
| Best model | `qwen2.5:3b` (balanced), `qwen2.5:7b` (better) |

### Benchmark (same long conversation)

| Engine | Time | Facts Extracted | Notes |
|--------|------|----------------|-------|
| Gemini 2.5 Flash | 13s | 34 | Every fact captured correctly |
| qwen2.5:7b | ~60s | 15–20 | Good quality |
| qwen2.5:3b | ~30s | 8–12 | Decent, fast |

> **Recommendation:** Use Gemini for extraction (fast, cheap, high quality).
> `bge-m3` for embeddings is always local — no data leaves your machine.

---

## Configuration

### `.env` file
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

### `mnemos_config.json` (runtime config, survives restarts)
```json
{
  "mode": "gemini",
  "gen_model": "qwen2.5:3b"
}
```

This file is written by `mnemos init`, the `mnemos model` command, the extension popup, and the web dashboard. All four interfaces stay in sync.

---

## Memory Privacy Levels

| Level | Description |
|-------|-------------|
| `global` | Shared across all apps for this user |
| `app_shared` | Visible only within the same app |
| `private` | Visible only to the specific app that stored it |

---

## Project Structure

```
mnemos/
├── server/
│   ├── main.py              FastAPI server — all REST endpoints
│   ├── memory_store.py      PostgreSQL + pgvector store/retrieve/dedup
│   └── context_engine.py    Gemini + Ollama extraction, config persistence
│
├── extension/
│   ├── manifest.json        Chrome MV3 manifest
│   ├── background.js        Service worker — message hub, queue, retry
│   ├── content/
│   │   ├── chatgpt.js       ChatGPT inject + extract
│   │   └── claude.js        Claude inject + extract
│   ├── popup/               Extension popup UI
│   └── onboarding/          First-install setup wizard
│
├── cli/
│   └── main.py              Typer CLI — all commands
│
├── sdk/python/mnemos/
│   └── client.py            Python SDK
│
├── dashboard/
│   └── index.html           Web UI — view + manage memories
│
├── integrations/
│   └── mcp_server.py        MCP server for Claude Desktop
│
├── protocol/
│   └── types.py             Shared Pydantic types
│
├── docker-compose.yml       PostgreSQL + pgvector
├── requirements.txt
└── setup.py
```

---

## License

MIT
