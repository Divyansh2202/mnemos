"""
MnemOS Terminal Simulation
Behaves exactly like the browser extension:
  - You type a message (like sending on ChatGPT)
  - MnemOS retrieves memories and injects context invisibly
  - qwen2.5:7b answers (acting as the AI)
  - MnemOS extracts facts from the exchange and stores them
  - Dashboard view updates after every turn
"""

import requests
import json
import sys
import time

MNEMOS  = "http://localhost:8765"
OLLAMA  = "http://localhost:11434"
MODEL   = "qwen2.5:7b"
USER_ID = "default"
APP_ID  = "chatgpt-sim"
SEP     = "\uE000"          # same invisible delimiter the extension uses

# ── ANSI colours ────────────────────────────────────────────
R  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
PURPLE = "\033[95m"
BLUE   = "\033[94m"
RED    = "\033[91m"
WHITE  = "\033[97m"
BG_DARK = "\033[48;5;235m"

def clr(text, *codes): return "".join(codes) + str(text) + R
def bar(char="─", n=64): return clr(char * n, DIM)
def header(text): print(f"\n{clr('┌' + '─'*(len(text)+2) + '┐', DIM)}\n{clr('│', DIM)} {clr(text, BOLD, CYAN)} {clr('│', DIM)}\n{clr('└' + '─'*(len(text)+2) + '┘', DIM)}")

conversation = []   # full chat history for the session

# ── Step 1: retrieve relevant memories (extension: injectMemoryContext) ──
def retrieve_memories(query: str) -> list[dict]:
    try:
        r = requests.post(f"{MNEMOS}/memory/retrieve", json={
            "query":   query,
            "user_id": USER_ID,
            "app_id":  APP_ID,
            "limit":   5,
        })
        return r.json().get("memories", [])
    except Exception:
        return []

# ── Step 2: inject context into message (extension: injectMemoryContext) ──
def inject_context(user_msg: str, memories: list[dict]) -> str:
    if not memories:
        return user_msg
    ctx = "\n".join(f"- {m['content']}" for m in memories)
    return f"[Memory Context from MnemOS]\n{ctx}\n{SEP}{user_msg}"

# ── Step 3: clean injected message before storing (extension: cleanMessages) ──
def clean_message(content: str) -> str:
    idx = content.find(SEP)
    if idx != -1:
        return content[idx + 1:].strip()
    return content

# ── Step 4: call AI (qwen2.5:7b via Ollama, acting as ChatGPT) ─────────
def call_ai(injected_msg: str, history: list[dict]) -> str:
    messages = [
        {"role": "system", "content": (
            "You are a helpful AI assistant. "
            "If the user message begins with '[Memory Context from MnemOS]', "
            "use those facts as background knowledge about the user to give "
            "a personalised response. Do NOT mention that you received memory context."
        )}
    ]
    # add prior conversation (cleaned)
    for turn in history[:-1]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    # current user message (injected)
    messages.append({"role": "user", "content": injected_msg})

    print(clr("  thinking", DIM), end="", flush=True)
    start = time.perf_counter()
    resp = requests.post(f"{OLLAMA}/api/chat", json={
        "model":    MODEL,
        "messages": messages,
        "stream":   True,
        "options":  {"temperature": 0.7, "num_gpu": -1},
    }, stream=True)

    full = ""
    first_token = True
    for line in resp.iter_lines():
        if not line:
            continue
        data = json.loads(line)
        token = data.get("message", {}).get("content", "")
        if token:
            if first_token:
                elapsed = time.perf_counter() - start
                # clear "thinking..." and move to new line
                print(f"\r{clr(f'  ⚡ first token: {elapsed:.2f}s', DIM)}")
                print(f"\n{clr('  GPT', BOLD, GREEN)}  ", end="", flush=True)
                first_token = False
            print(token, end="", flush=True)
            full += token
        if data.get("done"):
            elapsed = time.perf_counter() - start
            print(f"\n{clr(f'  total: {elapsed:.1f}s', DIM)}")
            break
    return full

# ── Step 5: learn from conversation (extension: background.js LEARN) ────
def learn(user_msg: str, ai_reply: str) -> dict:
    r = requests.post(f"{MNEMOS}/memory/learn", json={
        "messages":   [
            {"role": "user",      "content": user_msg},
            {"role": "assistant", "content": ai_reply},
        ],
        "app_id":     APP_ID,
        "user_id":    USER_ID,
        "session_id": "terminal-sim",
    })
    return r.json()

# ── Dashboard view (popup + dashboard combined) ───────────────────────
def show_dashboard():
    stats = requests.get(f"{MNEMOS}/stats").json()
    mems  = requests.get(f"{MNEMOS}/memory/all?user_id={USER_ID}&limit=8").json().get("memories", [])
    cfg   = requests.get(f"{MNEMOS}/config").json()

    print(f"\n{bar()}")
    print(clr("  DASHBOARD", BOLD, PURPLE))
    print(bar())
    print(f"  {clr('Engine :', DIM)}  {clr(cfg.get('mode','?'), CYAN)}  /  {clr(cfg.get('gen_model','?'), CYAN)}")
    print(f"  {clr('Device :', DIM)}  {clr('GPU (RTX 4070)', GREEN)}")
    print(f"  {clr('Memories:', DIM)} {clr(stats.get('total_memories', 0), BOLD, YELLOW)}")
    if mems:
        print(f"  {clr('Recent memories:', DIM)}")
        for m in mems:
            tag  = clr(f"[{m['type'][:3]}]", DIM)
            conf = clr(f"{m['confidence']:.2f}", YELLOW)
            print(f"    {tag} {conf}  {m['content'][:65]}")
    print(bar())

# ── MAIN LOOP ────────────────────────────────────────────────────────────
def main():
    header("MnemOS Terminal Simulation  —  GPT + Memory")
    print(clr("  Extension flow simulated in terminal.", DIM))
    print(clr("  Type a message and press Enter. Type 'exit' to quit.\n", DIM))

    show_dashboard()

    turn = 0
    while True:
        turn += 1
        print(f"\n{bar('═')}")
        try:
            user_input = input(clr(f"  YOU  ", BOLD, BLUE) + " ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n" + clr("  Bye!", DIM))
            break

        if user_input.lower() in ("exit", "quit", "q"):
            print(clr("  Bye!", DIM))
            break
        if not user_input:
            continue

        print()

        # ── STEP 1: Retrieve ─────────────────────────────────
        t0 = time.perf_counter()
        memories = retrieve_memories(user_input)
        t_retrieve = time.perf_counter() - t0

        if memories:
            print(clr(f"  [INJECT] {len(memories)} memories retrieved ({t_retrieve*1000:.0f}ms)", YELLOW))
            for m in memories:
                print(clr(f"    · [{m['relevance']:.3f}] {m['content'][:70]}", DIM))
        else:
            print(clr(f"  [INJECT] No memories yet ({t_retrieve*1000:.0f}ms)", DIM))

        # ── STEP 2: Inject context ────────────────────────────
        injected = inject_context(user_input, memories)
        if memories:
            print(clr(f"  [INJECT] Context prepended invisibly before sending", DIM))

        # ── STEP 3: Add to conversation history ──────────────
        conversation.append({"role": "user", "content": user_input})

        # ── STEP 4: AI responds ───────────────────────────────
        print(clr(f"\n  [AI] qwen2.5:7b generating response...", DIM))
        ai_reply = call_ai(injected, conversation)
        conversation.append({"role": "assistant", "content": ai_reply})

        # ── STEP 5: Learn ─────────────────────────────────────
        clean_user = clean_message(injected)
        print(clr(f"\n  [LEARN] Extracting memories from this exchange...", DIM), end="", flush=True)
        t0 = time.perf_counter()
        result = learn(clean_user, ai_reply)
        t_learn = time.perf_counter() - t0
        stored = result.get("stored", 0)

        if stored > 0:
            print(clr(f"\r  [LEARN] {stored} new {'memory' if stored==1 else 'memories'} stored  ({t_learn:.1f}s)", GREEN))
            for m in result.get("memories", []):
                print(clr(f"    + {m['content'][:70]}", GREEN))
        else:
            print(clr(f"\r  [LEARN] No new facts extracted ({t_learn:.1f}s)", DIM))

        # ── Dashboard update ──────────────────────────────────
        show_dashboard()

if __name__ == "__main__":
    main()
