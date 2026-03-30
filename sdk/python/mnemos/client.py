import requests
from typing import Optional


class MnemOS:
    """
    Python SDK for MnemOS — Universal Memory for AI Apps.

    Usage:
        from mnemos import MnemOS

        mem = MnemOS(app_id="my-app", user_id="user-123")
        mem.store("User prefers dark mode")
        results = mem.retrieve("what does the user prefer?")
    """

    def __init__(
        self,
        app_id:   str = "unknown",
        user_id:  str = "default",
        base_url: str = "http://localhost:8765",
    ):
        self.app_id   = app_id
        self.user_id  = user_id
        self.base_url = base_url.rstrip("/")

    # ─── STORE ────────────────────────────────────────────────

    def store(
        self,
        content:    str,
        type:       str   = "semantic",
        confidence: float = 0.8,
        privacy:    str   = "global",
        tags:       list  = [],
    ) -> dict:
        """Store a single memory."""
        resp = requests.post(
            f"{self.base_url}/memory/store",
            json={
                "content":    content,
                "type":       type,
                "confidence": confidence,
                "privacy":    privacy,
                "tags":       tags,
                "app_id":     self.app_id,
                "user_id":    self.user_id,
            }
        )
        resp.raise_for_status()
        return resp.json()

    # ─── RETRIEVE ─────────────────────────────────────────────

    def retrieve(
        self,
        query:          str,
        limit:          int   = 5,
        min_confidence: float = 0.5,
    ) -> list[dict]:
        """Semantic search for relevant memories."""
        resp = requests.post(
            f"{self.base_url}/memory/retrieve",
            json={
                "query":          query,
                "limit":          limit,
                "min_confidence": min_confidence,
                "app_id":         self.app_id,
                "user_id":        self.user_id,
            }
        )
        resp.raise_for_status()
        return resp.json()["memories"]

    # ─── LEARN ────────────────────────────────────────────────

    def learn(self, messages: list[dict]) -> dict:
        """
        Auto-extract memories from a conversation.

        messages format:
            [
                {"role": "user",      "content": "I love Python"},
                {"role": "assistant", "content": "Great choice!"},
            ]
        """
        resp = requests.post(
            f"{self.base_url}/memory/learn",
            json={
                "messages": messages,
                "app_id":   self.app_id,
                "user_id":  self.user_id,
            }
        )
        resp.raise_for_status()
        return resp.json()

    # ─── CONTEXT INJECTION ────────────────────────────────────

    def inject(self, query: str, limit: int = 5) -> str:
        """
        Returns a ready-to-use system prompt string with relevant memories.
        Inject this into your AI's system message.

        Usage:
            system = mem.inject("tell me about the user")
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user_message},
                ]
            )
        """
        memories = self.retrieve(query, limit=limit)
        if not memories:
            return ""
        lines = ["[Relevant memories about this user]"]
        for i, m in enumerate(memories, 1):
            lines.append(f"{i}. {m['content']}  (relevance: {m['relevance']})")
        return "\n".join(lines)

    # ─── MANAGE ───────────────────────────────────────────────

    def all(self, limit: int = 100) -> list[dict]:
        """List all memories for this user."""
        resp = requests.get(
            f"{self.base_url}/memory/all",
            params={"user_id": self.user_id, "limit": limit}
        )
        resp.raise_for_status()
        return resp.json()["memories"]

    def delete(self, memory_id: str) -> dict:
        """Delete a memory by ID."""
        resp = requests.delete(f"{self.base_url}/memory/{memory_id}")
        resp.raise_for_status()
        return resp.json()

    def stats(self) -> dict:
        """Get memory store statistics."""
        resp = requests.get(f"{self.base_url}/stats")
        resp.raise_for_status()
        return resp.json()

    def health(self) -> bool:
        """Check if MnemOS server is running."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    # ─── MODEL MANAGEMENT ─────────────────────────────────────

    def get_model(self) -> dict:
        """Get current extraction engine and model."""
        resp = requests.get(f"{self.base_url}/config")
        resp.raise_for_status()
        return resp.json()

    def set_model(self, engine: str = None, model: str = None) -> dict:
        """
        Switch extraction engine or model at runtime.

        Usage:
            mem.set_model(engine="gemini")
            mem.set_model(engine="ollama", model="qwen2.5:7b")
        """
        payload = {}
        if engine: payload["mode"]      = engine
        if model:  payload["gen_model"] = model
        resp = requests.post(f"{self.base_url}/config", json=payload)
        resp.raise_for_status()
        return resp.json()

    def list_models(self) -> list[dict]:
        """List all downloaded Ollama models."""
        resp = requests.get(f"{self.base_url}/ollama/models")
        resp.raise_for_status()
        return resp.json().get("models", [])

    def pull_model(self, model: str) -> dict:
        """
        Download an Ollama model.

        Usage:
            mem.pull_model("qwen2.5:7b")
        """
        resp = requests.post(f"{self.base_url}/ollama/pull", json={"model": model})
        resp.raise_for_status()
        return resp.json()
