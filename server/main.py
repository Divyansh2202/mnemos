import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import requests as _requests
from server.memory_store  import MemoryStore
from server.context_engine import ContextEngine, get_config, set_config
from protocol.types import Memory, MemoryQuery, StoreRequest, LearnRequest

app   = FastAPI(title="MnemOS", version="0.1.0")
store = MemoryStore()
engine = ContextEngine()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r".*",   # covers chrome-extension:// origins
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── DASHBOARD ────────────────────────────────────────────────

@app.get("/")
@app.get("/dashboard")
def dashboard():
    path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")
    return FileResponse(os.path.abspath(path))


# ─── HEALTH ───────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/stats")
def stats():
    return store.stats()


# ─── STORE ────────────────────────────────────────────────────

@app.post("/memory/store")
def store_memory(req: StoreRequest):
    memory = Memory(
        content    = req.content,
        type       = req.type,
        confidence = req.confidence,
        privacy    = req.privacy,
        tags       = req.tags,
        app_id     = req.app_id,
        entity     = req.entity,
    )
    saved = store.store(memory, user_id=req.user_id)
    return {"id": saved.id, "status": "stored"}


# ─── RETRIEVE ─────────────────────────────────────────────────

@app.post("/memory/retrieve")
def retrieve_memories(query: MemoryQuery):
    results = store.retrieve(query)
    return {"memories": results, "count": len(results)}


# ─── LEARN (extract + store from conversation) ────────────────

class LearnWithSessionRequest(LearnRequest):
    session_id: str = ""
    title:      str = ""

@app.post("/memory/learn")
def learn_from_conversation(req: LearnWithSessionRequest):
    # 1. Store raw session
    if req.messages:
        sid = req.session_id or f"{req.app_id}_{req.user_id}"
        store.upsert_session(
            session_id = sid,
            messages   = req.messages,
            user_id    = req.user_id,
            app_id     = req.app_id,
            title      = req.title,
        )

    # 2. Extract + store memories
    memories = engine.extract(req.messages, app_id=req.app_id)
    if not memories:
        return {"stored": 0, "memories": []}
    saved = store.store_batch(memories, user_id=req.user_id)
    return {
        "stored":   len(saved),
        "memories": [{"id": m.id, "content": m.content} for m in saved]
    }


# ─── MANAGE ───────────────────────────────────────────────────

@app.get("/memory/all")
def get_all(user_id: str = "default", limit: int = 100):
    return {"memories": store.get_all(user_id=user_id, limit=limit)}


@app.delete("/memory/{memory_id}")
def delete_memory(memory_id: str):
    store.delete(memory_id)
    return {"status": "deleted", "id": memory_id}


# ─── SESSIONS ─────────────────────────────────────────────────

@app.get("/sessions")
def list_sessions(user_id: str = "default", app_id: str = None, limit: int = 50):
    return {"sessions": store.get_sessions(user_id=user_id, app_id=app_id, limit=limit)}

@app.get("/sessions/{session_id}")
def get_session(session_id: str, user_id: str = "default"):
    session = store.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ─── CONFIG ───────────────────────────────────────────────────

@app.get("/config")
def get_engine_config():
    return get_config()

class ConfigUpdate(BaseModel):
    mode:       str | None = None
    gen_model:  str | None = None
    gemini_key: str | None = None

@app.post("/config")
def update_engine_config(body: ConfigUpdate):
    if body.mode:
        set_config("mode", body.mode)
    if body.gen_model:
        set_config("gen_model", body.gen_model)
    if body.gemini_key:
        # persist key to .env and reload into environment
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        _update_env(env_path, "GEMINI_API_KEY", body.gemini_key)
        os.environ["GEMINI_API_KEY"] = body.gemini_key
        engine.gemini_key = body.gemini_key
    return get_config()

def _update_env(path: str, key: str, value: str):
    import re
    try:
        with open(path) as f:
            content = f.read()
        if key in content:
            content = re.sub(rf"{key}=.*", f"{key}={value}", content)
        else:
            content += f"\n{key}={value}\n"
        with open(path, "w") as f:
            f.write(content)
    except Exception:
        pass


# ─── OLLAMA MODELS ────────────────────────────────────────────

@app.get("/ollama/models")
def list_ollama_models():
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        resp = _requests.get(f"{ollama_url}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [
            {"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)}
            for m in resp.json().get("models", [])
        ]
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


class PullRequest(BaseModel):
    model: str

@app.post("/ollama/pull")
def pull_ollama_model(req: PullRequest):
    """Pull (download) an Ollama model. Streams progress, returns when done."""
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        resp = _requests.post(
            f"{ollama_url}/api/pull",
            json={"name": req.model, "stream": False},
        )
        resp.raise_for_status()
        return {"status": "ok", "model": req.model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── RUN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("MNEMOS_HOST", "localhost")
    port = int(os.getenv("MNEMOS_PORT", 8765))
    uvicorn.run("server.main:app", host=host, port=port, reload=True)
