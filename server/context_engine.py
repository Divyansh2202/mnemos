import os
import json
import requests
from protocol.types import Memory, MemoryType

EXTRACT_PROMPT = """You are an expert memory extraction AI for a personal AI assistant. Your job is to carefully analyze a conversation and extract every meaningful fact worth remembering about the user.

Think through this step by step:

=== STEP 1: SCAN for all user facts ===
Read every line carefully. Identify anything the user reveals about themselves:
- Identity: profession, age, location, background, name (use only to refer as "User")
- Skills & knowledge: programming languages, frameworks, tools, technologies they know
- Preferences: likes, dislikes, favorites, things they avoid, editor/theme/OS choices
- Goals & plans: what they want to learn, build, create, or achieve
- Opinions & decisions: views they hold, choices they've made, things they prefer
- Events & experiences: things that happened to them (episodic memories)
- Workflows & habits: how they do things, their processes, routines (procedural)
- Projects & code plans: if user is planning a project, discussing architecture, designing a system, writing or planning code — extract WHAT they are building, WHAT stack/language/tools they plan to use, WHAT the project does
- Learning path: topics they are currently studying, roadmaps they are following, courses or resources they mention

=== STEP 2: FILTER — keep only real user facts ===
Keep: anything that reveals something stable or meaningful about the user
Discard: generic greetings ("hi", "okay", "thanks"), pure questions with no user context, filler phrases, AI responses about itself
Example — "start with step 1" alone reveals nothing → skip it
Example — "I am building a REST API in FastAPI with PostgreSQL" → extract it

=== STEP 3: WRITE memories — STRICT RULES (never break these) ===
RULE 1 (CRITICAL): Every single memory MUST start with the word "User"
  CORRECT: "User knows Python"
  CORRECT: "User is building a REST API using FastAPI and PostgreSQL"
  CORRECT: "User is planning a project that uses React frontend and Node.js backend"
  WRONG:   "Divyansh knows Python"       ← real name, forbidden
  WRONG:   "I know Python"               ← first person, forbidden
  WRONG:   "The user said they know Python" ← indirect, forbidden

RULE 2: Write in third-person declarative form — no "said", "mentioned", "told me"
  CORRECT: "User prefers VSCode with Vim keybindings"
  WRONG:   "User said they prefer VSCode"

RULE 3: Be specific and concrete — never vague
  CORRECT: "User is learning backend development using Python and FastAPI"
  WRONG:   "User is learning something about programming"

RULE 4: One distinct fact per memory entry — do not combine multiple facts

RULE 5: If the conversation contains NO meaningful facts about the user, return {{"memories": []}}

=== STEP 4: ASSIGN metadata ===
For each memory decide:
- type:
    "semantic"   → facts, skills, preferences, knowledge, current projects/plans
    "episodic"   → past events or experiences ("User attended...", "User built X last year")
    "procedural" → how-to knowledge, workflows, step-by-step processes the user follows
- confidence:
    0.95 → user stated it directly and clearly
    0.80 → clearly implied from context
    0.65 → inferred, less certain
- tags: 1-3 short lowercase tags e.g. ["skill", "python"], ["project", "backend"], ["preference", "editor"]

=== STEP 5: OUTPUT — raw JSON only ===
No explanation. No markdown. No code fences (no ```). No extra text before or after.
Return exactly this format:
{{"memories": [{{"content": "User ...", "type": "semantic", "confidence": 0.9, "tags": ["tag1", "tag2"]}}]}}

Conversation to analyze:
{conversation}

JSON:"""


import pathlib

_CONFIG_FILE = pathlib.Path(__file__).parent.parent / "mnemos_config.json"
_config: dict = {}

def _load_config():
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE) as f:
                _config.update(json.load(f))
        except Exception:
            pass

def _save_config():
    try:
        with open(_CONFIG_FILE, "w") as f:
            json.dump(_config, f, indent=2)
    except Exception:
        pass

def get_config() -> dict:
    return _config

def set_config(key: str, value: str):
    _config[key] = value
    _save_config()

_load_config()


class ContextEngine:

    def __init__(self):
        self.ollama_url  = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.gemini_key  = os.getenv("GEMINI_API_KEY", "")
        # defaults from env — can be overridden at runtime via set_config()
        _config.setdefault("mode",      os.getenv("MNEMOS_EXTRACTION", "ollama"))
        _config.setdefault("gen_model", os.getenv("OLLAMA_GEN_MODEL",  "qwen2.5:3b"))
        print(f"[ContextEngine] Mode: {_config['mode']} | Model: {_config['gen_model']}")

    @property
    def mode(self):      return _config.get("mode", "ollama")
    @property
    def gen_model(self): return _config.get("gen_model", "qwen2.5:3b")

    def extract(self, messages: list[dict], app_id: str = "unknown") -> list[Memory]:
        conversation = self._format_messages(messages)
        if not conversation.strip():
            return []
        raw = self._call_llm(conversation)
        return self._parse(raw, app_id)

    # ─── LLM BACKENDS ─────────────────────────────────────────

    def _call_llm(self, conversation: str) -> str:
        prompt = EXTRACT_PROMPT.format(conversation=conversation)
        if self.mode == "gemini":
            return self._call_gemini(prompt)
        else:
            return self._call_ollama(prompt)

    def _call_ollama(self, prompt: str) -> str:
        resp = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model":   self.gen_model,
                "prompt":  prompt,
                "stream":  False,
                "options": {"temperature": 0.1}
            },
            timeout=None
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    def _call_gemini(self, prompt: str) -> str:
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not set")
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    # ─── HELPERS ──────────────────────────────────────────────

    def _format_messages(self, messages: list[dict]) -> str:
        lines = []
        for m in messages:
            role    = m.get("role", "user").capitalize()
            content = m.get("content", "")
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _parse(self, raw: str, app_id: str) -> list[Memory]:
        import re
        raw = raw.strip()
        # Strip markdown code blocks (```json ... ``` or ``` ... ```)
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw.strip()).strip()
        # Fix trailing commas before } or ] (common LLM mistake)
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[ContextEngine] JSON parse failed: {raw[:200]}")
            return []
        # Support both {"memories": [...]} and raw [...]
        if isinstance(data, dict):
            items = data.get("memories", [])
        elif isinstance(data, list):
            items = data
        else:
            return []

        memories = []
        for item in items:
            if not isinstance(item, dict) or not item.get("content"):
                continue
            try:
                mem_type = MemoryType(item.get("type", "semantic"))
            except ValueError:
                mem_type = MemoryType.SEMANTIC
            memories.append(Memory(
                content    = item["content"].strip(),
                type       = mem_type,
                confidence = float(item.get("confidence", 0.8)),
                tags       = item.get("tags", []),
                app_id     = app_id,
            ))
        return memories
