import os
import json
import requests
from protocol.types import Memory, MemoryType

EXTRACT_PROMPT = """You are a memory extraction system. Extract ALL facts worth remembering from this conversation.

Return ONLY valid JSON in this exact format:
{{"memories": [{{"content": "...", "type": "semantic", "confidence": 0.9, "tags": []}}]}}

Types: semantic (facts/preferences/knowledge), episodic (events/experiences), procedural (how-to/workflows)

Rules:
- ALWAYS start every memory with "User" — never use the person's real name (e.g. "User knows Python", NOT "Divyansh knows Python")
- Extract EVERY preference, hobby, tool, skill, topic, decision, and fact mentioned
- User likes/dislikes/loves/hates something = ALWAYS extract it
- If user mentions a topic (music, coding, food, etc.) = extract it
- Be generous — extract as much as possible

Conversation:
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
